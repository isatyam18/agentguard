"""API routes for transactions."""

from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from agentguard.core.database import get_db
from agentguard.core.errors import ConflictError, EntityNotFoundError
from agentguard.escrow.service import EscrowWorkflowService
from agentguard.models.audit_log import AuditLog
from agentguard.models.transaction import Transaction
from agentguard.schemas.approval import ApprovalActionRequest
from agentguard.schemas.transaction import TransactionCreate, TransactionResponse


router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record a new transaction",
)
def create_transaction(
    payload: TransactionCreate, db: Session = Depends(get_db)
) -> Transaction:
    """Validate and record an agent payment transaction without executing payment."""
    transaction = Transaction(
        external_reference=payload.external_reference,
        merchant_name=payload.merchant_name,
        merchant_id=payload.merchant_id,
        amount=payload.amount,
        currency=payload.currency,
        description=payload.description,
        risk_score=payload.risk_score,
        decision=payload.decision,
        payment_status=payload.payment_status,
        paypal_order_id=payload.paypal_order_id,
        paypal_authorization_id=payload.paypal_authorization_id,
    )

    db.add(transaction)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise ConflictError(
            message=f"Transaction with external reference '{payload.external_reference}' already exists.",
            details={"external_reference": payload.external_reference},
        ) from exc

    # Record automatic audit event for transaction creation
    audit_entry = AuditLog(
        transaction_id=transaction.id,
        event_type="TRANSACTION_RECORDED",
        actor="agent:gateway",
        details={
            "external_reference": transaction.external_reference,
            "amount": str(transaction.amount),
            "currency": transaction.currency,
            "merchant_name": transaction.merchant_name,
            "decision": transaction.decision,
        },
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get(
    "",
    response_model=List[TransactionResponse],
    summary="List transactions",
)
def list_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    decision: str | None = Query(default=None),
    payment_status: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> List[Transaction]:
    """Retrieve paginated transactions with optional status filters."""
    query = select(Transaction).order_by(desc(Transaction.created_at))
    if decision:
        query = query.where(Transaction.decision == decision)
    if payment_status:
        query = query.where(Transaction.payment_status == payment_status)

    query = query.offset(offset).limit(limit)
    return list(db.scalars(query).all())


@router.get(
    "/{transaction_id}",
    response_model=TransactionResponse,
    summary="Get transaction by ID",
)
def get_transaction(
    transaction_id: str, db: Session = Depends(get_db)
) -> Transaction:
    """Retrieve details for a specific transaction."""
    transaction = db.get(Transaction, transaction_id)
    if not transaction:
        raise EntityNotFoundError("Transaction", transaction_id)
    return transaction


@router.post(
    "/{transaction_id}/capture",
    response_model=Dict[str, Any],
    summary="Capture an authorized transaction",
)
def capture_transaction_endpoint(
    transaction_id: str,
    payload: ApprovalActionRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Capture an authorized payment hold via PayPal Payments v2."""
    admin_token = payload.admin_token or x_admin_token
    escrow_service = EscrowWorkflowService(session=db)
    return escrow_service.capture_transaction(
        transaction_id=transaction_id,
        reviewer_name=payload.reviewer,
        reviewer_token=admin_token,
        reason=payload.reason or "Authorized transaction captured",
        idempotency_key=payload.idempotency_key,
    )


@router.post(
    "/{transaction_id}/void",
    response_model=Dict[str, Any],
    summary="Void an authorized transaction",
)
def void_transaction_endpoint(
    transaction_id: str,
    payload: ApprovalActionRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Void an authorized payment hold via PayPal Payments v2."""
    admin_token = payload.admin_token or x_admin_token
    escrow_service = EscrowWorkflowService(session=db)
    return escrow_service.void_transaction(
        transaction_id=transaction_id,
        reviewer_name=payload.reviewer,
        reviewer_token=admin_token,
        reason=payload.reason or "Authorized transaction voided",
        idempotency_key=payload.idempotency_key,
    )

