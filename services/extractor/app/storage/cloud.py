"""
Cloud storage manager for handling file operations in cloud storage.

This module provides functionality to read from and write to
various cloud storage providers (GCS, S3, Azure Blob).
"""

import json
import os
from typing import List, Optional, Dict, Any

from google.cloud import storage

from app.models.document import ExtractionResult


class CloudStorageManager:
    """Storage manager for cloud storage operations."""

    def __init__(
            self,
            input_bucket: str,
            output_bucket: str,
            credentials_path: Optional[str] = None,
            project_id: Optional[str] = None,
    ) -> None:
        """
        Initialize the cloud storage manager.

        Args:
            input_bucket: Name of the bucket containing input files
            output_bucket: Name of the bucket where output files will be stored
            credentials_path: Path to GCP credentials JSON file (optional)
            project_id: GCP project ID (optional)
        """
        self.input_bucket = input_bucket
        self.output_bucket = output_bucket

        # Set credentials explicitly if provided
        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = credentials_path

        # Initialize storage client
        self.client = storage.Client(project=project_id)

        # Get bucket objects
        self._input_bucket = self.client.bucket(input_bucket)
        self._output_bucket = self.client.bucket(output_bucket)

    def list_input_documents(self) -> List[Dict[str, Any]]:
        """
        List all documents in the input bucket.

        Returns:
            List of document metadata
        """
        blobs = list(self.client.list_blobs(self.input_bucket))

        return [
            {
                "name": blob.name,
                "size": blob.size,
                "updated": blob.updated,
                "content_type": blob.content_type,
            }
            for blob in blobs
            if not blob.name.endswith("/")  # Skip directories
        ]

    def read_document(self, blob_name: str) -> str:
        """
        Read a document from cloud storage.

        Args:
            blob_name: Name of the blob to read

        Returns:
            Content of the document as a string
        """
        blob = self._input_bucket.blob(blob_name)
        return blob.download_as_text()

    def save_result(self, result: ExtractionResult, filename: str) -> str:
        """
        Save extraction result to the output bucket.

        Args:
            result: Extraction result to save
            filename: Name of the output file

        Returns:
            URI of the saved blob
        """
        # Convert model to dict
        result_dict = result.dict()

        # Create JSON string
        json_data = json.dumps(result_dict, indent=2)

        # Upload to cloud storage
        blob = self._output_bucket.blob(filename)
        blob.upload_from_string(json_data, content_type="application/json")

        return f"gs://{self.output_bucket}/{filename}"