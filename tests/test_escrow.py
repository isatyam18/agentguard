"""Verification suite for Milestone 6: Human Approval and Escrow Workflow.

Tests all state machine transitions, concurrent human approvals, duplicate resolution prevention,
PayPal capture/void execution, downstream failure handling, and AI agent self-approval prevention.
"""

from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
import pytest
import uuid

from agentguard.core.database import SessionFactory, init_db
from agentguard.escrow.exceptions import (
    AlreadyCapturedError,
    AlreadyVoidedError,
    DuplicateApprovalError,
    EscrowExecutionError,
    InvalidStateTransitionError,
    UnauthorizedReviewerError,
)
from agentguard.escrow.service import EscrowWorkflowService
from agentguard.escrow.state_machine import TransactionState, can_transition, validate_transition
from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.transaction import Transaction
from agentguard.paypal.client import PayPalClient
from agentguard.paypal.exceptions import PayPalApiError

ADMIN_TOKEN = "admin-secret-key-2026"  # [REDACTED]


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure hermetic database state for every escrow test."""
    init_db()
    session = SessionFactory()
    try:
        session.query(AuditLog).delete()
        session.query(Approval).delete()
        session.query(Transaction).delete()
        session.commit()
    finally:
        session.close()


def create_held_transaction(
    amount: Decimal = Decimal("150.00"),
    status: str = TransactionState.REVIEW_REQUIRED.value,
    with_auth_id: bool = True,
) -> tuple[str, str]:
    """Helper creating a transaction and associated pending approval record."""
    session = SessionFactory()
    try:
        txn_id = str(uuid.uuid4())
        appr_id = str(uuid.uuid4())
        auth_id = f"MOCK-AUTH-{uuid.uuid4().hex[:10].upper()}" if with_auth_id else None

        txn = Transaction(
            id=txn_id,
            external_reference=f"REF-{uuid.uuid4().hex[:8]}",
            merchant_name="Contractor Corp",
            merchant_id="m-contractor",
            amount=amount,
            currency="USD",
            description="Milestone 1 Deliverable",
            risk_score=Decimal("0.65"),
            decision="REVIEW",
            payment_status=status,
            paypal_order_id=f"MOCK-ORD-{uuid.uuid4().hex[:10].upper()}" if with_auth_id else None,
            paypal_authorization_id=auth_id,
        )
        appr = Approval(
            id=appr_id,
            transaction_id=txn_id,
            status="PENDING",
            reason="Exceeds autonomous spending threshold ($150.00 > $100.00).",
        )
        session.add(txn)
        session.add(appr)
        session.commit()
        return txn_id, appr_id
    finally:
        session.close()


def test_approve_and_capture_success():
    """Verify that human approval successfully triggers PayPal capture and transitions state to CAPTURED."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("150.00"))
    service = EscrowWorkflowService()

    result = service.approve_and_capture(
        approval_id=appr_id,
        reviewer_name="senior_finance_operator",
        reviewer_token=ADMIN_TOKEN,
        reason="Deliverable verified against contract requirements.",
        idempotency_key=f"APP-{appr_id}",
    )

    assert result["status"] == "APPROVED"
    assert result["payment_status"] == TransactionState.CAPTURED.value
    assert result["capture_id"] is not None

    # Verify DB records
    session = SessionFactory()
    try:
        txn = session.query(Transaction).filter(Transaction.id == txn_id).first()
        appr = session.query(Approval).filter(Approval.id == appr_id).first()
        assert txn.payment_status == TransactionState.CAPTURED.value
        assert txn.decision == "APPROVED"
        assert appr.status == "APPROVED"
        assert appr.reviewer == "senior_finance_operator"
        assert appr.resolved_at is not None

        # Verify state transition audit log exists
        state_log = (
            session.query(AuditLog)
            .filter(
                AuditLog.transaction_id == txn_id,
                AuditLog.event_type == "TRANSACTION_STATE_TRANSITION",
            )
            .first()
        )
        assert state_log is not None
        assert state_log.details["to_state"] == TransactionState.APPROVED_FOR_CAPTURE.value
    finally:
        session.close()


