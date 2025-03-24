"""
Rate limiting middleware for the API Gateway.

This module provides middleware for enforcing rate limits on API requests.
"""

import time
from collections import defaultdict
from typing import Callable, Dict, Tuple

import structlog
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.status import HTTP_429_TOO_MANY_REQUESTS

from app.core.config import settings

logger = structlog.get_logger(__name__)


class RateLimitingMiddleware(BaseHTTPMiddleware):
    """
    Middleware for enforcing rate limits on API requests.

    This middleware uses a simple in-memory rate limiting strategy based on IP addresses.
    In a production environment, you might want to use a distributed rate limiter
    (e.g., with Redis) to handle multiple instances.
    """

    def __init__(self, app: FastAPI):
        """
        Initialize the rate limiting middleware.

        Args:
            app: FastAPI application
        """
        super().__init__(app)
        # Rate limit: {ip_address: [(timestamp, request_count), ...]}
        self.rate_limits: Dict[str, list] = defaultdict(list)
        self.rate_limit_per_minute = settings.RATE_LIMIT_PER_MINUTE

    def _is_rate_limited(self, ip_address: str) -> Tuple[bool, Dict[str, str]]:
        """
        Check if a request is rate limited.

        Args:
            ip_address: IP address of the client

        Returns:
            Tuple of (is_rate_limited, headers)
        """
        # Get current time
        now = time.time()
        minute_ago = now - 60

        # Clean up old entries
        self.rate_limits[ip_address] = [
            (timestamp, count) for timestamp, count in self.rate_limits[ip_address]
            if timestamp > minute_ago
        ]

        # Calculate the current count within the last minute
        current_count = sum(count for timestamp, count in self.rate_limits[ip_address])

        # Check if rate limit exceeded
        is_limited = current_count >= self.rate_limit_per_minute

        # If not limited, add a new entry
        if not is_limited:
            self.rate_limits[ip_address].append((now, 1))

        # Calculate remaining requests
        remaining = max(0, self.rate_limit_per_minute - current_count)

        # Create headers
        headers = {
            "X-RateLimit-Limit": str(self.rate_limit_per_minute),
            "X-RateLimit-Remaining": str(remaining),
            "X-RateLimit-Reset": str(int(minute_ago + 60)),
        }

        return is_limited, headers

    async def dispatch(
            self, request: Request, call_next: Callable[[Request], Response]
    ) -> Response:
        """
        Process a request and enforce rate limits.

        Args:
            request: The incoming request
            call_next: The next middleware or route handler

        Returns:
            The response from the next middleware or route handler,
            or a 429 response if rate limited
        """
        # Skip rate limiting for some paths
        if (
                request.url.path.startswith("/api/docs")
                or request.url.path.startswith("/api/redoc")
                or request.url.path.startswith("/api/openapi.json")
                or request.url.path == "/api/health"
                or request.url.path == "/"
                or request.url.path == "/metrics"
        ):
            return await call_next(request)

        # Get client IP address
        ip_address = request.client.host if request.client else "unknown"

        # Check if rate limited
        is_limited, headers = self._is_rate_limited(ip_address)

        if is_limited:
            # Log rate limiting
            logger.warning(
                "Rate limit exceeded",
                ip_address=ip_address,
                path=request.url.path,
                method=request.method,
            )

            # Create response
            content = {
                "detail": "Too many requests",
                "status_code": HTTP_429_TOO_MANY_REQUESTS,
            }

            response = Response(
                content=str(content),
                status_code=HTTP_429_TOO_MANY_REQUESTS,
                media_type="application/json",
            )

            # Add headers
            for name, value in headers.items():
                response.headers[name] = value

            return response

        # Process the request
        response = await call_next(request)

        # Add rate limit headers
        for name, value in headers.items():
            response.headers[name] = value

        return response