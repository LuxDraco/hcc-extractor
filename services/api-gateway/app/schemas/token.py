"""
Token schemas for the API Gateway.

This module defines Pydantic models for authentication tokens.
"""

from typing import Optional

from pydantic import BaseModel, Field


class Token(BaseModel):
    """Schema for authentication token."""
    access_token: str = Field(..., description="JWT access token")
    token_type: str = Field("bearer", description="Token type")


class TokenPayload(BaseModel):
    """Schema for token payload."""
    sub: Optional[str] = Field(None, description="Subject (user ID)")
    exp: int = Field(..., description="Expiration timestamp")


class TokenData(BaseModel):
    """Schema for token data."""
    username: Optional[str] = Field(None, description="Username")