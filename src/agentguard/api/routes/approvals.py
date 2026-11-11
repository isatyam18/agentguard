"""API routes for human-in-the-loop approvals."""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, Header, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from agentguard.core.config import get_settings
from agentguard.core.database import get_db
from agentguard.core.errors import ConflictError, EntityNotFoundError
from agentguard.escrow.service import EscrowWorkflowService
from agentguard.models.approval import Approval
from agentguard.models.audit_log import AuditLog
from agentguard.models.transaction import Transaction
from agentguard.schemas.approval import (
    ApprovalActionRequest,
    ApprovalCreate,
    ApprovalDecision,
    ApprovalDetailResponse,
    ApprovalResponse,
)

router = APIRouter(prefix="/approvals", tags=["Approvals"])


@router.post(
    "",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create an approval request",
)
def create_approval(
    payload: ApprovalCreate, db: Session = Depends(get_db)
) -> Approval:
    """Register an escrowed transaction for human review."""
    transaction = db.get(Transaction, payload.transaction_id)
    if not transaction:
        raise EntityNotFoundError("Transaction", payload.transaction_id)

    # Check if there is already an active pending approval for this transaction
    existing = db.scalar(
        select(Approval).where(
            Approval.transaction_id == payload.transaction_id,
            Approval.status == "PENDING",
        )
    )
    if existing:
        raise ConflictError(
            f"Transaction '{payload.transaction_id}' already has a pending approval request.",
            details={"approval_id": existing.id},
        )

    transaction.payment_status = "REVIEW_REQUIRED"
    approval = Approval(
        transaction_id=payload.transaction_id,
        status="PENDING",
        reason=payload.reason,
    )
    db.add(approval)
    db.flush()

    audit_entry = AuditLog(
        transaction_id=transaction.id,
        event_type="APPROVAL_REQUESTED",
        actor="system:escrow",
        details={"approval_id": approval.id, "reason": payload.reason},
    )
    db.add(audit_entry)
    db.commit()
    db.refresh(approval)
    return approval


@router.get(
    "",
    response_model=List[ApprovalResponse],
    summary="List approval requests",
)
def list_approvals(
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
) -> List[Approval]:
    """Retrieve all approval records, optionally filtered by status."""
    query = select(Approval).order_by(desc(Approval.created_at))
    if status_filter:
        query = query.where(Approval.status == status_filter)
    return list(db.scalars(query).all())


@router.get(
    "/{approval_id}",
    response_model=ApprovalResponse,
    summary="Get approval by ID",
)
def get_approval(approval_id: str, db: Session = Depends(get_db)) -> Approval:
    """Retrieve details of an approval record."""
    approval = db.get(Approval, approval_id)
    if not approval:
        raise EntityNotFoundError("Approval", approval_id)
    return approval


@router.get(
    "/{approval_id}/details",
    response_model=ApprovalDetailResponse,
    summary="Get full approval details with transaction and security evidence",
)
def get_approval_details(
    approval_id: str,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Retrieve full transaction details, line items, and security findings for human review."""
    escrow_service = EscrowWorkflowService(session=db)
    return escrow_service.get_review_details(
        approval_id=approval_id,
        reviewer_token=x_admin_token,
    )


@router.post(
    "/{approval_id}/approve",
    response_model=Dict[str, Any],
    summary="Approve escrow and trigger PayPal capture",
)
def approve_escrow(
    approval_id: str,
    payload: ApprovalActionRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Human reviewer approves transaction; triggers PayPal capture on authorization hold."""
    admin_token = payload.admin_token or x_admin_token
    escrow_service = EscrowWorkflowService(session=db)
    return escrow_service.approve_and_capture(
        approval_id=approval_id,
        reviewer_name=payload.reviewer,
        reviewer_token=admin_token,
        reason=payload.reason or "Approved by human operator",
        idempotency_key=payload.idempotency_key,
    )


@router.post(
    "/{approval_id}/reject",
    response_model=Dict[str, Any],
    summary="Reject escrow and trigger PayPal void",
)
def reject_escrow(
    approval_id: str,
    payload: ApprovalActionRequest,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Human reviewer rejects transaction; voids PayPal authorization hold."""
    admin_token = payload.admin_token or x_admin_token
    escrow_service = EscrowWorkflowService(session=db)
    return escrow_service.reject_and_void(
        approval_id=approval_id,
        reviewer_name=payload.reviewer,
        reviewer_token=admin_token,
        reason=payload.reason or "Rejected by human operator",
        idempotency_key=payload.idempotency_key,
    )


@router.post(
    "/{approval_id}/decide",
    response_model=ApprovalResponse,
    summary="Submit human approval decision",
)
def decide_approval(
    approval_id: str,
    payload: ApprovalDecision,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token"),
    db: Session = Depends(get_db),
) -> Approval:
    """Record a human operator decision (APPROVED or REJECTED) through escrow state machine."""
    settings = get_settings()
    admin_token = x_admin_token or settings.admin_api_key.get_secret_value()

    approval = db.get(Approval, approval_id)
    if not approval:
        raise EntityNotFoundError("Approval", approval_id)

    escrow_service = EscrowWorkflowService(session=db)
    if payload.status == "APPROVED":
        escrow_service.approve_and_capture(
            approval_id=approval_id,
            reviewer_name=payload.reviewer,
            reviewer_token=admin_token,
            reason=payload.reason or "Human operator decision: APPROVED",
        )
        transaction = db.get(Transaction, approval.transaction_id)
        if transaction:
            transaction.decision = "ALLOW"
            db.commit()
    else:
        escrow_service.reject_and_void(
            approval_id=approval_id,
            reviewer_name=payload.reviewer,
            reviewer_token=admin_token,
            reason=payload.reason or "Human operator decision: REJECTED",
        )
        transaction = db.get(Transaction, approval.transaction_id)
        if transaction:
            transaction.decision = "BLOCK"
            db.commit()

    db.refresh(approval)
    return approval

