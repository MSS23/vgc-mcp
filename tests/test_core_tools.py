"""Tests for core building and team suggestion tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.core_tools import register_core_tools


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.size = 0
    manager.is_full = False
    manager.team = MagicMock()
    manager.team.get_pokemon_names.return_value = []
    return manager


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def tools(mock_team_manager, mock_smogon):
    """Register core tools and return functions."""
    mcp = FastMCP("test")
    register_core_tools(mcp, mock_team_manager, mock_smogon)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestGetPokemonRoles:
    """Tests for get_pokemon_roles."""

    async def test_known_pokemon(self, tools):
        """Test getting roles for a known Pokemon."""
        fn = tools["get_pokemon_roles"].fn
        result = await fn(pokemon_name="incineroar")
        assert result["pokemon"] == "incineroar"
        assert "roles" in result

    async def test_unknown_pokemon(self, tools):
        """Test getting roles for a Pokemon without specific roles."""
        fn = tools["get_pokemon_roles"].fn
        result = await fn(pokemon_name="magikarp")
        assert "roles" in result


class TestListRolePokemon:
    """Tests for list_role_pokemon."""

    async def test_valid_role(self, tools):
        """Test listing Pokemon for a valid role."""
        fn = tools["list_role_pokemon"].fn
        result = await fn(role="fake_out")
        assert "pokemon" in result
        assert result["count"] > 0

    async def test_invalid_role(self, tools):
        """Test with an invalid role."""
        fn = tools["list_role_pokemon"].fn
        result = await fn(role="nonexistent_role")
        assert "error" in result
        assert "available_roles" in result


class TestAnalyzeTeamSynergy:
    """Tests for analyze_team_synergy."""

    async def test_empty_team(self, tools):
        """Test with fewer than 2 Pokemon."""
        fn = tools["analyze_team_synergy"].fn
        result = await fn()
        assert "error" in result


class TestSuggestTeamCompletion:
    """Tests for suggest_team_completion."""

    async def test_empty_team(self, tools):
        """Test with no Pokemon on team."""
        fn = tools["suggest_team_completion"].fn
        result = await fn()
        assert "error" in result

    async def test_full_team(self, tools, mock_team_manager):
        """Test with a full team."""
        mock_team_manager.size = 6
        mock_team_manager.is_full = True
        mock_team_manager.team.get_pokemon_names.return_value = ["a", "b", "c", "d", "e", "f"]

        fn = tools["suggest_team_completion"].fn
        result = await fn()
        assert "message" in result
        assert "full" in result["message"].lower()


class TestSuggestPartnersWithSynergy:
    """Tests for suggest_partners_with_synergy."""

    async def test_no_data(self, tools, mock_smogon):
        """Test when Smogon returns no suggestions."""
        import vgc_mcp.tools.core_tools as mod
        original = mod.suggest_partners
        async def mock_suggest(*args, **kwargs):
            return []
        mod.suggest_partners = mock_suggest

        try:
            fn = tools["suggest_partners_with_synergy"].fn
            result = await fn(pokemon_name="unknown-pokemon")
            assert "error" in result
        finally:
            mod.suggest_partners = original
