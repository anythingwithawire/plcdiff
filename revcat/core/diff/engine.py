"""Diff engine for comparing two PLC projects."""

from datetime import datetime

from revcat.models.project import Project
from revcat.models.program import Program
from revcat.models.routine import Routine
from revcat.models.tag import Tag
from revcat.models.diff import (
    ChangeType,
    DiffResult,
    DiffSummary,
    ProgramDiff,
    RoutineDiff,
    TagDiff,
)


class DiffEngine:
    """Engine for computing differences between two PLC projects.

    Compares program structure, routines, and tags between a source
    (baseline) and target (modified) project.
    """

    def compare(self, source: Project, target: Project) -> DiffResult:
        """Compare two projects and return the diff result.

        Args:
            source: The baseline/original project.
            target: The modified/new project.

        Returns:
            DiffResult containing all differences found.
        """
        # Validate platforms match
        if source.platform != target.platform:
            raise ValueError(
                f"Cannot compare projects from different platforms: "
                f"{source.platform.value} vs {target.platform.value}"
            )

        # Compare programs
        program_diffs = self._compare_programs(source.programs, target.programs)

        # Compare controller-scope tags
        tag_diffs = self._compare_tags(source.tags, target.tags)

        # Build summary
        summary = self._build_summary(program_diffs, tag_diffs)

        return DiffResult(
            source=source,
            target=target,
            timestamp=datetime.now(),
            program_diffs=program_diffs,
            tag_diffs=tag_diffs,
            summary=summary,
        )

    def _compare_programs(
        self, source_programs: list[Program], target_programs: list[Program]
    ) -> list[ProgramDiff]:
        """Compare programs between source and target."""
        diffs = []

        source_by_name = {p.name: p for p in source_programs}
        target_by_name = {p.name: p for p in target_programs}

        all_names = set(source_by_name.keys()) | set(target_by_name.keys())

        for name in sorted(all_names):
            source_prog = source_by_name.get(name)
            target_prog = target_by_name.get(name)

            if source_prog is None:
                # Program added
                routine_diffs = [
                    RoutineDiff(
                        name=r.name,
                        program_name=name,
                        language=r.language,
                        change_type=ChangeType.ADDED,
                        target_routine=r,
                    )
                    for r in target_prog.routines
                ]
                tag_diffs = [
                    TagDiff(
                        name=t.name,
                        change_type=ChangeType.ADDED,
                        target_tag=t,
                    )
                    for t in target_prog.local_tags
                ]
                diffs.append(ProgramDiff(
                    name=name,
                    change_type=ChangeType.ADDED,
                    target_program=target_prog,
                    routine_diffs=routine_diffs,
                    tag_diffs=tag_diffs,
                ))

            elif target_prog is None:
                # Program removed
                routine_diffs = [
                    RoutineDiff(
                        name=r.name,
                        program_name=name,
                        language=r.language,
                        change_type=ChangeType.REMOVED,
                        source_routine=r,
                    )
                    for r in source_prog.routines
                ]
                tag_diffs = [
                    TagDiff(
                        name=t.name,
                        change_type=ChangeType.REMOVED,
                        source_tag=t,
                    )
                    for t in source_prog.local_tags
                ]
                diffs.append(ProgramDiff(
                    name=name,
                    change_type=ChangeType.REMOVED,
                    source_program=source_prog,
                    routine_diffs=routine_diffs,
                    tag_diffs=tag_diffs,
                ))

            else:
                # Program exists in both - compare contents
                routine_diffs = self._compare_routines(
                    source_prog.routines, target_prog.routines, name
                )
                tag_diffs = self._compare_tags(
                    source_prog.local_tags, target_prog.local_tags
                )

                # Determine if program itself changed (description, etc.)
                has_routine_changes = any(
                    d.change_type != ChangeType.UNCHANGED for d in routine_diffs
                )
                has_tag_changes = any(
                    d.change_type != ChangeType.UNCHANGED for d in tag_diffs
                )

                if has_routine_changes or has_tag_changes:
                    change_type = ChangeType.MODIFIED
                else:
                    change_type = ChangeType.UNCHANGED

                diffs.append(ProgramDiff(
                    name=name,
                    change_type=change_type,
                    source_program=source_prog,
                    target_program=target_prog,
                    routine_diffs=routine_diffs,
                    tag_diffs=tag_diffs,
                ))

        return diffs

    def _compare_routines(
        self,
        source_routines: list[Routine],
        target_routines: list[Routine],
        program_name: str,
    ) -> list[RoutineDiff]:
        """Compare routines between source and target."""
        diffs = []

        source_by_name = {r.name: r for r in source_routines}
        target_by_name = {r.name: r for r in target_routines}

        all_names = set(source_by_name.keys()) | set(target_by_name.keys())

        for name in sorted(all_names):
            source_routine = source_by_name.get(name)
            target_routine = target_by_name.get(name)

            if source_routine is None:
                # Routine added
                diffs.append(RoutineDiff(
                    name=name,
                    program_name=program_name,
                    language=target_routine.language,
                    change_type=ChangeType.ADDED,
                    target_routine=target_routine,
                ))

            elif target_routine is None:
                # Routine removed
                diffs.append(RoutineDiff(
                    name=name,
                    program_name=program_name,
                    language=source_routine.language,
                    change_type=ChangeType.REMOVED,
                    source_routine=source_routine,
                ))

            else:
                # Routine exists in both - compare
                changes = self._get_routine_changes(source_routine, target_routine)

                if changes:
                    change_type = ChangeType.MODIFIED
                else:
                    change_type = ChangeType.UNCHANGED

                diffs.append(RoutineDiff(
                    name=name,
                    program_name=program_name,
                    language=source_routine.language,
                    change_type=change_type,
                    source_routine=source_routine,
                    target_routine=target_routine,
                    changes=changes,
                ))

        return diffs

    def _get_routine_changes(
        self, source: Routine, target: Routine
    ) -> list[str]:
        """Detect what changed between two routines."""
        changes = []

        # Check language change (unlikely but possible)
        if source.language != target.language:
            changes.append(f"language: {source.language.value} → {target.language.value}")

        # Check description change
        if source.description != target.description:
            changes.append("description changed")

        # Check content counts (indicates structural changes)
        if source.language.value == "LD":
            if source.rung_count != target.rung_count:
                changes.append(f"rung count: {source.rung_count} → {target.rung_count}")
        elif source.language.value == "FBD":
            if source.network_count != target.network_count:
                changes.append(f"network count: {source.network_count} → {target.network_count}")
        elif source.language.value == "ST":
            if source.line_count != target.line_count:
                changes.append(f"line count: {source.line_count} → {target.line_count}")

        return changes

    def _compare_tags(
        self, source_tags: list[Tag], target_tags: list[Tag]
    ) -> list[TagDiff]:
        """Compare tags between source and target."""
        diffs = []

        source_by_name = {t.name: t for t in source_tags}
        target_by_name = {t.name: t for t in target_tags}

        all_names = set(source_by_name.keys()) | set(target_by_name.keys())

        for name in sorted(all_names):
            source_tag = source_by_name.get(name)
            target_tag = target_by_name.get(name)

            if source_tag is None:
                # Tag added
                diffs.append(TagDiff(
                    name=name,
                    change_type=ChangeType.ADDED,
                    target_tag=target_tag,
                ))

            elif target_tag is None:
                # Tag removed
                diffs.append(TagDiff(
                    name=name,
                    change_type=ChangeType.REMOVED,
                    source_tag=source_tag,
                ))

            else:
                # Tag exists in both - compare
                changes = self._get_tag_changes(source_tag, target_tag)

                if changes:
                    change_type = ChangeType.MODIFIED
                else:
                    change_type = ChangeType.UNCHANGED

                diffs.append(TagDiff(
                    name=name,
                    change_type=change_type,
                    source_tag=source_tag,
                    target_tag=target_tag,
                    changes=changes,
                ))

        return diffs

    def _get_tag_changes(self, source: Tag, target: Tag) -> list[str]:
        """Detect what changed between two tags."""
        changes = []

        if source.data_type != target.data_type:
            changes.append(f"data type: {source.data_type} → {target.data_type}")

        if source.description != target.description:
            if source.description and target.description:
                changes.append("description changed")
            elif target.description:
                changes.append("description added")
            else:
                changes.append("description removed")

        if source.initial_value != target.initial_value:
            src_val = source.initial_value or "(none)"
            tgt_val = target.initial_value or "(none)"
            changes.append(f"initial value: {src_val} → {tgt_val}")

        if source.dimensions != target.dimensions:
            src_dim = str(source.dimensions) if source.dimensions else "(scalar)"
            tgt_dim = str(target.dimensions) if target.dimensions else "(scalar)"
            changes.append(f"dimensions: {src_dim} → {tgt_dim}")

        if source.scope != target.scope:
            changes.append(f"scope: {source.scope.value} → {target.scope.value}")

        return changes

    def _build_summary(
        self, program_diffs: list[ProgramDiff], tag_diffs: list[TagDiff]
    ) -> DiffSummary:
        """Build summary statistics from diff results."""
        summary = DiffSummary()

        for pd in program_diffs:
            if pd.change_type == ChangeType.ADDED:
                summary.programs_added += 1
                # All routines in added program are considered added
                summary.routines_added += len(pd.routine_diffs)
                summary.tags_added += len(pd.tag_diffs)
            elif pd.change_type == ChangeType.REMOVED:
                summary.programs_removed += 1
                summary.routines_removed += len(pd.routine_diffs)
                summary.tags_removed += len(pd.tag_diffs)
            elif pd.change_type == ChangeType.MODIFIED:
                summary.programs_modified += 1
                # Count individual routine and tag changes
                for rd in pd.routine_diffs:
                    if rd.change_type == ChangeType.ADDED:
                        summary.routines_added += 1
                    elif rd.change_type == ChangeType.REMOVED:
                        summary.routines_removed += 1
                    elif rd.change_type == ChangeType.MODIFIED:
                        summary.routines_modified += 1
                for td in pd.tag_diffs:
                    if td.change_type == ChangeType.ADDED:
                        summary.tags_added += 1
                    elif td.change_type == ChangeType.REMOVED:
                        summary.tags_removed += 1
                    elif td.change_type == ChangeType.MODIFIED:
                        summary.tags_modified += 1

        # Count controller-scope tags
        for td in tag_diffs:
            if td.change_type == ChangeType.ADDED:
                summary.tags_added += 1
            elif td.change_type == ChangeType.REMOVED:
                summary.tags_removed += 1
            elif td.change_type == ChangeType.MODIFIED:
                summary.tags_modified += 1

        return summary
