"""Parser for Schneider EcoStruxure Control Expert / Unity Pro XEF export files."""

from datetime import datetime
from pathlib import Path
from typing import Any
from xml.etree import ElementTree as ET

from revcat.core.parsers.base import BaseParser, ParserError
from revcat.models import Platform, Program, Project, Routine, Tag
from revcat.models.routine import Language
from revcat.models.tag import Scope


class XEFParser(BaseParser):
    """Parser for Schneider EcoStruxure Control Expert / Unity Pro XEF XML export files.

    Supports XEF files from Unity Pro v11+ and Control Expert v14+.
    """

    def can_parse(self, filepath: Path) -> bool:
        """Check if file is a valid XEF file."""
        if not filepath.exists():
            return False

        if filepath.suffix.lower() != ".xef":
            return False

        # Quick check for XEF signature in file
        try:
            with open(filepath, "rb") as f:
                header = f.read(1000).decode("utf-8", errors="ignore")
                # XEF files contain Exchange element or specific Schneider markers
                return "Exchange" in header or "ContentHeader" in header or "schneider" in header.lower()
        except (OSError, UnicodeDecodeError):
            return False

    def parse(self, filepath: Path) -> Project:
        """Parse XEF file and return Project model."""
        if not filepath.exists():
            raise ParserError(f"File not found: {filepath}", filepath)

        try:
            tree = ET.parse(filepath)
            root = tree.getroot()
        except ET.ParseError as e:
            raise ParserError(f"XML parse error: {e}", filepath) from e

        # Detect and store namespace
        self._ns = self._detect_namespace(root)

        # Handle namespace in root tag
        root_tag = self._strip_ns(root.tag)

        # Validate this is an XEF file
        if root_tag not in ("Exchange", "Project", "ContentHeader"):
            if not self._looks_like_xef(root):
                raise ParserError("Not a valid XEF file", filepath)

        # Extract project information
        project_name, version, modified = self._extract_metadata(root, filepath)

        # Parse programs first (so we know which variables are program-local)
        programs = self._parse_programs(root)

        # Get program-local variable names to exclude from global
        program_var_names = set()
        for prog in programs:
            for tag in prog.local_tags:
                program_var_names.add(tag.name)

        # Parse global variables (tags) - only from dataBlock, not from programs
        tags = self._parse_global_variables(root, program_var_names)

        # Count DFBs (Derived Function Blocks)
        dfb_count = self._count_dfbs(root)

        return Project(
            name=project_name,
            platform=Platform.SCHNEIDER,
            source_file=filepath,
            version=version,
            software_version=version,
            controller_type=self._get_controller_type(root),
            modified=modified,
            programs=programs,
            tags=tags,
            aoi_count=dfb_count,  # DFBs are equivalent to AOIs
            metadata=self._extract_all_metadata(root),
        )

    def get_platform_name(self) -> str:
        """Return platform name."""
        return "Schneider EcoStruxure Control Expert"

    def get_file_extensions(self) -> list[str]:
        """Return supported extensions."""
        return [".xef"]

    def _detect_namespace(self, root: ET.Element) -> str:
        """Detect the XML namespace used in the document."""
        if root.tag.startswith("{"):
            return root.tag[1:root.tag.index("}")]
        return ""

    def _strip_ns(self, tag: str) -> str:
        """Strip namespace from tag name."""
        if "}" in tag:
            return tag.split("}")[-1]
        return tag

    def _ns_path(self, path: str) -> str:
        """Convert path to namespace-aware path."""
        if not self._ns:
            return path

        parts = []
        for part in path.split("/"):
            # Skip empty parts and special xpath prefixes
            if not part or part in (".", ".."):
                parts.append(part)
            elif part.startswith("{"):
                # Already has namespace
                parts.append(part)
            else:
                parts.append(f"{{{self._ns}}}{part}")
        return "/".join(parts)

    def _find(self, elem: ET.Element, path: str) -> ET.Element | None:
        """Find element with namespace awareness."""
        # Try with namespace first (most likely for XEF files)
        if self._ns:
            ns_path = self._ns_path(path)
            result = elem.find(ns_path)
            if result is not None:
                return result

        # Fallback to without namespace
        return elem.find(path)

    def _findall(self, elem: ET.Element, path: str) -> list[ET.Element]:
        """Find all elements with namespace awareness."""
        # Try with namespace first (most likely for XEF files)
        if self._ns:
            ns_path = self._ns_path(path)
            results = elem.findall(ns_path)
            if results:
                return results

        # Fallback to without namespace
        return elem.findall(path)

    def _looks_like_xef(self, root: ET.Element) -> bool:
        """Check if XML structure looks like XEF format."""
        xef_indicators = ["variables", "variable", "program", "section", "dataBlock"]
        for indicator in xef_indicators:
            if self._find(root, f".//{indicator}") is not None:
                return True
        return False

    def _extract_metadata(self, root: ET.Element, filepath: Path) -> tuple[str, str | None, datetime | None]:
        """Extract project name, version, and modification date."""
        project_name = filepath.stem  # Default to filename
        version = None
        modified = None

        # Try to find ContentHeader
        header = self._find(root, ".//ContentHeader")
        if header is not None:
            if header.get("name"):
                project_name = header.get("name")
            if header.get("version"):
                version = header.get("version")
            if header.get("dateTime"):
                modified = self._parse_timestamp(header.get("dateTime"))

        # Also check root attributes
        if root.get("name"):
            project_name = root.get("name")

        return project_name, version, modified

    def _parse_timestamp(self, timestamp_str: str | None) -> datetime | None:
        """Parse XEF timestamp format."""
        if not timestamp_str:
            return None

        formats = [
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
        ]

        for fmt in formats:
            try:
                return datetime.strptime(timestamp_str.split(".")[0], fmt)
            except ValueError:
                continue

        return None

    def _get_controller_type(self, root: ET.Element) -> str | None:
        """Extract controller type if available."""
        processor = self._find(root, ".//processor")
        if processor is not None:
            return processor.get("type") or processor.get("name") or processor.text
        return None

    def _parse_global_variables(self, root: ET.Element, exclude_names: set[str]) -> list[Tag]:
        """Parse global variables/tags from dataBlock only."""
        tags = []

        # Only look in dataBlock for global variables
        data_block = self._find(root, ".//dataBlock")
        if data_block is not None:
            variables = self._find(data_block, "variables")
            if variables is not None:
                for var_elem in self._findall(variables, "variable"):
                    tag = self._parse_variable(var_elem, Scope.CONTROLLER)
                    if tag.name not in exclude_names:
                        tags.append(tag)

        return tags

    def _parse_variable(self, var_elem: ET.Element, scope: Scope) -> Tag:
        """Parse a single variable element."""
        name = var_elem.get("name", "Unknown")
        data_type = var_elem.get("typeName", "UNKNOWN")

        # Get description/comment
        description = None
        comment_elem = self._find(var_elem, "comment")
        if comment_elem is not None and comment_elem.text:
            description = comment_elem.text.strip()

        # Get initial value
        initial_value = var_elem.get("value") or var_elem.get("initialValue")

        # Parse dimensions for arrays
        dimensions = None
        dim_str = var_elem.get("dimensions") or var_elem.get("arrayDimension")
        if dim_str:
            try:
                dimensions = [int(d.strip()) for d in dim_str.split(",")]
            except ValueError:
                pass

        return Tag(
            name=name,
            data_type=data_type,
            scope=scope,
            description=description,
            initial_value=initial_value,
            dimensions=dimensions,
            metadata={},
        )

    def _parse_programs(self, root: ET.Element) -> list[Program]:
        """Parse program units and sections."""
        programs = []

        # Find explicit program elements
        for prog_elem in self._findall(root, ".//program"):
            program = self._parse_program_element(prog_elem)
            if program.routines:  # Only add if it has content
                programs.append(program)

        # If no programs found, look for sections at root and create a default program
        if not programs:
            sections = self._findall(root, ".//section")
            if sections:
                routines = [self._parse_section(s) for s in sections]
                programs.append(Program(
                    name="MainProgram",
                    description="Default program",
                    routines=routines,
                    local_tags=[],
                    metadata={},
                ))

        return programs

    def _parse_program_element(self, prog_elem: ET.Element) -> Program:
        """Parse a single program element."""
        name = prog_elem.get("name", "Program")

        # Get description
        desc_elem = self._find(prog_elem, "comment")
        description = None
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()

        # Parse sections (routines) - direct children only
        routines = []
        for section in self._findall(prog_elem, "section"):
            routines.append(self._parse_section(section))

        # Parse local variables
        local_tags = []
        local_vars = self._find(prog_elem, "variables")
        if local_vars is not None:
            for var_elem in self._findall(local_vars, "variable"):
                local_tags.append(self._parse_variable(var_elem, Scope.PROGRAM))

        return Program(
            name=name,
            description=description,
            routines=routines,
            local_tags=local_tags,
            metadata={},
        )

    def _parse_section(self, section_elem: ET.Element) -> Routine:
        """Parse a single section element."""
        name = section_elem.get("name", "Section")
        lang_str = section_elem.get("language", "UNKNOWN")
        language = Language.from_string(lang_str)

        # Get description
        desc_elem = self._find(section_elem, "comment")
        description = None
        if desc_elem is not None and desc_elem.text:
            description = desc_elem.text.strip()

        # Count content based on language
        rung_count = 0
        network_count = 0
        line_count = 0

        if language == Language.LADDER:
            ld_source = self._find(section_elem, "LDSource")
            if ld_source is not None:
                # Count networks in LD
                networks = self._findall(ld_source, "network")
                rung_count = len(networks)
                if rung_count == 0:
                    # Try networkLD
                    networks = self._findall(ld_source, "networkLD")
                    rung_count = len(networks)

        elif language == Language.FBD:
            fbd_source = self._find(section_elem, "FBDSource")
            if fbd_source is not None:
                networks = self._findall(fbd_source, "networkFBD")
                network_count = len(networks)
                if network_count == 0:
                    networks = self._findall(fbd_source, "network")
                    network_count = len(networks)

        elif language == Language.ST:
            st_source = self._find(section_elem, "STSource")
            if st_source is not None:
                # ST content is usually in CDATA
                if st_source.text:
                    line_count = len(st_source.text.strip().split("\n"))

        return Routine(
            name=name,
            language=language,
            description=description,
            rung_count=rung_count,
            network_count=network_count,
            line_count=line_count,
            metadata={"original_language": lang_str},
        )

    def _count_dfbs(self, root: ET.Element) -> int:
        """Count Derived Function Blocks."""
        dfb_count = 0
        for tag_name in ["DFBType", "derivedFB", "DerivedFunctionBlock"]:
            dfb_count += len(self._findall(root, f".//{tag_name}"))
        return dfb_count

    def _extract_all_metadata(self, root: ET.Element) -> dict[str, Any]:
        """Extract additional metadata from the file."""
        metadata = {}

        header = self._find(root, ".//ContentHeader")
        if header is not None:
            for attr in header.attrib:
                metadata[attr] = header.get(attr)

        return metadata
