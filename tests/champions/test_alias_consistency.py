"""Catches drift between regulations.json and the router's alias map.

If a contributor adds a regulation to JSON but forgets to add a phrase alias
(or vice versa) the project still works, but user-facing wording silently
fails to resolve. This file fails fast in CI when the two go out of sync.
"""

from vgc_mcp_core.rules.regulation_loader import RegulationConfig
from vgc_mcp_core.rules.regulation_router import CHAMPIONS_DEFAULT, _ALIASES, resolve_regulation

# Codes that exist in the router's alias table but are intentionally not yet
# defined in regulations.json (e.g. future regulations stubbed out so users
# don't get blank stares when they ask early). These should resolve to None
# until the JSON entry is added. Empty for now — reg_i was promoted to a real
# regulation when the 2-restrict format definition landed.
_PROVISIONAL_CODES: set[str] = set()


def _user_phrase(code: str) -> str:
    """'reg_f' -> 'Reg F', 'reg_mc_champs' -> 'Reg MC'."""
    letters = code.removeprefix("reg_").removesuffix("_champs")
    return f"Reg {letters.upper()}"


def test_every_regulation_resolves_from_its_user_phrase():
    """'Reg X' must resolve for every code in JSON, whether via an explicit
    alias or the router's pattern fallback — otherwise a regulation added by
    scripts/sync_regulations.py would be unselectable by users."""
    cfg = RegulationConfig()
    for code in cfg.list_regulation_codes():
        phrase = _user_phrase(code)
        assert resolve_regulation(phrase, cfg) == code, (
            f"{phrase!r} does not resolve to {code!r}; add an alias or extend the pattern fallback."
        )


def test_every_router_alias_points_to_a_real_or_provisional_code():
    """Every alias target must resolve to a real regulation, except the
    provisional placeholder set kept for forward-compatibility."""
    cfg = RegulationConfig()
    available = set(cfg.list_regulation_codes())

    bad_targets = {
        target
        for target in _ALIASES.values()
        if target not in available and target not in _PROVISIONAL_CODES and target != CHAMPIONS_DEFAULT
    }
    assert not bad_targets, (
        f"Router aliases point at codes that don't exist in regulations.json "
        f"and aren't in the provisional list: {sorted(bad_targets)}. "
        f"Either add the JSON entry or move the code into _PROVISIONAL_CODES."
    )


def test_canonical_codes_resolve_to_themselves():
    """`resolve_regulation('reg_f')` -> `reg_f`, etc. Catches a regression where
    the normalization pipeline mangles already-canonical input."""
    cfg = RegulationConfig()
    for code in cfg.list_regulation_codes():
        assert resolve_regulation(code, cfg) == code, (
            f"Canonical code {code!r} did not resolve to itself."
        )


def test_provisional_codes_resolve_to_none():
    """Until reg_i (etc.) is added to regulations.json, the router must return
    None for those phrasings rather than silently routing to a stale code."""
    cfg = RegulationConfig()
    for code in _PROVISIONAL_CODES:
        if code in cfg.list_regulation_codes():
            continue  # JSON has caught up; alias is now real
        # Construct the canonical user phrasing — last component is the letter.
        letter = code.split("_")[-1]
        assert resolve_regulation(letter.upper(), cfg) is None
        assert resolve_regulation(f"Reg {letter.upper()}", cfg) is None


def test_format_system_per_regulation_is_set():
    """Every regulation in JSON declares (or defaults) a known format_system."""
    cfg = RegulationConfig()
    for code in cfg.list_regulation_codes():
        fmt = cfg.get_format_system(code)
        assert fmt in {"mainline", "champions"}, (
            f"Regulation {code!r} has unknown format_system={fmt!r}; "
            f"only 'mainline' or 'champions' are supported."
        )
