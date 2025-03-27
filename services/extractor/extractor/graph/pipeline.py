"""
LangGraph-based pipeline for condition extraction.

This module implements a workflow for extracting medical conditions
from clinical documents using LangChain with Vertex AI Gemini.
"""

from langgraph.graph import StateGraph, END

from extractor.graph.nodes import (
    GraphState,
    preprocess,
    extract_conditions,
    load_hcc_codes,
    determine_hcc_relevance,
    convert_to_model_objects,
    create_result,
)
from extractor.models.document import ClinicalDocument, ExtractionResult


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
        builder.add_node("extract_conditions", extract_conditions)
        builder.add_node("load_hcc_codes", load_hcc_codes)
        builder.add_node("determine_hcc_relevance", determine_hcc_relevance)
        builder.add_node("convert_to_model_objects", convert_to_model_objects)
        builder.add_node("create_result", create_result)

        # Define edges
        builder.add_edge("preprocess", "extract_conditions")
        builder.add_edge("extract_conditions", "load_hcc_codes")
        builder.add_edge("load_hcc_codes", "determine_hcc_relevance")
        builder.add_edge("determine_hcc_relevance", "convert_to_model_objects")
        builder.add_edge("convert_to_model_objects", "create_result")
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
            "conditions_extracted": [],
            "final_conditions": [],
            "hcc_codes": [],
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