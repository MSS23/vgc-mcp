"""End-to-end regressions for native SP input and complete recommendations."""

from unittest.mock import AsyncMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.speed_tools import register_speed_tools
from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp.tools.stats_tools import register_stats_tools
from vgc_mcp_core.calc.champions_optimization import complete_sp_allocation
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.calc.stats_champions import find_speed_sps
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats, IVSpread, Nature, PokemonBuild, StatPointSpread
from vgc_mcp_core.rules.regulation_loader import get_regulation_config, reset_regulation_config


@pytest.fixture
def tools(monkeypatch):
    reset_regulation_config()
    get_regulation_config().set_session_regulation("reg_ma_champs", by_user=True)
    bases = {
        "farigiraf": BaseStats(hp=120, attack=90, defense=70, special_attack=110, special_defense=70, speed=60),
        "salamence-mega": BaseStats(hp=95, attack=145, defense=130, special_attack=120, special_defense=90, speed=120),
    }
    api = AsyncMock()
    api.get_base_stats.side_effect = lambda name: bases[name]
    api.get_pokemon_types.return_value = ["normal", "psychic"]
    api.get_pokemon_abilities.return_value = ["armor-tail"]
    api.get_move.return_value = Move(name="tackle", type="normal", category=MoveCategory.PHYSICAL, power=40)
    monkeypatch.setattr("vgc_mcp.tools.spread_tools._get_common_spread", AsyncMock(return_value=None))
    mcp = FastMCP("SP regressions")
    register_stats_tools(mcp, api)
    register_speed_tools(mcp, api)
    register_spread_tools(mcp, api)
    yield mcp._tool_manager
    reset_regulation_config()


@pytest.mark.parametrize("investment,speed", [(0, 80), (9, 89), (10, 90), (15, 95), (32, 112)])
async def test_farigiraf_native_sps_across_tools(tools, investment, speed):
    stats = await tools.call_tool("get_pokemon_stats", {
        "pokemon_name": "farigiraf", "nature": "bold", "spe_evs": investment,
    })
    single = await tools.call_tool("get_pokemon_speed", {
        "pokemon_name": "farigiraf", "nature": "bold", "speed_evs": investment,
    })
    probability = await tools.call_tool("analyze_outspeed_probability", {
        "pokemon_name": "farigiraf", "target_pokemon": "farigiraf",
        "nature": "bold", "speed_evs": investment,
    })
    assert stats["final_stats"]["speed"] == single["calculated_speed"] == probability["your_speed"] == speed
    assert probability["speed_sps"] == investment
    assert "SPs" in probability["summary_table"]
    assert find_speed_sps(60, speed, Nature.BOLD) == investment


async def test_mainline_still_uses_evs(tools):
    get_regulation_config().set_session_regulation("reg_g", by_user=True)
    result = await tools.call_tool("analyze_outspeed_probability", {
        "pokemon_name": "farigiraf", "target_pokemon": "farigiraf",
        "nature": "bold", "speed_evs": 10,
    })
    assert result["your_speed"] == 81
    assert result["speed_evs"] == 10


async def test_speed_rejects_over_cap(tools):
    result = await tools.call_tool("analyze_outspeed_probability", {
        "pokemon_name": "farigiraf", "target_pokemon": "farigiraf", "speed_evs": 33,
    })
    assert result["error"] == "invalid_parameter"
    assert "32" in result["message"]


@pytest.mark.parametrize("target_tailwind,investment,outspeeds", [(False, 15, True), (True, 32, False)])
async def test_tailwind_benchmark(tools, target_tailwind, investment, outspeeds):
    result = await tools.call_tool("design_spread_with_benchmarks", {
        "pokemon_name": "farigiraf", "nature": "bold",
        "outspeed_pokemon": "salamence-mega", "outspeed_pokemon_nature": "timid",
        "outspeed_pokemon_evs": 32, "my_pokemon_has_tailwind": True,
        "outspeed_target_has_tailwind": target_tailwind,
    })
    assert result["spread"]["total"] == 66
    speed = result["benchmarks"]["speed"]
    assert speed["sps_needed"] == investment
    assert speed["my_speed"] == 80 + investment
    assert speed["my_effective_speed"] == 2 * (80 + investment)
    assert speed["target_speed"] == (378 if target_tailwind else 189)
    assert speed["outspeeds"] is outspeeds
    assert result["verified"] is outspeeds
    assert result["verdict"] == ("SUCCESS" if outspeeds else "BENCHMARK_NOT_MET")


