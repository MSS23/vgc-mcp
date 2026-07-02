"""Tool-level regression tests for Champions (Reg MA) support in the meta-threat
and multi-threat tool layer:
  - src/vgc_mcp/tools/meta_threat_tools.py
  - src/vgc_mcp/tools/multi_threat_tools.py

These call the ACTUAL registered @mcp.tool functions in a Champions session
(reg_ma_champs) with fake clients and assert SP-scale output:
  - the USER'S subject build is format_system='champions' (saturated SP stats),
  - returned *showdown_paste lines use 'SPs:' (never an 'EVs:' line),
  - SP-unit keys (minimum_sps / hp_sps / def_sps / total_sps) replace EV keys,
  - opposing meta threats stay mainline, and the mainline path is unchanged.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.meta_threat_tools import register_meta_threat_tools
from vgc_mcp.tools.multi_threat_tools import register_multi_threat_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config

_BASE = {
    "garchomp": BaseStats(hp=108, attack=130, defense=95,
                          special_attack=80, special_defense=85, speed=102),
    "amoonguss": BaseStats(hp=114, attack=85, defense=70,
                           special_attack=85, special_defense=80, speed=30),
    "flutter-mane": BaseStats(hp=55, attack=55, defense=55,
                              special_attack=135, special_defense=135, speed=135),
}
_TYPES = {
    "garchomp": ["ground", "dragon"],
    "amoonguss": ["grass", "poison"],
    "flutter-mane": ["ghost", "fairy"],
}


def _moonblast():
    return Move(name="moonblast", type="fairy", category=MoveCategory.SPECIAL,
                power=95, accuracy=100, target="selected-pokemon")


def _close_combat():
    return Move(name="close-combat", type="fighting", category=MoveCategory.PHYSICAL,
                power=120, accuracy=100, target="selected-pokemon")


def _fake_pokeapi(move: Move, abilities=None):
    api = MagicMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n, *a, **k: _BASE[n])
    api.get_pokemon_types = AsyncMock(side_effect=lambda n, *a, **k: _TYPES[n])
    api.get_pokemon_abilities = AsyncMock(return_value=abilities or ["Overcoat"])
    api.get_move = AsyncMock(return_value=move)
    return api


def _fake_smogon():
    s = MagicMock()
    s.get_pokemon_usage = AsyncMock(return_value=None)
    s.get_usage_stats = AsyncMock(return_value={"_meta": {}, "data": {}})
    return s


def _register_meta(pokeapi, smogon):
    mcp = FastMCP("test")
    captured = {}
    orig = mcp.tool

    def patched(*a, **k):
        decorator = orig(*a, **k)

        def wrap(fn):
            captured[fn.__name__] = fn
            return decorator(fn)

        return wrap

    mcp.tool = patched
    register_meta_threat_tools(mcp, smogon, pokeapi, MagicMock())
    return captured


def _register_multi(pokeapi):
    mcp = FastMCP("test")
    captured = {}
    orig = mcp.tool

    def patched(*a, **k):
        decorator = orig(*a, **k)

        def wrap(fn):
            captured[fn.__name__] = fn
            return decorator(fn)

        return wrap

    mcp.tool = patched
    register_multi_threat_tools(mcp, pokeapi, None)
    return captured


@pytest.fixture
def champions_session():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_ma_champs")
    try:
        yield cfg
    finally:
        cfg.clear_session_override()


@pytest.fixture
def mainline_session():
    cfg = get_regulation_config()
    cfg.set_session_regulation("reg_h")
    try:
        yield cfg
    finally:
        cfg.clear_session_override()


# --------------------------------------------------------------------------- #
# analyze_spread_vs_threats
# --------------------------------------------------------------------------- #

class TestAnalyzeSpreadVsThreatsChampions:
    def test_subject_is_champions_with_sp_paste(self, champions_session):
        tools = _register_meta(_fake_pokeapi(_moonblast()), _fake_smogon())
        res = asyncio.run(tools["analyze_spread_vs_threats"](
            pokemon_name="garchomp",
            nature="adamant",
            hp_evs=4, atk_evs=252, spe_evs=252,
        ))
        assert "error" not in res
        assert res["spread"]["format_system"] == "champions"
        sps = res["spread"]["sps"]
        assert all(0 <= v <= 32 for v in sps.values())
        assert sps["attack"] == 32 and sps["speed"] == 32
        assert "SPs:" in res["showdown_paste"]
        assert "EVs:" not in res["showdown_paste"]

    def test_mainline_unchanged(self, mainline_session):
        tools = _register_meta(_fake_pokeapi(_moonblast()), _fake_smogon())
        res = asyncio.run(tools["analyze_spread_vs_threats"](
            pokemon_name="garchomp",
            nature="adamant",
            hp_evs=4, atk_evs=252, spe_evs=252,
        ))
        assert "format_system" not in res["spread"]
        assert res["spread"]["attack"] == 252
        assert "SPs:" not in res["showdown_paste"]
        assert "EVs:" in res["showdown_paste"]


# --------------------------------------------------------------------------- #
# check_survival_benchmark
# --------------------------------------------------------------------------- #

class TestCheckSurvivalBenchmarkChampions:
    def test_subject_sp_paste(self, champions_session):
        tools = _register_meta(_fake_pokeapi(_moonblast()), _fake_smogon())
        res = asyncio.run(tools["check_survival_benchmark"](
            pokemon_name="garchomp", nature="careful",
            hp_evs=252, def_evs=0, spd_evs=252,
            threat_pokemon="flutter-mane", threat_move="moonblast",
            survival_threshold=93.75,
        ))
        assert res["format_system"] == "champions"
        assert "SPs:" in res["showdown_paste"]
        assert "EVs:" not in res["showdown_paste"]

    def test_mainline_unchanged(self, mainline_session):
        tools = _register_meta(_fake_pokeapi(_moonblast()), _fake_smogon())
        res = asyncio.run(tools["check_survival_benchmark"](
            pokemon_name="garchomp", nature="careful",
            hp_evs=252, def_evs=0, spd_evs=252,
            threat_pokemon="flutter-mane", threat_move="moonblast",
            survival_threshold=93.75,
        ))
        assert res["format_system"] == "mainline"
        assert "SPs:" not in res["showdown_paste"]


# --------------------------------------------------------------------------- #
# find_survival_evs_meta
# --------------------------------------------------------------------------- #

class TestFindSurvivalEvsMetaChampions:
    def test_sp_units_and_caps(self, champions_session):
        # Garchomp (Dragon, 4x weak to Fairy) needs real SP to live Moonblast.
        tools = _register_meta(_fake_pokeapi(_moonblast()), _fake_smogon())
        res = asyncio.run(tools["find_survival_evs_meta"](
            pokemon_name="garchomp", nature="careful",
            threat_pokemon="flutter-mane", threat_move="moonblast",
            survival_threshold=93.75,
        ))
        if res.get("impossible"):
            assert res["units"] == "Stat Points"
            return
        assert res["format_system"] == "champions"
        assert res["units"] == "Stat Points"
        ms = res["minimum_sps"]
        assert "minimum_evs" not in res
        assert 0 <= ms["hp_sps"] <= 32
        assert 0 <= ms["spd_sps"] <= 32
        assert ms["total_sps"] <= 66
        assert "EVs:" not in res["showdown_paste"]
        if ms["total_sps"]:
            assert "SPs:" in res["showdown_paste"]

    def test_mainline_returns_ev_units(self, mainline_session):
        tools = _register_meta(_fake_pokeapi(_moonblast()), _fake_smogon())
        res = asyncio.run(tools["find_survival_evs_meta"](
            pokemon_name="garchomp", nature="careful",
            threat_pokemon="flutter-mane", threat_move="moonblast",
            survival_threshold=93.75,
        ))
        if not res.get("impossible"):
            assert "minimum_evs" in res
            assert "minimum_sps" not in res
            assert "SPs:" not in res.get("showdown_paste", "")


# --------------------------------------------------------------------------- #
# find_multi_threat_bulk_evs
# --------------------------------------------------------------------------- #

class TestFindMultiThreatBulkEvsChampions:
    def test_sp_units_and_caps(self, champions_session):
        tools = _register_multi(_fake_pokeapi(_close_combat()))
        res = asyncio.run(tools["find_multi_threat_bulk_evs"](
            pokemon_name="amoonguss", nature="calm",
            threats=[{"name": "garchomp", "move": "close-combat",
                      "spread": {"nature": "adamant", "evs": {"attack": 252}}}],
            target_survival_chance=93.75,
        ))
        assert "error" not in res
        assert res["format_system"] == "champions"
        assert res["units"] == "Stat Points"
        rs = res["recommended_spread"]
        assert "hp_sps" in rs and "hp_evs" not in rs
        assert rs["total_sps"] <= 66
        assert rs["hp_sps"] <= 32 and rs["def_sps"] <= 32 and rs["spd_sps"] <= 32
        assert "/66" in res["markdown_summary"]
        assert "EVs:" not in res["showdown_paste"]

    def test_mainline_unchanged(self, mainline_session):
        tools = _register_multi(_fake_pokeapi(_close_combat()))
        res = asyncio.run(tools["find_multi_threat_bulk_evs"](
            pokemon_name="amoonguss", nature="calm",
            threats=[{"name": "garchomp", "move": "close-combat",
                      "spread": {"nature": "adamant", "evs": {"attack": 252}}}],
            target_survival_chance=93.75,
        ))
        assert res["format_system"] == "mainline"
        rs = res["recommended_spread"]
        assert "hp_evs" in rs and "hp_sps" not in rs
        assert "/508" in res["markdown_summary"]
        assert "SPs:" not in res["showdown_paste"]
