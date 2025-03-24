"""
Batch processing endpoints for the API Gateway.

This module defines endpoints for batch document processing operations.
"""

import uuid
from typing import Any, List, Optional

import structlog
from fastapi import (
    APIRouter, BackgroundTasks, Depends, File, Form, HTTPException,
    Path, Query, UploadFile, status
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user, require_admin_role
from app.db.models.document import Document, ProcessingStatus
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.document import DocumentRead, DocumentList
from app.services.document import DocumentService
from app.services.message_broker import MessageBrokerService
from app.services.storage import StorageService

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/upload",
    response_model=DocumentList,
    status_code=status.HTTP_201_CREATED,
    summary="Batch upload documents",
    description="Upload multiple documents for processing in a single request."
)
async def batch_upload(
        files: List[UploadFile] = File(...),
        priority: bool = Form(False),
        background_tasks: BackgroundTasks = None,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        document_service: DocumentService = Depends(),
        storage_service: StorageService = Depends(),
        message_broker: MessageBrokerService = Depends(),
) -> Any:
    """
    Upload multiple documents for processing in a single request.

    Args:
        files: Document files to upload
        priority: Whether to prioritize processing these documents
        background_tasks: FastAPI background tasks
        db: Database session
        current_user: Current authenticated user
        document_service: Document service
        storage_service: Storage service
        message_broker: Message broker service

    Returns:
        List of created documents
    """
    logger.info(
        "Batch upload requested",
        file_count=len(files),
        priority=priority,
        user_id=str(current_user.id),
    )

    if not files:
        logger.warning("No files provided for batch upload")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No files provided",
        )

    # Limit the number of files in a single batch
    max_batch_size = 20  # Configurable limit
    if len(files) > max_batch_size:
        logger.warning(
            "Batch upload exceeds maximum size",
            provided=len(files),
            max_size=max_batch_size,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum batch size is {max_batch_size} files",
        )

    # Track created documents
    created_documents = []
    errors = []

    # Process each file
    for file in files:
        try:
            # Validate file type
            if not document_service.is_valid_document_type(file.content_type):
                errors.append({
                    "filename": file.filename,
                    "error": "Invalid document type"
                })
                continue

            # Read file content
            content = await file.read()

            # Store the document
            storage_info = await storage_service.store_document(
                content=content,
                filename=file.filename,
                content_type=file.content_type,
            )

            # Create document in database
            document_in = DocumentCreate(
                filename=file.filename,
                file_size=len(content),
                content_type=file.content_type,
                storage_type=storage_info["storage_type"],
                storage_path=storage_info["storage_path"],
                description=None,  # No description in batch mode
                priority=priority,
                user_id=current_user.id,
            )

            document = await document_service.create_document(db, document_in)
            created_documents.append(document)

            # Queue for processing (non-blocking)
            if background_tasks:
                # Use background tasks to publish without blocking
                background_tasks.add_task(
                    message_broker.publish_document_uploaded,
                    document_id=str(document.id),
                    storage_path=document.storage_path,
                    storage_type=document.storage_type.value,
                    content_type=document.content_type,
                    priority=priority,
                )
            else:
                # Publish directly if background tasks not available
                await message_broker.publish_document_uploaded(
                    document_id=str(document.id),
                    storage_path=document.storage_path,
                    storage_type=document.storage_type.value,
                    content_type=document.content_type,
                    priority=priority,
                )

        except Exception as e:
            logger.exception(
                "Error processing file in batch upload",
                filename=file.filename,
                error=str(e),
            )
            errors.append({
                "filename": file.filename,
                "error": str(e)
            })

    # Log summary
    logger.info(
        "Batch upload completed",
        total=len(files),
        successful=len(created_documents),
        failed=len(errors),
    )

    # If no documents were created, return an error
    if not created_documents:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to process any documents: {errors}",
        )

    # Return both created documents and errors
    return {
        "items": created_documents,
        "total": len(created_documents),
        "skip": 0,
        "limit": len(created_documents),
        "errors": errors,
    }


