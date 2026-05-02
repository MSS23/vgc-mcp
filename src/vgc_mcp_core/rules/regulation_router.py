"""Resolve user phrasing into a regulation code.

Users mention regulations in many ways:
- "regulation F", "Reg F", "RegF", "F", "regulation_f"
- "champions", "Pokemon Champions", "Reg MA", "MA", "M-A"

This module turns any of those into a canonical code (e.g. `reg_f`,
`reg_ma_champs`) using a single normalization pipeline plus alias map. It
returns `None` for unrecognized phrasing so callers can decide whether to
prompt or fall back.

The router is the single source of truth for "what regulation did the user
mean?" — both the MCP tool layer and any heuristic auto-selection should go
through `resolve_regulation()` rather than reimplementing string matching.
"""

import re
from typing import Optional

from .regulation_loader import RegulationConfig, get_regulation_config

# Canonical aliases: every key is a normalized phrase (lowercase, hyphens and
# spaces collapsed to underscores) -> regulation code in regulations.json.
# Order matters only for documentation; lookup is exact-match.
_ALIASES: dict[str, str] = {
    # Reg F (mainline, 2 restricteds)
    "f": "reg_f",
    "reg_f": "reg_f",
    "regulation_f": "reg_f",
    "reg2026f": "reg_f",
    "vgc_reg_f": "reg_f",
    "vgc_2026_f": "reg_f",

    # Reg G (mainline, 1 restricted)
    "g": "reg_g",
    "reg_g": "reg_g",
    "regulation_g": "reg_g",
    "vgc_reg_g": "reg_g",
    "vgc_2025_g": "reg_g",

    # Reg H (mainline, no restricteds)
    "h": "reg_h",
    "reg_h": "reg_h",
    "regulation_h": "reg_h",
    "vgc_reg_h": "reg_h",
    "vgc_2025_h": "reg_h",
    "no_restricted": "reg_h",

    # Reg I (mainline, future) — alias placeholder; falls through if not in JSON
    "i": "reg_i",
    "reg_i": "reg_i",
    "regulation_i": "reg_i",

    # Reg MA — Pokemon Champions
    "ma": "reg_ma_champs",
    "m_a": "reg_ma_champs",
    "reg_ma": "reg_ma_champs",
    "reg_m_a": "reg_ma_champs",
    "regulation_ma": "reg_ma_champs",
    "regulation_m_a": "reg_ma_champs",
    "champions": "reg_ma_champs",
    "pokemon_champions": "reg_ma_champs",
    "champs": "reg_ma_champs",
    "champions_ma": "reg_ma_champs",
    "champions_reg_ma": "reg_ma_champs",
    "champions_regulation_ma": "reg_ma_champs",
    "ncp": "reg_ma_champs",
    "ncp_ma": "reg_ma_champs",
    "gen10": "reg_ma_champs",
    "gen_10": "reg_ma_champs",
}


def _normalize(phrase: str) -> str:
    """Lowercase + collapse whitespace/hyphens to underscores."""
    s = phrase.strip().lower()
    s = re.sub(r"[\s\-]+", "_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s


def resolve_regulation(
    phrase: str,
    config: Optional[RegulationConfig] = None,
) -> Optional[str]:
    """Map a user phrase like 'Reg I' or 'champions' to a regulation code.

    Steps (first match wins):
    1. Exact code lookup against `regulations.json` (e.g. "reg_f", "reg_ma_champs")
    2. Alias table lookup (covers "champions", "ma", "F", "regulation g", etc.)
    3. Pattern fallback: a single letter/`reg_<letter>` -> `reg_<letter>` if that
       code exists in the loaded config (handles future regs without an explicit alias)

    Returns None if no rule matches.
    """
    if not phrase:
        return None
    cfg = config or get_regulation_config()
    available = set(cfg.list_regulation_codes())

    norm = _normalize(phrase)
    if not norm:
        return None

    # 1. Exact code
    if norm in available:
        return norm

    # 2. Alias table
    aliased = _ALIASES.get(norm)
    if aliased and aliased in available:
        return aliased

    # 3. Pattern fallback for `reg_<letter>` / single letter
    m = re.fullmatch(r"reg_?([a-z])", norm)
    if m:
        candidate = f"reg_{m.group(1)}"
        if candidate in available:
            return candidate
    if len(norm) == 1 and norm.isalpha():
        candidate = f"reg_{norm}"
        if candidate in available:
            return candidate

    return None


def describe_regulation(code: str, config: Optional[RegulationConfig] = None) -> dict:
    """Return a small dict describing the regulation's format system + key caps.

    Useful for tool responses that confirm what the user just selected.
    """
    cfg = config or get_regulation_config()
    reg = cfg.get_regulation(code)
    fmt = cfg.get_format_system(code)
    payload: dict = {
        "code": code,
        "name": reg.get("name", code),
        "format_system": fmt,
        "smogon_formats": cfg.get_smogon_formats(code),
        "default_smogon_rating": cfg.get_default_smogon_rating(code),
        "legality_mode": cfg.get_legality_mode(code),
    }
    if fmt == "champions":
        payload["sp_limits"] = cfg.get_sp_limits(code)
        payload["stat_units"] = "Stat Points (SPs)"
        payload["max_per_stat"] = 32
        payload["max_total"] = 66
    else:
        payload["stat_units"] = "EVs"
        payload["max_per_stat"] = 252
        payload["max_total"] = 508
    return payload
