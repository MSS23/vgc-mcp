"""Champions (Reg MA) stat-point optimization helpers.

Mirrors the most-used EV optimizers (`hp_optimization`, `bulk_optimization`,
speed allocation) for the SP system: 0-32 per stat, 66-point total budget.

Functions here are pure — they take raw numbers and return raw allocations.
Tool handlers should dispatch to this module when `pokemon.is_champions()`.
"""

import math
from typing import Optional

from ..models.pokemon import Nature
from .stats_champions import (
    SP_BREAKPOINTS_LV50,
    calculate_hp_sp,
    calculate_speed_sp,
    calculate_stat_sp,
)

SP_PER_STAT_MAX = 32
SP_TOTAL_MAX = 66


# ---------- Speed ----------

def find_speed_sps_to_outspeed(
    base_speed: int,
    target_speed: int,
    nature: Nature = Nature.SERIOUS,
    iv: int = 31,
    level: int = 50,
) -> Optional[int]:
    """Minimum Speed SPs (0-32) to reach `target_speed + 1` (i.e. outspeed).

    Returns None if even 32 SP with this nature/IV cannot outspeed the target.
    """
    needed = target_speed + 1
    for sp in SP_BREAKPOINTS_LV50:
        if calculate_speed_sp(base_speed, iv, sp, level, nature) >= needed:
            return sp
    return None


# ---------- HP / Survival ----------

def find_survival_hp_sps(
    base_hp: int,
    base_def: int,
    raw_damage_max: int,
    iv_hp: int = 31,
    iv_def: int = 31,
    def_nature_mod: float = 1.0,
    def_sp: int = 0,
    level: int = 50,
) -> Optional[int]:
    """Minimum HP SP needed so that `final_hp > raw_damage_max` survives the hit.

    `raw_damage_max` is the unrolled max damage already adjusted for the
    defender's existing Defense/SpDef (caller computes that, since damage scales
    with the defensive stat). For Champions we sweep HP SP 0-32 and return the
    smallest value at which HP exceeds the rolled max.

    Returns None if max HP investment still cannot survive.
    """
    for sp in SP_BREAKPOINTS_LV50:
        hp = calculate_hp_sp(base_hp, iv_hp, sp, level)
        if hp > raw_damage_max:
            return sp
    return None


