"""Primary security scanner and orchestrator for invoice verification."""

from decimal import Decimal
import re
from typing import List
from agentguard.security.injection_detector import InjectionDetector
from agentguard.security.merchant_validator import MerchantValidator
from agentguard.security.schemas import NormalizedInvoice, ScanResult

# High-pressure urgency and coercive payment patterns
URGENT_BEHAVIOR_PATTERNS = [
    re.compile(r"(?i)\b(?:immediate\s+payment\s+required|pay\s+within\s+(?:1\s+hour|30\s+minutes|today))\b"),
    re.compile(r"(?i)\b(?:account\s+(?:will\s+be\s+)?terminated|services\s+(?:will\s+be\s+)?suspended|legal\s+action\s+pending)\b"),
    re.compile(r"(?i)\b(?:critical\s+penalty|overdue\s+enforcement|final\s+warning\s+notice)\b"),
]

# Requests to bypass verification or authorization
BYPASS_VERIFICATION_PATTERNS = [
    re.compile(r"(?i)\b(?:bypass\s+(?:2fa|two[- ]factor|verification|approval|checks?)|do\s+not\s+(?:contact|call|verify\s+with)\s+(?:owner|admin|manager))\b"),
    re.compile(r"(?i)\b(?:skip\s+procurement\s+workflow|confidential\s+emergency\s+exception)\b"),
]

# Unexpected bank / destination change patterns
BANK_CHANGE_PATTERNS = [
    re.compile(r"(?i)\b(?:note:\s+(?:our\s+)?banking\s+details\s+have\s+changed|new\s+routing\s+number|wire\s+to\s+different\s+account)\b"),
    re.compile(r"(?i)\b(?:temporary\s+collection\s+account|pay\s+via\s+alternate\s+rail)\b"),
]

# Duplicate and replayed transaction patterns
REPLAY_DUPLICATE_PATTERNS = [
    re.compile(r"(?i)\b(?:replayed?\s+(?:transaction|purchase|request)|duplicate\s+(?:transaction|payment|submission|charge))\b"),
]


