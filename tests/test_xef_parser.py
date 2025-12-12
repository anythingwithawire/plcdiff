"""Tests for XEF parser."""

from pathlib import Path

import pytest

from revcat.core.parsers import XEFParser, get_parser
from revcat.models import Platform
from revcat.models.routine import Language


FIXTURES_DIR = Path(__file__).parent / "fixtures"
SAMPLE_XEF = FIXTURES_DIR / "sample.XEF"


class TestXEFParser:
    """Tests for the XEF parser."""

    def test_can_parse_valid_xef(self):
        """Test that parser recognizes valid XEF files."""
        parser = XEFParser()
        assert parser.can_parse(SAMPLE_XEF) is True

    def test_can_parse_invalid_extension(self, tmp_path):
        """Test that parser rejects non-XEF files."""
        parser = XEFParser()
        fake_file = tmp_path / "test.txt"
        fake_file.write_text("Not an XEF file")
        assert parser.can_parse(fake_file) is False

    def test_can_parse_nonexistent(self, tmp_path):
        """Test that parser handles missing files."""
        parser = XEFParser()
        assert parser.can_parse(tmp_path / "missing.XEF") is False

    def test_parse_project_metadata(self):
        """Test parsing basic project metadata."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        assert project.name == "ConveyorControl"
        assert project.platform == Platform.SCHNEIDER
        assert project.version == "14.1"
        assert project.controller_type == "M340"

    def test_parse_modified_date(self):
        """Test parsing modification date."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        assert project.modified is not None
        assert project.modified.year == 2024
        assert project.modified.month == 12
        assert project.modified.day == 10

    def test_parse_programs(self):
        """Test parsing programs."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        assert len(project.programs) == 2

        program_names = [p.name for p in project.programs]
        assert "MainProgram" in program_names
        assert "DiagnosticsProgram" in program_names

    def test_parse_routines(self):
        """Test parsing routines/sections."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        assert len(main_prog.routines) == 3

        routine_names = [r.name for r in main_prog.routines]
        assert "Startup" in routine_names
        assert "MainControl" in routine_names
        assert "SafetyLogic" in routine_names

    def test_parse_st_routine(self):
        """Test parsing ST routine."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        startup = next(r for r in main_prog.routines if r.name == "Startup")

        assert startup.language == Language.ST
        assert startup.line_count > 0

    def test_parse_ld_routine(self):
        """Test parsing Ladder routine."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        main_control = next(r for r in main_prog.routines if r.name == "MainControl")

        assert main_control.language == Language.LADDER
        assert main_control.rung_count == 4

    def test_parse_fbd_routine(self):
        """Test parsing FBD routine."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        safety_logic = next(r for r in main_prog.routines if r.name == "SafetyLogic")

        assert safety_logic.language == Language.FBD
        assert safety_logic.network_count == 3

    def test_parse_variables(self):
        """Test parsing global variables."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        assert len(project.tags) == 4

        tag_names = [t.name for t in project.tags]
        assert "System_Status" in tag_names
        assert "Conveyor_Speed" in tag_names
        assert "Temperature_Sensors" in tag_names
        assert "Motor_Running" in tag_names

    def test_parse_array_variable(self):
        """Test parsing array variable."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        temp_tag = next(t for t in project.tags if t.name == "Temperature_Sensors")
        assert temp_tag.is_array
        assert temp_tag.dimensions == [8]
        assert temp_tag.data_type == "REAL"

    def test_parse_variable_with_value(self):
        """Test parsing variable with initial value."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        speed_tag = next(t for t in project.tags if t.name == "Conveyor_Speed")
        assert speed_tag.initial_value == "100"
        assert speed_tag.data_type == "INT"

    def test_parse_local_variables(self):
        """Test parsing program-local variables."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        main_prog = next(p for p in project.programs if p.name == "MainProgram")
        assert len(main_prog.local_tags) == 1
        assert main_prog.local_tags[0].name == "Local_Timer"

    def test_parse_dfb_count(self):
        """Test counting DFBs."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        assert project.aoi_count == 3

    def test_total_routines(self):
        """Test total routine count."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        # 3 in MainProgram + 1 in DiagnosticsProgram
        assert project.total_routines == 4

    def test_total_tags(self):
        """Test total tag count."""
        parser = XEFParser()
        project = parser.parse(SAMPLE_XEF)

        # 4 global tags + 1 program local tag
        assert project.total_tags == 5


class TestXEFParserRegistry:
    """Tests for XEF parser in registry."""

    def test_get_parser_for_xef(self):
        """Test getting parser via registry."""
        parser = get_parser(SAMPLE_XEF)
        assert isinstance(parser, XEFParser)

    def test_get_parser_platform_name(self):
        """Test parser platform name."""
        parser = get_parser(SAMPLE_XEF)
        assert parser.get_platform_name() == "Schneider EcoStruxure Control Expert"
