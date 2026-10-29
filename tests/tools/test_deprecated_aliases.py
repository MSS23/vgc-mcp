"""Deprecated alias tools delegate to their canonical tool."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

BASES = {
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "amoonguss": BaseStats(hp=114, attack=85, defense=70, special_attack=85, special_defense=80, speed=30),
}


@pytest.fixture
def mainline():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_h")
    try:
        yield
    finally:
        cfg.clear_session_override()


@pytest.fixture
def pokeapi():
    client = AsyncMock()
    client.get_base_stats = AsyncMock(side_effect=lambda n: BASES[n.lower()])
    client.get_pokemon_types = AsyncMock(return_value=["Fire", "Dark"])
    return client


@pytest.fixture
def spread_tools(pokeapi):
    mcp = FastMCP("test")
    register_spread_tools(mcp, pokeapi)
    return {t.name: t for t in mcp._tool_manager._tools.values()}


def test_alias_docstrings_lead_with_deprecation(spread_tools):
    desc = spread_tools["optimize_bulk_math"].description
    assert desc.startswith("Deprecated alias of `optimize_bulk`; will be removed in the next release.")


async def test_optimize_bulk_math_delegates_to_optimize_bulk(spread_tools, mainline):
    args = {"pokemon_name": "amoonguss", "nature": "bold", "total_bulk_evs": 508, "item": "sitrus-berry"}
    alias = await spread_tools["optimize_bulk_math"].fn(defense_weight=0.7, **args)
    canonical = await spread_tools["optimize_bulk"].fn(defense_bias=0.7, include_analysis=True, **args)

    assert alias["optimal_spread"] == canonical["optimal_spread"]
    assert alias["showdown_paste"] == canonical["showdown_paste"]
    assert alias["bulk_scores"] == canonical["bulk_scores"]
    assert alias["defense_weight"] == 0.7
    # Legacy keys of the alias are still present.
    for key in ("final_stats", "efficiency_score", "explanation", "comparison_vs_naive", "base_stats"):
        assert key in alias


async def test_find_multi_threat_bulk_evs_delegates_to_optimize_multi_survival(pokeapi, mainline):
    from vgc_mcp.tools.multi_threat_tools import register_multi_threat_tools
    from vgc_mcp_core.models.move import Move, MoveCategory

    moves = {
        "flare-blitz": Move(name="flare-blitz", type="fire", category=MoveCategory.PHYSICAL, power=120),
        "knock-off": Move(name="knock-off", type="dark", category=MoveCategory.PHYSICAL, power=65),
        "heat-wave": Move(name="heat-wave", type="fire", category=MoveCategory.SPECIAL, power=95),
    }
    pokeapi.get_move = AsyncMock(side_effect=lambda name, user_name=None: moves[name])
    mcp = FastMCP("test")
    register_spread_tools(mcp, pokeapi)
    register_multi_threat_tools(mcp, pokeapi)
    tools = {t.name: t for t in mcp._tool_manager._tools.values()}

    spread = {"nature": "adamant", "evs": {"attack": 252, "special_attack": 252}, "item": "life-orb", "ability": "blaze"}
    legacy = [{"name": "incineroar", "move": m, "spread": spread} for m in moves]
    canonical_threats = [
        {"attacker": "incineroar", "move": m, "nature": "adamant", "evs": 252, "item": "life-orb", "ability": "blaze"}
        for m in moves
    ]
    alias = await tools["find_multi_threat_bulk_evs"].fn(
        pokemon_name="amoonguss", threats=legacy, nature="calm", item="rocky-helmet",
        ability="regenerator", target_survival_chance=93.75,
    )
    canonical = await tools["optimize_multi_survival_spread"].fn(
        pokemon_name="amoonguss", threats=canonical_threats, nature="calm", item="rocky-helmet",
        ability="regenerator", target_survival=93.75,
    )
    assert canonical["success"], canonical
    opt = canonical["optimal_spread"]
    rec = alias["recommended_spread"]
    assert (rec["hp_evs"], rec["def_evs"], rec["spd_evs"]) == (opt["hp_evs"], opt["def_evs"], opt["spd_evs"])
    assert alias["showdown_paste"] == canonical["showdown_paste"]
    assert alias["all_survive"] and "/508" in alias["markdown_summary"]


async def test_optimize_bulk_analysis_is_opt_in(spread_tools, mainline):
    plain = await spread_tools["optimize_bulk"].fn(pokemon_name="incineroar", nature="careful")
    assert "bulk_scores" not in plain
    spread = plain["optimal_spread"]
    assert spread["hp_evs"] + spread["def_evs"] + spread["spd_evs"] <= 252
