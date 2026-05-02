"""Tests for the zero-config regulation auto-detection.

These exercise the workflow where a user mentions a Pokemon and the server
flips into the right regulation/format system without any explicit
"use Champions" / "set regulation X" command.
"""

import pytest

from vgc_mcp_core.models.pokemon import BaseStats, Nature, PokemonBuild
from vgc_mcp_core.rules.regulation_loader import RegulationConfig
from vgc_mcp_core.rules.regulation_router import auto_detect_regulation
from vgc_mcp_core.team.manager import TeamManager


@pytest.fixture
def cfg():
    return RegulationConfig()


def test_mega_mention_auto_sets_champions(cfg):
    assert not cfg.session_set_explicitly
    result = auto_detect_regulation(["Mega Manectric", "Garchomp"], cfg)
    assert result["action"] == "set"
    assert result["regulation"] == "reg_ma_champs"
    assert cfg.current_regulation == "reg_ma_champs"
    assert cfg.get_format_system() == "champions"


def test_explicit_set_blocks_subsequent_auto_detect(cfg):
    # User explicitly picked Reg F; a later Mega mention must NOT override it.
    cfg.set_session_regulation("reg_f", by_user=True)
    assert cfg.session_set_explicitly is True

    result = auto_detect_regulation(["Mega Manectric"], cfg)
    assert result["action"] == "skipped"
    assert cfg.current_regulation == "reg_f"
    assert cfg.get_format_system() == "mainline"


def test_one_restricted_auto_sets_reg_g(cfg):
    result = auto_detect_regulation(["Kyogre", "Incineroar", "Amoonguss"], cfg)
    assert result["action"] == "set"
    assert result["regulation"] == "reg_g"
    assert cfg.current_regulation == "reg_g"


def test_two_restricteds_auto_set_reg_i(cfg):
    result = auto_detect_regulation(
        ["Calyrex-Shadow-Rider", "Koraidon", "Urshifu-Rapid-Strike"], cfg
    )
    assert result["action"] == "set"
    assert result["regulation"] == "reg_i"
    assert cfg.current_regulation == "reg_i"


def test_team_manager_auto_detects_on_add():
    """Adding a Pokemon to the team triggers auto-detection and surfaces it."""
    cfg = RegulationConfig()
    cfg.clear_session_override()  # ensure clean state

    tm = TeamManager()
    pb = PokemonBuild(
        name="manectric-mega",
        base_stats=BaseStats(
            hp=70, attack=75, defense=80,
            special_attack=135, special_defense=80, speed=135,
        ),
        nature=Nature.TIMID,
        ability="Intimidate",
    )
    success, _msg, data = tm.add_pokemon(pb)
    assert success
    auto = data.get("regulation_auto_detected")
    assert auto is not None, "TeamManager should surface auto-detected regulation"
    assert auto["regulation"] == "reg_ma_champs"
    assert auto["format_system"] == "champions"
    assert auto["stat_units"] == "Stat Points (SPs)"
    assert auto["confidence"] == "high"


def test_auto_detect_records_result_on_config(cfg):
    auto_detect_regulation(["Mega Salamence"], cfg)
    last = cfg.last_auto_detection
    assert last is not None
    assert last["regulation"] == "reg_ma_champs"
    assert last["action"] == "set"


def test_clear_session_override_resets_auto_detect_flag(cfg):
    cfg.set_session_regulation("reg_f", by_user=True)
    assert cfg.session_set_explicitly

    cfg.clear_session_override()
    assert not cfg.session_set_explicitly
    assert cfg.last_auto_detection is None
