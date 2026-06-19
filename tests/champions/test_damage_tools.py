"""Tool-level regression tests for the Champions (Reg MA) Stat-Point system in
src/vgc_mcp/tools/damage_tools.py (Agent T3).

These call the ACTUAL registered @mcp.tool functions in a Champions session
(reg_ma_champs) with a fake PokeAPI client, and assert SP-scale output:
  - builds carry format_system='champions' so calc dispatches on SP stats,
  - returned *_showdown_paste lines use 'SPs:' (never an 'EVs:' line),
  - SP-unit keys ('sps_needed' / 'hp_sps_needed' / 'def_sps_needed') replace
    the EV-unit keys for champions, and the mainline path keeps EV keys.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.damage_tools import register_damage_tools
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


# --------------------------------------------------------------------------- #
# Fixtures / helpers
# --------------------------------------------------------------------------- #

_BASE_STATS = {
    "manectric-mega": BaseStats(
        hp=70, attack=75, defense=80,
        special_attack=135, special_defense=80, speed=135,
    ),
    "incineroar": BaseStats(
        hp=95, attack=115, defense=90,
        special_attack=80, special_defense=90, speed=60,
    ),
    "flutter-mane": BaseStats(
        hp=55, attack=55, defense=55,
        special_attack=135, special_defense=135, speed=135,
    ),
    "hydreigon": BaseStats(
        hp=92, attack=105, defense=90,
        special_attack=125, special_defense=90, speed=98,
    ),
    "garchomp": BaseStats(
        hp=108, attack=130, defense=95,
        special_attack=80, special_defense=85, speed=102,
    ),
    "amoonguss": BaseStats(
        hp=114, attack=85, defense=70,
        special_attack=85, special_defense=80, speed=30,
    ),
}
_TYPES = {
    "manectric-mega": ["electric"],
    "incineroar": ["fire", "dark"],
    "flutter-mane": ["ghost", "fairy"],
    "hydreigon": ["dark", "dragon"],
    "garchomp": ["ground", "dragon"],
    "amoonguss": ["grass", "poison"],
}


def _fake_pokeapi(move: Move, abilities=None):
    api = MagicMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n, *a, **k: _BASE_STATS[n])
    api.get_pokemon_types = AsyncMock(side_effect=lambda n, *a, **k: _TYPES[n])
    api.get_pokemon_abilities = AsyncMock(return_value=abilities or ["Intimidate"])
    api.get_move = AsyncMock(return_value=move)
    return api


def _register(pokeapi):
    """Register damage tools against a throwaway FastMCP and capture the fns."""
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
    register_damage_tools(mcp, pokeapi, smogon=None)
    return captured


@pytest.fixture
def champions_session():
    """Force the session to Champions (Reg MA) and clean up afterwards."""
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


def _thunderbolt():
    return Move(
        name="thunderbolt", type="electric", category=MoveCategory.SPECIAL,
        power=90, accuracy=100, target="selected-pokemon",
    )


def _moonblast():
    return Move(
        name="moonblast", type="fairy", category=MoveCategory.SPECIAL,
        power=95, accuracy=100, target="selected-pokemon",
    )


def _close_combat():
    return Move(
        name="close-combat", type="fighting", category=MoveCategory.PHYSICAL,
        power=120, accuracy=100, target="selected-pokemon",
    )


# --------------------------------------------------------------------------- #
# [T3-a] calculate_damage_output
# --------------------------------------------------------------------------- #

class TestCalculateDamageOutputChampions:
    def test_sp_inputs_reach_champions_stats_and_sp_paste(self, champions_session):
        """Mega Manectric 32 SpA / 32 Spe must hit 187 SpA / 205 Spe and the
        attacker paste must use 'SPs:', not 'EVs:'."""
        tools = _register(_fake_pokeapi(_thunderbolt(), abilities=["Intimidate"]))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="manectric-mega",
            defender_name="incineroar",
            move_name="thunderbolt",
            attacker_nature="timid",  # +Spe reaches 205; SpA stays 187
            attacker_sps="0/0/0/32/0/32",
            defender_sps="8/0/0/0/0/0",
            use_smogon_spreads=False,
        ))
        assert "error" not in res
        # 187 SpA / 205 Spe are the saturated champions stats (vs old 155/170).
        assert "187" in res["transparent_output"]
        assert "205" in res["transparent_output"]
        paste = res["attacker_showdown_paste"]
        assert "SPs:" in paste
        assert "EVs:" not in paste
        assert "32 SpA" in paste and "32 Spe" in paste
        # Defender paste is also SP-scale (no EV line).
        assert "EVs:" not in res["defender_showdown_paste"]

    def test_transparent_table_labels_stat_points(self, champions_session):
        tools = _register(_fake_pokeapi(_thunderbolt(), abilities=["Intimidate"]))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="manectric-mega",
            defender_name="incineroar",
            move_name="thunderbolt",
            attacker_sps="0/0/0/32/0/32",
            use_smogon_spreads=False,
        ))
        # The allocation row is labelled SPs, never EVs, for champions builds.
        assert "| SPs  |" in res["transparent_output"]
        assert "| EVs  |" not in res["transparent_output"]

    def test_invalid_sp_string_returns_structured_error(self, champions_session):
        tools = _register(_fake_pokeapi(_thunderbolt()))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="manectric-mega",
            defender_name="incineroar",
            move_name="thunderbolt",
            attacker_sps="0/0/0",  # too few values
            use_smogon_spreads=False,
        ))
        assert "error" in res  # structured error_response, not a raw dict

    def test_over_budget_sp_string_returns_structured_error(self, champions_session):
        """Per-stat cap (32) is enforced by StatPointSpread; tool surfaces it."""
        tools = _register(_fake_pokeapi(_thunderbolt()))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="manectric-mega",
            defender_name="incineroar",
            move_name="thunderbolt",
            attacker_sps="0/0/0/40/0/0",  # 40 > 32 per-stat cap
            use_smogon_spreads=False,
        ))
        assert "error" in res

    def test_mainline_path_unchanged(self, mainline_session):
        """Mainline session still produces an EVs paste (no SPs line)."""
        tools = _register(_fake_pokeapi(_thunderbolt(), abilities=["Intimidate"]))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="manectric-mega",
            defender_name="incineroar",
            move_name="thunderbolt",
            attacker_spa_evs=252,
            attacker_nature="timid",
            defender_hp_evs=4,
            defender_nature="careful",
            use_smogon_spreads=False,
        ))
        assert "SPs:" not in res["attacker_showdown_paste"]
        # Mainline 252 SpA Timid Mega Manectric special_attack = 187 too, but the
        # paste must carry an EVs line, never SPs.
        assert "EVs:" in res["attacker_showdown_paste"]

class TestCalculateDamageOutputChampionsDisplayFields:
    """Auxiliary DISPLAY/summary fields must read the StatPointSpread in a
    Champions session — not the empty EV spread (which used to read as zeros)."""

    def test_display_fields_show_sp_not_zero_evs(self, champions_session):
        tools = _register(_fake_pokeapi(_moonblast(), abilities=["Intimidate"]))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="flutter-mane",
            defender_name="incineroar",
            move_name="moonblast",
            attacker_nature="timid",
            attacker_sps="0/0/0/32/0/32",
            defender_sps="32/0/0/0/8/0",
            use_smogon_spreads=False,
        ))
        assert "error" not in res

        # Top-level attacker_ev_spread: SP allocation, never "0 EVs".
        ev_spread = res["attacker_ev_spread"]
        assert ev_spread == "SPs: 32 SpA / 32 Spe"
        assert "0 EVs" not in ev_spread

        # condensed_summary.attacker_line shows the real SP allocation, not
        # the old "Serious 0/0/0/0/0/0" empty-EV string.
        attacker_line = res["condensed_summary"]["attacker_line"]
        assert "0/0/0/32/0/32 SP" in attacker_line
        assert "0/0/0/0/0/0" not in attacker_line
        # Defender line is SP-scale too.
        assert "SP" in res["condensed_summary"]["defender_line"]

        # analysis text reflects SP investment, not "0 SpA".
        analysis = res["analysis"]
        assert "32 SP SpA" in analysis
        assert "0 SpA flutter-mane" not in analysis

    def test_mainline_display_fields_unchanged(self, mainline_session):
        """Mainline keeps EV-style display fields byte-for-byte (no 'SP' unit)."""
        tools = _register(_fake_pokeapi(_moonblast(), abilities=["Intimidate"]))
        res = asyncio.run(tools["calculate_damage_output"](
            attacker_name="flutter-mane",
            defender_name="incineroar",
            move_name="moonblast",
            attacker_spa_evs=252,
            attacker_nature="timid",
            defender_hp_evs=252,
            defender_def_evs=0,
            defender_nature="careful",
            use_smogon_spreads=False,
        ))
        assert res["attacker_ev_spread"] == "252 SpA"
        assert "SPs:" not in res["attacker_ev_spread"]
        # No "SP" unit leaks into the analysis text on the mainline path.
        assert " SP " not in res["analysis"]
        assert "0/0/0/252/0/0" in res["condensed_summary"]["attacker_line"]


# --------------------------------------------------------------------------- #
# [T3-b] find_survival_evs
# --------------------------------------------------------------------------- #

class TestFindSurvivalEvsChampions:
    def test_returns_sp_units_and_sp_paste(self, champions_session):
        tools = _register(_fake_pokeapi(_close_combat(), abilities=["Rough Skin"]))
        res = asyncio.run(tools["find_survival_evs"](
            attacker_name="garchomp",
            defender_name="amoonguss",
            move_name="close-combat",
            attacker_nature="adamant",
            attacker_evs=32,
            defender_nature="sassy",
            use_smogon_spreads=False,
        ))
        assert res["achievable"] is True
        assert res["units"] == "Stat Points"
        # SP-unit keys present; EV-unit keys absent.
        assert "hp_sps_needed" in res
        assert "def_sps_needed" in res
        assert "hp_evs_needed" not in res
        assert "def_evs_needed" not in res
        assert 0 <= res["hp_sps_needed"] <= 32
        assert 0 <= res["def_sps_needed"] <= 32
        assert res["hp_sps_needed"] + res["def_sps_needed"] <= 66
        # Defender paste is SP-scale: never an EVs line.
        assert "EVs:" not in res["defender_showdown_paste"]

    def test_sp_paste_emitted_when_investment_needed(self, champions_session):
        """A heavy super-effective hit forces real SP investment; the paste then
        carries an explicit 'SPs:' line (never 'EVs:')."""
        # Garchomp Close Combat is super-effective vs Incineroar (Dark) — needs bulk.
        tools = _register(_fake_pokeapi(_close_combat(), abilities=["Rough Skin"]))
        res = asyncio.run(tools["find_survival_evs"](
            attacker_name="garchomp",
            defender_name="incineroar",
            move_name="close-combat",
            attacker_nature="adamant",
            attacker_evs=32,
            defender_nature="careful",
            use_smogon_spreads=False,
        ))
        if res["achievable"] and (res["hp_sps_needed"] or res["def_sps_needed"]):
            assert "SPs:" in res["defender_showdown_paste"]
        assert "EVs:" not in res["defender_showdown_paste"]

    def test_mainline_returns_ev_units(self, mainline_session):
        tools = _register(_fake_pokeapi(_close_combat(), abilities=["Rough Skin"]))
        res = asyncio.run(tools["find_survival_evs"](
            attacker_name="garchomp",
            defender_name="incineroar",
            move_name="close-combat",
            attacker_nature="adamant",
            attacker_evs=252,
            defender_nature="careful",
            use_smogon_spreads=False,
        ))
        if res.get("achievable"):
            assert "hp_evs_needed" in res
            assert "hp_sps_needed" not in res
            assert "SPs:" not in res["defender_showdown_paste"]


# --------------------------------------------------------------------------- #
# [T3-c] find_ko_evs
# --------------------------------------------------------------------------- #

class TestFindKoEvsChampions:
    def test_returns_sps_needed_and_sp_paste(self, champions_session):
        tools = _register(_fake_pokeapi(_moonblast(), abilities=["Protosynthesis"]))
        res = asyncio.run(tools["find_ko_evs"](
            attacker_name="flutter-mane",
            defender_name="hydreigon",  # dark/dragon -> 4x weak to fairy
            move_name="moonblast",
            attacker_nature="modest",
            use_smogon_spreads=False,
        ))
        assert res["achievable"] is True
        assert res["units"] == "Stat Points"
        assert "sps_needed" in res
        assert "evs_needed" not in res
        assert 0 <= res["sps_needed"] <= 32
        assert "EVs:" not in res["attacker_showdown_paste"]

    def test_sp_paste_uses_sps_when_achievable(self, champions_session):
        """When a KO is achievable in a champions session the attacker paste is
        SP-scale (carries 'SPs:' if any SP is needed, never an 'EVs:' line)."""
        tools = _register(_fake_pokeapi(_moonblast(), abilities=["Protosynthesis"]))
        res = asyncio.run(tools["find_ko_evs"](
            attacker_name="flutter-mane",
            defender_name="hydreigon",  # 4x weak — guaranteed achievable
            move_name="moonblast",
            attacker_nature="modest",
            use_smogon_spreads=False,
        ))
        assert res["achievable"] is True
        paste = res["attacker_showdown_paste"]
        assert "EVs:" not in paste
        if res.get("sps_needed"):
            assert "SPs:" in paste

    def test_mainline_returns_evs_needed(self, mainline_session):
        tools = _register(_fake_pokeapi(_moonblast(), abilities=["Protosynthesis"]))
        res = asyncio.run(tools["find_ko_evs"](
            attacker_name="flutter-mane",
            defender_name="hydreigon",
            move_name="moonblast",
            attacker_nature="modest",
            use_smogon_spreads=False,
        ))
        assert res["achievable"] is True
        assert "evs_needed" in res
        assert "sps_needed" not in res
        assert "SPs:" not in res["attacker_showdown_paste"]
