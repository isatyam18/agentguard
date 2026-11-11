"""Domain errors and API exception definitions for AgentGuard."""

from typing import Any
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AgentGuardError(Exception):
    """Base exception for all AgentGuard domain errors."""

    def __init__(
        self,
        message: str,
        code: str = "INTERNAL_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class EntityNotFoundError(AgentGuardError):
    """Raised when an entity is not found in storage."""

    def __init__(self, entity_name: str, entity_id: str) -> None:
        super().__init__(
            message=f"{entity_name} with ID '{entity_id}' not found.",
            code="NOT_FOUND",
            status_code=status.HTTP_404_NOT_FOUND,
            details={"entity": entity_name, "id": entity_id},
        )


class ConflictError(AgentGuardError):
    """Raised when an entity conflict or unique constraint violation occurs."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="CONFLICT",
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class PolicyViolationError(AgentGuardError):
    """Raised when an operation violates active firewall policies."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="POLICY_VIOLATION",
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class DomainValidationError(AgentGuardError):
    """Raised when domain logic validation fails."""

    def __init__(self, message: str, details: dict[str, Any] | None = None) -> None:
        super().__init__(
            message=message,
            code="VALIDATION_ERROR",
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            details=details,
        )


def register_exception_handlers(app: FastAPI) -> None:
    """Register uniform error response handlers on the FastAPI application."""

    @app.exception_handler(AgentGuardError)
    async def agentguard_exception_handler(
        request: Request, exc: AgentGuardError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                    "path": request.url.path,
                }
            },
        )

    from agentguard.escrow.exceptions import EscrowError

    @app.exception_handler(EscrowError)
    async def escrow_exception_handler(
        request: Request, exc: EscrowError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": exc.error_name,
                    "message": exc.message,
                    "details": exc.details,
                    "path": request.url.path,
                }
            },
        )

    @app.exception_handler(RequestValidationError)
    async def request_validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        formatted_errors = []
        for err in exc.errors():
            formatted_errors.append(
                {
                    "loc": [str(loc) for loc in err.get("loc", [])],
                    "msg": err.get("msg"),
                    "type": err.get("type"),
                }
            )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "error": {
                    "code": "REQUEST_VALIDATION_ERROR",
                    "message": "The incoming payload failed schema validation.",
                    "details": {"validation_errors": formatted_errors},
                    "path": request.url.path,
                }
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An unexpected server error occurred.",
                    "details": {"error_type": type(exc).__name__},
                    "path": request.url.path,
                }
            },
        )
