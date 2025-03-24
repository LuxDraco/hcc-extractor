"""
Main module for the HCC Analyzer Service.

This module serves as the entry point for the analyzer service, which is responsible
for determining the HCC relevance of medical conditions extracted from clinical notes.
It uses LangGraph and Vertex AI Gemini 1.5 Flash to perform this analysis.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Union

from app.graph.pipeline import AnalysisPipeline
from app.models.condition import Condition, ProcessingStatus
from app.storage.local import LocalStorageManager

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
            input_dir: Union[str, Path],
            output_dir: Union[str, Path],
            hcc_codes_path: Union[str, Path]
    ) -> None:
        """
        Initialize the analysis service.

        Args:
            input_dir: Directory containing input extraction results
            output_dir: Directory where analysis results will be saved
            hcc_codes_path: Path to the CSV file containing HCC codes
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.hcc_codes_path = Path(hcc_codes_path)
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

        results: List[ProcessingStatus] = []
        for file_path in extraction_files:
            try:
                # Read extraction result
                extraction_data = self.storage.read_json_file(file_path)

                # Extract conditions from the extraction result
                conditions = [
                    Condition.model_validate(cond)
                    for cond in extraction_data.get("conditions", [])
                ]

                document_id = extraction_data.get("document_id", file_path.stem)

                if not conditions:
                    logger.warning(f"No conditions found in {file_path.name}")
                    status = ProcessingStatus(
                        document_id=document_id,
                        status="warning",
                        message="No conditions found to analyze",
                        output_file=None,
                    )
                    results.append(status)
                    continue

                # Log number of conditions to analyze
                logger.info(f"Analyzing {len(conditions)} conditions from {file_path.name}")

                # Process conditions to determine HCC relevance
                analysis_result = self.pipeline.process(document_id, conditions)

                # Log summary of analysis
                hcc_relevant = sum(1 for c in analysis_result.conditions if c.hcc_relevant)
                logger.info(
                    f"Found {hcc_relevant} HCC-relevant conditions out of {len(analysis_result.conditions)} total"
                )

                # Save results
                output_filename = f"{file_path.stem}_analyzed.json"
                self.storage.save_result(analysis_result, output_filename)

                status = ProcessingStatus(
                    document_id=document_id,
                    status="success",
                    message=f"Analysis completed. Found {hcc_relevant} HCC-relevant conditions.",
                    output_file=output_filename,
                )
                results.append(status)
                logger.info(f"Successfully analyzed {file_path.name}")

            except Exception as e:
                logger.error(f"Error analyzing {file_path.name}: {str(e)}")
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

        with open(self.output_dir / "analysis_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return results


def main() -> None:
    """Run the analysis service."""
    # Get directories from environment variables or use defaults
    input_dir = os.environ.get("INPUT_DIR", "./data")
    output_dir = os.environ.get("OUTPUT_DIR", "./output")
    hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

    logger.info(
        f"Starting analysis service with input_dir={input_dir}, "
        f"output_dir={output_dir}, hcc_codes_path={hcc_codes_path}"
    )

    service = AnalysisService(input_dir, output_dir, hcc_codes_path)
    results = service.process_extractions()

    logger.info(f"Processed {len(results)} extraction results")
    logger.info(f"Successful: {sum(1 for r in results if r.status == 'success')}")
    logger.info(f"Warnings: {sum(1 for r in results if r.status == 'warning')}")
    logger.info(f"Failed: {sum(1 for r in results if r.status == 'error')}")


if __name__ == "__main__":
    main()
