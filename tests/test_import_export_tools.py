"""Tests for import/export tools."""

import pytest
from unittest.mock import AsyncMock, MagicMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.import_export_tools import register_import_export_tools
from vgc_mcp_core.models.pokemon import BaseStats, PokemonBuild, Nature, EVSpread, IVSpread
from vgc_mcp_core.team.manager import TeamManager


SINGLE_POKEMON_PASTE = """Urshifu-Rapid-Strike @ Choice Scarf
Ability: Unseen Fist
Level: 50
Tera Type: Water
EVs: 4 HP / 252 Atk / 252 Spe
Jolly Nature
- Surging Strikes
- Close Combat
- U-turn
- Aqua Jet
"""

TEAM_PASTE = """Flutter Mane @ Choice Specs
Ability: Protosynthesis
Level: 50
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
IVs: 0 Atk
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Protect

Incineroar @ Safety Goggles
Ability: Intimidate
Level: 50
EVs: 252 HP / 4 Atk / 116 Def / 4 SpD / 132 Spe
Careful Nature
- Fake Out
- Knock Off
- Flare Blitz
- Parting Shot
"""


@pytest.fixture
def mock_pokeapi():
    """Create a mock PokeAPI client."""
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=BaseStats(
        hp=100, attack=130, defense=100,
        special_attack=63, special_defense=60, speed=97
    ))
    client.get_pokemon_types = AsyncMock(return_value=["Water", "Fighting"])
    return client


@pytest.fixture
def real_team_manager():
    """Create a real TeamManager for integration-style tests."""
    return TeamManager()


@pytest.fixture
def tools(mock_pokeapi, real_team_manager):
    """Register tools and return functions."""
    mcp = FastMCP("test")
    register_import_export_tools(mcp, mock_pokeapi, real_team_manager)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


class TestImportShowdownPokemon:
    """Tests for import_showdown_pokemon."""

    async def test_import_single_pokemon(self, tools):
        """Test importing a single Pokemon."""
        fn = tools["import_showdown_pokemon"].fn
        result = await fn(paste=SINGLE_POKEMON_PASTE, add_to_team=False)
        assert result["success"] is True
        assert "parsed" in result
        assert result["parsed"]["moves"] == ["Surging Strikes", "Close Combat", "U-turn", "Aqua Jet"]

    async def test_import_and_add_to_team(self, tools):
        """Test importing and adding to team."""
        fn = tools["import_showdown_pokemon"].fn
        result = await fn(paste=SINGLE_POKEMON_PASTE, add_to_team=True)
        assert result["success"] is True
        assert "team" in result
        assert result["team"]["added"] is True

    async def test_import_invalid_paste(self, tools, mock_pokeapi):
        """Test importing invalid paste that fails API lookup."""
        mock_pokeapi.get_base_stats.side_effect = Exception("Pokemon not found")
        fn = tools["import_showdown_pokemon"].fn
        result = await fn(paste="not a valid pokemon paste", add_to_team=True)
        # Parser is lenient, but API will fail for invalid species
        assert result["success"] is False or "error" in str(result)

    async def test_parsed_fields(self, tools):
        """Test that parsed data has expected fields."""
        fn = tools["import_showdown_pokemon"].fn
        result = await fn(paste=SINGLE_POKEMON_PASTE, add_to_team=False)
        parsed = result["parsed"]
        assert "species" in parsed
        assert "item" in parsed
        assert "ability" in parsed
        assert "nature" in parsed
        assert "evs" in parsed
        assert "moves" in parsed


class TestImportShowdownTeam:
    """Tests for import_showdown_team."""

    async def test_import_team(self, tools):
        """Test importing a full team."""
        fn = tools["import_showdown_team"].fn
        result = await fn(paste=TEAM_PASTE)
        assert result["success"] is True
        assert result["imported_count"] == 2

    async def test_import_empty_paste(self, tools):
        """Test importing empty paste."""
        fn = tools["import_showdown_team"].fn
        result = await fn(paste="")
        assert result["success"] is False

    async def test_clear_existing(self, tools):
        """Test clearing existing team before import."""
        fn = tools["import_showdown_team"].fn
        # Import twice, second time with clear
        await fn(paste=TEAM_PASTE)
        result = await fn(paste=TEAM_PASTE, clear_existing=True)
        assert result["success"] is True


class TestExportTeamToPaste:
    """Tests for export_team_to_paste."""

    async def test_export_empty_team(self, tools):
        """Test exporting empty team returns error."""
        fn = tools["export_team_to_paste"].fn
        result = await fn()
        assert result["success"] is False
        assert "empty" in result["error"]

    async def test_export_after_import(self, tools):
        """Test exporting after importing."""
        import_fn = tools["import_showdown_team"].fn
        export_fn = tools["export_team_to_paste"].fn

        await import_fn(paste=TEAM_PASTE)
        result = await export_fn()
        assert result["success"] is True
        assert "paste" in result


class TestExportPokemonToPaste:
    """Tests for export_pokemon_to_paste."""

    async def test_export_invalid_slot(self, tools):
        """Test exporting from invalid slot."""
        fn = tools["export_pokemon_to_paste"].fn
        result = await fn(slot=1)
        assert result["success"] is False

    async def test_export_after_import(self, tools):
        """Test exporting a specific Pokemon after import."""
        import_fn = tools["import_showdown_team"].fn
        export_fn = tools["export_pokemon_to_paste"].fn

        await import_fn(paste=TEAM_PASTE)
        result = await export_fn(slot=1)
        assert result["success"] is True
        assert "paste" in result
