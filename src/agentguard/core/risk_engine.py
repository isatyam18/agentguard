"""Deterministic risk scoring engine for AgentGuard.

Calculates transparent, reproducible risk scores (0-100) from objective transaction signals.
Risk scoring is strictly decoupled from hard policy violations.
"""

from decimal import Decimal
import re
from typing import Any, Dict, List
from pydantic import BaseModel, Field


class RiskSignal(BaseModel):
    """Individual signal breakdown for transparency."""
    name: str
    points: int
    reason: str


class RiskAssessment(BaseModel):
    """Aggregate risk score and contributing signals."""
    score: int = Field(ge=0, le=100)
    signals: List[RiskSignal] = Field(default_factory=list)
    reasons: List[str] = Field(default_factory=list)


# Known high-reputation vendor identifiers and domains
TRUSTED_MERCHANTS: set[str] = {
    "openai",
    "anthropic",
    "aws",
    "amazon web services",
    "github",
    "google cloud",
    "cloudflare",
    "microsoft azure",
    "stripe",
    "vercel",
    "fastly",
    "datadog",
}

# Prompt injection & adversarial transaction description patterns
PROMPT_INJECTION_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("IGNORE_INSTRUCTIONS", re.compile(r"(?i)\bignore\s+(?:all\s+)?(?:previous|prior)\s+instructions?\b")),
    ("SYSTEM_OVERRIDE", re.compile(r"(?i)\b(?:system\s+override|sudo\s+mode|root\s+access|admin\s+override)\b")),
    ("POLICY_BYPASS", re.compile(r"(?i)\b(?:bypass|disregard|disable|skip)\s+(?:all\s+)?(?:security|guard|policy|firewall|limits?)\b")),
    ("JAILBREAK_KEYWORD", re.compile(r"(?i)\b(?:jailbreak|dan\s+mode|developer\s+mode\s+enabled)\b")),
    ("URGENT_EXFILTRATION", re.compile(r"(?i)\b(?:transfer\s+all\s+funds|drain\s+wallet|send\s+max\s+budget|emergency\s+payout)\b")),
    ("SUSPICIOUS_PAYLOAD", re.compile(r"(?i)(?:<script|javascript:|eval\(|base64_decode|cmd\.exe|/bin/sh)")),
]


