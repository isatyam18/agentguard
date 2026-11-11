"""SQLAlchemy model for firewall spending policies and rules."""

import uuid
from decimal import Decimal
from typing import List

from sqlalchemy import Boolean, CheckConstraint, JSON, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from agentguard.models.base import Base


class Policy(Base):
    """Represents a spending policy rule enforced by the AgentGuard firewall."""

    __tablename__ = "policies"

    id: Mapped[str] = mapped_column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
    )

    # Spending thresholds (strictly Decimal)
    max_transaction_amount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )
    daily_spending_limit: Mapped[Decimal] = mapped_column(
        Numeric(12, 2, asdecimal=True),
        nullable=False,
    )

    # Allowed merchants list (stored as JSON array of merchant identifiers or domains)
    allowed_merchants: Mapped[List[str]] = mapped_column(
        JSON,
        nullable=False,
        default=list,
    )

    # Security controls
    require_human_approval: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        index=True,
    )

    __table_args__ = (
        CheckConstraint(
            "max_transaction_amount > 0",
            name="ck_policies_max_transaction_positive",
        ),
        CheckConstraint(
            "daily_spending_limit > 0",
            name="ck_policies_daily_limit_positive",
        ),
    )

    def __repr__(self) -> str:
        return (
            f"<Policy(id='{self.id}', max_amount={self.max_transaction_amount}, "
            f"daily_limit={self.daily_spending_limit}, active={self.is_active})>"
        )
