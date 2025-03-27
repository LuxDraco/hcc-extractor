"""
Data models for messages passed between services.

This module defines the message structures used for communication
between the extractor and analyzer services.
"""

from typing import Dict, List, Any

from pydantic import BaseModel, Field

from analyzer.models.condition import Condition


class ExtractionMessage(BaseModel):
    """Message containing extraction results to be analyzed."""

    document_id: str = Field(..., description="Identifier of the source document")
    source: str = Field(..., description="Source of the document (e.g., filename)")
    conditions: List[Condition] = Field(
        ..., description="Conditions extracted from the document"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the extraction"
    )


class AnalysisMessage(BaseModel):
    """Message containing analysis results."""

    document_id: str = Field(..., description="Identifier of the source document")
    conditions: List[Condition] = Field(
        ..., description="Analyzed conditions with HCC relevance determinations"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata about the analysis"
    )
    errors: List[str] = Field(
        default_factory=list, description="Errors encountered during analysis"
    )
