"""Health check endpoint for AgentGuard."""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy import text
from sqlalchemy.orm import Session

from agentguard import __version__
from agentguard.core.config import get_settings
from agentguard.core.database import get_db
from agentguard.schemas.health import HealthResponse

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="System Health & Database Status",
)
def check_health(db: Session = Depends(get_db)) -> HealthResponse:
    """Verifies that the application is running and the database connection is live."""
    settings = get_settings()

    db_status = "connected"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "disconnected"

    dialect_name = db.bind.dialect.name if db.bind else "unknown"

    return HealthResponse(
        status="healthy" if db_status == "connected" else "degraded",
        app_name=settings.app_name,
        version=__version__,
        environment=settings.env,
        database=db_status,
        database_dialect=dialect_name,
        timestamp=datetime.now(timezone.utc),
    )
