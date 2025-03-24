"""
Nodes for the LangGraph analysis workflow.

This module defines the individual processing nodes used in the analysis
workflow graph, including HCC relevance determination and verification.
"""

from app.graph.state import GraphState
from app.llm.client import GeminiClient


def load_hcc_codes(state: GraphState) -> GraphState:
    """
    Load and prepare HCC codes for analysis.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with HCC codes
    """
    # HCC codes should already be in the state, validate and return
    if not state.get("hcc_codes"):
        state["errors"].append("HCC codes not found in state")

    return state


def prepare_conditions(state: GraphState) -> GraphState:
    """
    Prepare conditions for HCC relevance analysis.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with prepared conditions
    """
    # Initialize analyzed_conditions list if not present
    if "analyzed_conditions" not in state:
        state["analyzed_conditions"] = []

    # Get conditions from state
    conditions = state.get("conditions", [])

    # Check if there are conditions to analyze
    if not conditions:
        state["errors"].append("No conditions found to analyze")

    return state


def determine_hcc_relevance(state: GraphState) -> GraphState:
    """
    Determine HCC relevance using a rule-based approach first.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with HCC relevance determinations
    """
    conditions = state.get("conditions", [])
    hcc_codes = state.get("hcc_codes", [])

    # Create a dictionary for quick lookup of HCC-relevant codes
    hcc_code_dict = {code["ICD-10-CM Codes"]: code for code in hcc_codes}

    analyzed_conditions = []

    for condition in conditions:
        # Copy the condition to avoid modifying the original
        analyzed = condition.model_copy(deep=True)

        # Get the ICD code
        icd_code = condition.icd_code

        # Check if the ICD code is HCC-relevant
        if icd_code and icd_code in hcc_code_dict:
            # Mark as HCC-relevant
            hcc_info = hcc_code_dict[icd_code]
            analyzed.hcc_relevant = True
            analyzed.hcc_code = icd_code
            analyzed.hcc_category = hcc_info.get("Tags", "")
            analyzed.confidence = 1.0
            analyzed.reasoning = f"Direct match with HCC-relevant code: {icd_code}"
        else:
            # Not HCC-relevant based on exact match
            analyzed.hcc_relevant = False
            analyzed.hcc_code = None
            analyzed.hcc_category = None
            analyzed.confidence = 0.8  # High confidence but not 100% since we're checking exact matches only
            analyzed.reasoning = "No exact match with HCC-relevant codes in reference data"

        analyzed_conditions.append(analyzed)

    # Update state
    state["analyzed_conditions"] = analyzed_conditions

    return state


def enrichment_with_llm(state: GraphState) -> GraphState:
    """
    Enrich HCC analysis with LLM-based determinations.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with LLM-enriched HCC determinations
    """
    conditions = state.get("analyzed_conditions", [])
    hcc_codes = state.get("hcc_codes", [])

    # Skip if no conditions or all are already confidently determined
    confident_conditions = [c for c in conditions if c.confidence >= 0.9]
    if len(confident_conditions) == len(conditions):
        # All conditions already have high confidence
        return state

    # Initialize Gemini client
    client = GeminiClient()

    # Prepare conditions for LLM analysis
    conditions_for_llm = [c.model_dump() for c in conditions]

    # Sample HCC codes for the prompt (to avoid token limits)
    hcc_sample = hcc_codes[:50] if len(hcc_codes) > 50 else hcc_codes

    # Get LLM analysis
    try:
        llm_results = client.analyze_hcc_relevance(conditions_for_llm, hcc_sample)

        # Create a map of conditions by ID for easy lookup
        condition_map = {c.id: c for c in conditions}

        # Update conditions with LLM results
        for llm_result in llm_results:
            condition_id = llm_result.get("id")
            if condition_id in condition_map:
                condition = condition_map[condition_id]

                # Only update if LLM has higher confidence or rule-based was uncertain
                llm_confidence = llm_result.get("confidence", 0.0)
                if llm_confidence > condition.confidence:
                    condition.hcc_relevant = llm_result.get("hcc_relevant", condition.hcc_relevant)
                    condition.hcc_code = llm_result.get("hcc_code", condition.hcc_code)
                    condition.hcc_category = llm_result.get("hcc_category", condition.hcc_category)
                    condition.confidence = llm_confidence
                    condition.reasoning = llm_result.get("reasoning", condition.reasoning)
                    # Add metadata about source
                    condition.metadata["analysis_source"] = "llm"
                else:
                    # Keep the original values but add LLM perspective
                    condition.metadata["llm_hcc_relevant"] = llm_result.get("hcc_relevant")
                    condition.metadata["llm_confidence"] = llm_confidence
                    condition.metadata["llm_reasoning"] = llm_result.get("reasoning")
                    condition.metadata["analysis_source"] = "rule_based"

    except Exception as e:
        # Log error but continue with rule-based results
        state["errors"].append(f"LLM enrichment failed: {str(e)}")
        # Mark all conditions as rule-based since LLM failed
        for condition in conditions:
            condition.metadata["analysis_source"] = "rule_based"

    return state


def finalize_analysis(state: GraphState) -> GraphState:
    """
    Finalize the analysis results.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with finalized analysis
    """
    document_id = state.get("document_id", "unknown")
    conditions = state.get("analyzed_conditions", [])

    # Calculate statistics for metadata
    total_conditions = len(conditions)
    hcc_relevant_count = sum(1 for c in conditions if c.hcc_relevant)
    high_confidence_count = sum(1 for c in conditions if c.confidence >= 0.9)

    # Update metadata
    state["metadata"] = {
        "document_id": document_id,
        "total_conditions": total_conditions,
        "hcc_relevant_count": hcc_relevant_count,
        "high_confidence_count": high_confidence_count,
        "confidence_avg": sum(c.confidence for c in conditions) / total_conditions if total_conditions > 0 else 0,
        "error_count": len(state.get("errors", [])),
    }

    return state
