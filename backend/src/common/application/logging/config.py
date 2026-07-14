"""
Structlog configuration for production-ready structured logging.

Features:
- JSON output for production
- Colored console output for development
- Request correlation IDs
- Performance metrics (duration tracking)
- Consistent event naming: domain.action.state
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import EventDict, WrappedLogger

from src.common.domain.logging import get_logger
from src.common.settings import settings

__all__ = ["configure_logging", "get_logger"]


def add_app_context(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add application context to all log events."""
    event_dict["environment"] = settings.ENVIRONMENT.value
    event_dict["stage"] = settings.STAGE.value
    event_dict["process"] = settings.PROCESS_LABEL.value
    event_dict["version"] = settings.VERSION
    return event_dict


def add_log_level_name(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Add log level name for easier filtering."""
    event_dict["level"] = method_name.upper()
    return event_dict


def drop_debug_in_production(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """Drop debug logs in production for performance."""
    if settings.ENVIRONMENT.is_production and method_name == "debug":
        raise structlog.DropEvent
    return event_dict


def extract_from_record(
    logger: WrappedLogger,
    method_name: str,
    event_dict: EventDict,
) -> EventDict:
    """
    Extract extra information from standard library logging.
    Allows compatibility with libraries using stdlib logging.
    """
    record = event_dict.get("_record")
    if record:
        event_dict["logger_name"] = record.name
        event_dict["line"] = record.lineno
        event_dict["function"] = record.funcName

    return event_dict


def configure_logging() -> None:
    """
    Configure structlog with appropriate processors for the environment.

    Development: Colored console output with human-readable format
    Production: JSON output for log aggregation systems
    """
    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    )

    # Silence noisy loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Determine output format based on environment
    if settings.ENVIRONMENT.is_production:
        # Production: JSON for machine parsing
        renderer = structlog.processors.JSONRenderer()
    else:
        # Development: Colored console for human readability
        renderer = structlog.dev.ConsoleRenderer(
            colors=True,
            exception_formatter=structlog.dev.plain_traceback,
        )

    # Shared processors for all environments
    shared_processors: list[Any] = [
        # Add context
        structlog.contextvars.merge_contextvars,
        add_app_context,
        add_log_level_name,
        drop_debug_in_production,
        # Add timestamps
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        # Stack info for errors
        structlog.processors.StackInfoRenderer(),
        # Exception formatting
        structlog.processors.format_exc_info,
        # Unicode handling
        structlog.processors.UnicodeDecoder(),
    ]

    # Configure structlog
    structlog.configure(
        processors=[
            # Filter by log level
            structlog.stdlib.filter_by_level,
            *shared_processors,
            # Standard library compatibility
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to use structlog
    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            extract_from_record,
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.DEBUG if settings.DEBUG else logging.INFO)
