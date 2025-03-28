"""
Database session management for the API Gateway.

This module provides utilities for creating and managing database sessions
with SQLAlchemy's async functionality.
"""

from typing import AsyncGenerator

import structlog
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker

from app.core.config import settings

logger = structlog.get_logger(__name__)

load_dotenv()

# Create async engine for PostgresSQL
engine = create_async_engine(
    f"postgresql+asyncpg://{settings.POSTGRES_USER}:postgres@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}",
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
    postgres_uri = f"postgresql+asyncpg://{settings.POSTGRES_USER}:postgres@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}"
    logger.info("Creating database connection pool", db_uri=postgres_uri)


async def close_database_pool():
    """Close database connection pool."""
    logger.info("Closing database connection pool")
    await engine.dispose()


def get_db_session():
    """Get a database session."""
    engine_tmp = create_engine(
        f"postgresql://{settings.POSTGRES_USER}:postgres@{settings.POSTGRES_HOST}:{settings.POSTGRES_PORT}/{settings.POSTGRES_DB}")
    session_local = sessionmaker(autocommit=False, autoflush=False, bind=engine_tmp)
    db = session_local()
    try:
        yield db
    finally:
        db.close()


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