@pytest.mark.parametrize("target_investment,expected", [(10, 11), (15, 16), (252, 32)])
async def test_benchmark_target_uses_native_sps(tools, target_investment, expected):
    result = await tools.call_tool("design_spread_with_benchmarks", {
        "pokemon_name": "farigiraf", "nature": "bold", "outspeed_pokemon": "farigiraf",
        "outspeed_pokemon_nature": "bold", "outspeed_pokemon_evs": target_investment,
    })
    assert result["spread"]["spe_sps"] == expected
    assert result["spread"]["total"] == 66


@pytest.mark.parametrize("role", ["offensive", "bulky", "bulky_offense", "support"])
@pytest.mark.parametrize("item", [None, "sitrus-berry", "life-orb", "leftovers"])
async def test_recommendations_spend_all_points(tools, role, item):
    result = await tools.call_tool("suggest_spread", {
        "pokemon_name": "farigiraf", "role": role, "item": item, "speed_target": 88,
    })
    sps = result["suggestion"]["sps"]
    assert sum(sps.values()) == 66
    assert all(0 <= value <= 32 for value in sps.values())
    assert "SPs:" in result["showdown_paste"]
    assert "EVs:" not in result["showdown_paste"]


@pytest.mark.parametrize("item", ["life-orb", "sitrus-berry", "leftovers"])
async def test_bulk_item_adjustments_reallocate_points(tools, item):
    result = await tools.call_tool("optimize_bulk", {
        "pokemon_name": "farigiraf", "nature": "bold", "item": item,
    })
    spread = result["optimal_spread"]
    assert spread["hp_sps"] + spread["def_sps"] + spread["spd_sps"] == 66
    assert spread["final_def"] == int((70 + spread["def_sps"] + 20) * 1.1)
    assert spread["final_spd"] == 70 + spread["spd_sps"] + 20


async def test_incomplete_spread_explicitly_reported(tools):
    result = await tools.call_tool("check_spread_efficiency", {
        "pokemon_name": "farigiraf", "nature": "bold", "spe_evs": 10,
    })
    assert result["is_valid"] is True
    assert result["is_complete"] is False
    assert result["remaining_sps"] == 56


@pytest.mark.parametrize("tool_name", ["design_spread_with_benchmarks", "optimize_multi_survival_spread"])
async def test_survival_recommendation_is_completed_and_verified(tools, tool_name):
    inputs = {"pokemon_name": "farigiraf", "nature": "bold"}
    if tool_name == "design_spread_with_benchmarks":
        inputs.update({"survive_pokemon": "farigiraf", "survive_move": "tackle"})
    else:
        inputs["threats"] = [{"attacker": "farigiraf", "move": "tackle"}] * 3
    result = await tools.call_tool(tool_name, inputs)
    assert result["spread"]["total"] == 66
    if tool_name == "design_spread_with_benchmarks":
        assert result["benchmarks"]["survival"]["verified"] is True
    else:
        assert result["verified"] is True


def test_completion_preserves_speed_and_caps():
    result = complete_sp_allocation({"hp": 32, "defense": 19, "speed": 10})
    assert result == {"hp": 32, "defense": 24, "special_defense": 0, "speed": 10}
    with pytest.raises(ValueError):
        complete_sp_allocation({"hp": 32, "defense": 32, "speed": 10})


@pytest.mark.parametrize("allocation", [{"spe": 10}, {"speed": 10.0}, {"speed": True}])
def test_completion_rejects_ambiguous_input(allocation):
    with pytest.raises(ValueError):
        complete_sp_allocation(allocation)


def test_champions_stats_ignore_legacy_ivs():
    pokemon = PokemonBuild(
        name="farigiraf", nature=Nature.BOLD, format_system="champions",
        base_stats=BaseStats(hp=120, attack=90, defense=70, special_attack=110, special_defense=70, speed=60),
        sps=StatPointSpread(hp=32, defense=24, speed=10),
        ivs=IVSpread(**{stat: 0 for stat in IVSpread.model_fields}),
    )
    assert calculate_all_stats(pokemon) == {"hp": 227, "attack": 99, "defense": 125,
                                            "special_attack": 130, "special_defense": 90, "speed": 90}
    assert calculate_all_stats(pokemon) == calculate_all_stats(pokemon.model_copy(update={"ivs": IVSpread()}))


