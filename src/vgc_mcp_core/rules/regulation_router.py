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


def _is_mega_form(name: str) -> bool:
    """A Pokemon name suggests a Mega form (e.g. `kangaskhan-mega`, `mega-charizard-x`)."""
    n = name.lower().strip().replace(" ", "-")
    return "-mega" in n or n.startswith("mega-") or n.endswith("-mega-x") or n.endswith("-mega-y")


# Restricted-format preference order: when multiple regulations match a given
# restricted-count, prefer the one most aligned with the real-world 2026 VGC
# progression (where F = 0 restricteds, G = 1, H = 0/no-items, I = 2, MA = NCP).
# These keys are consulted by `infer_format_from_pokemon` to pick a primary
# answer when the data alone leaves multiple regs as valid candidates.
_PREFERENCE_BY_RESTRICTED_COUNT: dict[int, list[str]] = {
    0: ["reg_f", "reg_h"],          # Reg F is the active 0-restrict format; H is older/no-items
    1: ["reg_g"],                   # Only mainline 1-restrict format
    2: ["reg_i", "reg_f"],          # Prefer reg_i (true 2-restrict format) over legacy reg_f
}


def infer_format_from_pokemon(
    pokemon_names: list[str],
    config: Optional[RegulationConfig] = None,
) -> dict:
    """Guess which regulation a team belongs to from the Pokemon mentioned.

    Heuristics, in order:
    1. Any Mega form -> `reg_ma_champs` (Megas are Champions-only).
    2. Any name in the Champions allowlist BUT illegal in mainline (e.g. an
       NCP-only mon) -> `reg_ma_champs`.
    3. Count Pokemon that are restricted in mainline regs:
       - 0 restricteds -> the active 0-restrict reg (`reg_f` first, then `reg_h`)
       - 1 restricted  -> `reg_g`
       - 2+ restricteds -> `reg_i` (the modern 2-restrict format), then `reg_f`
    4. If a mentioned Pokemon is banned in every regulation -> return None
       primary with a `notes` field flagging the illegal mention.

    Returns:
        {
            "regulation": "reg_g" | None,
            "confidence": "high" | "medium" | "low",
            "reasons": [str, ...],
            "alternatives": [reg_code, ...],
            "restricted_seen": [pokemon_name, ...],
            "illegal_seen": [pokemon_name, ...],
        }
    """
    cfg = config or get_regulation_config()
    available = cfg.list_regulation_codes()

    norm_names = [n.lower().strip().replace(" ", "-") for n in pokemon_names if n]
    reasons: list[str] = []
    illegal_seen: list[str] = []

    # 1. Mega forms => Champions
    megas = [n for n in norm_names if _is_mega_form(n)]
    if megas and "reg_ma_champs" in available:
        reasons.append(f"Mega form(s) detected ({', '.join(megas)}) — Megas are only legal in Champions Reg MA.")
        return {
            "regulation": "reg_ma_champs",
            "confidence": "high",
            "reasons": reasons,
            "alternatives": [],
            "restricted_seen": [],
            "illegal_seen": [],
        }

    # 2. Pokemon legal in Champions but absent from mainline => Champions.
    # We approximate "absent from mainline" by checking the union of all
    # mainline regs' banned + restricted lists; if the mon isn't legal in any
    # mainline format and IS in Champions, it must be Champions.
    if "reg_ma_champs" in available:
        champ_legal = cfg.get_legal_pokemon("reg_ma_champs")
        mainline_codes = [c for c in available if cfg.get_format_system(c) == "mainline"]
        # A Pokemon is "mainline-legal" if it's NOT banned and NOT in any reg's
        # banned list. Banned lists are uniform across regs, so it's enough to
        # check one. If any mentioned mon is banned mainline but legal in champs,
        # that's a strong Champions signal.
        for n in norm_names:
            if n in champ_legal:
                # Banned in mainline?
                banned_mainline = any(cfg.is_pokemon_banned(n, c) for c in mainline_codes)
                if banned_mainline:
                    reasons.append(
                        f"{n!r} is in the Champions allowlist but banned in mainline — Champions only."
                    )
                    return {
                        "regulation": "reg_ma_champs",
                        "confidence": "high",
                        "reasons": reasons,
                        "alternatives": [],
                        "restricted_seen": [],
                        "illegal_seen": [],
                    }

    # 3. Count restricteds against any mainline reg's restricted list (they're
    # the same across regs, so use the first available).
    mainline_codes = [c for c in available if cfg.get_format_system(c) == "mainline"]
    if not mainline_codes:
        return {
            "regulation": None,
            "confidence": "low",
            "reasons": ["No mainline regulations defined in regulations.json."],
            "alternatives": [],
            "restricted_seen": [],
            "illegal_seen": [],
        }

    restricted_set = cfg.get_restricted_pokemon(mainline_codes[0])
    banned_set = cfg.get_banned_pokemon(mainline_codes[0])
    restricteds_seen = [n for n in norm_names if n in restricted_set]
    illegal_seen = [n for n in norm_names if n in banned_set]

    if illegal_seen:
        reasons.append(
            f"Mentioned Pokemon is banned in all mainline regs: {', '.join(illegal_seen)}. "
            f"This may be a Champions team or a typo."
        )

    n_restricted = len(restricteds_seen)
    bucket = min(n_restricted, 2)  # 2+ all map to the 2-restrict bucket
    preferred = _PREFERENCE_BY_RESTRICTED_COUNT.get(bucket, [])
    primary: Optional[str] = None
    alternatives: list[str] = []
    for code in preferred:
        if code in available:
            if primary is None:
                primary = code
            else:
                alternatives.append(code)

    # If none of the preferred codes exist, fall back to ANY mainline reg with
    # the matching restricted_limit.
    if primary is None:
        for code in mainline_codes:
            if cfg.get_restricted_limit(code) == bucket:
                primary = code
                break

    if restricteds_seen:
        reasons.append(
            f"{len(restricteds_seen)} restricted Pokemon mentioned ({', '.join(restricteds_seen)}) — "
            f"matches a {bucket}-restricted format."
        )
    else:
        reasons.append(
            "No restricted Pokemon mentioned — matches a 0-restricted format."
        )

    # Current-meta hint: tournaments through May 2026 are predominantly Reg I,
    # transitioning to Reg MA Champions in June (Turin onward). For teams that
    # could plausibly fit either Champions or a mainline 0-restrict reg, surface
    # Champions as a likely-popular alternative so callers can ask.
    if (
        bucket == 0
        and not illegal_seen
        and "reg_ma_champs" in available
        and "reg_ma_champs" not in alternatives
        and primary != "reg_ma_champs"
    ):
        champ_legal = cfg.get_legal_pokemon("reg_ma_champs")
        if norm_names and all(n in champ_legal for n in norm_names):
            alternatives.append("reg_ma_champs")
            reasons.append(
                "All mentioned Pokemon are also legal in Champions Reg MA — "
                "consider it if this is a recent team (Champions is the most "
                "popular current format from June 2026 onward)."
            )

    confidence = "high" if restricteds_seen else "medium"
    if illegal_seen:
        confidence = "low"

    return {
        "regulation": primary,
        "confidence": confidence,
        "reasons": reasons,
        "alternatives": alternatives,
        "restricted_seen": restricteds_seen,
        "illegal_seen": illegal_seen,
    }


