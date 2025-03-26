"""
API v1 router for the API Gateway.

This module defines the main router for API v1 endpoints.
"""

import structlog
from fastapi import APIRouter

from gateway.api.v1.endpoints import auth, documents, batch, hcc, webhooks

logger = structlog.get_logger(__name__)

# Create main router for API v1
api_router = APIRouter()

# Include routers from endpoint modules
api_router.include_router(
    auth.router, prefix="/auth", tags=["authentication"]
)
api_router.include_router(
    documents.router, prefix="/documents", tags=["documents"]
)
api_router.include_router(
    batch.router, prefix="/batch", tags=["batch processing"]
)
api_router.include_router(
    hcc.router, prefix="/hcc", tags=["hcc"]
)
api_router.include_router(
    webhooks.router, prefix="/webhooks", tags=["webhooks"]
)

logger.info("API v1 router configured")