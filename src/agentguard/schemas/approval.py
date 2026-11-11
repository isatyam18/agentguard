"""Pydantic schemas for Human-in-the-Loop approvals."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ApprovalCreate(BaseModel):
    """Payload to submit an approval request."""

    transaction_id: str = Field(description="UUID of transaction requiring approval")
    reason: str | None = Field(
        default=None,
        description="Reason why approval was required (e.g. threshold exceeded)",
    )


class ApprovalDecision(BaseModel):
    """Payload submitted by human reviewer to approve or reject escrow."""

    status: Literal["APPROVED", "REJECTED"] = Field(
        ...,
        description="Decision outcome (APPROVED or REJECTED)",
    )
    reviewer: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of the human reviewer or operator",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Optional justification or review notes",
    )


class ApprovalResponse(BaseModel):
    """Public DTO for approval records."""

    model_config = ConfigDict(from_attributes=True)

    id: str = Field(description="UUID of the approval record")
    transaction_id: str = Field(description="Associated transaction UUID")
    status: str = Field(description="Approval state (PENDING, APPROVED, REJECTED)")
    reviewer: str | None = None
    reason: str | None = None
    created_at: datetime
    resolved_at: datetime | None = None


class ApprovalActionRequest(BaseModel):
    """Payload to approve or reject an escrowed transaction."""

    reviewer: str = Field(
        ...,
        min_length=1,
        max_length=100,
        description="Identifier of the human reviewer or operator",
    )
    reason: str | None = Field(
        default=None,
        max_length=500,
        description="Justification notes for approval or rejection",
    )
    admin_token: str | None = Field(
        default=None,
        description="Administrative secret token for authentication",
    )
    idempotency_key: str | None = Field(
        default=None,
        max_length=100,
        description="Client idempotency key for replay prevention",
    )


class ApprovalDetailResponse(BaseModel):
    """Comprehensive approval details including transaction metadata and security evidence."""

    approval_id: str
    approval_status: str
    transaction_id: str
    external_reference: str
    merchant_name: str
    merchant_id: str
    amount: str
    currency: str
    description: str
    current_state: str
    risk_score: int
    reason_for_hold: str | None = None
    paypal_order_id: str | None = None
    paypal_authorization_id: str | None = None
    created_at: str
    resolved_at: str | None = None
    reviewer: str | None = None
    policy_violations: list[str] = Field(default_factory=list)
    security_evidence: list[str] = Field(default_factory=list)
    audit_events: list[str] = Field(default_factory=list)

