"""
LangGraph-based pipeline for condition extraction.

This module implements a workflow for extracting medical conditions
from clinical documents using a multi-stage approach combining
rule-based and LLM-based extraction methods.
"""

from typing import Dict, List, Any, Optional

from langgraph.graph import StateGraph, END

from app.models.document import ClinicalDocument, ExtractionResult
from app.graph.nodes import (
    GraphState,
    preprocess,
    extract_rule_based,
    extract_llm_based,
    merge_results,
    create_result,
)


class ExtractionPipeline:
    """LangGraph-based pipeline for condition extraction."""

    def __init__(self) -> None:
        """Initialize the extraction pipeline."""
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        Returns:
            Compiled workflow graph
        """
        # Create a new graph
        builder = StateGraph(GraphState)

        # Add nodes
        builder.add_node("preprocess", preprocess)
        builder.add_node("extract_rule_based", extract_rule_based)
        builder.add_node("extract_llm_based", extract_llm_based)
        builder.add_node("merge_results", merge_results)
        builder.add_node("create_result", create_result)

        # Define edges
        builder.add_edge("preprocess", "extract_rule_based")
        builder.add_edge("extract_rule_based", "extract_llm_based")
        builder.add_edge("extract_llm_based", "merge_results")
        builder.add_edge("merge_results", "create_result")
        builder.add_edge("create_result", END)

        # Set the entry point
        builder.set_entry_point("preprocess")

        # Compile the graph
        return builder.compile()

    def process(self, document: ClinicalDocument) -> ExtractionResult:
        """
        Process a clinical document using the workflow.

        Args:
            document: Clinical document to process

        Returns:
            Extraction result with conditions
        """
        # Initialize the state
        initial_state: GraphState = {
            "document": document,
            "assessment_plan": None,
            "conditions_rule_based": [],
            "conditions_llm_based": [],
            "final_conditions": [],
            "extraction_result": None,
        }

        # Execute the workflow
        result = self.graph.invoke(initial_state)

        # Return the final result
        if result["extraction_result"] is not None:
            return result["extraction_result"]

        # Fallback in case of failure
        return ExtractionResult(
            document_id=document.document_id,
            conditions=[],
            metadata={"error": "Pipeline execution failed"}
        )