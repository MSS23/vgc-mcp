"""Champions (Reg MA) regression tests for the team & build-state tools.

These exercise the ACTUAL @mcp.tool handlers in a champions session and assert
SP-scale behavior (32/stat, 66 total) instead of EV-scale (252/508):

- team_tools.add_to_team / swap_team_pokemon build a champions PokemonBuild so
  Flutter Mane with 32 Speed SP reaches Speed 205 (not 174).
- build_tools.create_build / modify_build / get_build_state store and surface
  Stat Points, and round-trip through BuildStateManager so calculate_all_stats
  dispatches to the SP formula.
"""

import pytest
from unittest.mock import AsyncMock

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.team_tools import register_team_tools
from vgc_mcp.tools.build_tools import register_build_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.team.analysis import TeamAnalyzer
from vgc_mcp_core.state.build_manager import BuildStateManager
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.rules.regulation_loader import (
    get_regulation_config,
    reset_regulation_config,
)


# Flutter Mane base stats — base Speed 135.
FLUTTER_MANE_BASE = BaseStats(
    hp=55, attack=55, defense=55,
    special_attack=135, special_defense=135, speed=135,
)


@pytest.fixture
def champions_session():
    """Force the session into Champions (Reg MA) and reset afterward."""
    reset_regulation_config()
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_ma_champs", by_user=True)
    assert cfg.get_format_system() == "champions"
    yield cfg
    reset_regulation_config()


@pytest.fixture
def mainline_session():
    reset_regulation_config()
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_f", by_user=True)
    assert cfg.get_format_system() == "mainline"
    yield cfg
    reset_regulation_config()


@pytest.fixture
def mock_pokeapi():
    client = AsyncMock()
    client.get_base_stats = AsyncMock(return_value=FLUTTER_MANE_BASE)
    client.get_pokemon_types = AsyncMock(return_value=["Ghost", "Fairy"])
    client.get_pokemon_abilities = AsyncMock(return_value=["Protosynthesis"])
    return client


@pytest.fixture
def team_tools(mock_pokeapi):
    mcp = FastMCP("test")
    team_manager = TeamManager()
    analyzer = TeamAnalyzer()
    register_team_tools(mcp, mock_pokeapi, team_manager, analyzer)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools, team_manager


@pytest.fixture
def build_tools(mock_pokeapi):
    mcp = FastMCP("test")
    build_manager = BuildStateManager()
    register_build_tools(mcp, build_manager, mock_pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}
    return tools, build_manager


# --------------------------- team_tools -----------------------------------

class TestAddToTeamChampions:
    async def test_32_speed_sp_yields_205(self, champions_session, team_tools):
        tools, team_manager = team_tools
        fn = tools["add_to_team"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            nature="timid",
            spe_evs=32,  # interpreted as 32 Stat Points in a champions session
        )
        assert result["success"] is True

        stored = team_manager.team.slots[0].pokemon
        assert stored.format_system == "champions"
        assert stored.sps is not None
        assert stored.sps.speed == 32
        # The whole point: SP formula gives 205, NOT the EV-scale 174.
        stats = calculate_all_stats(stored)
        assert stats["speed"] == 205

    async def test_sp_total_cap_enforced(self, champions_session, team_tools):
        tools, _ = team_tools
        fn = tools["add_to_team"].fn
        # 32 + 32 + 32 = 96 > 66 total budget.
        result = await fn(
            pokemon_name="flutter-mane",
            hp_evs=32, spa_evs=32, spe_evs=32,
        )
        assert result["success"] is False
        assert "error" in result

    async def test_per_stat_cap_enforced(self, champions_session, team_tools):
        tools, _ = team_tools
        fn = tools["add_to_team"].fn
        result = await fn(pokemon_name="flutter-mane", spe_evs=40)  # > 32/stat
        assert result["success"] is False
        assert "error" in result

    async def test_swap_uses_sp(self, champions_session, team_tools):
        tools, team_manager = team_tools
        add = tools["add_to_team"].fn
        await add(pokemon_name="flutter-mane", nature="timid", spe_evs=4)

        swap = tools["swap_team_pokemon"].fn
        result = await swap(
            slot=1, pokemon_name="flutter-mane", nature="timid", spe_evs=32,
        )
        assert result["success"] is True
        stored = team_manager.team.slots[0].pokemon
        assert stored.format_system == "champions"
        assert stored.sps.speed == 32
        assert calculate_all_stats(stored)["speed"] == 205


