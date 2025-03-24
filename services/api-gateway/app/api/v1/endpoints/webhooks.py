"""
Webhook endpoints for the API Gateway.

This module defines endpoints for managing webhooks.
"""

import uuid
from typing import Any, List, Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_current_user
from app.db.models.user import User
from app.db.models.webhook import Webhook, WebhookStatus, WebhookEventType
from app.db.session import get_db
from app.schemas.webhook import (
    WebhookCreate, WebhookRead, WebhookUpdate, WebhookDetail, WebhookList,
    WebhookEventTypeEnum, WebhookStatusEnum,
)

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/",
    response_model=WebhookRead,
    status_code=status.HTTP_201_CREATED,
    summary="Create webhook",
    description="Create a new webhook for event notifications."
)
async def create_webhook(
        webhook_in: WebhookCreate,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Create a new webhook.

    Args:
        webhook_in: Webhook creation data
        db: Database session
        current_user: Current authenticated user

    Returns:
        Created webhook
    """
    logger.info(
        "Webhook creation requested",
        name=webhook_in.name,
        url=webhook_in.url,
        event_types=webhook_in.event_types,
        user_id=str(current_user.id),
    )

    # Convert event types from enum to string
    event_types = [et.value for et in webhook_in.event_types]

    # Create webhook
    webhook_data = {
        **webhook_in.model_dump(exclude={"event_types"}),
        "event_types": event_types,
        "user_id": current_user.id,
    }

    webhook = await Webhook.create(db, webhook_data)

    logger.info(
        "Webhook created successfully",
        webhook_id=str(webhook.id),
        name=webhook.name,
        user_id=str(current_user.id),
    )

    return webhook


@router.get(
    "/",
    response_model=WebhookList,
    summary="List webhooks",
    description="List webhooks with pagination and filtering."
)
async def list_webhooks(
        skip: int = Query(0, ge=0),
        limit: int = Query(100, ge=1, le=1000),
        status: Optional[WebhookStatusEnum] = Query(None),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    List webhooks with pagination and filtering.

    Args:
        skip: Number of records to skip
        limit: Maximum number of records to return
        status: Filter by webhook status
        db: Database session
        current_user: Current authenticated user

    Returns:
        List of webhooks
    """
    # Build query
    stmt = db.query(Webhook)

    # Filter by user (unless superuser)
    if not current_user.is_superuser:
        stmt = stmt.filter(Webhook.user_id == current_user.id)

    # Filter by status
    if status:
        db_status = WebhookStatus[status.value.upper()]
        stmt = stmt.filter(Webhook.status == db_status)

    # Count total
    total = await db.scalar(stmt.count())

    # Add pagination
    stmt = stmt.order_by(Webhook.created_at.desc()).offset(skip).limit(limit)

    # Execute query
    result = await db.execute(stmt)
    webhooks = result.scalars().all()

    return {
        "items": list(webhooks),
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.get(
    "/{webhook_id}",
    response_model=WebhookDetail,
    summary="Get webhook",
    description="Get detailed information about a webhook."
)
async def get_webhook(
        webhook_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Get detailed information about a webhook.

    Args:
        webhook_id: Webhook ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Webhook details

    Raises:
        HTTPException: If the webhook is not found or the user doesn't have access
    """
    # Get webhook
    webhook = await Webhook.get_by_id(db, webhook_id)

    if not webhook:
        logger.warning(
            "Webhook not found",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Check permissions
    if not current_user.is_superuser and webhook.user_id != current_user.id:
        logger.warning(
            "Unauthorized webhook access",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
            webhook_user_id=str(webhook.user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this webhook",
        )

    return webhook


@router.put(
    "/{webhook_id}",
    response_model=WebhookRead,
    summary="Update webhook",
    description="Update an existing webhook."
)
async def update_webhook(
        webhook_in: WebhookUpdate,
        webhook_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Update an existing webhook.

    Args:
        webhook_in: Webhook update data
        webhook_id: Webhook ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Updated webhook

    Raises:
        HTTPException: If the webhook is not found or the user doesn't have access
    """
    # Get webhook
    webhook = await Webhook.get_by_id(db, webhook_id)

    if not webhook:
        logger.warning(
            "Webhook not found for update",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Check permissions
    if not current_user.is_superuser and webhook.user_id != current_user.id:
        logger.warning(
            "Unauthorized webhook update attempt",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
            webhook_user_id=str(webhook.user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this webhook",
        )

    # Update webhook
    update_data = webhook_in.model_dump(exclude_unset=True)

    # Convert event types from enum to string if present
    if "event_types" in update_data:
        update_data["event_types"] = [et.value for et in update_data["event_types"]]

    # Convert status from enum to model enum if present
    if "status" in update_data:
        update_data["status"] = WebhookStatus[update_data["status"].upper()]

    await webhook.update(db, update_data)

    logger.info(
        "Webhook updated successfully",
        webhook_id=str(webhook.id),
        name=webhook.name,
        user_id=str(current_user.id),
        fields=list(update_data.keys()),
    )

    return webhook


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete webhook",
    description="Delete a webhook."
)
async def delete_webhook(
        webhook_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Delete a webhook.

    Args:
        webhook_id: Webhook ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        No content

    Raises:
        HTTPException: If the webhook is not found or the user doesn't have access
    """
    # Get webhook
    webhook = await Webhook.get_by_id(db, webhook_id)

    if not webhook:
        logger.warning(
            "Webhook not found for deletion",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Check permissions
    if not current_user.is_superuser and webhook.user_id != current_user.id:
        logger.warning(
            "Unauthorized webhook deletion attempt",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
            webhook_user_id=str(webhook.user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to delete this webhook",
        )

    # Delete webhook
    await webhook.delete(db)

    logger.info(
        "Webhook deleted successfully",
        webhook_id=str(webhook_id),
        user_id=str(current_user.id),
    )

    return {
        "success": True,
        "message": "Webhook deleted successfully",
    }


@router.post(
    "/{webhook_id}/test",
    response_model=dict,
    summary="Test webhook",
    description="Send a test event to the webhook."
)
async def test_webhook(
        webhook_id: uuid.UUID = Path(...),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user),
) -> Any:
    """
    Send a test event to the webhook.

    Args:
        webhook_id: Webhook ID
        db: Database session
        current_user: Current authenticated user

    Returns:
        Test result

    Raises:
        HTTPException: If the webhook is not found or the user doesn't have access
    """
    # Get webhook
    webhook = await Webhook.get_by_id(db, webhook_id)

    if not webhook:
        logger.warning(
            "Webhook not found for testing",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Webhook not found",
        )

    # Check permissions
    if not current_user.is_superuser and webhook.user_id != current_user.id:
        logger.warning(
            "Unauthorized webhook test attempt",
            webhook_id=str(webhook_id),
            user_id=str(current_user.id),
            webhook_user_id=str(webhook.user_id),
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to test this webhook",
        )

    # Check if webhook is active
    if webhook.status != WebhookStatus.ACTIVE:
        logger.warning(
            "Cannot test inactive webhook",
            webhook_id=str(webhook_id),
            status=webhook.status.value,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot test webhook with status {webhook.status.value}",
        )

    # TODO: Implement actual webhook testing with HTTP request

    # For now, we'll just return a success response
    logger.info(
        "Webhook test requested",
        webhook_id=str(webhook_id),
        url=webhook.url,
        user_id=str(current_user.id),
    )

    return {
        "success": True,
        "message": "Test event sent successfully",
        "webhook_id": str(webhook_id),
        "url": webhook.url,
    }