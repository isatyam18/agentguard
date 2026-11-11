"""Pytest suite for benign purchase scenarios (Scenarios 19 through 22).

Verifies that valid, compliant agent purchases from approved merchants
with consistent line item totals and ordinary notes are seamlessly authorized
via PayPal with intent: AUTHORIZE, proving zero false positives.
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
from tests.benign.payloads import get_benign_scenarios


@pytest.fixture(autouse=True)
def setup_benign_policy():
    """Seed clean database with active buyer policy allowing test merchants."""
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
async def test_benign_19_normal_25_purchase():
    """Scenario 19: Normal $25 purchase from approved merchant must be approved & authorized."""
    benign = next(b for b in get_benign_scenarios() if b["id"] == 19)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**benign["payload"])

    assert res["decision"] == "APPROVE"
    assert res["payment_status"] == "AUTHORIZED"
    assert res.get("paypal_order_id") is not None
    assert res.get("paypal_authorization_id") is not None
    assert res.get("risk_score") < 35
    session.close()


@pytest.mark.asyncio
async def test_benign_20_normal_75_purchase():
    """Scenario 20: Normal $75 purchase from approved merchant must be approved & authorized."""
    benign = next(b for b in get_benign_scenarios() if b["id"] == 20)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**benign["payload"])

    assert res["decision"] == "APPROVE"
    assert res["payment_status"] == "AUTHORIZED"
    assert res.get("paypal_order_id") is not None
    assert res.get("paypal_authorization_id") is not None
    assert res.get("risk_score") < 35
    session.close()


@pytest.mark.asyncio
async def test_benign_21_repeat_purchase():
    """Scenario 21: Repeat purchase within limits must be approved & authorized."""
    benign = next(b for b in get_benign_scenarios() if b["id"] == 21)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    # First purchase of $20
    res1 = await gateway.request_purchase(**benign["payload"])
    assert res1["decision"] == "APPROVE"

    # Second successive purchase of $20 with unique reference
    p2 = dict(benign["payload"])
    p2["invoice"] = {"invoice_id": "INV-BENIGN-21-B", "notes": "Second refill"}
    res2 = await gateway.request_purchase(**p2)

    assert res2["decision"] == "APPROVE"
    assert res2["payment_status"] == "AUTHORIZED"
    assert res2.get("paypal_order_id") is not None
    session.close()


@pytest.mark.asyncio
async def test_benign_22_valid_invoice_notes():
    """Scenario 22: Valid invoice with ordinary payment notes must be approved & authorized."""
    benign = next(b for b in get_benign_scenarios() if b["id"] == 22)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**benign["payload"])

    assert res["decision"] == "APPROVE"
    assert res["payment_status"] == "AUTHORIZED"
    assert res.get("paypal_order_id") is not None
    assert res.get("paypal_authorization_id") is not None
    assert res.get("risk_score") < 35
    session.close()
