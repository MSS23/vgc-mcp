"""'HP/Atk/Def/SpA/SpD/Spe' slash strings are accepted wherever a spread is passed."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp.tools.workflow_tools import register_workflow_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

BASES = {
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "amoonguss": BaseStats(hp=114, attack=85, defense=70, special_attack=85, special_defense=80, speed=30),
}
MOVES = {
    "flare-blitz": Move(name="flare-blitz", type="fire", category=MoveCategory.PHYSICAL, power=120),
    "knock-off": Move(name="knock-off", type="dark", category=MoveCategory.PHYSICAL, power=65),
    "heat-wave": Move(name="heat-wave", type="fire", category=MoveCategory.SPECIAL, power=95),
}


@pytest.fixture(autouse=True)
def mainline():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_h")
    try:
        yield
    finally:
        cfg.clear_session_override()


@pytest.fixture
def tools():
    api = AsyncMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n: BASES[n.lower()])
    api.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    api.get_pokemon_abilities = AsyncMock(return_value=["blaze"])
    api.get_move = AsyncMock(side_effect=lambda name, user_name=None: MOVES[name])
    mcp = FastMCP("test")
    register_spread_tools(mcp, api)
    register_workflow_tools(mcp, api, None, AsyncMock(), AsyncMock())
    return {t.name: t.fn for t in mcp._tool_manager._tools.values()}


async def test_check_spread_efficiency_slash_matches_ints(tools):
    ints = await tools["check_spread_efficiency"](pokemon_name="incineroar", nature="careful", hp_evs=252, def_evs=4, spd_evs=252)
    slash = await tools["check_spread_efficiency"](pokemon_name="incineroar", nature="careful", spread="252/0/4/0/252/0")
    assert slash == ints


async def test_suggest_nature_optimization_accepts_slash_alone(tools):
    ints = await tools["suggest_nature_optimization"](
        pokemon_name="incineroar", current_nature="serious",
        hp_evs=4, atk_evs=252, def_evs=0, spa_evs=0, spd_evs=0, spe_evs=252,
    )
    slash = await tools["suggest_nature_optimization"](
        pokemon_name="incineroar", current_nature="serious", spread="4/252/0/0/0/252",
    )
    assert slash == ints


async def test_attacker_slash_uses_offensive_stat(tools):
    common = dict(pokemon_name="amoonguss", nature="bold", survive_pokemon="incineroar",
                  survive_move="flare-blitz", survive_pokemon_ability="blaze", survive_pokemon_item="life-orb")
    as_int = await tools["design_spread_with_benchmarks"](survive_pokemon_evs=196, **common)
    as_slash = await tools["design_spread_with_benchmarks"](survive_pokemon_evs="0/196/0/252/0/60", **common)
    assert as_slash["benchmarks"]["survival"] == as_int["benchmarks"]["survival"]
    assert as_slash["showdown_paste"] == as_int["showdown_paste"]


async def test_threat_evs_slash_matches_int(tools):
    def threats(evs):
        return [{"attacker": "incineroar", "move": m, "nature": "adamant", "evs": evs, "item": "life-orb", "ability": "blaze"}
                for m in MOVES]
    a = await tools["optimize_multi_survival_spread"](pokemon_name="amoonguss", threats=threats(252), nature="calm")
    b = await tools["optimize_multi_survival_spread"](pokemon_name="amoonguss", threats=threats("4/252/0/252/0/0"), nature="calm")
    assert a["optimal_spread"] == b["optimal_spread"]


@pytest.mark.parametrize("tool,param", [
    ("calc_damage_vs_smogon_sets", {"my_pokemon": "amoonguss", "my_nature": "bold", "my_spread": "999/0/0/0/0/0"}),
    ("optimize_spread", {"pokemon_name": "amoonguss", "current_spread": "252/0/252"}),
    ("check_spread_efficiency", {"pokemon_name": "amoonguss", "nature": "bold", "spread": "253/0/0/0/0/0"}),
])
async def test_bad_slash_string_is_invalid_parameter(tools, tool, param):
    result = await tools[tool](**param)
    assert result["error"] == "invalid_parameter"
