"""
Metrics utilities for the API Gateway with registry uniqueness.

This module provides functions for setting up metrics collection and reporting
with safeguards to prevent duplicate metric registration.
"""

import structlog
from fastapi import FastAPI
from prometheus_client import (
    Counter, Gauge, Histogram, CONTENT_TYPE_LATEST,
    generate_latest, CollectorRegistry
)
from starlette.responses import Response

logger = structlog.get_logger(__name__)

# Create a custom registry to avoid conflicts with the global registry
# This is particularly important when using hot-reloading in development
custom_registry = CollectorRegistry()

# System metrics
SYSTEM_INFO = Gauge(
    "system_info",
    "Information about the API Gateway system",
    ["version", "environment"],
    registry=custom_registry
)

# Database metrics
DB_POOL_SIZE = Gauge(
    "db_pool_size",
    "Database connection pool size",
    registry=custom_registry
)
DB_POOL_AVAILABLE = Gauge(
    "db_pool_available",
    "Database connection pool available connections",
    registry=custom_registry
)
DB_QUERY_TIME = Histogram(
    "db_query_time_seconds",
    "Database query time in seconds",
    ["query_type", "table"],
    registry=custom_registry
)

# RabbitMQ metrics
RABBITMQ_MESSAGES_PUBLISHED = Counter(
    "rabbitmq_messages_published_total",
    "Total number of messages published to RabbitMQ",
    ["queue", "message_type"],
    registry=custom_registry
)
RABBITMQ_MESSAGES_FAILED = Counter(
    "rabbitmq_messages_failed_total",
    "Total number of messages that failed to publish to RabbitMQ",
    ["queue", "message_type"],
    registry=custom_registry
)

# Document processing metrics
DOCUMENTS_PROCESSED = Counter(
    "documents_processed_total",
    "Total number of documents processed",
    ["status"],
    registry=custom_registry
)
PROCESSING_TIME = Histogram(
    "document_processing_time_seconds",
    "Document processing time in seconds",
    ["stage"],
    registry=custom_registry
)

# Storage metrics
STORAGE_OPERATIONS = Counter(
    "storage_operations_total",
    "Total number of storage operations",
    ["operation", "storage_type"],
    registry=custom_registry
)
STORAGE_OPERATION_TIME = Histogram(
    "storage_operation_time_seconds",
    "Storage operation time in seconds",
    ["operation", "storage_type"],
    registry=custom_registry
)
STORAGE_SIZE = Gauge(
    "storage_size_bytes",
    "Total size of stored documents in bytes",
    ["storage_type"],
    registry=custom_registry
)

# API metrics
API_REQUESTS = Counter(
    "api_requests_total",
    "Total number of API requests",
    ["method", "endpoint", "status"],
    registry=custom_registry
)
API_REQUEST_TIME = Histogram(
    "api_request_time_seconds",
    "API request time in seconds",
    ["method", "endpoint"],
    registry=custom_registry
)

# HCC metrics
HCC_OPERATIONS = Counter(
    "hcc_operations_total",
    "Total number of HCC operations",
    ["operation"],
    registry=custom_registry
)
HCC_OPERATION_TIME = Histogram(
    "hcc_operation_time_seconds",
    "HCC operation time in seconds",
    ["operation"],
    registry=custom_registry
)


def setup_metrics_endpoint(app: FastAPI) -> None:
    """
    Set up the metrics endpoint for Prometheus scraping.

    Args:
        app: FastAPI application
    """

    @app.get("/metrics", include_in_schema=False)
    async def metrics():
        """
        Expose Prometheus metrics.

        Returns:
            Prometheus metrics in the correct format
        """
        return Response(
            content=generate_latest(custom_registry),
            media_type=CONTENT_TYPE_LATEST,
        )

    # Set the system info metric
    from gateway.core.config import settings

    SYSTEM_INFO.labels(
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    ).set(1)

    logger.info("Metrics endpoint configured at /metrics")


def record_db_metrics(current_pool_size: int, available_connections: int) -> None:
    """
    Record database connection pool metrics.

    Args:
        current_pool_size: Current pool size
        available_connections: Available connections
    """
    DB_POOL_SIZE.set(current_pool_size)
    DB_POOL_AVAILABLE.set(available_connections)


def record_document_processed(status: str) -> None:
    """
    Record a document processing event.

    Args:
        status: Processing status (success, error, etc.)
    """
    DOCUMENTS_PROCESSED.labels(status=status).inc()