@pytest.mark.parametrize("investment,expected", [(1, 1), (11, 11), (32, 32), (252, 32)])
async def test_explicit_offensive_investment(tools, investment, expected):
    result = await tools.call_tool("design_spread_with_benchmarks", {
        "pokemon_name": "farigiraf", "nature": "bold", "prioritize": "offense",
        "offensive_evs": investment,
    })
    assert result["spread"]["spa_sps"] == expected
    assert result["spread"]["total"] == 66


@pytest.mark.parametrize("investment,expected", [(10, 10), (32, 32), (252, 32)])
async def test_survival_attacker_uses_sps(tools, investment, expected):
    result = await tools.call_tool("design_spread_with_benchmarks", {
        "pokemon_name": "farigiraf", "nature": "bold", "survive_pokemon": "farigiraf",
        "survive_move": "tackle", "survive_pokemon_evs": investment,
    })
    benchmark = result["benchmarks"]["survival"]
    assert benchmark["attacker_sps"] == expected
    assert f"{expected} Atk" in benchmark["attacker_showdown_paste"]
    assert "SPs:" in benchmark["attacker_showdown_paste"]
    assert "EVs:" not in benchmark["attacker_showdown_paste"]
    assert benchmark["hp_remaining"] == f"{100 - benchmark['max_percent']:.1f}%"


async def test_survival_preserves_sourced_champions_spread(tools, monkeypatch):
    monkeypatch.setattr("vgc_mcp.tools.spread_tools._get_common_spread", AsyncMock(return_value={
        "nature": "bold", "sps": {"hp": 32, "at": 10, "df": 14, "sp": 10},
        "format_system": "champions",
    }))
    result = await tools.call_tool("optimize_multi_survival_spread", {
        "pokemon_name": "farigiraf", "nature": "bold",
        "threats": [{"attacker": "farigiraf", "move": "tackle"}] * 3,
    })
    paste = result["threat_breakdown"][0]["attacker_showdown_paste"]
    assert "SPs: 32 HP / 10 Atk / 14 Def / 10 Spe" in paste


@pytest.mark.parametrize("parameters", [
    {"survive_pokemon": "farigiraf"},
    {"survive_move": "tackle"},
    {"outspeed_pokemon": "missing"},
    {"survive_pokemon": "missing", "survive_move": "tackle"},
    {"prioritize": "unknown"},
    {"defender_tera_type": "normal"},
])
async def test_invalid_benchmarks_do_not_emit_a_recommendation(tools, parameters):
    result = await tools.call_tool("design_spread_with_benchmarks", {"pokemon_name": "farigiraf", **parameters})
    assert result["error"] == "invalid_parameter"
    assert "showdown_paste" not in result


@pytest.mark.parametrize("tool_name", ["optimize_dual_survival_spread", "optimize_multi_survival_spread"])
@pytest.mark.parametrize("fixed_sps,expected,verified", [(None, 15, True), (10, 10, False), (16, 16, True)])
async def test_survival_speed_modifiers_and_override(tools, tool_name, fixed_sps, expected, verified):
    inputs = {"pokemon_name": "farigiraf", "nature": "bold", "outspeed_pokemon": "salamence-mega",
              "outspeed_pokemon_nature": "timid", "my_pokemon_has_tailwind": True}
    if fixed_sps is not None:
        inputs["speed_evs"] = fixed_sps
    if tool_name == "optimize_dual_survival_spread":
        inputs.update({"survive_hit1_attacker": "farigiraf", "survive_hit1_move": "tackle",
                       "survive_hit2_attacker": "farigiraf", "survive_hit2_move": "tackle"})
    else:
        inputs["threats"] = [{"attacker": "farigiraf", "move": "tackle"}] * 3
    result = await tools.call_tool(tool_name, inputs)
    assert result["spread"]["spe_sps"] == expected
    assert result["spread"]["total"] == 66
    assert result["verified"] is verified
    assert result["speed_benchmark"]["my_effective_speed"] == 2 * (80 + expected)
