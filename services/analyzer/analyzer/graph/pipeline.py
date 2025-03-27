"""
LangGraph-based pipeline for HCC relevance analysis.

This module implements a workflow for analyzing medical conditions
and determining their HCC relevance using a multi-stage approach
combining rule-based and LLM-based methods.
"""
import os
from pathlib import Path
from typing import Dict, List, Any, Union

import pandas as pd
from langgraph.graph import StateGraph, END

from analyzer.graph.nodes import (
    load_hcc_codes,
    prepare_conditions,
    determine_hcc_relevance,
    enrichment_with_llm,
    finalize_analysis,
)
from analyzer.graph.state import GraphState
from analyzer.models.condition import Condition, AnalysisResult


class AnalysisPipeline:
    """LangGraph-based pipeline for HCC relevance analysis."""

    def __init__(self, hcc_codes_path: Union[str, Path]) -> None:
        """
        Initialize the analysis pipeline.

        Args:
            hcc_codes_path: Path to the CSV file containing HCC codes
        """
        self.hcc_codes_path = Path(hcc_codes_path)
        self.hcc_codes = self._load_hcc_codes()
        self.graph = self._build_graph()

    def _load_hcc_codes(self) -> List[Dict[str, Any]]:
        """
        Load HCC codes from CSV file.

        Returns:
            List of HCC codes as dictionaries
        """
        try:
            # Load HCC codes from CSV
            df = pd.read_csv(self.hcc_codes_path)

            # Convert to list of dictionaries
            hcc_codes = df.to_dict(orient="records")

            return hcc_codes
        except Exception as e:
            # Handle loading error
            raise RuntimeError(f"Failed to load HCC codes from {self.hcc_codes_path}: {str(e)}")

    def _build_graph(self) -> StateGraph:
        """
        Build the LangGraph workflow.

        Returns:
            Compiled workflow graph
        """
        # Create a new graph
        builder = StateGraph(GraphState)

        # Add nodes
        builder.add_node("load_hcc_codes", load_hcc_codes)
        builder.add_node("prepare_conditions", prepare_conditions)
        builder.add_node("determine_hcc_relevance", determine_hcc_relevance)
        builder.add_node("enrichment_with_llm", enrichment_with_llm)
        builder.add_node("finalize_analysis", finalize_analysis)

        # Define edges
        builder.add_edge("load_hcc_codes", "prepare_conditions")
        builder.add_edge("prepare_conditions", "determine_hcc_relevance")
        builder.add_edge("determine_hcc_relevance", "enrichment_with_llm")
        builder.add_edge("enrichment_with_llm", "finalize_analysis")
        builder.add_edge("finalize_analysis", END)

        # Set the entry point
        builder.set_entry_point("load_hcc_codes")

        # Compile the graph
        return builder.compile()

    def process(self, document_id: str, conditions: List[Condition]) -> AnalysisResult:
        """
        Process conditions using the workflow to determine HCC relevance.

        Args:
            document_id: ID of the document containing the conditions
            conditions: List of conditions to analyze

        Returns:
            Analysis result with HCC relevance determinations
        """
        # Initialize the state
        initial_state: GraphState = {
            "document_id": document_id,
            "conditions": conditions,
            "hcc_codes": self.hcc_codes,
            "analyzed_conditions": [],
            "errors": [],
            "metadata": {},
        }

        # Execute the workflow
        result = self.graph.invoke(initial_state)

        # Create analysis result
        analysis_result = AnalysisResult(
            document_id=document_id,
            conditions=result["analyzed_conditions"],
            metadata=result["metadata"],
            errors=result["errors"],
        )

        return analysis_result


# Add this to the end of the file for easier development access
def get_analysis_graph():
    hcc_codes_path = os.environ.get("HCC_CODES_PATH", "../../data/HCC_relevant_codes.csv")
    pipeline = AnalysisPipeline(hcc_codes_path=hcc_codes_path)
    return pipeline.graph


# Expose directly for CLI discovery
analysis_graph = get_analysis_graph()
