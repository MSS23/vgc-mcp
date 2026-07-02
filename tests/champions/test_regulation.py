"""Tests for Reg MA Champions regulation config."""

import pytest

from vgc_mcp_core.rules.regulation_loader import RegulationConfig


@pytest.fixture
def cfg():
    # Use a fresh instance, not the global singleton, to avoid polluting state.
    return RegulationConfig()


def test_reg_ma_present(cfg):
    assert "reg_ma_champs" in cfg.list_regulation_codes()


def test_reg_ma_format_system_is_champions(cfg):
    assert cfg.get_format_system("reg_ma_champs") == "champions"


def test_other_regs_remain_mainline(cfg):
    # Pre-existing regs must keep defaulting to mainline.
    for reg in ["reg_f", "reg_g", "reg_h"]:
        assert cfg.get_format_system(reg) == "mainline"


def test_reg_ma_sp_limits(cfg):
    limits = cfg.get_sp_limits("reg_ma_champs")
    assert limits == {"per_stat_max": 32, "total_max": 66}


def test_reg_ma_default_smogon_rating_is_1500(cfg):
    assert cfg.get_default_smogon_rating("reg_ma_champs") == 1500


def test_mainline_default_smogon_rating_is_1500(cfg):
    # All regs (mainline + champions) standardize on 1500 so cross-format
    # usage comparisons are apples-to-apples.
    assert cfg.get_default_smogon_rating("reg_f") == 1500
    assert cfg.get_default_smogon_rating("reg_g") == 1500
    assert cfg.get_default_smogon_rating("reg_h") == 1500


def test_reg_ma_uses_allowlist(cfg):
    assert cfg.get_legality_mode("reg_ma_champs") == "allowlist"


def test_mainline_uses_banlist(cfg):
    assert cfg.get_legality_mode("reg_f") == "banlist"


def test_garchomp_legal_in_reg_ma(cfg):
    assert cfg.is_pokemon_legal("garchomp", "reg_ma_champs") is True


def test_calyrex_shadow_rider_illegal_in_reg_ma(cfg):
    assert cfg.is_pokemon_legal("calyrex-shadow-rider", "reg_ma_champs") is False


def test_iron_hands_illegal_in_reg_ma(cfg):
    # Paradox Pokemon are not in the Reg MA allowlist
    assert cfg.is_pokemon_legal("iron-hands", "reg_ma_champs") is False


def test_legal_pokemon_list_is_populated(cfg):
    legal = cfg.get_legal_pokemon("reg_ma_champs")
    assert len(legal) > 100  # Reg MA has 168 legal Pokemon
    assert "garchomp" in legal
    assert "incineroar" in legal
    assert "dragapult" in legal


def test_reg_ma_smogon_format(cfg):
    formats = cfg.get_smogon_formats("reg_ma_champs")
    assert "gen9championsvgc2026regma" in formats


# --- Regression: allowlist legality fallbacks (F1-c) ---


def test_reg_ma_mega_form_legal_via_base(cfg):
    # 'manectric-mega' / 'Mega Manectric' resolve legal because base
    # 'manectric' is allowlisted; do NOT require fake Mega entries in JSON.
    assert cfg.is_pokemon_legal("manectric-mega", "reg_ma_champs")
    assert cfg.is_pokemon_legal("Mega Manectric", "reg_ma_champs")


def test_reg_ma_regional_and_rotom_forms_legal_via_base(cfg):
    assert cfg.is_pokemon_legal("rotom-wash", "reg_ma_champs")
    assert cfg.is_pokemon_legal("tauros-paldea-aqua", "reg_ma_champs")


def test_reg_ma_absent_species_stay_illegal(cfg):
    for name in ["urshifu", "ogerpon", "indeedee"]:
        assert not cfg.is_pokemon_legal(name, "reg_ma_champs"), name


# --- Regression: restricted.py allowlist awareness (F1-e) ---

from vgc_mcp_core.rules.restricted import (  # noqa: E402
    get_pokemon_legality,
    get_restricted_status,
)


def test_restricted_status_offlist_mon_is_illegal():
    # flutter-mane is NOT on the Reg MA allowlist -> 'illegal', not 'allowed'.
    assert get_restricted_status("flutter-mane", "reg_ma_champs") == "illegal"
    legality = get_pokemon_legality("flutter-mane", "reg_ma_champs")
    assert legality["status"] == "illegal"
    assert legality["can_use"] is False


def test_restricted_status_onlist_mons_allowed():
    assert get_restricted_status("incineroar", "reg_ma_champs") == "allowed"
    assert get_restricted_status("pikachu", "reg_ma_champs") == "allowed"
