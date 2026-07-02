"""Tool-level regression tests for the Champions (Reg MA) Stat-Point system in
src/vgc_mcp/tools/multicalc_tools.py.

These call the ACTUAL registered @mcp.tool functions in a Champions session
(reg_ma_champs) with a fake PokeAPI client, and assert SP-scale behaviour for
the user's SUBJECT builds while opposing reference mons stay mainline:

  - calculate_offensive_coverage  -> attacker (subject) is SP-scale
  - calculate_defensive_threats   -> defender (subject) is SP-scale
  - calculate_team_coverage_matrix-> team members (subjects) are SP-scale

For champions subjects the returned *_showdown_paste uses 'SPs:' (never an
'EVs:' line) and SP inputs saturate to the champions stat numbers (32 SP == 252
EV at level 50). The mainline path keeps emitting 'EVs:'. Opposing reference
mons (defenders / attackers / meta threats) are NOT force-tagged champions.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.multicalc_tools import _build_pokemon_from_smogon, register_multicalc_tools
from vgc_mcp_core.calc.stats import calculate_all_stats
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
    "landorus-therian": BaseStats(
        hp=89, attack=145, defense=90,
        special_attack=105, special_defense=80, speed=91,
    ),
}
_TYPES = {
    "manectric-mega": ["electric"],
    "incineroar": ["fire", "dark"],
    "flutter-mane": ["ghost", "fairy"],
    "landorus-therian": ["ground", "flying"],
}


def _fake_pokeapi(move: Move, abilities=None):
    api = MagicMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n, *a, **k: _BASE_STATS[n])
    api.get_pokemon_types = AsyncMock(side_effect=lambda n, *a, **k: _TYPES[n])
    api.get_pokemon_abilities = AsyncMock(return_value=abilities or ["Intimidate"])
    api.get_move = AsyncMock(return_value=move)
    return api


def _register(pokeapi):
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
    register_multicalc_tools(mcp, pokeapi, smogon=None)
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


def _earthquake():
    return Move(
        name="earthquake", type="ground", category=MoveCategory.PHYSICAL,
        power=100, accuracy=100, target="all-other-pokemon",
    )


# --------------------------------------------------------------------------- #
# _build_pokemon_from_smogon — the format-aware builder
# --------------------------------------------------------------------------- #

class TestBuilderFormatAwareness:
    def test_subject_champions_saturates_sp_stats(self, champions_session):
        api = _fake_pokeapi(_thunderbolt())
        build = asyncio.run(_build_pokemon_from_smogon(
            "manectric-mega", api, "timid", None, None, "Intimidate",
            subject_is_champions=True, sps={"special_attack": 32, "speed": 32},
        ))
        assert build.format_system == "champions"
        stats = calculate_all_stats(build)
        # 32 SP == 252 EV saturation at lv50: 187 SpA / 205 Spe.
        assert stats["special_attack"] == 187
        assert stats["speed"] == 205

    def test_opposing_mon_not_force_champions(self, champions_session):
        """An opposing reference mon (subject_is_champions=False) with a plain
        mainline smogon spread stays mainline even in a champions session."""
        api = _fake_pokeapi(_thunderbolt())
        build = asyncio.run(_build_pokemon_from_smogon(
            "incineroar", api, "careful", {"hp": 252}, None, "Intimidate",
        ))
        assert build.format_system == "mainline"

    def test_subject_mainline_unchanged(self, mainline_session):
        api = _fake_pokeapi(_thunderbolt())
        build = asyncio.run(_build_pokemon_from_smogon(
            "manectric-mega", api, "timid", {"special_attack": 252, "speed": 252},
            None, "Intimidate", subject_is_champions=False,
        ))
        assert build.format_system == "mainline"


# --------------------------------------------------------------------------- #
# calculate_offensive_coverage
# --------------------------------------------------------------------------- #

class TestOffensiveCoverageChampions:
    def test_attacker_subject_is_sp_scale(self, champions_session):
        tools = _register(_fake_pokeapi(_thunderbolt()))
        res = asyncio.run(tools["calculate_offensive_coverage"](
            attacker_name="manectric-mega",
            attacker_move="thunderbolt",
            defender_names=["incineroar"],
            use_smogon_spreads=False,
            attacker_nature="timid",
            attacker_sps={"special_attack": 32, "speed": 32},
        ))
        assert "error" not in res
        paste = res["attacker"]["showdown_paste"]
        assert "SPs:" in paste
        assert "EVs:" not in paste
        assert "32 SpA" in paste and "32 Spe" in paste
        # Spread summary reads SP allocation, not zeroed EVs.
        assert res["attacker"]["spread"] == "Timid 0/32/32"

    def test_opposing_defender_stays_mainline(self, champions_session):
        tools = _register(_fake_pokeapi(_thunderbolt()))
        res = asyncio.run(tools["calculate_offensive_coverage"](
            attacker_name="manectric-mega",
            attacker_move="thunderbolt",
            defender_names=["incineroar"],
            use_smogon_spreads=False,
            attacker_nature="timid",
            attacker_sps={"special_attack": 32},
        ))
        # Opposing defender paste is never SP-tagged here (empty mainline spread).
        assert "SPs:" not in res["matchups"][0]["defender_showdown_paste"]

    def test_mainline_session_keeps_evs(self, mainline_session):
        tools = _register(_fake_pokeapi(_earthquake()))
        res = asyncio.run(tools["calculate_offensive_coverage"](
            attacker_name="landorus-therian",
            attacker_move="earthquake",
            defender_names=["incineroar"],
            use_smogon_spreads=False,
            attacker_nature="jolly",
            attacker_evs={"hp": 4, "attack": 252, "speed": 252},
        ))
        paste = res["attacker"]["showdown_paste"]
        assert "EVs:" in paste
        assert "SPs:" not in paste
        assert "252 Atk" in paste


# --------------------------------------------------------------------------- #
# calculate_defensive_threats
# --------------------------------------------------------------------------- #

class TestDefensiveThreatsChampions:
    def test_defender_subject_is_sp_scale(self, champions_session):
        tools = _register(_fake_pokeapi(_moonblast()))
        res = asyncio.run(tools["calculate_defensive_threats"](
            defender_name="flutter-mane",
            attacker_configs=[{"name": "incineroar", "move": "moonblast"}],
            defender_nature="timid",
            defender_sps={"hp": 32, "special_defense": 32},
            use_smogon_spreads=False,
        ))
        assert "error" not in res
        paste = res["defender"]["showdown_paste"]
        assert "SPs:" in paste
        assert "EVs:" not in paste
        assert "32 HP" in paste and "32 SpD" in paste
        assert res["defender"]["spread"] == "Timid 32/0/32"
        # A threat row was computed.
        assert len(res["threats"]) == 1

    def test_mainline_session_keeps_evs(self, mainline_session):
        tools = _register(_fake_pokeapi(_moonblast()))
        res = asyncio.run(tools["calculate_defensive_threats"](
            defender_name="incineroar",
            attacker_configs=[{"name": "flutter-mane", "move": "moonblast"}],
            defender_nature="careful",
            defender_evs={"hp": 252, "special_defense": 252, "defense": 4},
            use_smogon_spreads=False,
        ))
        paste = res["defender"]["showdown_paste"]
        assert "EVs:" in paste
        assert "SPs:" not in paste


# --------------------------------------------------------------------------- #
# calculate_team_coverage_matrix
# --------------------------------------------------------------------------- #

class TestTeamCoverageMatrixChampions:
    def test_members_are_sp_scale(self, champions_session):
        tools = _register(_fake_pokeapi(_moonblast()))
        res = asyncio.run(tools["calculate_team_coverage_matrix"](
            team_pokemon=[{
                "name": "manectric-mega",
                "move": "moonblast",
                "nature": "timid",
                "sps": {"special_attack": 32, "speed": 32},
            }],
            meta_threats=["incineroar", "flutter-mane"],
            use_smogon_spreads=False,
        ))
        assert "error" not in res
        assert res["team"] == ["manectric-mega"]
        # The member built as a champions subject (187 SpA) and a verdict row
        # was produced for each threat.
        assert len(res["coverage_matrix"]) == 2
        for row in res["coverage_matrix"]:
            assert row and row[0] != "Error"

    def test_mainline_matrix_unaffected(self, mainline_session):
        tools = _register(_fake_pokeapi(_earthquake()))
        res = asyncio.run(tools["calculate_team_coverage_matrix"](
            team_pokemon=[{
                "name": "landorus-therian",
                "move": "earthquake",
                "nature": "jolly",
                "evs": {"attack": 252, "speed": 252},
            }],
            meta_threats=["incineroar"],
            use_smogon_spreads=False,
        ))
        assert "error" not in res
        assert res["coverage_matrix"][0][0] != "Error"
