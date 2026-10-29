"""Read-only Champions-format detection for tool dispatch.

Pure calc/spread/stat tools need to know whether the active session is the
Champions (Reg MA) Stat-Point format so they can branch their math and output.
They must NOT mutate session state to find that out.

`regulation_router.auto_detect_regulation` DOES mutate (it calls
`set_session_regulation(..., by_user=False)` + `record_auto_detection`), which
is correct for the user-surfaced auto-detect tool and import/team/build flows
but wrong for a plain damage or speed calc — a mainline user shouldn't have
their session silently rewritten just by mentioning a Pokemon in a calc.

`detect_champions_format` is side-effect free: an existing session choice
(explicit or auto-detected) always wins; otherwise it INFERS the format from
the mentioned Pokemon via the read-only `infer_format_from_pokemon` without
persisting anything.
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Optional

from .regulation_loader import RegulationConfig, get_regulation_config
from .regulation_router import auto_detect_regulation, infer_format_from_pokemon

# The regulation inferred for the current tool call when the session has no
# regulation of its own. Usage-data lookups read it so a calc that resolved to
# mainline Reg F does not pull Champions sets from the default regulation.
# A ContextVar is scoped to one request's task, so the hint never reaches
# another call or another session, and the session itself is never changed.
_INFERRED_REGULATION: ContextVar[Optional[str]] = ContextVar(
    "vgc_inferred_regulation", default=None
)


def inferred_regulation() -> Optional[str]:
    """Regulation inferred by detect_champions_format in this call, if any."""
    return _INFERRED_REGULATION.get()


def detect_champions_format(
    *pokemon_names: Optional[str],
    cfg: Optional[RegulationConfig] = None,
) -> bool:
    """Return True when the active format resolves to Champions (Reg MA).

    Read-only: never calls set_session_regulation / record_auto_detection.

    Resolution order:
    1. An existing user/session regulation always wins.
    2. Otherwise infer (read-only) from the mentioned Pokemon names.
    3. Otherwise fall back to the configured default regulation.
    """
    cfg = cfg or get_regulation_config()

    # 1. A persisted session choice wins outright. This includes the result of
    # the user-facing auto-detect tool: a later single-Pokemon calculation must
    # not silently reinterpret that established session as another format.
    if cfg.session_regulation is not None:
        return (cfg.get_format_system() or "mainline") == "champions"

    # 2. Read-only inference from the Pokemon mentioned.
    names = [n for n in pokemon_names if n]
    if names:
        try:
            info = infer_format_from_pokemon(names, cfg)
            reg = info.get("regulation")
            if reg:
                _INFERRED_REGULATION.set(reg)
                return cfg.get_format_system(reg) == "champions"
        except Exception:  # noqa: BLE001 — inference must never break a calc
            pass

    # 3. Fall back to the session's current (possibly default) format.
    return (cfg.get_format_system() or "mainline") == "champions"


def auto_detect_champions_format(
    *pokemon_names: str,
    cfg: Optional[RegulationConfig] = None,
) -> bool:
    """MUTATING variant for build/team/import flows.

    Runs `auto_detect_regulation`, which may persist an auto-detected session
    regulation (an explicit user choice still wins), then reports whether the
    resolved format is Champions. Use `detect_champions_format` for pure
    calc/spread/stat tools that must not touch session state.
    """
    cfg = cfg or get_regulation_config()
    try:
        auto_detect_regulation(list(pokemon_names), cfg)
    except Exception:  # noqa: BLE001 — detection must never break a build
        pass
    return (cfg.get_format_system() or "mainline") == "champions"
