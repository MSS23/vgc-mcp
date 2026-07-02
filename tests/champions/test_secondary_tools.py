"""Champions (Reg MA) regression tests for the long-tail secondary tools.

Covers:
- get_pokemon_stats / get_pokemon_speed (stats_tools.py): SP input is read as
  Stat Points, stats use the SP formula, investment is labelled Stat Points,
  and an 'SPs:' paste is returned.
- analyze_team_matchup (team_matchup_tools.py): the user's team builds
  format-aware in a Champions session.
- TeamManager.get_team_summary / list_pokemon_context (manager.py): champions
  builds surface an 'sps' key instead of an all-zero 'evs' dict.

Each tool is exercised via its ACTUAL registered function in a Champions
session, with a mainline guard proving the EV path is untouched.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.stats_tools import register_stats_tools
from vgc_mcp.tools.team_matchup_tools import register_team_matchup_tools
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.team.manager import TeamManager

# --- Fakes (no network) ---------------------------------------------------

_BASE = {
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "rillaboom": BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
    "amoonguss": BaseStats(hp=114, attack=85, defense=70, special_attack=85, special_defense=80, speed=30),
    "dragapult": BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142),
    "landorus-incarnate": BaseStats(hp=89, attack=125, defense=90, special_attack=115, special_defense=80, speed=101),
    "tornadus": BaseStats(hp=79, attack=115, defense=70, special_attack=125, special_defense=80, speed=111),
}
_TYPES = {
    "flutter-mane": ["ghost", "fairy"],
    "incineroar": ["fire", "dark"],
    "rillaboom": ["grass"],
    "amoonguss": ["grass", "poison"],
    "dragapult": ["dragon", "ghost"],
    "landorus-incarnate": ["ground", "flying"],
    "tornadus": ["flying"],
}


class _FakePokeAPI:
    async def get_base_stats(self, name):
        return _BASE.get(name.lower(), BaseStats(hp=80, attack=80, defense=80, special_attack=80, special_defense=80, speed=80))

    async def get_pokemon_types(self, name):
        return list(_TYPES.get(name.lower(), ["normal"]))


class _FakeSmogon:
    async def get_pokemon_usage(self, *a, **k):
        return None


# --- Session fixtures -----------------------------------------------------

@pytest.fixture
def champ_session():
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_ma_champs")
    yield
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


@pytest.fixture
def main_session():
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_h")
    yield
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


def _stats_tm():
    mcp = FastMCP("test")
    register_stats_tools(mcp, _FakePokeAPI())
    return mcp._tool_manager


def _matchup_tm(team_manager):
    mcp = FastMCP("test")
    register_team_matchup_tools(mcp, _FakePokeAPI(), _FakeSmogon(), team_manager)
    return mcp._tool_manager


def _assert_sp_paste(paste: str):
    assert paste is not None
    assert "SPs:" in paste
    assert "EVs:" not in paste


# --- get_pokemon_stats ----------------------------------------------------

class TestGetPokemonStatsChampions:
    async def test_sp_input_uses_sp_formula(self, champ_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_stats",
            {"pokemon_name": "flutter-mane", "nature": "timid", "spa_evs": 32, "spe_evs": 32, "hp_evs": 2},
        )
        assert r["format_system"] == "champions"
        # 32 Spe SP Timid Flutter Mane = 205 (NOT the 252-EV mainline number).
        assert r["final_stats"]["speed"] == 205
        assert "sps" in r and "evs" not in r
        assert r["sps"]["total"] == 66
        for stat in ("hp", "attack", "defense", "special_attack", "special_defense", "speed"):
            assert r["sps"][stat] <= 32
        # Investment labelled as Stat Points in the table + analysis.
        assert "SPs" in r["summary_table"]
        assert "Stat Points" in r["analysis"]
        _assert_sp_paste(r["showdown_paste"])

    async def test_over_per_stat_cap_rejected(self, champ_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_stats",
            {"pokemon_name": "flutter-mane", "nature": "timid", "spe_evs": 40},
        )
        assert "error" in r or r.get("code")

    async def test_over_total_cap_rejected(self, champ_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_stats",
            {"pokemon_name": "flutter-mane", "nature": "serious",
             "hp_evs": 32, "atk_evs": 32, "def_evs": 10},
        )
        assert "error" in r or r.get("code")


class TestGetPokemonSpeedChampions:
    async def test_sp_speed_formula(self, champ_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_speed",
            {"pokemon_name": "flutter-mane", "nature": "timid", "speed_evs": 32},
        )
        assert r["format_system"] == "champions"
        assert r["calculated_speed"] == 205
        assert r["sps"] == 32
        assert "SPs" in r["summary_table"]

    async def test_over_cap_rejected(self, champ_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_speed",
            {"pokemon_name": "flutter-mane", "nature": "timid", "speed_evs": 40},
        )
        assert "error" in r or r.get("code")


# --- analyze_team_matchup -------------------------------------------------

class TestAnalyzeTeamMatchupChampions:
    async def test_champions_team_builds_format_aware(self, champ_session):
        tm = _matchup_tm(TeamManager())
        team = ["flutter-mane", "incineroar", "rillaboom", "amoonguss", "dragapult", "tornadus"]
        r = await tm.call_tool("analyze_team_matchup", {"team_pokemon": team})
        assert r.get("format_system") == "champions"
        assert "overall_rating" in r
        assert r["team"] == team


# --- TeamManager summary / context ---------------------------------------

def _champ_build(name):
    return PokemonBuild(
        name=name,
        base_stats=_BASE[name],
        types=_TYPES[name],
        nature=Nature.TIMID,
        format_system="champions",
        sps=StatPointSpread(special_attack=32, speed=32, hp=2),
    )


class TestTeamManagerChampions:
    def test_team_summary_surfaces_sps(self):
        tmgr = TeamManager()
        tmgr.add_pokemon(_champ_build("flutter-mane"))
        summary = tmgr.get_team_summary()
        entry = summary["pokemon"][0]
        assert entry["format_system"] == "champions"
        assert "sps" in entry and "evs" not in entry
        assert entry["sps"]["speed"] == 32
        assert entry["sps"]["special_attack"] == 32

    def test_context_list_surfaces_sps(self):
        tmgr = TeamManager()
        tmgr.set_pokemon_context("flutter-mane", _champ_build("flutter-mane"))
        ctx = tmgr.list_pokemon_context()
        assert ctx[0]["format_system"] == "champions"
        assert "sps" in ctx[0] and "evs" not in ctx[0]
        assert ctx[0]["sps"]["speed"] == 32


# --- Mainline guards ------------------------------------------------------

class TestMainlineUnchanged:
    async def test_stats_still_ev(self, main_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_stats",
            {"pokemon_name": "flutter-mane", "nature": "timid", "spa_evs": 252, "spe_evs": 252, "hp_evs": 4},
        )
        assert "format_system" not in r
        assert "evs" in r and "sps" not in r
        assert r["evs"]["total"] == 508
        assert "EVs" in r["summary_table"]

    async def test_speed_still_ev(self, main_session):
        tm = _stats_tm()
        r = await tm.call_tool(
            "get_pokemon_speed",
            {"pokemon_name": "flutter-mane", "nature": "timid", "speed_evs": 252},
        )
        assert "format_system" not in r
        assert r["evs"] == 252

    def test_team_summary_still_ev(self):
        tmgr = TeamManager()
        tmgr.add_pokemon(PokemonBuild(
            name="incineroar",
            base_stats=_BASE["incineroar"],
            types=_TYPES["incineroar"],
            nature=Nature.ADAMANT,
            evs=EVSpread(hp=252, attack=252, defense=4),
        ))
        entry = tmgr.get_team_summary()["pokemon"][0]
        assert "evs" in entry and "sps" not in entry
        assert "format_system" not in entry
        assert entry["evs"]["hp"] == 252

    def test_context_list_still_ev(self):
        tmgr = TeamManager()
        tmgr.set_pokemon_context("incineroar", PokemonBuild(
            name="incineroar",
            base_stats=_BASE["incineroar"],
            types=_TYPES["incineroar"],
            nature=Nature.ADAMANT,
            evs=EVSpread(hp=252, attack=252, defense=4),
        ))
        ctx = tmgr.list_pokemon_context()
        assert "evs" in ctx[0] and "sps" not in ctx[0]
        assert "format_system" not in ctx[0]
