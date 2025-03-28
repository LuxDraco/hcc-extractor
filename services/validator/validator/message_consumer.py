"""
Message consumer for the HCC Validator Service.

This module provides functionality for consuming analysis messages from RabbitMQ
and validating HCC relevance determinations for compliance.
"""

import asyncio
import datetime
import json
import logging
import os
import sys
from datetime import timezone
from typing import Dict, Any, Optional

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from dotenv import load_dotenv

from validator.data.code_repository import CodeRepository
from validator.db.database_integration import db_updater
from validator.db.models.document import ProcessingStatus
from validator.models.condition import AnalysisResult
from validator.storage.local import LocalStorageManager
from validator.validator.hcc_validator import HCCValidator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)

load_dotenv()


class MessageConsumer:
    """Consumer for processing messages from RabbitMQ."""

    def __init__(
            self,
            host: str,
            port: int = 5672,
            username: str = "guest",
            password: str = "guest",
            queue: str = "validator-events",
            exchange: str = "hcc-extractor",
            virtual_host: str = "/",
            input_dir: str = "./data",
            output_dir: str = "./output",
            hcc_codes_path: str = "./data/HCC_relevant_codes.csv",
    ) -> None:
        """
        Initialize the message consumer.

        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            queue: Queue name to consume from
            exchange: Exchange name
            virtual_host: RabbitMQ virtual host
            input_dir: Directory for input documents
            output_dir: Directory for output results
            hcc_codes_path: Path to the CSV file containing HCC codes
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.queue_name = queue
        self.exchange_name = exchange
        self.virtual_host = virtual_host
        self.input_dir = input_dir
        self.output_dir = output_dir
        self.hcc_codes_path = hcc_codes_path

        # Initialize components
        self.storage = LocalStorageManager(self.input_dir, self.output_dir)
        self.code_repository = CodeRepository(self.hcc_codes_path)
        self.validator = HCCValidator(self.code_repository)

        # RabbitMQ connection and channel
        self.connection: Optional[aio_pika.Connection] = None
        self.channel: Optional[aio_pika.Channel] = None
        self.queue: Optional[aio_pika.Queue] = None
        self.exchange: Optional[aio_pika.Exchange] = None

    async def connect(self) -> None:
        """
        Connect to RabbitMQ and set up the channel and queue.

        Raises:
            ConnectionError: If connection fails
        """
        try:
            # Create connection string
            host = self.virtual_host.replace("/", "%2F")
            connection_string = f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{host}"
            logging.info(f"Connecting to RabbitMQ at {connection_string}")

            # Connect to RabbitMQ
            self.connection = await aio_pika.connect_robust(connection_string)

            # Create channel
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1)

            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                self.exchange_name,
                ExchangeType.TOPIC,
                durable=True
            )

            # Declare queue
            self.queue = await self.channel.declare_queue(
                self.queue_name,
                durable=True
            )

            # Bind queue to exchange with routing keys for analysis completed messages
            await self.queue.bind(self.exchange, routing_key="document.analysis.completed")

            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise ConnectionError(f"Failed to connect to RabbitMQ: {str(e)}")

    async def start_consuming(self) -> None:
        """
        Start consuming messages from the queue.

        This method runs indefinitely, processing incoming messages.
        """
        if not self.connection or not self.channel or not self.queue:
            await self.connect()

        logger.info(f"Starting to consume messages from queue '{self.queue_name}'")

        # Set up message handler
        await self.queue.consume(self._process_message)

        # Keep the consumer running
        try:
            while True:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Consumer was cancelled, shutting down")
        except Exception as e:
            logger.error(f"Error in consumer: {str(e)}")
        finally:
            await self.close()

    async def _process_message(self, message: AbstractIncomingMessage) -> None:
        """
        Process an incoming message.

        Args:
            message: The incoming message from RabbitMQ
        """
        async with message.process():
            try:
                # Decode message body
                body = message.body.decode()
                logger.info(f"Received message: {body[:250]}...")

                # Parse message content
                content = json.loads(body)
                message_type = content.get("message_type")

                # Handle different message types
                if message_type == "analysis.completed":
                    await self._handle_analysis_completed(content)
                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                logger.error("Failed to decode message as JSON")
            except Exception as e:
                logger.exception(f"Error processing message: {str(e)}")

    async def _handle_analysis_completed(
            self,
            content: Dict[str, Any],
    ) -> None:
        """
        Handle an analysis.completed message.

        Args:
            content: Message content
        """
        document_id = content.get("document_id")
        analysis_result_path = content.get("analysis_result_path")
        hcc_relevant_conditions = content.get("hcc_relevant_conditions", 0)

        if not document_id or not analysis_result_path:
            logger.error("Missing required fields in analysis.completed message")
            return

        try:
            logger.info(f"Processing analysis result: {document_id}, path: {analysis_result_path}")

            # Actualizar el estado del documento en la base de datos a VALIDATING
            db_updater.update_document_validation_status(
                document_id=document_id,
                status=ProcessingStatus.VALIDATING
            )

            # Read analysis result from file
            input_filepath = os.path.join(self.output_dir, analysis_result_path)

            if not os.path.exists(input_filepath):
                logger.error(f"Analysis result file not found: {input_filepath}")
                # Actualizar estado a FAILED si no se encuentra el archivo
                db_updater.update_document_validation_status(
                    document_id=document_id,
                    status=ProcessingStatus.FAILED
                )
                return

            with open(input_filepath, 'r') as f:
                analysis_data = json.load(f)

            # Parse into AnalysisResult model
            analysis_result = AnalysisResult.model_validate(analysis_data)

            # Check if there are conditions to validate
            if not analysis_result.conditions:
                logger.warning(f"No conditions found in {analysis_result_path}")
                return

            # Log number of conditions to validate
            logger.info(f"Validating {len(analysis_result.conditions)} conditions from {analysis_result_path}")

            # Validate HCC relevance determinations
            validation_result = self.validator.validate(analysis_result)

            # Count compliant conditions
            compliant_count = sum(1 for c in validation_result.conditions if c.is_compliant)

            # Save results
            output_filename = f"{document_id}_validated.json"
            output_path = self.storage.save_result(validation_result, output_filename)

            logger.info(
                f"Validation completed for document {document_id}. "
                f"Found {compliant_count} compliant conditions out of {len(validation_result.conditions)} total."
            )

            db_updater.update_document_validation_status(
                document_id=document_id,
                compliant_conditions=compliant_count,
                validation_result_path=output_filename,
                status=ProcessingStatus.COMPLETED,
                processing_completed_at=datetime.datetime.now(timezone.utc)
            )

            # Publish validation completed message
            await self._publish_validation_completed(
                document_id=document_id,
                validation_result_path=output_filename,
                compliant_conditions=compliant_count,
                total_conditions=len(validation_result.conditions)
            )

        except Exception as e:
            logger.exception(f"Error processing analysis result {document_id}: {str(e)}")
            db_updater.update_document_validation_status(
                document_id=document_id,
                status=ProcessingStatus.FAILED
            )
            # Could publish an error message back to the queue here

    async def _publish_validation_completed(
            self, document_id: str, validation_result_path: str,
            compliant_conditions: int, total_conditions: int
    ) -> None:
        """
        Publish a validation.completed message.

        Args:
            document_id: Document ID
            validation_result_path: Path to the validation result
            compliant_conditions: Number of compliant conditions
            total_conditions: Total number of conditions validated
        """
        if not self.channel or not self.exchange:
            logger.error("Cannot publish message: not connected to RabbitMQ")
            return

        try:
            # Create message
            message_data = {
                "message_type": "validation.completed",
                "document_id": document_id,
                "validation_result_path": validation_result_path,
                "compliant_conditions": compliant_conditions,
                "total_conditions": total_conditions,
                "timestamp": asyncio.get_event_loop().time()
            }

            # Convert to JSON and create message
            message_json = json.dumps(message_data)
            message = Message(
                body=message_json.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json"
            )

            # Publish to exchange
            await self.exchange.publish(
                message,
                routing_key="document.validation.completed"
            )

            logger.info(f"Published validation.completed for document {document_id}")

        except Exception as e:
            logger.error(f"Error publishing validation.completed message: {str(e)}")

    async def close(self) -> None:
        """
        Close the connection to RabbitMQ.

        This should be called when shutting down the service.
        """
        if self.connection:
            try:
                await self.connection.close()
                logger.info("Closed RabbitMQ connection")
            except Exception as e:
                logger.error(f"Error closing RabbitMQ connection: {str(e)}")

        self.connection = None
        self.channel = None
        self.queue = None
        self.exchange = None


async def run_consumer():
    """Run the message consumer."""
    # Get configuration from environment variables or use defaults
    host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    port = int(os.environ.get("RABBITMQ_PORT", "5672"))
    username = os.environ.get("RABBITMQ_USER", "guest")
    password = os.environ.get("RABBITMQ_PASSWORD", "guest")
    queue = os.environ.get("RABBITMQ_QUEUE", "validator-events")
    exchange = os.environ.get("RABBITMQ_EXCHANGE", "hcc-extractor")
    virtual_host = os.environ.get("RABBITMQ_VHOST", "/")
    input_dir = os.environ.get("INPUT_DIR", "./data")
    output_dir = os.environ.get("OUTPUT_DIR", "./output")
    hcc_codes_path = os.environ.get("HCC_CODES_PATH", "./data/HCC_relevant_codes.csv")

    # Create and start consumer
    consumer = MessageConsumer(
        host=host,
        port=port,
        username=username,
        password=password,
        queue=queue,
        exchange=exchange,
        virtual_host=virtual_host,
        input_dir=input_dir,
        output_dir=output_dir,
        hcc_codes_path=hcc_codes_path,
    )

    try:
        await consumer.connect()
        await consumer.start_consuming()
    except asyncio.CancelledError:
        logger.info("Consumer cancelled, shutting down")
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down")
    except Exception as e:
        logger.exception(f"Error running consumer: {str(e)}")
    finally:
        await consumer.close()


if __name__ == "__main__":
    asyncio.run(run_consumer())
