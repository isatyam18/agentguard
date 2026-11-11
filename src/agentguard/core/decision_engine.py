"""Deterministic decision engine for AgentGuard.

Coordinates policy verification and objective risk scoring into an immutable,
reproducible decision: APPROVE, REVIEW, or BLOCK.
"""

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field

from agentguard.core.policy_engine import (
    PolicyConfig,
    PolicyEngine,
    PurchaseRequest,
    SpendingContext,
)
from agentguard.core.risk_engine import RiskEngine


class DecisionOutput(BaseModel):
    """Canonical decision output contract required by AgentGuard specifications."""

    decision: Literal["APPROVE", "REVIEW", "BLOCK"] = Field(
        description="Final deterministic verdict for the purchase request"
    )
    risk_score: int = Field(
        ge=0, le=100, description="Transparent risk score from 0 to 100"
    )
    reasons: List[str] = Field(
        default_factory=list,
        description="Comprehensive explanations for the decision and risk factors",
    )
    policy_violations: List[str] = Field(
        default_factory=list,
        description="Explicit hard policy violations, if any",
    )
    requires_human_approval: bool = Field(
        default=False,
        description="True if human-in-the-loop sign-off is mandatory before settlement",
    )
    policy_version: str = Field(
        default="1.0",
        description="Version of policy evaluated for audit reproducibility",
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert decision to standard JSON dictionary."""
        return self.model_dump()


class DecisionEngine:
    """Evaluates purchase requests against policies and risk signals to generate decisions."""

    # Risk score threshold at or above which an unblocked transaction mandates human review
    REVIEW_RISK_THRESHOLD: int = 50

    @classmethod
    def evaluate(
        cls,
        request: PurchaseRequest,
        policy: Optional[PolicyConfig],
        context: SpendingContext,
    ) -> DecisionOutput:
        """Deterministically evaluate purchase request.

        Guarantees:
        - Explicit policy violations ALWAYS result in BLOCK.
        - Risk score cannot override hard spending limits.
        - REVIEW is never converted to APPROVE.
        - A failed evaluation or missing policy never authorizes a payment.
        - Identical inputs produce identical outputs.
        """
        reasons: List[str] = []

        # 1. Evaluate hard deterministic policies
        try:
            policy_result = PolicyEngine.evaluate(request, policy, context)
        except Exception as exc:
            # Defensive guard: any unhandled exception in policy logic defaults to BLOCK / REVIEW
            return DecisionOutput(
                decision="BLOCK",
                risk_score=100,
                reasons=[f"INTERNAL_POLICY_ERROR: Evaluation exception '{type(exc).__name__}'."],
                policy_violations=["INTERNAL_EVALUATION_ERROR"],
                requires_human_approval=True,
                policy_version="error",
            )

        # 2. Evaluate objective risk signals
        daily_limit = policy.daily_spending_limit if policy else request.amount
        risk_result = RiskEngine.evaluate_risk(
            amount=request.amount,
            currency=request.currency,
            merchant_name=request.merchant_name,
            merchant_id=request.merchant_id,
            description=request.description,
            daily_spent=context.daily_cumulative_spent,
            daily_limit=daily_limit,
            recent_attempt_count=context.recent_attempt_count,
            metadata=request.metadata,
        )

        # Collect all explanatory reasons
        reasons.extend(policy_result.review_reasons)
        reasons.extend(risk_result.reasons)

        # 3. Decision Rule Hierarchy
        # Rule A: Any explicit policy violation ALWAYS blocks immediately
        if policy_result.policy_violations:
            for violation in policy_result.policy_violations:
                reasons.insert(0, f"VIOLATION: {violation}")

            return DecisionOutput(
                decision="BLOCK",
                risk_score=risk_result.score,
                reasons=reasons,
                policy_violations=policy_result.policy_violations,
                requires_human_approval=False,
                policy_version=policy_result.policy_version,
            )

        # Rule B: Missing merchant identity, suspicious metadata, unconfigured policy, or elevated risk score -> REVIEW
        is_elevated_risk = risk_result.score >= cls.REVIEW_RISK_THRESHOLD
        if is_elevated_risk:
            reasons.append(
                f"ELEVATED_RISK_SCORE: Risk score of {risk_result.score}/100 exceeds autonomous approval threshold ({cls.REVIEW_RISK_THRESHOLD})."
            )

        if policy_result.requires_human_approval or is_elevated_risk:
            return DecisionOutput(
                decision="REVIEW",
                risk_score=risk_result.score,
                reasons=reasons,
                policy_violations=[],
                requires_human_approval=True,
                policy_version=policy_result.policy_version,
            )

        # Rule C: All checks passed with low risk -> APPROVE
        reasons.append("All policy parameters verified. Risk score within autonomous limits.")
        return DecisionOutput(
            decision="APPROVE",
            risk_score=risk_result.score,
            reasons=reasons,
            policy_violations=[],
            requires_human_approval=False,
            policy_version=policy_result.policy_version,
        )
