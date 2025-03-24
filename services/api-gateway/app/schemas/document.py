"""
Document schemas for the API Gateway.

This module defines Pydantic models for document-related operations.
"""

import enum
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Any, Union

from pydantic import BaseModel, Field, HttpUrl


class StorageTypeEnum(str, enum.Enum):
    """Enum for document storage types."""
    LOCAL = "local"
    S3 = "s3"
    GCS = "gcs"


class ProcessingStatusEnum(str, enum.Enum):
    """Enum for document processing status."""
    PENDING = "pending"
    EXTRACTING = "extracting"
    ANALYZING = "analyzing"
    VALIDATING = "validating"
    COMPLETED = "completed"
    FAILED = "failed"


class DocumentBase(BaseModel):
    """Base schema for document operations."""
    filename: str = Field(..., description="Filename of the document")
    description: Optional[str] = Field(None, description="Optional description of the document")


class DocumentCreate(DocumentBase):
    """Schema for document creation."""
    file_size: int = Field(..., description="Size of the document in bytes")
    content_type: str = Field(..., description="MIME type of the document")
    storage_type: StorageTypeEnum = Field(..., description="Storage type of the document")
    storage_path: str = Field(..., description="Path to the document in storage")
    priority: bool = Field(False, description="Whether to prioritize processing the document")
    user_id: Optional[uuid.UUID] = Field(None, description="ID of the user who uploaded the document")


class DocumentUpdate(BaseModel):
    """Schema for document update."""
    description: Optional[str] = Field(None, description="Optional description of the document")
    status: Optional[ProcessingStatusEnum] = Field(None, description="Processing status of the document")
    is_processed: Optional[bool] = Field(None, description="Whether the document has been processed")
    total_conditions: Optional[int] = Field(None, description="Total number of conditions extracted")
    hcc_relevant_conditions: Optional[int] = Field(None, description="Number of HCC-relevant conditions")
    extraction_result_path: Optional[str] = Field(None, description="Path to extraction result")
    analysis_result_path: Optional[str] = Field(None, description="Path to analysis result")
    validation_result_path: Optional[str] = Field(None, description="Path to validation result")
    patient_info: Optional[Dict[str, Any]] = Field(None, description="Patient information extracted from document")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Additional metadata")


class DocumentRead(DocumentBase):
    """Schema for document read operations."""
    id: uuid.UUID = Field(..., description="ID of the document")
    file_size: int = Field(..., description="Size of the document in bytes")
    content_type: str = Field(..., description="MIME type of the document")
    storage_type: StorageTypeEnum = Field(..., description="Storage type of the document")
    status: ProcessingStatusEnum = Field(..., description="Processing status of the document")
    is_processed: bool = Field(..., description="Whether the document has been processed")
    created_at: datetime = Field(..., description="Timestamp when the document was created")
    updated_at: datetime = Field(..., description="Timestamp when the document was last updated")

    class Config:
        """Pydantic model configuration."""
        orm_mode = True
        from_attributes = True


class DocumentDetail(DocumentRead):
    """Schema for detailed document information."""
    processing_started_at: Optional[datetime] = Field(None, description="Timestamp when processing started")
    processing_completed_at: Optional[datetime] = Field(None, description="Timestamp when processing completed")
    total_conditions: Optional[int] = Field(None, description="Total number of conditions extracted")
    hcc_relevant_conditions: Optional[int] = Field(None, description="Number of HCC-relevant conditions")
    extraction_result_path: Optional[str] = Field(None, description="Path to extraction result")
    analysis_result_path: Optional[str] = Field(None, description="Path to analysis result")
    validation_result_path: Optional[str] = Field(None, description="Path to validation result")
    errors: Optional[str] = Field(None, description="Error messages if processing failed")
    patient_info: Optional[Dict[str, Any]] = Field(None, description="Patient information extracted from document")
    metadata: Dict[str, Any] = Field({}, description="Additional metadata")
    user_id: Optional[uuid.UUID] = Field(None, description="ID of the user who uploaded the document")


class DocumentList(BaseModel):
    """Schema for list of documents."""
    items: List[DocumentRead] = Field(..., description="List of documents")
    total: int = Field(..., description="Total number of documents")
    skip: int = Field(..., description="Number of documents skipped")
    limit: int = Field(..., description="Maximum number of documents returned")


class ConditionBase(BaseModel):
    """Base schema for condition information."""
    id: str = Field(..., description="ID of the condition")
    name: str = Field(..., description="Name of the condition")
    icd_code: Optional[str] = Field(None, description="ICD-10 code of the condition")
    icd_description: Optional[str] = Field(None, description="Description of the ICD-10 code")
    details: Optional[str] = Field(None, description="Additional details about the condition")
    hcc_relevant: bool = Field(False, description="Whether the condition is HCC-relevant")
    hcc_code: Optional[str] = Field(None, description="HCC code if the condition is HCC-relevant")
    hcc_category: Optional[str] = Field(None, description="HCC category if the condition is HCC-relevant")
    confidence: float = Field(0.0, description="Confidence score for the condition")


class ExtractionResult(BaseModel):
    """Schema for extraction result."""
    document_id: str = Field(..., description="ID of the document")
    conditions: List[ConditionBase] = Field(..., description="Extracted conditions")
    metadata: Dict[str, Any] = Field({}, description="Additional metadata")


class AnalysisResult(BaseModel):
    """Schema for analysis result."""
    document_id: str = Field(..., description="ID of the document")
    conditions: List[ConditionBase] = Field(..., description="Analyzed conditions")
    metadata: Dict[str, Any] = Field({}, description="Additional metadata")
    errors: List[str] = Field([], description="Errors encountered during analysis")


class ValidationResult(BaseModel):
    """Schema for validation result."""
    document_id: str = Field(..., description="ID of the document")
    conditions: List[ConditionBase] = Field(..., description="Validated conditions")
    metadata: Dict[str, Any] = Field({}, description="Additional metadata")