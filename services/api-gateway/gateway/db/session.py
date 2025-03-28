"""
Database session management for the API Gateway.

This module provides utilities for creating and managing database sessions
with SQLAlchemy's async functionality.
"""

from typing import AsyncGenerator

import structlog
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from gateway.core.config import settings

logger = structlog.get_logger(__name__)

# Create async engine for PostgresSQL
engine = create_async_engine(
    str(settings.POSTGRES_URI),
    echo=settings.DEBUG,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# Create session factory
async_session_factory = async_sessionmaker(
    engine, expire_on_commit=False, autoflush=False
)


async def create_database_pool():
    """Initialize database connection pool."""
    logger.info("Creating database connection pool", db_uri=settings.POSTGRES_URI)


async def close_database_pool():
    """Close database connection pool."""
    logger.info("Closing database connection pool")
    await engine.dispose()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Get a database session.

    This dependency yields a SQLAlchemy async session that will automatically
    be closed when the request is finished.

    Yields:
        An async SQLAlchemy session
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
