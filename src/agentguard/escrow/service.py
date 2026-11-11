"""Core escrow workflow service executing authenticated human approvals, captures, and voids."""

from datetime import datetime, timezone
import threading
from typing import Any, Dict, List, Optional
import uuid

from sqlalchemy.orm import Session

from agentguard.core.config import get_settings
from agentguard.core.database import SessionFactory
from agentguard.core.logging import logger
from agentguard.escrow.exceptions import (
    AlreadyCapturedError,
    AlreadyVoidedError,
    DuplicateApprovalError,
    EscrowExecutionError,
    InvalidStateTransitionError,
    UnauthorizedReviewerError,
)
from agentguard.escrow.state_machine import (
    TransactionState,
    validate_transition,
)
from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.transaction import Transaction
from agentguard.paypal.client import PayPalClient
from agentguard.paypal.payments import PayPalPayments

# In-process mutex table guarding concurrent approval/rejection attempts
_APPROVAL_LOCKS: Dict[str, threading.Lock] = {}
_GLOBAL_LOCK = threading.Lock()


def _get_approval_lock(approval_id: str) -> threading.Lock:
    """Retrieve or register a thread-safe mutex for a specific approval task."""
    with _GLOBAL_LOCK:
        if approval_id not in _APPROVAL_LOCKS:
            _APPROVAL_LOCKS[approval_id] = threading.Lock()
        return _APPROVAL_LOCKS[approval_id]


