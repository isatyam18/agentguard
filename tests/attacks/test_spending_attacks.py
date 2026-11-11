"""Pytest suite for spending attack scenarios (Scenarios 1 through 6).

Verifies that all spending boundary bypass attempts, unauthorized merchants,
currency tampering, and duplicate/replay requests are strictly blocked
without ever invoking PayPal payment rails.
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
from tests.attacks.payloads import get_spending_attacks


@pytest.fixture(autouse=True)
def setup_spending_policy():
    """Seed default active policy with allowlisted merchants and spending caps."""
    init_db()
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
async def test_spending_attack_1_purchase_above_100():
    """Scenario 1: Purchase above $100 limit must be unconditionally blocked."""
    attack = next(a for a in get_spending_attacks() if a["id"] == 1)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert res.get("paypal_authorization_id") is None
    assert any("MAX_TRANSACTION_LIMIT_EXCEEDED" in str(v) for v in res.get("policy_violations", []))
    session.close()


@pytest.mark.asyncio
async def test_spending_attack_2_exceed_daily_500():
    """Scenario 2: Cumulative daily spending exceeding $500 must block subsequent purchase."""
    session = SessionFactory()

    # Pre-seed $450 in cumulative spending today across allowlisted purchases
    prior_tx = Transaction(
        external_reference="TXN-PRIOR-SPENT-450",
        merchant_name="AWS",
        merchant_id="aws_cloud",
        amount=Decimal("450.00"),
        currency="USD",
        description="Prior daily compute spend",
        risk_score=Decimal("0.10"),
        decision="APPROVE",
        payment_status="AUTHORIZED",
    )
    session.add(prior_tx)
    session.commit()

    attack = next(a for a in get_spending_attacks() if a["id"] == 2)
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert any("DAILY_SPENDING_LIMIT_EXCEEDED" in str(v) for v in res.get("policy_violations", []))
    session.close()


@pytest.mark.asyncio
async def test_spending_attack_3_unauthorized_merchant():
    """Scenario 3: Purchase from unauthorized vendor not on allowlist must block."""
    attack = next(a for a in get_spending_attacks() if a["id"] == 3)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert any("MERCHANT_NOT_ALLOWLISTED" in str(v) for v in res.get("policy_violations", []))
    session.close()


@pytest.mark.asyncio
async def test_spending_attack_4_currency_manipulation():
    """Scenario 4: Currency manipulation with unsupported denomination must block."""
    attack = next(a for a in get_spending_attacks() if a["id"] == 4)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert any("INVALID_CURRENCY" in str(v) for v in res.get("policy_violations", []))
    session.close()


@pytest.mark.asyncio
async def test_spending_attack_5_duplicate_transaction():
    """Scenario 5: Submitting duplicate transaction attempt must be blocked before calling PayPal."""
    attack = next(a for a in get_spending_attacks() if a["id"] == 5)
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
async def test_spending_attack_6_replayed_request():
    """Scenario 6: Replaying an already settled transaction must be blocked before calling PayPal."""
    attack = next(a for a in get_spending_attacks() if a["id"] == 6)
    session = SessionFactory()
    paypal = PayPalClient()
    gateway = AgentGuardMCPGateway(session=session, paypal_client=paypal)

    res = await gateway.request_purchase(**attack["payload"])

    assert res["decision"] == "BLOCK"
    assert res["payment_status"] == "BLOCKED"
    assert res.get("paypal_order_id") is None
    assert "INVOICE_MANIPULATION" in res.get("security_threats", [])
    session.close()
