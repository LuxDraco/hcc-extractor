"""
Message publisher for sending events to RabbitMQ.

This module provides functionality to publish storage events
to RabbitMQ for consumption by other services.
"""

import json
import logging
from typing import Any, Dict, Optional

import aio_pika

logger = logging.getLogger(__name__)


class MessagePublisher:
    """Publisher for sending messages to RabbitMQ."""

    def __init__(
            self,
            host: str,
            port: int = 5672,
            username: str = "guest",
            password: str = "guest",
            queue: str = "document-events",
            exchange: str = "",
            virtual_host: str = "/",
            connection_timeout: float = 5.0,
    ) -> None:
        """
        Initialize the message publisher.

        Args:
            host: RabbitMQ host
            port: RabbitMQ port
            username: RabbitMQ username
            password: RabbitMQ password
            queue: Queue name to publish to
            exchange: Exchange name (default is direct exchange)
            virtual_host: RabbitMQ virtual host
            connection_timeout: Connection timeout in seconds
        """
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.queue_name = queue
        self.exchange_name = exchange
        self.virtual_host = virtual_host
        self.connection_timeout = connection_timeout

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
            connection_string = f"amqp://{self.username}:{self.password}@{self.host}:{self.port}/{self.virtual_host}"

            # Connect to RabbitMQ
            self.connection = await aio_pika.connect_robust(
                connection_string, timeout=self.connection_timeout
            )

            # Create channel
            self.channel = await self.connection.channel()

            # Declare queue
            self.queue = await self.channel.declare_queue(
                self.queue_name, durable=True
            )

            # Get exchange
            if self.exchange_name:
                self.exchange = await self.channel.declare_exchange(
                    self.exchange_name, type=aio_pika.ExchangeType.TOPIC, durable=True
                )
            else:
                self.exchange = self.channel.default_exchange

            logger.info(f"Connected to RabbitMQ at {self.host}:{self.port}")

        except Exception as e:
            logger.error(f"Failed to connect to RabbitMQ: {str(e)}")
            raise ConnectionError(f"Failed to connect to RabbitMQ: {str(e)}")

    async def publish_message(self, message: Dict[str, Any], routing_key: Optional[str] = None) -> None:
        """
        Publish a message to RabbitMQ.

        Args:
            message: Message to publish (will be converted to JSON)
            routing_key: Optional routing key (defaults to queue name)

        Raises:
            RuntimeError: If not connected to RabbitMQ
            ValueError: If message serialization fails
        """
        if not self.channel or not self.exchange:
            raise RuntimeError("Not connected to RabbitMQ. Call connect() first.")

        # Use queue name as routing key if not specified
        if routing_key is None:
            routing_key = self.queue_name

        try:
            # Convert message to JSON
            message_json = json.dumps(message)

            # Create message
            pika_message = aio_pika.Message(
                body=message_json.encode("utf-8"),
                delivery_mode=aio_pika.DeliveryMode.PERSISTENT,
                content_type="application/json",
            )

            # Publish message
            await self.exchange.publish(pika_message, routing_key=routing_key)

            logger.debug(f"Published message to {routing_key}")

        except (TypeError, ValueError) as e:
            logger.error(f"Failed to serialize message: {str(e)}")
            raise ValueError(f"Failed to serialize message: {str(e)}")
        except Exception as e:
            logger.error(f"Failed to publish message: {str(e)}")
            raise

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
