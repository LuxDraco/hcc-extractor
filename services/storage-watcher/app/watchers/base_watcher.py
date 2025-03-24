"""
Base watcher for abstracting storage monitoring functionality.

This module defines the abstract base class for storage watchers,
ensuring a consistent interface across different storage implementations.
"""

import abc
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Union, Any


class BaseStorageWatcher(abc.ABC):
    """Abstract base class for storage watchers."""

    def __init__(
            self, watch_path: Union[str, Path], file_patterns: List[str]
    ) -> None:
        """
        Initialize the storage watcher.

        Args:
            watch_path: Path or URI to monitor
            file_patterns: List of file patterns to watch (e.g., '*.txt', '*.pdf')
        """
        self.watch_path = watch_path
        self.file_patterns = file_patterns
        self._last_seen_files: Dict[str, datetime] = {}

    @abc.abstractmethod
    async def list_files(self) -> List[Dict[str, Any]]:
        """
        List files in the watched location.

        Returns:
            List of file information dictionaries with keys:
                - path: Path or URI of the file
                - name: Name of the file
                - timestamp: Last modified timestamp
                - size: Size of the file in bytes
                - metadata: Additional metadata (optional)
        """
        pass

    async def check_for_changes(self) -> List[Dict[str, Any]]:
        """
        Check for new files since the last check.

        Returns:
            List of file information dictionaries for new files
        """
        current_files = await self.list_files()
        new_files = []

        for file_info in current_files:
            file_path = str(file_info["path"])
            file_timestamp = file_info["timestamp"]

            # Check if file is new or modified
            if (
                    file_path not in self._last_seen_files
                    or file_timestamp > self._last_seen_files[file_path]
            ):
                new_files.append(file_info)
                self._last_seen_files[file_path] = file_timestamp

        return new_files

    def _matches_pattern(self, filename: str) -> bool:
        """
        Check if a filename matches any of the watched patterns.

        Args:
            filename: Name of the file to check

        Returns:
            Whether the filename matches any pattern
        """
        from fnmatch import fnmatch

        if not self.file_patterns or "*" in self.file_patterns:
            return True

        return any(fnmatch(filename, pattern) for pattern in self.file_patterns)
