"""
Storage service for the API Gateway.

This module provides functionality for storing and retrieving documents
from various storage backends (local, S3, GCS).
"""

import os
import time
import uuid
from pathlib import Path
from typing import Dict, Optional, Tuple, Union, Any

import aiofiles
import boto3
import structlog
from fastapi import Depends
from google.cloud import storage

from app.core.config import settings
from app.utils.metrics import STORAGE_OPERATIONS, STORAGE_OPERATION_TIME

logger = structlog.get_logger(__name__)


class StorageService:
    """Service for document storage operations."""

    def __init__(self):
        """Initialize the storage service."""
        self.storage_type = settings.STORAGE_TYPE

        # Set up storage backends
        if self.storage_type == "local":
            self.local_storage_path = settings.LOCAL_STORAGE_PATH
            os.makedirs(self.local_storage_path, exist_ok=True)

        elif self.storage_type == "s3":
            self.s3_client = boto3.client(
                "s3",
                region_name=settings.S3_REGION,
            )
            self.s3_bucket = settings.S3_BUCKET

        elif self.storage_type == "gcs":
            self.gcs_client = storage.Client(project=settings.GCS_PROJECT_ID)
            self.gcs_bucket = self.gcs_client.bucket(settings.GCS_BUCKET)

    async def store_document(
            self,
            content: bytes,
            filename: str,
            content_type: str,
    ) -> Dict[str, str]:
        """
        Store a document in the configured storage backend.

        Args:
            content: Document content
            filename: Document filename
            content_type: Document MIME type

        Returns:
            Dictionary with storage information
        """
        start_time = time.time()

        # Generate a unique path
        unique_id = str(uuid.uuid4())
        storage_path = f"{unique_id}/{filename}"

        # Store in the appropriate backend
        if self.storage_type == "local":
            await self._store_local(content, storage_path)

        elif self.storage_type == "s3":
            await self._store_s3(content, storage_path, content_type)

        elif self.storage_type == "gcs":
            await self._store_gcs(content, storage_path, content_type)

        # Record metrics
        duration = time.time() - start_time
        STORAGE_OPERATIONS.labels(operation="store", storage_type=self.storage_type).inc()
        STORAGE_OPERATION_TIME.labels(operation="store", storage_type=self.storage_type).observe(duration)

        logger.info(
            "Document stored",
            storage_type=self.storage_type,
            storage_path=storage_path,
            content_type=content_type,
            size=len(content),
        )

        return {
            "storage_type": self.storage_type,
            "storage_path": storage_path,
        }

    async def get_document(
            self, storage_type: str, storage_path: str
    ) -> Tuple[bytes, str, str]:
        """
        Get a document from storage.

        Args:
            storage_type: Storage type (local, s3, gcs)
            storage_path: Path to the document in storage

        Returns:
            Tuple of (content, filename, content_type)

        Raises:
            Exception: If the document cannot be retrieved
        """
        start_time = time.time()

        # Extract filename from path
        filename = storage_path.split("/")[-1]

        # Get from the appropriate backend
        if storage_type == "local":
            content, content_type = await self._get_local(storage_path)

        elif storage_type == "s3":
            content, content_type = await self._get_s3(storage_path)

        elif storage_type == "gcs":
            content, content_type = await self._get_gcs(storage_path)

        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

        # Record metrics
        duration = time.time() - start_time
        STORAGE_OPERATIONS.labels(operation="get", storage_type=storage_type).inc()
        STORAGE_OPERATION_TIME.labels(operation="get", storage_type=storage_type).observe(duration)

        logger.info(
            "Document retrieved",
            storage_type=storage_type,
            storage_path=storage_path,
            content_type=content_type,
            size=len(content),
        )

        return content, filename, content_type

    async def delete_document(self, storage_type: str, storage_path: str) -> bool:
        """
        Delete a document from storage.

        Args:
            storage_type: Storage type (local, s3, gcs)
            storage_path: Path to the document in storage

        Returns:
            Whether the document was deleted successfully

        Raises:
            Exception: If the document cannot be deleted
        """
        start_time = time.time()

        # Delete from the appropriate backend
        if storage_type == "local":
            success = await self._delete_local(storage_path)

        elif storage_type == "s3":
            success = await self._delete_s3(storage_path)

        elif storage_type == "gcs":
            success = await self._delete_gcs(storage_path)

        else:
            raise ValueError(f"Unsupported storage type: {storage_type}")

        # Record metrics
        duration = time.time() - start_time
        STORAGE_OPERATIONS.labels(operation="delete", storage_type=storage_type).inc()
        STORAGE_OPERATION_TIME.labels(operation="delete", storage_type=storage_type).observe(duration)

        logger.info(
            "Document deleted",
            storage_type=storage_type,
            storage_path=storage_path,
            success=success,
        )

        return success

    async def _store_local(self, content: bytes, storage_path: str) -> None:
        """
        Store a document in local storage.

        Args:
            content: Document content
            storage_path: Path to store the document
        """
        # Create directory if it doesn't exist
        full_path = self.local_storage_path / storage_path
        os.makedirs(full_path.parent, exist_ok=True)

        # Write file
        async with aiofiles.open(full_path, "wb") as f:
            await f.write(content)

    async def _get_local(self, storage_path: str) -> Tuple[bytes, str]:
        """
        Get a document from local storage.

        Args:
            storage_path: Path to the document

        Returns:
            Tuple of (content, content_type)

        Raises:
            FileNotFoundError: If the document is not found
        """
        full_path = self.local_storage_path / storage_path

        if not full_path.exists():
            raise FileNotFoundError(f"Document not found: {storage_path}")

        # Read file
        async with aiofiles.open(full_path, "rb") as f:
            content = await f.read()

        # Guess content type
        content_type = self._guess_content_type(storage_path)

        return content, content_type

    async def _delete_local(self, storage_path: str) -> bool:
        """
        Delete a document from local storage.

        Args:
            storage_path: Path to the document

        Returns:
            Whether the document was deleted successfully
        """
        full_path = self.local_storage_path / storage_path

        if not full_path.exists():
            return False

        # Delete file
        os.remove(full_path)

        return True

    async def _store_s3(
            self, content: bytes, storage_path: str, content_type: str
    ) -> None:
        """
        Store a document in S3.

        Args:
            content: Document content
            storage_path: Path to store the document
            content_type: Document MIME type
        """
        import aioboto3

        session = aioboto3.Session()
        async with session.client("s3", region_name=settings.S3_REGION) as s3:
            await s3.put_object(
                Bucket=self.s3_bucket,
                Key=storage_path,
                Body=content,
                ContentType=content_type,
            )

    async def _get_s3(self, storage_path: str) -> Tuple[bytes, str]:
        """
        Get a document from S3.

        Args:
            storage_path: Path to the document

        Returns:
            Tuple of (content, content_type)

        Raises:
            Exception: If the document cannot be retrieved
        """
        import aioboto3

        session = aioboto3.Session()
        async with session.client("s3", region_name=settings.S3_REGION) as s3:
            try:
                response = await s3.get_object(
                    Bucket=self.s3_bucket,
                    Key=storage_path,
                )

                content = await response["Body"].read()
                content_type = response.get("ContentType", self._guess_content_type(storage_path))

                return content, content_type

            except Exception as e:
                logger.error(
                    "Error retrieving document from S3",
                    storage_path=storage_path,
                    error=str(e),
                )
                raise

    async def _delete_s3(self, storage_path: str) -> bool:
        """
        Delete a document from S3.

        Args:
            storage_path: Path to the document

        Returns:
            Whether the document was deleted successfully
        """
        import aioboto3

        session = aioboto3.Session()
        async with session.client("s3", region_name=settings.S3_REGION) as s3:
            try:
                await s3.delete_object(
                    Bucket=self.s3_bucket,
                    Key=storage_path,
                )

                return True

            except Exception as e:
                logger.error(
                    "Error deleting document from S3",
                    storage_path=storage_path,
                    error=str(e),
                )
                return False

    async def _store_gcs(
            self, content: bytes, storage_path: str, content_type: str
    ) -> None:
        """
        Store a document in GCS.

        Args:
            content: Document content
            storage_path: Path to store the document
            content_type: Document MIME type
        """
        import asyncio

        blob = self.gcs_bucket.blob(storage_path)

        # Run in a thread to avoid blocking
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(
            None,
            lambda: blob.upload_from_string(content, content_type=content_type)
        )

    async def _get_gcs(self, storage_path: str) -> Tuple[bytes, str]:
        """
        Get a document from GCS.

        Args:
            storage_path: Path to the document

        Returns:
            Tuple of (content, content_type)

        Raises:
            Exception: If the document cannot be retrieved
        """
        import asyncio

        blob = self.gcs_bucket.blob(storage_path)

        # Check if blob exists
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, blob.exists)

        if not exists:
            raise FileNotFoundError(f"Document not found: {storage_path}")

        # Download blob
        content = await loop.run_in_executor(None, blob.download_as_bytes)

        # Get content type
        content_type = blob.content_type
        if not content_type:
            content_type = self._guess_content_type(storage_path)

        return content, content_type

    async def _delete_gcs(self, storage_path: str) -> bool:
        """
        Delete a document from GCS.

        Args:
            storage_path: Path to the document

        Returns:
            Whether the document was deleted successfully
        """
        import asyncio

        blob = self.gcs_bucket.blob(storage_path)

        # Check if blob exists
        loop = asyncio.get_event_loop()
        exists = await loop.run_in_executor(None, blob.exists)

        if not exists:
            return False

        # Delete blob
        await loop.run_in_executor(None, blob.delete)

        return True

    def _guess_content_type(self, path: str) -> str:
        """
        Guess the MIME type of a file based on its extension.

        Args:
            path: File path

        Returns:
            Guessed MIME type
        """
        import mimetypes

        mime_type, _ = mimetypes.guess_type(path)
        return mime_type or "application/octet-stream"