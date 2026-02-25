"""Tests for coverage analysis tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock, PropertyMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.coverage_tools import register_coverage_tools
from vgc_mcp_core.models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread
from vgc_mcp_core.team.manager import TeamManager


def _make_team_slot(name, types, moves):
    """Helper to create a mock team slot."""
    pokemon = MagicMock()
    pokemon.name = name
    pokemon.types = types
    pokemon.moves = moves
    slot = MagicMock()
    slot.pokemon = pokemon
    return slot


@pytest.fixture
def team_manager():
    """Create a mock team manager with a team."""
    manager = MagicMock()
    team = MagicMock()
    team.slots = [
        _make_team_slot("Flutter Mane", ["Ghost", "Fairy"], ["Moonblast", "Shadow Ball", "Dazzling Gleam", "Protect"]),
        _make_team_slot("Incineroar", ["Fire", "Dark"], ["Fake Out", "Flare Blitz", "Knock Off", "Parting Shot"]),
        _make_team_slot("Rillaboom", ["Grass"], ["Grassy Glide", "Wood Hammer", "Fake Out", "U-Turn"]),
    ]
    manager.get_current_team.return_value = team
    return manager


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_pokemon_types = AsyncMock(return_value=["Water", "Fighting"])
    # check_coverage_vs_target uses get_pokemon() which returns a dict with "types"
    client.get_pokemon = AsyncMock(return_value={"types": ["Water", "Fighting"]})
    return client


@pytest.fixture
def tools(team_manager, mock_pokeapi):
    """Register coverage tools and return functions."""
    mcp = FastMCP("test")
    register_coverage_tools(mcp, team_manager, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAnalyzeTeamMoveCoverage:
    """Tests for analyze_team_move_coverage."""

    async def test_coverage_with_team(self, tools):
        """Test coverage analysis with a team."""
        fn = tools["analyze_team_move_coverage"].fn
        result = await fn()
        assert "error" not in result
        assert "coverage_summary" in result
        assert "team_pokemon" in result

    async def test_empty_team(self, tools, team_manager):
        """Test coverage with empty team."""
        team = MagicMock()
        team.slots = []
        team_manager.get_current_team.return_value = team
        fn = tools["analyze_team_move_coverage"].fn
        result = await fn()
        assert "error" in result

    async def test_no_team(self, tools, team_manager):
        """Test coverage with no team."""
        team_manager.get_current_team.return_value = None
        fn = tools["analyze_team_move_coverage"].fn
        result = await fn()
        assert "error" in result


class TestFindTeamCoverageHoles:
    """Tests for find_team_coverage_holes."""

    async def test_finds_holes(self, tools):
        """Test finding coverage holes."""
        fn = tools["find_team_coverage_holes"].fn
        result = await fn()
        assert "holes" in result
        assert "has_holes" in result

    async def test_empty_team(self, tools, team_manager):
        """Test with empty team."""
        team = MagicMock()
        team.slots = []
        team_manager.get_current_team.return_value = team
        fn = tools["find_team_coverage_holes"].fn
        result = await fn()
        assert result["holes"] == []


class TestCheckTeamQuadWeaknesses:
    """Tests for check_team_quad_weaknesses."""

    async def test_with_team(self, tools):
        """Test quad weakness check with a team."""
        fn = tools["check_team_quad_weaknesses"].fn
        result = await fn()
        assert "quad_weaknesses" in result
        assert "has_quad_weakness" in result

    async def test_empty_team(self, tools, team_manager):
        """Test quad weakness check with empty team."""
        team = MagicMock()
        team.slots = []
        team_manager.get_current_team.return_value = team
        fn = tools["check_team_quad_weaknesses"].fn
        result = await fn()
        assert result["quad_weaknesses"] == []


class TestCheckCoverageVsTarget:
    """Tests for check_coverage_vs_target."""

    async def test_coverage_vs_pokemon(self, tools):
        """Test checking coverage against a specific Pokemon."""
        fn = tools["check_coverage_vs_target"].fn
        result = await fn(target_pokemon="urshifu-rapid-strike")
        assert "has_coverage" in result
        assert "target_pokemon" in result

    async def test_empty_team(self, tools, team_manager):
        """Test with empty team."""
        team = MagicMock()
        team.slots = []
        team_manager.get_current_team.return_value = team
        fn = tools["check_coverage_vs_target"].fn
        result = await fn(target_pokemon="incineroar")
        assert result["has_coverage"] is False

    async def test_pokemon_fetch_error(self, tools, mock_pokeapi):
        """Test handling of failed Pokemon fetch."""
        mock_pokeapi.get_pokemon.side_effect = Exception("Not found")
        fn = tools["check_coverage_vs_target"].fn
        result = await fn(target_pokemon="xyznonexistent")
        assert "error" in result


class TestGetCoverageMoveOptions:
    """Tests for get_coverage_move_options."""

    async def test_fire_coverage_moves(self, tools):
        """Test getting Fire coverage moves."""
        fn = tools["get_coverage_move_options"].fn
        result = await fn(move_type="Fire")
        assert "type" in result
        assert result["type"] == "Fire"
        assert "super_effective_vs" in result

    async def test_invalid_type(self, tools):
        """Test invalid type returns error."""
        fn = tools["get_coverage_move_options"].fn
        result = await fn(move_type="InvalidType")
        assert "error" in result