def auto_detect_regulation(
    pokemon_names: list[str],
    config: Optional[RegulationConfig] = None,
) -> dict:
    """Auto-detect the regulation from mentioned Pokemon and apply it.

    This is the zero-config entry point — call it from any tool that takes
    Pokemon names as input. Behavior:

    - If the user already explicitly set the session regulation
      (`set_session_regulation` invoked directly or via wording), this is a
      no-op that returns `{"action": "skipped", ...}` so the existing choice
      is respected.
    - Otherwise runs `infer_format_from_pokemon` and, if confidence is
      high or medium, sets the session regulation as a side effect (with
      `by_user=False` so a later explicit set still wins).
    - Records the result on the config so tool responses can surface
      `regulation_auto_detected` and tell the user what happened.

    Returns a dict with: `action` ("set" | "skipped" | "low_confidence"),
    plus the inference fields (`regulation`, `confidence`, `reasons`,
    `alternatives`, etc.). Tools should pass the returned dict through to
    their response so the user sees what the server inferred.
    """
    cfg = config or get_regulation_config()

    if cfg.session_set_explicitly:
        return {
            "action": "skipped",
            "reason": "session regulation was set explicitly — keeping it",
            "regulation": cfg.current_regulation,
        }

    result = infer_format_from_pokemon(pokemon_names, cfg)
    primary = result.get("regulation")
    confidence = result.get("confidence", "low")

    if primary and confidence in ("high", "medium"):
        cfg.set_session_regulation(primary, by_user=False)
        result["action"] = "set"
        cfg.record_auto_detection(result)
        return result

    result["action"] = "low_confidence"
    cfg.record_auto_detection(result)
    return result


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
