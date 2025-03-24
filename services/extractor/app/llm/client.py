"""
Gemini 1.5 client for interacting with the Vertex AI API.
"""

import os
import json
from typing import Dict, List, Any, Optional

from google.cloud import aiplatform
from vertexai.generative_models import GenerativeModel, GenerationConfig


class GeminiClient:
    """Client for interacting with Vertex AI Gemini 1.5 Flash model."""

    def __init__(
            self,
            project_id: Optional[str] = None,
            location: str = "us-central1",
            model_name: str = "gemini-1.5-flash",
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

    def extract_conditions(self, clinical_text: str) -> List[Dict[str, Any]]:
        """
        Extract conditions from clinical text using Gemini.

        Args:
            clinical_text: Clinical text to analyze

        Returns:
            List of extracted conditions
        """
        # Create generation config
        generation_config = GenerationConfig(
            temperature=0.1,
            top_p=0.95,
            top_k=40,
            max_output_tokens=1024,
        )

        # Create prompt for condition extraction
        prompt = self._create_extraction_prompt(clinical_text)

        # Generate response
        response = self.model.generate_content(
            prompt,
            generation_config=generation_config,
        )

        # Parse and return the results
        try:
            # Extract JSON from response
            results = json.loads(response.text)
            return results.get("conditions", [])
        except (json.JSONDecodeError, AttributeError):
            # Fallback in case of parsing error
            return []

    def _create_extraction_prompt(self, clinical_text: str) -> str:
        """
        Create a prompt for condition extraction.

        Args:
            clinical_text: Clinical text to analyze

        Returns:
            Prompt for the Gemini model
        """
        prompt = f"""
            You are a medical information extraction expert specialized in analyzing clinical progress notes.
            
            I will provide you with a clinical note. Your task is to:
            
            1. Identify the "Assessment/Plan" section
            2. Extract all medical conditions listed in this section
            3. For each condition, extract:
                - The condition name
                - The ICD-10 code (if present)
                - The description associated with the ICD-10 code (if present)
                - Any additional details about the condition
            
            Return the results as a structured JSON object with this exact format:
            {{
                "conditions": [
                {{
                    "id": "cond-1",
                    "name": "Condition name",
                    "icd_code": "ICD-10 code",
                    "icd_description": "ICD code description",
                    "details": "Additional details about condition",
                    "confidence": 0.95  // Your confidence in the extraction accuracy (0.0 to 1.0)
                }},
                // Additional conditions...
                ]
            }}
            
            Focus only on the Assessment/Plan section. Ensure the output is valid JSON. Only include information that is explicitly mentioned in the text.
            
            Here is the clinical note:
            {clinical_text}
            """
        return prompt
