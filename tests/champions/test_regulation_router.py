"""Tests for the wording-based regulation router."""

import pytest

from vgc_mcp_core.rules.regulation_loader import RegulationConfig
from vgc_mcp_core.rules.regulation_router import (
    describe_regulation,
    resolve_regulation,
)


@pytest.fixture
def cfg():
    return RegulationConfig()


@pytest.mark.parametrize(
    "phrase",
    [
        "Reg F",
        "reg_f",
        "regulation F",
        "regulation_f",
        "F",
        " f ",
        "REG-F",
    ],
)
def test_reg_f_phrasings(cfg, phrase):
    assert resolve_regulation(phrase, cfg) == "reg_f"


@pytest.mark.parametrize(
    "phrase",
    [
        "Reg G",
        "reg_g",
        "regulation G",
        "G",
    ],
)
def test_reg_g_phrasings(cfg, phrase):
    assert resolve_regulation(phrase, cfg) == "reg_g"


@pytest.mark.parametrize(
    "phrase",
    [
        "Reg H",
        "reg_h",
        "regulation H",
        "H",
    ],
)
def test_reg_h_phrasings(cfg, phrase):
    assert resolve_regulation(phrase, cfg) == "reg_h"


@pytest.mark.parametrize(
    "phrase",
    [
        # Generic Champions phrasing now resolves to the current default reg (MB).
        "Champions",
        "champions",
        "Pokemon Champions",
        "pokemon champions",
        "champs",
        "NCP",
        "gen 10",
    ],
)
def test_generic_champions_phrasings_default_to_mb(cfg, phrase):
    assert resolve_regulation(phrase, cfg) == "reg_mb_champs"


@pytest.mark.parametrize(
    "phrase",
    [
        "Reg MA",
        "regulation MA",
        "regulation M-A",
        "MA",
        "M-A",
        "ma",
        "Champions Reg MA",
    ],
)
def test_reg_ma_explicit_phrasings(cfg, phrase):
    # MA stays reachable only via explicit MA wording.
    assert resolve_regulation(phrase, cfg) == "reg_ma_champs"


@pytest.mark.parametrize(
    "phrase",
    [
        "Reg MB",
        "regulation MB",
        "regulation M-B",
        "MB",
        "M-B",
        "mb",
        "Champions Reg MB",
    ],
)
def test_reg_mb_explicit_phrasings(cfg, phrase):
    assert resolve_regulation(phrase, cfg) == "reg_mb_champs"


def test_unknown_phrasing_returns_none(cfg):
    assert resolve_regulation("regulation Z", cfg) is None
    assert resolve_regulation("totally bogus", cfg) is None
    assert resolve_regulation("", cfg) is None


def test_reg_i_resolves_now_that_it_exists(cfg):
    # reg_i was promoted to a real regulation (2-restrict format) — these
    # phrasings should now resolve. If reg_i is ever removed from JSON, this
    # test must be reverted to assert None.
    assert "reg_i" in cfg.list_regulation_codes()
    assert resolve_regulation("Reg I", cfg) == "reg_i"
    assert resolve_regulation("I", cfg) == "reg_i"


def test_describe_mainline(cfg):
    info = describe_regulation("reg_f", cfg)
    assert info["format_system"] == "mainline"
    assert info["stat_units"] == "EVs"
    assert info["max_per_stat"] == 252
    assert info["max_total"] == 508


def test_describe_champions(cfg):
    info = describe_regulation("reg_ma_champs", cfg)
    assert info["format_system"] == "champions"
    assert info["stat_units"] == "Stat Points (SPs)"
    assert info["max_per_stat"] == 32
    assert info["max_total"] == 66
    assert info["legality_mode"] == "allowlist"
    assert info["default_smogon_rating"] == 1630
    assert "gen9championsvgc2026regma" in info["smogon_formats"]


def test_describe_champions_mb(cfg):
    info = describe_regulation("reg_mb_champs", cfg)
    assert info["format_system"] == "champions"
    assert info["stat_units"] == "Stat Points (SPs)"
    assert info["max_per_stat"] == 32
    assert info["max_total"] == 66
    assert info["legality_mode"] == "allowlist"
    assert info["default_smogon_rating"] == 1630
    assert "gen9championsvgc2026regmb" in info["smogon_formats"]


def test_mb_is_superset_of_ma(cfg):
    ma = set(cfg.get_legal_pokemon("reg_ma_champs"))
    mb = set(cfg.get_legal_pokemon("reg_mb_champs"))
    assert ma.issubset(mb)
    # MB adds the Reg MB species (e.g. Gholdengo, Annihilape, Metagross).
    assert {"gholdengo", "annihilape", "metagross"}.issubset(mb)
    assert not ({"gholdengo", "annihilape", "metagross"} & ma)


def test_session_set_via_phrasing(cfg):
    # End-to-end: phrase -> resolve -> set_session_regulation -> verify.
    # Generic "Champions" now defaults to MB.
    code = resolve_regulation("Pokemon Champions", cfg)
    assert code == "reg_mb_champs"
    assert cfg.set_session_regulation(code) is True
    assert cfg.current_regulation == "reg_mb_champs"
    assert cfg.get_format_system() == "champions"

    cfg.clear_session_override()
    code = resolve_regulation("Reg F", cfg)
    assert code == "reg_f"
    assert cfg.set_session_regulation(code) is True
    assert cfg.get_format_system() == "mainline"


# --- Regression: base-form-aware restricted detection (F1-d) ---

from vgc_mcp_core.rules.regulation_router import infer_format_from_pokemon  # noqa: E402


def test_infer_short_form_restricteds_route_to_reg_i(cfg):
    # 'Calyrex-Shadow' (short form) must match the restricted-list key
    # 'calyrex-shadow-rider'. Two restricteds -> reg_i, not reg_g.
    result = infer_format_from_pokemon(["Calyrex-Shadow", "Koraidon"], cfg)
    assert result["regulation"] == "reg_i"
    assert "calyrex-shadow" in result["restricted_seen"]
    assert "koraidon" in result["restricted_seen"]
    assert len(result["restricted_seen"]) == 2


def test_infer_calyrex_ice_short_form_counted(cfg):
    result = infer_format_from_pokemon(["Calyrex-Ice", "Miraidon"], cfg)
    assert result["regulation"] == "reg_i"
    assert len(result["restricted_seen"]) == 2
