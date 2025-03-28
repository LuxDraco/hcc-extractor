"""
Unit tests for the HCC Extractor service.

This module contains tests for the extractor components, including the DocumentParser,
DocumentProcessor, and Extraction utility functions.
"""

import unittest
from unittest.mock import MagicMock, patch
import json
import os
from pathlib import Path

from extractor.models.document import ClinicalDocument, Condition, ExtractionResult
from extractor.extractor.processor import DocumentProcessor
from extractor.utils.document_parser import DocumentParser
from extractor.extraction.utils import extract_assessment_plan
from extractor.utils.hcc_utils import HCCCodeManager


class TestDocumentParser(unittest.TestCase):
    """Unit tests for the DocumentParser class."""

    def setUp(self):
        """Set up the test environment."""
        self.parser = DocumentParser()

        # Sample test document content
        self.test_content = """
        Patient
        Name SMITH, JOHN (67yo, M) ID# 12345 Appt. Date/Time 07/15/2024 02:30PM
        DOB 04/20/1957 Service Dept. athenaHealth
        Provider DR. JONES

        Chief Complaint
        Followup: Diabetes

        Assessment / Plan

        1. Type 2 diabetes mellitus -
           Stable
           Continue Metformin 1000mg twice daily
           E11.9: Type 2 diabetes mellitus without complications

        2. Essential hypertension -
           Improving with medication
           Continue lisinopril 20mg daily
           I10: Essential (primary) hypertension

        Return to Office
        Patient will return in 3 months
        """

        # Expected patient info
        self.expected_patient_info = {
            "name": "SMITH, JOHN",
            "id": "12345",
            "age": 67,
            "gender": "Male",
            "dob": "04/20/1957"
        }

    def test_parse_patient_info(self):
        """Test parsing patient information from document content."""
        # Call the private method directly for testing
        patient_info = self.parser._extract_patient_info(self.parser, self.test_content)

        # Verify name extraction
        self.assertEqual(patient_info.get("name"), "SMITH, JOHN")

        # Verify patient ID extraction
        self.assertEqual(patient_info.get("id"), "12345")

        # Verify age extraction
        self.assertEqual(patient_info.get("age"), 67)

        # Verify gender extraction
        self.assertEqual(patient_info.get("gender"), "Male")

        # Verify DOB extraction
        self.assertEqual(patient_info.get("dob"), "04/20/1957")

    def test_parse_metadata(self):
        """Test parsing metadata from document content."""
        # Call the private method directly for testing
        metadata = self.parser._extract_metadata(self.parser, self.test_content)

        # Verify provider extraction
        self.assertEqual(metadata.get("provider"), "DR. JONES")

        # Verify appointment date extraction
        self.assertEqual(metadata.get("appointment_date"), "07/15/2024")

        # Verify chief complaint extraction
        self.assertTrue("Diabetes" in metadata.get("chief_complaint", ""))

    def test_parse_document(self):
        """Test the complete document parsing process."""
        # Parse the document
        document = self.parser.parse(self.test_content, "test_document.txt")

        # Verify document ID
        self.assertEqual(document.document_id, "doc-test_document")

        # Verify source
        self.assertEqual(document.source, "test_document.txt")

        # Verify content
        self.assertEqual(document.content, self.test_content)

        # Verify patient info and metadata are populated
        self.assertTrue(document.patient_info)
        self.assertTrue(document.metadata)


