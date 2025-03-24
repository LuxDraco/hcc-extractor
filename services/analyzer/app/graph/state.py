"""
State definitions for the LangGraph analysis workflow.

This module defines the state schema and validation functions
for the HCC analysis workflow graph.
"""

from typing import Dict, List, Any, TypedDict

from app.models.condition import Condition


class GraphState(TypedDict):
    """Type definition for the state passed between nodes in the graph."""

    document_id: str
    conditions: List[Condition]
    hcc_codes: List[Dict[str, Any]]
    analyzed_conditions: List[Condition]
    errors: List[str]
    metadata: Dict[str, Any]
