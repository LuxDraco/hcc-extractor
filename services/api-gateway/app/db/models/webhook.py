"""
Webhook model for the API Gateway.

This module defines the Webhook model for tracking webhooks registered
in the system for event notifications.
"""

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Type, TypeVar, Any

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, JSON,
    select
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Type variable for Webhook class
T = TypeVar("T", bound="Webhook")


class WebhookEventType(enum.Enum):
    """Enum for webhook event types."""
    DOCUMENT_UPLOADED = "document.uploaded"
    EXTRACTION_COMPLETED = "extraction.completed"
    ANALYSIS_COMPLETED = "analysis.completed"
    VALIDATION_COMPLETED = "validation.completed"
    PROCESSING_COMPLETED = "processing.completed"
    ERROR = "error"
    ALL = "all"


class WebhookStatus(enum.Enum):
    """Enum for webhook status."""
    ACTIVE = "active"
    DISABLED = "disabled"
    SUSPENDED = "suspended"  # Automatic suspension after too many failures


class Webhook(Base):
    """
    Webhook model for event notifications.

    This model represents webhooks registered in the system for notifying
    external systems about events.
    """

    # Core webhook information
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Configuration
    event_types: Mapped[List[WebhookEventType]] = mapped_column(
        JSON, default=[], nullable=False
    )
    status: Mapped[WebhookStatus] = mapped_column(
        Enum(WebhookStatus), default=WebhookStatus.ACTIVE, nullable=False
    )

    # Authentication
    secret_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    headers: Mapped[Dict[str, str]] = mapped_column(JSON, default={}, nullable=False)

    # Rate limiting and retry settings
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=10, nullable=False)

    # Statistics
    last_triggered_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    success_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Relationships
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False
    )
    # user: "User" = relationship("User", back_populates="webhooks")

    @classmethod
    async def get_active_webhooks_for_event(
        cls: Type[T],
        db: AsyncSession,
        event_type: WebhookEventType,
    ) -> List[T]:
        """
        Get active webhooks that are subscribed to a specific event type.

        Args:
            db: Database session
            event_type: Event type to filter by

        Returns:
            List of active webhooks subscribed to the event type
        """
        # We need a custom query because event_types is a JSON array
        stmt = (
            select(cls)
            .where(cls.status == WebhookStatus.ACTIVE)
            # Check if event_type is in the event_types array or if "all" is in the array
            .where(
                (
                    cls.event_types.contains([event_type.value])
                    | cls.event_types.contains([WebhookEventType.ALL.value])
                )
            )
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_success_stats(self, db: AsyncSession) -> None:
        """
        Update webhook statistics after a successful delivery.

        Args:
            db: Database session
        """
        now = datetime.now()
        self.last_triggered_at = now
        self.last_success_at = now
        self.success_count += 1

        await db.commit()
        await db.refresh(self)

    async def update_failure_stats(self, db: AsyncSession) -> None:
        """
        Update webhook statistics after a failed delivery.

        Args:
            db: Database session
        """
        now = datetime.now()
        self.last_triggered_at = now
        self.last_failure_at = now
        self.failure_count += 1

        # Auto-suspend webhook if it has too many consecutive failures
        if self.failure_count > 10 and not self.last_success_at:
            # If we've had more than 10 failures and no successes ever
            self.status = WebhookStatus.SUSPENDED
        elif self.last_success_at and (now - self.last_success_at).days > 7:
            # Or if we haven't had a success in more than a week
            self.status = WebhookStatus.SUSPENDED

        await db.commit()
        await db.refresh(self)