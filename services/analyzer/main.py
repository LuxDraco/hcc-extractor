"""
Main module for the HCC Analyzer Service.

This module serves as the entry point for the analyzer service, which is responsible
for determining the HCC relevance of medical conditions extracted from clinical notes.
It uses LangGraph and Vertex AI Gemini 1.5 Flash to perform this analysis.
"""

import argparse
import asyncio
import logging
import os
import sys
from typing import List

from analyzer.message_consumer import run_consumer
from analyzer.models.condition import ProcessingStatus
from analyzer.storage.local import LocalStorageManager
from analyzer.graph.pipeline import AnalysisPipeline

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class AnalysisService:
    """Service for analyzing medical conditions and determining HCC relevance."""

    def __init__(
            self,
            input_dir: str,
            output_dir: str,
            hcc_codes_path: str
    ) -> None:
        """
        Initialize the analysis service.

        Args:
            input_dir: Directory containing input extraction results
            output_dir: Directory where analysis results will be saved
            hcc_codes_path: Path to the CSV file containing HCC codes
        """
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.hcc_codes_path = hcc_codes_path
        self.storage = LocalStorageManager(self.input_dir, self.output_dir)
        self.pipeline = AnalysisPipeline(hcc_codes_path=self.hcc_codes_path)

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        logger.info(
            f"Initialized analysis service with HCC codes from {hcc_codes_path}"
        )

    def process_extractions(self) -> List[ProcessingStatus]:
        """
        Process all extraction results in the input directory.

        Returns:
            List of processing status objects for each extraction result
        """
        extraction_files = self.storage.list_input_files()
        logger.info(f"Found {len(extraction_files)} extraction results to process")

        results = []
        for file_path in extraction_files:
            try:
                # Read extraction result from file
                extraction_data = self.storage.read_json_file(file_path)

                # Extract document ID and conditions
                document_id = extraction_data.get("document_id", file_path.stem)
                conditions_data = extraction_data.get("conditions", [])

                if not conditions_data:
                    logger.warning(f"No conditions found in {file_path.name}")
                    results.append(
                        ProcessingStatus(
                            document_id=document_id,
                            status="warning",
                            message="No conditions found to analyze",
                            output_file=None,
                        )
                    )
                    continue

                # Convert to condition objects
                from analyzer.models.condition import Condition
                conditions = [
                    Condition(**cond_data) for cond_data in conditions_data
                ]

                # Process conditions to determine HCC relevance
                logger.info(f"Analyzing {len(conditions)} conditions from {file_path.name}")
                analysis_result = self.pipeline.process(document_id, conditions)

                # Log summary of analysis
                hcc_relevant = sum(1 for c in analysis_result.conditions if c.hcc_relevant)
                logger.info(
                    f"Found {hcc_relevant} HCC-relevant conditions out of {len(analysis_result.conditions)} total"
                )

                # Save results
                file_path_tmp = file_path.stem
                file_path_tmp = file_path_tmp.replace("extracted", "analyzed")
                # output_filename = f"{file_path_tmp}_analyzed.json"
                output_filename = file_path_tmp + ".json"
                self.storage.save_result(analysis_result, output_filename)

                results.append(
                    ProcessingStatus(
                        document_id=document_id,
                        status="success",
                        message=f"Analysis completed. Found {hcc_relevant} HCC-relevant conditions.",
                        output_file=output_filename,
                    )
                )
                logger.info(f"Successfully analyzed {file_path.name}")

            except Exception as e:
                logger.exception(f"Error analyzing {file_path.name}: {str(e)}")
                results.append(
                    ProcessingStatus(
                        document_id=file_path.name,
                        status="error",
                        message=f"Error: {str(e)}",
                        output_file=None,
                    )
                )

        # Log summary
        logger.info(f"Processed {len(results)} extraction results")
        logger.info(f"Successful: {sum(1 for r in results if r.status == 'success')}")
        logger.info(f"Warnings: {sum(1 for r in results if r.status == 'warning')}")
        logger.info(f"Failed: {sum(1 for r in results if r.status == 'error')}")

        return results


async def run_service(mode: str) -> None:
    """
    Run the analyzer service in the specified mode.

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
                f"Starting analysis service in batch mode with input_dir={input_dir}, "
                f"output_dir={output_dir}, hcc_codes_path={hcc_codes_path}"
            )

            service = AnalysisService(input_dir, output_dir, hcc_codes_path)
            service.process_extractions()

        elif mode == "consumer":
            # Run as message consumer
            await run_consumer()

        elif mode == "both":
            # First process local files, then run as consumer
            input_dir = os.environ.get("INPUT_DIR", "./data")
            output_dir = os.environ.get("OUTPUT_DIR", "./output")
            hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

            logger.info(
                f"Starting analysis service in both modes with input_dir={input_dir}, "
                f"output_dir={output_dir}, hcc_codes_path={hcc_codes_path}"
            )

            service = AnalysisService(input_dir, output_dir, hcc_codes_path)
            service.process_extractions()

            # Then start the consumer
            await run_consumer()
        else:
            logger.error(f"Unknown mode: {mode}")
    except Exception as e:
        logger.exception(f"Error running service: {str(e)}")


def main() -> None:
    """Entry point for the service."""
    # Define command line arguments
    parser = argparse.ArgumentParser(description="HCC Analyzer Service")
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