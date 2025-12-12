"""Program model for PLC program units."""

from dataclasses import dataclass, field
from typing import Any, Optional

from revcat.models.routine import Routine
from revcat.models.tag import Tag


@dataclass
class Program:
    """Program or program unit representation.

    In Rockwell terminology, this is a "Program" containing routines.
    In Schneider terminology, this maps to a program organizational unit.
    """

    name: str
    description: Optional[str] = None
    routines: list[Routine] = field(default_factory=list)
    local_tags: list[Tag] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def get_routine(self, name: str) -> Optional[Routine]:
        """Find a routine by name."""
        for routine in self.routines:
            if routine.name == name:
                return routine
        return None
