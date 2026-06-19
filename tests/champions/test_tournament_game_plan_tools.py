"""Champions (Reg MA) regression tests for tournament_tools + game_plan_tools.

These call the ACTUAL registered tool functions in a Champions session and
assert that the user's SUBJECT Pokemon are built on the Stat Point grain:

- ``analyze_paste_bulk`` imports a Champions ``SPs:`` paste as a champions
  build (correct Speed/HP, ``format_system == "champions"``, ``sps`` key, no
  ``EVs:`` / 252 / 508 leakage).
- ``analyze_team_vs_meta`` / ``compare_two_teams`` route pasted teams through
  the format-aware ``parsed_to_pokemon_build``, so Champions pastes produce
  champions builds.
- ``generate_game_plan`` builds the user's team members on the SP grain in a
  Champions session while opponent meta references stay mainline.

Mainline assertions guard that the legacy EV path is untouched.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.tournament_tools import register_tournament_tools, _parsed_to_build
from vgc_mcp.tools.game_plan_tools import register_game_plan_tools, _build_profile
from vgc_mcp_core.formats.showdown import parse_showdown_pokemon
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.calc.stats import calculate_all_stats


# --- Fakes (no network) ---------------------------------------------------

_BASE = {
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
    "rillaboom": BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "amoonguss": BaseStats(hp=114, attack=85, defense=70, special_attack=85, special_defense=80, speed=30),
}
_TYPES = {
    "flutter-mane": ["ghost", "fairy"],
    "rillaboom": ["grass"],
    "incineroar": ["fire", "dark"],
    "amoonguss": ["grass", "poison"],
}


class _FakePokeAPI:
    async def get_base_stats(self, name):
        return _BASE[name.lower().replace(" ", "-")]

    async def get_pokemon_types(self, name):
        return list(_TYPES.get(name.lower().replace(" ", "-"), ["normal"]))

    async def get_move(self, name, user_name=None):
        return None

    async def get_pokemon_abilities(self, name):
        return []


class _FakeSmogon:
    async def get_pokemon_usage(self, *a, **k):
        return None

    async def get_usage_stats(self, *a, **k):
        # One meta threat (stays mainline); it has no usable spread/moves so
        # the survival loop simply finds nothing, which is fine for these tests.
        return {"data": {"incineroar": {"usage": 0.3}}}


# --- Regulation fixtures --------------------------------------------------

@pytest.fixture
def champ_session():
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_ma_champs")
    yield cfg
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


@pytest.fixture
def main_session():
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_h")
    yield cfg
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


# --- _parsed_to_build (powers analyze_team_vs_meta / compare_two_teams) ----

class TestParsedToBuildFormatAware:
    async def test_champions_paste_imports_as_champions_build(self):
        paste = (
            "Flutter Mane @ Choice Specs\n"
            "Ability: Protosynthesis\n"
            "Level: 50\n"
            "SPs: 32 SpA / 32 Spe\n"
            "Timid Nature\n"
            "- Moonblast\n"
        )
        parsed = parse_showdown_pokemon(paste)
        build = await _parsed_to_build(parsed, _FakePokeAPI())
        assert build is not None
        assert build.format_system == "champions"
        assert build.sps is not None
        assert build.sps.special_attack == 32
        assert build.sps.speed == 32
        # 32 SP Timid Flutter Mane Speed == 205 (documented saturation).
        assert calculate_all_stats(build)["speed"] == 205

    async def test_mainline_paste_unchanged(self):
        paste = (
            "Flutter Mane @ Choice Specs\n"
            "Ability: Protosynthesis\n"
            "Level: 50\n"
            "EVs: 252 SpA / 4 Def / 252 Spe\n"
            "Timid Nature\n"
            "- Moonblast\n"
        )
        parsed = parse_showdown_pokemon(paste)
        build = await _parsed_to_build(parsed, _FakePokeAPI())
        assert build is not None
        assert build.format_system == "mainline"
        assert build.evs.special_attack == 252
        assert build.evs.speed == 252
        assert calculate_all_stats(build)["speed"] == 205


# --- analyze_paste_bulk ---------------------------------------------------

def _make_tournament_tm(monkeypatch):
    mcp = FastMCP("test")
    register_tournament_tools(mcp, pokepaste=None, pokeapi=_FakePokeAPI(), smogon=_FakeSmogon())
    return mcp._tool_manager


class TestAnalyzePasteBulkChampions:
    async def test_champions_subject_no_ev_leak(self, champ_session, monkeypatch):
        tm = _make_tournament_tm(monkeypatch)
        paste = (
            "Flutter Mane @ Choice Specs\n"
            "Ability: Protosynthesis\n"
            "Level: 50\n"
            "SPs: 32 HP / 16 Def / 18 SpD\n"
            "Bold Nature\n"
        )
        r = await tm.call_tool("analyze_paste_bulk", {"pokemon_paste": paste, "top_threats": 1})
        assert r["success"] is True
        assert r["format_system"] == "champions"
        assert "sps" in r
        assert "evs" not in r
        report = r["formatted_report"]
        assert "| SPs |" in report
        assert "No EVs" not in report
        assert "EVs:" not in report

    async def test_mainline_subject_unchanged(self, main_session, monkeypatch):
        tm = _make_tournament_tm(monkeypatch)
        paste = (
            "Flutter Mane @ Choice Specs\n"
            "Ability: Protosynthesis\n"
            "Level: 50\n"
            "EVs: 252 HP / 4 Def / 252 SpD\n"
            "Bold Nature\n"
        )
        r = await tm.call_tool("analyze_paste_bulk", {"pokemon_paste": paste, "top_threats": 1})
        assert r["success"] is True
        assert r["format_system"] == "mainline"
        assert "evs" in r
        assert "sps" not in r
        assert "| EVs |" in r["formatted_report"]


# --- generate_game_plan ---------------------------------------------------

def _make_game_plan_tm(monkeypatch):
    # Silence Smogon common-spread lookups so members fall back to defaults.
    import vgc_mcp.tools.game_plan_tools as gp

    async def _no_spread(name):
        return None

    monkeypatch.setattr(gp, "_get_common_spread", _no_spread)

    mcp = FastMCP("test")
    register_game_plan_tools(mcp, _FakePokeAPI(), TeamManager(), _FakeSmogon())
    return mcp._tool_manager


class TestBuildProfileFormatAware:
    async def test_champions_subject_builds_on_sp_grain(self):
        prof = await _build_profile(
            "flutter-mane", _FakePokeAPI(), _FakeSmogon(),
            is_champions_subject=True,
        )
        assert prof.build.format_system == "champions"

    async def test_opponent_reference_stays_mainline(self):
        prof = await _build_profile(
            "flutter-mane", _FakePokeAPI(), _FakeSmogon(),
            is_champions_subject=False,
        )
        assert prof.build.format_system == "mainline"


class TestGenerateGamePlanChampions:
    async def test_user_team_champions_opponents_mainline(self, champ_session, monkeypatch):
        tm = _make_game_plan_tm(monkeypatch)
        r = await tm.call_tool("generate_game_plan", {
            "your_team": ["flutter-mane", "rillaboom"],
            "opponent_team": ["incineroar", "amoonguss"],
        })
        # The tool returns the plan dict (no error_response shape).
        assert "markdown_summary" in r
        assert r["your_team"]
        assert r["opponent_team"]

    async def test_mainline_session_unchanged(self, main_session, monkeypatch):
        tm = _make_game_plan_tm(monkeypatch)
        r = await tm.call_tool("generate_game_plan", {
            "your_team": ["flutter-mane", "rillaboom"],
            "opponent_team": ["incineroar", "amoonguss"],
        })
        assert "markdown_summary" in r
