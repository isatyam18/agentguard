"""Merchant identity, phishing link, and fraudulent payment instruction validator."""

import re
from typing import List, Tuple
from agentguard.security.schemas import NormalizedInvoice

# Free webmail providers that enterprise merchants would never legitimately use for invoices
FREE_WEBMAIL_DOMAINS: set[str] = {
    "gmail.com",
    "yahoo.com",
    "hotmail.com",
    "outlook.com",
    "protonmail.com",
    "proton.me",
    "mail.com",
    "yandex.com",
    "yandex.ru",
    "yopmail.com",
    "tempmail.com",
    "guerrillamail.com",
}

# Major enterprise platforms where free webmail indicates impersonation
ENTERPRISE_MERCHANTS: set[str] = {
    "openai",
    "anthropic",
    "aws",
    "amazon web services",
    "microsoft",
    "github",
    "google",
    "google cloud",
    "cloudflare",
    "stripe",
    "paypal",
    "salesforce",
    "datadog",
}

# Suspicious TLDs frequently utilized in automated phishing campaigns
SUSPICIOUS_TLDS: list[str] = [
    ".xyz", ".top", ".click", ".buzz", ".ru", ".cc", ".tk",
    ".live", ".work", ".biz", ".download", ".link", ".rest",
]

# Cryptocurrency wallet address patterns
CRYPTO_PATTERNS: list[Tuple[str, re.Pattern[str]]] = [
    ("BITCOIN", re.compile(r"\b(?:[13][a-km-zA-HJ-NP-Z1-9]{25,34}|bc1[a-z0-9]{39,59})\b")),
    ("ETHEREUM", re.compile(r"\b0x[a-fA-F0-9]{40}\b")),
    ("MONERO", re.compile(r"\b4[0-9AB][1-9A-HJ-NP-Za-km-z]{93}\b")),
    ("USDT_TRC20", re.compile(r"\bT[A-Za-z1-9]{33}\b")),
]

# Raw IP address URL pattern
RAW_IP_URL_PATTERN = re.compile(r"https?://(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?(?:/|\b)")

# Brand typosquatting / lookalike regexes
LOOKALIKE_PATTERNS: list[Tuple[str, re.Pattern[str]]] = [
    (
        "PAYPAL_LOOKALIKE",
        re.compile(
            r"(?i)\b(?:paypa[1i]|paypal-(?:security|verify|verification|token|support|checkout|update|billing|login)|pay-pal)(?:-[a-z0-9]+)?\.[a-z0-9\.\-]+\b"  # [REDACTED]
        ),
    ),
    (
        "OPENAI_LOOKALIKE",
        re.compile(
            r"(?i)\b(?:open-ai|openai-(?:billing|auth|pay|support)|0penai)(?:-[a-z0-9]+)?\.[a-z0-9\.\-]+\b"
        ),
    ),
    (
        "AWS_LOOKALIKE",
        re.compile(
            r"(?i)\b(?:aws-(?:billing|invoice|support|pay)|amazon-aws-pay)(?:-[a-z0-9]+)?\.[a-z0-9\.\-]+\b"
        ),
    ),
]


class MerchantValidator:
    """Validates merchant authenticity, detects phishing links, and catches payment routing diversion."""

    @classmethod
    def validate_merchant(cls, invoice: NormalizedInvoice) -> Tuple[bool, List[str], List[str]]:
        """Scan merchant metadata, contact info, notes, and payment instructions.

        Returns:
            (is_suspicious, threat_categories, evidence)
        """
        threats: set[str] = set()
        evidence: List[str] = []

        all_text = " ".join(
            filter(
                None,
                [
                    invoice.merchant_name,
                    invoice.merchant_id,
                    invoice.description,
                    invoice.notes,
                    invoice.payment_instructions,
                    invoice.contact_details.email if invoice.contact_details else None,
                    invoice.contact_details.support_url if invoice.contact_details else None,
                ],
            )
        )

        # 1. Check for Unexpected Cryptocurrency Payment Instructions
        for crypto_name, pattern in CRYPTO_PATTERNS:
            matches = pattern.findall(all_text)
            if matches:
                threats.add("PHISHING")
                threats.add("UNUSUAL_BEHAVIOR")
                evidence.append(
                    f"Unexpected cryptocurrency {crypto_name} address detected in payment instructions: '{matches[0]}'."
                )

        # 2. Check for Suspicious Payment Links & Raw IP URLs
        if RAW_IP_URL_PATTERN.search(all_text):
            threats.add("PHISHING")
            evidence.append("Invoice contains raw IP address URL in payment links or contact details.")

        for name, pattern in LOOKALIKE_PATTERNS:
            matches = pattern.findall(all_text)
            if matches:
                threats.add("PHISHING")
                evidence.append(f"Detected suspicious typosquatting/lookalike domain: '{matches[0]}'.")

        # 3. Check for Free Webmail Used by Enterprise Brands
        m_name_lower = invoice.merchant_name.lower()
        is_enterprise = any(ent in m_name_lower for ent in ENTERPRISE_MERCHANTS)

        if invoice.contact_details and invoice.contact_details.email:
            email = invoice.contact_details.email.strip().lower()
            domain = email.split("@")[-1] if "@" in email else ""
            if is_enterprise and domain in FREE_WEBMAIL_DOMAINS:
                threats.add("PHISHING")
                threats.add("INVOICE_MANIPULATION")
                evidence.append(
                    f"Enterprise merchant '{invoice.merchant_name}' provided free webmail contact '{email}'."
                )

        # 4. Check for Suspicious TLDs in Merchant ID or URLs
        m_id_lower = invoice.merchant_id.lower()
        if any(m_id_lower.endswith(tld) or f"{tld}/" in m_id_lower for tld in SUSPICIOUS_TLDS):
            threats.add("PHISHING")
            evidence.append(f"Merchant ID '{invoice.merchant_id}' uses high-risk TLD associated with phishing.")

        # 5. Check Merchant Name vs Merchant ID Mismatch
        if is_enterprise:
            # If merchant claims to be AWS, OpenAI, etc. but merchant_id is completely disparate
            if not any(ent in m_id_lower for ent in ENTERPRISE_MERCHANTS):
                threats.add("INVOICE_MANIPULATION")
                threats.add("PHISHING")
                evidence.append(
                    f"Merchant identity mismatch: Name claims enterprise brand '{invoice.merchant_name}' but ID is '{invoice.merchant_id}'."
                )

        is_suspicious = len(threats) > 0
        return is_suspicious, sorted(list(threats)), evidence
