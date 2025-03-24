"""
Configuration module for the HCC Extractor API Gateway.

This module defines the settings and configuration parameters for the API Gateway.
It uses Pydantic's Settings management to load configuration from environment variables.
"""

import os
import secrets
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from pydantic import (
    AnyHttpUrl,
    Field,
    PostgresDsn,
    SecretStr,
    field_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict


class LogLevel(str, Enum):
    """Log level enumeration."""
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class Environment(str, Enum):
    """Environment enumeration."""
    DEVELOPMENT = "development"
    STAGING = "staging"
    PRODUCTION = "production"
    TEST = "test"


class Settings(BaseSettings):
    """
    Application settings loaded from environment variables.

    This class defines all configuration parameters for the API Gateway service,
    with appropriate defaults and validation.
    """
    # General settings
    PROJECT_NAME: str = "HCC Extractor API Gateway"
    PROJECT_DESCRIPTION: str = "API Gateway for the HCC Extractor System"
    VERSION: str = "0.1.0"
    ENVIRONMENT: Environment = Environment.DEVELOPMENT
    DEBUG: bool = False
    LOG_LEVEL: LogLevel = LogLevel.INFO
    API_PREFIX: str = "/api/v1"
    SHOW_DOCS: bool = True
    PORT: int = 8000

    # Security settings
    SECRET_KEY: str = Field(default_factory=lambda: secrets.token_urlsafe(32))
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    ALGORITHM: str = "HS256"

    # CORS settings
    CORS_ORIGINS: List[Union[AnyHttpUrl, str]] = ["*"]

    # Database settings
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "postgres"
    POSTGRES_PASSWORD: SecretStr = Field(default=SecretStr("postgres"))
    POSTGRES_DB: str = "hcc_extractor"
    POSTGRES_URI: Optional[PostgresDsn] = None

    # RabbitMQ settings
    RABBITMQ_HOST: str = "localhost"
    RABBITMQ_PORT: int = 5672
    RABBITMQ_USER: str = "guest"
    RABBITMQ_PASSWORD: SecretStr = Field(default=SecretStr("guest"))
    RABBITMQ_QUEUE: str = "document-events"
    RABBITMQ_EXCHANGE: str = "hcc-extractor"

    # Storage settings
    STORAGE_TYPE: str = "local"  # "local", "s3", or "gcs"
    LOCAL_STORAGE_PATH: Path = Path("./data")
    S3_BUCKET: Optional[str] = None
    S3_REGION: Optional[str] = None
    GCS_BUCKET: Optional[str] = None
    GCS_PROJECT_ID: Optional[str] = None

    # Vertex AI settings
    VERTEX_AI_PROJECT_ID: Optional[str] = None
    VERTEX_AI_LOCATION: str = "us-central1"

    # Telemetry settings
    TELEMETRY_ENABLED: bool = False
    SENTRY_DSN: Optional[str] = None

    # Rate limiting settings
    RATE_LIMIT_PER_MINUTE: int = 60

    @field_validator("POSTGRES_URI", mode="before")
    def assemble_postgres_uri(cls, v: Optional[str], info: Dict[str, Any]) -> Any:
        """
        Assemble PostgreSQL URI from individual components.

        Args:
            v: The value to validate
            info: Validation context information

        Returns:
            Assembled PostgreSQL URI
        """
        if isinstance(v, str):
            return v

        data = info.data
        password = data.get("POSTGRES_PASSWORD")
        if isinstance(password, SecretStr):
            password = password.get_secret_value()

        return PostgresDsn.build(
            scheme="postgresql+asyncpg",
            username=data.get("POSTGRES_USER"),
            password=password,
            host=data.get("POSTGRES_HOST"),
            port=data.get("POSTGRES_PORT"),
            path=f"/{data.get('POSTGRES_DB') or ''}",
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        use_enum_values=True,
        extra="ignore",
    )


# Create global settings instance
settings = Settings()