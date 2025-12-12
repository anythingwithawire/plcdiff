"""Routine model for PLC routines/sections."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional, Union


class Language(Enum):
    """IEC 61131-3 programming languages."""

    LADDER = "LD"      # Ladder Diagram
    FBD = "FBD"        # Function Block Diagram
    ST = "ST"          # Structured Text
    SFC = "SFC"        # Sequential Function Chart
    UNKNOWN = "UNKNOWN"

    @classmethod
    def from_string(cls, value: str) -> "Language":
        """Parse language from string representation."""
        value_upper = value.upper()
        mapping = {
            "LD": cls.LADDER,
            "RLL": cls.LADDER,  # Rockwell Relay Ladder Logic
            "LADDER": cls.LADDER,
            "FBD": cls.FBD,
            "ST": cls.ST,
            "STRUCTURED TEXT": cls.ST,
            "SFC": cls.SFC,
        }
        return mapping.get(value_upper, cls.UNKNOWN)


@dataclass
class Routine:
    """Routine or section representation.

    A routine contains the actual PLC logic in one of the supported
    IEC 61131-3 languages.
    """

    name: str
    language: Language
    description: Optional[str] = None
    content: Optional[Union["LadderContent", "FBDContent", "STContent"]] = None
    rung_count: int = 0      # For Ladder
    network_count: int = 0   # For FBD
    line_count: int = 0      # For ST
    metadata: dict[str, Any] = field(default_factory=dict)


# Placeholder content classes - will be fully implemented later
@dataclass
class LadderContent:
    """Ladder diagram content placeholder."""
    rungs: list = field(default_factory=list)


@dataclass
class FBDContent:
    """Function Block Diagram content placeholder."""
    networks: list = field(default_factory=list)


@dataclass
class STContent:
    """Structured Text content placeholder."""
    lines: list = field(default_factory=list)
