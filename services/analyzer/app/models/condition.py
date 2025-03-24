"""
Data models for conditions and analysis results.

This module defines the core data structures used throughout the analysis
service, including representations of medical conditions, their HCC relevance,
and analysis results.
"""

from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field


class Condition(BaseModel):
    """Representation of a medical condition with HCC relevance information."""

    id: str = Field(..., description="Unique identifier for the condition")
    name: str = Field(..., description="Name of the condition")
    icd_code: Optional[str] = Field(None, description="ICD-10 code for the condition")
    icd_description: Optional[str] = Field(
        None, description="Description associated with the ICD code"
    )
    details: Optional[str] = Field(None, description="Additional details about the condition")

    # HCC relevance information
    hcc_relevant: bool = Field(
        False, description="Whether the condition is HCC-relevant"
    )
    hcc_code: Optional[str] = Field(
        None, description="HCC code if the condition is HCC-relevant"
    )
    hcc_category: Optional[str] = Field(
        None, description="HCC category if the condition is HCC-relevant"
    )
    confidence: float = Field(
        0.0, description="Confidence score for the HCC relevance determination (0.0 to 1.0)"
    )
    reasoning: Optional[str] = Field(
        None, description="Reasoning behind the HCC relevance determination"
    )

    # Additional metadata
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the condition"
    )


class AnalysisResult(BaseModel):
    """Result of analyzing conditions for HCC relevance."""

    document_id: str = Field(..., description="Identifier of the source document")
    conditions: List[Condition] = Field(
        ..., description="Analyzed conditions with HCC relevance determinations"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the analysis process"
    )
    errors: List[str] = Field(
        default_factory=list, description="Errors encountered during analysis"
    )


class ProcessingStatus(BaseModel):
    """Status of processing a set of extracted conditions."""

    document_id: str = Field(..., description="Identifier of the source document")
    status: str = Field(..., description="Processing status (success/warning/error)")
    message: str = Field(..., description="Status message")
    output_file: Optional[str] = Field(
        None, description="Path to the output file if successful"
    )
