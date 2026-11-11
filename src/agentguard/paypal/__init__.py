"""PayPal Orders v2 & Payments v2 integration package."""

from agentguard.paypal.client import PayPalClient, SANDBOX_BASE_URL
from agentguard.paypal.exceptions import (
    PayPalApiError,
    PayPalAuthError,
    PayPalDeclinedError,
    PayPalDuplicateCaptureError,
    PayPalError,
    PayPalInvalidResourceError,
    PayPalTimeoutError,
)
from agentguard.paypal.orders import PayPalOrders
from agentguard.paypal.payments import PayPalPayments

__all__ = [
    "PayPalClient",
    "SANDBOX_BASE_URL",
    "PayPalOrders",
    "PayPalPayments",
    "PayPalError",
    "PayPalAuthError",
    "PayPalApiError",
    "PayPalTimeoutError",
    "PayPalDuplicateCaptureError",
    "PayPalDeclinedError",
    "PayPalInvalidResourceError",
]
