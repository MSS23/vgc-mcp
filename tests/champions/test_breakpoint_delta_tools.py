"""Champions (Reg MA) regression tests for breakpoint_tools + delta_tools.

These call the ACTUAL registered tool functions (via the FastMCP tool manager)
in a Champions session and assert SP-scale output:
- breakpoints sweep SP (0-32 per stat, <=66 total) and report SP units,
- compare_build_changes builds the subject as a Champions SP build and emits
  'SPs:' pastes (never 'EVs:' / 252 / 508),
- responses are tagged format_system == 'champions'.

Matching mainline assertions guard that the legacy EV path is untouched.
Opposing threats / targets always stay mainline meta references.
"""

import pytest
from mcp.server.fastmcp import FastMCP

import vgc_mcp.tools.breakpoint_tools as bt
import vgc_mcp.tools.delta_tools as dt
from vgc_mcp.tools.breakpoint_tools import register_breakpoint_tools
from vgc_mcp.tools.delta_tools import register_delta_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

# --- Fakes (no network) ---------------------------------------------------

_BASE = {
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "dragapult": BaseStats(hp=88, attack=120, defense=75, special_attack=100, special_defense=75, speed=142),
    "frail": BaseStats(hp=50, attack=50, defense=40, special_attack=50, special_defense=40, speed=50),
}
_TYPES = {
    "flutter-mane": ["ghost", "fairy"],
    "incineroar": ["fire", "dark"],
    "dragapult": ["dragon", "ghost"],
    "frail": ["dragon"],
}
_MOVES = {
    "moonblast": Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL, power=95),
    "shadow-ball": Move(name="shadow-ball", type="ghost", category=MoveCategory.SPECIAL, power=80),
    "flare-blitz": Move(name="flare-blitz", type="fire", category=MoveCategory.PHYSICAL, power=120),
    "tackle": Move(name="tackle", type="normal", category=MoveCategory.PHYSICAL, power=40),
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


def _make_breakpoint_tm(monkeypatch):
    async def _no_spread(client, name):
        return None

    async def _no_ability(name, **kwargs):
        return (None, None)

    monkeypatch.setattr(bt, "get_common_spread", _no_spread)
    monkeypatch.setattr(bt, "resolve_ability", _no_ability)

    mcp = FastMCP("test")
    register_breakpoint_tools(mcp, _FakePokeAPI(), _FakeSmogon())
    return mcp._tool_manager


def _make_delta_tm(monkeypatch):
    async def _no_spread(client, name):
        return None

    monkeypatch.setattr(dt, "get_common_spread", _no_spread)

    mcp = FastMCP("test")
    register_delta_tools(mcp, _FakePokeAPI(), _FakeSmogon())
    return mcp._tool_manager


@pytest.fixture
def champ_bp(monkeypatch):
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_ma_champs")
    yield _make_breakpoint_tm(monkeypatch)
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


@pytest.fixture
def main_bp(monkeypatch):
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_h")
    yield _make_breakpoint_tm(monkeypatch)
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


@pytest.fixture
def champ_delta(monkeypatch):
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_ma_champs")
    yield _make_delta_tm(monkeypatch)
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


@pytest.fixture
def main_delta(monkeypatch):
    cfg = get_regulation_config()
    prev = cfg.current_regulation
    cfg.set_session_regulation("reg_h")
    yield _make_delta_tm(monkeypatch)
    cfg.clear_session_override()
    if prev:
        cfg.set_session_regulation(prev)


# --- Assertion helpers ----------------------------------------------------

def _assert_sp_paste(paste: str):
    assert paste is not None
    assert "EVs:" not in paste
    assert "252" not in paste
    assert "508" not in paste
    # An SP paste with any nonzero stat carries an 'SPs:' line; a fully-zero
    # spread legitimately omits it. Never an EV line either way.


def _assert_sp_caps(sps: dict):
    for stat, val in sps.items():
        assert 0 <= val <= 32, f"{stat}={val} violates per-stat cap 32"
    assert sum(sps.values()) <= 66, "SP total exceeds 66"


# --- find_breakpoint: outspeed -------------------------------------------

class TestOutspeedBreakpointChampions:
    async def test_reports_sp_units(self, champ_bp):
        r = await champ_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "outspeed",
             "target_pokemon": "incineroar"},
        )
        assert r["format_system"] == "champions"
        opt = r["options"][0]
        assert "sps" in opt and "evs" not in opt
        assert "sp_cost" in opt
        _assert_sp_caps(opt["sps"])
        _assert_sp_paste(opt["showdown_paste"])

    async def test_fast_target_uses_plus_nature_sp(self, champ_bp):
        # Outspeeding fast Dragapult forces real Speed SP investment.
        r = await champ_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "outspeed",
             "target_pokemon": "dragapult"},
        )
        assert r["format_system"] == "champions"
        for opt in r["options"]:
            _assert_sp_caps(opt["sps"])
            assert opt["sps"]["speed"] <= 32

    async def test_mainline_unchanged(self, main_bp):
        r = await main_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "outspeed",
             "target_pokemon": "incineroar"},
        )
        assert "format_system" not in r
        opt = r["options"][0]
        assert "evs" in opt and "sps" not in opt
        assert "ev_cost" in opt


