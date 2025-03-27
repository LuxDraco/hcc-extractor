"""
Data models for clinical documents and extraction results.

This module defines the core data structures used throughout the extraction
service, including representations of clinical documents, medical conditions,
and extraction results.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class Condition(BaseModel):
    """Representation of a medical condition extracted from a clinical document."""

    id: str = Field(..., description="Unique identifier for the condition")
    name: str = Field(..., description="Name of the condition")
    icd_code: Optional[str] = Field(None, description="ICD-10 code for the condition")
    icd_description: Optional[str] = Field(
        None, description="Description associated with the ICD code"
    )
    details: Optional[str] = Field(None, description="Additional details about the condition")
    confidence: float = Field(
        1.0, description="Confidence score for the extraction (0.0 to 1.0)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the condition"
    )

    @property
    def icd_code_no_dot(self) -> Optional[str]:
        """Get the ICD code without the dot."""
        if self.icd_code:
            return self.icd_code.replace(".", "")
        return None

    @property
    def is_hcc_relevant(self) -> bool:
        """Get whether this condition is HCC-relevant."""
        return self.metadata.get("is_hcc_relevant", False)

    @property
    def status(self) -> Optional[str]:
        """Get the status of the condition."""
        return self.metadata.get("status")


class ClinicalDocument(BaseModel):
    """Representation of a clinical document."""

    document_id: str = Field(..., description="Unique identifier for the document")
    source: str = Field(..., description="Source of the document (e.g., filename)")
    content: str = Field(..., description="Full content of the document")
    patient_info: Dict[str, Any] = Field(
        default_factory=dict, description="Patient information extracted from the document"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the document"
    )


class ExtractionResult(BaseModel):
    """Result of extracting conditions from a clinical document."""

    document_id: str = Field(..., description="Identifier of the source document")
    conditions: List[Condition] = Field(
        ..., description="Conditions extracted from the document"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the extraction process"
    )

    @property
    def total_conditions(self) -> int:
        """Get the total number of conditions."""
        return len(self.conditions)

    @property
    def hcc_relevant_conditions(self) -> List[Condition]:
        """Get only the HCC-relevant conditions."""
        return [c for c in self.conditions if c.is_hcc_relevant]

    @property
    def hcc_relevant_count(self) -> int:
        """Get the count of HCC-relevant conditions."""
        return len(self.hcc_relevant_conditions)


class ProcessingStatus(BaseModel):
    """Status of processing a clinical document."""

    document_id: str = Field(..., description="Identifier of the source document")
    status: str = Field(..., description="Processing status (success/error)")
    message: str = Field(..., description="Status message")
    output_file: Optional[str] = Field(
        None, description="Path to the output file if successful"
    )