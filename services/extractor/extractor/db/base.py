"""
Base model for SQLAlchemy models.

This module provides a base class for SQLAlchemy models with common
functionality and utility methods.
"""

import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar

from sqlalchemy import DateTime, func, select
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

# Type variable for the model class
T = TypeVar("T", bound="Base")


class Base(DeclarativeBase):
    """
    Base class for all SQLAlchemy models.

    This class provides common columns and utility methods for all models.
    """

    # Make tablename automatically generated from class name
    @declared_attr.directive
    def __tablename__(cls) -> str:
        return cls.__name__.lower() + "s"

    # Common columns for all tables
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    @classmethod
    async def get_by_id(
            cls: Type[T], db: AsyncSession, id: uuid.UUID
    ) -> Optional[T]:
        """
        Get a record by ID.

        Args:
            db: Database session
            id: Record ID

        Returns:
            The record if found, None otherwise
        """
        stmt = select(cls).where(cls.id == id)
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def get_all(
            cls: Type[T], db: AsyncSession, *, skip: int = 0, limit: int = 100
    ) -> List[T]:
        """
        Get all records with pagination.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of records
        """
        stmt = select(cls).offset(skip).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def create(cls: Type[T], db: AsyncSession, obj_in: Dict[str, Any]) -> T:
        """
        Create a new record.

        Args:
            db: Database session
            obj_in: Dictionary with record data

        Returns:
            The created record
        """
        db_obj = cls(**obj_in)
        db.add(db_obj)
        await db.commit()
        await db.refresh(db_obj)
        return db_obj

    async def update(
            self: T, db: AsyncSession, obj_in: Dict[str, Any]
    ) -> T:
        """
        Update a record.

        Args:
            db: Database session
            obj_in: Dictionary with record data

        Returns:
            The updated record
        """
        for field, value in obj_in.items():
            setattr(self, field, value)

        await db.commit()
        await db.refresh(self)
        return self

    async def delete(self: T, db: AsyncSession) -> T:
        """
        Delete a record.

        Args:
            db: Database session

        Returns:
            The deleted record
        """
        await db.delete(self)
        await db.commit()
        return self
