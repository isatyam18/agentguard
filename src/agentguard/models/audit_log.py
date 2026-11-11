"""SQLAlchemy model for immutable audit logs."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Dict

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard.models.base import Base

if TYPE_CHECKING:
    from agentguard.models.transaction import Transaction


class AuditLog(Base):
    """Represents an append-only audit trail record of all security and financial events."""

    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    transaction_id: Mapped[str | None] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )

    event_type: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    actor: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )
    details: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=False,
        default=dict,
    )

    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relationship to transaction
    transaction: Mapped["Transaction | None"] = relationship(
        "Transaction",
        back_populates="audit_logs",
    )

    __table_args__ = (
        Index("ix_audit_logs_event_timestamp", "event_type", "timestamp"),
        Index("ix_audit_logs_actor_timestamp", "actor", "timestamp"),
    )

    def __repr__(self) -> str:
        return (
            f"<AuditLog(id='{self.id}', event='{self.event_type}', "
            f"actor='{self.actor}', ts='{self.timestamp}')>"
        )
