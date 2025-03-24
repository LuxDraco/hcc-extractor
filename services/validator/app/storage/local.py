"""
Local storage manager for handling file operations on the local filesystem.
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Any, Union

from app.models.condition import ValidationResult


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

    def list_input_files(self) -> List[Path]:
        """
        List all JSON files in the input directory.

        Returns:
            List of paths to input files
        """
        # Find all JSON files in the input directory
        return [
            f for f in self.input_dir.glob("*")
            if f.is_file() and f.suffix.lower() == ".json"
        ]

    def read_json_file(self, path: Path) -> Dict[str, Any]:
        """
        Read a JSON file from the filesystem.

        Args:
            path: Path to the JSON file

        Returns:
            Content of the file as a dictionary
        """
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def save_result(self, result: ValidationResult, filename: str) -> Path:
        """
        Save validation result to the output directory.

        Args:
            result: Validation result to save
            filename: Name of the output file

        Returns:
            Path where the result was saved
        """
        output_path = self.output_dir / filename

        # Convert model to dict
        result_dict = result.model_dump()

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, indent=2)

        return output_path