def test_reject_and_void_success():
    """Verify that human rejection triggers PayPal void and transitions state to VOIDED."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("200.00"))
    service = EscrowWorkflowService()

    result = service.reject_and_void(
        approval_id=appr_id,
        reviewer_name="compliance_officer",
        reviewer_token=ADMIN_TOKEN,
        reason="Milestone deliverable failed acceptance tests.",
        idempotency_key=f"REJ-{appr_id}",
    )

    assert result["status"] == "REJECTED"
    assert result["payment_status"] == TransactionState.VOIDED.value

    # Verify DB records
    session = SessionFactory()
    try:
        txn = session.query(Transaction).filter(Transaction.id == txn_id).first()
        appr = session.query(Approval).filter(Approval.id == appr_id).first()
        assert txn.payment_status == TransactionState.VOIDED.value
        assert txn.decision == "REJECTED"
        assert appr.status == "REJECTED"
        assert appr.reviewer == "compliance_officer"
    finally:
        session.close()


def test_duplicate_approval_prevention():
    """Verify that attempting to resolve an already approved transaction raises DuplicateApprovalError."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("120.00"))
    service = EscrowWorkflowService()

    # First resolution: Successful
    service.approve_and_capture(
        approval_id=appr_id,
        reviewer_name="human_lead",
        reviewer_token=ADMIN_TOKEN,
    )

    # Second resolution: Must fail with DuplicateApprovalError
    with pytest.raises(DuplicateApprovalError):
        service.approve_and_capture(
            approval_id=appr_id,
            reviewer_name="human_lead",
            reviewer_token=ADMIN_TOKEN,
        )

    # Rejection on already approved task must also fail with DuplicateApprovalError
    with pytest.raises(DuplicateApprovalError):
        service.reject_and_void(
            approval_id=appr_id,
            reviewer_name="human_lead",
            reviewer_token=ADMIN_TOKEN,
        )


def test_concurrent_approvals_race_condition():
    """Verify thread-safe concurrency protection: exactly one parallel approval succeeds."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("300.00"))

    def attempt_approve(reviewer: str):
        svc = EscrowWorkflowService()
        return svc.approve_and_capture(
            approval_id=appr_id,
            reviewer_name=reviewer,
            reviewer_token=ADMIN_TOKEN,
            reason="Concurrent test attempt",
        )

    results = []
    errors = []

    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = [executor.submit(attempt_approve, f"reviewer_{i}") for i in range(5)]
        for f in futures:
            try:
                results.append(f.result())
            except Exception as e:
                errors.append(e)

    # Invariant: Exactly one approval must succeed
    assert len(results) == 1
    assert results[0]["status"] == "APPROVED"
    assert results[0]["payment_status"] == TransactionState.CAPTURED.value

    # Invariant: All other 4 attempts must fail with DuplicateApprovalError
    assert len(errors) == 4
    for err in errors:
        assert isinstance(err, (DuplicateApprovalError, AlreadyCapturedError))


def test_invalid_state_transitions():
    """Verify that illegal state transitions are strictly blocked by state machine."""
    # 1. Cannot capture an already captured transaction
    with pytest.raises(AlreadyCapturedError):
        validate_transition(TransactionState.CAPTURED, TransactionState.CAPTURED)

    with pytest.raises(AlreadyCapturedError):
        validate_transition(TransactionState.CAPTURED, TransactionState.VOIDED)

    # 2. Cannot capture a voided authorization
    with pytest.raises(AlreadyVoidedError):
        validate_transition(TransactionState.VOIDED, TransactionState.CAPTURED)

    with pytest.raises(AlreadyVoidedError):
        validate_transition(TransactionState.VOIDED, TransactionState.APPROVED_FOR_CAPTURE)

    # 3. Cannot transition out of BLOCKED
    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransactionState.BLOCKED, TransactionState.CAPTURED)

    with pytest.raises(InvalidStateTransitionError):
        validate_transition(TransactionState.BLOCKED, TransactionState.AUTHORIZED)


def test_failed_paypal_capture_transitions_to_failed(monkeypatch):
    """Verify that a downstream PayPal capture error transitions transaction to FAILED."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("175.00"))

    # Mock PayPal capture to throw an API exception
    def mock_capture_failure(*args, **kwargs):
        raise PayPalApiError("Simulated PayPal card network gateway decline (500).", status_code=500)

    monkeypatch.setattr("agentguard.paypal.payments.PayPalPayments.capture_authorization", mock_capture_failure)

    service = EscrowWorkflowService()
    with pytest.raises(EscrowExecutionError) as exc_info:
        service.approve_and_capture(
            approval_id=appr_id,
            reviewer_name="operator_bob",
            reviewer_token=ADMIN_TOKEN,
        )

    assert "PayPal capture execution failed" in str(exc_info.value)

    # Verify transaction transitioned to FAILED
    session = SessionFactory()
    try:
        txn = session.query(Transaction).filter(Transaction.id == txn_id).first()
        assert txn.payment_status == TransactionState.FAILED.value

        fail_log = (
            session.query(AuditLog)
            .filter(
                AuditLog.transaction_id == txn_id,
                AuditLog.event_type == "PAYPAL_CAPTURE_FAILED",
            )
            .first()
        )
        assert fail_log is not None
    finally:
        session.close()


