"""Data contracts and schemas for invoice scanning and threat detection."""

from decimal import Decimal
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class InvoiceLineItem(BaseModel):
    """A discrete line item on a commercial invoice."""

    description: str = Field(..., min_length=1, description="Product or service description")
    quantity: Decimal = Field(default=Decimal("1.00"), description="Quantity purchased")
    unit_price: Decimal = Field(..., description="Unit price per item")
    total: Decimal = Field(..., description="Reported total for this line item")

    @field_validator("quantity", "unit_price", "total")
    @classmethod
    def validate_decimals(cls, v: Decimal) -> Decimal:
        if v.as_tuple().exponent < -2:
            raise ValueError("Line item values cannot have more than 2 decimal places.")
        return v


class ContactDetails(BaseModel):
    """Merchant contact and billing support details."""

    email: Optional[str] = None
    phone: Optional[str] = None
    support_url: Optional[str] = None
    address: Optional[str] = None


class NormalizedInvoice(BaseModel):
    """Normalized commercial invoice object presented for security inspection."""

    invoice_id: str = Field(..., min_length=1, description="Unique invoice or reference identifier")
    merchant_name: str = Field(..., min_length=1, description="Merchant commercial or trading name")
    merchant_id: str = Field(..., min_length=1, description="Merchant account ID or domain")
    amount: Decimal = Field(..., description="Reported total invoice amount")
    currency: str = Field(default="USD", min_length=3, max_length=3, description="ISO 4217 currency")
    description: str = Field(..., description="Summary invoice description or service summary")
    line_items: List[InvoiceLineItem] = Field(default_factory=list, description="Itemized billing breakdown")
    notes: Optional[str] = Field(default=None, description="Invoice notes, memo, or payment terms")
    payment_instructions: Optional[str] = Field(default=None, description="Instructions for payment routing")
    contact_details: Optional[ContactDetails] = Field(default=None, description="Support contact information")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary invoice metadata")


class ThreatCategory(str):
    PROMPT_INJECTION = "PROMPT_INJECTION"
    PHISHING = "PHISHING"
    INVOICE_MANIPULATION = "INVOICE_MANIPULATION"
    UNUSUAL_BEHAVIOR = "UNUSUAL_BEHAVIOR"


class ScanResult(BaseModel):
    """Canonical security scan verdict matching AgentGuard specifications."""

    is_suspicious: bool = Field(description="True if any security or integrity threats were identified")
    threat_categories: List[Literal["PROMPT_INJECTION", "PHISHING", "INVOICE_MANIPULATION", "UNUSUAL_BEHAVIOR"]] = Field(
        default_factory=list, description="Detected threat classifications"
    )
    severity: Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"] = Field(
        default="LOW", description="Overall threat severity rating"
    )
    evidence: List[str] = Field(
        default_factory=list, description="Specific textual or mathematical evidence for findings"
    )
    recommended_action: Literal["ALLOW", "REVIEW", "BLOCK"] = Field(
        default="ALLOW", description="Enforced policy firewall recommendation"
    )
    confidence: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence score of the threat assessment"
    )

    model_config = ConfigDict(from_attributes=True)
