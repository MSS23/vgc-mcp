"""EV <-> SP conversion for the dual-format system.

Mainline VGC uses 0-252 EVs per stat (508 total). Pokemon Champions Reg MA
uses 0-32 Stat Points per stat (66 total). The two map onto the same stat
formula: 1 SP contributes the same stat increment as 8 EVs (because the
Champions formula substitutes `SP * 2` into the `EV / 4` slot of the Gen 9
formula). At saturation, 32 SP == 252 EV at level 50.

This module is the canonical converter so callers don't redo the math
inline. Use `evs_to_sps_spread` / `sps_to_evs_spread` to round-trip whole
spreads, and the scalar helpers (`ev_to_sp` / `sp_to_ev`) for one-stat
conversions.
"""

from __future__ import annotations

from typing import Optional

from ..models.pokemon import EVSpread, StatPointSpread

# 1 SP contributes the same stat increment as 8 EVs at level 50.
EV_PER_SP = 8
SP_MAX_PER_STAT = 32
SP_MAX_TOTAL = 66
EV_MAX_PER_STAT = 252
EV_MAX_TOTAL = 508


def ev_to_sp(ev: int, *, round_mode: str = "ceil") -> int:
    """Convert an EV value (0-252) to the equivalent SP value (0-32).

    `round_mode`:
    - "ceil" (default): round up so the SP allocation matches or exceeds the
      EV allocation's stat output. Use when porting a defensive spread.
    - "floor": round down. Use when porting an offensive spread where you
      do NOT want to over-invest past the original budget.
    - "nearest": round to the closest SP, breaking ties up.
    """
    ev = max(0, min(EV_MAX_PER_STAT, int(ev)))
    if ev == 0:
        return 0
    if ev >= EV_MAX_PER_STAT:
        return SP_MAX_PER_STAT
    raw = ev / EV_PER_SP
    if round_mode == "floor":
        sp = int(raw)
    elif round_mode == "nearest":
        sp = int(raw + 0.5)
    else:  # "ceil"
        sp = int(raw) if raw.is_integer() else int(raw) + 1
    return max(0, min(SP_MAX_PER_STAT, sp))


def sp_to_ev(sp: int) -> int:
    """Convert an SP value (0-32) to the equivalent EV value (0-252).

    32 SP saturates to 252 EV (the same stat output). Below that, 1 SP
    maps to 8 EVs.
    """
    sp = max(0, min(SP_MAX_PER_STAT, int(sp)))
    if sp >= SP_MAX_PER_STAT:
        return EV_MAX_PER_STAT
    return sp * EV_PER_SP


def evs_to_sps_spread(
    evs: EVSpread, *, round_mode: str = "ceil"
) -> StatPointSpread:
    """Convert a full EVSpread to a StatPointSpread.

    If the per-stat conversion overflows the 66 SP total budget, stats are
    trimmed proportionally from the lowest-priority slots first. Priority
    order matches Champions convention: Spe > HP > offensive stat > defenses.
    The result is always a valid StatPointSpread (`is_valid() == True`).
    """
    raw = {
        "hp": ev_to_sp(evs.hp, round_mode=round_mode),
        "attack": ev_to_sp(evs.attack, round_mode=round_mode),
        "defense": ev_to_sp(evs.defense, round_mode=round_mode),
        "special_attack": ev_to_sp(evs.special_attack, round_mode=round_mode),
        "special_defense": ev_to_sp(evs.special_defense, round_mode=round_mode),
        "speed": ev_to_sp(evs.speed, round_mode=round_mode),
    }
    total = sum(raw.values())
    if total <= SP_MAX_TOTAL:
        return StatPointSpread(**raw)

    # Trim overflow from least-prioritized stats first.
    trim_order = ["defense", "special_defense", "attack", "special_attack", "hp", "speed"]
    overflow = total - SP_MAX_TOTAL
    for stat in trim_order:
        if overflow <= 0:
            break
        take = min(raw[stat], overflow)
        raw[stat] -= take
        overflow -= take
    return StatPointSpread(**raw)


def sps_to_evs_spread(sps: StatPointSpread) -> EVSpread:
    """Convert a StatPointSpread to a mainline EVSpread.

    Each SP becomes 8 EVs (32 SP → 252 EVs at saturation). Result is
    guaranteed multiple-of-4 for every stat, which the Showdown format
    expects.
    """
    return EVSpread(
        hp=sp_to_ev(sps.hp),
        attack=sp_to_ev(sps.attack),
        defense=sp_to_ev(sps.defense),
        special_attack=sp_to_ev(sps.special_attack),
        special_defense=sp_to_ev(sps.special_defense),
        speed=sp_to_ev(sps.speed),
    )


