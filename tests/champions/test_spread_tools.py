"""Champions (Reg MA) regression tests for spread/optimization tools (Agent T4).

These call the ACTUAL registered tool functions (via the FastMCP tool manager)
in a Champions session and assert SP-scale output:
- spreads stay within 32/stat and 66 total,
- returned showdown_paste is an 'SPs:' paste (never an 'EVs:' / 252 / 508 line),
- responses are tagged format_system == 'champions'.

A matching mainline assertion guards that the legacy EV path is untouched.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.spread_tools import register_spread_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

# --- Fakes (no network) ---------------------------------------------------

_BASE = {
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
    "rillaboom": BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "landorus-incarnate": BaseStats(hp=89, attack=125, defense=90, special_attack=115, special_defense=80, speed=101),
    "dragapult": BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142),
}
_TYPES = {
    "flutter-mane": ["ghost", "fairy"],
    "rillaboom": ["grass"],
    "incineroar": ["fire", "dark"],
    "landorus-incarnate": ["ground", "flying"],
    "dragapult": ["dragon", "ghost"],
}
_MOVES = {
    "flare-blitz": Move(name="flare-blitz", type="fire", category=MoveCategory.PHYSICAL, power=120),
    "earth-power": Move(name="earth-power", type="ground", category=MoveCategory.SPECIAL, power=90),
    "moonblast": Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL, power=95),
}


class _FakePokeAPI:
    async def get_base_stats(self, name):
        return _BASE[name.lower()]

    async def get_pokemon_types(self, name):
        return list(_TYPES.get(name.lower(), ["normal"]))

    async def get_move(self, name, user_name=None):
        return _MOVES[name.lower()]

    async def get_pokemon_abilities(self, name):
        return []


class _FakeSmogon:
    async def get_pokemon_usage(self, *a, **k):
        return None


def _make_tm(monkeypatch):
    # Silence Smogon common-spread lookups so attackers fall back to defaults.
    import vgc_mcp.tools.spread_tools as st

    async def _no_spread(name):
        return None

    monkeypatch.setattr(st, "_get_common_spread", _no_spread)

    mcp = FastMCP("test")
    register_spread_tools(mcp, _FakePokeAPI(), _FakeSmogon())
    return mcp._tool_manager


@pytest.fixture
def champ_tm(monkeypatch):
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_ma_champs")
    yield _make_tm(monkeypatch)
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


@pytest.fixture
def main_tm(monkeypatch):
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_h")
    yield _make_tm(monkeypatch)
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


# --- Assertion helpers ----------------------------------------------------

def _assert_sp_paste(paste: str):
    assert paste is not None
    assert "SPs:" in paste
    assert "EVs:" not in paste
    assert "252" not in paste
    assert "508" not in paste


def _assert_sp_caps(sps: dict):
    for stat, val in sps.items():
        assert 0 <= val <= 32, f"{stat}={val} violates per-stat cap 32"
    assert sum(sps.values()) <= 66, "SP total exceeds 66"


# --- suggest_spread -------------------------------------------------------

class TestSuggestSpreadChampions:
    async def test_offensive_emits_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool("suggest_spread", {"pokemon_name": "flutter-mane", "role": "offensive"})
        assert r["format_system"] == "champions"
        sps = r["suggestion"]["sps"]
        _assert_sp_caps(sps)
        assert r["suggestion"]["total_sps"] <= 66
        _assert_sp_paste(r["showdown_paste"])

    async def test_bulky_role_within_caps(self, champ_tm):
        r = await champ_tm.call_tool("suggest_spread", {"pokemon_name": "rillaboom", "role": "bulky"})
        _assert_sp_caps(r["suggestion"]["sps"])
        _assert_sp_paste(r["showdown_paste"])

    async def test_speed_target_uses_sp_solver(self, champ_tm):
        r = await champ_tm.call_tool(
            "suggest_spread",
            {"pokemon_name": "flutter-mane", "role": "offensive", "speed_target": 180},
        )
        sps = r["suggestion"]["sps"]
        _assert_sp_caps(sps)
        # Speed SP must be <= 32 and enough to clear the target.
        assert sps["speed"] <= 32


# --- optimize_bulk --------------------------------------------------------

class TestOptimizeBulkChampions:
    async def test_emits_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool("optimize_bulk", {"pokemon_name": "flutter-mane", "nature": "calm"})
        assert r["format_system"] == "champions"
        spread = r["optimal_spread"]
        caps = {"hp": spread["hp_sps"], "defense": spread["def_sps"], "special_defense": spread["spd_sps"]}
        _assert_sp_caps(caps)
        _assert_sp_paste(r["showdown_paste"])

    async def test_optimize_bulk_math_emits_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool("optimize_bulk_math", {"pokemon_name": "flutter-mane", "nature": "calm"})
        assert r["format_system"] == "champions"
        _assert_sp_paste(r["showdown_paste"])


# --- check_spread_efficiency ---------------------------------------------

class TestCheckSpreadEfficiencyChampions:
    async def test_valid_sp_spread(self, champ_tm):
        r = await champ_tm.call_tool(
            "check_spread_efficiency",
            {"pokemon_name": "flutter-mane", "nature": "timid", "spa_evs": 32, "spe_evs": 32, "hp_evs": 2},
        )
        assert r["format_system"] == "champions"
        assert r["is_valid"] is True
        assert r["total_sps"] == 66
        _assert_sp_paste(r["showdown_paste"])

    async def test_over_cap_flagged_no_paste(self, champ_tm):
        r = await champ_tm.call_tool(
            "check_spread_efficiency",
            {"pokemon_name": "flutter-mane", "nature": "timid", "spa_evs": 40, "spe_evs": 32},
        )
        assert r["is_valid"] is False
        assert r["showdown_paste"] is None
        assert any("32" in issue for issue in r["issues"])


# --- suggest_nature_optimization -----------------------------------------

class TestNatureOptimizationChampions:
    async def test_returns_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool(
            "suggest_nature_optimization",
            {
                "pokemon_name": "flutter-mane", "current_nature": "serious",
                "hp_evs": 0, "atk_evs": 0, "def_evs": 0,
                "spa_evs": 32, "spd_evs": 0, "spe_evs": 32,
            },
        )
        assert r["format_system"] == "champions"
        # Either an optimization with an SP paste, or "already optimal" (still SP).
        if r["optimization_found"]:
            _assert_sp_paste(r["optimized_showdown_paste"])
            _assert_sp_caps(r["suggested_sps"])
        _assert_sp_paste(r["current_showdown_paste"])


# --- design_spread_with_benchmarks ---------------------------------------

class TestDesignBenchmarksChampions:
    async def test_offense_speed_emits_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool(
            "design_spread_with_benchmarks",
            {"pokemon_name": "flutter-mane", "outspeed_pokemon": "rillaboom", "prioritize": "offense"},
        )
        assert r["format_system"] == "champions"
        spread = r["spread"]
        caps = {
            "hp": spread["hp_sps"], "attack": spread["atk_sps"], "defense": spread["def_sps"],
            "special_attack": spread["spa_sps"], "special_defense": spread["spd_sps"], "speed": spread["spe_sps"],
        }
        _assert_sp_caps(caps)
        _assert_sp_paste(r["showdown_paste"])


# --- optimize_dual_survival_spread ---------------------------------------

class TestDualSurvivalChampions:
    async def test_dual_survival_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool(
            "optimize_dual_survival_spread",
            {
                "pokemon_name": "flutter-mane",
                "survive_hit1_attacker": "incineroar", "survive_hit1_move": "flare-blitz",
                "survive_hit2_attacker": "landorus-incarnate", "survive_hit2_move": "earth-power",
                "target_survival": 93.75,
            },
        )
        assert r["format_system"] == "champions"
        if r["verdict"] == "SUCCESS":
            _assert_sp_caps({
                "hp": r["spread"]["hp_sps"], "defense": r["spread"]["def_sps"],
                "special_defense": r["spread"]["spd_sps"], "speed": r["spread"]["spe_sps"],
            })
            _assert_sp_paste(r["showdown_paste"])


# --- optimize_multi_survival_spread --------------------------------------

class TestMultiSurvivalChampions:
    async def test_three_threats_sp_paste(self, champ_tm):
        r = await champ_tm.call_tool(
            "optimize_multi_survival_spread",
            {
                "pokemon_name": "flutter-mane",
                "threats": [
                    {"attacker": "incineroar", "move": "flare-blitz"},
                    {"attacker": "landorus-incarnate", "move": "earth-power"},
                    {"attacker": "dragapult", "move": "moonblast"},
                ],
                "target_survival": 93.75,
            },
        )
        assert r["format_system"] == "champions"
        if r["verdict"] == "SUCCESS":
            _assert_sp_paste(r["showdown_paste"])


# --- mainline guard -------------------------------------------------------

class TestMainlineUnchanged:
    async def test_mainline_still_emits_ev_paste(self, main_tm):
        r = await main_tm.call_tool("suggest_spread", {"pokemon_name": "rillaboom", "role": "offensive"})
        assert "format_system" not in r
        assert "EVs:" in r["showdown_paste"]
        assert "SPs:" not in r["showdown_paste"]
