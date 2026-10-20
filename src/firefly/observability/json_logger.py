"""Structured JSON logging with levels, rotation, and secret redaction (Feature 106)."""

from __future__ import annotations

import datetime
import json
import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional

from firefly.core.config import settings
from firefly.memory.redactor import SecretRedactor


class JSONFormatter(logging.Formatter):
    """Formats log records as structured, single-line JSON with redacted secrets."""

    def format(self, record: logging.LogRecord) -> str:
        # Base structured fields
        timestamp = datetime.datetime.fromtimestamp(
            record.created, tz=datetime.timezone.utc
        ).isoformat()

        # Sanitize message of secrets
        raw_msg = record.getMessage()
        clean_msg = SecretRedactor.redact(raw_msg)

        payload: Dict[str, Any] = {
            "timestamp": timestamp,
            "level": record.levelname,
            "logger": record.name,
            "message": clean_msg,
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "pid": os.getpid(),
        }

        # Include custom extra fields if present
        extra_keys = {
            k: v
            for k, v in record.__dict__.items()
            if k
            not in {
                "args",
                "asctime",
                "created",
                "exc_info",
                "exc_text",
                "filename",
                "funcName",
                "levelname",
                "levelno",
                "lineno",
                "module",
                "msecs",
                "message",
                "msg",
                "name",
                "pathname",
                "process",
                "processName",
                "relativeCreated",
                "stack_info",
                "thread",
                "threadName",
            }
        }
        if extra_keys:
            # Redact string values in extra keys
            clean_extras = {}
            for k, v in extra_keys.items():
                if isinstance(v, str):
                    clean_extras[k] = SecretRedactor.redact(v)
                else:
                    clean_extras[k] = v
            payload["extra"] = clean_extras

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


class StructuredLogger:
    """Convenience wrapper around standard logger providing structured context."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def debug(self, msg: str, **kwargs: Any) -> None:
        self._logger.debug(msg, extra=kwargs)

    def info(self, msg: str, **kwargs: Any) -> None:
        self._logger.info(msg, extra=kwargs)

    def warning(self, msg: str, **kwargs: Any) -> None:
        self._logger.warning(msg, extra=kwargs)

    def error(self, msg: str, **kwargs: Any) -> None:
        self._logger.error(msg, extra=kwargs)

    def critical(self, msg: str, **kwargs: Any) -> None:
        self._logger.critical(msg, extra=kwargs)


def configure_json_logging(
    log_file: Optional[Path] = None,
    level: int = logging.INFO,
    max_bytes: int = 5 * 1024 * 1024,  # 5 MB
    backup_count: int = 5,
) -> RotatingFileHandler:
    """Configures structured JSON rotating file logger."""
    target_path = log_file or (settings.paths.data_dir / "logs" / "firefly.json.log")
    target_path.parent.mkdir(parents=True, exist_ok=True)

    handler = RotatingFileHandler(
        str(target_path),
        maxBytes=max_bytes,
        backupCount=backup_count,
        encoding="utf-8",
    )
    handler.setFormatter(JSONFormatter())

    root = logging.getLogger("firefly")
    root.setLevel(level)

    # Avoid duplicate handlers
    if not any(isinstance(h, RotatingFileHandler) for h in root.handlers):
        root.addHandler(handler)

    return handler


def get_json_logger(name: str = "firefly") -> StructuredLogger:
    """Returns a structured logger with JSON formatting capabilities."""
    return StructuredLogger(logging.getLogger(name))


# Global default structured logger
json_logger = get_json_logger()
