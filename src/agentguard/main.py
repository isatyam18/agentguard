"""FastAPI application entry point for AgentGuard."""

import time
import uuid
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from agentguard import __version__
from agentguard.api.router import api_router
from agentguard.api.routes.health import router as health_router
from agentguard.core.config import get_settings
from agentguard.core.database import init_db
from agentguard.core.errors import register_exception_handlers
from agentguard.core.logging import logger, setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan context: initialize database on startup."""
    settings = get_settings()
    setup_logging(level=settings.log_level)
    logger.info(
        "AgentGuard backend starting",
        extra={"event": "APP_START", "env": settings.env, "version": __version__},
    )

    # Initialize SQLite database and tables
    init_db()

    yield

    logger.info(
        "AgentGuard backend shutting down",
        extra={"event": "APP_SHUTDOWN"},
    )


def create_app() -> FastAPI:
    """Build and configure the FastAPI application instance."""
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=__version__,
        description="Policy Firewall & Escrow for Autonomous AI Payments using PayPal",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS configuration
    allowed_origins = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]
    # Allow additional custom origins via AGENTGUARD_ALLOWED_ORIGINS environment variable
    import os

    extra_origins = os.environ.get("AGENTGUARD_ALLOWED_ORIGINS", "")
    if extra_origins:
        for origin in extra_origins.split(","):
            cleaned = origin.strip()
            if cleaned and cleaned not in allowed_origins:
                allowed_origins.append(cleaned)

    # Allow localhost and *.onrender.com domains by default
    allowed_origin_regex = (
        r"^https?:\/\/(localhost|127\.0\.0\.1)(:\d+)?$|^https:\/\/[a-zA-Z0-9_\-]+\.onrender\.com$"
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=allowed_origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Request body size limit middleware (1 MB max payload)
    max_request_body_size = 1_048_576

    @app.middleware("http")
    async def request_size_limit_middleware(
        request: Request, call_next: object
    ) -> Response:
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                if int(content_length) > max_request_body_size:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        status_code=413,
                        content={
                            "error": {
                                "code": "PAYLOAD_TOO_LARGE",
                                "message": f"Request body exceeds maximum permitted size of {max_request_body_size} bytes.",
                                "path": request.url.path,
                            }
                        },
                    )
            except ValueError:
                pass
        return await call_next(request)  # type: ignore[misc]

    # Structured request logging middleware
    @app.middleware("http")
    async def request_logging_middleware(
        request: Request, call_next: object
    ) -> Response:
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        start_time = time.perf_counter()

        # Execute downstream request
        response: Response = await call_next(request)  # type: ignore[misc]

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        response.headers["X-Request-ID"] = request_id

        # Skip spamming logs for standard polling health checks in non-debug mode
        if request.url.path not in ("/health", "/api/v1/health") or settings.debug:
            logger.info(
                f"{request.method} {request.url.path} completed with status {response.status_code}",
                extra={
                    "event": "HTTP_REQUEST",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                },
            )

        return response

    # Uniform error response handlers
    register_exception_handlers(app)

    # Mount health checks at root and versioned prefix
    app.include_router(health_router)
    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()
