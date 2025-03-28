"""
Message consumer for the HCC Extractor Service.

This module provides functionality for consuming messages from RabbitMQ
and processing documents based on message content.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from typing import Dict, Any, Optional

import aio_pika
from aio_pika import Message, DeliveryMode, ExchangeType
from aio_pika.abc import AbstractIncomingMessage
from sqlalchemy import update

from extractor.db.models.document import Document
from extractor.db.session import get_db_session
from extractor.extractor.processor import DocumentProcessor
from extractor.storage.local import LocalStorageManager
from extractor.utils.document_parser import DocumentParser

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
            username: str = "hccuser",
            password: str = "hccpass",
            queue: str = "extractor-events",
            exchange: str = "hcc-extractor",
            virtual_host: str = "/",
            input_dir: str = "./data",
            output_dir: str = "./output",
            use_langgraph: bool = True,
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
            use_langgraph: Whether to use LangGraph for extraction
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
        self.use_langgraph = use_langgraph

        # Initialize components
        self.storage = LocalStorageManager(self.input_dir, self.output_dir)
        self.document_parser = DocumentParser()
        self.processor = DocumentProcessor(use_langgraph=self.use_langgraph)

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
            self.connection = await aio_pika.connect_robust(
                connection_string,
                timeout=30.0,
            )

            # Create channel
            self.channel = await self.connection.channel()
            await self.channel.set_qos(prefetch_count=1, timeout=360, all_channels=True)

            # Declare exchange
            self.exchange = await self.channel.declare_exchange(
                name=self.exchange_name,
                type=ExchangeType.TOPIC,
                durable=True
            )

            # Declare queue
            self.queue = await self.channel.declare_queue(
                name=self.queue_name,
                durable=True
            )

            # Bind queue to exchange with appropriate routing keys
            # await self.queue.bind(self.exchange, routing_key="#")
            await self.queue.bind(
                self.exchange,
                routing_key="document.uploaded"
            )

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
        logging.info(f"Received message from queue '{self.queue_name}': {message.body[:100]}...")
        async with message.process():
            try:
                # Decode message body
                body = message.body.decode()
                logger.info(f"Received message: {body[:100]}...")

                # Parse message content
                content = json.loads(body)
                message_type = content.get("message_type")

                # Handle different message types
                if message_type == "document.uploaded":
                    await self._handle_document_uploaded(content)
                else:
                    logger.warning(f"Unknown message type: {message_type}")

            except json.JSONDecodeError:
                logger.error("Failed to decode message as JSON")
            except Exception as e:
                logger.exception(f"Error processing message: {str(e)}")

    async def _handle_document_uploaded(
            self,
            content: Dict[str, Any],
    ) -> Any:
        """
        Handle a document.uploaded message.

        Args:
            content: Message content
        """
        document_id = content.get("document_id")
        storage_path = content.get("storage_path")
        storage_type = content.get("storage_type")

        if not document_id or not storage_path or not storage_type:
            logger.error("Missing required fields in document.uploaded message")
            return

        document_content_tmp = content.get("document_content")

        if not document_content_tmp:
            storage_full = os.path.join(self.input_dir, storage_path)
            document_content_tmp = await self._read_file(storage_full)

        try:
            logger.info(f"Processing document: {document_id}, path: {storage_path}")

            # For local storage, read the document
            if storage_type == "LOCAL":

                # Read document content
                document_content = document_content_tmp

                # Parse document content
                doc = self.document_parser.parse(document_content, os.path.basename(storage_path))

                # Override document_id with the one from the message
                doc.document_id = document_id

                # Process document to extract conditions
                extraction_result = self.processor.process(doc)

                # Save to db
                logging.info(f"Updating document {document_id} in database")
                from uuid import UUID
                db = next(get_db_session())
                stmt = (
                    update(Document)
                    .where(Document.id == UUID(extraction_result.document_id))
                    .values(
                        total_conditions=len(extraction_result.conditions),
                        doc_metadata=extraction_result.metadata,
                    )
                )
                db.execute(stmt)
                db.commit()

                # Save results
                output_filename = f"{document_id}_extracted.json"
                await self._save_result(extraction_result, output_filename)

                logger.info(f"Document processed successfully: {document_id}")

                # Publish extraction completed message
                await self._publish_extraction_completed(
                    document_id=document_id,
                    extraction_result_path=f"{output_filename}",
                    total_conditions=len(extraction_result.conditions),
                    extracted_content=document_content
                )
            else:
                logger.error(f"Unsupported storage type: {storage_type}")

        except Exception as e:
            logger.exception(f"Error processing document {document_id}: {str(e)}")
            # Could publish an error message back to the queue here

    async def _read_file(self, path: str) -> str:
        """
        Read a file asynchronously.

        Args:
            path: Path to the file

        Returns:
            File content as string
        """
        async with aio_pika.pool.Pool(self.connection):
            loop = asyncio.get_event_loop()
            with open(path, "r", encoding="utf-8") as f:
                content = await loop.run_in_executor(None, f.read)
            return content

    async def _save_result(self, extraction_result, filename: str) -> None:
        """
        Save extraction result asynchronously.

        Args:
            extraction_result: Extraction result to save
            filename: Output filename
        """
        output_path = os.path.join(self.output_dir, filename)

        # Convert model to dict
        result_dict = extraction_result.dict()

        # Save to file
        async with aio_pika.pool.Pool(self.connection):
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None,
                lambda: self._write_json_file(self, output_path, result_dict)
            )

    @staticmethod
    def _write_json_file(self, path: str, data: Dict[str, Any]) -> None:
        """
        Write JSON data to a file.

        Args:
            path: Output file path
            data: Data to write
        """
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    async def _publish_extraction_completed(
            self, document_id: str, extraction_result_path: str, total_conditions: int, extracted_content: str
    ) -> None:
        """
        Publish an extraction.completed message.

        Args:
            document_id: Document ID
            extraction_result_path: Path to the extraction result
            total_conditions: Total number of conditions extracted
        """
        if not self.channel or not self.exchange:
            logger.error("Cannot publish message: not connected to RabbitMQ")
            return

        try:
            # Create message
            message_data = {
                "message_type": "document.extraction.completed",
                "document_id": document_id,
                "extraction_result_path": extraction_result_path,
                "total_conditions": total_conditions,
                # "extracted_content": extracted_content,
                # "timestamp": asyncio.get_event_loop().time()
            }

            # Convert to JSON and create message
            message_json = json.dumps(message_data)
            message = Message(
                body=message_json.encode(),
                delivery_mode=DeliveryMode.PERSISTENT,
                content_type="application/json",
                message_id=str(uuid.uuid4()),
                expiration=300
            )

            # Publish to exchange
            await self.exchange.publish(
                message,
                routing_key="document.extraction.completed"
            )

            logger.info(f"Published extraction.completed for document {document_id}")

        except Exception as e:
            logger.error(f"Error publishing extraction.completed message: {str(e)}")

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
    queue = os.environ.get("RABBITMQ_QUEUE", "extractor-events")
    exchange = os.environ.get("RABBITMQ_EXCHANGE", "hcc-extractor")
    virtual_host = os.environ.get("RABBITMQ_VHOST", "/")
    input_dir = os.environ.get("INPUT_DIR", "./data")
    output_dir = os.environ.get("OUTPUT_DIR", "./output")
    use_langgraph_str = os.environ.get("USE_LANGGRAPH", "true")
    use_langgraph = use_langgraph_str.lower() in ("true", "1", "yes")

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
        use_langgraph=use_langgraph,
    )

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()

    async def shutdown():
        await consumer.close()

    for signal_name in ('SIGINT', 'SIGTERM'):
        try:
            loop.add_signal_handler(
                getattr(signal_name),
                lambda: asyncio.create_task(shutdown())
            )
        except:
            pass

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
