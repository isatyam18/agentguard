"""Direct alias for security.merchant_validator."""

from agentguard.security.merchant_validator import (
    ENTERPRISE_MERCHANTS,
    FREE_WEBMAIL_DOMAINS,
    MerchantValidator,
)

__all__ = [
    "ENTERPRISE_MERCHANTS",
    "FREE_WEBMAIL_DOMAINS",
    "MerchantValidator",
]
