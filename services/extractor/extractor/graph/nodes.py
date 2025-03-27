"""
Nodes for the LangGraph extraction workflow.
"""
import csv
import logging
import os
from pathlib import Path
from typing import List, TypedDict, Optional, Dict, Any

from dotenv import load_dotenv

from extractor.extraction.utils import extract_assessment_plan
from extractor.llm.client import LangChainGeminiClient
from extractor.models.document import ClinicalDocument, Condition, ExtractionResult

load_dotenv()


class GraphState(TypedDict):
    """Type definition for the state passed between nodes in the graph."""

    document: ClinicalDocument
    assessment_plan: Optional[str]
    conditions_extracted: List[Dict[str, Any]]
    final_conditions: List[Condition]
    hcc_codes: List[str]
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

    # Extract the Assessment/Plan section
    assessment_plan = extract_assessment_plan(content)

    # Update state
    state["assessment_plan"] = assessment_plan

    return state


def extract_conditions(state: GraphState) -> GraphState:
    """
    Extract conditions using LangChain and Gemini.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with condition extraction results
    """
    document = state["document"]

    # Use LangChain client for extraction
    client = LangChainGeminiClient()
    extracted_conditions = client.extract_conditions(document.content)

    # Update state
    state["conditions_extracted"] = extracted_conditions

    return state


def load_hcc_codes(state: GraphState) -> GraphState:
    """
    Load HCC-relevant codes from the CSV file.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with HCC codes loaded
    """
    # Path to the HCC codes CSV file
    csv_path = os.environ.get("HCC_CODES_PATH", "../data/HCC_relevant_codes.csv")
    csv_path = Path(csv_path)
    hcc_codes = []

    try:
        if csv_path.exists():
            with open(csv_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Get the ICD-10 code without the dot
                    code = row.get("ICD-10-CM Codes", "").strip()
                    hcc_codes.append(code)
        else:
            # Fallback to in-memory processing if file not available
            # This would be populated from the database or another source
            pass

    except Exception as e:
        print(f"Error loading HCC codes: {e}")

    # Update state
    state["hcc_codes"] = hcc_codes

    return state


def determine_hcc_relevance(state: GraphState) -> GraphState:
    """
    Determine which conditions are HCC-relevant.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with HCC relevance determined
    """
    extracted_conditions = state["conditions_extracted"]
    hcc_codes = state["hcc_codes"]

    logging.info(f"HCC codes: {hcc_codes[0]}")

    # Check each condition for HCC relevance
    for condition in extracted_conditions:
        icd_code_no_dot = condition.get("icd_code_no_dot")
        icd_code = condition.get("icd_code")
        logging.info(f"Checking HCC relevance for {icd_code_no_dot} || ({icd_code})")
        condition["is_hcc_relevant"] = icd_code_no_dot in hcc_codes or icd_code in hcc_codes

    return state


def convert_to_model_objects(state: GraphState) -> GraphState:
    """
    Convert extracted conditions to Condition model objects.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with final condition objects
    """
    extracted_conditions = state["conditions_extracted"]
    final_conditions = []

    for idx, cond_data in enumerate(extracted_conditions):
        condition = Condition(
            id=cond_data.get("id", f"cond-{idx + 1}"),
            name=cond_data.get("name", ""),
            icd_code=cond_data.get("icd_code"),
            icd_description=cond_data.get("icd_description"),
            details=cond_data.get("details"),
            confidence=cond_data.get("confidence", 0.9),
            metadata={
                "extraction_method": "langgraph_llm",
                "status": cond_data.get("status"),
                "icd_code_no_dot": cond_data.get("icd_code_no_dot"),
                "is_hcc_relevant": cond_data.get("is_hcc_relevant", False)
            }
        )
        final_conditions.append(condition)

    # Update state
    state["final_conditions"] = final_conditions

    return state


def create_result(state: GraphState) -> GraphState:
    """
    Create the final extraction result.

    Args:
        state: Current state of the workflow

    Returns:
        Updated state with final extraction result
    """
    document = state["document"]
    conditions = state["final_conditions"]

    # Count HCC-relevant conditions
    hcc_relevant_count = sum(1 for c in conditions if c.metadata.get("is_hcc_relevant", False))

    # Create extraction result
    result = ExtractionResult(
        document_id=document.document_id,
        conditions=conditions,
        metadata={
            "source": document.source,
            "total_conditions": len(conditions),
            "hcc_relevant_count": hcc_relevant_count,
            "extraction_method": "langgraph_llm",
        }
    )

    # Update state
    state["extraction_result"] = result

    return state