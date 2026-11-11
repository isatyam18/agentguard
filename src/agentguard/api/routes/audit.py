"""API routes for audit logs."""

from typing import List
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from agentguard.core.database import get_db
from agentguard.models.audit_log import AuditLog
from agentguard.schemas.audit_log import AuditLogCreate, AuditLogResponse

router = APIRouter(prefix="/audit-logs", tags=["Audit Logs"])


@router.post(
    "",
    response_model=AuditLogResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Record an audit log entry",
)
def create_audit_log(
    payload: AuditLogCreate, db: Session = Depends(get_db)
) -> AuditLog:
    """Append a structured audit log event to the immutable audit trail."""
    entry = AuditLog(
        transaction_id=payload.transaction_id,
        event_type=payload.event_type,
        actor=payload.actor,
        details=payload.details,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


@router.get(
    "",
    response_model=List[AuditLogResponse],
    summary="List audit log entries",
)
def list_audit_logs(
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    event_type: str | None = Query(default=None),
    transaction_id: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> List[AuditLog]:
    """Query audit events with pagination and filters."""
    query = select(AuditLog).order_by(desc(AuditLog.timestamp))
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if transaction_id:
        query = query.where(AuditLog.transaction_id == transaction_id)

    query = query.offset(offset).limit(limit)
    return list(db.scalars(query).all())
