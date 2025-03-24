"""
Local filesystem watcher for monitoring local directories.

This module provides functionality to watch local directories
for file changes and generate events when new files are detected.
"""

import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Any

from app.watchers.base_watcher import BaseStorageWatcher


class LocalStorageWatcher(BaseStorageWatcher):
    """Watcher for local filesystem directories."""

    def __init__(
        self, watch_path: Union[str, Path], file_patterns: List[str]
    ) -> None:
        """
        Initialize the local storage watcher.

        Args:
            watch_path: Path to directory to monitor
            file_patterns: List of file patterns to watch (e.g., '*.txt', '*.pdf')
        """
        super().__init__(watch_path, file_patterns)
        self.watch_path = Path(watch_path)

        # Ensure the directory exists
        os.makedirs(self.watch_path, exist_ok=True)

    async def list_files(self) -> List[Dict[str, Any]]:
        """
        List files in the watched directory.

        Returns:
            List of file information dictionaries
        """
        files = []

        try:
            for entry in os.scandir(self.watch_path):
                if not entry.is_file():
                    continue

                # Check if the file matches the pattern
                if not self._matches_pattern(entry.name):
                    continue

                # Get file stats
                stat = entry.stat()
                file_info = {
                    "path": Path(entry.path),
                    "name": entry.name,
                    "timestamp": datetime.fromtimestamp(stat.st_mtime),
                    "size": stat.st_size,
                    "metadata": {
                        "created": datetime.fromtimestamp(stat.st_ctime),
                        "accessed": datetime.fromtimestamp(stat.st_atime),
                        "inode": stat.st_ino,
                    },
                }

                files.append(file_info)

        except (PermissionError, FileNotFoundError) as e:
            # Log the error but return an empty list rather than raising
            import logging
            logging.getLogger(__name__).error(
                f"Error scanning directory {self.watch_path}: {str(e)}"
            )

        return files