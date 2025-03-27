"""
Document processor for extracting medical conditions from clinical documents.
"""

from typing import List, Dict, Any

from extractor.llm.client import LangChainGeminiClient
from extractor.models.document import (
    ClinicalDocument,
    Condition,
    ExtractionResult,
)


class DocumentProcessor:
    """Processor for extracting conditions from clinical documents."""

    def __init__(self, use_langgraph: bool = True) -> None:
        """
        Initialize the document processor.

        Args:
            use_langgraph: Whether to use the LangGraph pipeline (if False, only use direct LLM)
        """
        self.use_langgraph = use_langgraph
        self._pipeline = None
        self.llm_client = LangChainGeminiClient()

    @property
    def pipeline(self):
        """Lazy-load the pipeline to avoid circular imports."""
        if self._pipeline is None and self.use_langgraph:
            from extractor.graph.pipeline import ExtractionPipeline
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
            # Use direct LLM extraction as fallback
            return self._process_with_llm(document)

    def _process_with_llm(self, document: ClinicalDocument) -> ExtractionResult:
        """
        Process a document using direct LLM extraction without the full graph.

        Args:
            document: The clinical document to process

        Returns:
            Extraction result with LLM-based extraction
        """
        # Extract conditions using LLM
        raw_conditions = self.llm_client.extract_conditions(document.content)

        # Convert to Condition objects
        conditions = self._convert_to_condition_objects(raw_conditions)

        return ExtractionResult(
            document_id=document.document_id,
            conditions=conditions,
            metadata={
                "source": document.source,
                "total_conditions": len(conditions),
                "extraction_method": "llm_direct"
            }
        )

    def _convert_to_condition_objects(self, raw_conditions: List[Dict[str, Any]]) -> List[Condition]:
        """
        Convert raw condition dictionaries to Condition objects.

        Args:
            raw_conditions: List of condition dictionaries from LLM

        Returns:
            List of Condition objects
        """
        conditions = []

        for idx, cond_data in enumerate(raw_conditions):
            condition = Condition(
                id=cond_data.get("id", f"llm-cond-{idx + 1}"),
                name=cond_data.get("name", ""),
                icd_code=cond_data.get("icd_code"),
                icd_description=cond_data.get("icd_description"),
                details=cond_data.get("details"),
                confidence=cond_data.get("confidence", 0.9),
                metadata={
                    "extraction_method": "llm",
                    "status": cond_data.get("status"),
                    "icd_code_no_dot": cond_data.get("icd_code_no_dot"),
                    "is_hcc_relevant": cond_data.get("is_hcc_relevant", False)
                }
            )
            conditions.append(condition)

        return conditions