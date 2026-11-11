"""Health check schemas for AgentGuard."""

from datetime import datetime
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """System health check response."""

    status: str = Field(default="healthy", description="Application overall health status")
    app_name: str = Field(description="Application title")
    version: str = Field(description="Application release version")
    environment: str = Field(description="Active execution environment")
    database: str = Field(description="Database connectivity status ('connected' or 'disconnected')")
    database_dialect: str = Field(description="Underlying database driver/dialect")
    timestamp: datetime = Field(description="Current UTC server timestamp")
