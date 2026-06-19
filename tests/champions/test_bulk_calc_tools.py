"""Tool-level regression tests for the Champions (Reg MA) Stat-Point system in
src/vgc_mcp/tools/bulk_calc_tools.py.

These call the ACTUAL registered @mcp.tool functions in a Champions session
(reg_ma_champs) with a fake PokeAPI client, and assert that:
  - the USER's subject attacker becomes a Stat-Point build (format_system=
    'champions') so calc dispatches on SP-saturated stats,
  - the returned attacker_showdown_paste uses 'SPs:' (never an 'EVs:' line),
  - SP input is accepted via attacker_sps and capped/validated,
  - opposing meta defenders stay MAINLINE,
  - the mainline path is unchanged (EV paste, EV input).
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from mcp.server.fastmcp import FastMCP

from vgc_mcp.tools.bulk_calc_tools import register_bulk_calc_tools
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
    "garchomp": BaseStats(
        hp=108, attack=130, defense=95,
        special_attack=80, special_defense=85, speed=102,
    ),
}
_TYPES = {
    "manectric-mega": ["electric"],
    "incineroar": ["fire", "dark"],
    "garchomp": ["ground", "dragon"],
}


def _thunderbolt():
    return Move(
        name="thunderbolt", type="electric", category=MoveCategory.SPECIAL,
        power=90, accuracy=100, target="selected-pokemon",
    )


def _fake_pokeapi():
    api = MagicMock()
    api.get_base_stats = AsyncMock(side_effect=lambda n, *a, **k: _BASE_STATS[n])
    api.get_pokemon_types = AsyncMock(side_effect=lambda n, *a, **k: _TYPES[n])
    api.get_pokemon_abilities = AsyncMock(return_value=["Intimidate"])
    api.get_move = AsyncMock(side_effect=lambda n, *a, **k: _thunderbolt())
    return api


def _register(pokeapi):
    """Register bulk-calc tools against a throwaway FastMCP and capture the fns."""
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
    register_bulk_calc_tools(mcp, pokeapi, smogon=None)
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
# calculate_bulk_offensive_calcs — champions
# --------------------------------------------------------------------------- #

class TestBulkOffensiveCalcsChampions:
    def test_sp_attacker_paste_and_format(self, champions_session):
        """Mega Manectric 32 SpA / 32 Spe must produce an 'SPs:' paste and a
        champions-tagged attacker; defenders stay mainline."""
        tools = _register(_fake_pokeapi())
        res = asyncio.run(tools["calculate_bulk_offensive_calcs"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar", "garchomp"],
            attacker_nature="timid",
            attacker_sps="0/0/0/32/0/32",
        ))
        assert "error" not in res
        paste = res["attacker"]["attacker_showdown_paste"]
        assert "SPs:" in paste
        assert "EVs:" not in paste
        assert "32 SpA" in paste and "32 Spe" in paste
        assert res["attacker"]["format_system"] == "champions"
        # The reported spread string is SP-scale, not 0/0/0/0 from empty EVs.
        assert "(SPs)" in res["attacker"]["spread"]
        assert res["total_calcs"] == 2

    def test_sp_attacker_reaches_saturated_stats(self, champions_session):
        """Damage must reflect 187 SpA (saturated SP stat), not the 0-investment
        stat. We compare 32 SpA against 0 SpA — the former must hit harder."""
        tools = _register(_fake_pokeapi())
        invested = asyncio.run(tools["calculate_bulk_offensive_calcs"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar"],
            attacker_nature="timid",
            attacker_sps="0/0/0/32/0/32",
        ))
        none = asyncio.run(tools["calculate_bulk_offensive_calcs"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar"],
            attacker_nature="timid",
            attacker_sps="0/0/0/0/0/0",
        ))
        inv_pct = invested["results_by_defender"]["incineroar"]["thunderbolt"]["normal"]["damage_pct"]
        none_pct = none["results_by_defender"]["incineroar"]["thunderbolt"]["normal"]["damage_pct"]
        inv_max = float(inv_pct.split("-")[1].rstrip("%"))
        none_max = float(none_pct.split("-")[1].rstrip("%"))
        assert inv_max > none_max

    def test_invalid_sp_string_returns_structured_error(self, champions_session):
        tools = _register(_fake_pokeapi())
        res = asyncio.run(tools["calculate_bulk_offensive_calcs"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar"],
            attacker_nature="timid",
            attacker_sps="32/32",  # only two values
        ))
        assert "error" in res

    def test_sp_over_cap_rejected(self, champions_session):
        """A per-stat value above 32 violates the StatPointSpread cap and must
        surface as a structured error, not a wrong build."""
        tools = _register(_fake_pokeapi())
        res = asyncio.run(tools["calculate_bulk_offensive_calcs"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar"],
            attacker_nature="timid",
            attacker_sps="0/0/0/40/0/32",
        ))
        assert "error" in res


# --------------------------------------------------------------------------- #
# mainline path unchanged
# --------------------------------------------------------------------------- #

class TestBulkOffensiveCalcsMainline:
    def test_mainline_uses_ev_paste(self, mainline_session):
        tools = _register(_fake_pokeapi())
        res = asyncio.run(tools["calculate_bulk_offensive_calcs"](
            attacker_name="garchomp",
            move_names=["thunderbolt"],
            defender_names=["incineroar"],
            attacker_nature="jolly",
            attacker_evs="4/252/0/0/0/252",
        ))
        assert "error" not in res
        paste = res["attacker"]["attacker_showdown_paste"]
        assert "EVs:" in paste
        assert "SPs:" not in paste
        assert res["attacker"]["format_system"] == "mainline"


# --------------------------------------------------------------------------- #
# export_damage_report — champions
# --------------------------------------------------------------------------- #

class TestExportDamageReportChampions:
    def test_champions_attacker_builds_and_exports(self, champions_session, tmp_path):
        tools = _register(_fake_pokeapi())
        out = tmp_path / "report.xlsx"
        res = asyncio.run(tools["export_damage_report"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar", "garchomp"],
            format="excel",
            attacker_nature="timid",
            attacker_sps="0/0/0/32/0/32",
            output_path=str(out),
        ))
        assert "error" not in res
        assert res["total_calcs"] == 2
        assert out.exists()

    def test_export_invalid_sp_string_errors(self, champions_session, tmp_path):
        tools = _register(_fake_pokeapi())
        res = asyncio.run(tools["export_damage_report"](
            attacker_name="manectric-mega",
            move_names=["thunderbolt"],
            defender_names=["incineroar"],
            format="excel",
            attacker_nature="timid",
            attacker_sps="bad",
            output_path=str(tmp_path / "r.xlsx"),
        ))
        assert "error" in res
