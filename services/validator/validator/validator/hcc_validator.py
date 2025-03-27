"""
HCC validator for validating HCC relevance determinations.

This module contains the core logic for validating whether conditions are
properly identified as HCC-relevant, applying business rules, and ensuring
compliant documentation.
"""

from validator.data.code_repository import CodeRepository
from validator.models.condition import (
    AnalysisResult,
    ValidationResult,
    ValidatedCondition,
    ValidationRule
)
from validator.validator.rules_engine import RulesEngine


class HCCValidator:
    """Validator for HCC relevance determinations."""

    def __init__(self, code_repository: CodeRepository) -> None:
        """
        Initialize the HCC validator.

        Args:
            code_repository: Repository of HCC codes
        """
        self.code_repository = code_repository
        self.rules_engine = RulesEngine()

        # Register validation rules
        self._register_rules()

    def _register_rules(self) -> None:
        """Register validation rules with the rules engine."""
        # Rule 1: Condition must have a valid ICD-10 code
        self.rules_engine.register_rule(
            "valid_icd_code",
            lambda condition: condition.icd_code is not None and self.code_repository.is_valid_icd_code(
                condition.icd_code),
            "Condition must have a valid ICD-10 code"
        )

        # Rule 2: If marked as HCC-relevant, must be in the HCC codes list
        self.rules_engine.register_rule(
            "hcc_relevance_verified",
            lambda condition: (not condition.hcc_relevant) or
                              (condition.hcc_code is not None and
                               self.code_repository.is_hcc_relevant(condition.icd_code)),
            "HCC-relevant conditions must have a code in the HCC reference list"
        )

        # Rule 3: Confidence must be above threshold for inclusion
        self.rules_engine.register_rule(
            "sufficient_confidence",
            lambda condition: condition.confidence >= 0.7,
            "Confidence score must be at least 0.7 for inclusion"
        )

        # Rule 4: Code and description must match
        self.rules_engine.register_rule(
            "code_description_match",
            lambda condition: condition.icd_code is None or
                              self.code_repository.verify_code_description(
                                  condition.icd_code, condition.icd_description
                              ),
            "ICD code and description must match"
        )

    def validate(self, analysis_result: AnalysisResult) -> ValidationResult:
        """
        Validate an analysis result.

        Args:
            analysis_result: Result of HCC relevance analysis

        Returns:
            Validation result
        """
        validated_conditions = []

        for condition in analysis_result.conditions:
            # Apply validation rules
            validation_results = self.rules_engine.evaluate(condition)

            # Determine overall compliance
            is_compliant = all(result.passed for result in validation_results)

            # Convert to validated condition
            validated_condition = ValidatedCondition(
                id=condition.id,
                name=condition.name,
                icd_code=condition.icd_code,
                icd_description=condition.icd_description,
                details=condition.details,
                hcc_relevant=condition.hcc_relevant,
                hcc_code=condition.hcc_code,
                hcc_category=condition.hcc_category,
                confidence=condition.confidence,
                reasoning=condition.reasoning,
                metadata=condition.metadata,
                is_compliant=is_compliant,
                validation_results=validation_results
            )

            validated_conditions.append(validated_condition)

        # Create validation result
        result = ValidationResult(
            document_id=analysis_result.document_id,
            conditions=validated_conditions,
            metadata={
                **analysis_result.metadata,
                "total_conditions": len(validated_conditions),
                "compliant_conditions": sum(1 for c in validated_conditions if c.is_compliant),
                "non_compliant_conditions": sum(1 for c in validated_conditions if not c.is_compliant),
            }
        )

        return result