import enum


class ProcessingStatus(str, enum.Enum):
    """Enum for document processing status."""
    PENDING = "PENDING"
    EXTRACTING = "EXTRACTING"
    ANALYZING = "ANALYZING"
    VALIDATING = "VALIDATING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
