"""Pydantic schemas for transactions with strict Decimal validation."""

import re
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TransactionBase(BaseModel):
    """Shared transaction fields."""

    external_reference: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique external reference from buyer agent or caller",
    )
    merchant_name: str = Field(
        ...,
        min_length=1,
        max_length=255,
        description="Human-readable merchant name",
    )
    merchant_id: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Unique merchant account identifier or domain",
    )
    amount: Decimal = Field(
        ...,
        description="Transaction amount in specified currency (strictly Decimal)",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 3-letter currency code (e.g. USD, EUR)",
    )
    description: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Purpose and line item details of the payment",
    )

    @field_validator("external_reference", "merchant_name", "merchant_id", "description")
    @classmethod
    def strip_and_validate_non_empty(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Field must not be empty or whitespace.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def validate_currency_code(cls, v: str) -> str:
        upper = v.strip().upper()
        if not re.match(r"^[A-Z]{3}$", upper):
            raise ValueError("Currency must be a valid 3-letter uppercase ISO 4217 code.")
        return upper

    @field_validator("amount")
    @classmethod
    def validate_positive_decimal(cls, v: Decimal) -> Decimal:
        if v <= Decimal("0.00"):
            raise ValueError("Transaction amount must be strictly greater than 0.")
        # Ensure at most 2 decimal places (standard currency cents)
        if v.as_tuple().exponent < -2:
            raise ValueError("Transaction amount cannot have more than 2 decimal places.")
        return v


class TransactionCreate(TransactionBase):
    """Payload to submit a transaction for evaluation and storage."""

    risk_score: Decimal = Field(
        default=Decimal("0.00"),
        ge=Decimal("0.00"),
        le=Decimal("1.00"),
        description="Pre-calculated or simulated risk score (0.00 to 1.00)",
    )
    decision: Literal["PENDING", "ALLOW", "HOLD", "BLOCK"] = Field(
        default="PENDING",
        description="Firewall policy decision",
    )
    payment_status: Literal[
        "PENDING", "AUTHORIZED", "CAPTURED", "VOIDED", "FAILED"
    ] = Field(
        default="PENDING",
        description="Payment execution lifecycle state",
    )
    paypal_order_id: str | None = Field(
        default=None,
        max_length=100,
        description="PayPal Orders v2 Order ID",
    )
    paypal_authorization_id: str | None = Field(
        default=None,
        max_length=100,
        description="PayPal Payments v2 Authorization ID",
    )


class TransactionUpdate(BaseModel):
    """Payload for updating transaction state (e.g., after policy or PayPal webhook)."""

    decision: Literal["ALLOW", "HOLD", "BLOCK"] | None = None
    payment_status: (
        Literal["PENDING", "AUTHORIZED", "CAPTURED", "VOIDED", "FAILED"] | None
    ) = None
    risk_score: Decimal | None = Field(
        default=None, ge=Decimal("0.00"), le=Decimal("1.00")
    )
    paypal_order_id: str | None = None
    paypal_authorization_id: str | None = None


class TransactionResponse(TransactionBase):
    """Public DTO for returning transaction data."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="Internal UUID of the transaction")
    risk_score: Decimal = Field(description="Firewall risk score")
    decision: str = Field(description="Policy decision (ALLOW, HOLD, BLOCK)")
    payment_status: str = Field(description="Payment execution state")
    paypal_order_id: str | None = None
    paypal_authorization_id: str | None = None
    created_at: datetime
    updated_at: datetime
