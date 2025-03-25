"""
Core dependencies for the API Gateway.

This module extends the existing dependencies.py file with
functions for accessing the HCC codes data.
"""

import os
from pathlib import Path
from typing import AsyncGenerator
from typing import Optional

import aio_pika
import numpy as np
import pandas as pd
import structlog
from aio_pika import Channel
from app.core.config import settings
from app.core.security import get_current_user
from app.db.models.user import User
from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

# RabbitMQ connection
_rabbitmq_connection = None
_rabbitmq_channel = None

# Telemetry
tracer_provider = None
logger = structlog.get_logger(__name__)

# Define HCC codes path
_HCC_CODES_PATH: Optional[Path] = None


def get_hcc_codes_path() -> Path:
    """
    Get the path to the HCC codes CSV file.

    Returns:
        Path to the HCC codes CSV file
    """
    global _HCC_CODES_PATH

    if _HCC_CODES_PATH is None:
        # Look for the CSV file in different locations
        potential_paths = [
            Path("./data/HCC_relevant_codes.csv"),
            Path("../data/HCC_relevant_codes.csv"),
            Path("/app/data/HCC_relevant_codes.csv"),
        ]

        # Check environment variable
        env_path = os.environ.get("HCC_CODES_PATH")
        if env_path:
            potential_paths.insert(0, Path(env_path))

        # Find the first path that exists
        for path in potential_paths:
            if path.exists():
                _HCC_CODES_PATH = path
                logger.info(f"HCC codes file found at {path}")
                break

        # If no file found, use the first path and log warning
        if _HCC_CODES_PATH is None:
            _HCC_CODES_PATH = potential_paths[0]
            logger.warning(
                f"HCC codes file not found, will use {_HCC_CODES_PATH} if created"
            )

        logger.info(f"HCC codes path: {_HCC_CODES_PATH}")

    return _HCC_CODES_PATH


async def require_admin_role(
        current_user: User = Depends(get_current_user),
) -> User:
    """
    Verify that the current user is an admin.

    Args:
        current_user: The current authenticated user

    Returns:
        The current user if they are an admin

    Raises:
        HTTPException: If the user is not an admin
    """
    if not current_user.is_superuser:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not enough permissions",
        )
    return current_user


class OptionalHTTPBearer(HTTPBearer):
    """HTTP Bearer auth scheme that makes authorization optional."""

    async def __call__(
            self, request: Request
    ) -> Optional[HTTPAuthorizationCredentials]:
        try:
            return await super().__call__(request)
        except HTTPException:
            return None


oauth2_scheme_optional = OptionalHTTPBearer(auto_error=False)


async def get_current_user_optional(
        token: Optional[str] = Depends(oauth2_scheme_optional)
) -> Optional[User]:
    """
    Get the current user if authenticated, or None if not.

    This allows endpoints to support both authenticated and anonymous access.

    Args:
        token: JWT token (optional)

    Returns:
        The authenticated user, or None if not authenticated
    """
    if token is None:
        return None

    try:
        return await get_current_user(token)
    except HTTPException:
        return None


async def get_rabbitmq_channel() -> AsyncGenerator[Channel, None]:
    """
    Get a RabbitMQ channel.

    This dependency yields an aio_pika Channel that will automatically
    be closed when the request is finished.

    Yields:
        An aio_pika Channel
    """
    global _rabbitmq_connection, _rabbitmq_channel

    # Create connection if not exists
    if _rabbitmq_connection is None or _rabbitmq_connection.is_closed:
        # Create connection string
        # Create connection string

        vhost = settings.RABBITMQ_VHOST if settings.RABBITMQ_VHOST != "/" else "%2F"
        connection_string = f"amqp://{settings.RABBITMQ_USER}:{settings.RABBITMQ_PASSWORD}@{settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}/{vhost}"

        logger.info(f"Connecting to RabbitMQ using {connection_string}")

        # Connect to RabbitMQ
        _rabbitmq_connection = await aio_pika.connect_robust(connection_string)

        logger.info(f"Connected to RabbitMQ at {settings.RABBITMQ_HOST}:{settings.RABBITMQ_PORT}")

    # Create channel if not exists
    if _rabbitmq_channel is None or _rabbitmq_channel.is_closed:
        _rabbitmq_channel = await _rabbitmq_connection.channel()

    try:
        yield _rabbitmq_channel
    finally:
        # Don't close the channel here, it's reused
        pass


def initialize_telemetry():
    """
    Initialize OpenTelemetry.

    Sets up the tracer provider and exporters for telemetry.
    """
    global tracer_provider

    if tracer_provider is not None:
        # Already initialized
        return

    try:
        # Create a resource with service info
        resource = Resource.create({
            SERVICE_NAME: settings.PROJECT_NAME,
            "service.version": settings.VERSION,
            "deployment.environment": settings.ENVIRONMENT,
        })

        # Create a tracer provider
        tracer_provider = TracerProvider(resource=resource)

        # Add a console exporter for development
        if settings.ENVIRONMENT == "development":
            console_exporter = ConsoleSpanExporter()
            tracer_provider.add_span_processor(BatchSpanProcessor(console_exporter))

        # Set the global tracer provider
        trace.set_tracer_provider(tracer_provider)

        logger.info("Telemetry initialized")

    except Exception as e:
        logger.error(f"Failed to initialize telemetry: {str(e)}")


def get_telemetry():
    """
    Get the tracer provider.

    Returns:
        The tracer provider
    """
    return tracer_provider


def read_hcc_codes():
    csv_path = get_hcc_codes_path()

    # Leer el CSV con tipos explícitos
    df = pd.read_csv(csv_path, dtype={
        'ICD-10-CM Codes': str,
        'Description': str,
        'Tags': str
    })

    # Renombrar las columnas
    df = df.rename(columns={
        'ICD-10-CM Codes': 'code',
        'Description': 'description',
        'Tags': 'category'
    })

    # Reemplazar NaN y None con string vacío
    df = df.replace({np.nan: '', None: ''})

    # Asegurarse de que la columna category tenga un valor por defecto
    df['category'] = df['category'].apply(lambda x: 'UNCATEGORIZED' if pd.isna(x) or x == '' else str(x))

    # Convertir a diccionarios y asegurarse de que todo sea string
    records = []
    for record in df.to_dict('records'):
        records.append({
            'code': str(record['code']).strip(),
            'description': str(record['description']).strip(),
            'category': str(record['category']).strip() or 'UNCATEGORIZED'
        })

    return records
