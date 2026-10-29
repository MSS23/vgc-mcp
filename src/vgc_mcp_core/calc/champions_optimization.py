"""Champions (Reg MA) stat-point optimization helpers.

Mirrors the most-used EV optimizers (`hp_optimization`, `bulk_optimization`,
speed allocation) for the SP system: 0-32 per stat, 66-point total budget.

Functions here are pure — they take raw numbers and return raw allocations.
Tool handlers should dispatch to this module when `pokemon.is_champions()`.
"""

from typing import Any, Optional

from ..models.pokemon import Nature, StatPointSpread
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


def design_speed_benchmark_sps(
    base_speed: int,
    target_base_speed: int,
    target_sps: int,
    nature: Nature,
    target_nature: Nature,
    *,
    target_stage: int = 0,
    target_booster: bool = False,
    target_tailwind: bool = False,
    booster: bool = False,
    tailwind: bool = False,
    fixed_sps: Optional[int] = None,
) -> dict[str, int]:
    """Find minimum SP to strictly outspeed a target after speed modifiers."""
    if not 0 <= target_sps <= SP_PER_STAT_MAX or not -6 <= target_stage <= 6:
        raise ValueError("Invalid Speed SP allocation or speed stage")
    if fixed_sps is not None and not 0 <= fixed_sps <= SP_PER_STAT_MAX:
        raise ValueError("Speed SP must be between 0 and 32")
    target_speed = calculate_speed_sp(target_base_speed, sp=target_sps, nature=target_nature)
    if target_booster:
        target_speed = target_speed * 3 // 2
    if target_stage >= 0:
        target_speed = target_speed * (2 + target_stage) // 2
    else:
        target_speed = target_speed * 2 // (2 - target_stage)
    if target_tailwind:
        target_speed *= 2

    for sp in ([fixed_sps] if fixed_sps is not None else SP_BREAKPOINTS_LV50):
        speed = calculate_speed_sp(base_speed, sp=sp, nature=nature)
        effective_speed = speed * 3 // 2 if booster else speed
        if tailwind:
            effective_speed *= 2
        if effective_speed > target_speed:
            break
    return {
        "target_speed": target_speed,
        "target_sps": target_sps,
        "sps_needed": sp,
        "my_speed": speed,
        "my_effective_speed": effective_speed,
        "outspeeds": effective_speed > target_speed,
    }


# ---------- HP / Survival ----------

def find_optimal_hp_sps(
    base_hp: int,
    item: str,
    iv: int = 31,
    level: int = 50,
) -> list[dict[str, Any]]:
    """All HP SP options with item-driven optimization scores.

    Same scoring rules as `hp_optimization.find_optimal_hp_evs` (mod-16 for
    Leftovers, mod-10 for Life Orb, mod-4 for Sitrus) but the input grain is
    SP 0-32 instead of EV 0-252.
    """
    from .hp_optimization import _get_item_category, score_hp_for_item

    category = _get_item_category(item)
    results: list[dict[str, Any]] = []
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
) -> Optional[dict[str, Any]]:
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

    best: Optional[dict[str, Any]] = None
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

# ---------- Validators ----------

def complete_sp_allocation(
    allocation: dict[str, int],
    priorities: tuple[str, ...] = ("hp", "defense", "special_defense"),
    budget: int = SP_TOTAL_MAX,
) -> dict[str, int]:
    """Spend a recommendation's remaining budget without changing locked stats.

    Existing investment is preserved. Only listed stats receive extra points,
    so Speed benchmarks and item-specific HP numbers can be kept fixed.
    Partial inputs remain supported by the stat calculators and search helpers.
    """
    if any(stat not in StatPointSpread.model_fields for stat in allocation):
        raise ValueError("SP allocation contains unknown stat names")
    if type(budget) is not int or any(type(value) is not int for value in allocation.values()):
        raise ValueError("SP allocations and budgets must be whole numbers")
    spread = StatPointSpread(**allocation)
    if not spread.is_valid() or not spread.total <= budget <= SP_TOTAL_MAX:
        raise ValueError("SP allocation exceeds the available budget")
    result = dict(allocation)
    remaining = budget - spread.total
    for stat in priorities:
        if stat not in StatPointSpread.model_fields:
            raise ValueError(f"Unknown stat: {stat}")
        extra = min(SP_PER_STAT_MAX - result.get(stat, 0), remaining)
        result[stat] = result.get(stat, 0) + extra
        remaining -= extra
    if remaining:
        raise ValueError("Cannot spend the SP budget without changing locked stats")
    return result

def validate_sp_allocation(allocation: dict[str, int]) -> dict[str, Any]:
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
        "is_complete": total == SP_TOTAL_MAX and not per_stat_violations,
    }
