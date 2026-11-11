"""Deterministic policy engine for AgentGuard.

Evaluates every purchase request against buyer-defined spending authority
and hard boundaries before any payment execution is authorized.
"""

from decimal import Decimal
import re
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from agentguard.core.risk_engine import PROMPT_INJECTION_PATTERNS


class PurchaseRequest(BaseModel):
    """Normalized purchase request presented to the policy engine."""

    amount: Decimal = Field(description="Transaction amount in specified currency")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    merchant_name: Optional[str] = Field(default=None, description="Merchant legal or trading name")
    merchant_id: Optional[str] = Field(default=None, description="Merchant account ID or domain")
    description: Optional[str] = Field(default=None, description="Purchase description or memo")
    external_reference: Optional[str] = Field(default=None, description="Client or agent reference")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary transaction metadata")


class PolicyConfig(BaseModel):
    """Buyer-defined policy configuration rules."""

    max_transaction_amount: Decimal = Field(
        default=Decimal("100.00"),
        description="Maximum permitted amount per single transaction",
    )
    daily_spending_limit: Decimal = Field(
        default=Decimal("500.00"),
        description="Maximum cumulative spending permitted across a 24-hour window",
    )
    allowed_merchants: List[str] = Field(
        default_factory=list,
        description="Allowlisted merchant names or IDs (empty list disables allowlisting)",
    )
    require_human_approval: bool = Field(
        default=False,
        description="Force human approval for all requests under this policy",
    )
    is_active: bool = Field(
        default=True,
        description="Whether this policy rule is active",
    )
    policy_version: str = Field(
        default="1.0",
        description="Version string for deterministic policy auditing",
    )


class SpendingContext(BaseModel):
    """Current cumulative spending and velocity context for the agent."""

    daily_cumulative_spent: Decimal = Field(
        default=Decimal("0.00"),
        description="Sum of all settled and held transactions for the current day",
    )
    recent_attempt_count: int = Field(
        default=0,
        description="Number of transaction requests attempted within the last hour",
    )


class PolicyEvaluationResult(BaseModel):
    """Intermediate evaluation results from policy rules."""

    policy_violations: List[str] = Field(default_factory=list)
    review_reasons: List[str] = Field(default_factory=list)
    requires_human_approval: bool = False
    policy_version: str = "1.0"


class PolicyEngine:
    """Enforces deterministic buyer policies against purchase requests."""

    SUPPORTED_CURRENCIES: set[str] = {"USD", "EUR", "GBP", "CAD", "AUD"}

    @classmethod
    def evaluate(
        cls,
        request: PurchaseRequest,
        policy: Optional[PolicyConfig],
        context: SpendingContext,
    ) -> PolicyEvaluationResult:
        """Run all deterministic policy rules against the incoming purchase request."""
        violations: List[str] = []
        review_reasons: List[str] = []
        requires_human = False

        # Rule 8: Unknown or unavailable policy configuration -> REVIEW
        if policy is None or not policy.is_active:
            review_reasons.append(
                "POLICY_CONFIG_UNAVAILABLE: Active policy configuration is missing or disabled."
            )
            return PolicyEvaluationResult(
                policy_violations=[],
                review_reasons=review_reasons,
                requires_human_approval=True,
                policy_version="unknown",
            )

        policy_ver = policy.policy_version

        # Rule 4: Invalid currency or negative / zero amount -> BLOCK
        if request.amount <= Decimal("0.00"):
            violations.append(
                f"INVALID_AMOUNT: Transaction amount must be positive, got {request.amount}."
            )

        norm_currency = (request.currency or "").strip().upper()
        if not norm_currency or norm_currency not in cls.SUPPORTED_CURRENCIES:
            violations.append(
                f"INVALID_CURRENCY: Unsupported or malformed currency '{request.currency}'."
            )

        # Rule 5: Missing merchant identity -> REVIEW
        name_clean = (request.merchant_name or "").strip()
        id_clean = (request.merchant_id or "").strip()
        is_missing_identity = not name_clean or not id_clean
        if is_missing_identity:
            review_reasons.append(
                "MISSING_MERCHANT_IDENTITY: Merchant name or identifier is missing."
            )
        elif policy.allowed_merchants:
            # Rule 3: Merchant must be on the allowlist (evaluated when identity is provided)
            if not cls._is_merchant_allowed(name_clean, id_clean, policy.allowed_merchants):
                violations.append(
                    f"MERCHANT_NOT_ALLOWLISTED: Merchant '{name_clean}' ({id_clean}) is not on the buyer allowlist."
                )

        # Rule 1 & Rule 6: Maximum transaction spending limit exceeded -> BLOCK
        if request.amount > policy.max_transaction_amount:
            violations.append(
                f"MAX_TRANSACTION_LIMIT_EXCEEDED: Amount ${request.amount:.2f} exceeds per-transaction limit of ${policy.max_transaction_amount:.2f}."
            )

        # Rule 2 & Rule 6: Daily cumulative spending limit exceeded -> BLOCK
        projected_total = context.daily_cumulative_spent + max(Decimal("0.00"), request.amount)
        if projected_total > policy.daily_spending_limit:
            violations.append(
                f"DAILY_SPENDING_LIMIT_EXCEEDED: Projected daily spending ${projected_total:.2f} exceeds limit of ${policy.daily_spending_limit:.2f}."
            )

        # Rule 7: Suspicious transaction metadata or injection artifacts -> REVIEW
        if cls._has_suspicious_metadata(request):
            review_reasons.append(
                "SUSPICIOUS_METADATA: Anomalous, adversarial, or injection artifacts detected in transaction payload."
            )

        # Policy-level explicit human approval requirement
        if policy.require_human_approval:
            requires_human = True
            review_reasons.append(
                "POLICY_MANDATED_APPROVAL: Active policy explicitly mandates human sign-off for all transactions."
            )

        if review_reasons:
            requires_human = True

        return PolicyEvaluationResult(
            policy_violations=violations,
            review_reasons=review_reasons,
            requires_human_approval=requires_human,
            policy_version=policy_ver,
        )

    @classmethod
    def _is_merchant_allowed(
        cls, merchant_name: str, merchant_id: str, allowed_list: List[str]
    ) -> bool:
        """Check if merchant name or ID matches any entry on the allowlist (case-insensitive)."""
        name_lower = merchant_name.lower()
        id_lower = merchant_id.lower()

        for item in allowed_list:
            clean_item = item.strip().lower()
            if not clean_item:
                continue
            # Exact match or substring / domain match
            if clean_item == name_lower or clean_item == id_lower:
                return True
            if clean_item in name_lower or clean_item in id_lower:
                return True
        return False

    @classmethod
    def _has_suspicious_metadata(cls, request: PurchaseRequest) -> bool:
        """Check for prompt injection signatures or suspicious payload anomalies."""
        text_to_scan = (request.description or "") + " "
        if request.metadata:
            text_to_scan += " ".join(str(v) for v in request.metadata.values())

        for _, pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(text_to_scan):
                return True

        # Check for control characters or non-printable garbage
        if request.description and any(ord(c) < 32 and c not in "\n\r\t" for c in request.description):
            return True

        return False