def test_failed_paypal_void_transitions_to_failed(monkeypatch):
    """Verify that a downstream PayPal void error transitions transaction to FAILED."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("175.00"))

    # Mock PayPal void to throw an API exception
    def mock_void_failure(*args, **kwargs):
        raise PayPalApiError("Simulated PayPal void timeout error.", status_code=504)

    monkeypatch.setattr("agentguard.paypal.payments.PayPalPayments.void_authorization", mock_void_failure)

    service = EscrowWorkflowService()
    with pytest.raises(EscrowExecutionError) as exc_info:
        service.reject_and_void(
            approval_id=appr_id,
            reviewer_name="operator_bob",
            reviewer_token=ADMIN_TOKEN,
        )

    assert "PayPal void execution failed" in str(exc_info.value)

    # Verify transaction transitioned to FAILED
    session = SessionFactory()
    try:
        txn = session.query(Transaction).filter(Transaction.id == txn_id).first()
        assert txn.payment_status == TransactionState.FAILED.value
    finally:
        session.close()


def test_ai_buyer_agent_cannot_approve_own_transaction():
    """Verify that an AI buyer agent is strictly prohibited from approving its own transactions."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("95.00"))
    service = EscrowWorkflowService()

    prohibited_agent_names = [
        "mcp_buyer_agent",
        "buyer_agent",
        "buyer_agent_001",
        "agent:autonomous_procurement",
        "agent_buyer",
    ]

    for agent_name in prohibited_agent_names:
        with pytest.raises(UnauthorizedReviewerError) as exc_info:
            service.approve_and_capture(
                approval_id=appr_id,
                reviewer_name=agent_name,
                reviewer_token=ADMIN_TOKEN,
            )
        assert "Autonomous AI buyer agents are strictly prohibited" in str(exc_info.value)


def test_unauthenticated_human_approval_rejected():
    """Verify that an approval attempt without a valid admin token is rejected."""
    txn_id, appr_id = create_held_transaction(amount=Decimal("100.00"))
    service = EscrowWorkflowService()

    # Missing token
    with pytest.raises(UnauthorizedReviewerError):
        service.approve_and_capture(
            approval_id=appr_id,
            reviewer_name="human_operator",
            reviewer_token=None,
        )

    # Invalid token
    with pytest.raises(UnauthorizedReviewerError):
        service.approve_and_capture(
            approval_id=appr_id,
            reviewer_name="human_operator",
            reviewer_token="invalid-admin-token",
        )


def test_reviewer_sees_transaction_details_and_security_evidence():
    """Verify that human reviewer retrieves complete transaction data, risk telemetry, and audit trail."""
    session = SessionFactory()
    try:
        txn_id = str(uuid.uuid4())
        appr_id = str(uuid.uuid4())

        txn = Transaction(
            id=txn_id,
            external_reference="REF-SEC-EVIDENCE",
            merchant_name="Security Audit Store",
            merchant_id="m-audit",
            amount=Decimal("75.00"),
            currency="USD",
            description="Consulting with security findings",
            risk_score=Decimal("0.55"),
            decision="REVIEW",
            payment_status=TransactionState.REVIEW_REQUIRED.value,
        )
        appr = Approval(
            id=appr_id,
            transaction_id=txn_id,
            status="PENDING",
            reason="Uncertain metadata requires human sign-off.",
        )
        log1 = AuditLog(
            transaction_id=txn_id,
            event_type="INVOICE_SECURITY_SCAN",
            actor="invoice_scanner",
            details={"scanner_threats": ["UNUSUAL_BEHAVIOR", "URGENCY_DEMAND"]},
        )
        log2 = AuditLog(
            transaction_id=txn_id,
            event_type="POLICY_FIREWALL_EVALUATION",
            actor="policy_firewall",
            details={"policy_violations": ["SUSPICIOUS_METADATA_DETECTED"]},
        )
        session.add_all([txn, appr, log1, log2])
        session.commit()
    finally:
        session.close()

    service = EscrowWorkflowService()
    details = service.get_review_details(approval_id=appr_id)

    assert details["approval_id"] == appr_id
    assert details["transaction_id"] == txn_id
    assert details["merchant_name"] == "Security Audit Store"
    assert details["amount"] == "75.00"
    assert details["risk_score"] == 55
    assert any("UNUSUAL_BEHAVIOR" in t for t in details["security_evidence"])
    assert "SUSPICIOUS_METADATA_DETECTED" in details["policy_violations"]
    assert "INVOICE_SECURITY_SCAN" in details["audit_events"]
