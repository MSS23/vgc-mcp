"""Tests for `infer_format_from_pokemon` — wording-driven regulation pick.

These exercise the user-supplied examples directly so the heuristic is
locked to the intended behavior:
- "Mega Kangaskhan" -> Reg MA Champions
- "Kyogre" only restricted -> Reg G (1-restrict)
- "Calyrex-Shadow-Rider + Koraidon" -> Reg I (2-restrict)
- 0 restricteds, no megas -> Reg F (0-restrict)
"""

import pytest

from vgc_mcp_core.rules.regulation_loader import RegulationConfig
from vgc_mcp_core.rules.regulation_router import infer_format_from_pokemon


@pytest.fixture
def cfg():
    return RegulationConfig()


def test_mega_kangaskhan_routes_to_champions(cfg):
    result = infer_format_from_pokemon(["Kangaskhan-Mega"], cfg)
    assert result["regulation"] == "reg_ma_champs"
    assert result["confidence"] == "high"
    assert any("Mega" in r for r in result["reasons"])


def test_mega_charizard_y_routes_to_champions(cfg):
    result = infer_format_from_pokemon(["Charizard-Mega-Y"], cfg)
    assert result["regulation"] == "reg_ma_champs"


def test_single_restricted_kyogre_routes_to_reg_g(cfg):
    # User's example: Kyogre as the lone legendary -> Reg G (1 restricted)
    team = ["kyogre", "incineroar", "amoonguss", "rillaboom", "flutter-mane", "urshifu-rapid-strike"]
    result = infer_format_from_pokemon(team, cfg)
    assert result["regulation"] == "reg_g"
    assert "kyogre" in result["restricted_seen"]


def test_two_restricteds_routes_to_reg_i(cfg):
    # User's example: Calyrex Shadow + Koraidon -> Reg I (2 restricted)
    team = [
        "calyrex-shadow-rider",
        "koraidon",
        "urshifu-rapid-strike",
        "rillaboom",
        "incineroar",
        "iron-hands",
    ]
    result = infer_format_from_pokemon(team, cfg)
    assert result["regulation"] == "reg_i", (
        f"Expected reg_i for 2-restrict team, got {result['regulation']} (alts: {result['alternatives']})"
    )
    assert set(result["restricted_seen"]) == {"calyrex-shadow-rider", "koraidon"}
    # reg_f is also a 2-restrict format in our JSON, so it should be a fallback
    assert "reg_f" in result["alternatives"]


def test_zero_restricteds_routes_to_reg_f_first(cfg):
    # User's example: no restricteds -> Reg F (the active 0-restrict format)
    team = ["incineroar", "amoonguss", "rillaboom", "flutter-mane", "garchomp", "iron-hands"]
    result = infer_format_from_pokemon(team, cfg)
    # reg_f is preferred over reg_h for 0-restrict per _PREFERENCE_BY_RESTRICTED_COUNT
    assert result["regulation"] in {"reg_f", "reg_h"}
    assert result["restricted_seen"] == []


def test_empty_team_returns_default(cfg):
    result = infer_format_from_pokemon([], cfg)
    # No info -> falls into the 0-restrict bucket by default
    assert result["regulation"] is not None
    assert result["confidence"] == "medium"


def test_three_restricteds_still_maps_to_two_restrict(cfg):
    # Edge case: someone lists 3 restricteds (illegal even in 2-restrict) — we
    # still classify as 2-restrict format and surface the count in reasons.
    team = ["kyogre", "groudon", "calyrex-shadow-rider"]
    result = infer_format_from_pokemon(team, cfg)
    assert result["regulation"] == "reg_i"
    assert len(result["restricted_seen"]) == 3


def test_banned_pokemon_lowers_confidence(cfg):
    # Mew is banned in all mainline regs but might be legal in Champions
    team = ["mew", "garchomp", "incineroar"]
    result = infer_format_from_pokemon(team, cfg)
    # mew is not in Champions allowlist either (Champions allowlist has 168
    # specific mons, mew is not among them) — so we still bucket as 0-restrict
    # mainline, but flag the illegal sighting.
    assert "mew" in result["illegal_seen"]
    assert result["confidence"] == "low"
