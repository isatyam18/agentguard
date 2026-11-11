"""Pydantic schemas for analytics and dashboard metrics."""

from typing import Any, Dict, List
from pydantic import BaseModel, Field


class OverviewStats(BaseModel):
    """High-level metrics for the overview dashboard."""

    total_transactions: int = Field(..., description="Total number of evaluated transactions")
    approved_transactions: int = Field(..., description="Number of approved transactions")
    blocked_transactions: int = Field(..., description="Number of blocked transactions")
    pending_approvals: int = Field(..., description="Number of pending human approvals")
    total_authorized_amount: str = Field(..., description="Sum of authorized transaction amounts (USD)")
    total_captured_amount: str = Field(..., description="Sum of captured transaction amounts (USD)")
    currency: str = Field(default="USD", description="Default operational currency")
    risk_distribution: Dict[str, int] = Field(
        ..., description="Risk distribution count: low (<0.35), medium (0.35-0.69), high (>=0.70)"
    )
    recent_activity: List[Dict[str, Any]] = Field(
        default_factory=list, description="Latest transaction activity stream"
    )


class SecurityStats(BaseModel):
    """Detailed threat and security firewall metrics."""

    threat_summary: Dict[str, int] = Field(
        ..., description="Counts of detected threats across security categories"
    )
    metrics: Dict[str, Any] = Field(
        ..., description="Defense rate, false positive rate, inspection latency, benchmark score"
    )
    risk_histogram: List[Dict[str, Any]] = Field(
        ..., description="Distribution of risk scores across buckets"
    )
    top_blocked_reasons: List[Dict[str, Any]] = Field(
        ..., description="Most frequent reasons for blocking purchase requests"
    )