# --- find_breakpoint: ko --------------------------------------------------

class TestKOBreakpointChampions:
    async def test_achievable_emits_sp_paste(self, champ_bp):
        r = await champ_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "ko",
             "target_pokemon": "frail", "target_move": "moonblast"},
        )
        assert r["format_system"] == "champions"
        achievable = [o for o in r["options"] if o.get("achievable")]
        assert achievable, "expected at least one achievable KO option"
        for o in achievable:
            assert "sps" in o and "evs" not in o
            assert "sp_cost" in o
            _assert_sp_caps(o["sps"])
            _assert_sp_paste(o["showdown_paste"])

    async def test_mainline_unchanged(self, main_bp):
        r = await main_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "ko",
             "target_pokemon": "frail", "target_move": "moonblast"},
        )
        assert "format_system" not in r
        achievable = [o for o in r["options"] if o.get("achievable")]
        assert achievable
        for o in achievable:
            assert "evs" in o and "sps" not in o


# --- find_breakpoint: survive --------------------------------------------

class TestSurviveBreakpointChampions:
    async def test_reports_sp_units(self, champ_bp):
        r = await champ_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "survive",
             "target_pokemon": "dragapult", "target_move": "shadow-ball"},
        )
        assert r["format_system"] == "champions"
        achievable = [o for o in r["options"] if o.get("achievable")]
        assert achievable, "expected an achievable survival option"
        for o in achievable:
            assert "sps" in o and "evs" not in o
            assert "sp_cost" in o
            _assert_sp_caps(o["sps"])
            assert o["sps"].get("hp", 0) + o["sps"].get("special_defense", 0) <= 66
            _assert_sp_paste(o["showdown_paste"])

    async def test_mainline_unchanged(self, main_bp):
        r = await main_bp.call_tool(
            "find_breakpoint",
            {"pokemon_name": "flutter-mane", "benchmark_type": "survive",
             "target_pokemon": "dragapult", "target_move": "shadow-ball"},
        )
        assert "format_system" not in r
        achievable = [o for o in r["options"] if o.get("achievable")]
        assert achievable
        for o in achievable:
            assert "evs" in o and "sps" not in o


# --- compare_build_changes ------------------------------------------------

class TestCompareBuildChangesChampions:
    async def test_subject_is_sp_paste(self, champ_delta):
        r = await champ_delta.call_tool(
            "compare_build_changes",
            {"pokemon_name": "flutter-mane",
             "before": {"sps": {"special_attack": 0}},
             "after": {"sps": {"special_attack": 32}},
             "threats": ["incineroar"],
             "as_attacker": True},
        )
        assert r["format_system"] == "champions"
        _assert_sp_paste(r["before_showdown_paste"])
        _assert_sp_paste(r["after_showdown_paste"])
        # The 32-SpA 'after' build must carry a real SPs: line and stay in caps.
        assert "SPs:" in r["after_showdown_paste"]
        assert "32" in r["after_showdown_paste"]

    async def test_evs_key_accepted_as_sp(self, champ_delta):
        # Users may keep passing the 'evs' key by habit; in a champions session
        # it is interpreted on the SP scale, not the EV scale.
        r = await champ_delta.call_tool(
            "compare_build_changes",
            {"pokemon_name": "flutter-mane",
             "before": {"evs": {"special_attack": 0}},
             "after": {"evs": {"special_attack": 16, "speed": 16}},
             "threats": ["incineroar"],
             "as_attacker": False},
        )
        assert r["format_system"] == "champions"
        _assert_sp_paste(r["after_showdown_paste"])
        assert "SPs:" in r["after_showdown_paste"]

    async def test_defender_mode_sp_deltas(self, champ_delta):
        r = await champ_delta.call_tool(
            "compare_build_changes",
            {"pokemon_name": "flutter-mane",
             "before": {"sps": {"hp": 0}},
             "after": {"sps": {"hp": 32, "special_defense": 16}},
             "threats": ["dragapult"],
             "as_attacker": False},
        )
        assert r["format_system"] == "champions"
        assert "deltas" in r and r["deltas"]
        _assert_sp_paste(r["after_showdown_paste"])

    async def test_mainline_unchanged(self, main_delta):
        r = await main_delta.call_tool(
            "compare_build_changes",
            {"pokemon_name": "flutter-mane",
             "before": {"evs": {"special_attack": 0}},
             "after": {"evs": {"special_attack": 252}},
             "threats": ["incineroar"],
             "as_attacker": True},
        )
        assert "format_system" not in r
        assert "EVs:" in r["after_showdown_paste"]
        assert "SPs:" not in r["after_showdown_paste"]
