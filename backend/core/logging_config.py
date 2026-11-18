"""Structured logging configuration for the application."""

import logging
import logging.handlers
import sys
from pathlib import Path

from core.config import settings


def setup_logging() -> None:
    """Configure structured JSON logging for the application."""
    log_dir = Path("storage/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # JSON formatter for structured logging
    class JsonFormatter(logging.Formatter):
        def format(self, record: logging.LogRecord) -> str:
            import json
            from datetime import datetime

            payload = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }

            # Add extra fields if present
            if hasattr(record, "request_id"):
                payload["request_id"] = record.request_id
            if hasattr(record, "user_id"):
                payload["user_id"] = record.user_id
            if record.exc_info:
                payload["exception"] = self.formatException(record.exc_info)

            return json.dumps(payload)

    # Console handler with JSON formatting
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(JsonFormatter())
    console_handler.setLevel(logging.INFO)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "app.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(JsonFormatter())
    file_handler.setLevel(logging.INFO)

    # Error file handler
    error_handler = logging.handlers.RotatingFileHandler(
        log_dir / "error.log",
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setFormatter(JsonFormatter())
    error_handler.setLevel(logging.ERROR)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers = [console_handler, file_handler, error_handler]

    # Configure specific loggers
    logging.getLogger("uvicorn").setLevel(logging.INFO)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.SQL_ECHO else logging.WARNING
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name."""
    return logging.getLogger(name)