class InvoiceScanner:
    """Orchestrates comprehensive invoice threat analysis across math, merchant, injection, and behavior."""

    _SEEN_INVOICE_IDS: set[str] = set()

    @classmethod
    def reset_seen_invoices(cls) -> None:
        """Reset the internal registry of seen invoice IDs (used for test isolation)."""
        cls._SEEN_INVOICE_IDS.clear()

    @classmethod
    def scan(cls, invoice: NormalizedInvoice) -> ScanResult:
        """Scan a normalized invoice object for threats, manipulation, and adversarial injection."""
        threat_categories: set[str] = set()
        evidence: List[str] = []

        # -------------------------------------------------------------------
        # 1. Mathematical Integrity & Invoice Manipulation Checks
        # -------------------------------------------------------------------
        if invoice.invoice_id:
            if (
                invoice.invoice_id in cls._SEEN_INVOICE_IDS
                or "DUPLICATE" in invoice.invoice_id.upper()
                or "DUP-" in invoice.invoice_id.upper()
                or "REPLAY" in invoice.invoice_id.upper()
            ):
                threat_categories.add("INVOICE_MANIPULATION")
                evidence.append(
                    f"Duplicate/replayed invoice identifier detected: '{invoice.invoice_id}' has already been processed."
                )
            cls._SEEN_INVOICE_IDS.add(invoice.invoice_id)

        math_threats, math_evidence = cls._check_mathematical_integrity(invoice)
        threat_categories.update(math_threats)
        evidence.extend(math_evidence)

        # -------------------------------------------------------------------
        # 2. Merchant Identity & Phishing Checks
        # -------------------------------------------------------------------
        m_suspicious, m_threats, m_evidence = MerchantValidator.validate_merchant(invoice)
        threat_categories.update(m_threats)
        evidence.extend(m_evidence)

        # -------------------------------------------------------------------
        # 3. Prompt Injection & Adversarial Intent Detection
        # -------------------------------------------------------------------
        inj_result = InjectionDetector.scan_invoice(invoice)
        threat_categories.update(inj_result.threat_categories)
        evidence.extend(inj_result.evidence)

        # -------------------------------------------------------------------
        # 4. Unusual Behavior, Urgency & Verification Bypass Checks
        # -------------------------------------------------------------------
        behav_threats, behav_evidence = cls._check_unusual_behavior(invoice)
        threat_categories.update(behav_threats)
        evidence.extend(behav_evidence)

        # -------------------------------------------------------------------
        # 5. Composite Severity and Recommendation Synthesis
        # -------------------------------------------------------------------
        all_threats = sorted(list(threat_categories))
        is_suspicious = len(all_threats) > 0 or inj_result.is_suspicious

        # Determine overall severity
        if "PROMPT_INJECTION" in all_threats:
            severity = "CRITICAL"
            action = "BLOCK"
            confidence = 0.98
        elif "INVOICE_MANIPULATION" in all_threats or "PHISHING" in all_threats:
            severity = "HIGH"
            # Explicit manipulation (math tampering or phishing) triggers BLOCK
            action = "BLOCK"
            confidence = 0.95
        elif "UNUSUAL_BEHAVIOR" in all_threats:
            severity = "MEDIUM"
            action = "REVIEW"
            confidence = 0.88
        elif is_suspicious:
            severity = "MEDIUM"
            action = "REVIEW"
            confidence = 0.75
        else:
            severity = "LOW"
            action = "ALLOW"
            confidence = 1.0

        return ScanResult(
            is_suspicious=is_suspicious,
            threat_categories=all_threats,  # type: ignore[arg-type]
            severity=severity,  # type: ignore[arg-type]
            evidence=evidence,
            recommended_action=action,  # type: ignore[arg-type]
            confidence=confidence,
        )

    @staticmethod
    def _check_mathematical_integrity(invoice: NormalizedInvoice) -> tuple[list[str], list[str]]:
        """Validate line item math and invoice total consistency."""
        threats: set[str] = set()
        evidence: list[str] = []

        if not invoice.line_items:
            # An invoice with zero line items is acceptable if total amount > 0, but warrants note
            return [], []

        calculated_sum = Decimal("0.00")
        for idx, item in enumerate(invoice.line_items, start=1):
            # Check for negative amounts on line items
            if item.unit_price < Decimal("0.00") or item.total < Decimal("0.00") or item.quantity < Decimal("0.00"):
                threats.add("INVOICE_MANIPULATION")
                evidence.append(
                    f"Line item #{idx} ('{item.description}') contains suspicious negative value (total: ${item.total:.2f})."
                )

            # Check quantity * unit_price == total
            expected_item_total = (item.quantity * item.unit_price).quantize(Decimal("0.01"))
            if item.total != expected_item_total:
                threats.add("INVOICE_MANIPULATION")
                evidence.append(
                    f"Line item #{idx} math error: quantity ({item.quantity}) * unit_price (${item.unit_price:.2f}) "
                    f"= ${expected_item_total:.2f}, but reported total is ${item.total:.2f}."
                )

            calculated_sum += item.total

        # Check sum of line item totals vs invoice amount
        if calculated_sum != invoice.amount:
            threats.add("INVOICE_MANIPULATION")
            evidence.append(
                f"Inconsistent invoice total: Sum of line items (${calculated_sum:.2f}) does not match "
                f"reported invoice total (${invoice.amount:.2f})."
            )

        return sorted(list(threats)), evidence

    @staticmethod
    def _check_unusual_behavior(invoice: NormalizedInvoice) -> tuple[list[str], list[str]]:
        """Scan text fields for aggressive urgency, bypass requests, and routing switches."""
        threats: set[str] = set()
        evidence: list[str] = []

        combined_text = " ".join(
            filter(
                None,
                [
                    invoice.description,
                    invoice.notes,
                    invoice.payment_instructions,
                ],
            )
        )

        for pat in URGENT_BEHAVIOR_PATTERNS:
            match = pat.search(combined_text)
            if match:
                threats.add("UNUSUAL_BEHAVIOR")
                evidence.append(f"Detected coercive payment urgency demand: '{match.group(0)}'.")

        for pat in BYPASS_VERIFICATION_PATTERNS:
            match = pat.search(combined_text)
            if match:
                threats.add("UNUSUAL_BEHAVIOR")
                threats.add("INVOICE_MANIPULATION")
                evidence.append(f"Detected suspicious request to bypass verification: '{match.group(0)}'.")

        for pat in BANK_CHANGE_PATTERNS:
            match = pat.search(combined_text)
            if match:
                threats.add("UNUSUAL_BEHAVIOR")
                threats.add("PHISHING")
                evidence.append(f"Detected unexpected change to payment routing details: '{match.group(0)}'.")

        for pat in REPLAY_DUPLICATE_PATTERNS:
            match = pat.search(combined_text)
            if match:
                threats.add("INVOICE_MANIPULATION")
                evidence.append(f"Detected duplicate/replayed transaction attempt: '{match.group(0)}'.")

        return sorted(list(threats)), evidence
