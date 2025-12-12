"""Project model for unified PLC project representation."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

from revcat.models.program import Program
from revcat.models.tag import Tag


class Platform(Enum):
    """Supported PLC platforms."""

    ROCKWELL = "rockwell"
    SCHNEIDER = "schneider"
    UNKNOWN = "unknown"


@dataclass
class Project:
    """Unified project representation for any supported PLC platform.

    This is the top-level data structure that represents a parsed PLC project
    export file. It provides a platform-agnostic view of the project structure.
    """

    name: str
    platform: Platform
    source_file: Path
    version: Optional[str] = None
    software_version: Optional[str] = None
    controller_type: Optional[str] = None
    created: Optional[datetime] = None
    modified: Optional[datetime] = None
    programs: list[Program] = field(default_factory=list)
    tags: list[Tag] = field(default_factory=list)
    aoi_count: int = 0  # Add-On Instructions (Rockwell) / DFBs (Schneider)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def total_routines(self) -> int:
        """Return the total number of routines across all programs."""
        return sum(len(prog.routines) for prog in self.programs)

    @property
    def total_tags(self) -> int:
        """Return the total number of tags including program-scoped tags."""
        program_tags = sum(len(prog.local_tags) for prog in self.programs)
        return len(self.tags) + program_tags

    def get_summary(self) -> dict[str, Any]:
        """Return a summary dictionary of project information."""
        return {
            "name": self.name,
            "platform": self.platform.value,
            "source_file": str(self.source_file),
            "version": self.version,
            "software_version": self.software_version,
            "controller_type": self.controller_type,
            "modified": self.modified.isoformat() if self.modified else None,
            "programs": len(self.programs),
            "routines": self.total_routines,
            "tags": self.total_tags,
            "aoi_count": self.aoi_count,
        }
