"""Structured logging configuration for AgentGuard."""

import json
import logging
import sys
from datetime import datetime, timezone
from typing import Any


class JSONFormatter(logging.Formatter):
    """Formats log records as structured single-line JSON objects."""

    def format(self, record: logging.LogRecord) -> str:
        log_payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include structured context if attached to record
        if hasattr(record, "event"):
            log_payload["event"] = getattr(record, "event")
        if hasattr(record, "details"):
            log_payload["details"] = getattr(record, "details")
        if hasattr(record, "request_id"):
            log_payload["request_id"] = getattr(record, "request_id")
        if hasattr(record, "transaction_id"):
            log_payload["transaction_id"] = getattr(record, "transaction_id")

        if record.exc_info:
            log_payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_payload, default=str)


def setup_logging(level: str = "INFO", json_format: bool = False) -> logging.Logger:
    """Configure root logger with structured formatting."""
    root_logger = logging.getLogger("agentguard")
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(numeric_level)

    # Avoid adding duplicate handlers on re-runs
    if not root_logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(numeric_level)

        if json_format:
            handler.setFormatter(JSONFormatter())
        else:
            standard_formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(standard_formatter)

        root_logger.addHandler(handler)

    return root_logger


logger = setup_logging()
