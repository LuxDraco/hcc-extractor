"""
Utility functions for handling HCC-relevant codes.
"""

import csv
import os
from pathlib import Path
from typing import List, Dict, Any, Set, Optional

import pandas as pd


class HCCCodeManager:
    """Manager for HCC-relevant codes."""

    def __init__(self, csv_path: Optional[str] = None) -> None:
        """
        Initialize the HCC code manager.

        Args:
            csv_path: Path to the CSV file with HCC codes
        """
        self.csv_path = csv_path or os.environ.get(
            "HCC_CODES_PATH", "./data/HCC_relevant_codes.csv"
        )
        self._hcc_codes: Set[str] = set()
        self._hcc_code_lookup: Dict[str, Dict[str, Any]] = {}
        self._loaded = False

    def load_hcc_codes(self) -> None:
        """Load HCC codes from the CSV file."""
        if self._loaded:
            return

        path = Path(self.csv_path)
        if not path.exists():
            raise FileNotFoundError(f"HCC codes file not found: {self.csv_path}")

        try:
            # Use pandas for robust CSV handling
            df = pd.read_csv(path)

            # Process each code
            for _, row in df.iterrows():
                code = row["ICD-10-CM Codes"].strip()
                # Store the code without the dot for matching
                code_no_dot = code.replace(".", "")

                self._hcc_codes.add(code_no_dot)
                self._hcc_code_lookup[code_no_dot] = {
                    "code": code,
                    "description": row.get("Description", ""),
                    "tags": row.get("Tags", ""),
                }

            self._loaded = True
        except Exception as e:
            raise RuntimeError(f"Failed to load HCC codes: {e}")

    def is_hcc_relevant(self, code: Optional[str]) -> bool:
        """
        Check if a code is HCC-relevant.

        Args:
            code: ICD-10 code (with or without dot)

        Returns:
            Whether the code is HCC-relevant
        """
        if not self._loaded:
            self.load_hcc_codes()

        # Handle None or empty string
        if not code:
            return False

        # Normalize the code by removing the dot
        code_no_dot = code.replace(".", "")
        return code_no_dot in self._hcc_codes

    def get_code_info(self, code: str) -> Dict[str, Any]:
        """
        Get information about an HCC code.

        Args:
            code: ICD-10 code (with or without dot)

        Returns:
            Dictionary with code information
        """
        if not self._loaded:
            self.load_hcc_codes()

        # Handle None or empty string
        if not code:
            return {}

        # Normalize the code by removing the dot
        code_no_dot = code.replace(".", "")
        return self._hcc_code_lookup.get(code_no_dot, {})

    def get_all_hcc_codes(self) -> List[str]:
        """
        Get all HCC-relevant codes.

        Returns:
            List of HCC-relevant codes (without dots)
        """
        if not self._loaded:
            self.load_hcc_codes()

        return list(self._hcc_codes)


# Create a singleton instance
hcc_manager = HCCCodeManager()


def load_hcc_codes_from_csv(csv_path: str) -> List[str]:
    """
    Load HCC-relevant codes from a CSV file.

    Args:
        csv_path: Path to the CSV file

    Returns:
        List of HCC-relevant codes (without dots)
    """
    codes = []

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                code = row["ICD-10-CM Codes"].strip()
                # Remove the dot for matching
                code_no_dot = code.replace(".", "")
                codes.append(code_no_dot)
    except Exception as e:
        print(f"Error loading HCC codes: {e}")

    return codes