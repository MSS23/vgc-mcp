"""HP number optimization for item-based recovery and recoil.

In VGC, recovery and recoil use integer division (floor), so small HP
differences can change the actual amount recovered/lost per turn:

- Leftovers / Black Sludge / Grassy Terrain: hp // 16 recovery
  Optimal: HP divisible by 16 (e.g., 176 recovers 11, 175 recovers 10)

- Life Orb: hp // 10 recoil per attack
  Optimal: HP = 10n-1 (e.g., 159 loses 15, 160 loses 16)

- Sitrus Berry: hp // 4 heal at 50% HP
  Optimal: HP divisible by 4
"""

from ..config import EV_BREAKPOINTS_LV50
from .stats import calculate_hp

# Items that benefit from 1/16 HP divisibility
RECOVERY_16_ITEMS = {"leftovers", "black-sludge"}

# Terrain that uses 1/16 recovery (not an item, but same formula)
RECOVERY_16_TERRAIN = {"grassy-terrain"}

# Items that use 1/10 HP recoil
RECOIL_10_ITEMS = {"life-orb"}

# Items that use 1/4 HP heal
HEAL_4_ITEMS = {"sitrus-berry"}


def _normalize_item(item: str) -> str:
    """Normalize item name to lowercase hyphenated format."""
    return item.lower().replace(" ", "-")


def _get_item_category(item: str) -> str | None:
    """Get the optimization category for an item.

    Returns:
        "recovery_16", "recoil_10", "heal_4", or None
    """
    normalized = _normalize_item(item)
    if normalized in RECOVERY_16_ITEMS or normalized in RECOVERY_16_TERRAIN:
        return "recovery_16"
    if normalized in RECOIL_10_ITEMS:
        return "recoil_10"
    if normalized in HEAL_4_ITEMS:
        return "heal_4"
    return None


def score_hp_for_item(hp_stat: int, item: str) -> float:
    """Score how optimal an HP stat is for a given item.

    Args:
        hp_stat: The calculated HP stat value
        item: Item name (e.g., "leftovers", "life-orb", "sitrus-berry")

    Returns:
        0.0-1.0 quality score (1.0 = perfect HP number for this item)
    """
    category = _get_item_category(item)

    if category is None:
        return 1.0  # No preference for unknown/irrelevant items

    if category == "recovery_16":
        # HP % 16 == 0 is perfect (max recovery per HP point)
        remainder = hp_stat % 16
        if remainder == 0:
            return 1.0
        # Score based on how close to a multiple of 16
        # 0 remainder = 1.0, 8 remainder = worst (0.0)
        return 1.0 - (min(remainder, 16 - remainder) / 8.0)

    if category == "recoil_10":
        # HP % 10 == 9 is best (10n-1 minimizes floor(HP/10) as fraction of HP)
        # HP % 10 == 0 is worst (loses extra 1 HP per attack)
        remainder = hp_stat % 10
        if remainder == 9:
            return 1.0
        if remainder == 0:
            return 0.0
        # Other values are in between
        # Closer to 9 is better (higher remainder = lower recoil fraction)
        return remainder / 9.0

    if category == "heal_4":
        # HP % 4 == 0 is perfect (max Sitrus heal)
        remainder = hp_stat % 4
        if remainder == 0:
            return 1.0
        return 1.0 - (remainder / 3.0)

    return 1.0


