"""
Gemini 1.5 client for interacting with the Vertex AI API.
"""

import json
import os
from typing import Dict, List, Any, Optional

import logging

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, GenerationConfig


class GeminiClient:
    """Client for interacting with Vertex AI Gemini 1.5 Flash model."""

    def __init__(
            self,
            project_id: Optional[str] = None,
            location: str = "us-central1",
            model_name: str = "gemini-2.0-flash",
    ) -> None:
        """
        Initialize the Gemini client.

        Args:
            project_id: Google Cloud project ID
            location: Google Cloud region
            model_name: Name of the Gemini model to use
        """
        self.project_id = project_id or os.environ.get("VERTEX_AI_PROJECT_ID")
        self.location = location or os.environ.get("VERTEX_AI_LOCATION", "us-central1")
        self.model_name = model_name

        # Initialize Vertex AI
        aiplatform.init(project=self.project_id, location=self.location)

        # Initialize the model
        self.model = GenerativeModel(self.model_name)

    def analyze_hcc_relevance(
            self, conditions: List[Dict[str, Any]], hcc_codes: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Analyze conditions to determine HCC relevance.

        Args:
            conditions: List of conditions with their ICD codes
            hcc_codes: Reference list of HCC-relevant codes

        Returns:
            List of conditions with HCC relevance determination
        """
        # Create generation config
        generation_config = GenerationConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=2048,
        )

        # Create prompt for HCC relevance analysis
        prompt = self._create_hcc_analysis_prompt(conditions, hcc_codes)

        # Generate response
        response = self.model.generate_content(
            prompt,
            generation_config=generation_config,
        )

        response_str = response.text
        response_str = response_str.replace("```json", "```json\n")
        response_str = response_str.replace("```", "```\n")
        response_str = response_str.replace("NaN", "null")
        response_str = response_str.replace("nan", "null")

        # logging.info(f"Response text: {response_str}")

        # Parse and return the results
        try:
            # First try direct JSON parsing
            try:
                results = json.loads(response_str)
                return results.get("conditions", [])
            except json.JSONDecodeError:
                # If direct parsing fails, try to extract JSON from Markdown code blocks
                import re

                # Look for JSON code blocks (```json ... ```)
                json_match = re.search(r'```(?:json)?\s*\n(.*?)\n```', response_str, re.DOTALL)
                if json_match:
                    json_content = json_match.group(1)
                    results = json.loads(json_content)
                    conditions_result = results.get("conditions", [])

                    # Fix NaN values
                    from analyzer.graph.nodes import fix_nan_values
                    conditions_result = fix_nan_values(conditions_result)

                    return conditions_result

                # Try looking for just the JSON object pattern
                json_object_match = re.search(r'(\{\s*"conditions"\s*:.*\})', response_str, re.DOTALL)
                if json_object_match:
                    json_content = json_object_match.group(1)
                    results = json.loads(json_content)
                    conditions_result = results.get("conditions", [])

                    # Fix NaN values
                    from analyzer.graph.nodes import fix_nan_values
                    conditions_result = fix_nan_values(conditions_result)

                    return conditions_result

                # If we get here, we couldn't parse the JSON
                raise ValueError(f"Could not extract valid JSON from response: {response_str[:200]}...")

        except Exception as e:
            # Log the error and response for debugging
            logging.error(f"Error parsing response: {str(e)}")
            # logging.error(f"Response text: {response.text}")
            return []

    def _create_hcc_analysis_prompt(
            self,
            conditions: List[Dict[str, Any]],
            hcc_codes: List[Dict[str, Any]]
    ) -> str:
        """
        Create a prompt for HCC relevance analysis.

        Args:
            conditions: List of conditions with their ICD codes
            hcc_codes: Reference list of HCC-relevant codes

        Returns:
            Prompt for the Gemini model
        """
        # Fix NaN values in HCC codes before using them
        fixed_hcc_codes = []
        import math

        for code in hcc_codes:
            fixed_code = {}
            for key, value in code.items():
                # Check for NaN values in any field
                if isinstance(value, float) and math.isnan(value):
                    fixed_code[key] = ""
                elif isinstance(value, str):
                    # Replace string "NaN" or "nan" with empty string
                    fixed_code[key] = value.replace("NaN", "").replace("nan", "")
                else:
                    fixed_code[key] = value
            fixed_hcc_codes.append(fixed_code)

        logging.info(f"Fixed HCC codes sample: {fixed_hcc_codes[:2]}")

        # Convert conditions to string
        conditions_str = json.dumps(conditions, indent=2)

        # Create a condensed version of HCC codes
        # We'll limit to a maximum of 50 codes to avoid token limits
        hcc_codes_sample = fixed_hcc_codes[:50]
        hcc_codes_str = json.dumps(hcc_codes_sample, indent=2)

        prompt = f"""
            You are a medical coding expert specializing in HCC (Hierarchical Condition Categories) analysis.

            I will provide you with:
            1. A list of medical conditions with their ICD-10 codes extracted from a clinical note
            2. A sample of HCC-relevant ICD-10 codes for reference

            Your task is to:
            1. Determine which of the extracted conditions are HCC-relevant
            2. For HCC-relevant conditions, provide the matching HCC code and category
            3. For all conditions, provide a confidence score for your determination

            Return the results as a structured JSON object with this exact format:
            {{
                "conditions": [
                {{
                    "id": "condition-id",
                    "name": "Condition name",
                    "icd_code": "ICD-10 code",
                    "hcc_relevant": true/false,
                    "hcc_code": "HCC code" (if relevant, otherwise null),
                    "hcc_category": "HCC category" (if relevant, otherwise null),
                    "confidence": 0.95,  // Your confidence in the determination (0.0 to 1.0)
                    "reasoning": "Brief explanation of your determination"
                }},
                // Additional conditions...
                ]
            }}

            Even if the exact ICD code is not in the sample of HCC-relevant codes I provided, use your knowledge to determine if a condition would be HCC-relevant. Consider disease severity, chronicity, and impact on resource utilization and risk adjustment.

            Here are the extracted conditions:
                    {conditions_str}
            Here is a sample of HCC-relevant ICD-10 codes:
                    {hcc_codes_str}
            Note that this is only a sample. The full list of HCC-relevant codes is much more extensive. Use your knowledge to make determinations for codes not in this sample. If you're uncertain, state so in the reasoning field.

            Ensure the output is valid JSON.

            Return just the JSON object with the conditions. Do not include any additional text or formatting.
            Do not include code limiters (triple quotes) in the response like ```json ``` or ```python```.
            """
        return prompt
