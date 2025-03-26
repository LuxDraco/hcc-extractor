
"""
Utility functions for document extraction shared across modules.
"""

import re
from typing import Optional, List, Pattern

from app.models.document import ClinicalDocument, Condition


# Regex patterns for condition extraction
CONDITION_PATTERN: Pattern = re.compile(
    r"(\d+\.)\s*(.*?)(?:\s*-\s*)(.*?)(?:\n|$)", re.MULTILINE
)

# Pattern to extract ICD-10 codes
ICD_CODE_PATTERN: Pattern = re.compile(r"([A-Z]\d+\.\d+):\s*(.*?)(?:\n|$)")


def extract_assessment_plan(content: str) -> Optional[str]:
    """
    Extract the Assessment/Plan section from the clinical document.
    """
    assessment_pattern = re.compile(
        r"(?:Assessment\s*/?\s*Plan|Assessment and Plan)[\s\n]*(.*?)(?:\n\s*(?:Return to Office|Encounter Sign-Off|Follow-up|Plan of Care)|$)",
        re.DOTALL | re.IGNORECASE
    )

    match = assessment_pattern.search(content)
    if match:
        return match.group(1).strip()

    return None


def extract_conditions_rule_based(assessment_plan: str) -> List[Condition]:
    """
    Extract conditions from the Assessment/Plan section using rule-based approach.
    """
    conditions: List[Condition] = []

    # Find all condition matches
    matches = CONDITION_PATTERN.finditer(assessment_plan)

    for match in matches:
        number = match.group(1).strip().rstrip('.')
        condition_name = match.group(2).strip()
        details = match.group(3).strip()

        # Extract ICD code if present
        icd_code = None
        icd_description = None

        icd_match = ICD_CODE_PATTERN.search(details)
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