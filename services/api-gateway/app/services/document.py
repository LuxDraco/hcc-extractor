"""
Document service for the API Gateway.

This module provides business logic for document operations.
"""

import re
import time
import uuid
from typing import Dict, List, Optional, Tuple, Any

import structlog
from fastapi import Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import Select

from app.db.models.document import Document, ProcessingStatus
from app.db.session import get_db
from app.schemas.document import DocumentCreate, DocumentUpdate
from app.utils.metrics import DB_QUERY_TIME

logger = structlog.get_logger(__name__)


class DocumentService:
    """Service for document operations."""

    def __init__(self, db: AsyncSession = Depends(get_db)):
        """
        Initialize the document service.

        Args:
            db: Database session
        """
        self.db = db

    def is_valid_document_type(self, content_type: str) -> bool:
        """
        Check if a document type is valid for processing.

        Args:
            content_type: MIME type of the document

        Returns:
            Whether the document type is valid
        """
        # List of valid MIME types
        valid_types = [
            "text/plain",
            "application/pdf",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/msword",
        ]

        return content_type in valid_types

    async def create_document(
            self, db: AsyncSession, document_in: DocumentCreate
    ) -> Document:
        """
        Create a new document.

        Args:
            db: Database session
            document_in: Document creation data

        Returns:
            Created document
        """
        start_time = time.time()

        document_data = document_in.model_dump()
        document = await Document.create(db, document_data)

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="insert", table="documents").observe(query_time)

        logger.info(
            "Document created",
            document_id=str(document.id),
            filename=document.filename,
            content_type=document.content_type,
        )

        return document

    async def get_document(
            self, db: AsyncSession, document_id: uuid.UUID
    ) -> Optional[Document]:
        """
        Get a document by ID.

        Args:
            db: Database session
            document_id: Document ID

        Returns:
            Document if found, None otherwise
        """
        start_time = time.time()

        document = await Document.get_by_id(db, document_id)

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="select", table="documents").observe(query_time)

        return document

    async def get_documents(
            self,
            db: AsyncSession,
            *,
            skip: int = 0,
            limit: int = 100,
            status: Optional[ProcessingStatus] = None,
            user_id: Optional[uuid.UUID] = None,
    ) -> Tuple[List[Document], int]:
        """
        Get documents with pagination and filtering.

        Args:
            db: Database session
            skip: Number of records to skip
            limit: Maximum number of records to return
            status: Filter by processing status
            user_id: Filter by user ID

        Returns:
            Tuple of (documents, total_count)
        """
        start_time = time.time()

        # Build query
        query = select(Document)

        # Add filters
        if status:
            query = query.where(Document.status == status)

        if user_id:
            query = query.where(Document.user_id == user_id)

        # Add sorting
        query = query.order_by(Document.created_at.desc())

        # Count total records
        count_query = select(func.count()).select_from(query.subquery())
        result = await db.execute(count_query)
        total = result.scalar_one()

        # Add pagination
        query = query.offset(skip).limit(limit)

        # Execute query
        result = await db.execute(query)
        documents = result.scalars().all()

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="select", table="documents").observe(query_time)

        return list(documents), total

    async def update_document(
            self, db: AsyncSession, document_id: uuid.UUID, document_in: DocumentUpdate
    ) -> Optional[Document]:
        """
        Update a document.

        Args:
            db: Database session
            document_id: Document ID
            document_in: Document update data

        Returns:
            Updated document if found, None otherwise
        """
        start_time = time.time()

        # Get document
        document = await self.get_document(db, document_id)

        if not document:
            return None

        # Update document
        update_data = document_in.model_dump(exclude_unset=True)
        await document.update(db, update_data)

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="update", table="documents").observe(query_time)

        logger.info(
            "Document updated",
            document_id=str(document.id),
            fields=list(update_data.keys()),
        )

        return document

    async def delete_document(
            self, db: AsyncSession, document_id: uuid.UUID
    ) -> Optional[Document]:
        """
        Delete a document.

        Args:
            db: Database session
            document_id: Document ID

        Returns:
            Deleted document if found, None otherwise
        """
        start_time = time.time()

        # Get document
        document = await self.get_document(db, document_id)

        if not document:
            return None

        # Delete document
        await document.delete(db)

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="delete", table="documents").observe(query_time)

        logger.info(
            "Document deleted",
            document_id=str(document_id),
        )

        return document

    async def update_document_status(
            self,
            db: AsyncSession,
            document_id: uuid.UUID,
            status: ProcessingStatus,
            *,
            errors: Optional[str] = None,
    ) -> Optional[Document]:
        """
        Update the processing status of a document.

        Args:
            db: Database session
            document_id: Document ID
            status: New processing status
            errors: Optional error messages

        Returns:
            Updated document if found, None otherwise
        """
        start_time = time.time()

        # Get document
        document = await self.get_document(db, document_id)

        if not document:
            return None

        # Update status
        document = await document.update_status(db, status, errors=errors)

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="update", table="documents").observe(query_time)

        logger.info(
            "Document status updated",
            document_id=str(document_id),
            status=status.value,
            has_errors=errors is not None,
        )

        return document

    async def update_document_results(
            self,
            db: AsyncSession,
            document_id: uuid.UUID,
            **kwargs: Any,
    ) -> Optional[Document]:
        """
        Update processing results for a document.

        Args:
            db: Database session
            document_id: Document ID
            **kwargs: Processing results (see Document.update_processing_results)

        Returns:
            Updated document if found, None otherwise
        """
        start_time = time.time()

        # Get document
        document = await self.get_document(db, document_id)

        if not document:
            return None

        # Update results
        document = await document.update_processing_results(db, **kwargs)

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="update", table="documents").observe(query_time)

        logger.info(
            "Document results updated",
            document_id=str(document_id),
            fields=list(kwargs.keys()),
        )

        return document

    async def get_documents_by_status(
            self,
            db: AsyncSession,
            status: ProcessingStatus,
            *,
            skip: int = 0,
            limit: int = 100,
    ) -> List[Document]:
        """
        Get documents by processing status.

        Args:
            db: Database session
            status: Processing status
            skip: Number of records to skip
            limit: Maximum number of records to return

        Returns:
            List of documents with the specified status
        """
        return await Document.get_by_status(db, status, skip=skip, limit=limit)

    async def count_documents_by_status(
            self,
            db: AsyncSession,
            status: ProcessingStatus,
            *,
            user_id: Optional[uuid.UUID] = None,
    ) -> int:
        """
        Count documents with a specific status.

        Args:
            db: Database session
            status: Processing status
            user_id: Filter by user ID

        Returns:
            Number of documents with the specified status
        """
        start_time = time.time()

        # Build query
        stmt = select(func.count()).select_from(Document)

        # Add filters
        stmt = stmt.where(Document.status == status)

        if user_id:
            stmt = stmt.where(Document.user_id == user_id)

        # Execute query
        result = await db.execute(stmt)
        count = result.scalar_one()

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="count", table="documents").observe(query_time)

        return count

    async def get_recent_documents(
            self,
            db: AsyncSession,
            *,
            limit: int = 10,
            user_id: Optional[uuid.UUID] = None,
    ) -> List[Document]:
        """
        Get recently processed documents.

        Args:
            db: Database session
            limit: Maximum number of records to return
            user_id: Filter by user ID

        Returns:
            List of recently processed documents
        """
        start_time = time.time()

        # Build query
        stmt = select(Document)

        # Add filters
        if user_id:
            stmt = stmt.where(Document.user_id == user_id)

        # Add completed/failed filter to show only processed documents
        stmt = stmt.where(
            (Document.status == ProcessingStatus.COMPLETED) |
            (Document.status == ProcessingStatus.FAILED)
        )

        # Add sorting and limit
        stmt = stmt.order_by(Document.processing_completed_at.desc().nullslast())
        stmt = stmt.limit(limit)

        # Execute query
        result = await db.execute(stmt)
        documents = result.scalars().all()

        # Record query time
        query_time = time.time() - start_time
        DB_QUERY_TIME.labels(query_type="select", table="documents").observe(query_time)

        return list(documents)