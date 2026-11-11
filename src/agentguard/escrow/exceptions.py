"""Custom domain exceptions for escrow state machine and approval workflows."""

from typing import Any, Dict, Optional


class EscrowError(Exception):
    """Base exception for all escrow and state transition errors."""

    def __init__(
        self,
        message: str,
        status_code: int = 400,
        error_name: str = "ESCROW_ERROR",
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_name = error_name
        self.details = details or {}


class InvalidStateTransitionError(EscrowError):
    """Raised when an illegal transaction state transition is attempted."""

    def __init__(
        self,
        message: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        error_details = details or {}
        if from_state:
            error_details["from_state"] = from_state
        if to_state:
            error_details["to_state"] = to_state
        super().__init__(
            message=message,
            status_code=422,
            error_name="INVALID_STATE_TRANSITION",
            details=error_details,
        )


class DuplicateApprovalError(EscrowError):
    """Raised when an approval is requested or resolved more than once."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            status_code=409,
            error_name="DUPLICATE_APPROVAL",
            details=details,
        )


class AlreadyCapturedError(DuplicateApprovalError):
    """Raised when attempting to capture or re-capture an already captured transaction."""

    def __init__(
        self,
        message: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        error_details = details or {}
        if from_state:
            error_details["from_state"] = from_state
        if to_state:
            error_details["to_state"] = to_state
        super().__init__(message=message, details=error_details)
        self.error_name = "ALREADY_CAPTURED"


class AlreadyVoidedError(InvalidStateTransitionError):
    """Raised when attempting to operate on a voided transaction."""

    def __init__(
        self,
        message: str,
        from_state: Optional[str] = None,
        to_state: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        super().__init__(
            message=message,
            from_state=from_state,
            to_state=to_state,
            details=details,
        )
        self.error_name = "ALREADY_VOIDED"


class UnauthorizedReviewerError(EscrowError):
    """Raised when an unauthenticated reviewer or AI buyer agent attempts human approval."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            status_code=403,
            error_name="UNAUTHORIZED_REVIEWER",
            details=details,
        )


class EscrowExecutionError(EscrowError):
    """Raised when a downstream PayPal payment operation fails during escrow transition."""

    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            message=message,
            status_code=502,
            error_name="ESCROW_EXECUTION_FAILURE",
            details=details,
        )