class TestDocumentProcessor(unittest.TestCase):
    """Unit tests for the DocumentProcessor class."""

    def setUp(self):
        """Set up the test environment."""
        # Mock LLM client
        self.mock_llm_client = MagicMock()
        self.mock_llm_client.extract_conditions.return_value = [
            {
                "id": "cond-1",
                "name": "Type 2 diabetes mellitus",
                "icd_code": "E11.9",
                "icd_code_no_dot": "E119",
                "icd_description": "Type 2 diabetes mellitus without complications",
                "details": "Stable\nContinue Metformin 1000mg twice daily",
                "status": "Stable",
                "confidence": 0.95
            },
            {
                "id": "cond-2",
                "name": "Essential hypertension",
                "icd_code": "I10",
                "icd_code_no_dot": "I10",
                "icd_description": "Essential (primary) hypertension",
                "details": "Improving with medication\nContinue lisinopril 20mg daily",
                "status": "Improving",
                "confidence": 0.92
            }
        ]

        # Create test document
        self.test_document = ClinicalDocument(
            document_id="doc-test",
            source="test_source.txt",
            content="Test content with assessment plan",
            patient_info={"name": "Test Patient"},
            metadata={"provider": "Test Provider"}
        )

        # Pass the mock LLM client through a patch
        with patch('extractor.extractor.processor.LangChainGeminiClient', return_value=self.mock_llm_client):
            self.processor = DocumentProcessor(use_langgraph=False)
            self.processor.llm_client = self.mock_llm_client

    def test_process_with_llm(self):
        """Test processing a document with direct LLM extraction."""
        # Process the document
        result = self.processor._process_with_llm(self.test_document)

        # Verify result structure
        self.assertIsInstance(result, ExtractionResult)
        self.assertEqual(result.document_id, "doc-test")

        # Verify conditions
        self.assertEqual(len(result.conditions), 2)

        # Verify first condition details
        first_condition = result.conditions[0]
        self.assertEqual(first_condition.id, "cond-1")
        self.assertEqual(first_condition.name, "Type 2 diabetes mellitus")
        self.assertEqual(first_condition.icd_code, "E11.9")

        # Verify metadata
        self.assertEqual(result.metadata["extraction_method"], "llm_direct")

        # Verify LLM client was called
        self.mock_llm_client.extract_conditions.assert_called_once()

    @patch('extractor.graph.pipeline.ExtractionPipeline')
    def test_process_with_langgraph(self, mock_pipeline_class):
        """Test processing a document using LangGraph pipeline."""
        # Configure the mock pipeline
        mock_pipeline = MagicMock()
        mock_pipeline_class.return_value = mock_pipeline

        # Set up mock result
        mock_result = ExtractionResult(
            document_id="doc-test",
            conditions=[
                Condition(
                    id="cond-1",
                    name="Type 2 diabetes mellitus",
                    icd_code="E11.9",
                    icd_description="Type 2 diabetes mellitus without complications",
                    confidence=0.95,
                    metadata={"extraction_method": "langgraph"}
                )
            ],
            metadata={"extraction_method": "langgraph"}
        )

        mock_pipeline.process.return_value = mock_result

        # Create processor with LangGraph enabled
        processor = DocumentProcessor(use_langgraph=True)
        processor._pipeline = mock_pipeline

        # Process document
        result = processor.process(self.test_document)

        # Verify pipeline was called
        mock_pipeline.process.assert_called_once_with(self.test_document)

        # Verify result
        self.assertEqual(result.document_id, "doc-test")
        self.assertEqual(len(result.conditions), 1)
        self.assertEqual(result.conditions[0].id, "cond-1")
        self.assertEqual(result.metadata["extraction_method"], "langgraph")


class TestExtractionUtils(unittest.TestCase):
    """Unit tests for extraction utility functions."""

    def test_extract_assessment_plan(self):
        """Test extracting assessment plan from document content."""
        # Test document with assessment/plan section
        document_content = """
        History of Present Illness
        Patient presents for follow-up.

        Assessment / Plan
        1. Type 2 diabetes - Stable, continue medications
        2. Hypertension - Improving with current regimen

        Follow-up in 3 months.
        """

        # Extract assessment plan
        assessment_plan = extract_assessment_plan(document_content)

        # Verify extraction
        self.assertIsNotNone(assessment_plan)
        self.assertIn("Type 2 diabetes", assessment_plan)
        self.assertIn("Hypertension", assessment_plan)

        # Test document without assessment/plan section
        document_without_plan = "This is a document without an assessment or plan section."

        # Extract assessment plan
        result = extract_assessment_plan(document_without_plan)

        # Verify no extraction
        self.assertIsNone(result)

        # Test document with alternative format
        document_alt_format = """
        Medical Assessment and Plan:
        1. GERD - Continue PPI
        2. Arthritis - Recommend physical therapy
        """

        # Extract assessment plan
        result_alt = extract_assessment_plan(document_alt_format)

        # Verify extraction with alternative format
        self.assertIsNotNone(result_alt)
        self.assertIn("GERD", result_alt)


