"""Parser for Rockwell Studio 5000 L5X export files."""

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from revcat.core.parsers.base import BaseParser, ParserError
from revcat.models import Platform, Program, Project, Routine, Tag
from revcat.models.routine import Language
from revcat.models.tag import Scope


class L5XParser(BaseParser):
    """Parser for Rockwell Studio 5000 L5X XML export files.

    Supports L5X files from Studio 5000 v20 through v36+.
    """

    def can_parse(self, filepath: Path) -> bool:
        """Check if file is a valid L5X file."""
        if not filepath.exists():
            return False

        if filepath.suffix.lower() != ".l5x":
            return False

        # Quick check for L5X signature in file
        try:
            with open(filepath, "rb") as f:
                header = f.read(500).decode("utf-8", errors="ignore")
                return "RSLogix5000Content" in header
        except (OSError, UnicodeDecodeError):
            return False

    def parse(self, filepath: Path) -> Project:
        """Parse L5X file and return Project model."""
        if not filepath.exists():
            raise ParserError(f"File not found: {filepath}", filepath)

        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ParserError(f"XML parse error: {e}", filepath) from e

        # Validate this is an L5X file
        if "RSLogix5000Content" not in root.tag:
            raise ParserError("Not a valid L5X file", filepath)

        # Extract metadata from root element
        schema_revision = root.get("SchemaRevision", "")
        software_revision = root.get("SoftwareRevision", "")
        target_name = root.get("TargetName", "Unknown")
        target_type = root.get("TargetType", "")

        # Find the Controller element
        controller = root.find(".//Controller")
        if controller is None:
            raise ParserError("No Controller element found in L5X file", filepath)

        controller_name = controller.get("Name", target_name)

        # Extract timestamps if available
        modified = self._parse_timestamp(controller.get("LastModifiedDate"))

        # Parse programs
        programs = self._parse_programs(controller)

        # Parse controller-scoped tags
        tags = self._parse_tags(controller.find("Tags"), Scope.CONTROLLER)

        # Count AOIs
        aoi_defs = controller.find("AddOnInstructionDefinitions")
        aoi_count = len(list(aoi_defs)) if aoi_defs is not None else 0

        return Project(
            name=controller_name,
            platform=Platform.ROCKWELL,
            source_file=filepath,
            version=schema_revision,
            software_version=software_revision,
            controller_type=target_type,
            modified=modified,
            programs=programs,
            tags=tags,
            aoi_count=aoi_count,
            metadata={
                "target_name": target_name,
                "target_type": target_type,
                "schema_revision": schema_revision,
                "software_revision": software_revision,
            },
        )

    def get_platform_name(self) -> str:
        """Return platform name."""
        return "Rockwell Studio 5000"

    def get_file_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".l5x"]

    def _parse_timestamp(self, timestamp_str: str | None) -> datetime | None:
        """Parse L5X timestamp format."""
        if not timestamp_str:
            return None

        # L5X uses various date formats, try common ones
        formats = [
            "%a %b %d %H:%M:%S %Y",  # "Mon Dec 09 14:30:00 2024"
            "%Y-%m-%dT%H:%M:%S",     # ISO format
            "%m/%d/%Y %H:%M:%S",     # US format
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str, fmt)
            except ValueError:
                continue

        return None

    def _parse_programs(self, controller: ET.Element) -> list[Program]:
        """Parse all programs in the controller."""
        programs = []
        programs_elem = controller.find("Programs")

        if programs_elem is None:
            return programs

        for prog_elem in programs_elem.findall("Program"):
            program = self._parse_program(prog_elem)
            programs.append(program)

        return programs

    def _parse_program(self, prog_elem: ET.Element) -> Program:
        """Parse a single program element."""
        name = prog_elem.get("Name", "Unknown")

        # Get description
        desc_elem = prog_elem.find("Description")
        description = None
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()

        # Parse routines
        routines = self._parse_routines(prog_elem.find("Routines"))

        # Parse program-scoped tags
        local_tags = self._parse_tags(prog_elem.find("Tags"), Scope.PROGRAM)

        return Program(
            name=name,
            description=description,
            routines=routines,
            local_tags=local_tags,
            metadata={},
        )

    def _parse_routines(self, routines_elem: ET.Element | None) -> list[Routine]:
        """Parse all routines in a program."""
        routines = []

        if routines_elem is None:
            return routines

        for routine_elem in routines_elem.findall("Routine"):
            routine = self._parse_routine(routine_elem)
            routines.append(routine)

        return routines

    def _parse_routine(self, routine_elem: ET.Element) -> Routine:
        """Parse a single routine element."""
        name = routine_elem.get("Name", "Unknown")
        routine_type = routine_elem.get("Type", "UNKNOWN")
        language = Language.from_string(routine_type)

        # Get description
        desc_elem = routine_elem.find("Description")
        description = None
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()

        # Count content elements based on language
        rung_count = 0
        network_count = 0
        line_count = 0

        if language == Language.LADDER:
            rll_content = routine_elem.find("RLLContent")
            if rll_content is not None:
                rung_count = len(rll_content.findall("Rung"))
        elif language == Language.FBD:
            fbd_content = routine_elem.find("FBDContent")
            if fbd_content is not None:
                # Count sheets/networks
                network_count = len(fbd_content.findall("Sheet"))
        elif language == Language.ST:
            st_content = routine_elem.find("STContent")
            if st_content is not None:
                line_count = len(st_content.findall("Line"))

        return Routine(
            name=name,
            language=language,
            description=description,
            rung_count=rung_count,
            network_count=network_count,
            line_count=line_count,
            metadata={"type": routine_type},
        )

    def _parse_tags(self, tags_elem: ET.Element | None, scope: Scope) -> list[Tag]:
        """Parse tags from a Tags element."""
        tags = []

        if tags_elem is None:
            return tags

        for tag_elem in tags_elem.findall("Tag"):
            tag = self._parse_tag(tag_elem, scope)
            tags.append(tag)

        return tags

    def _parse_tag(self, tag_elem: ET.Element, scope: Scope) -> Tag:
        """Parse a single tag element."""
        name = tag_elem.get("Name", "Unknown")
        data_type = tag_elem.get("DataType", "UNKNOWN")
        value = tag_elem.get("Value")

        # Get description
        desc_elem = tag_elem.find("Description")
        description = None
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()

        # Parse dimensions if array
        dimensions = None
        dims_str = tag_elem.get("Dimensions")
        if dims_str:
            try:
                dimensions = [int(d.strip()) for d in dims_str.split(",")]
            except ValueError:
                dimensions = None

        return Tag(
            name=name,
            data_type=data_type,
            scope=scope,
            description=description,
            initial_value=value,
            dimensions=dimensions,
            metadata={},
        )
