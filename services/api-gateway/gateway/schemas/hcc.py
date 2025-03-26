"""
HCC schemas for the API Gateway.

This module defines Pydantic models for HCC-related operations.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class HCCCodeBase(BaseModel):
    """Base schema for HCC code operations."""
    code: str = Field(..., description="ICD-10 diagnosis code")
    description: str = Field(..., description="Description of the diagnosis code")
    category: Optional[str] = Field(..., description="HCC category of the code")
    risk_score: float = Field(..., description="Risk adjustment score for the code")


class HCCCodeRead(HCCCodeBase):
    """Schema for HCC code read operations with additional details."""
    related_codes: List[str] = Field(..., description="Related ICD-10 codes")
    documentation_requirements: str = Field(..., description="Documentation requirements for the code")
    common_errors: str = Field(..., description="Common errors when coding this condition")


class HCCCodeList(BaseModel):
    """Schema for list of HCC codes."""
    items: List[HCCCodeBase] = Field(..., description="List of HCC codes")
    total: int = Field(..., description="Total number of HCC codes")
    skip: int = Field(..., description="Number of HCC codes skipped")
    limit: int = Field(..., description="Maximum number of HCC codes returned")


class HCCCategory(BaseModel):
    """Schema for HCC categories."""
    id: str = Field(..., description="HCC category identifier")
    name: str = Field(..., description="Name of the HCC category")
    description: str = Field(..., description="Description of the HCC category")
    avg_risk_score: float = Field(..., description="Average risk score for codes in this category")
    code_count: int = Field(..., description="Number of codes in this category")


class HCCRelevanceResult(BaseModel):
    """Schema for HCC relevance check results."""
    is_relevant: bool = Field(..., description="Whether the code is HCC-relevant")
    code: Optional[str] = Field(None, description="ICD-10 code if found")
    category: Optional[str] = Field(None, description="HCC category if relevant")
    confidence: float = Field(..., description="Confidence score for the determination")
    alternatives: List[str] = Field(default_factory=list, description="Alternative codes to consider")
    explanation: str = Field(..., description="Explanation of the determination")


class HCCCodeRequest(BaseModel):
    """Schema for HCC code relevance check requests."""
    diagnosis_code: Optional[str] = Field(None, description="ICD-10 diagnosis code")
    diagnosis_text: Optional[str] = Field(None, description="Text description of the diagnosis")

    class Config:
        """Pydantic model configuration."""
        json_schema_extra = {
            "example": {
                "diagnosis_code": "E11.9",
                "diagnosis_text": "Type 2 diabetes mellitus"
            }
        }
