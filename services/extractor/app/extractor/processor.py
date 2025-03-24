"""
Document processor for extracting medical conditions from clinical documents.

This module contains the core logic for analyzing the "Assessment/Plan" section
of clinical progress notes and extracting medical conditions with their ICD-10 codes.
"""

import re
from typing import Dict, List, Optional, Pattern, Match, Tuple

from app.models.document import (
    ClinicalDocument,
    Condition,
    ExtractionResult,
)
from app.graph.pipeline import ExtractionPipeline


class DocumentProcessor:
    """Processor for extracting conditions from clinical documents."""

    # Regex patterns for condition extraction
    CONDITION_PATTERN: Pattern = re.compile(
        r"(\d+\.)\s*(.*?)(?:\s*-\s*)(.*?)(?:\n|$)", re.MULTILINE
    )

    # Pattern to extract ICD-10 codes
    ICD_CODE_PATTERN: Pattern = re.compile(r"([A-Z]\d+\.\d+):\s*(.*?)(?:\n|$)")

    def __init__(self, use_langgraph: bool = True) -> None:
        """
        Initialize the document processor.

        Args:
            use_langgraph: Whether to use the LangGraph pipeline (if False, only rule-based)
        """
        self.use_langgraph = use_langgraph
        if use_langgraph:
            self.pipeline = ExtractionPipeline()

    def process(self, document: ClinicalDocument) -> ExtractionResult:
        """
        Process a clinical document to extract conditions.

        Args:
            document: The clinical document to process

        Returns:
            Extraction result containing the extracted conditions
        """
        if self.use_langgraph:
            # Use the LangGraph pipeline for extraction with both methods
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
        assessment_plan = self._extract_assessment_plan(document.content)
        if not assessment_plan:
            return ExtractionResult(
                document_id=document.document_id,
                conditions=[],
                metadata={
                    "error": "Assessment/Plan section not found in document"
                }
            )

        # Extract conditions from the Assessment/Plan section
        conditions = self._extract_conditions(assessment_plan)

        return ExtractionResult(
            document_id=document.document_id,
            conditions=conditions,
            metadata={
                "source": document.source,
                "total_conditions": len(conditions),
                "extraction_method": "rule_based"
            }
        )

    def _extract_assessment_plan(self, content: str) -> Optional[str]:
        """
        Extract the Assessment/Plan section from the clinical document.

        Args:
            content: The content of the clinical document

        Returns:
            The Assessment/Plan section if found, None otherwise
        """
        # Look for Assessment/Plan section
        # This pattern is based on the specific structure of the provided example
        assessment_pattern = re.compile(
            r"(?:Assessment\s*/?\s*Plan|Assessment and Plan)[\s\n]*(.*?)(?:\n\s*(?:Return to Office|Encounter Sign-Off|Follow-up|Plan of Care)|$)",
            re.DOTALL | re.IGNORECASE
        )

        match = assessment_pattern.search(content)
        if match:
            return match.group(1).strip()

        return None

    def _extract_conditions(self, assessment_plan: str) -> List[Condition]:
        """
        Extract conditions from the Assessment/Plan section.

        Args:
            assessment_plan: The Assessment/Plan section text

        Returns:
            List of extracted conditions
        """
        conditions: List[Condition] = []

        # Find all condition matches
        matches = self.CONDITION_PATTERN.finditer(assessment_plan)

        for match in matches:
            number = match.group(1).strip().rstrip('.')
            condition_name = match.group(2).strip()
            details = match.group(3).strip()

            # Extract ICD code if present
            icd_code = None
            icd_description = None

            icd_match = self.ICD_CODE_PATTERN.search(details)
            if icd_match:
                icd_code = icd_match.group(1).strip()
                icd_description = icd_match.group(2).strip()

            # Create condition object
            condition = Condition(
                id=f"cond-{number}",
                name=condition_name,
                icd_code=icd_code,
                icd_description=icd_description,
                details=details,
                confidence=1.0,  # Default confidence for regex extraction
                metadata={
                    "section_number": number,
                    "raw_text": match.group(0),
                    "extraction_method": "rule_based"
                }
            )

            conditions.append(condition)

        return conditions