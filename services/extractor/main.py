"""
Main module for the HCC Extractor Service.

This module serves as the entry point for the extractor service, which is responsible
for consuming clinical progress notes, parsing them, and forwarding the extracted
information to the next stage in the pipeline.
"""

import argparse
import asyncio
import logging
import os
import sys

from extractor.message_consumer import run_consumer
from extractor.services.extraction import ExtractionService

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

    # Determine whether to use LangGraph
    use_langgraph_str = os.environ.get("USE_LANGGRAPH", "true")
    use_langgraph = use_langgraph_str.lower() in ("true", "1", "yes")

    logger.info(
        f"Starting extraction service in batch mode with input_dir={input_dir}, output_dir={output_dir}, "
        f"use_langgraph={use_langgraph}"
    )

    service = ExtractionService(input_dir, output_dir, use_langgraph=use_langgraph)
    results = service.process_documents()

    logger.info(f"Processed {len(results)} documents")
    logger.info(f"Successful: {sum(1 for r in results if r.status == 'success')}")
    logger.info(f"Failed: {sum(1 for r in results if r.status == 'error')}")


async def run_service(mode: str) -> None:
    """
    Run the extractor service in the specified mode.

    Args:
        mode: Service mode ('batch' for local file processing, 'consumer' for message queue)
    """
    try:
        if mode == "batch":
            # Process local files in batch mode
            process_local_files()
        elif mode == "consumer":
            # Run as message consumer
            await run_consumer()
        elif mode == "both":
            # First process local files, then run as consumer
            process_local_files()
            await run_consumer()
        else:
            logger.error(f"Unknown mode: {mode}")
    except Exception as e:
        logger.exception(f"Error running service: {str(e)}")


def main() -> None:
    """Entry point for the service."""
    # Define command line arguments
    parser = argparse.ArgumentParser(description="HCC Extractor Service")
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
