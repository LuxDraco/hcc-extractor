"""
User schemas for the API Gateway.

This module defines Pydantic models for user-related operations.
"""

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field, validator


class UserBase(BaseModel):
    """Base schema for user operations."""
    email: EmailStr = Field(..., description="User email")
    full_name: Optional[str] = Field(None, description="User full name")
    is_active: bool = Field(True, description="Whether the user is active")


class UserCreate(UserBase):
    """Schema for user creation."""
    password: str = Field(..., description="User password")

    @validator("password")
    def password_min_length(cls, v: str) -> str:
        """Validate that the password meets minimum length requirements."""
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserUpdate(BaseModel):
    """Schema for user update."""
    email: Optional[EmailStr] = Field(None, description="User email")
    full_name: Optional[str] = Field(None, description="User full name")
    password: Optional[str] = Field(None, description="User password")
    is_active: Optional[bool] = Field(None, description="Whether the user is active")

    @validator("password")
    def password_min_length(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the password meets minimum length requirements if provided."""
        if v is not None and len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserRead(UserBase):
    """Schema for user read operations."""
    id: uuid.UUID = Field(..., description="User ID")
    created_at: datetime = Field(..., description="Timestamp when the user was created")
    updated_at: datetime = Field(..., description="Timestamp when the user was last updated")
    is_superuser: bool = Field(..., description="Whether the user is a superuser")
    last_login: Optional[datetime] = Field(None, description="Timestamp of the last login")

    class Config:
        """Pydantic model configuration."""
        from_attributes = True


class UserDetail(UserRead):
    """Schema for detailed user information."""
    pass
