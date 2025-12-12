"""Diff result models for representing comparison results."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from revcat.models.project import Project
from revcat.models.program import Program
from revcat.models.routine import Routine, Language
from revcat.models.tag import Tag


class ChangeType(Enum):
    """Type of change detected."""

    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


@dataclass
class TagDiff:
    """Difference for a single tag."""

    name: str
    change_type: ChangeType
    source_tag: Optional[Tag] = None
    target_tag: Optional[Tag] = None
    changes: list[str] = field(default_factory=list)  # List of what changed

    def get_change_summary(self) -> str:
        """Get a human-readable summary of changes."""
        if self.change_type == ChangeType.ADDED:
            return f"Added tag '{self.name}' ({self.target_tag.data_type})"
        elif self.change_type == ChangeType.REMOVED:
            return f"Removed tag '{self.name}' ({self.source_tag.data_type})"
        elif self.change_type == ChangeType.MODIFIED:
            return f"Modified tag '{self.name}': {', '.join(self.changes)}"
        return f"Tag '{self.name}' unchanged"


@dataclass
class RoutineDiff:
    """Difference for a single routine."""

    name: str
    program_name: str
    language: Language
    change_type: ChangeType
    source_routine: Optional[Routine] = None
    target_routine: Optional[Routine] = None
    changes: list[str] = field(default_factory=list)

    def get_change_summary(self) -> str:
        """Get a human-readable summary of changes."""
        if self.change_type == ChangeType.ADDED:
            return f"Added routine '{self.name}' ({self.language.value})"
        elif self.change_type == ChangeType.REMOVED:
            return f"Removed routine '{self.name}' ({self.language.value})"
        elif self.change_type == ChangeType.MODIFIED:
            return f"Modified routine '{self.name}': {', '.join(self.changes)}"
        return f"Routine '{self.name}' unchanged"


@dataclass
class ProgramDiff:
    """Difference for a single program."""

    name: str
    change_type: ChangeType
    source_program: Optional[Program] = None
    target_program: Optional[Program] = None
    routine_diffs: list[RoutineDiff] = field(default_factory=list)
    tag_diffs: list[TagDiff] = field(default_factory=list)  # Program-local tags

    @property
    def routines_added(self) -> int:
        return sum(1 for d in self.routine_diffs if d.change_type == ChangeType.ADDED)

    @property
    def routines_removed(self) -> int:
        return sum(1 for d in self.routine_diffs if d.change_type == ChangeType.REMOVED)

    @property
    def routines_modified(self) -> int:
        return sum(1 for d in self.routine_diffs if d.change_type == ChangeType.MODIFIED)


@dataclass
class DiffSummary:
    """Summary statistics of a diff result."""

    programs_added: int = 0
    programs_removed: int = 0
    programs_modified: int = 0

    routines_added: int = 0
    routines_removed: int = 0
    routines_modified: int = 0

    tags_added: int = 0
    tags_removed: int = 0
    tags_modified: int = 0

    @property
    def total_changes(self) -> int:
        """Total number of changes."""
        return (
            self.programs_added + self.programs_removed + self.programs_modified +
            self.routines_added + self.routines_removed + self.routines_modified +
            self.tags_added + self.tags_removed + self.tags_modified
        )

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return self.total_changes > 0


@dataclass
class DiffResult:
    """Complete diff result between two projects."""

    source: Project
    target: Project
    timestamp: datetime = field(default_factory=datetime.now)

    program_diffs: list[ProgramDiff] = field(default_factory=list)
    tag_diffs: list[TagDiff] = field(default_factory=list)  # Controller-scope tags
    summary: DiffSummary = field(default_factory=DiffSummary)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return self.summary.has_changes

    def get_all_routine_diffs(self) -> list[RoutineDiff]:
        """Get all routine diffs across all programs."""
        result = []
        for prog_diff in self.program_diffs:
            result.extend(prog_diff.routine_diffs)
        return result

    def get_changed_items_by_type(self, change_type: ChangeType) -> dict[str, list]:
        """Get all changed items filtered by change type."""
        result = {
            "programs": [],
            "routines": [],
            "tags": [],
        }

        for prog_diff in self.program_diffs:
            if prog_diff.change_type == change_type:
                result["programs"].append(prog_diff)
            for routine_diff in prog_diff.routine_diffs:
                if routine_diff.change_type == change_type:
                    result["routines"].append(routine_diff)
            for tag_diff in prog_diff.tag_diffs:
                if tag_diff.change_type == change_type:
                    result["tags"].append(tag_diff)

        for tag_diff in self.tag_diffs:
            if tag_diff.change_type == change_type:
                result["tags"].append(tag_diff)

        return result

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "source_file": str(self.source.source_file),
            "target_file": str(self.target.source_file),
            "source_name": self.source.name,
            "target_name": self.target.name,
            "platform": self.source.platform.value,
            "timestamp": self.timestamp.isoformat(),
            "summary": {
                "programs_added": self.summary.programs_added,
                "programs_removed": self.summary.programs_removed,
                "programs_modified": self.summary.programs_modified,
                "routines_added": self.summary.routines_added,
                "routines_removed": self.summary.routines_removed,
                "routines_modified": self.summary.routines_modified,
                "tags_added": self.summary.tags_added,
                "tags_removed": self.summary.tags_removed,
                "tags_modified": self.summary.tags_modified,
                "total_changes": self.summary.total_changes,
            },
            "programs": [
                {
                    "name": pd.name,
                    "change_type": pd.change_type.value,
                    "routines": [
                        {
                            "name": rd.name,
                            "language": rd.language.value,
                            "change_type": rd.change_type.value,
                            "changes": rd.changes,
                        }
                        for rd in pd.routine_diffs
                        if rd.change_type != ChangeType.UNCHANGED
                    ],
                    "local_tags": [
                        {
                            "name": td.name,
                            "change_type": td.change_type.value,
                            "changes": td.changes,
                        }
                        for td in pd.tag_diffs
                        if td.change_type != ChangeType.UNCHANGED
                    ],
                }
                for pd in self.program_diffs
                if pd.change_type != ChangeType.UNCHANGED or any(
                    rd.change_type != ChangeType.UNCHANGED for rd in pd.routine_diffs
                )
            ],
            "tags": [
                {
                    "name": td.name,
                    "change_type": td.change_type.value,
                    "data_type": (td.target_tag or td.source_tag).data_type,
                    "changes": td.changes,
                }
                for td in self.tag_diffs
                if td.change_type != ChangeType.UNCHANGED
            ],
        }
