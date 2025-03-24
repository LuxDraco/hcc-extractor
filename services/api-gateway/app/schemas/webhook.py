"""
Webhook schemas for the API Gateway.

This module defines Pydantic models for webhook-related operations.
"""

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field, HttpUrl, validator


class WebhookEventTypeEnum(str, enum.Enum):
    """Enum for webhook event types."""
    DOCUMENT_UPLOADED = "document.uploaded"
    EXTRACTION_COMPLETED = "extraction.completed"
    ANALYSIS_COMPLETED = "analysis.completed"
    VALIDATION_COMPLETED = "validation.completed"
    PROCESSING_COMPLETED = "processing.completed"
    ERROR = "error"
    ALL = "all"


class WebhookStatusEnum(str, enum.Enum):
    """Enum for webhook status."""
    ACTIVE = "active"
    DISABLED = "disabled"
    SUSPENDED = "suspended"


class WebhookBase(BaseModel):
    """Base schema for webhook operations."""
    name: str = Field(..., description="Name of the webhook")
    url: HttpUrl = Field(..., description="URL to send events to")
    description: Optional[str] = Field(None, description="Description of the webhook")
    event_types: List[WebhookEventTypeEnum] = Field(
        ..., description="Event types to trigger the webhook"
    )


class WebhookCreate(WebhookBase):
    """Schema for webhook creation."""
    secret_key: Optional[str] = Field(None, description="Secret key for webhook authentication")
    headers: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional headers to send with webhook requests"
    )
    max_attempts: int = Field(3, description="Maximum number of delivery attempts")
    timeout_seconds: int = Field(10, description="Timeout for webhook requests in seconds")

    @validator("event_types")
    def event_types_not_empty(cls, v: List[WebhookEventTypeEnum]) -> List[WebhookEventTypeEnum]:
        """Validate that event types is not empty."""
        if not v:
            raise ValueError("Event types cannot be empty")
        return v


class WebhookUpdate(BaseModel):
    """Schema for webhook update."""
    name: Optional[str] = Field(None, description="Name of the webhook")
    url: Optional[HttpUrl] = Field(None, description="URL to send events to")
    description: Optional[str] = Field(None, description="Description of the webhook")
    event_types: Optional[List[WebhookEventTypeEnum]] = Field(
        None, description="Event types to trigger the webhook"
    )
    status: Optional[WebhookStatusEnum] = Field(None, description="Status of the webhook")
    secret_key: Optional[str] = Field(None, description="Secret key for webhook authentication")
    headers: Optional[Dict[str, str]] = Field(
        None, description="Additional headers to send with webhook requests"
    )
    max_attempts: Optional[int] = Field(None, description="Maximum number of delivery attempts")
    timeout_seconds: Optional[int] = Field(None, description="Timeout for webhook requests in seconds")

    @validator("event_types")
    def event_types_not_empty(cls, v: Optional[List[WebhookEventTypeEnum]]) -> Optional[List[WebhookEventTypeEnum]]:
        """Validate that event types is not empty if provided."""
        if v is not None and not v:
            raise ValueError("Event types cannot be empty")
        return v

    @validator("max_attempts")
    def max_attempts_range(cls, v: Optional[int]) -> Optional[int]:
        """Validate max attempts range."""
        if v is not None and (v < 1 or v > 10):
            raise ValueError("Max attempts must be between 1 and 10")
        return v

    @validator("timeout_seconds")
    def timeout_seconds_range(cls, v: Optional[int]) -> Optional[int]:
        """Validate timeout seconds range."""
        if v is not None and (v < 1 or v > 60):
            raise ValueError("Timeout seconds must be between 1 and 60")
        return v


class WebhookRead(WebhookBase):
    """Schema for webhook read operations."""
    id: uuid.UUID = Field(..., description="ID of the webhook")
    status: WebhookStatusEnum = Field(..., description="Status of the webhook")
    created_at: datetime = Field(..., description="Timestamp when the webhook was created")
    updated_at: datetime = Field(..., description="Timestamp when the webhook was last updated")

    class Config:
        """Pydantic model configuration."""
        orm_mode = True
        from_attributes = True


class WebhookDetail(WebhookRead):
    """Schema for detailed webhook information."""
    secret_key: Optional[str] = Field(None, description="Secret key for webhook authentication")
    headers: Dict[str, str] = Field(
        ..., description="Additional headers to send with webhook requests"
    )
    max_attempts: int = Field(..., description="Maximum number of delivery attempts")
    timeout_seconds: int = Field(..., description="Timeout for webhook requests in seconds")
    last_triggered_at: Optional[datetime] = Field(None, description="Timestamp of the last trigger attempt")
    last_success_at: Optional[datetime] = Field(None, description="Timestamp of the last successful delivery")
    last_failure_at: Optional[datetime] = Field(None, description="Timestamp of the last failed delivery")
    success_count: int = Field(..., description="Number of successful deliveries")
    failure_count: int = Field(..., description="Number of failed deliveries")
    user_id: uuid.UUID = Field(..., description="ID of the user who created the webhook")


class WebhookList(BaseModel):
    """Schema for list of webhooks."""
    items: List[WebhookRead] = Field(..., description="List of webhooks")
    total: int = Field(..., description="Total number of webhooks")
    skip: int = Field(..., description="Number of webhooks skipped")
    limit: int = Field(..., description="Maximum number of webhooks returned")