"""
User model for the API Gateway.

This module defines the User model for authentication and authorization.
"""

from datetime import datetime
from typing import Optional, Type, TypeVar

from sqlalchemy import Boolean, DateTime, String, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from gateway.db.base import Base
from gateway.utils.password import get_password_hash, verify_password

# Type variable for User class
T = TypeVar("T", bound="User")


class User(Base):
    """
    User model for authentication and authorization.

    This model represents users of the API Gateway.
    """

    # User information
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Flags
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # Additional fields
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    # webhooks: List["Webhook"] = relationship("Webhook", back_populates="user")

    @classmethod
    async def get_by_email(
            cls: Type[T], db: AsyncSession, email: str
    ) -> Optional[T]:
        """
        Get a user by email.

        Args:
            db: Database session
            email: User email

        Returns:
            The user if found, None otherwise
        """
        stmt = select(cls).where(cls.email == email)
        result = await db.execute(stmt)
        return result.scalars().first()

    @classmethod
    async def create_user(
            cls: Type[T],
            db: AsyncSession,
            *,
            email: str,
            password: str,
            full_name: Optional[str] = None,
            is_superuser: bool = False,
    ) -> T:
        """
        Create a new user.

        Args:
            db: Database session
            email: User email
            password: User password (will be hashed)
            full_name: User full name
            is_superuser: Whether the user is a superuser

        Returns:
            The created user
        """
        user_dict = {
            "email": email,
            "hashed_password": get_password_hash(password),
            "full_name": full_name,
            "is_superuser": is_superuser,
        }

        return await cls.create(db, user_dict)

    def verify_password(self, password: str) -> bool:
        """
        Verify a password.

        Args:
            password: Password to verify

        Returns:
            True if the password is correct, False otherwise
        """
        return verify_password(password, self.hashed_password)

    async def update_last_login(self, db: AsyncSession) -> None:
        """
        Update the last login timestamp.

        Args:
            db: Database session
        """
        self.last_login = datetime.now()
        await db.commit()
        await db.refresh(self)
