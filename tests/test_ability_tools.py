"""Tests for ability synergy analysis tools."""

import pytest
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.ability_tools import register_ability_tools


def _make_slot(name, ability):
    """Create a mock team slot with a Pokemon that has an ability."""
    slot = MagicMock()
    slot.pokemon.name = name
    slot.pokemon.ability = ability
    return slot


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.get_current_team.return_value = None
    return manager


@pytest.fixture
def tools(mock_team_manager):
    """Register ability tools and return functions."""
    mcp = FastMCP("test")
    register_ability_tools(mcp, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAnalyzeTeamAbilities:
    """Tests for analyze_team_abilities."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["analyze_team_abilities"].fn
        result = await fn()
        assert "error" in result

    async def test_team_with_abilities(self, tools, mock_team_manager):
        """Test with a team that has abilities."""
        team = MagicMock()
        team.slots = [
            _make_slot("incineroar", "Intimidate"),
            _make_slot("rillaboom", "Grassy Surge"),
        ]
        mock_team_manager.get_current_team.return_value = team

        fn = tools["analyze_team_abilities"].fn
        result = await fn()
        assert "weather" in result
        assert "terrain" in result
        assert "intimidate" in result


class TestCheckIntimidateAnswers:
    """Tests for check_intimidate_answers."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["check_intimidate_answers"].fn
        result = await fn()
        assert result["protected"] is False

    async def test_team_with_intimidate(self, tools, mock_team_manager):
        """Test team that has Intimidate user."""
        team = MagicMock()
        team.slots = [
            _make_slot("incineroar", "Intimidate"),
            _make_slot("flutter-mane", "Protosynthesis"),
        ]
        mock_team_manager.get_current_team.return_value = team

        fn = tools["check_intimidate_answers"].fn
        result = await fn()
        assert result["has_intimidate"] is True


class TestCheckRedirectAbilities:
    """Tests for check_redirect_abilities."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["check_redirect_abilities"].fn
        result = await fn()
        assert result["redirects"] == []

    async def test_team_with_redirect(self, tools, mock_team_manager):
        """Test team with redirect ability."""
        team = MagicMock()
        team.slots = [
            _make_slot("raichu", "Lightning Rod"),
        ]
        mock_team_manager.get_current_team.return_value = team

        fn = tools["check_redirect_abilities"].fn
        result = await fn()
        assert result["has_redirect"] is True


class TestCheckPartnerAbilities:
    """Tests for check_partner_abilities."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["check_partner_abilities"].fn
        result = await fn()
        assert result["partner_abilities"] == []


class TestGetCommonIntimidatePokemon:
    """Tests for get_common_intimidate_pokemon."""

    async def test_returns_pokemon_list(self, tools):
        """Test that it returns Intimidate Pokemon list."""
        fn = tools["get_common_intimidate_pokemon"].fn
        result = await fn()
        assert "intimidate_pokemon" in result
        assert "common_vgc_users" in result
        assert "counters" in result
        assert len(result["common_vgc_users"]) > 0


class TestGetWeatherAbilityInfo:
    """Tests for get_weather_ability_info."""

    async def test_returns_weather_info(self, tools):
        """Test that it returns weather ability information."""
        fn = tools["get_weather_ability_info"].fn
        result = await fn()
        assert "weather_setters" in result
        assert "weather_abusers" in result
        assert "notes" in result


class TestSuggestAbilityAdditions:
    """Tests for suggest_ability_additions."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["suggest_ability_additions"].fn
        result = await fn()
        assert result["suggestions"] == []

    async def test_with_team_style(self, tools, mock_team_manager):
        """Test with a specific team style."""
        team = MagicMock()
        team.slots = [_make_slot("flutter-mane", "Protosynthesis")]
        mock_team_manager.get_current_team.return_value = team

        fn = tools["suggest_ability_additions"].fn
        result = await fn(team_style="sun")
        assert "suggestions" in result
        assert result["team_style"] == "sun"


class TestFindAbilityConflicts:
    """Tests for find_ability_conflicts."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["find_ability_conflicts"].fn
        result = await fn()
        assert result["conflicts"] == []