def find_optimal_hp_evs(
    base_hp: int,
    item: str,
    iv: int = 31,
    level: int = 50,
) -> list[dict]:
    """Find all HP EV options with their item optimization scores.

    Args:
        base_hp: Base HP stat
        item: Item name (e.g., "leftovers", "life-orb")
        iv: HP IV (default 31)
        level: Pokemon level (default 50)

    Returns:
        List of dicts sorted by score desc then ev asc:
        [{"ev": int, "hp_stat": int, "score": float,
          "recovery_per_turn": int, "notes": str}, ...]
    """
    category = _get_item_category(item)
    results = []

    for ev in EV_BREAKPOINTS_LV50:
        hp = calculate_hp(base_hp, iv, ev, level)
        score = score_hp_for_item(hp, item)

        # Calculate recovery/recoil amount
        recovery = 0
        notes = ""

        if category == "recovery_16":
            recovery = hp // 16
            remainder = hp % 16
            if remainder == 0:
                notes = f"{hp} % 16 = 0 (optimal!)"
            else:
                notes = f"{hp} % 16 = {remainder}"

        elif category == "recoil_10":
            recovery = -(hp // 10)  # Negative = recoil
            remainder = hp % 10
            if remainder == 9:
                notes = f"{hp} % 10 = 9 (optimal - min recoil!)"
            elif remainder == 0:
                notes = f"{hp} % 10 = 0 (worst - max recoil)"
            else:
                notes = f"{hp} % 10 = {remainder}"

        elif category == "heal_4":
            recovery = hp // 4
            remainder = hp % 4
            if remainder == 0:
                notes = f"{hp} % 4 = 0 (optimal!)"
            else:
                notes = f"{hp} % 4 = {remainder}"

        results.append({
            "ev": ev,
            "hp_stat": hp,
            "score": round(score, 3),
            "recovery_per_turn": recovery,
            "notes": notes,
        })

    # Sort by score descending, then by ev ascending (fewer EVs preferred)
    results.sort(key=lambda x: (-x["score"], x["ev"]))
    return results


def adjust_hp_evs_for_item(
    base_hp: int,
    current_hp_evs: int,
    item: str,
    max_adjustment: int = 8,
    iv: int = 31,
    level: int = 50,
) -> dict:
    """Adjust HP EVs to the nearest optimal number for the given item.

    Looks within ±max_adjustment EVs of the current allocation to find
    a better HP number. Only suggests changes that are valid EV breakpoints.

    Args:
        base_hp: Base HP stat
        current_hp_evs: Current HP EV allocation
        item: Item name (e.g., "leftovers", "life-orb")
        max_adjustment: Maximum EV adjustment allowed (default 8)
        iv: HP IV (default 31)
        level: Pokemon level (default 50)

    Returns:
        Dict with adjustment info:
        {"adjusted_evs": int, "original_hp": int, "adjusted_hp": int,
         "improvement": str, "ev_cost": int, "score_before": float,
         "score_after": float}
    """
    category = _get_item_category(item)
    original_hp = calculate_hp(base_hp, iv, current_hp_evs, level)
    original_score = score_hp_for_item(original_hp, item)

    # If no optimization relevant or already perfect, return unchanged
    if category is None or original_score == 1.0:
        return {
            "adjusted_evs": current_hp_evs,
            "original_hp": original_hp,
            "adjusted_hp": original_hp,
            "improvement": (
                "Already optimal" if original_score == 1.0
                else "No optimization for this item"
            ),
            "ev_cost": 0,
            "score_before": round(original_score, 3),
            "score_after": round(original_score, 3),
        }

    # Try all valid EV breakpoints within range
    best_ev = current_hp_evs
    best_score = original_score
    best_hp = original_hp

    for ev in EV_BREAKPOINTS_LV50:
        if ev < 0 or ev > 252:
            continue
        if abs(ev - current_hp_evs) > max_adjustment:
            continue

        hp = calculate_hp(base_hp, iv, ev, level)
        score = score_hp_for_item(hp, item)

        if score > best_score:
            best_score = score
            best_ev = ev
            best_hp = hp
        elif score == best_score and abs(ev - current_hp_evs) < abs(best_ev - current_hp_evs):
            # Prefer smaller adjustment when scores are equal
            best_ev = ev
            best_hp = hp

    ev_cost = best_ev - current_hp_evs
    if best_ev == current_hp_evs:
        improvement = "No better HP number within adjustment range"
    else:
        # Describe the improvement
        if category == "recovery_16":
            old_recovery = original_hp // 16
            new_recovery = best_hp // 16
            if new_recovery > old_recovery:
                diff = new_recovery - old_recovery
                improvement = f"+{diff} HP recovery/turn ({old_recovery} -> {new_recovery})"
            else:
                improvement = f"Better Leftovers number ({best_hp} % 16 = {best_hp % 16})"
        elif category == "recoil_10":
            old_recoil = original_hp // 10
            new_recoil = best_hp // 10
            if new_recoil < old_recoil:
                diff = old_recoil - new_recoil
                improvement = f"-{diff} recoil/attack ({old_recoil} -> {new_recoil})"
            else:
                improvement = f"Better Life Orb number ({best_hp} % 10 = {best_hp % 10})"
        elif category == "heal_4":
            old_heal = original_hp // 4
            new_heal = best_hp // 4
            if new_heal > old_heal:
                improvement = f"+{new_heal - old_heal} Sitrus heal ({old_heal} -> {new_heal})"
            else:
                improvement = f"Better Sitrus number ({best_hp} % 4 = {best_hp % 4})"
        else:
            improvement = f"HP adjusted from {original_hp} to {best_hp}"

    return {
        "adjusted_evs": best_ev,
        "original_hp": original_hp,
        "adjusted_hp": best_hp,
        "improvement": improvement,
        "ev_cost": ev_cost,
        "score_before": round(original_score, 3),
        "score_after": round(best_score, 3),
    }