class EscrowWorkflowService:
    """Authoritative escrow workflow service enforcing human approval and PayPal settlement."""

    def __init__(
        self,
        session: Optional[Session] = None,
        paypal_client: Optional[PayPalClient] = None,
    ) -> None:
        self._session = session
        self._paypal_client = paypal_client

    def _get_db(self) -> Session:
        return self._session or SessionFactory()

    @staticmethod
    def authenticate_reviewer(
        reviewer_token: Optional[str],
        reviewer_name: str,
    ) -> None:
        """Verify human operator authorization and prohibit AI agent self-approval.
        
        Rules:
        - Never let the AI buyer agent approve its own transactions.
        - Human approval must be authenticated with the administrative credential.
        """
        clean_name = (reviewer_name or "").strip().lower()
        if not clean_name:
            raise UnauthorizedReviewerError("Reviewer identity must be specified.")

        # Prohibit AI agent self-approval
        prohibited_agent_names = {
            "mcp_buyer_agent",
            "buyer_agent",
            "buyer_agent_001",
            "ai_agent",
            "agentguard_agent",
        }
        if clean_name in prohibited_agent_names or clean_name.startswith("agent:") or clean_name.startswith("agent_"):
            logger.warning(f"AI buyer agent '{reviewer_name}' attempted self-approval.")
            raise UnauthorizedReviewerError(
                "Autonomous AI buyer agents are strictly prohibited from approving their own transactions. "
                "Human operator authorization is mandatory."
            )

        settings = get_settings()
        expected_secret = settings.admin_api_key.get_secret_value()

        if not reviewer_token or reviewer_token.strip() != expected_secret:
            logger.warning(f"Unauthenticated approval attempt by '{reviewer_name}'.")
            raise UnauthorizedReviewerError(
                "Administrative authentication required to execute human approval or escrow release."
            )

    def get_review_details(
        self,
        approval_id: str,
        reviewer_token: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Fetch complete transaction details and security evidence for human inspection."""
        session = self._get_db()
        owns_session = self._session is None

        try:
            approval = session.query(Approval).filter(Approval.id == approval_id).first()
            if not approval:
                raise EscrowError(
                    f"Approval request '{approval_id}' was not found.",
                    status_code=404,
                    error_name="APPROVAL_NOT_FOUND",
                )

            transaction = approval.transaction
            if not transaction:
                raise EscrowError(
                    f"Transaction for approval '{approval_id}' was not found.",
                    status_code=404,
                    error_name="TRANSACTION_NOT_FOUND",
                )

            # Collect audit trail logs
            logs = (
                session.query(AuditLog)
                .filter(AuditLog.transaction_id == transaction.id)
                .order_by(AuditLog.timestamp.asc())
                .all()
            )

            security_evidence: List[str] = []
            policy_violations: List[str] = []

            for log in logs:
                details = log.details or {}
                if log.event_type == "INVOICE_SECURITY_SCAN":
                    threats = details.get("scanner_threats", [])
                    if threats:
                        security_evidence.extend([f"Threat: {t}" for t in threats])
                elif log.event_type == "POLICY_FIREWALL_EVALUATION":
                    violations = details.get("policy_violations", [])
                    policy_violations.extend(violations)
                elif log.event_type == "DECISION_FINALIZED":
                    reasons = details.get("reasons", [])
                    for r in reasons:
                        if "SECURITY_EVIDENCE" in r:
                            security_evidence.append(r)

            return {
                "approval_id": approval.id,
                "approval_status": approval.status,
                "transaction_id": transaction.id,
                "external_reference": transaction.external_reference,
                "merchant_name": transaction.merchant_name,
                "merchant_id": transaction.merchant_id,
                "amount": str(transaction.amount),
                "currency": transaction.currency,
                "description": transaction.description,
                "current_state": transaction.payment_status,
                "risk_score": int(transaction.risk_score * 100),
                "reason_for_hold": approval.reason,
                "paypal_order_id": transaction.paypal_order_id,
                "paypal_authorization_id": transaction.paypal_authorization_id,
                "created_at": approval.created_at.isoformat(),
                "resolved_at": approval.resolved_at.isoformat() if approval.resolved_at else None,
                "reviewer": approval.reviewer,
                "policy_violations": policy_violations,
                "security_evidence": security_evidence,
                "audit_events": [log.event_type for log in logs],
            }

        finally:
            if owns_session:
                session.close()

    def approve_and_capture(
        self,
        approval_id: str,
        reviewer_name: str,
        reviewer_token: Optional[str] = None,
        reason: str = "Human operator approved deliverable.",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute human approval and trigger PayPal authorization capture.
        
        Guarantees:
        - Reviewer is authenticated and not an AI buyer agent.
        - Concurrency protection prevents double-approval.
        - Validates transaction state: never captures an already captured or voided transaction.
        - State transition recorded: APPROVED_FOR_CAPTURE -> CAPTURED.
        - Failures in PayPal capture safely transition transaction to FAILED.
        """
        # 1. Authenticate human reviewer
        self.authenticate_reviewer(reviewer_token=reviewer_token, reviewer_name=reviewer_name)

        # 2. Concurrency protection via approval-specific mutex
        lock = _get_approval_lock(approval_id)
        acquired = lock.acquire(blocking=True, timeout=10.0)
        if not acquired:
            raise EscrowError("Timeout acquiring concurrency lock for approval.", status_code=503)

        session = self._get_db()
        owns_session = self._session is None

        try:
            # 3. Retrieve approval record and lock row
            approval = session.query(Approval).filter(Approval.id == approval_id).first()
            if not approval:
                raise EscrowError(
                    f"Approval '{approval_id}' was not found.",
                    status_code=404,
                    error_name="APPROVAL_NOT_FOUND",
                )

            # Check duplicate approval resolution
            if approval.status != "PENDING":
                raise DuplicateApprovalError(
                    f"Approval '{approval_id}' has already been resolved with status '{approval.status}'."
                )

            transaction = approval.transaction
            if not transaction:
                raise EscrowError(
                    f"Associated transaction for approval '{approval_id}' was not found.",
                    status_code=404,
                )

            current_status = transaction.payment_status

            # Invariant: Never capture an already captured transaction
            if current_status == TransactionState.CAPTURED.value:
                raise AlreadyCapturedError(
                    f"Transaction '{transaction.id}' has already been captured."
                )

            # Invariant: Never capture a voided authorization
            if current_status == TransactionState.VOIDED.value:
                raise AlreadyVoidedError(
                    f"Cannot capture transaction '{transaction.id}': Authorization is already VOIDED."
                )

            # Invariant: Validate legal state transition to APPROVED_FOR_CAPTURE
            validate_transition(current_status, TransactionState.APPROVED_FOR_CAPTURE)

            # 4. State transition: -> APPROVED_FOR_CAPTURE
            transaction.payment_status = TransactionState.APPROVED_FOR_CAPTURE.value
            state_audit_1 = AuditLog(
                transaction_id=transaction.id,
                event_type="TRANSACTION_STATE_TRANSITION",
                actor=f"human:{reviewer_name}",
                details={
                    "from_state": current_status,
                    "to_state": TransactionState.APPROVED_FOR_CAPTURE.value,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                },
            )
            session.add(state_audit_1)
            session.flush()

            # 5. Execute PayPal capture on the authorization hold
            capture_id: Optional[str] = None
            paypal_client = self._paypal_client or PayPalClient(timeout=10.0)
            payments_service = PayPalPayments(paypal_client)

            if transaction.paypal_authorization_id:
                try:
                    capture_resp = payments_service.capture_authorization(
                        authorization_id=transaction.paypal_authorization_id,
                        amount=transaction.amount,
                        currency=transaction.currency,
                        final_capture=True,
                        note_to_payer=f"Approved by {reviewer_name}: {reason}",
                        idempotency_key=idempotency_key or f"CAP-{transaction.id}",
                    )
                    capture_id = capture_resp.get("capture_id")
                except Exception as pay_err:
                    logger.error(
                        f"PayPal capture failed for authorization '{transaction.paypal_authorization_id}': {pay_err}",
                        exc_info=True,
                    )
                    # Downstream failure: transition to FAILED
                    transaction.payment_status = TransactionState.FAILED.value
                    fail_audit = AuditLog(
                        transaction_id=transaction.id,
                        event_type="PAYPAL_CAPTURE_FAILED",
                        actor="paypal_adapter",
                        details={
                            "authorization_id": transaction.paypal_authorization_id,
                            "error": str(pay_err),
                        },
                    )
                    session.add(fail_audit)
                    session.commit()
                    raise EscrowExecutionError(
                        f"PayPal capture execution failed: {pay_err}",
                        details={"error": str(pay_err)},
                    ) from pay_err
            else:
                # If no prior authorization exists, mock capture identifier
                capture_id = f"MOCK-CAP-{uuid.uuid4().hex[:12].upper()}"

            # 6. State transition: -> CAPTURED
            validate_transition(TransactionState.APPROVED_FOR_CAPTURE, TransactionState.CAPTURED)
            transaction.payment_status = TransactionState.CAPTURED.value
            transaction.decision = "APPROVED"

            approval.status = "APPROVED"
            approval.reviewer = reviewer_name
            approval.reason = reason
            approval.resolved_at = datetime.now(timezone.utc)

            success_audit = AuditLog(
                transaction_id=transaction.id,
                event_type="APPROVAL_GRANTED_AND_CAPTURED",
                actor=f"human:{reviewer_name}",
                details={
                    "approval_id": approval.id,
                    "capture_id": capture_id,
                    "settled_amount": str(transaction.amount),
                    "currency": transaction.currency,
                },
            )
            session.add(success_audit)
            session.commit()

            return {
                "approval_id": approval.id,
                "transaction_id": transaction.id,
                "status": "APPROVED",
                "payment_status": TransactionState.CAPTURED.value,
                "capture_id": capture_id,
                "reviewer": reviewer_name,
                "resolved_at": approval.resolved_at.isoformat(),
            }

        finally:
            lock.release()
            if owns_session:
                session.close()

    def reject_and_void(
        self,
        approval_id: str,
        reviewer_name: str,
        reviewer_token: Optional[str] = None,
        reason: str = "Human operator rejected request.",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute human rejection and trigger PayPal authorization voiding.
        
        Guarantees:
        - Reviewer is authenticated and not an AI buyer agent.
        - Concurrency protection prevents race conditions.
        - Validates state: never voids an already captured transaction.
        - Rejection triggers PayPal void where an authorization exists.
        - State transition recorded: REVIEW_REQUIRED -> VOIDED.
        """
        # 1. Authenticate human reviewer
        self.authenticate_reviewer(reviewer_token=reviewer_token, reviewer_name=reviewer_name)

        # 2. Concurrency protection
        lock = _get_approval_lock(approval_id)
        acquired = lock.acquire(blocking=True, timeout=10.0)
        if not acquired:
            raise EscrowError("Timeout acquiring concurrency lock for approval rejection.", status_code=503)

        session = self._get_db()
        owns_session = self._session is None

        try:
            # 3. Retrieve approval record
            approval = session.query(Approval).filter(Approval.id == approval_id).first()
            if not approval:
                raise EscrowError(
                    f"Approval '{approval_id}' was not found.",
                    status_code=404,
                    error_name="APPROVAL_NOT_FOUND",
                )

            if approval.status != "PENDING":
                raise DuplicateApprovalError(
                    f"Approval '{approval_id}' has already been resolved with status '{approval.status}'."
                )

            transaction = approval.transaction
            if not transaction:
                raise EscrowError(
                    f"Associated transaction for approval '{approval_id}' was not found.",
                    status_code=404,
                )

            current_status = transaction.payment_status

            # Invariant: Never void an already captured transaction
            if current_status == TransactionState.CAPTURED.value:
                raise InvalidStateTransitionError(
                    f"Cannot void transaction '{transaction.id}': Funds have already been CAPTURED.",
                    from_state=current_status,
                    to_state=TransactionState.VOIDED.value,
                )

            # Invariant: Never void an already voided transaction
            if current_status == TransactionState.VOIDED.value:
                raise AlreadyVoidedError(
                    f"Transaction '{transaction.id}' has already been voided."
                )

            # Validate legal transition to VOIDED
            validate_transition(current_status, TransactionState.VOIDED)

            # 4. Trigger PayPal void where authorization exists
            paypal_client = self._paypal_client or PayPalClient(timeout=10.0)
            payments_service = PayPalPayments(paypal_client)

            if transaction.paypal_authorization_id:
                try:
                    payments_service.void_authorization(
                        authorization_id=transaction.paypal_authorization_id,
                        note_to_payer=f"Rejected by {reviewer_name}: {reason}",
                        idempotency_key=idempotency_key or f"VOID-{transaction.id}",
                    )
                except Exception as pay_err:
                    logger.error(
                        f"PayPal void failed for authorization '{transaction.paypal_authorization_id}': {pay_err}",
                        exc_info=True,
                    )
                    transaction.payment_status = TransactionState.FAILED.value
                    fail_audit = AuditLog(
                        transaction_id=transaction.id,
                        event_type="PAYPAL_VOID_FAILED",
                        actor="paypal_adapter",
                        details={
                            "authorization_id": transaction.paypal_authorization_id,
                            "error": str(pay_err),
                        },
                    )
                    session.add(fail_audit)
                    session.commit()
                    raise EscrowExecutionError(
                        f"PayPal void execution failed: {pay_err}",
                        details={"error": str(pay_err)},
                    ) from pay_err

            # 5. State transition: -> VOIDED
            transaction.payment_status = TransactionState.VOIDED.value
            transaction.decision = "REJECTED"

            approval.status = "REJECTED"
            approval.reviewer = reviewer_name
            approval.reason = reason
            approval.resolved_at = datetime.now(timezone.utc)

            void_audit = AuditLog(
                transaction_id=transaction.id,
                event_type="APPROVAL_REJECTED_AND_VOIDED",
                actor=f"human:{reviewer_name}",
                details={
                    "approval_id": approval.id,
                    "reason": reason,
                    "authorization_id": transaction.paypal_authorization_id,
                },
            )
            session.add(void_audit)
            session.commit()

            return {
                "approval_id": approval.id,
                "transaction_id": transaction.id,
                "status": "REJECTED",
                "payment_status": TransactionState.VOIDED.value,
                "reviewer": reviewer_name,
                "resolved_at": approval.resolved_at.isoformat(),
            }

        finally:
            lock.release()
            if owns_session:
                session.close()

    def capture_transaction(
        self,
        transaction_id: str,
        reviewer_name: str,
        reviewer_token: Optional[str] = None,
        reason: str = "Authorized payment captured by human operator.",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Capture an authorized transaction.
        
        If an approval record exists for this transaction, delegates to approve_and_capture.
        Otherwise directly coordinates state transition and PayPal capture.
        """
        self.authenticate_reviewer(reviewer_token=reviewer_token, reviewer_name=reviewer_name)

        session = self._get_db()
        owns_session = self._session is None

        try:
            approval = (
                session.query(Approval)
                .filter(Approval.transaction_id == transaction_id, Approval.status == "PENDING")
                .first()
            )
            if approval:
                return self.approve_and_capture(
                    approval_id=approval.id,
                    reviewer_name=reviewer_name,
                    reviewer_token=reviewer_token,
                    reason=reason,
                    idempotency_key=idempotency_key,
                )

            transaction = session.query(Transaction).filter(Transaction.id == transaction_id).first()
            if not transaction:
                raise EscrowError(
                    f"Transaction '{transaction_id}' was not found.",
                    status_code=404,
                    error_name="TRANSACTION_NOT_FOUND",
                )

            current_status = transaction.payment_status

            if current_status == TransactionState.CAPTURED.value:
                raise AlreadyCapturedError(
                    f"Transaction '{transaction_id}' has already been captured.",
                    from_state=current_status,
                    to_state=TransactionState.CAPTURED.value,
                )

            if current_status == TransactionState.VOIDED.value:
                raise AlreadyVoidedError(
                    f"Cannot capture transaction '{transaction_id}': Authorization is already VOIDED.",
                    from_state=current_status,
                    to_state=TransactionState.CAPTURED.value,
                )

            validate_transition(current_status, TransactionState.APPROVED_FOR_CAPTURE)

            transaction.payment_status = TransactionState.APPROVED_FOR_CAPTURE.value
            state_audit = AuditLog(
                transaction_id=transaction.id,
                event_type="TRANSACTION_STATE_TRANSITION",
                actor=f"human:{reviewer_name}",
                details={
                    "from_state": current_status,
                    "to_state": TransactionState.APPROVED_FOR_CAPTURE.value,
                    "reason": reason,
                    "idempotency_key": idempotency_key,
                },
            )
            session.add(state_audit)
            session.flush()

            capture_id: Optional[str] = None
            paypal_client = self._paypal_client or PayPalClient(timeout=10.0)
            payments_service = PayPalPayments(paypal_client)

            if transaction.paypal_authorization_id:
                try:
                    capture_resp = payments_service.capture_authorization(
                        authorization_id=transaction.paypal_authorization_id,
                        amount=transaction.amount,
                        currency=transaction.currency,
                        final_capture=True,
                        note_to_payer=f"Approved by {reviewer_name}: {reason}",
                        idempotency_key=idempotency_key or f"CAP-{transaction.id}",
                    )
                    capture_id = capture_resp.get("capture_id")
                except Exception as pay_err:
                    logger.error(
                        f"PayPal capture failed for authorization '{transaction.paypal_authorization_id}': {pay_err}",
                        exc_info=True,
                    )
                    transaction.payment_status = TransactionState.FAILED.value
                    fail_audit = AuditLog(
                        transaction_id=transaction.id,
                        event_type="PAYPAL_CAPTURE_FAILED",
                        actor="paypal_adapter",
                        details={
                            "authorization_id": transaction.paypal_authorization_id,
                            "error": str(pay_err),
                        },
                    )
                    session.add(fail_audit)
                    session.commit()
                    raise EscrowExecutionError(
                        f"PayPal capture execution failed: {pay_err}",
                        details={"error": str(pay_err)},
                    ) from pay_err
            else:
                capture_id = f"MOCK-CAP-{uuid.uuid4().hex[:12].upper()}"

            validate_transition(TransactionState.APPROVED_FOR_CAPTURE, TransactionState.CAPTURED)
            transaction.payment_status = TransactionState.CAPTURED.value
            transaction.decision = "APPROVED"

            success_audit = AuditLog(
                transaction_id=transaction.id,
                event_type="TRANSACTION_CAPTURED",
                actor=f"human:{reviewer_name}",
                details={
                    "capture_id": capture_id,
                    "settled_amount": str(transaction.amount),
                    "currency": transaction.currency,
                },
            )
            session.add(success_audit)
            session.commit()

            return {
                "transaction_id": transaction.id,
                "payment_status": TransactionState.CAPTURED.value,
                "capture_id": capture_id,
                "reviewer": reviewer_name,
            }
        finally:
            if owns_session:
                session.close()

    def void_transaction(
        self,
        transaction_id: str,
        reviewer_name: str,
        reviewer_token: Optional[str] = None,
        reason: str = "Authorized payment voided by human operator.",
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Void an active authorization for a transaction."""
        self.authenticate_reviewer(reviewer_token=reviewer_token, reviewer_name=reviewer_name)

        session = self._get_db()
        owns_session = self._session is None

        try:
            approval = (
                session.query(Approval)
                .filter(Approval.transaction_id == transaction_id, Approval.status == "PENDING")
                .first()
            )
            if approval:
                return self.reject_and_void(
                    approval_id=approval.id,
                    reviewer_name=reviewer_name,
                    reviewer_token=reviewer_token,
                    reason=reason,
                    idempotency_key=idempotency_key,
                )

            transaction = session.query(Transaction).filter(Transaction.id == transaction_id).first()
            if not transaction:
                raise EscrowError(
                    f"Transaction '{transaction_id}' was not found.",
                    status_code=404,
                    error_name="TRANSACTION_NOT_FOUND",
                )

            current_status = transaction.payment_status

            if current_status == TransactionState.CAPTURED.value:
                raise InvalidStateTransitionError(
                    f"Cannot void transaction '{transaction_id}': Funds have already been CAPTURED.",
                    from_state=current_status,
                    to_state=TransactionState.VOIDED.value,
                )

            if current_status == TransactionState.VOIDED.value:
                raise AlreadyVoidedError(
                    f"Transaction '{transaction_id}' has already been voided.",
                    from_state=current_status,
                    to_state=TransactionState.VOIDED.value,
                )

            validate_transition(current_status, TransactionState.VOIDED)

            paypal_client = self._paypal_client or PayPalClient(timeout=10.0)
            payments_service = PayPalPayments(paypal_client)

            if transaction.paypal_authorization_id:
                try:
                    payments_service.void_authorization(
                        authorization_id=transaction.paypal_authorization_id,
                        note_to_payer=f"Voided by {reviewer_name}: {reason}",
                        idempotency_key=idempotency_key or f"VOID-{transaction.id}",
                    )
                except Exception as pay_err:
                    logger.error(
                        f"PayPal void failed for authorization '{transaction.paypal_authorization_id}': {pay_err}",
                        exc_info=True,
                    )
                    transaction.payment_status = TransactionState.FAILED.value
                    fail_audit = AuditLog(
                        transaction_id=transaction.id,
                        event_type="PAYPAL_VOID_FAILED",
                        actor="paypal_adapter",
                        details={
                            "authorization_id": transaction.paypal_authorization_id,
                            "error": str(pay_err),
                        },
                    )
                    session.add(fail_audit)
                    session.commit()
                    raise EscrowExecutionError(
                        f"PayPal void execution failed: {pay_err}",
                        details={"error": str(pay_err)},
                    ) from pay_err

            transaction.payment_status = TransactionState.VOIDED.value
            transaction.decision = "REJECTED"

            void_audit = AuditLog(
                transaction_id=transaction.id,
                event_type="TRANSACTION_VOIDED",
                actor=f"human:{reviewer_name}",
                details={
                    "reason": reason,
                    "authorization_id": transaction.paypal_authorization_id,
                },
            )
            session.add(void_audit)
            session.commit()

            return {
                "transaction_id": transaction.id,
                "payment_status": TransactionState.VOIDED.value,
                "reviewer": reviewer_name,
            }
        finally:
            if owns_session:
                session.close()

