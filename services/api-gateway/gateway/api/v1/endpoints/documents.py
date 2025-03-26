"""
Document endpoints for the API Gateway.

This module defines endpoints for document operations.
"""

import uuid
from typing import Any, Optional

import structlog
from fastapi import (
    APIRouter, Depends, File, Form, HTTPException, Path, Query,
    UploadFile, status
)
from sqlalchemy.ext.asyncio import AsyncSession

from gateway.core.config import settings
from gateway.core.dependencies import get_current_user, get_current_user_optional
from gateway.db.models.document import ProcessingStatus, StorageType
from gateway.db.models.user import User
from gateway.db.session import get_db
from gateway.schemas.document import (
    DocumentCreate, DocumentRead, DocumentDetail,
    DocumentList, ProcessingStatusEnum
)
from gateway.services.document import DocumentService
from gateway.services.message_broker import MessageBrokerService
from gateway.services.storage import StorageService
from gateway.utils.logging import configure_logging
from gateway.utils.metrics import record_document_processed

configure_logging(log_level=settings.LOG_LEVEL)
logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=DocumentRead,
    status_code=status.HTTP_201_CREATED,
    summary="Upload a document",
    description="Upload a clinical document for processing.",
)
async def upload_document(
        file: UploadFile = File(...),
        description: Optional[str] = Form(None),
        priority: bool = Form(False),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        document_service: DocumentService = Depends(),
        storage_service: StorageService = Depends(),
        message_broker: MessageBrokerService = Depends(),
) -> Any:
    """Upload a clinical document for processing."""
    logger.info(
        "Document upload requested",
        filename=file.filename,
        content_type=file.content_type,
        priority=priority,
        user_id=current_user.id if current_user else None,
    )

    # Validate file type
    if not document_service.is_valid_document_type(file.content_type):
        logger.warning(
            "Invalid document type",
            content_type=file.content_type,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid document type. Supported types: text/plain, application/pdf, application/msword, application/octet-stream",
        )

    # Read file content
    content = await file.read()

    # Store the document
    storage_info = await storage_service.store_document(
        content=content,
        filename=file.filename,
        content_type=file.content_type,
    )

    # Create document in database with transaction
    document_in = DocumentCreate(
        filename=file.filename,
        file_size=len(content),
        content_type=file.content_type,
        storage_type=StorageType[storage_info["storage_type"].upper()].value.upper(),
        storage_path=storage_info["storage_path"],
        status=ProcessingStatus.PENDING,
        is_processed=False,
        processing_started_at=None,
        processing_completed_at=None,
        user_id=current_user.id if current_user else None,
        description=description,
        priority=priority,
    )

    document = await document_service.create_document(db, document_in)

    # Publish message to processing queue - this must succeed
    try:
        content_str = content.decode("utf-8")
        await message_broker.publish_document_uploaded(
            document_id=str(document.id),
            storage_path=document.storage_path,
            storage_type=document.storage_type.value,
            content_type=document.content_type,
            document_content=content_str,
            priority=priority,
        )
    except Exception as e:
        logger.error(
            "Failed to publish document to processing queue",
            document_id=str(document.id),
            error=str(e),
        )
        # Delete the document from database since processing can't continue
        if document:
            await document_service.delete_document(db, document.id)

        # Clean up the stored file
        try:
            await storage_service.delete_document(
                storage_type=storage_info["storage_type"],
                storage_path=storage_info["storage_path"],
            )
        except Exception as storage_e:
            logger.warning(f"Failed to clean up storage after RabbitMQ failure: {str(storage_e)}")

        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Document processing system is currently unavailable. Please try again later.",
        )

    logger.info(
        "Document uploaded successfully",
        document_id=str(document.id),
        storage_type=document.storage_type.value,
        storage_path=document.storage_path,
    )

    return document


