"""
Prompt templates for interactions with the Gemini model.

This module contains predefined prompts for various analysis tasks
related to HCC relevance determination.
"""

from typing import Dict, List, Any


class PromptTemplates:
    """Collection of prompt templates for Gemini interactions."""

    @staticmethod
    def hcc_analysis_prompt(
            conditions: List[Dict[str, Any]], hcc_codes_sample: List[Dict[str, Any]]
    ) -> str:
        """
        Generate a prompt for HCC relevance analysis.

        Args:
            conditions: List of conditions to analyze
            hcc_codes_sample: Sample of HCC-relevant codes for reference

        Returns:
            Formatted prompt for the Gemini model
        """
        return f"""
        You are a medical coding expert specializing in HCC (Hierarchical Condition Categories) analysis.
        
        Your task is to analyze a list of medical conditions extracted from a clinical document and determine their HCC relevance.
        
        For each condition:
        1. Check if its ICD-10 code is HCC-relevant
        2. Determine the appropriate HCC category if relevant
        3. Provide a confidence score and explanation for your determination
        
        Here are the conditions to analyze:
        {conditions}
        
        Here is a sample of HCC-relevant ICD-10 codes for reference:
        {hcc_codes_sample}
        
        Respond with a structured analysis of each condition, including:
        - Whether it's HCC-relevant (true/false)
        - The HCC category if relevant
        - Your confidence in the determination (0-1)
        - A brief explanation of your reasoning
        
        Format your response as valid JSON.
        """

    @staticmethod
    def icd_code_verification_prompt(
            condition_name: str, proposed_icd_code: str
    ) -> str:
        """
        Generate a prompt for ICD code verification.

        Args:
            condition_name: Name of the medical condition
            proposed_icd_code: ICD code to verify

        Returns:
            Formatted prompt for the Gemini model
        """
        return f"""
        As a medical coding expert, verify if the ICD-10 code "{proposed_icd_code}" is appropriate for the condition "{condition_name}".
        
        Provide:
        1. Whether the code is correct (true/false)
        2. A confidence score (0-1)
        3. If incorrect, suggest a more appropriate code
        4. A brief explanation of your determination
        
        Format your response as valid JSON.
        """

    @staticmethod
    def condition_enrichment_prompt(
            condition_name: str, icd_code: str
    ) -> str:
        """
        Generate a prompt for enriching condition information.

        Args:
            condition_name: Name of the medical condition
            icd_code: ICD code of the condition

        Returns:
            Formatted prompt for the Gemini model
        """
        return f"""
        As a medical expert, provide additional context about the condition "{condition_name}" (ICD-10 code: {icd_code}).
        
        Include:
        1. Common symptoms and signs
        2. Typical treatment approaches
        3. Risk factors and complications
        4. Relevance to overall patient health assessment
        
        Keep your response concise and clinically relevant. Format as valid JSON.
        """
