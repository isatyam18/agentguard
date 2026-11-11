"""Pytest suite for invoice manipulation attacks (Scenarios 13 through 18).

Verifies that crypto diversion notes, merchant ID spoofing, line item math manipulation,
duplicate invoice IDs, free webmail impersonation, and phishing lookalike URLs are all blocked
without ever initiating PayPal money-moving operations.
"""

from decimal import Decimal
import pytest

from agentguard.core.database import SessionFactory, init_db
from agentguard.mcp.gateway import AgentGuardMCPGateway
from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.policy import Policy
from agentguard.models.transaction import Transaction
from agentguard.paypal.client import PayPalClient
from agentguard.security.invoice_scanner import InvoiceScanner
from tests.attacks.payloads import get_invoice_manipulation_attacks


@pytest.fixture(autouse=True)
def setup_invoice_policy():
    """Seed clean database with active buyer policy."""
    init_db()
    InvoiceScanner.reset_seen_invoices()
    session = SessionFactory()
    try:
        session.query(AuditLog).delete()
        session.query(Approval).delete()
        session.query(Transaction).delete()
        session.query(Policy).delete()

        policy = Policy(
            max_transaction_amount=Decimal("100.00"),
            daily_spending_limit=Decimal("500.00"),
            allowed_merchants=["github_copilot", "aws_cloud", "openai", "slack", "digitalocean"],
            require_human_approval=False,
            is_active=True,
        )
        session.add(policy)
        session.commit()
    finally:
        session.close()


@pytest.mark.asyncio
async def test_invoice_manipulation_13_crypto_instructions():
    """Scenario 13: Fake cryptocurrency payment instructions must be blocked."""
    attack = next(a for a in get_invoice_manipulation_attacks() if a["id"] == 13)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert any(t in ("PHISHING", "UNUSUAL_BEHAVIOR") for t in res.get("security_threats", []))
    session.close()


@pytest.mark.asyncio
async def test_invoice_manipulation_14_merchant_mismatch():
    """Scenario 14: Merchant identity mismatch (Name claims AWS, ID is rogue) must be blocked."""
    attack = next(a for a in get_invoice_manipulation_attacks() if a["id"] == 14)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    session.close()


@pytest.mark.asyncio
async def test_invoice_manipulation_15_modified_amount_math():
    """Scenario 15: Modified invoice amount with inconsistent line item sum must be blocked."""
    attack = next(a for a in get_invoice_manipulation_attacks() if a["id"] == 15)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert "INVOICE_MANIPULATION" in res.get("security_threats", [])
    session.close()


@pytest.mark.asyncio
async def test_invoice_manipulation_16_duplicate_invoice_id():
    """Scenario 16: Duplicate invoice ID submission must be blocked."""
    # Pre-register the invoice ID as already processed
    InvoiceScanner._SEEN_INVOICE_IDS.add("INV-DUP-PREVIOUS-PAID")

    attack = next(a for a in get_invoice_manipulation_attacks() if a["id"] == 16)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert "INVOICE_MANIPULATION" in res.get("security_threats", [])
    session.close()


@pytest.mark.asyncio
async def test_invoice_manipulation_17_fake_support_contact():
    """Scenario 17: Enterprise invoice with free webmail support address must be blocked."""
    attack = next(a for a in get_invoice_manipulation_attacks() if a["id"] == 17)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert "PHISHING" in res.get("security_threats", [])
    session.close()


@pytest.mark.asyncio
async def test_invoice_manipulation_18_suspicious_payment_url():
    """Scenario 18: Brand lookalike / typosquatting payment URL must be blocked."""
    attack = next(a for a in get_invoice_manipulation_attacks() if a["id"] == 18)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert "PHISHING" in res.get("security_threats", [])
    session.close()
