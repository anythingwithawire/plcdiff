"""Parser registry for automatic parser selection."""

from pathlib import Path

from revcat.core.parsers.base import BaseParser, ParserError
from revcat.core.parsers.l5x_parser import L5XParser
from revcat.core.parsers.xef_parser import XEFParser


class ParserRegistry:
    """Registry for managing available file parsers.

    Provides automatic parser selection based on file content and extension.
    """

    def __init__(self):
        self._parsers: list[BaseParser] = []
        self._register_default_parsers()

    def _register_default_parsers(self):
        """Register built-in parsers."""
        self.register(L5XParser())
        self.register(XEFParser())

    def register(self, parser: BaseParser):
        """Register a new parser."""
        self._parsers.append(parser)

    def get_parser(self, filepath: Path) -> BaseParser:
        """Find an appropriate parser for the given file.

        Args:
            filepath: Path to the file to parse.

        Returns:
            A parser that can handle the file.

        Raises:
            ParserError: If no suitable parser is found.
        """
        for parser in self._parsers:
            if parser.can_parse(filepath):
                return parser

        # Try to give a helpful error message
        extension = filepath.suffix.lower()
        supported = []
        for parser in self._parsers:
            supported.extend(parser.get_file_extensions())

        if extension not in supported:
            raise ParserError(
                f"Unsupported file type: {extension}. "
                f"Supported types: {', '.join(supported)}",
                filepath,
            )

        raise ParserError(
            f"Could not find a parser for: {filepath}",
            filepath,
        )

    def list_supported_formats(self) -> list[dict[str, str]]:
        """List all supported file formats.

        Returns:
            List of dicts with 'platform' and 'extensions' keys.
        """
        return [
            {
                "platform": parser.get_platform_name(),
                "extensions": parser.get_file_extensions(),
            }
            for parser in self._parsers
        ]


# Global registry instance
_registry = ParserRegistry()


def get_parser(filepath: Path) -> BaseParser:
    """Get a parser for the given file using the global registry."""
    return _registry.get_parser(filepath)
