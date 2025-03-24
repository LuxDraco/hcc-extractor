"""
Main module for the HCC Storage Watcher Service.

This module serves as the entry point for the storage watcher service, which is responsible
for monitoring storage systems (local, S3, GCS) for changes and publishing notifications
to RabbitMQ when new files are detected.
"""

import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Type, Union

from app.publisher.message_publisher import MessagePublisher
from app.watchers.base_watcher import BaseStorageWatcher
from app.watchers.gcs_watcher import GCSStorageWatcher
from app.watchers.local_watcher import LocalStorageWatcher
from app.watchers.s3_watcher import S3StorageWatcher

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


class StorageWatcherService:
    """Service for monitoring storage systems for changes."""

    def __init__(
        self,
        storage_type: str,
        watch_path: Union[str, Path],
        rabbitmq_host: str,
        rabbitmq_port: int = 5672,
        rabbitmq_user: str = "guest",
        rabbitmq_password: str = "guest",
        rabbitmq_queue: str = "document-events",
        watch_interval: float = 10.0,
        file_patterns: Optional[List[str]] = None,
    ) -> None:
        """
        Initialize the storage watcher service.

        Args:
            storage_type: Type of storage to monitor ('local', 's3', or 'gcs')
            watch_path: Path or URI to monitor
            rabbitmq_host: RabbitMQ host
            rabbitmq_port: RabbitMQ port
            rabbitmq_user: RabbitMQ username
            rabbitmq_password: RabbitMQ password
            rabbitmq_queue: RabbitMQ queue name for publishing events
            watch_interval: Interval in seconds between checks
            file_patterns: List of file patterns to watch (e.g., '*.txt', '*.pdf')
        """
        self.storage_type = storage_type.lower()
        self.watch_path = watch_path
        self.watch_interval = watch_interval
        self.file_patterns = file_patterns or ["*"]

        # Initialize message publisher
        self.publisher = MessagePublisher(
            host=rabbitmq_host,
            port=rabbitmq_port,
            username=rabbitmq_user,
            password=rabbitmq_password,
            queue=rabbitmq_queue,
        )

        # Select appropriate storage watcher based on type
        self.watcher = self._create_watcher()

        logger.info(
            f"Initialized storage watcher service with {self.storage_type} storage type, "
            f"watching {self.watch_path} every {self.watch_interval} seconds"
        )

    def _create_watcher(self) -> BaseStorageWatcher:
        """
        Create the appropriate storage watcher based on storage type.

        Returns:
            Storage watcher instance
        """
        watcher_classes: Dict[str, Type[BaseStorageWatcher]] = {
            "local": LocalStorageWatcher,
            "s3": S3StorageWatcher,
            "gcs": GCSStorageWatcher,
        }

        if self.storage_type not in watcher_classes:
            raise ValueError(
                f"Unsupported storage type: {self.storage_type}. "
                f"Supported types: {', '.join(watcher_classes.keys())}"
            )

        watcher_class = watcher_classes[self.storage_type]
        return watcher_class(
            watch_path=self.watch_path,
            file_patterns=self.file_patterns,
        )

    async def start(self) -> None:
        """Start the storage watcher service."""
        logger.info(f"Starting storage watcher service for {self.storage_type}")

        # Initialize message publisher
        await self.publisher.connect()

        try:
            while True:
                try:
                    # Check for new files
                    new_files = await self.watcher.check_for_changes()

                    if new_files:
                        logger.info(f"Detected {len(new_files)} new files")

                        # Publish events for each new file
                        for file_info in new_files:
                            event = {
                                "event_type": "new_file",
                                "storage_type": self.storage_type,
                                "file_path": str(file_info["path"]),
                                "file_name": file_info["name"],
                                "timestamp": file_info["timestamp"].isoformat(),
                                "metadata": file_info.get("metadata", {}),
                            }

                            await self.publisher.publish_message(event)
                            logger.info(f"Published event for {file_info['name']}")

                    # Wait before checking again
                    await asyncio.sleep(self.watch_interval)

                except Exception as e:
                    logger.error(f"Error checking for changes: {str(e)}")
                    # Wait a bit before retrying
                    await asyncio.sleep(5)

        finally:
            # Close the publisher connection
            await self.publisher.close()

    async def stop(self) -> None:
        """Stop the storage watcher service."""
        logger.info("Stopping storage watcher service")
        await self.publisher.close()


async def run_service():
    """Run the storage watcher service."""
    # Get configuration from environment variables or use defaults
    storage_type = os.environ.get("STORAGE_TYPE", "local")
    watch_path = os.environ.get("WATCH_PATH", "./data")
    rabbitmq_host = os.environ.get("RABBITMQ_HOST", "rabbitmq")
    rabbitmq_port = int(os.environ.get("RABBITMQ_PORT", "5672"))
    rabbitmq_user = os.environ.get("RABBITMQ_USER", "guest")
    rabbitmq_password = os.environ.get("RABBITMQ_PASSWORD", "guest")
    rabbitmq_queue = os.environ.get("RABBITMQ_QUEUE", "document-events")
    watch_interval = float(os.environ.get("WATCH_INTERVAL", "10.0"))
    file_patterns_str = os.environ.get("FILE_PATTERNS", "*.txt,*.pdf")
    file_patterns = [p.strip() for p in file_patterns_str.split(",")]

    service = StorageWatcherService(
        storage_type=storage_type,
        watch_path=watch_path,
        rabbitmq_host=rabbitmq_host,
        rabbitmq_port=rabbitmq_port,
        rabbitmq_user=rabbitmq_user,
        rabbitmq_password=rabbitmq_password,
        rabbitmq_queue=rabbitmq_queue,
        watch_interval=watch_interval,
        file_patterns=file_patterns,
    )

    # Set up signal handlers for graceful shutdown
    loop = asyncio.get_event_loop()
    for signal_name in ("SIGINT", "SIGTERM"):
        try:
            loop.add_signal_handler(
                getattr(signal_name), lambda: asyncio.create_task(service.stop())
            )
        except (NotImplementedError, AttributeError):
            # Signal handling is not available on Windows
            pass

    try:
        await service.start()
    except asyncio.CancelledError:
        logger.info("Service cancelled")
    finally:
        await service.stop()


def main() -> None:
    """Entry point for the service."""
    try:
        asyncio.run(run_service())
    except KeyboardInterrupt:
        logger.info("Service interrupted")


if __name__ == "__main__":
    main()