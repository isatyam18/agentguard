"""Tests for CRUD operations across all database models."""

from datetime import datetime, timezone
from decimal import Decimal
import uuid
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.policy import Policy
from agentguard.models.transaction import Transaction


def test_transaction_crud(db_session: Session, sample_transaction_data: dict) -> None:
    """Test full CRUD lifecycle for Transaction model."""
    # Create
    txn = Transaction(**sample_transaction_data)
    db_session.add(txn)
    db_session.flush()

    assert txn.id is not None
    assert uuid.UUID(txn.id)  # Verifies valid UUID string
    assert txn.amount == Decimal("49.99")
    assert isinstance(txn.amount, Decimal)

    # Read
    fetched = db_session.get(Transaction, txn.id)
    assert fetched is not None
    assert fetched.external_reference == sample_transaction_data["external_reference"]
    assert fetched.merchant_name == "Anthropic API"

    # Update
    fetched.decision = "ALLOW"
    fetched.payment_status = "AUTHORIZED"
    fetched.paypal_authorization_id = "AUTH-PAYPAL-123"
    db_session.flush()

    updated = db_session.get(Transaction, txn.id)
    assert updated.decision == "ALLOW"
    assert updated.payment_status == "AUTHORIZED"
    assert updated.paypal_authorization_id == "AUTH-PAYPAL-123"

    # Delete
    db_session.delete(updated)
    db_session.flush()
    assert db_session.get(Transaction, txn.id) is None


def test_policy_crud(db_session: Session) -> None:
    """Test full CRUD lifecycle for Policy model."""
    policy = Policy(
        max_transaction_amount=Decimal("100.00"),
        daily_spending_limit=Decimal("500.00"),
        allowed_merchants=["OpenAI", "AWS", "GitHub"],
        require_human_approval=True,
        is_active=True,
    )
    db_session.add(policy)
    db_session.flush()

    assert policy.id is not None
    assert uuid.UUID(policy.id)
    assert policy.max_transaction_amount == Decimal("100.00")
    assert isinstance(policy.max_transaction_amount, Decimal)
    assert "OpenAI" in policy.allowed_merchants

    # Read
    fetched = db_session.get(Policy, policy.id)
    assert fetched is not None
    assert fetched.is_active is True

    # Update
    fetched.daily_spending_limit = Decimal("750.00")
    fetched.is_active = False
    db_session.flush()

    updated = db_session.get(Policy, policy.id)
    assert updated.daily_spending_limit == Decimal("750.00")
    assert updated.is_active is False


def test_approval_crud_and_relationship(db_session: Session, sample_transaction_data: dict) -> None:
    """Test Approval CRUD and relationship linking with Transaction."""
    txn = Transaction(**sample_transaction_data)
    db_session.add(txn)
    db_session.flush()

    approval = Approval(
        transaction_id=txn.id,
        status="PENDING",
        reason="Transaction amount exceeds autonomous threshold",
    )
    db_session.add(approval)
    db_session.flush()

    assert approval.id is not None
    assert uuid.UUID(approval.id)
    assert approval.transaction_id == txn.id
    assert approval.transaction.external_reference == txn.external_reference

    # Update: Resolve approval
    approval.status = "APPROVED"
    approval.reviewer = "security_lead"
    approval.reason = "Approved for infrastructure token purchase"
    approval.resolved_at = datetime.now(timezone.utc)
    db_session.flush()

    resolved = db_session.get(Approval, approval.id)
    assert resolved.status == "APPROVED"
    assert resolved.reviewer == "security_lead"
    assert resolved.resolved_at is not None


def test_audit_log_crud(db_session: Session, sample_transaction_data: dict) -> None:
    """Test AuditLog record creation and JSON details retrieval."""
    txn = Transaction(**sample_transaction_data)
    db_session.add(txn)
    db_session.flush()

    audit = AuditLog(
        transaction_id=txn.id,
        event_type="FIREWALL_POLICY_EVALUATED",
        actor="system:firewall",
        details={
            "rules_checked": ["max_limit", "vendor_allowlist"],
            "result": "PASSED",
            "score": 0.05,
        },
    )
    db_session.add(audit)
    db_session.flush()

    assert audit.id is not None
    assert uuid.UUID(audit.id)
    assert audit.transaction_id == txn.id
    assert audit.details["result"] == "PASSED"

    # Query by event_type
    entries = db_session.scalars(
        select(AuditLog).where(AuditLog.event_type == "FIREWALL_POLICY_EVALUATED")
    ).all()
    assert len(entries) >= 1
