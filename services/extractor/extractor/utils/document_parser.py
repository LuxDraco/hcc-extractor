"""
Document parser for converting raw clinical notes to structured format.

This module is responsible for parsing different formats of clinical
progress notes and converting them into a standardized structure.
"""

import re
from pathlib import Path
from typing import Dict, Any

from extractor.models.document import ClinicalDocument


class DocumentParser:
    """Parser for clinical documents."""

    def parse(self, content: str, source: str) -> ClinicalDocument:
        """
        Parse raw content into a structured clinical document.

        Args:
            content: Raw content of the clinical document
            source: Source identifier of the document

        Returns:
            Structured clinical document
        """
        # Extract patient information
        patient_info = self._extract_patient_info(self, content=content)

        # Extract metadata
        metadata = self._extract_metadata(self, content=content)

        # Create document ID from source
        document_id = self._generate_document_id(self, source=source)

        return ClinicalDocument(
            document_id=document_id,
            source=source,
            content=content,
            patient_info=patient_info,
            metadata=metadata
        )

    @staticmethod
    def _extract_patient_info(self, content: str) -> Dict[str, Any]:
        """Extract patient information from the document content."""
        patient_info: Dict[str, Any] = {
            "name": None,
            "id": None,
            "age": None,
            "gender": None,
            "dob": None
        }

        # Extract patient name
        name_pattern = re.compile(r"Name\s*(.*?)(?:\s*\(|ID#|$)")
        name_match = name_pattern.search(content)
        if name_match:
            patient_info["name"] = name_match.group(1).strip()

        # Extract age and gender
        age_gender_pattern = re.compile(r"\((\d+)yo,\s*([MF])\)")
        age_gender_match = age_gender_pattern.search(content)
        if age_gender_match:
            patient_info["age"] = int(age_gender_match.group(1))
            patient_info["gender"] = "Male" if age_gender_match.group(2) == "M" else "Female"

        # Extract patient ID
        id_pattern = re.compile(r"ID#\s*(\d+)")
        id_match = id_pattern.search(content)
        if id_match:
            patient_info["id"] = id_match.group(1).strip()

        # Extract DOB
        dob_pattern = re.compile(r"DOB\s*(\d{2}/\d{2}/\d{4})")
        dob_match = dob_pattern.search(content)
        if dob_match:
            patient_info["dob"] = dob_match.group(1).strip()

        return patient_info

    @staticmethod
    def _extract_metadata(self, content: str) -> Dict[str, Any]:
        """Extract metadata from the document content."""
        metadata: Dict[str, Any] = {
            "provider": None,
            "appointment_date": None,
            "chief_complaint": None,
        }

        # Extract provider
        provider_pattern = re.compile(r"Provider\s*(.+)(?:\n|$)")
        provider_match = provider_pattern.search(content)
        if provider_match:
            metadata["provider"] = provider_match.group(1).strip()

        # Extract appointment date
        date_pattern = re.compile(r"Appt\.\s*Date/Time\s*(\d{2}/\d{2}/\d{4})")
        date_match = date_pattern.search(content)
        if date_match:
            metadata["appointment_date"] = date_match.group(1).strip()

        # Extract chief complaint
        cc_pattern = re.compile(r"Chief Complaint\s*\n(.*?)(?:\n\n|\n\w)", re.DOTALL)
        cc_match = cc_pattern.search(content)
        if cc_match:
            metadata["chief_complaint"] = cc_match.group(1).strip()

        return metadata

    @staticmethod
    def _generate_document_id(self, source: str) -> str:
        """Generate a document ID from the source."""
        # Use the filename without extension as the ID
        filename = Path(source).stem
        return f"doc-{filename}"
