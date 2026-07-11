"""
UnifyOps — Structured Logging (FR-0.5.1)

Every log entry includes: severity, request_id, service_name, latency_ms.
Uses structlog for JSON-structured output compatible with Cloud Logging.
"""

import logging
import structlog


def setup_logging() -> None:
    """Configure structlog for structured JSON logging."""

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Set root logger level
    logging.basicConfig(
        format="%(message)s",
        level=logging.INFO,
    )


def get_logger(service_name: str) -> structlog.stdlib.BoundLogger:
    """Get a structured logger bound to a specific service name."""
    return structlog.get_logger(service_name=service_name)
