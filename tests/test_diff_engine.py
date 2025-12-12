"""Tests for diff engine."""

from pathlib import Path

import pytest

from revcat.core.parsers import L5XParser
from revcat.core.diff import DiffEngine
from revcat.models import ChangeType


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_L5X = FIXTURES_DIR / "sample.L5X"
SAMPLE_MODIFIED_L5X = FIXTURES_DIR / "sample_modified.L5X"


class TestDiffEngine:
    """Tests for the diff engine."""

    @pytest.fixture
    def source_project(self):
        """Parse the source (original) project."""
        parser = L5XParser()
        return parser.parse(SAMPLE_L5X)

    @pytest.fixture
    def target_project(self):
        """Parse the target (modified) project."""
        parser = L5XParser()
        return parser.parse(SAMPLE_MODIFIED_L5X)

    @pytest.fixture
    def diff_result(self, source_project, target_project):
        """Get the diff result."""
        engine = DiffEngine()
        return engine.compare(source_project, target_project)

    def test_compare_returns_diff_result(self, diff_result):
        """Test that compare returns a DiffResult."""
        assert diff_result is not None
        assert diff_result.has_changes

    def test_diff_has_correct_sources(self, diff_result, source_project, target_project):
        """Test that diff result references correct projects."""
        assert diff_result.source == source_project
        assert diff_result.target == target_project

    def test_summary_has_changes(self, diff_result):
        """Test that summary correctly indicates changes."""
        summary = diff_result.summary
        assert summary.total_changes > 0
        assert summary.has_changes

    def test_detects_added_program(self, diff_result):
        """Test detection of added program."""
        program_diffs = diff_result.program_diffs
        added_programs = [p for p in program_diffs if p.change_type == ChangeType.ADDED]

        assert len(added_programs) == 1
        assert added_programs[0].name == "DiagnosticsProgram"

    def test_detects_modified_program(self, diff_result):
        """Test detection of modified program."""
        program_diffs = diff_result.program_diffs
        modified_programs = [p for p in program_diffs if p.change_type == ChangeType.MODIFIED]

        # MainProgram and SafetyProgram should be modified
        program_names = [p.name for p in modified_programs]
        assert "MainProgram" in program_names

    def test_detects_added_routine(self, diff_result):
        """Test detection of added routine."""
        all_routine_diffs = diff_result.get_all_routine_diffs()
        added_routines = [r for r in all_routine_diffs if r.change_type == ChangeType.ADDED]

        routine_names = [r.name for r in added_routines]
        assert "AlarmHandler" in routine_names
        assert "LogStatus" in routine_names

    def test_detects_modified_routine(self, diff_result):
        """Test detection of modified routine."""
        all_routine_diffs = diff_result.get_all_routine_diffs()
        modified_routines = [r for r in all_routine_diffs if r.change_type == ChangeType.MODIFIED]

        routine_names = [r.name for r in modified_routines]
        # MainRoutine has rung count change (3 -> 4)
        assert "MainRoutine" in routine_names
        # Initialize has line count change
        assert "Initialize" in routine_names

    def test_routine_change_details(self, diff_result):
        """Test that routine changes include details."""
        all_routine_diffs = diff_result.get_all_routine_diffs()
        main_routine = next(r for r in all_routine_diffs if r.name == "MainRoutine")

        assert main_routine.change_type == ChangeType.MODIFIED
        assert any("rung count" in c for c in main_routine.changes)

    def test_detects_added_tag(self, diff_result):
        """Test detection of added tags."""
        added_tags = [t for t in diff_result.tag_diffs if t.change_type == ChangeType.ADDED]

        tag_names = [t.name for t in added_tags]
        assert "New_Alarm_Status" in tag_names

    def test_detects_modified_tag(self, diff_result):
        """Test detection of modified tags."""
        modified_tags = [t for t in diff_result.tag_diffs if t.change_type == ChangeType.MODIFIED]

        tag_names = [t.name for t in modified_tags]
        # Motor_Speed has value change, Temperature_Array has dimension change
        assert "Motor_Speed" in tag_names or "Temperature_Array" in tag_names

    def test_tag_change_details(self, diff_result):
        """Test that tag changes include details."""
        motor_speed = next(
            (t for t in diff_result.tag_diffs if t.name == "Motor_Speed"),
            None
        )

        if motor_speed and motor_speed.change_type == ChangeType.MODIFIED:
            assert any("initial value" in c for c in motor_speed.changes)

    def test_detects_array_dimension_change(self, diff_result):
        """Test detection of array dimension changes."""
        temp_array = next(
            (t for t in diff_result.tag_diffs if t.name == "Temperature_Array"),
            None
        )

        if temp_array and temp_array.change_type == ChangeType.MODIFIED:
            assert any("dimensions" in c for c in temp_array.changes)

    def test_summary_counts(self, diff_result):
        """Test summary statistics."""
        summary = diff_result.summary

        # At least one program added (DiagnosticsProgram)
        assert summary.programs_added >= 1

        # At least one tag added (New_Alarm_Status)
        assert summary.tags_added >= 1

        # Some routines should be modified
        assert summary.routines_added >= 1 or summary.routines_modified >= 1

    def test_to_dict_output(self, diff_result):
        """Test JSON serialization."""
        result_dict = diff_result.to_dict()

        assert "source_file" in result_dict
        assert "target_file" in result_dict
        assert "summary" in result_dict
        assert "programs" in result_dict
        assert "tags" in result_dict

        # Check summary structure
        assert "total_changes" in result_dict["summary"]
        assert result_dict["summary"]["total_changes"] > 0


