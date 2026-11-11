"""SQLAlchemy model for Human-in-the-Loop approvals."""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard.models.base import Base

if TYPE_CHECKING:
    from agentguard.models.transaction import Transaction


class Approval(Base):
    """Represents a human-in-the-loop approval request for an escrowed transaction."""

    __tablename__ = "approvals"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    transaction_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("transactions.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )

    # State: PENDING, APPROVED, REJECTED
    status: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        default="PENDING",
    )

    reviewer: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )
    reason: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationship to transaction
    transaction: Mapped["Transaction"] = relationship(
        "Transaction",
        back_populates="approvals",
    )

    __table_args__ = (
        CheckConstraint(
            "status IN ('PENDING', 'APPROVED', 'REJECTED')",
            name="ck_approvals_valid_status",
        ),
        Index("ix_approvals_status_created", "status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Approval(id='{self.id}', txn_id='{self.transaction_id}', "
            f"status='{self.status}', reviewer='{self.reviewer}')>"
        )
