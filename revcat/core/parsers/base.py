"""Base parser interface for PLC file parsers."""

from abc import ABC, abstractmethod
from pathlib import Path

from revcat.models import Project


class ParserError(Exception):
    """Exception raised when parsing fails."""

    def __init__(self, message: str, file_path: Path | None = None, line: int | None = None):
        self.file_path = file_path
        self.line = line
        super().__init__(message)


class BaseParser(ABC):
    """Abstract base class for PLC file parsers.

    All platform-specific parsers must implement this interface to ensure
    consistent behavior across different PLC platforms.
    """

    @abstractmethod
    def can_parse(self, filepath: Path) -> bool:
        """Check if this parser can handle the given file.

        Args:
            filepath: Path to the file to check.

        Returns:
            True if this parser can handle the file, False otherwise.
        """

    @abstractmethod
    def parse(self, filepath: Path) -> Project:
        """Parse the file and return a unified Project model.

        Args:
            filepath: Path to the file to parse.

        Returns:
            A Project instance containing the parsed data.

        Raises:
            ParserError: If parsing fails.
        """

    @abstractmethod
    def get_platform_name(self) -> str:
        """Return a human-readable platform name.

        Returns:
            The platform name (e.g., "Rockwell Studio 5000").
        """

    @abstractmethod
    def get_file_extensions(self) -> list[str]:
        """Return supported file extensions.

        Returns:
            List of file extensions this parser handles (e.g., [".l5x"]).
        """