def describe_conversion(
    evs: Optional[EVSpread] = None,
    sps: Optional[StatPointSpread] = None,
) -> dict:
    """Round-trip both directions and return a side-by-side dict.

    Useful for tools that want to surface "this EV spread translates to
    this SP spread" so users can switch formats without redoing the math.
    """
    if evs is not None and sps is None:
        sps = evs_to_sps_spread(evs)
    elif sps is not None and evs is None:
        evs = sps_to_evs_spread(sps)
    elif evs is None and sps is None:
        evs = EVSpread()
        sps = StatPointSpread()
    return {
        "evs": {
            "hp": evs.hp, "atk": evs.attack, "def": evs.defense,
            "spa": evs.special_attack, "spd": evs.special_defense, "spe": evs.speed,
            "total": evs.total,
        },
        "sps": {
            "hp": sps.hp, "at": sps.attack, "df": sps.defense,
            "sa": sps.special_attack, "sd": sps.special_defense, "sp": sps.speed,
            "total": sps.total,
        },
    }


def regulation_uses_champions(regulation_code: Optional[str]) -> bool:
    """True if the regulation code uses the Champions SP system.

    Mirrors the `format_system` field on regulation entries without needing
    to load the whole RegulationConfig. Cheap predicate for tool dispatch.
    """
    if not regulation_code:
        return False
    code = regulation_code.lower()
    return code in {
        "reg_ma_champs", "reg_ma", "ma",
        "reg_mb_champs", "reg_mb", "mb",
        "champions",
    } or "champ" in code


def coerce_champions_allocation(allocation: dict[str, int]) -> tuple[dict[str, int], Optional[dict]]:
    """Interpret a user-supplied stat allocation for a Champions session.

    Tools with EV-named parameters (`hp_evs`, `spa_evs`, ...) interpret those
    values as Stat Points in a Champions session. Users porting mainline sets
    routinely pass EV-scale numbers (252 SpA, 196 HP, ...) which would fail
    the 32/stat cap. This helper detects the unambiguous case and converts.

    Rule:
    - If ANY stat exceeds the 32 SP per-stat cap, the input can only be an
      EV-scale spread -> convert every stat with `ev_to_sp` (round up, so
      defensive benchmarks are preserved) and trim to the 66 total via
      `evs_to_sps_spread`.
    - If every stat fits in 0-32, the values are taken as native SPs
      unchanged - even if the total overflows 66, because e.g. 30/30/30
      is more plausibly an over-budget SP attempt than a 12-EV spread,
      and the downstream validator gives a clear "total exceeds 66" error.

    Args:
        allocation: dict with full stat names (hp/attack/defense/
            special_attack/special_defense/speed) -> requested investment.

    Returns:
        (sp_allocation, conversion_note) - `conversion_note` is None when the
        input was already SP-scale, else a dict describing what was converted
        (include it in the tool response so the caller sees the translation).
    """
    if not any(v > SP_MAX_PER_STAT for v in allocation.values()):
        return dict(allocation), None

    ev_spread = EVSpread(
        hp=min(EV_MAX_PER_STAT, max(0, allocation.get("hp", 0))),
        attack=min(EV_MAX_PER_STAT, max(0, allocation.get("attack", 0))),
        defense=min(EV_MAX_PER_STAT, max(0, allocation.get("defense", 0))),
        special_attack=min(EV_MAX_PER_STAT, max(0, allocation.get("special_attack", 0))),
        special_defense=min(EV_MAX_PER_STAT, max(0, allocation.get("special_defense", 0))),
        speed=min(EV_MAX_PER_STAT, max(0, allocation.get("speed", 0))),
    )
    sp_spread = evs_to_sps_spread(ev_spread, round_mode="ceil")
    converted = {
        "hp": sp_spread.hp,
        "attack": sp_spread.attack,
        "defense": sp_spread.defense,
        "special_attack": sp_spread.special_attack,
        "special_defense": sp_spread.special_defense,
        "speed": sp_spread.speed,
    }
    note = {
        "detected_input": "EVs (mainline scale)",
        "interpreted_as": "Stat Points (Champions scale)",
        "original_evs": {k: v for k, v in allocation.items() if v},
        "converted_sps": {k: v for k, v in converted.items() if v},
        "rule": "1 SP = 8 EVs (252 EV saturates to 32 SP); rounded up, trimmed to the 66 SP budget",
    }
    return converted, note
