"""
Code repository for accessing and querying medical codes.

This module provides functionality to load, query, and validate
medical codes, particularly ICD-10 codes and their HCC relevance.
"""

from pathlib import Path
from typing import Optional, Union

import pandas as pd


class CodeRepository:
    """Repository for accessing and querying medical codes."""

    def __init__(self, hcc_codes_path: Union[str, Path]) -> None:
        """
        Initialize the code repository.

        Args:
            hcc_codes_path: Path to the CSV file containing HCC codes
        """
        self.hcc_codes_path = Path(hcc_codes_path)
        self.hcc_codes_df = self._load_hcc_codes()

        # Create dictionaries for fast lookup
        self._create_lookup_maps()

    def _load_hcc_codes(self) -> pd.DataFrame:
        """
        Load HCC codes from CSV file.

        Returns:
            DataFrame containing HCC codes
        """
        try:
            return pd.read_csv(self.hcc_codes_path)
        except Exception as e:
            raise RuntimeError(f"Failed to load HCC codes from {self.hcc_codes_path}: {str(e)}")

    def _create_lookup_maps(self) -> None:
        """Create lookup maps for efficient querying."""
        # Map from ICD code to row index
        self.icd_to_index = {
            code: idx for idx, code in enumerate(self.hcc_codes_df["ICD-10-CM Codes"])
        }

        # Map from ICD code to description
        self.icd_to_description = {
            code: desc for code, desc in zip(
                self.hcc_codes_df["ICD-10-CM Codes"],
                self.hcc_codes_df["Description"]
            )
        }

        # Map from ICD code to HCC category/tag
        self.icd_to_category = {
            code: tag for code, tag in zip(
                self.hcc_codes_df["ICD-10-CM Codes"],
                self.hcc_codes_df["Tags"]
            )
        }

    def is_valid_icd_code(self, icd_code: str) -> bool:
        """
        Check if an ICD-10 code is valid.

        Args:
            icd_code: ICD-10 code to check

        Returns:
            Whether the code is valid
        """
        if not icd_code:
            return False

        # Basic format validation
        if not (
                len(icd_code) >= 3 and
                icd_code[0].isalpha() and
                icd_code[1:].replace(".", "").isdigit()
        ):
            return False

        # Check if it's in our reference data
        return icd_code in self.icd_to_index

    def is_hcc_relevant(self, icd_code: str) -> bool:
        """
        Check if an ICD-10 code is HCC-relevant.

        Args:
            icd_code: ICD-10 code to check

        Returns:
            Whether the code is HCC-relevant
        """
        return icd_code in self.icd_to_index

    def get_hcc_category(self, icd_code: str) -> Optional[str]:
        """
        Get the HCC category for an ICD-10 code.

        Args:
            icd_code: ICD-10 code to query

        Returns:
            HCC category if the code is HCC-relevant, None otherwise
        """
        return self.icd_to_category.get(icd_code)

    def get_description(self, icd_code: str) -> Optional[str]:
        """
        Get the description for an ICD-10 code.

        Args:
            icd_code: ICD-10 code to query

        Returns:
            Description of the code if it exists, None otherwise
        """
        return self.icd_to_description.get(icd_code)

    def verify_code_description(self, icd_code: str, description: Optional[str]) -> bool:
        """
        Verify that an ICD-10 code and description match.

        Args:
            icd_code: ICD-10 code to verify
            description: Description to verify

        Returns:
            Whether the code and description match
        """
        if not icd_code or not description:
            return True  # Skip validation if either is missing

        reference_description = self.get_description(icd_code)
        if not reference_description:
            return False  # Unknown code

        # Check if the descriptions match (case-insensitive)
        return reference_description.lower() == description.lower()
