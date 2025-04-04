"""
Database integration for the Validator service.

This module contains the necessary functions to update the state of documents
in the database as they progress through the processing pipeline.
"""
import logging
import os
import uuid

from dotenv import load_dotenv
from sqlalchemy import create_engine, update
from sqlalchemy.orm import sessionmaker

from validator.db.models.document import ProcessingStatus

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()


class DatabaseUpdater:
    """Class to handle database updates."""

    def __init__(
            self,
            host=None,
            port=None,
            user=None,
            password=None,
            db_name=None
    ):
        """
        Initialize the database updater.

        Args:
            host: Database host
            port: Database port
            user: Database user
            password: Database password
            db_name: Database name
        """
        self.host = host or os.environ.get("POSTGRES_HOST", "postgres")
        self.port = port or os.environ.get("POSTGRES_PORT", "5432")
        self.user = user or os.environ.get("POSTGRES_USER", "postgres")
        self.password = password or "postgres"  # Default value
        self.db_name = db_name or os.environ.get("POSTGRES_DB", "hcc_extractor")

        self.engine = self._create_engine()
        self.Session = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)

    def _create_engine(self):
        """Create and return a database connection."""
        connection_string = f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.db_name}"
        logger.info(f"Connecting to database at {self.host}:{self.port}")
        return create_engine(connection_string)

    def update_document_validation_status(
            self, document_id, compliant_conditions=None,
            validation_result_path=None,
            status: ProcessingStatus = ProcessingStatus.VALIDATING,
            processing_completed_at=None
    ):
        """
        Update the document status during validation.

        Args:
            document_id: Document ID
            compliant_conditions: Number of conditions that comply with the rules
            validation_result_path: Path to the validation results file
            status: Current processing status
        """
        try:
            session = self.Session()
            # Import here to avoid circular import issues
            from validator.db.models.document import Document, ProcessingStatus

            # Convert status to enum if it's a string
            if isinstance(status, str):
                status = ProcessingStatus[status]

            # Prepare values to update
            values = {"status": status}

            if validation_result_path is not None:
                values["validation_result_path"] = validation_result_path

            # If status is completed, update the is_processed flag
            if status == ProcessingStatus.COMPLETED:
                values["is_processed"] = True

            if processing_completed_at is not None:
                values["processing_completed_at"] = processing_completed_at

            # Create and execute the update
            stmt = (
                update(Document)
                .where(Document.id == uuid.UUID(document_id))
                .values(**values)
            )

            session.execute(stmt)
            session.commit()
            logger.info(f"Updated document {document_id} status to {status}")

        except Exception as e:
            logger.error(f"Error updating document status: {str(e)}")
            if session:
                session.rollback()
        finally:
            if session:
                session.close()


# Global instance for easy access
db_updater = DatabaseUpdater()
