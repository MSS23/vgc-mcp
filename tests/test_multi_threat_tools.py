"""Tests for multi-threat bulk calculation tools."""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.multi_threat_tools import register_multi_threat_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()

    async def _get_base_stats(name):
        stats = {
            "ogerpon-hearthflame": BaseStats(hp=80, attack=120, defense=84, special_attack=60, special_defense=96, speed=110),
            "urshifu-rapid-strike": BaseStats(hp=100, attack=130, defense=100, special_attack=63, special_defense=60, speed=97),
            "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
        }
        return stats.get(name.lower(), BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80))

    async def _get_types(name):
        types_map = {
            "ogerpon-hearthflame": ["Grass", "Fire"],
            "urshifu-rapid-strike": ["Fighting", "Water"],
            "flutter-mane": ["Ghost", "Fairy"],
        }
        return types_map.get(name.lower(), ["Normal"])

    async def _get_abilities(name):
        return ["Intimidate"]

    async def _get_move(name):
        moves = {
            "surging-strikes": Move(name="surging-strikes", power=25, type="water", category=MoveCategory.PHYSICAL, accuracy=100, pp=5, priority=0),
            "moonblast": Move(name="moonblast", power=95, type="fairy", category=MoveCategory.SPECIAL, accuracy=100, pp=15, priority=0),
        }
        return moves.get(name.lower())

    client.get_base_stats = AsyncMock(side_effect=_get_base_stats)
    client.get_pokemon_types = AsyncMock(side_effect=_get_types)
    client.get_pokemon_abilities = AsyncMock(side_effect=_get_abilities)
    client.get_move = AsyncMock(side_effect=_get_move)
    return client


@pytest.fixture
def tools(mock_pokeapi):
    """Register multi-threat tools and return functions."""
    mcp = FastMCP("test")
    register_multi_threat_tools(mcp, mock_pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestFindMultiThreatBulkEvs:
    """Tests for find_multi_threat_bulk_evs."""

    async def test_basic_multi_threat(self, tools):
        """Test basic multi-threat optimization."""
        fn = tools["find_multi_threat_bulk_evs"].fn
        result = await fn(
            pokemon_name="ogerpon-hearthflame",
            threats=[
                {"name": "urshifu-rapid-strike", "move": "surging-strikes"},
                {"name": "flutter-mane", "move": "moonblast"},
            ],
            nature="careful"
        )
        assert "error" not in result or "survival" in str(result).lower()

    async def test_invalid_threat_format(self, tools):
        """Test with invalid threat format."""
        fn = tools["find_multi_threat_bulk_evs"].fn
        result = await fn(
            pokemon_name="ogerpon-hearthflame",
            threats=[{"no_name": True}],
            nature="bold"
        )
        assert "error" in result

    async def test_invalid_nature(self, tools):
        """Test with invalid nature."""
        fn = tools["find_multi_threat_bulk_evs"].fn
        result = await fn(
            pokemon_name="ogerpon-hearthflame",
            threats=[{"name": "urshifu-rapid-strike", "move": "surging-strikes"}],
            nature="notanature"
        )
        assert "error" in result

    async def test_pokemon_not_found(self, tools, mock_pokeapi):
        """Test when Pokemon is not found."""
        mock_pokeapi.get_base_stats = AsyncMock(side_effect=Exception("Not found"))
        fn = tools["find_multi_threat_bulk_evs"].fn
        result = await fn(
            pokemon_name="fakemon",
            threats=[{"name": "urshifu-rapid-strike", "move": "surging-strikes"}],
            nature="bold"
        )
        assert "error" in result

    async def test_empty_threats(self, tools):
        """Test with empty threats list."""
        fn = tools["find_multi_threat_bulk_evs"].fn
        result = await fn(
            pokemon_name="ogerpon-hearthflame",
            threats=[],
            nature="bold"
        )
        assert "error" in result or result.get("threats_analyzed", 0) == 0