def find_optimal_hp_sps(
    base_hp: int,
    item: str,
    iv: int = 31,
    level: int = 50,
) -> list[dict]:
    """All HP SP options with item-driven optimization scores.

    Same scoring rules as `hp_optimization.find_optimal_hp_evs` (mod-16 for
    Leftovers, mod-10 for Life Orb, mod-4 for Sitrus) but the input grain is
    SP 0-32 instead of EV 0-252.
    """
    from .hp_optimization import _get_item_category, score_hp_for_item

    category = _get_item_category(item)
    results: list[dict] = []
    for sp in SP_BREAKPOINTS_LV50:
        hp = calculate_hp_sp(base_hp, iv, sp, level)
        score = score_hp_for_item(hp, item)

        recovery = 0
        notes = ""
        if category == "recovery_16":
            recovery = hp // 16
            r = hp % 16
            notes = f"{hp} % 16 = {r}" + (" (optimal!)" if r == 0 else "")
        elif category == "recoil_10":
            recovery = -(hp // 10)
            r = hp % 10
            if r == 9:
                notes = f"{hp} % 10 = 9 (optimal - min recoil!)"
            elif r == 0:
                notes = f"{hp} % 10 = 0 (worst - max recoil)"
            else:
                notes = f"{hp} % 10 = {r}"
        elif category == "heal_4":
            recovery = hp // 4
            r = hp % 4
            notes = f"{hp} % 4 = {r}" + (" (optimal!)" if r == 0 else "")

        results.append({
            "sp": sp,
            "hp_stat": hp,
            "score": round(score, 3),
            "recovery_per_turn": recovery,
            "notes": notes,
        })
    results.sort(key=lambda x: (-x["score"], x["sp"]))
    return results


# ---------- Bulk allocation ----------

def find_bulk_sps_to_survive(
    base_hp: int,
    base_def: int,
    incoming_dmg_at_zero_def: int,
    iv_hp: int = 31,
    iv_def: int = 31,
    def_nature_mod: float = 1.0,
    level: int = 50,
    sp_budget: int = SP_TOTAL_MAX,
) -> Optional[dict]:
    """Find the cheapest HP+Def SP allocation to survive `incoming_dmg_at_zero_def`.

    Sweeps every (hp_sp, def_sp) pair in 0..32 × 0..32 with hp+def ≤ budget
    and returns the allocation that survives with the minimum total SP. Damage
    is scaled by the ratio (defensive_stat_at_zero_sp / defensive_stat_at_X_sp)
    — same approximation used by the EV bulk solver.

    Returns dict with `hp_sp`, `def_sp`, `total_sp`, `final_hp`, `final_def`,
    `damage_taken`, `hp_remaining`. None if no allocation survives.
    """
    from math import floor

    base_def_stat = calculate_stat_sp(base_def, iv_def, 0, level, def_nature_mod)
    if base_def_stat <= 0:
        return None

    best: Optional[dict] = None
    for hp_sp in SP_BREAKPOINTS_LV50:
        if hp_sp > sp_budget:
            break
        hp = calculate_hp_sp(base_hp, iv_hp, hp_sp, level)
        for def_sp in SP_BREAKPOINTS_LV50:
            total = hp_sp + def_sp
            if total > sp_budget:
                break
            new_def = calculate_stat_sp(base_def, iv_def, def_sp, level, def_nature_mod)
            damage = floor(incoming_dmg_at_zero_def * base_def_stat / new_def)
            if hp > damage:
                cand = {
                    "hp_sp": hp_sp,
                    "def_sp": def_sp,
                    "total_sp": total,
                    "final_hp": hp,
                    "final_def": new_def,
                    "damage_taken": damage,
                    "hp_remaining": hp - damage,
                }
                if best is None or cand["total_sp"] < best["total_sp"]:
                    best = cand
                    # Early break: cheapest at this HP level — try lower HP next.
                    break
    return best


# ---------- Offensive thresholds ----------

def find_attack_sps_for_ko(
    base_atk: int,
    target_dmg_floor: int,
    base_dmg_at_zero_atk: int,
    iv: int = 31,
    nature_mod: float = 1.0,
    level: int = 50,
) -> Optional[int]:
    """Minimum offensive SP to push damage above `target_dmg_floor`.

    `base_dmg_at_zero_atk` is the damage that would be dealt with 0 SP at the
    given nature/item config; we scale linearly with the offensive stat (same
    approximation used by the EV-side ko-search) and find the smallest SP at
    which damage clears the floor.
    """
    base_stat = calculate_stat_sp(base_atk, iv, 0, level, nature_mod)
    if base_stat <= 0:
        return None
    for sp in SP_BREAKPOINTS_LV50:
        new_stat = calculate_stat_sp(base_atk, iv, sp, level, nature_mod)
        scaled = math.floor(base_dmg_at_zero_atk * new_stat / base_stat)
        if scaled > target_dmg_floor:
            return sp
    return None


# ---------- Validators ----------

def validate_sp_allocation(allocation: dict[str, int]) -> dict:
    """Validate an SP allocation against the 32/stat, 66/total caps.

    Args:
        allocation: dict with stat name -> sp count.

    Returns:
        dict with `is_valid`, `total`, `over_budget`, `per_stat_violations`,
        `remaining` keys.
    """
    total = 0
    per_stat_violations: list[str] = []
    for stat, sp in allocation.items():
        total += sp
        if sp > SP_PER_STAT_MAX:
            per_stat_violations.append(
                f"{stat}: {sp} SP exceeds per-stat max ({SP_PER_STAT_MAX})"
            )
        if sp < 0:
            per_stat_violations.append(f"{stat}: SP cannot be negative")
    return {
        "is_valid": total <= SP_TOTAL_MAX and not per_stat_violations,
        "total": total,
        "over_budget": max(0, total - SP_TOTAL_MAX),
        "per_stat_violations": per_stat_violations,
        "remaining": max(0, SP_TOTAL_MAX - total),
    }
