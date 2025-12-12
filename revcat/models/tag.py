"""Tag model for PLC tags/variables."""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class Scope(Enum):
    """Tag scope levels."""

    CONTROLLER = "controller"  # Controller-scoped (global)
    PROGRAM = "program"        # Program-scoped
    LOCAL = "local"            # Local to routine/section


@dataclass
class Tag:
    """Tag or variable definition.

    Represents a named data element in a PLC program with its type,
    scope, and initial value information.
    """

    name: str
    data_type: str
    scope: Scope = Scope.CONTROLLER
    description: Optional[str] = None
    initial_value: Optional[str] = None
    dimensions: Optional[list[int]] = None  # For arrays
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def is_array(self) -> bool:
        """Check if this tag is an array."""
        return self.dimensions is not None and len(self.dimensions) > 0