class RiskEngine:
    """Calculates deterministic risk scores for purchase requests."""

    @classmethod
    def evaluate_risk(
        cls,
        amount: Decimal,
        currency: str,
        merchant_name: str | None,
        merchant_id: str | None,
        description: str | None,
        daily_spent: Decimal,
        daily_limit: Decimal,
        recent_attempt_count: int = 0,
        metadata: Dict[str, Any] | None = None,
    ) -> RiskAssessment:
        """Compute an objective, reproducible risk score between 0 and 100."""
        signals: List[RiskSignal] = []

        # 1. Transaction Amount Risk (0 - 25 points)
        # Higher amounts consume more authority and carry higher risk
        amount_points = cls._score_amount(amount)
        if amount_points > 0:
            signals.append(
                RiskSignal(
                    name="TRANSACTION_AMOUNT",
                    points=amount_points,
                    reason=f"Transaction amount of ${amount:.2f} allocated {amount_points} risk points.",
                )
            )

        # 2. Merchant Trust & Verification (0 - 25 points)
        merchant_points, merchant_reasons = cls._score_merchant(merchant_name, merchant_id)
        if merchant_points > 0:
            signals.append(
                RiskSignal(
                    name="MERCHANT_TRUST",
                    points=merchant_points,
                    reason="; ".join(merchant_reasons),
                )
            )

        # 3. Budget Consumption Velocity (0 - 20 points)
        budget_points, budget_reason = cls._score_budget_consumption(
            amount, daily_spent, daily_limit
        )
        if budget_points > 0:
            signals.append(
                RiskSignal(
                    name="BUDGET_CONSUMPTION",
                    points=budget_points,
                    reason=budget_reason,
                )
            )

        # 4. Description & Invoice Anomalies (0 - 15 points)
        anomaly_points, anomaly_reason = cls._score_invoice_anomalies(description)
        if anomaly_points > 0:
            signals.append(
                RiskSignal(
                    name="INVOICE_ANOMALY",
                    points=anomaly_points,
                    reason=anomaly_reason,
                )
            )

        # 5. Prompt Injection & Adversarial Indicators (0 - 25 points)
        injection_points, injection_reasons = cls._score_injection_indicators(description, metadata)
        if injection_points > 0:
            signals.append(
                RiskSignal(
                    name="PROMPT_INJECTION_ARTIFACT",
                    points=injection_points,
                    reason="; ".join(injection_reasons),
                )
            )

        # 6. Repeated Purchase Attempts / Velocity Flurry (0 - 15 points)
        velocity_points = cls._score_velocity(recent_attempt_count)
        if velocity_points > 0:
            signals.append(
                RiskSignal(
                    name="REPEATED_ATTEMPTS",
                    points=velocity_points,
                    reason=f"{recent_attempt_count} purchase attempts in the current velocity window.",
                )
            )

        # 7. Merchant Identity Mismatch (0 - 15 points)
        mismatch_points, mismatch_reason = cls._score_identity_mismatch(merchant_name, merchant_id)
        if mismatch_points > 0:
            signals.append(
                RiskSignal(
                    name="IDENTITY_MISMATCH",
                    points=mismatch_points,
                    reason=mismatch_reason,
                )
            )

        # Aggregate and clamp between 0 and 100
        raw_score = sum(s.points for s in signals)
        final_score = min(100, max(0, raw_score))
        all_reasons = [s.reason for s in signals]

        return RiskAssessment(
            score=final_score,
            signals=signals,
            reasons=all_reasons,
        )

    @staticmethod
    def _score_amount(amount: Decimal) -> int:
        if amount <= Decimal("0.00"):
            return 25  # Invalid amounts carry maximum amount risk
        if amount <= Decimal("20.00"):
            return 0
        if amount <= Decimal("50.00"):
            return 8
        if amount <= Decimal("80.00"):
            return 16
        return 25

    @classmethod
    def _score_merchant(cls, merchant_name: str | None, merchant_id: str | None) -> tuple[int, list[str]]:
        reasons: list[str] = []
        if not merchant_name or not merchant_id:
            return 25, ["Missing merchant name or merchant identifier."]

        name_lower = merchant_name.strip().lower()
        id_lower = merchant_id.strip().lower()

        # Check trusted merchant lists
        is_trusted = any(t in name_lower or t in id_lower for t in TRUSTED_MERCHANTS)
        if is_trusted:
            return 0, []

        reasons.append(f"Merchant '{merchant_name}' is not in the tier-1 global trust registry (+10 pts).")
        return 10, reasons

    @staticmethod
    def _score_budget_consumption(
        amount: Decimal, daily_spent: Decimal, daily_limit: Decimal
    ) -> tuple[int, str]:
        if daily_limit <= Decimal("0.00"):
            return 20, "Daily spending limit is zero or unconfigured."

        projected = daily_spent + max(Decimal("0.00"), amount)
        ratio = projected / daily_limit

        if ratio <= Decimal("0.25"):
            return 0, ""
        if ratio <= Decimal("0.50"):
            return 5, f"Projected spending reaches {float(ratio * 100):.1f}% of daily budget limit (+5 pts)."
        if ratio <= Decimal("0.75"):
            return 10, f"Projected spending reaches {float(ratio * 100):.1f}% of daily budget limit (+10 pts)."
        if ratio <= Decimal("1.00"):
            return 15, f"Projected spending reaches {float(ratio * 100):.1f}% of daily budget limit (+15 pts)."
        return 20, f"Projected spending exceeds 100% of daily budget limit (+20 pts)."

    @staticmethod
    def _score_invoice_anomalies(description: str | None) -> tuple[int, str]:
        if not description or not description.strip():
            return 15, "Purchase description is completely absent (+15 pts)."

        cleaned = description.strip()
        if len(cleaned) < 5:
            return 10, "Purchase description is suspiciously terse (< 5 chars) (+10 pts)."
        if len(cleaned) > 800:
            return 15, "Purchase description has abnormal length (> 800 chars) (+15 pts)."

        # Check for unprintable/control characters
        if any(ord(c) < 32 and c not in "\n\r\t" for c in cleaned):
            return 15, "Purchase description contains non-printable control characters (+15 pts)."

        return 0, ""

    @classmethod
    def _score_injection_indicators(
        cls, description: str | None, metadata: Dict[str, Any] | None
    ) -> tuple[int, list[str]]:
        reasons: list[str] = []
        text_to_scan = (description or "") + " "
        if metadata:
            text_to_scan += " ".join(str(v) for v in metadata.values())

        matched_points = 0
        for code, pattern in PROMPT_INJECTION_PATTERNS:
            if pattern.search(text_to_scan):
                matched_points = max(matched_points, 25)
                reasons.append(f"Prompt injection indicator detected: [{code}] (+25 pts).")

        return matched_points, reasons

    @staticmethod
    def _score_velocity(recent_attempt_count: int) -> int:
        if recent_attempt_count <= 2:
            return 0
        if recent_attempt_count <= 5:
            return 5
        if recent_attempt_count <= 10:
            return 10
        return 15

    @staticmethod
    def _score_identity_mismatch(merchant_name: str | None, merchant_id: str | None) -> tuple[int, str]:
        if not merchant_name or not merchant_id:
            return 0, ""

        name_lower = merchant_name.strip().lower()
        id_lower = merchant_id.strip().lower()

        # Check for obvious brand impersonation / domain divergence
        # e.g., name="Amazon Web Services" but id contains an unrelated domain like "paypal-support-verify.com"
        suspicious_domains = [".ru", ".xyz", ".top", ".su", ".click", ".buzz"]
        if any(s in id_lower for s in suspicious_domains) and not any(s in name_lower for s in suspicious_domains):
            return 15, f"Suspicious TLD in merchant ID '{merchant_id}' diverges from merchant name (+15 pts)."

        return 0, ""
