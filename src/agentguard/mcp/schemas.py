"""Pydantic schemas and strict request validation for AgentGuard MCP interface."""

from decimal import Decimal, InvalidOperation
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator, model_validator

# Defensive limits against denial-of-service and buffer injection
MAX_DESCRIPTION_LENGTH = 1000
MAX_MERCHANT_NAME_LENGTH = 255
MAX_MERCHANT_ID_LENGTH = 100
MAX_NOTES_LENGTH = 2000
MAX_PAYLOAD_SIZE = 65536  # 64 KB


class InvoiceData(BaseModel):
    """Untrusted invoice metadata provided alongside a purchase request."""

    invoice_id: Optional[str] = Field(default=None, max_length=100)
    notes: Optional[str] = Field(default=None, max_length=MAX_NOTES_LENGTH)
    line_items: Optional[List[Dict[str, Any]]] = Field(default=None)
    payment_instructions: Optional[str] = Field(default=None, max_length=MAX_NOTES_LENGTH)
    contact_details: Optional[Dict[str, Any]] = Field(default=None)

    @field_validator("notes", "payment_instructions")
    @classmethod
    def strip_null_bytes(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        return v.replace("\x00", "").strip()


class PurchaseRequestInput(BaseModel):
    """Guarded purchase request input presented by autonomous AI buyer agents."""

    merchant_id: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MERCHANT_ID_LENGTH,
        description="Target merchant identifier or account domain",
    )
    merchant_name: str = Field(
        ...,
        min_length=1,
        max_length=MAX_MERCHANT_NAME_LENGTH,
        description="Legal or trading name of the merchant",
    )
    amount: str = Field(
        ...,
        description="Purchase amount as a numeric string (e.g. '49.99')",
    )
    currency: str = Field(
        default="USD",
        min_length=3,
        max_length=3,
        description="ISO 4217 three-letter currency code (e.g. 'USD')",
    )
    description: str = Field(
        default="",
        max_length=MAX_DESCRIPTION_LENGTH,
        description="Clear human-readable description of goods/services purchased",
    )
    invoice: Optional[InvoiceData | Dict[str, Any]] = Field(
        default=None,
        description="Invoice metadata including line items, notes, or payment instructions",
    )
    idempotency_key: Optional[str] = Field(
        default=None,
        max_length=100,
        description="Optional client-provided idempotency key for replay prevention",
    )

    @field_validator("merchant_id", "merchant_name", "description")
    @classmethod
    def sanitize_strings(cls, v: str) -> str:
        clean = v.replace("\x00", "").strip()
        if not clean and v != "":
            raise ValueError("Field cannot be empty or contain only whitespace.")
        return clean

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, v: str) -> str:
        clean = v.strip().upper()
        if len(clean) != 3 or not clean.isalpha():
            raise ValueError(f"Invalid currency '{v}'. Must be a 3-letter ISO code.")
        return clean

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: Any) -> str:
        try:
            dec = Decimal(str(v).strip())
        except (InvalidOperation, ValueError, TypeError) as exc:
            raise ValueError(f"Invalid monetary amount '{v}'. Must be a valid numeric value.") from exc

        if dec <= Decimal("0.00"):
            raise ValueError(f"Transaction amount must be strictly positive, got {dec}.")

        # Enforce maximum 2 decimal places
        exponent = dec.as_tuple().exponent
        if isinstance(exponent, int) and exponent < -2:
            raise ValueError(f"Sub-cent amounts not permitted for currency. Precision exceeds 2 decimal places: {dec}.")

        return f"{dec:.2f}"

    @model_validator(mode="before")
    @classmethod
    def validate_payload_size(cls, data: Any) -> Any:
        if isinstance(data, dict):
            # Check rough payload character count
            raw_len = sum(len(str(k)) + len(str(v)) for k, v in data.items())
            if raw_len > MAX_PAYLOAD_SIZE:
                raise ValueError(f"Payload size exceeds defensive limit of {MAX_PAYLOAD_SIZE} bytes.")
        return data


class PurchaseDecisionResponse(BaseModel):
    """Structured response returned to buyer agent describing policy & escrow outcome."""

    decision: Literal["APPROVE", "REVIEW", "BLOCK"]
    payment_status: str
    transaction_id: str
    external_reference: str
    risk_score: int
    reasons: List[str] = Field(default_factory=list)
    policy_violations: List[str] = Field(default_factory=list)
    security_threats: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    approval_id: Optional[str] = None
    paypal_order_id: Optional[str] = None
    paypal_authorization_id: Optional[str] = None
    created_at: str


class TransactionStatusResponse(BaseModel):
    """Detailed query response for transaction status and audit history."""

    transaction_id: str
    external_reference: str
    merchant_name: str
    merchant_id: str
    amount: str
    currency: str
    description: str
    decision: str
    payment_status: str
    risk_score: int
    paypal_order_id: Optional[str] = None
    paypal_authorization_id: Optional[str] = None
    created_at: str
    updated_at: str
    approval_status: Optional[str] = None
    audit_events: List[str] = Field(default_factory=list)


class PendingApprovalItem(BaseModel):
    """Single item in the administrative approval queue."""

    approval_id: str
    transaction_id: str
    external_reference: str
    merchant_name: str
    amount: str
    currency: str
    reason: Optional[str] = None
    created_at: str
    risk_score: int


class PendingApprovalsResponse(BaseModel):
    """Response returned to administrative reviewers listing pending escrow tasks."""

    pending_count: int
    approvals: List[PendingApprovalItem] = Field(default_factory=list)
