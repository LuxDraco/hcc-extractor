"""
Rules engine for applying validation rules to conditions.

This module provides a flexible engine for registering, applying,
and evaluating validation rules on medical conditions.
"""

from typing import Dict, List, Any, Callable

from app.models.condition import Condition, ValidationRule


class RulesEngine:
    """Engine for applying validation rules to conditions."""

    def __init__(self) -> None:
        """Initialize the rules engine."""
        self.rules: Dict[str, Dict[str, Any]] = {}

    def register_rule(
            self, rule_id: str, validator_func: Callable[[Condition], bool], description: str
    ) -> None:
        """
        Register a validation rule.

        Args:
            rule_id: Unique identifier for the rule
            validator_func: Function that evaluates the rule
            description: Description of the rule
        """
        self.rules[rule_id] = {
            "validator": validator_func,
            "description": description,
        }

    def evaluate(self, condition: Condition) -> List[ValidationRule]:
        """
        Evaluate all rules against a condition.

        Args:
            condition: Condition to evaluate

        Returns:
            List of validation results
        """
        results = []

        for rule_id, rule_info in self.rules.items():
            # Apply the validation function
            try:
                passed = rule_info["validator"](condition)
            except Exception:
                # If the rule throws an exception, consider it failed
                passed = False

            # Create validation result
            result = ValidationRule(
                rule_id=rule_id,
                description=rule_info["description"],
                passed=passed,
            )

            results.append(result)

        return results
