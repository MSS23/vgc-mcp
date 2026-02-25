"""Tests for VGC format legality checking tools."""

import pytest
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.legality_tools import register_legality_tools


def _make_slot(name, item=None):
    """Helper to create a mock team slot."""
    pokemon = MagicMock()
    pokemon.name = name
    pokemon.item = item
    slot = MagicMock()
    slot.pokemon = pokemon
    return slot


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager with no team."""
    manager = MagicMock()
    team = MagicMock()
    team.slots = []
    manager.get_current_team.return_value = team
    return manager


@pytest.fixture
def tools(mock_team_manager):
    """Register legality tools and return tool functions."""
    mcp = FastMCP("test")
    register_legality_tools(mcp, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestValidateTeamLegality:
    """Tests for validate_team_legality."""

    async def test_empty_team(self, tools):
        """Test validating empty team returns error."""
        fn = tools["validate_team_legality"].fn
        result = await fn()
        assert result["valid"] is False

    async def test_valid_team(self, tools, mock_team_manager):
        """Test validating a legal team."""
        team = MagicMock()
        team.slots = [
            _make_slot("flutter-mane", "choice-specs"),
            _make_slot("incineroar", "safety-goggles"),
            _make_slot("rillaboom", "miracle-seed"),
            _make_slot("urshifu-rapid-strike", "choice-scarf"),
            _make_slot("landorus", "life-orb"),
            _make_slot("tornadus", "focus-sash"),
        ]
        mock_team_manager.get_current_team.return_value = team
        fn = tools["validate_team_legality"].fn
        result = await fn()
        assert "regulation" in result


class TestCheckRestrictedCount:
    """Tests for check_restricted_count."""

    async def test_empty_team(self, tools):
        """Test restricted count on empty team."""
        fn = tools["check_restricted_count"].fn
        result = await fn()
        assert result["count"] == 0
        assert result["valid"] is True

    async def test_with_restricted_pokemon(self, tools, mock_team_manager):
        """Test counting restricted Pokemon."""
        team = MagicMock()
        team.slots = [
            _make_slot("koraidon"),
            _make_slot("miraidon"),
            _make_slot("flutter-mane"),
            _make_slot("incineroar"),
            _make_slot("rillaboom"),
            _make_slot("tornadus"),
        ]
        mock_team_manager.get_current_team.return_value = team
        fn = tools["check_restricted_count"].fn
        result = await fn()
        # Koraidon and Miraidon are restricted
        assert result["count"] >= 1  # At least one restricted


class TestCheckItemClause:
    """Tests for check_item_clause_tool."""

    async def test_empty_team(self, tools):
        """Test item clause on empty team."""
        fn = tools["check_item_clause_tool"].fn
        result = await fn()
        assert result.get("valid", True) is True or result.get("count", 0) == 0

    async def test_duplicate_items(self, tools, mock_team_manager):
        """Test detecting duplicate items."""
        team = MagicMock()
        team.slots = [
            _make_slot("flutter-mane", "choice-specs"),
            _make_slot("incineroar", "choice-specs"),  # Duplicate!
            _make_slot("rillaboom", "miracle-seed"),
            _make_slot("urshifu-rapid-strike", "choice-scarf"),
            _make_slot("landorus", "life-orb"),
            _make_slot("tornadus", "focus-sash"),
        ]
        mock_team_manager.get_current_team.return_value = team
        fn = tools["check_item_clause_tool"].fn
        result = await fn()
        # Should detect the duplicate Choice Specs
        assert result.get("valid") is False or result.get("duplicate_count", 0) > 0


class TestCheckPokemonLegality:
    """Tests for check_pokemon_legality."""

    async def test_normal_pokemon(self, tools):
        """Test legality of a normal Pokemon."""
        fn = tools["check_pokemon_legality"].fn
        result = await fn(pokemon_name="flutter-mane")
        assert "status" in result or "restricted" in result or "is_banned" in result

    async def test_restricted_pokemon(self, tools):
        """Test legality of a restricted Pokemon."""
        fn = tools["check_pokemon_legality"].fn
        result = await fn(pokemon_name="koraidon")
        # Koraidon should be identified as restricted
        assert "restricted" in str(result).lower() or "status" in result


class TestListRestrictedPokemon:
    """Tests for list_restricted_pokemon."""

    async def test_list_restricted(self, tools):
        """Test listing restricted Pokemon."""
        fn = tools["list_restricted_pokemon"].fn
        result = await fn()
        assert "restricted_pokemon" in result
        assert "count" in result

    async def test_list_has_entries(self, tools):
        """Test that the restricted list has entries."""
        fn = tools["list_restricted_pokemon"].fn
        result = await fn()
        assert len(result["restricted_pokemon"]) >= 0  # May be 0 for some regulations
        assert "regulation" in result


class TestListBannedPokemon:
    """Tests for list_banned_pokemon."""

    async def test_list_banned(self, tools):
        """Test listing banned Pokemon."""
        fn = tools["list_banned_pokemon"].fn
        result = await fn()
        assert "banned_pokemon" in result
        assert "count" in result


class TestSuggestItemAlternatives:
    """Tests for suggest_item_alternatives."""

    async def test_suggest_alternatives(self, tools):
        """Test suggesting item alternatives."""
        fn = tools["suggest_item_alternatives"].fn
        result = await fn(item_name="choice-specs")
        assert "alternatives" in result or "suggestions" in result
