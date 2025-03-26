"""
Local storage manager for handling file operations on the local filesystem.
"""

import os
import json
from pathlib import Path
from typing import List, Dict, Any, Union

from extractor.models.document import ExtractionResult


class LocalStorageManager:
    """Storage manager for local filesystem operations."""

    def __init__(
            self, input_dir: Union[str, Path], output_dir: Union[str, Path]
    ) -> None:
        """
        Initialize the local storage manager.

        Args:
            input_dir: Directory containing input files
            output_dir: Directory where output files will be stored
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)

        # Ensure directories exist
        os.makedirs(self.input_dir, exist_ok=True)
        os.makedirs(self.output_dir, exist_ok=True)

    def list_input_documents(self) -> List[Path]:
        """
        List all documents in the input directory.

        Returns:
            List of paths to input documents
        """
        # Find all text and PDF files in the input directory
        return [
            f for f in self.input_dir.glob("*")
            if f.is_file() and f.suffix.lower() in (".txt", ".pdf", "")
        ]

    def read_document(self, path: Path) -> str:
        """
        Read a document from the filesystem.

        Args:
            path: Path to the document

        Returns:
            Content of the document as a string
        """
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def save_result(self, result: ExtractionResult, filename: str) -> Path:
        """
        Save extraction result to the output directory.

        Args:
            result: Extraction result to save
            filename: Name of the output file

        Returns:
            Path where the result was saved
        """
        output_path = self.output_dir / filename

        # Convert model to dict
        result_dict = result.dict()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2)

        return output_path