@router.post(
    "/process",
    response_model=dict,
    summary="Batch process documents",
    description="Reprocess multiple documents in a single request."
)
async def batch_process(
        document_ids: List[uuid.UUID],
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        document_service: DocumentService = Depends(),
        message_broker: MessageBrokerService = Depends(),
) -> Any:
    """
    Reprocess multiple documents in a single request.

    Args:
        document_ids: IDs of documents to reprocess
        db: Database session
        current_user: Current authenticated user
        document_service: Document service
        message_broker: Message broker service

    Returns:
        Processing status
    """
    logger.info(
        "Batch processing requested",
        document_count=len(document_ids),
        user_id=str(current_user.id),
    )

    if not document_ids:
        logger.warning("No document IDs provided for batch processing")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document IDs provided",
        )

    # Limit the number of documents in a single batch
    max_batch_size = 50  # Configurable limit
    if len(document_ids) > max_batch_size:
        logger.warning(
            "Batch processing exceeds maximum size",
            provided=len(document_ids),
            max_size=max_batch_size,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum batch size is {max_batch_size} documents",
        )

    # Track successful and failed operations
    successful = []
    failed = []

    # Process each document
    for doc_id in document_ids:
        try:
            # Get document
            document = await document_service.get_document(db, doc_id)

            if not document:
                failed.append({
                    "id": str(doc_id),
                    "error": "Document not found"
                })
                continue

            # Check permissions
            if (
                    not current_user.is_superuser
                    and document.user_id
                    and document.user_id != current_user.id
            ):
                failed.append({
                    "id": str(doc_id),
                    "error": "Not authorized to reprocess this document"
                })
                continue

            # Reset document status
            document = await document_service.update_document_status(
                db,
                doc_id,
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

            successful.append(str(doc_id))

        except Exception as e:
            logger.exception(
                "Error reprocessing document in batch",
                document_id=str(doc_id),
                error=str(e),
            )
            failed.append({
                "id": str(doc_id),
                "error": str(e)
            })

    # Log summary
    logger.info(
        "Batch processing completed",
        total=len(document_ids),
        successful=len(successful),
        failed=len(failed),
    )

    # Return results
    return {
        "successful": successful,
        "failed": failed,
        "total": len(document_ids),
    }


@router.delete(
    "/",
    status_code=status.HTTP_200_OK,  # Changed to 200 to return result info
    summary="Delete multiple documents",
    description="Delete multiple documents in a single request.",
)
async def batch_delete(
        document_ids: List[uuid.UUID],
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(require_admin_role),
        document_service: DocumentService = Depends(),
        storage_service: StorageService = Depends(),
) -> Any:
    """
    Delete multiple documents in a single request.

    Args:
        document_ids: IDs of documents to delete
        db: Database session
        current_user: Current authenticated user (must be admin)
        document_service: Document service
        storage_service: Storage service

    Returns:
        Deletion status
    """
    logger.info(
        "Batch deletion requested",
        document_count=len(document_ids),
        user_id=str(current_user.id),
    )

    if not document_ids:
        logger.warning("No document IDs provided for batch deletion")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No document IDs provided",
        )

    # Limit the number of documents in a single batch
    max_batch_size = 100  # Configurable limit
    if len(document_ids) > max_batch_size:
        logger.warning(
            "Batch deletion exceeds maximum size",
            provided=len(document_ids),
            max_size=max_batch_size,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Maximum batch size is {max_batch_size} documents",
        )

    # Track successful and failed operations
    successful = []
    failed = []

    # Process each document
    for doc_id in document_ids:
        try:
            # Get document
            document = await document_service.get_document(db, doc_id)

            if not document:
                failed.append({
                    "id": str(doc_id),
                    "error": "Document not found"
                })
                continue

            # Delete from storage
            try:
                await storage_service.delete_document(
                    storage_type=document.storage_type.value,
                    storage_path=document.storage_path,
                )
            except Exception as storage_e:
                logger.warning(
                    "Error deleting document from storage",
                    document_id=str(doc_id),
                    error=str(storage_e),
                )
                # Continue with DB deletion even if storage deletion fails

            # Delete from database
            await document_service.delete_document(db, doc_id)
            successful.append(str(doc_id))

        except Exception as e:
            logger.exception(
                "Error deleting document in batch",
                document_id=str(doc_id),
                error=str(e),
            )
            failed.append({
                "id": str(doc_id),
                "error": str(e)
            })

    # Log summary
    logger.info(
        "Batch deletion completed",
        total=len(document_ids),
        successful=len(successful),
        failed=len(failed),
    )

    # Return results
    return {
        "successful": successful,
        "failed": failed,
        "total": len(document_ids),
    }


@router.get(
    "/status",
    response_model=dict,
    summary="Get batch processing status",
    description="Get status information about current batch processing jobs."
)
async def batch_status(
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
        document_service: DocumentService = Depends(),
) -> Any:
    """
    Get status information about current batch processing jobs.

    Args:
        db: Database session
        current_user: Current authenticated user
        document_service: Document service

    Returns:
        Batch processing status
    """
    logger.info(
        "Batch status requested",
        user_id=str(current_user.id),
    )

    # Get counts of documents by status
    status_counts = {}
    for status_value in ProcessingStatus:
        count = await document_service.count_documents_by_status(
            db,
            status_value,
            user_id=None if current_user.is_superuser else current_user.id
        )
        status_counts[status_value.value.lower()] = count

    # Get recently processed documents
    recent_documents = await document_service.get_recent_documents(
        db,
        limit=10,
        user_id=None if current_user.is_superuser else current_user.id
    )

    return {
        "status_counts": status_counts,
        "recent_documents": [doc.id for doc in recent_documents],
        "total_documents": sum(status_counts.values()),
    }
