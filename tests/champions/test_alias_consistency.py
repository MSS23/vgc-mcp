"""Catches drift between regulations.json and the router's alias map.

If a contributor adds a regulation to JSON but forgets to add a phrase alias
(or vice versa) the project still works, but user-facing wording silently
fails to resolve. This file fails fast in CI when the two go out of sync.
"""

from vgc_mcp_core.rules.regulation_loader import RegulationConfig
from vgc_mcp_core.rules.regulation_router import _ALIASES, resolve_regulation


# Codes that exist in the router's alias table but are intentionally not yet
# defined in regulations.json (e.g. future regulations stubbed out so users
# don't get blank stares when they ask early). These should resolve to None
# until the JSON entry is added.
_PROVISIONAL_CODES = {"reg_i"}


def test_every_regulation_has_a_router_alias():
    """For each regulation code in JSON, at least one alias must point at it.

    Otherwise the user wording 'Reg X' would never resolve to that code.
    """
    cfg = RegulationConfig()
    available = set(cfg.list_regulation_codes())
    aliased_targets = set(_ALIASES.values())

    missing = available - aliased_targets
    assert not missing, (
        f"These regulation codes exist in regulations.json but no alias in "
        f"regulation_router._ALIASES points to them: {sorted(missing)}. "
        f"Add at least one phrase mapping or users won't be able to select them."
    )


def test_every_router_alias_points_to_a_real_or_provisional_code():
    """Every alias target must resolve to a real regulation, except the
    provisional placeholder set kept for forward-compatibility."""
    cfg = RegulationConfig()
    available = set(cfg.list_regulation_codes())

    bad_targets = {
        target
        for target in _ALIASES.values()
        if target not in available and target not in _PROVISIONAL_CODES
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
