"""
Nodes for the LangGraph extraction workflow.
"""

from typing import List, TypedDict, Optional

from app.extraction.utils import extract_assessment_plan, extract_conditions_rule_based
from app.llm.client import GeminiClient
from app.models.document import ClinicalDocument, Condition, ExtractionResult


class GraphState(TypedDict):
    """Type definition for the state passed between nodes in the graph."""

    document: ClinicalDocument
    assessment_plan: Optional[str]
    conditions_rule_based: List[Condition]
    conditions_llm_based: List[Condition]
    final_conditions: List[Condition]
    extraction_result: Optional[ExtractionResult]


def preprocess(state: GraphState) -> GraphState:
    """
    Preprocess the clinical document to prepare for extraction.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with extracted Assessment/Plan section
    """
    document = state["document"]
    content = document.content

    # Use the utility function
    assessment_plan = extract_assessment_plan(content)

    # Update state
    state["assessment_plan"] = assessment_plan

    return state


def extract_rule_based(state: GraphState) -> GraphState:
    """
    Extract conditions using rule-based approach.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with rule-based extraction results
    """
    document = state["document"]
    assessment_plan = state["assessment_plan"]

    if not assessment_plan:
        state["conditions_rule_based"] = []
        return state

    # Use the utility function directly instead of DocumentProcessor
    conditions = extract_conditions_rule_based(assessment_plan)

    # Update state
    state["conditions_rule_based"] = conditions

    return state


def extract_llm_based(state: GraphState) -> GraphState:
    """
    Extract conditions using LLM-based approach.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with LLM-based extraction results
    """
    document = state["document"]

    # Use Gemini for extraction
    client = GeminiClient()
    llm_conditions_data = client.extract_conditions(document.content)

    # Convert to Condition objects
    llm_conditions = []
    for idx, cond_data in enumerate(llm_conditions_data):
        condition = Condition(
            id=cond_data.get("id", f"llm-cond-{idx + 1}"),
            name=cond_data.get("name", ""),
            icd_code=cond_data.get("icd_code"),
            icd_description=cond_data.get("icd_description"),
            details=cond_data.get("details"),
            confidence=cond_data.get("confidence", 0.9),
            metadata={"source": "llm"}
        )
        llm_conditions.append(condition)

    # Update state
    state["conditions_llm_based"] = llm_conditions

    return state


def merge_results(state: GraphState) -> GraphState:
    """
    Merge and reconcile results from different extraction approaches.
    """
    # Este código permanece sin cambios ya que no contribuye al ciclo de importación
    rule_based = state["conditions_rule_based"]
    llm_based = state["conditions_llm_based"]

    # Create a map of rule-based conditions by name for easy lookup
    rule_based_map = {cond.name.lower(): cond for cond in rule_based}

    final_conditions = []

    # First, add all rule-based conditions to the final list
    for rule_cond in rule_based:
        rule_cond.metadata["extraction_method"] = "rule_based"
        final_conditions.append(rule_cond)

    # Then, add LLM-based conditions that weren't found by rules
    for llm_cond in llm_based:
        llm_name = llm_cond.name.lower()
        if llm_name not in rule_based_map:
            llm_cond.metadata["extraction_method"] = "llm_only"
            final_conditions.append(llm_cond)
        else:
            # For conditions found by both methods, we could update metadata
            # to indicate higher confidence, but we'll keep the rule-based one
            rule_cond = rule_based_map[llm_name]
            rule_cond.metadata["also_found_by_llm"] = True
            rule_cond.metadata["llm_confidence"] = llm_cond.confidence

    # Update state
    state["final_conditions"] = final_conditions

    return state


def create_result(state: GraphState) -> GraphState:
    """
    Create the final extraction result.
    """
    # Este código permanece sin cambios ya que no contribuye al ciclo de importación
    document = state["document"]
    conditions = state["final_conditions"]

    # Create extraction result
    result = ExtractionResult(
        document_id=document.document_id,
        conditions=conditions,
        metadata={
            "source": document.source,
            "total_conditions": len(conditions),
            "rule_based_count": len(state["conditions_rule_based"]),
            "llm_based_count": len(state["conditions_llm_based"]),
            "unique_to_rules": len([c for c in conditions if c.metadata.get("extraction_method") == "rule_based"]),
            "unique_to_llm": len([c for c in conditions if c.metadata.get("extraction_method") == "llm_only"]),
            "found_by_both": len([c for c in conditions if c.metadata.get("also_found_by_llm", False)]),
        }
    )

    # Update state
    state["extraction_result"] = result

    return state
