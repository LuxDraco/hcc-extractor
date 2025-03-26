"""
Logging configuration for the API Gateway.

This module provides utilities for configuring logging with structlog.
"""

import logging
import sys
import time
from typing import Any, Dict

import structlog
from structlog.stdlib import LoggerFactory
from structlog.types import Processor

from gateway.core.config import LogLevel, Environment, settings


def configure_logging(log_level: LogLevel = LogLevel.DEBUG) -> None:
    """
    Configure structured logging for the application.

    This function sets up structlog with appropriate processors
    for the current environment.

    Args:
        log_level: Logging level to use
    """
    # Set up standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level.upper(),
    )

    # Configure timestamp processor with correct format string
    def timestamper(logger: Any, name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add ISO-8601 formatted timestamp to the event dict."""
        event_dict["timestamp"] = time.strftime(
            "%Y-%m-%dT%H:%M:%S", time.gmtime()
        )
        return event_dict

    # Configure service name processor
    def add_service_info(logger: Any, name: str, event_dict: Dict[str, Any]) -> Dict[str, Any]:
        """Add service information to the event dict."""
        event_dict["service"] = settings.PROJECT_NAME
        event_dict["version"] = settings.VERSION
        event_dict["environment"] = settings.ENVIRONMENT
        return event_dict

    # Select processors based on environment
    processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        timestamper,
        add_service_info,
        structlog.processors.format_exc_info,
    ]

    if settings.ENVIRONMENT == Environment.DEVELOPMENT:
        # Pretty output for development
        processors.extend([
            structlog.dev.ConsoleRenderer(),
        ])
    else:
        # JSON output for production
        processors.extend([
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ])

    # Configure structlog
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
