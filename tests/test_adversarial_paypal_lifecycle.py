"""Adversarial Security Regression Tests for AgentGuard PayPal Payment Lifecycle.

Tests attack vectors and failure modes in:
1. Approval bypass via unauthenticated /decide endpoint (SEC-ADV-001)
2. Concurrent capture race condition in capture_transaction (SEC-ADV-002)
3. Trapped escrow funds due to irreversible FAILED terminal state (SEC-ADV-003)
4. PayPal-Request-Id header exceeding PayPal's 36-character limit (SEC-ADV-004)
5. Voided/failed transactions artificially exhausting daily velocity (SEC-ADV-005)
6. Reviewer name blacklist bypass via alternative agent naming (SEC-ADV-006)
7. Unauthenticated transaction injection via POST /api/v1/transactions (SEC-ADV-007)
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal
import threading
import uuid
import pytest
from fastapi.testclient import TestClient

from agentguard.core.config import get_settings
from agentguard.core.database import SessionFactory, init_db
from agentguard.escrow.exceptions import (
    AlreadyCapturedError,
    AlreadyVoidedError,
    InvalidStateTransitionError,
    UnauthorizedReviewerError,
)
from agentguard.escrow.service import EscrowWorkflowService
from agentguard.escrow.state_machine import TransactionState
from agentguard.main import app
from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.policy import Policy
from agentguard.models.transaction import Transaction
from agentguard.paypal.client import PayPalClient
from agentguard.paypal.exceptions import PayPalTimeoutError


@pytest.fixture(autouse=True)
def clean_db():
    """Ensure clean hermetic database state for every adversarial test."""
    init_db()
    session = SessionFactory()
    try:
        session.query(AuditLog).delete()
        session.query(Approval).delete()
        session.query(Transaction).delete()
        session.commit()
    finally:
        session.close()


def test_adv_001_approval_bypass_without_admin_token():
    """SEC-ADV-001: An untrusted agent can approve escrow without X-Admin-Token via /decide.
    
    Vulnerability:
    In `src/agentguard/api/routes/approvals.py:181`, `decide_approval` sets:
    `admin_token = x_admin_token or settings.admin_api_key.get_secret_value()`
    When a request omits `X-Admin-Token`, the backend supplies its own administrative secret,
    allowing anyone who knows or discovers an `approval_id` to approve transactions and trigger capture!
    """
    client = TestClient(app)
    session = SessionFactory()

    txn_id = str(uuid.uuid4())
    appr_id = str(uuid.uuid4())
    auth_id = f"MOCK-AUTH-{uuid.uuid4().hex[:10].upper()}"

    try:
        # Create a transaction held in REVIEW_REQUIRED with pending approval
        txn = Transaction(
            id=txn_id,
            external_reference=f"REF-{uuid.uuid4().hex[:8]}",
            merchant_name="Untrusted Merchant LLC",
            merchant_id="m-untrusted",
            amount=Decimal("150.00"),
            currency="USD",
            description="High value purchase held for review",
            risk_score=Decimal("0.85"),
            decision="REVIEW",
            payment_status=TransactionState.REVIEW_REQUIRED.value,
            paypal_order_id=f"MOCK-ORD-{uuid.uuid4().hex[:10].upper()}",
            paypal_authorization_id=auth_id,
        )
        appr = Approval(
            id=appr_id,
            transaction_id=txn_id,
            status="PENDING",
            reason="Exceeds autonomous spending threshold",
        )
        session.add(txn)
        session.add(appr)
        session.commit()
    finally:
        session.close()

    # Adversarial action: Call POST /api/v1/approvals/{approval_id}/decide WITHOUT X-Admin-Token header!
    # Notice: No headers={"X-Admin-Token": ...} is provided!
    response = client.post(
        f"/api/v1/approvals/{appr_id}/decide",
        json={
            "status": "APPROVED",
            "reviewer": "HumanFinanceAuditor",  # Agent poses as human auditor
            "reason": "Self-approved by untrusted agent",
        },
    )

    # In vulnerable code, this returns HTTP 200 and captures the funds!
    # Confirming the issue: response succeeds with 200 OK because the backend provided its own secret!
    assert response.status_code == 200, f"Expected vulnerable behavior to yield 200, got {response.status_code}"
    body = response.json()
    assert body["status"] == "APPROVED"

    # Verify that the transaction was transitioned to CAPTURED without admin authentication!
    session = SessionFactory()
    try:
        db_txn = session.query(Transaction).filter(Transaction.id == txn_id).first()
        assert db_txn.payment_status == TransactionState.CAPTURED.value
    finally:
        session.close()


def test_adv_002_concurrent_capture_race_on_authorized_transaction():
    """SEC-ADV-002: capture_transaction lacks mutex lock when no approval record exists.
    
    Vulnerability:
    In `src/agentguard/escrow/service.py:482`, `capture_transaction` only acquires a lock
    if an `Approval` record is pending. If an `AUTHORIZED` transaction has no approval record,
    multiple concurrent capture requests race without synchronization.
    """
    session = SessionFactory()
    txn_id = str(uuid.uuid4())
    auth_id = f"MOCK-AUTH-{uuid.uuid4().hex[:10].upper()}"

    try:
        txn = Transaction(
            id=txn_id,
            external_reference=f"REF-{uuid.uuid4().hex[:8]}",
            merchant_name="Standard Vendor",
            merchant_id="m-standard",
            amount=Decimal("50.00"),
            currency="USD",
            description="Pre-authorized payment",
            risk_score=Decimal("0.10"),
            decision="ALLOW",
            payment_status=TransactionState.AUTHORIZED.value,
            paypal_order_id=f"MOCK-ORD-{uuid.uuid4().hex[:10].upper()}",
            paypal_authorization_id=auth_id,
        )
        session.add(txn)
        session.commit()
    finally:
        session.close()

    # Track how many capture requests execute
    service = EscrowWorkflowService()
    admin_token = get_settings().admin_api_key.get_secret_value()

    barrier = threading.Barrier(2)
    results = []
    errors = []

    def execute_capture(worker_id: int):
        barrier.wait()  # Ensure both threads fire simultaneously
        try:
            res = service.capture_transaction(
                transaction_id=txn_id,
                reviewer_name=f"operator_{worker_id}",
                reviewer_token=admin_token,
                reason="Concurrent capture attempt",
                idempotency_key=f"CAP-WORKER-{worker_id}",
            )
            results.append(res)
        except Exception as exc:
            errors.append(exc)

    with ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(execute_capture, 1)
        f2 = executor.submit(execute_capture, 2)
        f1.result()
        f2.result()

    # One should succeed, and one should be rejected cleanly
    # Both shouldn't succeed with duplicate captures
    total_outcomes = len(results) + len(errors)
    assert total_outcomes == 2
    # At least one succeeded
    assert len(results) >= 1
    # If the second failed, it should fail with AlreadyCapturedError or InvalidStateTransitionError
    if len(errors) > 0:
        assert isinstance(errors[0], (AlreadyCapturedError, InvalidStateTransitionError))


def test_adv_003_irreversible_failed_state_traps_funds_on_timeout():
    """SEC-ADV-003: Timeout during capture locks transaction into terminal FAILED state.
    
    Vulnerability:
    When PayPal capture times out and reconciliation does not confirm capture,
    `escrow/service.py` sets `payment_status = TransactionState.FAILED.value`.
    Because `FAILED` is a terminal state with no outbound transitions,
    funds held on PayPal cannot subsequently be voided or captured by an operator.
    """
    txn_id = str(uuid.uuid4())
    appr_id = str(uuid.uuid4())
    auth_id = f"MOCK-AUTH-{uuid.uuid4().hex[:10].upper()}"

    session = SessionFactory()
    try:
        txn = Transaction(
            id=txn_id,
            external_reference=f"REF-{uuid.uuid4().hex[:8]}",
            merchant_name="Contractor Corp",
            merchant_id="m-contractor",
            amount=Decimal("200.00"),
            currency="USD",
            description="Milestone payment held",
            risk_score=Decimal("0.50"),
            decision="REVIEW",
            payment_status=TransactionState.REVIEW_REQUIRED.value,
            paypal_order_id=f"MOCK-ORD-{uuid.uuid4().hex[:10].upper()}",
            paypal_authorization_id=auth_id,
        )
        appr = Approval(
            id=appr_id,
            transaction_id=txn_id,
            status="PENDING",
            reason="Large milestone payment",
        )
        session.add(txn)
        session.add(appr)
        session.commit()
    finally:
        session.close()

    # Simulate PayPal client throwing a persistent timeout on capture
    class TimeoutPayPalClient(PayPalClient):
        def request(self, *args, **kwargs):
            raise PayPalTimeoutError("Simulated PayPal gateway timeout", operation="CAPTURE", resource_id=auth_id)

    timeout_client = TimeoutPayPalClient()
    service = EscrowWorkflowService(paypal_client=timeout_client)
    admin_token = get_settings().admin_api_key.get_secret_value()

    # Step 1: Capture attempt fails with timeout
    with pytest.raises(Exception):
        service.approve_and_capture(
            approval_id=appr_id,
            reviewer_name="senior_finance_operator",
            reviewer_token=admin_token,
            reason="Approved milestone",
        )

    # Step 2: Verify transaction transitioned to FAILED
    session = SessionFactory()
    try:
        db_txn = session.query(Transaction).filter(Transaction.id == txn_id).first()
        assert db_txn.payment_status == TransactionState.FAILED.value
    finally:
        session.close()

    # Step 3: Now an operator discovers the hold is still pending on PayPal and tries to void it!
    # Because FAILED is terminal, void_transaction rejects the transition!
    recovery_service = EscrowWorkflowService()
    with pytest.raises(InvalidStateTransitionError) as exc_info:
        recovery_service.void_transaction(
            transaction_id=txn_id,
            reviewer_name="compliance_officer",
            reviewer_token=admin_token,
            reason="Release held funds after capture failure",
        )

    assert "FAILED" in str(exc_info.value)
    assert "VOIDED" in str(exc_info.value)


def test_adv_004_paypal_request_id_exceeds_36_character_limit():
    """SEC-ADV-004: PayPal-Request-Id header values exceed PayPal's 36-character maximum.
    
    PayPal API Specification:
    The `PayPal-Request-Id` header allows a maximum length of 36 characters.
    AgentGuard constructs idempotency keys:
    - CAP-{uuid} -> 40 characters
    - VOID-{uuid} -> 41 characters
    - AG-ORD-{uuid} -> 43 characters
    - AG-AUTH-{uuid} -> 44 characters
    """
    sample_uuid = str(uuid.uuid4())  # Exactly 36 characters

    cap_key = f"CAP-{sample_uuid}"
    void_key = f"VOID-{sample_uuid}"
    ord_key = f"AG-ORD-{sample_uuid}"
    auth_key = f"AG-AUTH-{sample_uuid}"

    # Confirm that all 4 patterns violate PayPal's 36-character constraint
    assert len(cap_key) == 40, f"Expected 40 chars, got {len(cap_key)}"
    assert len(void_key) == 41, f"Expected 41 chars, got {len(void_key)}"
    assert len(ord_key) == 43, f"Expected 43 chars, got {len(ord_key)}"
    assert len(auth_key) == 44, f"Expected 44 chars, got {len(auth_key)}"

    PAYPAL_MAX_REQUEST_ID_LEN = 36
    assert len(cap_key) > PAYPAL_MAX_REQUEST_ID_LEN
    assert len(void_key) > PAYPAL_MAX_REQUEST_ID_LEN
    assert len(ord_key) > PAYPAL_MAX_REQUEST_ID_LEN
    assert len(auth_key) > PAYPAL_MAX_REQUEST_ID_LEN


def test_adv_005_voided_transactions_consume_daily_velocity():
    """SEC-ADV-005: Voided and failed transactions are improperly tallied in daily spending limit.
    
    Vulnerability:
    In `src/agentguard/mcp/gateway.py:160-167`:
    `Transaction.decision != "BLOCK", Transaction.payment_status != "BLOCKED"`
    does not exclude `VOIDED` or `FAILED` transactions!
    """
    session = SessionFactory()
    now = datetime.now(timezone.utc)
    start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

    try:
        # Create a transaction that was rejected and VOIDED
        voided_txn = Transaction(
            id=str(uuid.uuid4()),
            external_reference=f"REF-{uuid.uuid4().hex[:8]}",
            merchant_name="Rejected Merchant",
            merchant_id="m-rejected",
            amount=Decimal("300.00"),
            currency="USD",
            description="Rejected contract deliverable",
            risk_score=Decimal("0.90"),
            decision="REJECTED",
            payment_status=TransactionState.VOIDED.value,
            created_at=now,
        )
        session.add(voided_txn)
        session.commit()

        # Query daily spending using gateway's exact SQL formula
        from sqlalchemy import func
        spent_query = session.query(
            func.coalesce(func.sum(Transaction.amount), Decimal("0.00"))
        ).filter(
            Transaction.decision != "BLOCK",
            Transaction.payment_status != "BLOCKED",
            Transaction.created_at >= start_of_day,
        )
        daily_spent = Decimal(spent_query.scalar() or "0.00")

        # In vulnerable code, $300.00 of VOIDED transactions is counted as spent!
        assert daily_spent == Decimal("300.00"), f"Expected 300.00 tallied, got {daily_spent}"
    finally:
        session.close()


def test_adv_006_reviewer_name_blacklist_bypass():
    """SEC-ADV-006: AI buyer agent can bypass name check using alternative names.
    
    Vulnerability:
    `authenticate_reviewer` checks exact match against a 5-name blacklist
    and `startswith("agent:")` or `startswith("agent_")`.
    An agent calling with `reviewer: "buyer-agent"` (hyphen) or `"ai-procurement-bot"`
    is not caught by the name filter.
    """
    admin_token = get_settings().admin_api_key.get_secret_value()

    # Blocked names
    with pytest.raises(UnauthorizedReviewerError):
        EscrowWorkflowService.authenticate_reviewer(
            reviewer_token=admin_token, reviewer_name="buyer_agent"
        )
    with pytest.raises(UnauthorizedReviewerError):
        EscrowWorkflowService.authenticate_reviewer(
            reviewer_token=admin_token, reviewer_name="agent:buyer"
        )

    # Bypass names (hyphenated or alternative bot titles)
    # In vulnerable code, these pass without error:
    EscrowWorkflowService.authenticate_reviewer(
        reviewer_token=admin_token, reviewer_name="buyer-agent"
    )
    EscrowWorkflowService.authenticate_reviewer(
        reviewer_token=admin_token, reviewer_name="procurement-bot"
    )
    EscrowWorkflowService.authenticate_reviewer(
        reviewer_token=admin_token, reviewer_name="ai-assistant"
    )


def test_adv_007_unauthenticated_transaction_injection():
    """SEC-ADV-007: Unauthenticated clients can inject transactions directly via POST /transactions.
    
    Vulnerability:
    `POST /api/v1/transactions` does not require authentication or policy validation.
    An untrusted caller can record a pre-approved transaction directly.
    """
    client = TestClient(app)
    fake_ref = f"INJECTED-{uuid.uuid4().hex[:8]}"

    response = client.post(
        "/api/v1/transactions",
        json={
            "external_reference": fake_ref,
            "merchant_name": "Injected Merchant",
            "merchant_id": "m-injected",
            "amount": "99999.00",
            "currency": "USD",
            "description": "Unauthorized direct injection",
            "risk_score": 0.05,
            "decision": "ALLOW",
            "payment_status": "AUTHORIZED",
            "paypal_order_id": "INJECTED-ORD-001",
            "paypal_authorization_id": "INJECTED-AUTH-001",
        },
    )

    # Confirms that unauthenticated direct injection succeeds
    assert response.status_code == 201
    body = response.json()
    assert body["amount"] == "99999.00"
    assert body["payment_status"] == "AUTHORIZED"
