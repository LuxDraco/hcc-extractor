"""
Logging middleware for the API Gateway.

This module provides middleware for logging requests and responses.
"""

import time
import uuid
from typing import Callable, Dict, Any

import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp, Scope, Receive, Send

logger = structlog.get_logger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for logging requests and responses.

    This middleware logs details about each request and response,
    including timing information, status codes, and more.
    """

    async def dispatch(
            self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Process a request and log information about it.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response from the next middleware or route handler
        """
        # Generate a unique request ID
        request_id = str(uuid.uuid4())

        # Structlog context binding
        logger_ctx = structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
            query_params=dict(request.query_params),
            client_host=request.client.host if request.client else None,
        )

        # Start timer
        start_time = time.time()

        # Log the request
        logger.info(
            "Request started",
            user_agent=request.headers.get("user-agent"),
            content_length=request.headers.get("content-length"),
        )

        try:
            # Process the request
            response = await call_next(request)

            # Calculate processing time
            process_time = time.time() - start_time

            # Add the request ID to the response headers
            response.headers["X-Request-ID"] = request_id

            # Log the response
            logger.info(
                "Request completed",
                status_code=response.status_code,
                process_time=f"{process_time:.4f}s",
                content_length=response.headers.get("content-length"),
            )

            return response

        except Exception as e:
            # Calculate processing time
            process_time = time.time() - start_time

            # Log the error
            logger.exception(
                "Request failed",
                exc_info=e,
                process_time=f"{process_time:.4f}s",
            )

            # Re-raise the exception
            raise

        finally:
            # Clear the context variables
            structlog.contextvars.clear_contextvars()