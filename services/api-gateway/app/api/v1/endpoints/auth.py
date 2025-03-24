"""
Authentication endpoints for the API Gateway.

This module defines endpoints for user authentication and authorization.
"""

from datetime import timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import create_access_token
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.token import Token
from app.schemas.user import UserCreate, UserRead

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.post(
    "/login",
    response_model=Token,
    summary="Login and get access token",
    description="Login with username (email) and password to get an access token.",
)
async def login(
        db: AsyncSession = Depends(get_db),
        form_data: OAuth2PasswordRequestForm = Depends(),
) -> Any:
    """
    Login with username (email) and password to get an access token.

    Args:
        db: Database session
        form_data: Login form data

    Returns:
        Access token

    Raises:
        HTTPException: If authentication fails
    """
    user = await User.get_by_email(db, email=form_data.username)

    if not user:
        logger.warning(
            "Login attempt with invalid email",
            email=form_data.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.verify_password(form_data.password):
        logger.warning(
            "Login attempt with invalid password",
            email=form_data.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        logger.warning(
            "Login attempt for inactive user",
            email=form_data.username,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Inactive user",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Update last login
    await user.update_last_login(db)

    # Create access token
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )

    logger.info(
        "User logged in successfully",
        user_id=str(user.id),
        email=user.email,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
    }


@router.post(
    "/register",
    response_model=UserRead,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Register a new user with email and password.",
)
async def register(
        user_in: UserCreate,
        db: AsyncSession = Depends(get_db),
) -> Any:
    """
    Register a new user.

    Args:
        user_in: User creation data
        db: Database session

    Returns:
        Created user

    Raises:
        HTTPException: If registration fails
    """
    # Check if user already exists
    existing_user = await User.get_by_email(db, email=user_in.email)

    if existing_user:
        logger.warning(
            "Registration attempt with existing email",
            email=user_in.email,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user = await User.create_user(
        db,
        email=user_in.email,
        password=user_in.password,
        full_name=user_in.full_name,
    )

    logger.info(
        "User registered successfully",
        user_id=str(user.id),
        email=user.email,
    )

    return user