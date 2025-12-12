"""Tests for L5X parser."""

from pathlib import Path

import pytest

from revcat.core.parsers import L5XParser, get_parser
from revcat.models import Platform
from revcat.models.routine import Language


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_L5X = FIXTURES_DIR / "sample.L5X"


class TestL5XParser:
    """Tests for the L5X parser."""

    def test_can_parse_valid_l5x(self):
        """Test that parser recognizes valid L5X files."""
        parser = L5XParser()
        assert parser.can_parse(SAMPLE_L5X) is True

    def test_can_parse_invalid_extension(self, tmp_path):
        """Test that parser rejects non-L5X files."""
        parser = L5XParser()
        fake_file = tmp_path / "test.txt"
        fake_file.write_text("Not an L5X file")
        assert parser.can_parse(fake_file) is False

    def test_can_parse_nonexistent(self, tmp_path):
        """Test that parser handles missing files."""
        parser = L5XParser()
        assert parser.can_parse(tmp_path / "missing.L5X") is False

    def test_parse_project_metadata(self):
        """Test parsing basic project metadata."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        assert project.name == "SampleController"
        assert project.platform == Platform.ROCKWELL
        assert project.software_version == "32.011"
        assert project.controller_type == "1756-L83E"

    def test_parse_programs(self):
        """Test parsing programs."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        assert len(project.programs) == 2

        program_names = [p.name for p in project.programs]
        assert "MainProgram" in program_names
        assert "SafetyProgram" in program_names

    def test_parse_routines(self):
        """Test parsing routines."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        assert len(main_prog.routines) == 2

        # Check ladder routine
        main_routine = main_prog.get_routine("MainRoutine")
        assert main_routine is not None
        assert main_routine.language == Language.LADDER
        assert main_routine.rung_count == 3

        # Check ST routine
        init_routine = main_prog.get_routine("Initialize")
        assert init_routine is not None
        assert init_routine.language == Language.ST
        assert init_routine.line_count == 6

    def test_parse_fbd_routine(self):
        """Test parsing FBD routine."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        safety_prog = next(p for p in project.programs if p.name == "SafetyProgram")
        safety_routine = safety_prog.get_routine("SafetyCheck")

        assert safety_routine is not None
        assert safety_routine.language == Language.FBD
        assert safety_routine.network_count == 2

    def test_parse_controller_tags(self):
        """Test parsing controller-scoped tags."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        assert len(project.tags) == 3

        tag_names = [t.name for t in project.tags]
        assert "System_Running" in tag_names
        assert "Motor_Speed" in tag_names
        assert "Temperature_Array" in tag_names

        # Check array tag
        temp_tag = next(t for t in project.tags if t.name == "Temperature_Array")
        assert temp_tag.is_array
        assert temp_tag.dimensions == [10]

    def test_parse_program_tags(self):
        """Test parsing program-scoped tags."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        assert len(main_prog.local_tags) == 1
        assert main_prog.local_tags[0].name == "Local_Counter"

    def test_parse_aoi_count(self):
        """Test counting AOIs."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        assert project.aoi_count == 2

    def test_total_routines(self):
        """Test total routine count."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        assert project.total_routines == 3  # 2 in MainProgram + 1 in SafetyProgram

    def test_total_tags(self):
        """Test total tag count."""
        parser = L5XParser()
        project = parser.parse(SAMPLE_L5X)

        # 3 controller tags + 1 program tag
        assert project.total_tags == 4


class TestParserRegistry:
    """Tests for parser registry."""

    def test_get_parser_for_l5x(self):
        """Test getting parser via registry."""
        parser = get_parser(SAMPLE_L5X)
        assert isinstance(parser, L5XParser)

    def test_get_parser_platform_name(self):
        """Test parser platform name."""
        parser = get_parser(SAMPLE_L5X)
        assert parser.get_platform_name() == "Rockwell Studio 5000"
