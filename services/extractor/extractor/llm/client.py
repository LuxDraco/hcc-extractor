"""
LangChain-based client for interacting with Vertex AI Gemini models.
"""

import os
from typing import List, Dict, Any, Optional

import vertexai
from dotenv import load_dotenv
from langchain_google_vertexai import ChatVertexAI
from langchain.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain.schema.output_parser import StrOutputParser
from langchain.schema.runnable import RunnablePassthrough

load_dotenv()


class LangChainGeminiClient:
    """Client for interacting with Vertex AI Gemini models using LangChain."""

    def __init__(
            self,
            project_id: Optional[str] = None,
            location: str = "us-central1",
            model_name: str = "gemini-2.0-flash",
    ) -> None:
        """
        Initialize the LangChain Gemini client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region
            model_name: Name of the Gemini model to use
        """
        self.project_id = project_id or os.environ.get("VERTEX_AI_PROJECT_ID")
        self.location = location or os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        self.model_name = model_name

        vertexai.init(
            project=self.project_id,
            location=self.location,
        )

        # Initialize the LangChain model
        self.llm = ChatVertexAI(
            model_name=self.model_name,
            temperature=0.1,
            max_tokens=None,
        )

    def extract_conditions(self, clinical_text: str) -> List[Dict[str, Any]]:
        """
        Extract conditions from clinical text using Gemini via LangChain.

        Args:
            clinical_text: Clinical text to analyze

        Returns:
            List of extracted conditions
        """
        # Create the extraction chain
        extraction_prompt = ChatPromptTemplate.from_template(
            """
            You are a medical information extraction expert specialized in analyzing clinical progress notes.
            
            I will provide you with a clinical note. Your task is to:
            
            1. Identify the "Assessment/Plan" section
            2. Extract all medical conditions listed in this section
            3. For each condition, extract:
                - The condition name
                - The ICD-10 code WITH the dot/period (e.g., "E11.65")
                - The ICD-10 code WITHOUT the dot/period (e.g., "E1165")
                - The description associated with the ICD-10 code
                - Any additional details about the condition
                - The status of the condition (e.g., "Stable", "Worsening", "Improving", etc.)
            
            Return the results as a structured JSON object with this exact format:
            ```json
            {{
                "conditions": [
                    {{
                        "id": "cond-1",
                        "name": "Condition name",
                        "icd_code": "ICD-10 code with dot (e.g., E11.65)",
                        "icd_code_no_dot": "ICD-10 code without dot (e.g., E1165)",
                        "icd_description": "ICD code description",
                        "details": "Additional details about condition",
                        "status": "Status of the condition",
                        "confidence": 0.95
                    }}
                ]
            }}
            ```
            
            Focus only on the Assessment/Plan section. Ensure the output is valid JSON. Only include information that is explicitly mentioned in the text.
            
            Here is the clinical note:
            {clinical_text}
            """
        )

        # Create the extraction chain with JSON output parsing
        json_parser = JsonOutputParser()

        extraction_chain = (
                {"clinical_text": RunnablePassthrough()}
                | extraction_prompt
                | self.llm
                | StrOutputParser()
                | json_parser
        )

        # Run the chain and extract conditions
        try:
            results = extraction_chain.invoke(clinical_text)
            return results.get("conditions", [])
        except Exception as e:
            print(f"Error extracting conditions: {e}")
            # Fallback in case of parsing error
            return []

    def get_hcc_relevance(self, conditions: List[Dict[str, Any]], hcc_codes: List[str]) -> List[Dict[str, Any]]:
        """
        Determine HCC relevance for extracted conditions.

        Args:
            conditions: List of extracted conditions
            hcc_codes: List of HCC-relevant codes (without dots)

        Returns:
            Conditions with added HCC relevance flag
        """
        for condition in conditions:
            # Check if the condition's ICD code (without dot) is in the HCC codes list
            is_hcc_relevant = condition.get("icd_code_no_dot", "") in hcc_codes
            condition["is_hcc_relevant"] = is_hcc_relevant

        return conditions
