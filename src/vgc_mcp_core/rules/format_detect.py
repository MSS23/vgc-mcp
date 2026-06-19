"""Read-only Champions-format detection for tool dispatch.

Pure calc/spread/stat tools need to know whether the active session is the
Champions (Reg MA) Stat-Point format so they can branch their math and output.
They must NOT mutate session state to find that out.

`regulation_router.auto_detect_regulation` DOES mutate (it calls
`set_session_regulation(..., by_user=False)` + `record_auto_detection`), which
is correct for the user-surfaced auto-detect tool and import/team/build flows
but wrong for a plain damage or speed calc — a mainline user shouldn't have
their session silently rewritten just by mentioning a Pokemon in a calc.

`detect_champions_format` is side-effect free: an explicit session choice
always wins; otherwise it INFERS the format from the mentioned Pokemon via the
read-only `infer_format_from_pokemon` without persisting anything.
"""

from __future__ import annotations

from typing import Optional

from .regulation_loader import RegulationConfig, get_regulation_config
from .regulation_router import infer_format_from_pokemon


def detect_champions_format(
    *pokemon_names: Optional[str],
    cfg: Optional[RegulationConfig] = None,
) -> bool:
    """Return True when the active format resolves to Champions (Reg MA).

    Read-only: never calls set_session_regulation / record_auto_detection.

    Resolution order:
    1. An explicit user/session regulation always wins.
    2. Otherwise infer (read-only) from the mentioned Pokemon names.
    3. Otherwise fall back to whatever the session currently resolves to.
    """
    cfg = cfg or get_regulation_config()

    # 1. Explicit session choice wins outright.
    if cfg.session_set_explicitly:
        return (cfg.get_format_system() or "mainline") == "champions"

    # 2. Read-only inference from the Pokemon mentioned.
    names = [n for n in pokemon_names if n]
    if names:
        try:
            info = infer_format_from_pokemon(names, cfg)
            reg = info.get("regulation")
            if reg:
                return cfg.get_format_system(reg) == "champions"
        except Exception:  # noqa: BLE001 — inference must never break a calc
            pass

    # 3. Fall back to the session's current (possibly default) format.
    return (cfg.get_format_system() or "mainline") == "champions"
