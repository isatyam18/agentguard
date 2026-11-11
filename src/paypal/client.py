"""Direct alias for paypal.client."""

from agentguard.paypal.client import (
    PayPalClient,
    SANDBOX_BASE_URL,
)

__all__ = [
    "PayPalClient",
    "SANDBOX_BASE_URL",
]
