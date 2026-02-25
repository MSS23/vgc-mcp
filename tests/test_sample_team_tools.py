"""Tests for sample team tools."""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.sample_team_tools import register_sample_team_tools
from vgc_mcp_core.data.sample_teams import ALL_SAMPLE_TEAMS, get_all_archetypes


@pytest.fixture
def tools():
    """Register sample team tools and return tool functions."""
    mcp = FastMCP("test")
    register_sample_team_tools(mcp)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGetSampleTeam:
    """Tests for the get_sample_team tool."""

    async def test_get_all_teams(self, tools):
        """Test getting all sample teams with no filters."""
        fn = tools["get_sample_team"].fn
        result = await fn()
        assert "count" in result
        assert "teams" in result
        assert result["count"] == len(ALL_SAMPLE_TEAMS)

    async def test_filter_by_archetype(self, tools):
        """Test filtering by archetype."""
        fn = tools["get_sample_team"].fn
        archetypes = get_all_archetypes()
        if archetypes:
            result = await fn(archetype=archetypes[0])
            assert "count" in result
            for team in result["teams"]:
                assert team["archetype"].lower() == archetypes[0].lower()

    async def test_filter_no_match(self, tools):
        """Test filtering that returns no results."""
        fn = tools["get_sample_team"].fn
        result = await fn(archetype="nonexistent_archetype_xyz")
        assert "error" in result
        assert "available_archetypes" in result

    async def test_filter_by_pokemon(self, tools):
        """Test filtering by Pokemon name."""
        fn = tools["get_sample_team"].fn
        # Use a Pokemon from the first sample team
        if ALL_SAMPLE_TEAMS:
            pokemon = ALL_SAMPLE_TEAMS[0].pokemon[0]
            result = await fn(pokemon=pokemon)
            assert "count" in result
            assert result["count"] >= 1

    async def test_team_format(self, tools):
        """Test that team data has expected format."""
        fn = tools["get_sample_team"].fn
        result = await fn()
        if result.get("teams"):
            team = result["teams"][0]
            assert "name" in team
            assert "archetype" in team
            assert "pokemon" in team
            assert "description" in team
            assert "strengths" in team
            assert "weaknesses" in team


class TestListSampleTeamArchetypes:
    """Tests for the list_sample_team_archetypes tool."""

    async def test_returns_archetypes(self, tools):
        """Test that archetypes are listed."""
        fn = tools["list_sample_team_archetypes"].fn
        result = await fn()
        assert "archetypes" in result
        assert "total_teams" in result
        assert result["total_teams"] == len(ALL_SAMPLE_TEAMS)

    async def test_archetype_structure(self, tools):
        """Test archetype has name and description."""
        fn = tools["list_sample_team_archetypes"].fn
        result = await fn()
        for arch in result["archetypes"]:
            assert "name" in arch
            assert "description" in arch


class TestGetTeamPaste:
    """Tests for the get_team_paste tool."""

    async def test_get_existing_team(self, tools):
        """Test getting paste for an existing team."""
        fn = tools["get_team_paste"].fn
        if ALL_SAMPLE_TEAMS:
            team_name = ALL_SAMPLE_TEAMS[0].name
            result = await fn(team_name=team_name)
            assert "paste" in result
            assert result["name"] == team_name

    async def test_team_not_found(self, tools):
        """Test getting paste for non-existent team."""
        fn = tools["get_team_paste"].fn
        result = await fn(team_name="nonexistent_team_xyz")
        assert "error" in result
        assert "available_teams" in result


class TestSuggestTeamForPlaystyle:
    """Tests for the suggest_team_for_playstyle tool."""

    async def test_aggressive_playstyle(self, tools):
        """Test suggestion for aggressive playstyle."""
        fn = tools["suggest_team_for_playstyle"].fn
        result = await fn(playstyle="aggressive")
        assert "playstyle" in result
        assert result["playstyle"] == "aggressive"
        # Should return at least a recommended team or alternatives
        assert result.get("recommended") is not None or result.get("alternatives") is not None

    async def test_defensive_playstyle(self, tools):
        """Test suggestion for defensive playstyle."""
        fn = tools["suggest_team_for_playstyle"].fn
        result = await fn(playstyle="defensive")
        assert result["playstyle"] == "defensive"

    async def test_unknown_playstyle_defaults(self, tools):
        """Test unknown playstyle falls back to default."""
        fn = tools["suggest_team_for_playstyle"].fn
        result = await fn(playstyle="unknown_style")
        # Should still return something (defaults to goodstuffs)
        assert "playstyle" in result

    async def test_experience_level_filter(self, tools):
        """Test filtering by experience level."""
        fn = tools["suggest_team_for_playstyle"].fn
        result = await fn(playstyle="aggressive", experience_level="beginner")
        assert result["experience_level"] == "beginner"
