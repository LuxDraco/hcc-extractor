"""
Main application module for the HCC Extractor API Gateway.

This module serves as the entry point for the API Gateway service, which provides
a unified interface for accessing the various components of the HCC Extractor system.
"""

import logging
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from prometheus_client import Counter, Histogram

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.dependencies import get_telemetry, initialize_telemetry
from app.db.session import create_database_pool, close_database_pool
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limiting import RateLimitingMiddleware
from app.utils.logging import configure_logging
from app.utils.metrics import setup_metrics_endpoint

# Configure logging
configure_logging(log_level=settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)

# Define metrics
REQUEST_COUNT = Counter(
    "api_requests_total", "Total count of API requests", ["method", "endpoint", "status"]
)
REQUEST_LATENCY = Histogram(
    "api_request_latency_seconds",
    "Request latency in seconds",
    ["method", "endpoint"],
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Context manager for FastAPI lifespan events.

    This function handles startup and shutdown events for the FastAPI application.
    """
    # Startup
    logger.info("Starting up API Gateway service")

    # Initialize telemetry
    if settings.TELEMETRY_ENABLED:
        initialize_telemetry()

    # Initialize database connection pool
    await create_database_pool()

    logger.info(
        "API Gateway service started",
        version=settings.VERSION,
        environment=settings.ENVIRONMENT,
    )

    yield

    # Shutdown
    logger.info("Shutting down API Gateway service")

    # Close database connection pool
    await close_database_pool()

    logger.info("API Gateway service shut down")


# Create FastAPI application
app = FastAPI(
    title=settings.PROJECT_NAME,
    description=settings.PROJECT_DESCRIPTION,
    version=settings.VERSION,
    docs_url="/api/docs" if settings.SHOW_DOCS else None,
    redoc_url="/api/redoc" if settings.SHOW_DOCS else None,
    openapi_url="/api/openapi.json" if settings.SHOW_DOCS else None,
    lifespan=lifespan,
)

# Setup metrics endpoint
setup_metrics_endpoint(app)

# Add middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RateLimitingMiddleware)
app.add_middleware(LoggingMiddleware)

# Register routes
app.include_router(api_router, prefix=settings.API_PREFIX)

# Setup OpenTelemetry instrumentation
if settings.TELEMETRY_ENABLED:
    FastAPIInstrumentor.instrument_app(app)


@app.middleware("http")
async def add_metrics(request: Request, call_next):
    """
    Middleware for collecting request metrics.

    Args:
        request: The incoming request
        call_next: The next middleware or route handler

    Returns:
        The response from the next middleware or route handler
    """
    start_time = time.time()

    response = await call_next(request)

    # Record metrics
    duration = time.time() - start_time
    REQUEST_LATENCY.labels(
        method=request.method, endpoint=request.url.path
    ).observe(duration)
    REQUEST_COUNT.labels(
        method=request.method, endpoint=request.url.path, status=response.status_code
    ).inc()

    return response


@app.get("/api/health")
async def health_check():
    """
    Health check endpoint.

    Returns:
        A simple health status
    """
    return {"status": "healthy", "version": settings.VERSION}


@app.get("/")
async def root():
    """
    Root endpoint that redirects to the API documentation.

    Returns:
        A redirect to the API documentation
    """
    return {
        "message": "HCC Extractor API Gateway",
        "version": settings.VERSION,
        "docs": "/api/docs",
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
    )