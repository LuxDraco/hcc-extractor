"""
Message broker service for the API Gateway.

This module provides functionality for publishing messages to RabbitMQ
for communication with other services.
"""

import json
import time
import uuid
from typing import Any, Dict, Optional

import structlog
from aio_pika import Message, DeliveryMode
from fastapi import Depends

from app.core.config import settings
from app.core.dependencies import get_rabbitmq_channel
from app.utils.metrics import (
    RABBITMQ_MESSAGES_PUBLISHED,
    RABBITMQ_MESSAGES_FAILED,
)

logger = structlog.get_logger(__name__)


class MessageBrokerService:
    """Service for message broker operations."""

    def __init__(
            self, channel=Depends(get_rabbitmq_channel)
    ):
        """
        Initialize the message broker service.

        Args:
            channel: RabbitMQ channel
        """
        self.channel = channel
        self.exchange_name = settings.RABBITMQ_EXCHANGE
        self.queue_name = settings.RABBITMQ_QUEUE

    async def _initialize(self) -> None:
        """Initialize RabbitMQ exchanges and queues."""
        # Declare exchange
        self.exchange = await self.channel.declare_exchange(
            self.exchange_name,
            type="topic",
            durable=True,
        )

        # Declare queue
        self.queue = await self.channel.declare_queue(
            self.queue_name,
            durable=True,
        )

        # Bind queue to exchange
        await self.queue.bind(
            exchange=self.exchange,
            routing_key="document.#",
        )

    async def publish_message(
            self,
            routing_key: str,
            message: Dict[str, Any],
            message_type: str,
            content_type: str = "application/json",
            priority: Optional[int] = None,
    ) -> None:
        """
        Publish a message to RabbitMQ.

        Args:
            routing_key: Routing key for the message
            message: Message data
            message_type: Type of message
            content_type: Content type of the message
            priority: Priority of the message (0-9)
        """
        start_time = time.time()

        try:
            # Initialize if needed
            if not hasattr(self, "exchange") or self.exchange is None or not hasattr(self,
                                                                                     "queue") or self.queue is None:
                try:
                    await self._initialize()
                except Exception as e:
                    logger.error(f"Failed to initialize RabbitMQ: {str(e)}")
                    return  # Return early, don't try to publish

            # If initialization failed or didn't properly set up the exchange or queue
            if self.exchange is None or self.queue is None:
                logger.error("Cannot publish message: RabbitMQ not properly initialized")
                return  # Return early, don't try to publish

            # Add metadata
            message["message_id"] = str(uuid.uuid4())
            message["timestamp"] = time.time()
            message["message_type"] = message_type

            # Create message
            message_json = json.dumps(message)
            rabbitmq_message = Message(
                body=message_json.encode("utf-8"),
                content_type=content_type,
                delivery_mode=DeliveryMode.PERSISTENT,
                message_id=message["message_id"],
                type=message_type,
                timestamp=int(message["timestamp"]),
                priority=priority,
                app_id=settings.PROJECT_NAME,
            )

            # Publish message
            await self.exchange.publish(
                message=rabbitmq_message,
                routing_key=routing_key,
            )

            # Record metrics
            RABBITMQ_MESSAGES_PUBLISHED.labels(
                queue=self.queue_name, message_type=message_type
            ).inc()

            logger.info(
                "Message published",
                routing_key=routing_key,
                message_id=message["message_id"],
                message_type=message_type,
                duration=round(time.time() - start_time, 3),
            )

        except Exception as e:
            # Record metrics
            RABBITMQ_MESSAGES_FAILED.labels(
                queue=self.queue_name, message_type=message_type
            ).inc()

            logger.error(
                "Error publishing message",
                routing_key=routing_key,
                message_type=message_type,
                error=str(e),
                duration=round(time.time() - start_time, 3),
            )
            # Don't raise the exception further

    async def publish_document_uploaded(
            self,
            document_id: str,
            storage_path: str,
            storage_type: str,
            content_type: str,
            priority: bool = False,
    ) -> None:
        """
        Publish a document.uploaded message.

        Args:
            document_id: Document ID
            storage_path: Path to the document in storage
            storage_type: Storage type (local, s3, gcs)
            content_type: MIME type of the document
            priority: Whether to prioritize processing

        Raises:
            Exception: If the message cannot be published
        """
        message = {
            "document_id": document_id,
            "storage_path": storage_path,
            "storage_type": storage_type,
            "content_type": content_type,
        }

        await self.publish_message(
            routing_key="document.uploaded",
            message=message,
            message_type="document.uploaded",
            priority=5 if priority else None,
        )

    async def publish_extraction_completed(
            self,
            document_id: str,
            extraction_result_path: str,
            total_conditions: int,
    ) -> None:
        """
        Publish an extraction.completed message.

        Args:
            document_id: Document ID
            extraction_result_path: Path to the extraction result
            total_conditions: Total number of conditions extracted

        Raises:
            Exception: If the message cannot be published
        """
        message = {
            "document_id": document_id,
            "extraction_result_path": extraction_result_path,
            "total_conditions": total_conditions,
        }

        await self.publish_message(
            routing_key="document.extraction.completed",
            message=message,
            message_type="extraction.completed",
        )

    async def publish_analysis_completed(
            self,
            document_id: str,
            analysis_result_path: str,
            hcc_relevant_conditions: int,
    ) -> None:
        """
        Publish an analysis.completed message.

        Args:
            document_id: Document ID
            analysis_result_path: Path to the analysis result
            hcc_relevant_conditions: Number of HCC-relevant conditions

        Raises:
            Exception: If the message cannot be published
        """
        message = {
            "document_id": document_id,
            "analysis_result_path": analysis_result_path,
            "hcc_relevant_conditions": hcc_relevant_conditions,
        }

        await self.publish_message(
            routing_key="document.analysis.completed",
            message=message,
            message_type="analysis.completed",
        )

    async def publish_validation_completed(
            self,
            document_id: str,
            validation_result_path: str,
            compliant_conditions: int,
    ) -> None:
        """
        Publish a validation.completed message.

        Args:
            document_id: Document ID
            validation_result_path: Path to the validation result
            compliant_conditions: Number of compliant conditions

        Raises:
            Exception: If the message cannot be published
        """
        message = {
            "document_id": document_id,
            "validation_result_path": validation_result_path,
            "compliant_conditions": compliant_conditions,
        }

        await self.publish_message(
            routing_key="document.validation.completed",
            message=message,
            message_type="validation.completed",
        )

    async def publish_processing_completed(
            self,
            document_id: str,
            total_conditions: int,
            hcc_relevant_conditions: int,
            compliant_conditions: int,
    ) -> None:
        """
        Publish a processing.completed message.

        Args:
            document_id: Document ID
            total_conditions: Total number of conditions extracted
            hcc_relevant_conditions: Number of HCC-relevant conditions
            compliant_conditions: Number of compliant conditions

        Raises:
            Exception: If the message cannot be published
        """
        message = {
            "document_id": document_id,
            "total_conditions": total_conditions,
            "hcc_relevant_conditions": hcc_relevant_conditions,
            "compliant_conditions": compliant_conditions,
        }

        await self.publish_message(
            routing_key="document.processing.completed",
            message=message,
            message_type="processing.completed",
        )

    async def publish_error(
            self,
            document_id: str,
            error_type: str,
            error_message: str,
            stage: str,
    ) -> None:
        """
        Publish an error message.

        Args:
            document_id: Document ID
            error_type: Type of error
            error_message: Error message
            stage: Processing stage where the error occurred

        Raises:
            Exception: If the message cannot be published
        """
        message = {
            "document_id": document_id,
            "error_type": error_type,
            "error_message": error_message,
            "stage": stage,
        }

        await self.publish_message(
            routing_key="document.error",
            message=message,
            message_type="error",
        )