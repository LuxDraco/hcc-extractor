"""
Main module for the HCC Extractor Service.

This module serves as the entry point for the extractor service, which is responsible
for consuming clinical progress notes, parsing them, and forwarding the extracted
information to the next stage in the pipeline.
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import List, Union

from app.extractor.processor import DocumentProcessor
from app.models.document import (
    ProcessingStatus,
)
from app.storage.local import LocalStorageManager
from app.utils.document_parser import DocumentParser

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting medical conditions from clinical documents."""

    def __init__(
            self,
            input_dir: Union[str, Path],
            output_dir: Union[str, Path],
            use_langgraph: bool = True
    ) -> None:
        """
        Initialize the extraction service.

        Args:
            input_dir: Directory containing input clinical documents
            output_dir: Directory where extraction results will be saved
            use_langgraph: Whether to use LangGraph for extraction
        """
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.storage = LocalStorageManager(self.input_dir, self.output_dir)
        self.document_parser = DocumentParser()
        self.processor = DocumentProcessor(use_langgraph=use_langgraph)

        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)

        logger.info(
            f"Initialized extraction service with LangGraph {'enabled' if use_langgraph else 'disabled'}"
        )

    def process_documents(self) -> List[ProcessingStatus]:
        """
        Process all documents in the input directory.

        Returns:
            List of processing status objects for each document
        """
        documents = self.storage.list_input_documents()
        logger.info(f"Found {len(documents)} documents to process")

        results: List[ProcessingStatus] = []
        for doc_path in documents:
            try:
                # Read document content
                content = self.storage.read_document(doc_path)

                # Parse into structured format
                doc = self.document_parser.parse(content, doc_path.name)

                # Process document to extract conditions
                logger.info(f"Processing document: {doc_path.name}")
                extraction_result = self.processor.process(doc)

                # Log summary of extraction
                logger.info(
                    f"Extracted {len(extraction_result.conditions)} conditions from {doc_path.name}"
                )

                # Save results
                output_filename = f"{doc_path.stem}_extracted.json"
                self.storage.save_result(extraction_result, output_filename)

                status = ProcessingStatus(
                    document_id=doc.document_id,
                    status="success",
                    message=f"Document processed successfully. Extracted {len(extraction_result.conditions)} conditions.",
                    output_file=output_filename,
                )
                results.append(status)
                logger.info(f"Successfully processed {doc_path.name}")

            except Exception as e:
                logger.error(f"Error processing {doc_path.name}: {str(e)}")
                status = ProcessingStatus(
                    document_id=doc_path.name,
                    status="error",
                    message=f"Error: {str(e)}",
                    output_file=None,
                )
                results.append(status)

        # Save processing summary
        summary = {
            "total": len(results),
            "successful": sum(1 for r in results if r.status == "success"),
            "failed": sum(1 for r in results if r.status == "error"),
            "results": [r.dict() for r in results],
        }

        with open(self.output_dir / "processing_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        return results


def main() -> None:
    """Run the extraction service."""
    # Get directories from environment variables or use defaults
    input_dir = os.environ.get("INPUT_DIR", "./data")
    output_dir = os.environ.get("OUTPUT_DIR", "./output")

    # Determine whether to use LangGraph
    use_langgraph_str = os.environ.get("USE_LANGGRAPH", "true")
    use_langgraph = use_langgraph_str.lower() in ("true", "1", "yes")

    logger.info(
        f"Starting extraction service with input_dir={input_dir}, output_dir={output_dir}, "
        f"use_langgraph={use_langgraph}"
    )

    service = ExtractionService(input_dir, output_dir, use_langgraph=use_langgraph)
    results = service.process_documents()

    logger.info(f"Processed {len(results)} documents")
    logger.info(f"Successful: {sum(1 for r in results if r.status == 'success')}")
    logger.info(f"Failed: {sum(1 for r in results if r.status == 'error')}")


if __name__ == "__main__":
    main()