class TestAddToTeamMainlineUnchanged:
    async def test_32_speed_evs_yields_174(self, mainline_session, team_tools):
        tools, team_manager = team_tools
        fn = tools["add_to_team"].fn
        result = await fn(
            pokemon_name="flutter-mane", nature="timid", spe_evs=32,
        )
        assert result["success"] is True
        stored = team_manager.team.slots[0].pokemon
        assert stored.format_system == "mainline"
        assert stored.sps is None
        assert stored.evs.speed == 32
        # Mainline path byte-for-byte: 32 EVs -> 174 Speed.
        assert calculate_all_stats(stored)["speed"] == 174

    async def test_508_cap_still_enforced(self, mainline_session, team_tools):
        tools, _ = team_tools
        fn = tools["add_to_team"].fn
        result = await fn(
            pokemon_name="flutter-mane",
            hp_evs=252, spa_evs=252, spe_evs=252,
        )
        assert result["success"] is False
        assert "error" in result


# --------------------------- build_tools ----------------------------------

class TestCreateBuildChampions:
    async def test_create_stores_sps_and_round_trips_to_205(
        self, champions_session, build_tools
    ):
        tools, build_manager = build_tools
        create = tools["create_build"].fn
        result = await create(
            pokemon_name="flutter-mane", nature="Timid", spe_evs=32,
        )
        assert result["success"] is True
        assert result["build"]["format_system"] == "champions"
        assert result["build"]["sps"]["speed"] == 32
        assert "evs" not in result["build"]

        # Round-trip through the state manager: reconstructed build must
        # dispatch to the SP formula -> Speed 205.
        build_id = result["build_id"]
        stored = build_manager.get_build(build_id)
        assert stored["format_system"] == "champions"
        assert stored["sps"]["speed"] == 32

        rebuilt = build_manager.to_pokemon_build(build_id)
        assert rebuilt.format_system == "champions"
        assert calculate_all_stats(rebuilt)["speed"] == 205

    async def test_create_rejects_over_budget(self, champions_session, build_tools):
        tools, _ = build_tools
        create = tools["create_build"].fn
        result = await create(
            pokemon_name="flutter-mane",
            hp_evs=32, spa_evs=32, spe_evs=32,  # 96 > 66
        )
        assert result["success"] is False
        assert "error" in result

    async def test_get_build_state_surfaces_sps(self, champions_session, build_tools):
        tools, _ = build_tools
        await tools["create_build"].fn(
            pokemon_name="flutter-mane", nature="Timid", spe_evs=32,
        )
        result = await tools["get_build_state"].fn(pokemon_name="flutter-mane")
        assert result["success"] is True
        assert result["build"]["format_system"] == "champions"
        assert result["build"]["sps"]["speed"] == 32
        assert "evs" not in result["build"]

    async def test_modify_build_edits_sps(self, champions_session, build_tools):
        tools, build_manager = build_tools
        await tools["create_build"].fn(
            pokemon_name="flutter-mane", nature="Timid", spe_evs=4,
        )
        modify = tools["modify_build"].fn
        result = await modify(pokemon_name="flutter-mane", spe_evs=32)
        assert result["success"] is True
        assert "sps" in result.get("changes", [])
        assert result["build"]["format_system"] == "champions"
        assert result["build"]["sps"]["speed"] == 32

        rebuilt = build_manager.to_pokemon_build(result["build_id"])
        assert calculate_all_stats(rebuilt)["speed"] == 205

    async def test_modify_build_rejects_over_budget(
        self, champions_session, build_tools
    ):
        tools, _ = build_tools
        await tools["create_build"].fn(
            pokemon_name="flutter-mane", nature="Timid", hp_evs=32, spa_evs=32,
        )
        # Existing 64 SP; adding 32 Speed -> 96 > 66.
        result = await tools["modify_build"].fn(
            pokemon_name="flutter-mane", spe_evs=32,
        )
        assert result["success"] is False
        assert "error" in result


class TestCreateBuildMainlineUnchanged:
    async def test_create_stores_evs(self, mainline_session, build_tools):
        tools, build_manager = build_tools
        result = await tools["create_build"].fn(
            pokemon_name="flutter-mane", nature="Timid", spe_evs=32,
        )
        assert result["success"] is True
        assert "evs" in result["build"]
        assert "sps" not in result["build"]
        assert result["build"].get("format_system", "mainline") == "mainline"

        rebuilt = build_manager.to_pokemon_build(result["build_id"])
        assert rebuilt.format_system == "mainline"
        assert calculate_all_stats(rebuilt)["speed"] == 174
