"""Pydantic schemas for firewall policies."""

from decimal import Decimal
from typing import List

from pydantic import BaseModel, ConfigDict, Field, field_validator


class PolicyBase(BaseModel):
    """Shared policy fields."""

    max_transaction_amount: Decimal = Field(
        ...,
        description="Maximum allowed amount per single transaction (strictly Decimal)",
    )
    daily_spending_limit: Decimal = Field(
        ...,
        description="Cumulative 24-hour spending limit for the agent/policy",
    )
    allowed_merchants: List[str] = Field(
        default_factory=list,
        description="Allowlisted merchant IDs, names, or domains",
    )
    require_human_approval: bool = Field(
        default=True,
        description="Whether payments above autonomous limits trigger human review",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this policy is actively evaluated",
    )

    @field_validator("max_transaction_amount", "daily_spending_limit")
    @classmethod
    def validate_positive_amount(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0.00"):
            raise ValueError("Policy threshold amount must be strictly greater than 0.")
        if v.as_tuple().exponent < -2:
            raise ValueError("Policy threshold cannot exceed 2 decimal places.")
        return v


class PolicyCreate(PolicyBase):
    """Payload to create a new firewall policy."""
    pass


class PolicyUpdate(BaseModel):
    """Payload to partially update a policy."""

    max_transaction_amount: Decimal | None = None
    daily_spending_limit: Decimal | None = None
    allowed_merchants: List[str] | None = None
    require_human_approval: bool | None = None
    is_active: bool | None = None

    @field_validator("max_transaction_amount", "daily_spending_limit")
    @classmethod
    def validate_positive_amount_if_set(cls, v: Decimal | None) -> Decimal | None:
        if v is not None:
            if v <= Decimal("0.00"):
                raise ValueError("Policy threshold amount must be strictly greater than 0.")
            if v.as_tuple().exponent < -2:
                raise ValueError("Policy threshold cannot exceed 2 decimal places.")
        return v


class PolicyResponse(PolicyBase):
    """Public DTO for policy rules."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Internal UUID of the policy")