@router.get(
    "/",
    response_model=DocumentList,
    summary="List documents",
    description="List clinical documents with pagination and filtering.",
)
async def list_documents(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        status: Optional[ProcessingStatusEnum] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        document_service: DocumentService = Depends(),
) -> Any:
    """
    List clinical documents with pagination and filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        status: Filter by processing status
        db: Database session
        current_user: Current user (optional)
        document_service: Document service

    Returns:
        List of documents
    """
    logger.info(
        "Document list requested",
        skip=skip,
        limit=limit,
        status=status.value if status else None,
        user_id=current_user.id if current_user else None,
    )

    # Convert status enum to model status
    db_status = None
    if status:
        db_status = ProcessingStatus[status.value.upper()]

    # Get documents
    documents, total = await document_service.get_documents(
        db,
        skip=skip,
        limit=limit,
        status=db_status,
        user_id=current_user.id if current_user and not current_user.is_superuser else None,
    )

    return {
        "items": documents,
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/{document_id}",
    response_model=DocumentDetail,
    summary="Get document details",
    description="Get detailed information about a specific document.",
)
async def get_document(
        document_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        document_service: DocumentService = Depends(),
) -> Any:
    """
    Get detailed information about a specific document.

    Args:
        document_id: ID of the document
        db: Database session
        current_user: Current user (optional)
        document_service: Document service

    Returns:
        Document details

    Raises:
        HTTPException: If the document is not found
    """
    logger.info(
        "Document details requested",
        document_id=str(document_id),
        user_id=current_user.id if current_user else None,
    )

    # Get document
    document = await document_service.get_document(db, document_id)

    if not document:
        logger.warning(
            "Document not found",
            document_id=str(document_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check permissions
    if (
            current_user
            and not current_user.is_superuser
            and document.user_id
            and document.user_id != current_user.id
    ):
        logger.warning(
            "Unauthorized access to document",
            document_id=str(document_id),
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this document",
        )

    return document


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete document",
    description="Delete a document and its associated data.",
)
async def delete_document(
        document_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        document_service: DocumentService = Depends(),
        storage_service: StorageService = Depends(),
) -> Any:
    """
    Delete a document and its associated data.

    Args:
        document_id: ID of the document
        db: Database session
        current_user: Current user
        document_service: Document service
        storage_service: Storage service

    Returns:
        No content

    Raises:
        HTTPException: If the document is not found or cannot be deleted
    """
    logger.info(
        "Document deletion requested",
        document_id=str(document_id),
        user_id=current_user.id,
    )

    # Get document
    document = await document_service.get_document(db, document_id)

    if not document:
        logger.warning(
            "Document not found for deletion",
            document_id=str(document_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check permissions
    if (
            not current_user.is_superuser
            and document.user_id
            and document.user_id != current_user.id
    ):
        logger.warning(
            "Unauthorized document deletion attempt",
            document_id=str(document_id),
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this document",
        )

    try:
        # Delete from storage
        await storage_service.delete_document(
            storage_type=document.storage_type.value,
            storage_path=document.storage_path,
        )

        # Delete from database
        await document_service.delete_document(db, document_id)

        logger.info(
            "Document deleted successfully",
            document_id=str(document_id),
        )

        # Record metrics
        record_document_processed("deleted")

        return {
            "successful": True,
            "message": "Document deleted successfully",
        }

    except Exception as e:
        logger.exception(
            "Error deleting document",
            document_id=str(document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error deleting document",
        )


@router.get(
    "/{document_id}/download",
    summary="Download document",
    description="Download the original document file.",
)
async def download_document(
        document_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: Optional[User] = Depends(get_current_user_optional),
        document_service: DocumentService = Depends(),
        storage_service: StorageService = Depends(),
) -> Any:
    """
    Download the original document file.

    Args:
        document_id: ID of the document
        db: Database session
        current_user: Current user (optional)
        document_service: Document service
        storage_service: Storage service

    Returns:
        Document file

    Raises:
        HTTPException: If the document is not found or cannot be retrieved
    """
    logger.info(
        "Document download requested",
        document_id=str(document_id),
        user_id=current_user.id if current_user else None,
    )

    # Get document
    document = await document_service.get_document(db, document_id)

    if not document:
        logger.warning(
            "Document not found for download",
            document_id=str(document_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check permissions
    if (
            current_user
            and not current_user.is_superuser
            and document.user_id
            and document.user_id != current_user.id
    ):
        logger.warning(
            "Unauthorized document download attempt",
            document_id=str(document_id),
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to download this document",
        )

    try:
        # Get file from storage
        file_content, filename, content_type = await storage_service.get_document(
            storage_type=document.storage_type.value,
            storage_path=document.storage_path,
        )

        # Return file response
        from fastapi.responses import Response

        return Response(
            content=file_content,
            media_type=content_type,
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
            },
        )

    except Exception as e:
        logger.exception(
            "Error downloading document",
            document_id=str(document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error downloading document",
        )


@router.post(
    "/{document_id}/reprocess",
    response_model=DocumentRead,
    summary="Reprocess document",
    description="Reprocess a document that has already been processed.",
)
async def reprocess_document(
        document_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        document_service: DocumentService = Depends(),
        message_broker: MessageBrokerService = Depends(),
) -> Any:
    """
    Reprocess a document that has already been processed.

    Args:
        document_id: ID of the document
        db: Database session
        current_user: Current user
        document_service: Document service
        message_broker: Message broker service

    Returns:
        Updated document information

    Raises:
        HTTPException: If the document is not found or cannot be reprocessed
    """
    logger.info(
        "Document reprocessing requested",
        document_id=str(document_id),
        user_id=current_user.id,
    )

    # Get document
    document = await document_service.get_document(db, document_id)

    if not document:
        logger.warning(
            "Document not found for reprocessing",
            document_id=str(document_id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    # Check permissions
    if (
            not current_user.is_superuser
            and document.user_id
            and document.user_id != current_user.id
    ):
        logger.warning(
            "Unauthorized document reprocessing attempt",
            document_id=str(document_id),
            user_id=current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to reprocess this document",
        )

    try:
        # Reset document status
        document = await document_service.update_document_status(
            db,
            document_id,
            ProcessingStatus.PENDING,
        )

        # Publish message to processing queue
        await message_broker.publish_document_uploaded(
            document_id=str(document.id),
            storage_path=document.storage_path,
            storage_type=document.storage_type.value,
            content_type=document.content_type,
            priority=True,  # Prioritize reprocessing
        )

        logger.info(
            "Document reprocessing initiated",
            document_id=str(document.id),
        )

        # Record metrics
        record_document_processed("reprocessed")

        return document

    except Exception as e:
        logger.exception(
            "Error reprocessing document",
            document_id=str(document_id),
            error=str(e),
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Error reprocessing document",
        )