class TestHCCCodeManager(unittest.TestCase):
    """Unit tests for the HCC code manager."""

    def setUp(self):
        """Set up the test environment."""
        # Create temporary CSV file for testing
        self.test_csv_path = "temp_hcc_codes.csv"

        with open(self.test_csv_path, "w") as f:
            f.write("ICD-10-CM Codes,Description,Tags\n")
            f.write("E11.9,Type 2 diabetes mellitus without complications,HCC19\n")
            f.write("I10,Essential (primary) hypertension,HCC85\n")
            f.write("J44.9,Chronic obstructive pulmonary disease unspecified,HCC111\n")

        # Create HCC code manager
        self.hcc_manager = HCCCodeManager(self.test_csv_path)

    def tearDown(self):
        """Clean up after tests."""
        # Remove temporary CSV file
        if os.path.exists(self.test_csv_path):
            os.remove(self.test_csv_path)

    def test_load_hcc_codes(self):
        """Test loading HCC codes from CSV file."""
        # Load codes
        self.hcc_manager.load_hcc_codes()

        # Verify codes are loaded
        self.assertTrue(self.hcc_manager._loaded)
        self.assertGreater(len(self.hcc_manager._hcc_codes), 0)

        # Check specific codes
        self.assertIn("E119", self.hcc_manager._hcc_codes)
        self.assertIn("I10", self.hcc_manager._hcc_codes)
        self.assertIn("J449", self.hcc_manager._hcc_codes)

    def test_is_hcc_relevant(self):
        """Test checking if a code is HCC-relevant."""
        # Load codes
        self.hcc_manager.load_hcc_codes()

        # Check relevant codes
        self.assertTrue(self.hcc_manager.is_hcc_relevant("E11.9"))
        self.assertTrue(self.hcc_manager.is_hcc_relevant("E119"))  # Without dot
        self.assertTrue(self.hcc_manager.is_hcc_relevant("I10"))

        # Check non-relevant codes
        self.assertFalse(self.hcc_manager.is_hcc_relevant("Z00.00"))
        self.assertFalse(self.hcc_manager.is_hcc_relevant("Z0000"))
        self.assertFalse(self.hcc_manager.is_hcc_relevant(""))
        self.assertFalse(self.hcc_manager.is_hcc_relevant(None))

    def test_get_code_info(self):
        """Test getting information about an HCC code."""
        # Load codes
        self.hcc_manager.load_hcc_codes()

        # Get code info
        info = self.hcc_manager.get_code_info("E11.9")

        # Verify code info
        self.assertIsNotNone(info)
        self.assertEqual(info.get("code"), "E11.9")
        self.assertEqual(info.get("description"), "Type 2 diabetes mellitus without complications")
        self.assertEqual(info.get("tags"), "HCC19")

        # Get info with code without dot
        info_no_dot = self.hcc_manager.get_code_info("E119")

        # Verify info is the same
        self.assertEqual(info, info_no_dot)

        # Get info for non-existent code
        info_non_existent = self.hcc_manager.get_code_info("Z00.00")

        # Verify empty result
        self.assertEqual(info_non_existent, {})

    def test_get_all_hcc_codes(self):
        """Test getting all HCC-relevant codes."""
        # Load codes
        self.hcc_manager.load_hcc_codes()

        # Get all codes
        all_codes = self.hcc_manager.get_all_hcc_codes()

        # Verify result
        self.assertIsInstance(all_codes, list)
        self.assertEqual(len(all_codes), 3)
        self.assertIn("E119", all_codes)
        self.assertIn("I10", all_codes)
        self.assertIn("J449", all_codes)


if __name__ == "__main__":
    unittest.main()