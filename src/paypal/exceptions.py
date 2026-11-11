"""Direct alias for paypal.exceptions."""

from agentguard.paypal.exceptions import (
    PayPalApiError,
    PayPalAuthError,
    PayPalDeclinedError,
    PayPalDuplicateCaptureError,
    PayPalError,
    PayPalInvalidResourceError,
    PayPalTimeoutError,
)

__all__ = [
    "PayPalApiError",
    "PayPalAuthError",
    "PayPalDeclinedError",
    "PayPalDuplicateCaptureError",
    "PayPalError",
    "PayPalInvalidResourceError",
    "PayPalTimeoutError",
]
