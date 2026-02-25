"""Tests for priority move and turn order analysis tools."""

import pytest
from unittest.mock import MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.priority_tools import register_priority_tools


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.get_current_team.return_value = None
    return manager


@pytest.fixture
def tools(mock_team_manager):
    """Register priority tools and return functions."""
    mcp = FastMCP("test")
    register_priority_tools(mcp, mock_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestAnalyzeTurnOrder:
    """Tests for analyze_turn_order."""

    async def test_higher_priority_moves_first(self, tools):
        """Test that higher priority move goes first."""
        fn = tools["analyze_turn_order"].fn
        result = await fn(
            pokemon1_name="incineroar",
            pokemon1_move="fake-out",
            pokemon1_speed=80,
            pokemon2_name="flutter-mane",
            pokemon2_move="moonblast",
            pokemon2_speed=200
        )
        assert result["first_mover"] == "incineroar"
        assert result["pokemon1"]["priority"] > result["pokemon2"]["priority"]

    async def test_same_priority_faster_wins(self, tools):
        """Test that faster Pokemon moves first at same priority."""
        fn = tools["analyze_turn_order"].fn
        result = await fn(
            pokemon1_name="flutter-mane",
            pokemon1_move="moonblast",
            pokemon1_speed=200,
            pokemon2_name="incineroar",
            pokemon2_move="flare-blitz",
            pokemon2_speed=80
        )
        assert result["first_mover"] == "flutter-mane"

    async def test_trick_room_reverses(self, tools):
        """Test that Trick Room reverses speed order."""
        fn = tools["analyze_turn_order"].fn
        result = await fn(
            pokemon1_name="incineroar",
            pokemon1_move="flare-blitz",
            pokemon1_speed=80,
            pokemon2_name="flutter-mane",
            pokemon2_move="moonblast",
            pokemon2_speed=200,
            trick_room=True
        )
        assert result["first_mover"] == "incineroar"
        assert result["trick_room_active"] is True


class TestGetMovePriorityInfo:
    """Tests for get_move_priority_info."""

    async def test_fake_out_priority(self, tools):
        """Test Fake Out has +3 priority."""
        fn = tools["get_move_priority_info"].fn
        result = await fn(move_name="fake-out")
        assert result["priority"] == 3

    async def test_protect_priority(self, tools):
        """Test Protect has +4 priority."""
        fn = tools["get_move_priority_info"].fn
        result = await fn(move_name="protect")
        assert result["priority"] == 4

    async def test_normal_move_priority(self, tools):
        """Test normal move has 0 priority."""
        fn = tools["get_move_priority_info"].fn
        result = await fn(move_name="moonblast")
        assert result["priority"] == 0


class TestListTeamPriorityMoves:
    """Tests for list_team_priority_moves."""

    async def test_empty_team(self, tools):
        """Test with no team."""
        fn = tools["list_team_priority_moves"].fn
        result = await fn()
        assert result["priority_moves"] == {}

    async def test_team_with_priority(self, tools, mock_team_manager):
        """Test team that has priority moves."""
        team = MagicMock()
        slot1 = MagicMock()
        slot1.pokemon.name = "incineroar"
        slot1.pokemon.moves = ["fake-out", "flare-blitz", "knock-off", "parting-shot"]
        team.slots = [slot1]
        mock_team_manager.get_current_team.return_value = team

        fn = tools["list_team_priority_moves"].fn
        result = await fn()
        assert result["total_count"] >= 1


class TestCheckFakeOutInteraction:
    """Tests for check_fake_out_interaction."""

    async def test_faster_fake_out(self, tools):
        """Test faster Fake Out user wins."""
        fn = tools["check_fake_out_interaction"].fn
        result = await fn(
            your_speed=100,
            opponent_pokemon="incineroar",
            opponent_speed=80
        )
        assert "faster" in str(result).lower() or "first" in str(result).lower()


class TestListPriorityBracket:
    """Tests for list_priority_bracket."""

    async def test_bracket_3(self, tools):
        """Test priority +3 bracket has Fake Out."""
        fn = tools["list_priority_bracket"].fn
        result = await fn(bracket=3)
        assert "Fake Out" in result["moves"]

    async def test_bracket_display(self, tools):
        """Test bracket display formatting."""
        fn = tools["list_priority_bracket"].fn
        result = await fn(bracket=2)
        assert result["bracket_display"] == "+2"


class TestGetPriorityOverview:
    """Tests for get_priority_overview."""

    async def test_returns_all_brackets(self, tools):
        """Test that overview includes all brackets."""
        fn = tools["get_priority_overview"].fn
        result = await fn()
        assert "brackets" in result
        assert "notes" in result
        assert len(result["notes"]) > 0


class TestFindPriorityThreats:
    """Tests for find_priority_threats."""

    async def test_returns_threats(self, tools):
        """Test that it returns priority threats."""
        fn = tools["find_priority_threats"].fn
        result = await fn()
        assert "threats" in result
        assert "fake_out_users" in result["threats"]
        assert "prankster_users" in result["threats"]


class TestCheckPranksterInteraction:
    """Tests for check_prankster_interaction."""

    async def test_prankster_vs_dark(self, tools):
        """Test Prankster is blocked by Dark type."""
        fn = tools["check_prankster_interaction"].fn
        result = await fn(
            target_types=["Dark"],
            move_name="thunder-wave",
            user_ability="Prankster"
        )
        assert result["move_blocked"] is True

    async def test_prankster_vs_normal(self, tools):
        """Test Prankster works on non-Dark types."""
        fn = tools["check_prankster_interaction"].fn
        result = await fn(
            target_types=["Fairy"],
            move_name="thunder-wave",
            user_ability="Prankster"
        )
        assert result["move_blocked"] is False
        assert result["priority_boosted"] is True

    async def test_non_prankster(self, tools):
        """Test non-Prankster ability."""
        fn = tools["check_prankster_interaction"].fn
        result = await fn(
            target_types=["Dark"],
            move_name="thunder-wave",
            user_ability="Levitate"
        )
        assert result["ability_is_prankster"] is False
