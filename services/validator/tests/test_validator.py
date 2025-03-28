"""
Unit tests for the HCC Validator service.

This module contains tests for the validator components, including the RulesEngine
and HCCValidator classes.
"""
import unittest
from unittest.mock import MagicMock, patch
import pandas as pd

from validator.data.code_repository import CodeRepository
from validator.models.condition import Condition, AnalysisResult, ValidationResult
from validator.validator.rules_engine import RulesEngine
from validator.validator.hcc_validator import HCCValidator


class TestRulesEngine(unittest.TestCase):
    """Unit tests for the RulesEngine class."""

    def setUp(self):
        """Set up the test environment."""
        self.rules_engine = RulesEngine()

        # Register a few test rules
        self.rules_engine.register_rule(
            "always_true",
            lambda condition: True,
            "Rule that always passes"
        )

        self.rules_engine.register_rule(
            "is_hcc_relevant",
            lambda condition: condition.hcc_relevant,
            "Rule that checks if condition is HCC-relevant"
        )

        self.rules_engine.register_rule(
            "has_code",
            lambda condition: condition.icd_code is not None,
            "Rule that checks if condition has a code"
        )

        # Create a test condition
        self.test_condition = Condition(
            id="test-001",
            name="Test Condition",
            icd_code="E11.9",
            icd_description="Type 2 diabetes mellitus without complications",
            hcc_relevant=True,
            confidence=0.95,
            metadata={"test": True}
        )

    def test_rule_registration(self):
        """Test that rules can be registered successfully."""
        # Check the number of rules
        self.assertEqual(len(self.rules_engine.rules), 3)

        # Check rule descriptions
        self.assertEqual(
            self.rules_engine.rules["always_true"]["description"],
            "Rule that always passes"
        )

    def test_rule_evaluation(self):
        """Test rule evaluation against conditions."""
        # Evaluate all rules
        results = self.rules_engine.evaluate(self.test_condition)

        # Check number of results
        self.assertEqual(len(results), 3)

        # Check that all results are ValidationRule objects
        for result in results:
            self.assertEqual(result.rule_id in self.rules_engine.rules, True)
            self.assertIsNotNone(result.description)
            self.assertIsInstance(result.passed, bool)

        # Check specific rules
        always_true_rule = next(r for r in results if r.rule_id == "always_true")
        self.assertTrue(always_true_rule.passed)

        is_hcc_relevant_rule = next(r for r in results if r.rule_id == "is_hcc_relevant")
        self.assertTrue(is_hcc_relevant_rule.passed)

        has_code_rule = next(r for r in results if r.rule_id == "has_code")
        self.assertTrue(has_code_rule.passed)

    def test_rule_with_failing_condition(self):
        """Test rule evaluation with a condition that fails some rules."""
        # Create a condition that will fail some rules
        failing_condition = Condition(
            id="fail-001",
            name="Failing Condition",
            icd_code=None,  # Will fail the has_code rule
            icd_description="Description without code",
            hcc_relevant=False,  # Will fail the is_hcc_relevant rule
            confidence=0.95,
            metadata={"test": True}
        )

        # Evaluate all rules
        results = self.rules_engine.evaluate(failing_condition)

        # Check specific rules
        always_true_rule = next(r for r in results if r.rule_id == "always_true")
        self.assertTrue(always_true_rule.passed)

        is_hcc_relevant_rule = next(r for r in results if r.rule_id == "is_hcc_relevant")
        self.assertFalse(is_hcc_relevant_rule.passed)

        has_code_rule = next(r for r in results if r.rule_id == "has_code")
        self.assertFalse(has_code_rule.passed)

    def test_rule_exception_handling(self):
        """Test that exceptions in rule evaluation are handled gracefully."""
        # Register a rule that raises an exception
        self.rules_engine.register_rule(
            "error_rule",
            lambda condition: 1 / 0,  # Will raise ZeroDivisionError
            "Rule that raises an exception"
        )

        # Evaluate rules (should not raise an exception)
        results = self.rules_engine.evaluate(self.test_condition)

        # Check that the error rule failed
        error_rule = next(r for r in results if r.rule_id == "error_rule")
        self.assertFalse(error_rule.passed)


