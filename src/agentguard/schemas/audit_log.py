"""Pydantic schemas for audit logs."""

from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, ConfigDict, Field


class AuditLogCreate(BaseModel):
    """Payload to record an audit log event."""

    event_type: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Type of security or transaction event",
    )
    actor: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Principal who triggered the event (agent, system, reviewer)",
    )
    details: Dict[str, Any] = Field(
        default_factory=dict,
        description="Structured key-value context of the event",
    )
    transaction_id: str | None = Field(
        default=None,
        description="Associated transaction UUID, if applicable",
    )


class AuditLogResponse(BaseModel):
    """Public DTO for audit log events."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID of the audit log record")
    transaction_id: str | None = None
    event_type: str = Field(description="Event classification")
    actor: str = Field(description="Actor identity")
    details: Dict[str, Any] = Field(description="Event details")
    timestamp: datetime = Field(description="UTC event occurrence timestamp")
