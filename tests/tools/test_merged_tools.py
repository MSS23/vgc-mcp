"""Deprecated aliases delegate to their canonical tools; slash-string allocations work."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.bulk_calc_tools import register_bulk_calc_tools
from vgc_mcp.tools.damage_tools import register_damage_tools
from vgc_mcp.tools.meta_threat_tools import register_meta_threat_tools
from vgc_mcp.tools.speed_analysis_tools import register_speed_analysis_tools
from vgc_mcp.tools.speed_probability_tools import register_speed_probability_tools
from vgc_mcp.tools.speed_tools import register_speed_tools
from vgc_mcp.tools.speed_viz_tools import register_speed_viz_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature, PokemonBuild
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

_BASE = {
    "garchomp": BaseStats(hp=108, attack=130, defense=95, special_attack=80, special_defense=85, speed=102),
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
    "landorus": BaseStats(hp=89, attack=125, defense=90, special_attack=115, special_defense=80, speed=101),
}
_TYPES = {"garchomp": ["dragon", "ground"], "flutter-mane": ["ghost", "fairy"], "landorus": ["ground", "flying"]}
_MOVES = {
    "moonblast": Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL, power=95, accuracy=100),
    "earthquake": Move(name="earthquake", type="ground", category=MoveCategory.PHYSICAL, power=100, accuracy=100),
}

ALIASES = {
    "outspeed_probability": "analyze_outspeed_probability",
    "outspeed_probability_stored": "analyze_outspeed_probability",
    "get_meta_speed_tiers": "get_speed_tiers",
    "visualize_team_speed_tiers": "visualize_speed_tiers",
    "find_survival_evs_meta": "find_survival_evs",
}


@pytest.fixture(autouse=True)
def mainline_session():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_h")
    yield
    cfg.clear_session_override()


@pytest.fixture
def pokeapi():
    api = MagicMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n, *a, **k: _BASE[n])
    api.get_pokemon_types = AsyncMock(side_effect=lambda n, *a, **k: _TYPES[n])
    api.get_pokemon_abilities = AsyncMock(return_value=["Rough Skin"])
    api.get_move = AsyncMock(side_effect=lambda n, *a, **k: _MOVES[n])
    return api


@pytest.fixture
def smogon():
    s = MagicMock()
    s.current_regulation_from_data = None
    s.get_pokemon_usage = AsyncMock(return_value=None)
    s.get_usage_stats = AsyncMock(return_value={"_meta": {}, "data": {}})
    s.get_speed_distribution = AsyncMock(return_value={
        "base_speed": 101,
        "distribution": [{"speed": 168, "usage": 40}, {"speed": 153, "usage": 35}, {"speed": 101, "usage": 25}],
    })
    return s


@pytest.fixture
def tools(pokeapi, smogon):
    team_manager = MagicMock()
    team_manager.get_pokemon_context = MagicMock(return_value=PokemonBuild(
        name="garchomp", base_stats=_BASE["garchomp"], types=_TYPES["garchomp"],
        nature=Nature.JOLLY, evs=EVSpread(speed=252),
    ))
    mcp = FastMCP("test")
    register_damage_tools(mcp, pokeapi, smogon)
    register_meta_threat_tools(mcp, smogon, pokeapi, team_manager)
    register_speed_tools(mcp, pokeapi, smogon)
    register_speed_probability_tools(mcp, smogon, pokeapi, team_manager)
    register_speed_analysis_tools(mcp, pokeapi, team_manager, smogon)
    register_speed_viz_tools(mcp, pokeapi, smogon)
    register_bulk_calc_tools(mcp, pokeapi, smogon)
    return {name: t.fn for name, t in mcp._tool_manager._tools.items()}


def test_alias_docstrings_point_at_canonical(tools):
    for alias, canonical in ALIASES.items():
        first = tools[alias].__doc__.strip().splitlines()[0]
        assert first == f"Deprecated alias of `{canonical}`; will be removed in the next release."


async def test_outspeed_probability_alias(tools):
    canon = await tools["analyze_outspeed_probability"](
        pokemon_name="garchomp", target_pokemon="landorus", nature="jolly", speed_evs=252)
    alias = await tools["outspeed_probability"](
        your_pokemon="garchomp", your_speed_evs=252, your_nature="jolly", target_pokemon="landorus")
    assert alias["your_speed"] == canon["your_speed"] == 169
    assert alias["outspeed_probability"] == canon["outspeed_percent"]
    assert alias["speed_tie_probability"] == canon["tie_percent"]


async def test_outspeed_probability_stored_alias(tools):
    canon = await tools["analyze_outspeed_probability"](
        pokemon_name="garchomp", target_pokemon="landorus", speed_stat=169)
    alias = await tools["outspeed_probability_stored"](target_pokemon="landorus")
    assert alias["your_speed"] == 169
    assert alias["outspeed_probability"] == canon["outspeed_percent"]


async def test_get_meta_speed_tiers_alias(tools, smogon):
    smogon.get_usage_stats.side_effect = RuntimeError("offline")  # use the theoretical meta tiers
    canon = await tools["get_speed_tiers"](investment="meta", min_base_speed=0, max_base_speed=999)
    alias = await tools["get_meta_speed_tiers"]()
    assert alias["speed_tiers"] and alias["speed_tiers"] == canon["speed_tiers"]


async def test_visualize_team_speed_tiers_alias(tools):
    team = [{"name": "garchomp", "nature": "jolly", "evs": {"speed": 252}}]
    canon = await tools["visualize_speed_tiers"](pokemon_speeds=team, include_tailwind=True)
    alias = await tools["visualize_team_speed_tiers"](team_pokemon=team)
    assert alias["team_speeds"][0]["speed"] == 169
    assert alias["markdown_summary"] == canon["visualization"]


async def test_find_survival_evs_meta_alias(tools):
    canon = await tools["find_survival_evs"](
        attacker_name="flutter-mane", defender_name="garchomp", move_name="moonblast",
        defender_nature="careful", target_survival_chance=100, apply_defender_intimidate=False)
    alias = await tools["find_survival_evs_meta"](
        pokemon_name="garchomp", nature="careful", threat_pokemon="flutter-mane", threat_move="moonblast")
    assert alias["hp_evs_needed"] == canon["hp_evs_needed"]
    assert alias["minimum_evs"]["spd_evs"] == canon["def_evs_needed"]
    assert "EVs:" in alias["showdown_paste"]


async def test_find_survival_evs_slash_string(tools):
    common = dict(attacker_name="flutter-mane", defender_name="garchomp", move_name="moonblast",
                  attacker_nature="modest", use_smogon_spreads=False)
    as_int = await tools["find_survival_evs"](attacker_evs=252, **common)
    as_str = await tools["find_survival_evs"](attacker_evs="4/0/0/252/0/252", **common)
    assert as_str["hp_evs_needed"] == as_int["hp_evs_needed"]
    assert as_str["def_evs_needed"] == as_int["def_evs_needed"]
    assert as_str["attacker_ev_spread"] == "4 HP / 252 SpA / 252 Spe"
    bad = await tools["find_survival_evs"](attacker_evs="252/252", **common)
    assert bad["error"] == "invalid_parameter"


async def test_find_bulk_to_survive_hits_slash_string(tools):
    common = dict(attacker_name="landorus", defender_name="garchomp", move_name="earthquake",
                  apply_defender_intimidate=False, use_smogon_spreads=False)
    as_int = await tools["find_bulk_to_survive_hits"](attacker_evs=252, **common)
    as_str = await tools["find_bulk_to_survive_hits"](attacker_evs="0/252/0/0/4/252", **common)
    assert as_str["minimum_spread"] == as_int["minimum_spread"]


async def test_speed_tools_take_slash_strings(tools):
    as_int = await tools["compare_speed"](
        pokemon1_name="garchomp", pokemon2_name="landorus", pokemon1_nature="jolly", pokemon1_speed_evs=252)
    as_str = await tools["compare_speed"](
        pokemon1_name="garchomp", pokemon2_name="landorus", pokemon1_nature="jolly",
        pokemon1_speed_evs="4/252/0/0/0/252")
    assert as_str["pokemon1"] == as_int["pokemon1"]
    prob = await tools["analyze_outspeed_probability"](
        pokemon_name="garchomp", target_pokemon="landorus", nature="jolly", speed_evs="4/252/0/0/0/252")
    assert prob["your_speed"] == 169
