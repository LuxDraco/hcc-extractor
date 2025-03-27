"""
Message consumer for the HCC Analyzer Service.

This module provides functionality for consuming extraction messages from RabbitMQ
and analyzing conditions for HCC relevance.
"""

import asyncio
import json
import logging
import os
import sys
from typing import Dict, Any, Optional, List

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractIncomingMessage

from analyzer.db.models.document import ProcessingStatus
from analyzer.graph.pipeline import AnalysisPipeline
from analyzer.models.condition import Condition, AnalysisResult
from analyzer.storage.local import LocalStorageManager
from analyzer.db.database_integration import db_updater

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class MessageConsumer:
    """Consumer for processing messages from RabbitMQ."""

    def __init__(
            self,
            host: str,
            port: int = 5672,
            username: str = "guest",
            password: str = "guest",
            queue: str = "document-events",
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
        self.pipeline = AnalysisPipeline(hcc_codes_path=self.hcc_codes_path)

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
            #connection_string = f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{self.virtual_host}"
            connection_string = f"amqp://hccuser:hccpass@rabbitmq:5672/%2F"

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

            # Bind queue to exchange with routing keys for extraction completed messages
            await self.queue.bind(self.exchange, routing_key="document.extraction.completed")

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
                if message_type == "extraction.completed":
                    await self._handle_extraction_completed(content)
                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                logger.error("Failed to decode message as JSON")
            except Exception as e:
                logger.exception(f"Error processing message: {str(e)}")

    async def _handle_extraction_completed(
            self,
            content: Dict[str, Any],
    ) -> None:
        """
        Handle an extraction.completed message.

        Args:
            content: Message content
        """
        document_id = content.get("document_id")
        extraction_result_path = content.get("extraction_result_path")
        total_conditions = content.get("total_conditions", 0)

        if not document_id or not extraction_result_path:
            logger.error("Missing required fields in extraction.completed message")
            return

        try:
            logger.info(f"Processing extraction result: {document_id}, path: {extraction_result_path}")

            # Update document status in database to ANALYZING
            db_updater.update_document_analysis_status(
                document_id=document_id,
                total_conditions=total_conditions,
                status=ProcessingStatus.ANALYZING,
                extraction_result_path=str(extraction_result_path)
            )

            # Read extraction result from file or from message
            extraction_json = None

            # First try to get it from the message if it includes the data
            if "extracted_content" in content:
                logging.info("Extracted content found in message")
                extracted_content = content.get("extracted_content")
                if extracted_content:
                    # Create input file for the extraction result
                    input_filename = os.path.join(self.output_dir, extraction_result_path)
                    os.makedirs(os.path.dirname(input_filename), exist_ok=True)

                    # Parse the conditions from the extraction content
                    conditions_data = self._parse_conditions_from_content(extracted_content)
                    if conditions_data:
                        extraction_json = {
                            "document_id": document_id,
                            "conditions": conditions_data,
                            "metadata": {"total_conditions": len(conditions_data)}
                        }

            # If not available in message, try to read from file
            if not extraction_json:
                logging.info("Extracted content not found in message, trying to read from file")
                # Look for file in input directory
                input_filepath = os.path.join(self.output_dir, extraction_result_path)
                if os.path.exists(input_filepath):
                    with open(input_filepath, 'r') as f:
                        extraction_json = json.load(f)
                else:
                    logger.error(f"Extraction result file not found: {input_filepath}")

                    # Update status to FAILED if file not found
                    db_updater.update_document_analysis_status(
                        document_id=document_id,
                        status=ProcessingStatus.FAILED
                    )
                    return

            # Convert JSON to Condition objects
            conditions = []
            for cond_data in extraction_json.get("conditions", []):
                condition = Condition(
                    id=cond_data.get("id"),
                    name=cond_data.get("name"),
                    icd_code=cond_data.get("icd_code"),
                    icd_description=cond_data.get("icd_description"),
                    details=cond_data.get("details"),
                    confidence=cond_data.get("confidence", 0.0),
                    metadata=cond_data.get("metadata", {}),
                    # Initialize HCC fields as empty/default
                    hcc_relevant=False,
                    hcc_code=None,
                    hcc_category=None,
                    reasoning=None,
                )
                conditions.append(condition)

            # Process conditions to determine HCC relevance
            analysis_result = self.pipeline.process(document_id, conditions)

            # Save results
            output_filename = f"{document_id}_analyzed.json"
            output_path = self.storage.save_result(analysis_result, output_filename)

            # Count HCC-relevant conditions
            hcc_relevant_count = sum(1 for c in analysis_result.conditions if c.hcc_relevant)

            logger.info(
                f"Analysis completed for document {document_id}. Found {hcc_relevant_count} HCC-relevant conditions."
            )

            # Update document status and analysis information in database
            db_updater.update_document_analysis_status(
                document_id=document_id,
                total_conditions=len(analysis_result.conditions),
                hcc_relevant_conditions=hcc_relevant_count,
                analysis_result_path=output_filename,
                status=ProcessingStatus.ANALYZING  # At this point, we've completed the analysis
            )

            # Publish analysis completed message
            await self._publish_analysis_completed(
                document_id=document_id,
                analysis_result_path=output_filename,
                hcc_relevant_conditions=hcc_relevant_count
            )

        except Exception as e:
            logger.exception(f"Error processing extraction result {document_id}: {str(e)}")

            # Update status to FAILED in case of error
            db_updater.update_document_analysis_status(
                document_id=document_id,
                status=ProcessingStatus.FAILED
            )
            # Could publish an error message back to the queue here

    def _parse_conditions_from_content(self, content: str) -> List[Dict[str, Any]]:
        """
        Parse conditions from document content if extraction result is not available.
        This is a fallback method and not the primary path.

        Args:
            content: Document content

        Returns:
            List of condition dictionaries
        """
        try:
            # Try to parse as JSON first
            data = json.loads(content)
            if isinstance(data, dict) and "conditions" in data:
                return data["conditions"]

            # If not valid extraction result JSON, return empty list
            return []
        except:
            # Not JSON, return empty list
            return []

    async def _publish_analysis_completed(
            self, document_id: str, analysis_result_path: str, hcc_relevant_conditions: int
    ) -> None:
        """
        Publish an analysis.completed message.

        Args:
            document_id: Document ID
            analysis_result_path: Path to the analysis result
            hcc_relevant_conditions: Number of HCC-relevant conditions
        """
        if not self.channel or not self.exchange:
            logger.error("Cannot publish message: not connected to RabbitMQ")
            return

        try:
            # Create message
            message_data = {
                "message_type": "analysis.completed",
                "document_id": document_id,
                "analysis_result_path": analysis_result_path,
                "hcc_relevant_conditions": hcc_relevant_conditions,
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
                routing_key="document.analysis.completed"
            )

            logger.info(f"Published analysis.completed for document {document_id}")

        except Exception as e:
            logger.error(f"Error publishing analysis.completed message: {str(e)}")

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
    queue = os.environ.get("RABBITMQ_QUEUE", "document-events")
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