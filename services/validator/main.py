"""
Main module for the HCC Validator Service.

This module serves as the entry point for the validator service, which is responsible
for validating HCC relevance determinations, applying business rules, and ensuring
proper compliance documentation.
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Union

from validator.data.code_repository import CodeRepository
from validator.message_consumer import run_consumer
from validator.models.condition import AnalysisResult, ProcessingStatus
from validator.storage.local import LocalStorageManager
from validator.validator.hcc_validator import HCCValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ValidationService:
    """Service for validating HCC relevance determinations."""

    def __init__(
            self,
            input_dir: Union[str, Path],
            output_dir: Union[str, Path],
            hcc_codes_path: Union[str, Path]
    ) -> None:
        """
        Initialize the validation service.

        Args:
            input_dir: Directory containing input analysis results
            output_dir: Directory where validation results will be saved
            hcc_codes_path: Path to the CSV file containing HCC codes
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.hcc_codes_path = Path(hcc_codes_path)
        self.storage = LocalStorageManager(self.input_dir, self.output_dir)
        self.code_repository = CodeRepository(self.hcc_codes_path)
        self.validator = HCCValidator(self.code_repository)

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        logger.info(
            f"Initialized validation service with HCC codes from {hcc_codes_path}"
        )

    def process_analysis_results(self) -> List[ProcessingStatus]:
        """
        Process all analysis results in the input directory.

        Returns:
            List of processing status objects for each analysis result
        """
        analysis_files = self.storage.list_input_files()
        logger.info(f"Found {len(analysis_files)} analysis results to validate")

        results: List[ProcessingStatus] = []
        for file_path in analysis_files:
            try:
                # Read analysis result
                analysis_data = self.storage.read_json_file(file_path)

                # Parse into AnalysisResult model
                analysis_result = AnalysisResult.model_validate(analysis_data)

                document_id = analysis_result.document_id

                if not analysis_result.conditions:
                    logger.warning(f"No conditions found in {file_path.name}")
                    status = ProcessingStatus(
                        document_id=document_id,
                        status="warning",
                        message="No conditions found to validate",
                        output_file=None,
                    )
                    results.append(status)
                    continue

                # Log number of conditions to validate
                logger.info(f"Validating {len(analysis_result.conditions)} conditions from {file_path.name}")

                # Validate HCC relevance determinations
                validation_result = self.validator.validate(analysis_result)

                # Log summary of validation
                compliant = sum(1 for c in validation_result.conditions if c.is_compliant)
                logger.info(
                    f"Found {compliant} compliant conditions out of {len(validation_result.conditions)} total"
                )

                # Save results
                output_filename = f"{file_path.stem}_validated.json"
                self.storage.save_result(validation_result, output_filename)

                status = ProcessingStatus(
                    document_id=document_id,
                    status="success",
                    message=f"Validation completed. Found {compliant} compliant conditions.",
                    output_file=output_filename,
                )
                results.append(status)
                logger.info(f"Successfully validated {file_path.name}")

            except Exception as e:
                logger.error(f"Error validating {file_path.name}: {str(e)}")
                status = ProcessingStatus(
                    document_id=file_path.name,
                    status="error",
                    message=f"Error: {str(e)}",
                    output_file=None,
                )
                results.append(status)

        # Save processing summary
        summary = {
            "total": len(results),
            "successful": sum(1 for r in results if r.status == "success"),
            "warnings": sum(1 for r in results if r.status == "warning"),
            "failed": sum(1 for r in results if r.status == "error"),
            "results": [r.model_dump() for r in results],
        }

        with open(self.output_dir / "validation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return results


async def run_service(mode: str) -> None:
    """
    Run the validator service in the specified mode.

    Args:
        mode: Service mode ('batch' for local file processing, 'consumer' for message queue)
    """
    try:
        if mode == "batch":
            # Process local files in batch mode
            input_dir = os.environ.get("INPUT_DIR", "./data")
            output_dir = os.environ.get("OUTPUT_DIR", "./output")
            hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

            logger.info(
                f"Starting validation service in batch mode with input_dir={input_dir}, "
                f"output_dir={output_dir}, hcc_codes_path={hcc_codes_path}"
            )

            service = ValidationService(input_dir, output_dir, hcc_codes_path)
            service.process_analysis_results()

        elif mode == "consumer":
            # Run as message consumer
            await run_consumer()

        elif mode == "both":
            # First process local files, then run as consumer
            input_dir = os.environ.get("INPUT_DIR", "./data")
            output_dir = os.environ.get("OUTPUT_DIR", "./output")
            hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

            logger.info(
                f"Starting validation service in both modes with input_dir={input_dir}, "
                f"output_dir={output_dir}, hcc_codes_path={hcc_codes_path}"
            )

            service = ValidationService(input_dir, output_dir, hcc_codes_path)
            service.process_analysis_results()

            # Then start the consumer
            await run_consumer()
        else:
            logger.error(f"Unknown mode: {mode}")
    except Exception as e:
        logger.exception(f"Error running service: {str(e)}")


def main() -> None:
    """Entry point for the service."""
    # Define command line arguments
    parser = argparse.ArgumentParser(description="HCC Validator Service")
    parser.add_argument(
        "--mode",
        choices=["batch", "consumer", "both"],
        default="both",
        help="Service mode (batch for local files, consumer for message queue, both for both)"
    )

    # Parse arguments
    args = parser.parse_args()

    try:
        # Run service with specified mode
        asyncio.run(run_service(args.mode))
    except KeyboardInterrupt:
        logger.info("Service interrupted")


if __name__ == "__main__":
    main()