class TestHCCValidator(unittest.TestCase):
    """Unit tests for the HCCValidator class."""

    def setUp(self):
        """Set up the test environment."""
        # Create a mock code repository
        self.code_repository = MagicMock(spec=CodeRepository)

        # Configure the mock repository
        self.code_repository.is_valid_icd_code.return_value = True
        self.code_repository.is_hcc_relevant.return_value = True
        self.code_repository.verify_code_description.return_value = True

        # Create test conditions
        self.compliant_condition = Condition(
            id="test-001",
            name="Compliant Condition",
            icd_code="E11.9",
            icd_description="Type 2 diabetes mellitus without complications",
            hcc_relevant=True,
            hcc_code="HCC19",
            hcc_category="Diabetes",
            confidence=0.95,
            reasoning="Valid HCC diagnosis",
            metadata={"test": True}
        )

        self.non_compliant_condition = Condition(
            id="test-002",
            name="Non-Compliant Condition",
            icd_code="Z99.9",  # Not an HCC code
            icd_description="Dependence on unspecified enabling machines and devices",
            hcc_relevant=True,  # Incorrectly marked as HCC-relevant
            hcc_code="HCC99",  # Invalid HCC code
            confidence=0.6,  # Below threshold
            reasoning="Low confidence determination",
            metadata={"test": True}
        )

        # Create a test analysis result
        self.analysis_result = AnalysisResult(
            document_id="doc-001",
            conditions=[self.compliant_condition, self.non_compliant_condition],
            metadata={"test": True},
            errors=[]
        )

        # Create the validator
        self.validator = HCCValidator(self.code_repository)

    def test_validator_initialization(self):
        """Test that the validator initializes correctly."""
        # Check that the rules engine is initialized
        self.assertIsNotNone(self.validator.rules_engine)

        # Check that rules are registered
        self.assertGreaterEqual(len(self.validator.rules_engine.rules), 1)

    def test_validate_compliant_condition(self):
        """Test validation of a compliant condition."""
        # Configure the mock repository for this test
        self.code_repository.is_valid_icd_code.return_value = True
        self.code_repository.is_hcc_relevant.return_value = True

        # Create a single condition analysis result
        single_condition_result = AnalysisResult(
            document_id="doc-001",
            conditions=[self.compliant_condition],
            metadata={"test": True},
            errors=[]
        )

        # Validate the result
        validation_result = self.validator.validate(single_condition_result)

        # Check that validation result is created correctly
        self.assertEqual(validation_result.document_id, "doc-001")
        self.assertEqual(len(validation_result.conditions), 1)

        # Check that the condition is marked as compliant
        validated_condition = validation_result.conditions[0]
        self.assertTrue(validated_condition.is_compliant)
        self.assertEqual(validated_condition.id, "test-001")

        # Check that validation rules were applied
        self.assertGreaterEqual(len(validated_condition.validation_results), 1)

        # Check that metadata is updated
        self.assertEqual(validation_result.metadata["compliant_conditions"], 1)
        self.assertEqual(validation_result.metadata["non_compliant_conditions"], 0)

    def test_validate_non_compliant_condition(self):
        """Test validation of a non-compliant condition."""
        # Configure the mock repository for this test
        self.code_repository.is_valid_icd_code.return_value = True
        self.code_repository.is_hcc_relevant.return_value = False  # Important: will fail HCC relevance check

        # Create a single condition analysis result
        single_condition_result = AnalysisResult(
            document_id="doc-001",
            conditions=[self.non_compliant_condition],
            metadata={"test": True},
            errors=[]
        )

        # Validate the result
        validation_result = self.validator.validate(single_condition_result)

        # Check that validation result is created correctly
        self.assertEqual(validation_result.document_id, "doc-001")
        self.assertEqual(len(validation_result.conditions), 1)

        # Check that the condition is marked as non-compliant
        validated_condition = validation_result.conditions[0]
        self.assertFalse(validated_condition.is_compliant)
        self.assertEqual(validated_condition.id, "test-002")

        # Check that validation rules were applied
        self.assertGreaterEqual(len(validated_condition.validation_results), 1)

        # Find the failed rule for HCC relevance
        failed_rules = [r for r in validated_condition.validation_results if not r.passed]
        self.assertGreaterEqual(len(failed_rules), 1)

        # Check that metadata is updated
        self.assertEqual(validation_result.metadata["compliant_conditions"], 0)
        self.assertEqual(validation_result.metadata["non_compliant_conditions"], 1)

    def test_validate_mixed_conditions(self):
        """Test validation of multiple conditions with mixed compliance."""

        # Configure the mock repository to make one condition compliant and one non-compliant
        def is_hcc_relevant_side_effect(icd_code):
            return icd_code == "E11.9"  # Only the compliant condition's code is HCC-relevant

        self.code_repository.is_hcc_relevant.side_effect = is_hcc_relevant_side_effect

        # Validate the full analysis result with both conditions
        validation_result = self.validator.validate(self.analysis_result)

        # Check that validation result contains both conditions
        self.assertEqual(len(validation_result.conditions), 2)

        # Find compliant and non-compliant conditions
        compliant_conditions = [c for c in validation_result.conditions if c.is_compliant]
        non_compliant_conditions = [c for c in validation_result.conditions if not c.is_compliant]

        # Check counts
        self.assertEqual(len(compliant_conditions), 1)
        self.assertEqual(len(non_compliant_conditions), 1)

        # Check that metadata is correctly updated
        self.assertEqual(validation_result.metadata["total_conditions"], 2)
        self.assertEqual(validation_result.metadata["compliant_conditions"], 1)
        self.assertEqual(validation_result.metadata["non_compliant_conditions"], 1)


if __name__ == "__main__":
    unittest.main()