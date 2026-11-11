"""SQLAlchemy model for financial transactions initiated by agents."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, List

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from agentguard.models.base import Base

if TYPE_CHECKING:
    from agentguard.models.approval import Approval
    from agentguard.models.audit_log import AuditLog


class Transaction(Base):
    """Represents an agent payment transaction processed through AgentGuard."""

    __tablename__ = "transactions"

    # UUID Primary Key
    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Unique external tracking ID from agent
    external_reference: Mapped[str] = mapped_column(
        String(100),
        unique=True,
        index=True,
        nullable=False,
    )

    # Merchant details
    merchant_name: Mapped[str] = mapped_column(
        String(255),
        index=True,
        nullable=False,
    )
    merchant_id: Mapped[str] = mapped_column(
        String(100),
        index=True,
        nullable=False,
    )

    # Financial details - strictly Decimal
    amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )
    currency: Mapped[str] = mapped_column(
        String(3),
        index=True,
        nullable=False,
        default="USD",
    )
    description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    # Firewall evaluation outputs
    risk_score: Mapped[Decimal] = mapped_column(
        Numeric(3, 2, asdecimal=True),
        nullable=False,
        default=Decimal("0.00"),
    )
    decision: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        default="PENDING",
    )

    # Payment execution & escrow status
    payment_status: Mapped[str] = mapped_column(
        String(50),
        index=True,
        nullable=False,
        default="PENDING",
    )
    paypal_order_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )
    paypal_authorization_id: Mapped[str | None] = mapped_column(
        String(100),
        index=True,
        nullable=True,
    )

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        index=True,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    approvals: Mapped[List["Approval"]] = relationship(
        "Approval",
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(
        "AuditLog",
        back_populates="transaction",
    )

    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "risk_score >= 0.0 AND risk_score <= 1.0",
            name="ck_transactions_risk_score_bounds",
        ),
        Index("ix_transactions_status_created", "payment_status", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<Transaction(id='{self.id}', ref='{self.external_reference}', "
            f"amount={self.amount} {self.currency}, status='{self.payment_status}')>"
        )
