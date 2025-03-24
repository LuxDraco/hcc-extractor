"""
Google Cloud Storage watcher for monitoring GCS buckets.

This module provides functionality to watch Google Cloud Storage buckets
for file changes and generate events when new files are detected.
"""

import logging
import re
from datetime import datetime
from typing import Dict, List, Any, Optional, Tuple

from google.cloud import storage
from google.cloud.exceptions import NotFound

from app.watchers.base_watcher import BaseStorageWatcher

logger = logging.getLogger(__name__)


class GCSStorageWatcher(BaseStorageWatcher):
    """Watcher for Google Cloud Storage buckets."""

    def __init__(
        self,
        watch_path: str,
        file_patterns: List[str],
        credentials_path: Optional[str] = None,
        project_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the GCS storage watcher.

        Args:
            watch_path: GCS URI (gs://bucket-name/prefix) to monitor
            file_patterns: List of file patterns to watch (e.g., '*.txt', '*.pdf')
            credentials_path: Path to GCP service account credentials JSON (optional)
            project_id: GCP project ID (optional, can use default from credentials)
        """
        super().__init__(watch_path, file_patterns)

        # Parse GCS URI
        self.bucket_name, self.prefix = self._parse_gcs_uri(watch_path)

        # Initialize GCS client
        self.gcs_client = storage.Client.from_service_account_json(
            credentials_path
        ) if credentials_path else storage.Client(project=project_id)

        # Get bucket
        self.bucket = self.gcs_client.bucket(self.bucket_name)

    def _parse_gcs_uri(self, uri: str) -> Tuple[str, str]:
        """
        Parse a GCS URI into bucket name and prefix.

        Args:
            uri: GCS URI in the format gs://bucket-name/prefix

        Returns:
            Tuple of (bucket_name, prefix)

        Raises:
            ValueError: If the URI format is invalid
        """
        gcs_uri_pattern = r"^gs://([^/]+)/?(.*)$"
        match = re.match(gcs_uri_pattern, uri)

        if not match:
            raise ValueError(
                f"Invalid GCS URI: {uri}. Expected format: gs://bucket-name/prefix"
            )

        bucket_name = match.group(1)
        prefix = match.group(2)

        return bucket_name, prefix

    async def list_files(self) -> List[Dict[str, Any]]:
        """
        List files in the watched GCS bucket and prefix.

        Returns:
            List of file information dictionaries
        """
        files = []

        try:
            # List blobs with the specified prefix
            blobs = self.gcs_client.list_blobs(
                self.bucket_name, prefix=self.prefix
            )

            for blob in blobs:
                # Skip directories (objects ending with '/')
                if blob.name.endswith("/"):
                    continue

                # Extract just the filename for pattern matching
                filename = blob.name.split("/")[-1]
                if not self._matches_pattern(filename):
                    continue

                # Create file info
                file_info = {
                    "path": f"gs://{self.bucket_name}/{blob.name}",
                    "name": filename,
                    "timestamp": blob.updated,
                    "size": blob.size,
                    "metadata": {
                        "content_type": blob.content_type,
                        "md5_hash": blob.md5_hash,
                        "generation": blob.generation,
                        "metageneration": blob.metageneration,
                    },
                }

                files.append(file_info)

        except NotFound:
            logger.error(f"Bucket or prefix not found: {self.bucket_name}/{self.prefix}")
        except Exception as e:
            logger.error(f"Error listing objects in GCS: {str(e)}")

        return files