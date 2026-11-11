"""Configuration management for AgentGuard using Pydantic Settings."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application and environment configuration."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Core Application
    env: Literal["development", "testing", "production"] = Field(
        default="development", alias="AGENTGUARD_ENV"
    )
    debug: bool = Field(default=False, alias="AGENTGUARD_DEBUG")
    app_name: str = Field(
        default="AgentGuard - Policy Firewall & Escrow",
        alias="AGENTGUARD_APP_NAME",
    )
    api_prefix: str = Field(default="/api/v1", alias="AGENTGUARD_API_PREFIX")
    host: str = Field(default="127.0.0.1", alias="AGENTGUARD_HOST")
    port: int = Field(default=8000, alias="AGENTGUARD_PORT")
    log_level: str = Field(default="INFO", alias="AGENTGUARD_LOG_LEVEL")

    # Database
    database_url: str = Field(
        default="sqlite:///./data/agentguard.db",
        alias="AGENTGUARD_DATABASE_URL",
    )
    database_echo: bool = Field(default=False, alias="AGENTGUARD_DATABASE_ECHO")

    # PayPal Isolated Adapter Configuration
    paypal_mode: Literal["sandbox", "live", "mock"] = Field(
        default="mock", alias="PAYPAL_MODE"
    )
    paypal_client_id: str = Field(default="", alias="PAYPAL_CLIENT_ID")
    paypal_client_secret: SecretStr = Field(
        default=SecretStr(""), alias="PAYPAL_CLIENT_SECRET"  # [REDACTED]
    )
    paypal_webhook_id: str = Field(default="", alias="PAYPAL_WEBHOOK_ID")

    # Administrative Controls & MCP HITL Authentication
    admin_api_key: SecretStr = Field(
        default=SecretStr("admin-secret-key-2026"),  # [REDACTED]
        alias="AGENTGUARD_ADMIN_KEY",
    )

    @property
    def is_sqlite(self) -> bool:
        """Return True if using SQLite database engine."""
        return self.database_url.startswith("sqlite")

    @property
    def sqlite_file_path(self) -> Path | None:
        """Return Path to local SQLite database file, if applicable."""
        if not self.is_sqlite:
            return None
        raw_path = self.database_url.replace("sqlite:///", "").replace("sqlite://", "")
        if raw_path == ":memory:":
            return None
        return Path(raw_path)


@lru_cache
def get_settings() -> Settings:
    """Provide cached application settings instance."""
    return Settings()
