"""
Document processor for extracting medical conditions from clinical documents.
"""

from app.extraction.utils import extract_assessment_plan, extract_conditions_rule_based
from app.models.document import (
    ClinicalDocument,
    ExtractionResult,
)


class DocumentProcessor:
    """Processor for extracting conditions from clinical documents."""

    def __init__(self, use_langgraph: bool = True) -> None:
        """
        Initialize the document processor.

        Args:
            use_langgraph: Whether to use the LangGraph pipeline (if False, only rule-based)
        """
        self.use_langgraph = use_langgraph
        self._pipeline = None

    @property
    def pipeline(self):
        """Lazy-load the pipeline to avoid circular imports."""
        if self._pipeline is None and self.use_langgraph:
            from app.graph.pipeline import ExtractionPipeline
            self._pipeline = ExtractionPipeline()
        return self._pipeline

    def process(self, document: ClinicalDocument) -> ExtractionResult:
        """
        Process a clinical document to extract conditions.

        Args:
            document: The clinical document to process

        Returns:
            Extraction result containing the extracted conditions
        """
        if self.use_langgraph:
            # Use the LangGraph pipeline for extraction
            return self.pipeline.process(document)
        else:
            # Use only the rule-based extraction as fallback
            return self._process_rule_based(document)

    def _process_rule_based(self, document: ClinicalDocument) -> ExtractionResult:
        """
        Process a document using only rule-based extraction.

        Args:
            document: The clinical document to process

        Returns:
            Extraction result with rule-based extraction
        """
        # Extract the Assessment/Plan section
        assessment_plan = extract_assessment_plan(document.content)
        if not assessment_plan:
            return ExtractionResult(
                document_id=document.document_id,
                conditions=[],
                metadata={
                    "error": "Assessment/Plan section not found in document"
                }
            )

        # Extract conditions from the Assessment/Plan section
        conditions = extract_conditions_rule_based(assessment_plan)

        return ExtractionResult(
            document_id=document.document_id,
            conditions=conditions,
            metadata={
                "source": document.source,
                "total_conditions": len(conditions),
                "extraction_method": "rule_based"
            }
        )
