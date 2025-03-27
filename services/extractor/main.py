"""
Main module for the HCC Extractor Service.

This module serves as the entry point for the extractor service, which is responsible
for consuming clinical progress notes, parsing them, extracting medical conditions,
and determining which conditions are HCC-relevant.
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from extractor.message_consumer import run_consumer
from extractor.services.extraction import ExtractionService
from extractor.utils.hcc_utils import hcc_manager

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def process_local_files() -> None:
    """Run the extraction service in batch mode to process local files."""
    # Get directories from environment variables or use defaults
    input_dir = os.environ.get("INPUT_DIR", "./data")
    output_dir = os.environ.get("OUTPUT_DIR", "./output")
    hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

    # Determine whether to use LangGraph
    use_langgraph_str = os.environ.get("USE_LANGGRAPH", "true")
    use_langgraph = use_langgraph_str.lower() in ("true", "1", "yes")

    logger.info(
        f"Starting extraction service in batch mode with input_dir={input_dir}, output_dir={output_dir}, "
        f"use_langgraph={use_langgraph}, hcc_codes_path={hcc_codes_path}"
    )

    # Initialize HCC codes manager
    try:
        hcc_manager.csv_path = hcc_codes_path
        hcc_manager.load_hcc_codes()
        logger.info(f"Loaded {len(hcc_manager.get_all_hcc_codes())} HCC-relevant codes")
    except Exception as e:
        logger.error(f"Failed to load HCC codes: {e}")
        sys.exit(1)

    # Process documents
    service = ExtractionService(
        input_dir,
        output_dir,
        use_langgraph=use_langgraph,
        hcc_codes_path=hcc_codes_path
    )
    results = service.process_documents()

    logger.info(f"Processed {len(results)} documents")
    logger.info(f"Successful: {sum(1 for r in results if r.status == 'success')}")
    logger.info(f"Failed: {sum(1 for r in results if r.status == 'error')}")


def process_single_file(file_path: str) -> None:
    """
    Process a single file.

    Args:
        file_path: Path to the file to process
    """
    # Get directories from environment variables or use defaults
    output_dir = os.environ.get("OUTPUT_DIR", "./output")
    hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

    # Determine whether to use LangGraph
    use_langgraph_str = os.environ.get("USE_LANGGRAPH", "true")
    use_langgraph = use_langgraph_str.lower() in ("true", "1", "yes")

    logger.info(
        f"Processing single file: {file_path}, output_dir={output_dir}, "
        f"use_langgraph={use_langgraph}, hcc_codes_path={hcc_codes_path}"
    )

    # Process the file
    service = ExtractionService(
        Path(file_path).parent,
        output_dir,
        use_langgraph=use_langgraph,
        hcc_codes_path=hcc_codes_path
    )
    result = service.process_single_document(file_path)

    if result.status == "success":
        logger.info(f"Successfully processed {file_path}: {result.message}")
    else:
        logger.error(f"Failed to process {file_path}: {result.message}")


async def run_service(mode: str, file_path: str = None) -> None:
    """
    Run the extractor service in the specified mode.

    Args:
        mode: Service mode ('batch' for local file processing, 'consumer' for message queue)
        file_path: Path to a single file to process (only for 'file' mode)
    """
    try:
        if mode == "batch":
            # Process local files in batch mode
            process_local_files()
        elif mode == "file" and file_path:
            # Process a single file
            process_single_file(file_path)
        elif mode == "consumer":
            # Run as message consumer
            await run_consumer()
        elif mode == "both":
            # First process local files, then run as consumer
            process_local_files()
            await run_consumer()
        else:
            logger.error(f"Unknown mode: {mode} or missing file path for 'file' mode")
    except Exception as e:
        logger.exception(f"Error running service: {str(e)}")


def main() -> None:
    """Entry point for the service."""
    # Define command line arguments
    parser = argparse.ArgumentParser(description="HCC Extractor Service")
    parser.add_argument(
        "--mode",
        choices=["batch", "consumer", "both", "file"],
        default="both",
        help="Service mode (batch for local files, consumer for message queue, file for single file)"
    )
    parser.add_argument(
        "--file",
        type=str,
        help="Path to a single file to process (only for 'file' mode)"
    )

    # Parse arguments
    args = parser.parse_args()

    # Validate arguments
    if args.mode == "file" and not args.file:
        parser.error("--file argument is required for 'file' mode")

    try:
        # Run service with specified mode
        asyncio.run(run_service(args.mode, args.file))
    except KeyboardInterrupt:
        logger.info("Service interrupted")


if __name__ == "__main__":
    main()