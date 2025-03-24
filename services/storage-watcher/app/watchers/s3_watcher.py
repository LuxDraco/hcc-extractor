"""
S3 storage watcher for monitoring Amazon S3 buckets.

This module provides functionality to watch Amazon S3 buckets
for file changes and generate events when new files are detected.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

import boto3
from botocore.exceptions import ClientError

from app.watchers.base_watcher import BaseStorageWatcher

logger = logging.getLogger(__name__)


class S3StorageWatcher(BaseStorageWatcher):
    """Watcher for Amazon S3 buckets."""

    def __init__(
        self,
        watch_path: str,
        file_patterns: List[str],
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_region: Optional[str] = None,
    ) -> None:
        """
        Initialize the S3 storage watcher.

        Args:
            watch_path: S3 URI (s3://bucket-name/prefix) to monitor
            file_patterns: List of file patterns to watch (e.g., '*.txt', '*.pdf')
            aws_access_key_id: AWS access key ID (optional, can use environment variables)
            aws_secret_access_key: AWS secret access key (optional, can use environment variables)
            aws_region: AWS region (optional, defaults to us-east-1)
        """
        super().__init__(watch_path, file_patterns)

        # Parse S3 URI
        self.bucket_name, self.prefix = self._parse_s3_uri(watch_path)

        # Initialize S3 client
        self.s3_client = boto3.client(
            "s3",
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key,
            region_name=aws_region or "us-east-1",
        )

    def _parse_s3_uri(self, uri: str) -> Tuple[str, str]:
        """
        Parse an S3 URI into bucket name and prefix.

        Args:
            uri: S3 URI in the format s3://bucket-name/prefix

        Returns:
            Tuple of (bucket_name, prefix)

        Raises:
            ValueError: If the URI format is invalid
        """
        s3_uri_pattern = r"^s3://([^/]+)/?(.*)$"
        match = re.match(s3_uri_pattern, uri)

        if not match:
            raise ValueError(
                f"Invalid S3 URI: {uri}. Expected format: s3://bucket-name/prefix"
            )

        bucket_name = match.group(1)
        prefix = match.group(2)

        return bucket_name, prefix

    async def list_files(self) -> List[Dict[str, Any]]:
        """
        List files in the watched S3 bucket and prefix.

        Returns:
            List of file information dictionaries
        """
        files = []

        try:
            # Use paginator to handle large buckets
            paginator = self.s3_client.get_paginator("list_objects_v2")
            page_iterator = paginator.paginate(
                Bucket=self.bucket_name, Prefix=self.prefix
            )

            for page in page_iterator:
                if "Contents" not in page:
                    continue

                for obj in page["Contents"]:
                    # Skip directories (objects ending with '/')
                    key = obj["Key"]
                    if key.endswith("/"):
                        continue

                    # Extract just the filename for pattern matching
                    filename = key.split("/")[-1]
                    if not self._matches_pattern(filename):
                        continue

                    # Create file info
                    file_info = {
                        "path": f"s3://{self.bucket_name}/{key}",
                        "name": filename,
                        "timestamp": obj["LastModified"],
                        "size": obj["Size"],
                        "metadata": {
                            "etag": obj.get("ETag", "").strip('"'),
                            "storage_class": obj.get("StorageClass"),
                        },
                    }

                    files.append(file_info)

        except ClientError as e:
            logger.error(f"Error listing objects in S3: {str(e)}")

        return files