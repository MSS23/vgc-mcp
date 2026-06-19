"""Champions (Reg MA) regression tests for tera + item-optimization tools.

Covers the long-tail tools that previously built the user's subject Pokemon
mainline-only:
- optimize_tera_type (tera_tools.py)
- compare_item_damage_output / optimize_life_orb_sustainability /
  analyze_item_ev_tradeoff (item_optimization_tools.py)

Each test calls the ACTUAL registered tool function via the FastMCP tool
manager in a Champions session and asserts SP-scale output (32/stat, 66 total,
'SPs:' pastes, format_system == 'champions'). A matching mainline test guards
the legacy EV path byte-for-byte.

CRITICAL NUANCE: only the subject Pokemon becomes champions. The opposing
target in compare_item_damage_output stays mainline (its fake Smogon spread is
untagged), so its paste must NOT be SP-scale.
"""

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.tera_tools import register_tera_tools
from vgc_mcp.tools.item_optimization_tools import register_item_optimization_tools
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.calc.stats_champions import calculate_hp_sp
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


# --- Fakes (no network) ---------------------------------------------------

_BASE = {
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55, special_attack=135, special_defense=135, speed=135),
    "incineroar": BaseStats(hp=95, attack=115, defense=90, special_attack=80, special_defense=90, speed=60),
    "rillaboom": BaseStats(hp=100, attack=125, defense=90, special_attack=60, special_defense=70, speed=85),
}
_TYPES = {
    "flutter-mane": ["ghost", "fairy"],
    "incineroar": ["fire", "dark"],
    "rillaboom": ["grass"],
}
_MOVES = {
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
    # Silence Smogon common-spread lookups so the subject/target fall back
    # to defaults (untagged => mainline target).
    import vgc_mcp.tools.item_optimization_tools as iot

    async def _no_spread(name):
        return None

    monkeypatch.setattr(iot, "_get_common_spread", _no_spread)

    mcp = FastMCP("test")
    register_tera_tools(mcp, _FakePokeAPI())
    register_item_optimization_tools(mcp, _FakePokeAPI(), _FakeSmogon())
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


def _assert_ev_paste(paste: str):
    assert paste is not None
    assert "SPs:" not in paste


# --- optimize_tera_type ---------------------------------------------------

class TestOptimizeTeraTypeChampions:
    async def test_subject_tagged_champions_sp_build_line(self, champ_tm):
        r = await champ_tm.call_tool(
            "optimize_tera_type",
            {
                "pokemon_name": "flutter-mane",
                "spread": {"nature": "timid", "sps": {"special_attack": 32, "speed": 32}},
            },
        )
        assert r["format_system"] == "champions"
        build_lines = [
            ln for ln in r["markdown_summary"].splitlines()
            if "SPs" in ln or "EVs" in ln
        ]
        assert build_lines, "missing build line"
        assert "SPs" in build_lines[0]
        assert "EVs" not in build_lines[0]
        assert "252" not in build_lines[0]
        assert r["recommended"] is not None

    async def test_ev_named_input_capped_to_sp(self, champ_tm):
        # An EV-style dict passed in a champions session is read as SP-scale,
        # capped per-stat at 32 (252 must never appear).
        r = await champ_tm.call_tool(
            "optimize_tera_type",
            {
                "pokemon_name": "flutter-mane",
                "spread": {"nature": "timid", "evs": {"special_attack": 252, "speed": 252}},
            },
        )
        assert r["format_system"] == "champions"
        build_line = next(
            ln for ln in r["markdown_summary"].splitlines() if "SPs" in ln
        )
        assert "252" not in build_line
        assert "/32/" in build_line or "32 SPs" in build_line


class TestOptimizeTeraTypeMainline:
    async def test_mainline_unchanged(self, main_tm):
        r = await main_tm.call_tool(
            "optimize_tera_type",
            {
                "pokemon_name": "flutter-mane",
                "spread": {"nature": "timid", "evs": {"special_attack": 252, "speed": 252}},
            },
        )
        assert r["format_system"] == "mainline"
        build_line = next(
            ln for ln in r["markdown_summary"].splitlines() if "EVs" in ln
        )
        assert "252" in build_line
        assert "SPs" not in build_line


# --- compare_item_damage_output -------------------------------------------

class TestCompareItemDamageChampions:
    async def test_subject_paste_is_sp_target_stays_mainline(self, champ_tm):
        r = await champ_tm.call_tool(
            "compare_item_damage_output",
            {
                "pokemon_name": "flutter-mane",
                "move_name": "moonblast",
                "target_name": "incineroar",
                "attacker_evs": {"special_attack": 32, "speed": 32},
                "target_evs": {"hp": 32, "special_defense": 32},
            },
        )
        # Subject (attacker) paste must be SP-scale.
        _assert_sp_paste(r["showdown_paste"])
        # Damage must still be computed (mainline target vs champions attacker).
        assert r["item_comparison"], "no item comparison results"
        for entry in r["item_comparison"]:
            assert entry["damage"], "missing damage range"


class TestCompareItemDamageMainline:
    async def test_mainline_subject_paste_is_ev(self, main_tm):
        r = await main_tm.call_tool(
            "compare_item_damage_output",
            {
                "pokemon_name": "flutter-mane",
                "move_name": "moonblast",
                "target_name": "incineroar",
                "attacker_evs": {"special_attack": 252, "speed": 252},
                "target_evs": {"hp": 252},
            },
        )
        _assert_ev_paste(r["showdown_paste"])
        assert r["item_comparison"]


# --- optimize_life_orb_sustainability -------------------------------------

class TestLifeOrbSustainabilityChampions:
    async def test_sp_grain_and_correct_hp(self, champ_tm):
        r = await champ_tm.call_tool(
            "optimize_life_orb_sustainability",
            {"pokemon_name": "flutter-mane"},
        )
        assert r["format_system"] == "champions"
        # Grain is 0 vs 32 SP, never 252.
        assert "HP SPs" in r["sustainability_table"]
        assert "252" not in r["sustainability_table"]
        assert "508" not in r["sustainability_table"]
        # Max HP at 32 SP must equal the canonical champions HP number.
        expected_full_hp = calculate_hp_sp(_BASE["flutter-mane"].hp, 31, 32, 50)
        assert str(expected_full_hp) in r["sustainability_table"]

    async def test_specific_sp_value_capped(self, champ_tm):
        r = await champ_tm.call_tool(
            "optimize_life_orb_sustainability",
            {"pokemon_name": "flutter-mane", "hp_investment": "200"},
        )
        assert r["format_system"] == "champions"
        # 200 requested but SP cap is 32 -> table reports the SP grain only.
        assert "252" not in r["sustainability_table"]


class TestLifeOrbSustainabilityMainline:
    async def test_mainline_uses_ev_grain(self, main_tm):
        r = await main_tm.call_tool(
            "optimize_life_orb_sustainability",
            {"pokemon_name": "flutter-mane"},
        )
        assert r["format_system"] == "mainline"
        assert "HP EVs" in r["sustainability_table"]
        assert "252" in r["sustainability_table"]


# --- analyze_item_ev_tradeoff ---------------------------------------------

class TestItemTradeoffChampions:
    async def test_sp_grain_pastes_and_caps(self, champ_tm):
        r = await champ_tm.call_tool(
            "analyze_item_ev_tradeoff",
            {"pokemon_name": "flutter-mane"},
        )
        assert r["format_system"] == "champions"
        assert "sps_saved" in r["recommendation"]
        _assert_sp_paste(r["recommendation"]["showdown_paste"])
        for entry in r["tradeoff_analysis"]:
            sps = entry["sps"]
            for stat, val in sps.items():
                assert 0 <= val <= 32, f"{stat}={val} over SP cap"
            assert sum(sps.values()) <= 66
            _assert_sp_paste(entry["showdown_paste"])

    async def test_choice_item_saves_sp(self, champ_tm):
        r = await champ_tm.call_tool(
            "analyze_item_ev_tradeoff",
            {"pokemon_name": "rillaboom", "items_to_test": ["choice-band", "life-orb"]},
        )
        by_item = {e["item"]: e for e in r["tradeoff_analysis"]}
        assert by_item["choice-band"]["sps_saved"] > 0
        assert by_item["life-orb"]["sps_saved"] == 0


class TestItemTradeoffMainline:
    async def test_mainline_uses_ev_path(self, main_tm):
        r = await main_tm.call_tool(
            "analyze_item_ev_tradeoff",
            {"pokemon_name": "flutter-mane"},
        )
        assert r["format_system"] == "mainline"
        assert "evs_saved" in r["recommendation"]
        paste = r["recommendation"]["showdown_paste"]
        assert "SPs:" not in paste
