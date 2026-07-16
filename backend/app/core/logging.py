"""Structured logging configuration with defensive secret redaction."""
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import re
import sys
from datetime import datetime, timezone

SENSITIVE_PATTERNS = [
    re.compile(r'(?i)(authorization|password|secret|token|cookie)([\s\"\':=]+)([^\s,;\"}]+)'),
    re.compile(r'(?i)bearer\s+[a-z0-9._~-]+'),
]


def redact_text(value: str) -> str:
    """Remove common credential forms from free-text log messages."""
    redacted = value
    for pattern in SENSITIVE_PATTERNS:
        if pattern.pattern.lower().startswith('(?i)bearer'):
            redacted = pattern.sub('Bearer [REDACTED]', redacted)
        else:
            redacted = pattern.sub(lambda match: f'{match.group(1)}{match.group(2)}[REDACTED]', redacted)
    return redacted


class JsonFormatter(logging.Formatter):
    """Format log records as one privacy-aware JSON object per line."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': redact_text(record.getMessage()),
        }
        for field in (
            'request_id', 'method', 'path', 'status_code', 'duration_ms',
            'operation', 'outcome', 'dependency', 'scope',
        ):
            if hasattr(record, field):
                payload[field] = getattr(record, field)
        if record.exc_info:
            payload['exception'] = redact_text(self.formatException(record.exc_info))
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(
    level: str = 'INFO',
    log_file: str | None = None,
    max_bytes: int = 10_485_760,
    backup_count: int = 5,
) -> None:
    """Configure JSON stdout and an optional rotating file for Docker volumes."""
    formatter = JsonFormatter()
    handlers: list[logging.Handler] = []

    console = logging.StreamHandler(sys.stdout)
    console.setFormatter(formatter)
    handlers.append(console)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            path,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding='utf-8',
        )
        file_handler.setFormatter(formatter)
        handlers.append(file_handler)

    root = logging.getLogger()
    root.handlers.clear()
    for handler in handlers:
        root.addHandler(handler)
    root.setLevel(level.upper())
