"""Custom exceptions for PayPal Orders v2 and Payments v2 integration."""

from typing import Any, Dict, List, Optional


class PayPalError(Exception):
    """Base exception for all PayPal integration errors."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_name: Optional[str] = None,
        details: Optional[List[Dict[str, Any]]] = None,
        raw_response: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_name = error_name
        self.details = details or []
        self.raw_response = raw_response or {}


class PayPalAuthError(PayPalError):
    """Raised when OAuth2 authentication fails (invalid client credentials)."""
    pass


class PayPalApiError(PayPalError):
    """Raised when PayPal REST API returns 4xx/5xx responses."""
    pass


class PayPalTimeoutError(PayPalError):
    """Raised on ambiguous network timeout during a money-moving request."""

    def __init__(self, message: str, operation: str, resource_id: str) -> None:
        super().__init__(message)
        self.operation = operation
        self.resource_id = resource_id


class PayPalDuplicateCaptureError(PayPalError):
    """Raised when an authorization has already been captured."""
    pass


class PayPalDeclinedError(PayPalError):
    """Raised when a payment authorization or capture is declined by the rail."""
    pass


class PayPalInvalidResourceError(PayPalError):
    """Raised when an order or authorization ID does not exist."""
    pass