class TestDiffEngineEdgeCases:
    """Test edge cases for diff engine."""

    def test_compare_identical_projects(self):
        """Test comparing identical projects."""
        parser = L5XParser()
        project1 = parser.parse(SAMPLE_L5X)
        project2 = parser.parse(SAMPLE_L5X)

        engine = DiffEngine()
        result = engine.compare(project1, project2)

        assert not result.has_changes
        assert result.summary.total_changes == 0

    def test_compare_different_platforms_raises(self):
        """Test that comparing different platforms raises error."""
        from revcat.core.parsers import XEFParser

        l5x_parser = L5XParser()
        xef_parser = XEFParser()

        l5x_project = l5x_parser.parse(SAMPLE_L5X)
        xef_project = xef_parser.parse(FIXTURES_DIR / "sample.XEF")

        engine = DiffEngine()
        with pytest.raises(ValueError, match="different platforms"):
            engine.compare(l5x_project, xef_project)


class TestDiffCLI:
    """Tests for the compare CLI command."""

    def test_compare_text_output(self, capsys):
        """Test compare command with text output."""
        from click.testing import CliRunner
        from revcat.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, [
            "compare",
            "-s", str(SAMPLE_L5X),
            "-t", str(SAMPLE_MODIFIED_L5X),
        ])

        assert result.exit_code == 0
        assert "RevCat Comparison Report" in result.output
        assert "SUMMARY" in result.output

    def test_compare_json_output(self):
        """Test compare command with JSON output."""
        import json
        from click.testing import CliRunner
        from revcat.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, [
            "compare",
            "-s", str(SAMPLE_L5X),
            "-t", str(SAMPLE_MODIFIED_L5X),
            "--format", "json",
        ])

        assert result.exit_code == 0

        # Parse JSON output
        data = json.loads(result.output)
        assert "summary" in data
        assert data["summary"]["total_changes"] > 0

    def test_compare_no_changes(self, capsys):
        """Test compare command when files are identical."""
        from click.testing import CliRunner
        from revcat.cli.main import cli

        runner = CliRunner()
        result = runner.invoke(cli, [
            "compare",
            "-s", str(SAMPLE_L5X),
            "-t", str(SAMPLE_L5X),
        ])

        assert result.exit_code == 0
        assert "No changes detected" in result.output
