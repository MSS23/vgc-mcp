"""Tests for high-level workflow coordinator tools."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.workflow_tools import register_workflow_tools


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    return AsyncMock()


@pytest.fixture
def mock_smogon():
    """Create a mock Smogon client."""
    return AsyncMock()


@pytest.fixture
def mock_team_manager():
    """Create a mock team manager."""
    manager = MagicMock()
    manager.size = 0
    manager.team = MagicMock()
    return manager


@pytest.fixture
def mock_analyzer():
    """Create a mock analyzer."""
    return MagicMock()


@pytest.fixture
def tools(mock_pokeapi, mock_smogon, mock_team_manager, mock_analyzer):
    """Register workflow tools and return functions."""
    mcp = FastMCP("test")
    register_workflow_tools(mcp, mock_pokeapi, mock_smogon, mock_team_manager, mock_analyzer)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestFullTeamCheck:
    """Tests for full_team_check."""

    async def test_empty_team_no_paste(self, tools):
        """Test with no team and no paste."""
        fn = tools["full_team_check"].fn
        result = await fn()
        assert "error" in result or result.get("success") is False

    async def test_invalid_paste(self, tools):
        """Test with an empty paste."""
        fn = tools["full_team_check"].fn
        result = await fn(paste="")
        assert "error" in result or result.get("success") is False


FLUTTER_MANE = {
    "base_stats": {"hp": 55, "attack": 55, "defense": 55,
                   "special_attack": 135, "special_defense": 135, "speed": 135},
    "types": ["ghost", "fairy"],
}
INCINEROAR = {
    "base_stats": {"hp": 95, "attack": 115, "defense": 90,
                   "special_attack": 80, "special_defense": 90, "speed": 60},
    "types": ["fire", "dark"],
}


def _moonblast():
    from vgc_mcp_core.models.move import Move, MoveCategory
    return Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL,
                power=95, accuracy=100)


class TestQuickDamageCheck:
    """Tests for quick_damage_check — the one-call damage workflow."""

    async def test_happy_path_runs_real_damage_calc(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(
            side_effect=lambda name: FLUTTER_MANE if "flutter" in name else INCINEROAR)
        mock_pokeapi.get_move = AsyncMock(return_value=_moonblast())
        mock_pokeapi.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])

        fn = tools["quick_damage_check"].fn
        result = await fn(attacker="flutter-mane", defender="incineroar", move="moonblast")
        assert result.get("success", True) is not False
        # 252 SpA Modest Moonblast into 0/0 Incineroar does real damage
        text = str(result)
        assert "%" in text or "percent" in text.lower()

    async def test_unknown_attacker_is_error(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(return_value=None)
        mock_pokeapi.get_move = AsyncMock(return_value=_moonblast())
        fn = tools["quick_damage_check"].fn
        result = await fn(attacker="not-a-mon", defender="incineroar", move="moonblast")
        assert result["success"] is False

    async def test_unknown_move_is_error(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(
            side_effect=lambda name: FLUTTER_MANE if "flutter" in name else INCINEROAR)
        mock_pokeapi.get_move = AsyncMock(return_value=None)
        fn = tools["quick_damage_check"].fn
        result = await fn(attacker="flutter-mane", defender="incineroar", move="fake-move")
        assert result["success"] is False


class TestAnalyzeSpeedMatchup:
    """Tests for analyze_speed_matchup."""

    async def test_faster_pokemon_is_identified(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(
            side_effect=lambda name: FLUTTER_MANE if "flutter" in name else INCINEROAR)
        fn = tools["analyze_speed_matchup"].fn
        result = await fn(my_pokemon="flutter-mane", opponent_pokemon="incineroar")
        assert result.get("success", True) is not False
        # Base 135 vs 60, both jolly 252 — we must be flagged faster
        assert "faster" in str(result).lower()

    async def test_unknown_pokemon_is_error(self, tools, mock_pokeapi):
        mock_pokeapi.get_pokemon = AsyncMock(return_value=None)
        fn = tools["analyze_speed_matchup"].fn
        result = await fn(my_pokemon="ghost-mon", opponent_pokemon="incineroar")
        assert result["success"] is False


class TestCheckTeamVsThreat:
    async def test_empty_team_is_error(self, tools, mock_team_manager):
        mock_team_manager.size = 0
        fn = tools["check_team_vs_threat"].fn
        result = await fn(threat_pokemon="flutter-mane")
        assert result["success"] is False
        assert "team" in result["message"].lower()
