"""
Document model for the API Gateway.

This module defines the Document model for tracking clinical documents
processed by the system.
"""

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Type, TypeVar, Any

from sqlalchemy import (
    Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, JSON,
    select
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

# Type variable for Document class
T = TypeVar("T", bound="Document")


class ProcessingStatus(enum.Enum):
    """Enum for document processing status."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class StorageType(enum.Enum):
    """Enum for document storage types."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


class Document(Base):
    """
    Document model for clinical documents.

    This model represents clinical documents processed by the system,
    including their processing status and metadata.
    """

    # Core document information
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    content_type: Mapped[str] = mapped_column(String(100), nullable=False)

    # Storage information
    storage_type: Mapped[StorageType] = mapped_column(Enum(StorageType), nullable=False)
    storage_path: Mapped[str] = mapped_column(String(500), nullable=False)

    # Processing status
    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.PENDING, nullable=False
    )
    is_processed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    processing_completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Processing results
    total_conditions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    hcc_relevant_conditions: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extraction_result_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    analysis_result_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    validation_result_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Error tracking
    errors: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # JSON fields for flexible metadata
    patient_info: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON, nullable=True)
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default={}, nullable=False)

    # Relationships
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )

    # user: Optional["User"] = relationship("User", back_populates="documents")

    @classmethod
    async def get_by_status(
            cls: Type[T],
            db: AsyncSession,
            status: ProcessingStatus,
            *,
            skip: int = 0,
            limit: int = 100
    ) -> List[T]:
        """
        Get documents by processing status.

        Args:
            db: Database session
            status: Processing status to filter by
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of documents with the specified status
        """
        stmt = (
            select(cls)
            .where(cls.status == status)
            .order_by(cls.created_at.desc())
            .offset(skip)
            .limit(limit)
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    async def update_status(
            self: T,
            db: AsyncSession,
            status: ProcessingStatus,
            *,
            errors: Optional[str] = None
    ) -> T:
        """
        Update the processing status of a document.

        Args:
            db: Database session
            status: New processing status
            errors: Optional error messages

        Returns:
            The updated document
        """
        self.status = status

        if errors:
            self.errors = errors

        # Update timestamps based on status
        if status == ProcessingStatus.EXTRACTING and not self.processing_started_at:
            self.processing_started_at = datetime.now()

        if status in (ProcessingStatus.COMPLETED, ProcessingStatus.FAILED):
            self.processing_completed_at = datetime.now()
            self.is_processed = status == ProcessingStatus.COMPLETED

        await db.commit()
        await db.refresh(self)
        return self

    async def update_processing_results(
            self: T,
            db: AsyncSession,
            *,
            total_conditions: Optional[int] = None,
            hcc_relevant_conditions: Optional[int] = None,
            extraction_result_path: Optional[str] = None,
            analysis_result_path: Optional[str] = None,
            validation_result_path: Optional[str] = None,
            patient_info: Optional[Dict[str, Any]] = None,
            metadata: Optional[Dict[str, Any]] = None,
    ) -> T:
        """
        Update processing results for a document.

        Args:
            db: Database session
            total_conditions: Total number of conditions extracted
            hcc_relevant_conditions: Number of HCC-relevant conditions
            extraction_result_path: Path to extraction result
            analysis_result_path: Path to analysis result
            validation_result_path: Path to validation result
            patient_info: Patient information extracted from document
            metadata: Additional metadata

        Returns:
            The updated document
        """
        if total_conditions is not None:
            self.total_conditions = total_conditions

        if hcc_relevant_conditions is not None:
            self.hcc_relevant_conditions = hcc_relevant_conditions

        if extraction_result_path:
            self.extraction_result_path = extraction_result_path

        if analysis_result_path:
            self.analysis_result_path = analysis_result_path

        if validation_result_path:
            self.validation_result_path = validation_result_path

        if patient_info:
            self.patient_info = patient_info

        if metadata:
            # Merge with existing metadata
            self.metadata = {**self.metadata, **metadata}

        await db.commit()
        await db.refresh(self)
        return self