"""Mathematical bulk optimization with diminishing returns analysis.

This module provides optimal HP/Def/SpD distribution based on
the mathematical principle that Effective Bulk = HP * Defense.

Key insight: Diminishing returns mean that for maximum bulk:
- High base HP Pokemon should invest more in defenses
- High base Def/SpD Pokemon should invest more in HP
- Optimal point is when marginal gains are equal

Formula: Effective Physical Bulk = HP * Defense
         Effective Special Bulk = HP * Special Defense

When optimizing: d(HP*Def)/d(EV) should be equal across all three stats
This means: HP stat should roughly equal Defense stat for optimal bulk
"""

from dataclasses import dataclass
from typing import Optional
import math

from ..models.pokemon import Nature, NATURE_MODIFIERS
from ..config import EV_BREAKPOINTS_LV50, normalize_evs


@dataclass
class BulkOptimizationResult:
    """Result of bulk optimization calculation."""
    hp_evs: int
    def_evs: int
    spd_evs: int
    final_hp: int
    final_def: int
    final_spd: int
    physical_bulk: int   # HP * Def
    special_bulk: int    # HP * SpD
    total_bulk: int      # Combined bulk score
    efficiency_score: float  # How optimal this distribution is (0-1)
    explanation: str
    comparison: Optional[dict] = None  # Comparison to naive distribution


def get_nature_modifier(nature_name: str, stat: str) -> float:
    """Get nature modifier for a specific stat."""
    nature_name_lower = nature_name.lower().strip()

    for nature in Nature:
        if nature.value == nature_name_lower:
            mods = NATURE_MODIFIERS.get(nature, {})
            return mods.get(stat, 1.0)

    return 1.0


def calculate_hp(base: int, ev: int, iv: int = 31, level: int = 50) -> int:
    """Calculate HP stat at level 50."""
    if base == 1:  # Shedinja
        return 1
    return math.floor((2 * base + iv + ev // 4) * level / 100 + level + 10)


def calculate_defense_stat(
    base: int,
    ev: int,
    nature_mod: float = 1.0,
    iv: int = 31,
    level: int = 50
) -> int:
    """Calculate Def or SpD stat at level 50."""
    inner = math.floor((2 * base + iv + ev // 4) * level / 100)
    return math.floor((inner + 5) * nature_mod)


def calculate_effective_bulk(hp: int, defense: int) -> int:
    """Calculate effective bulk (HP * Defense product)."""
    return hp * defense


def find_optimal_hp_def_ratio(
    base_hp: int,
    base_def: int,
    nature_mod_def: float,
    total_evs: int
) -> tuple[int, int]:
    """
    Find the mathematically optimal HP/Def EV split.

    The optimal point is where the marginal gains are equal.
    For HP*Def maximization: d(HP*Def)/dHP_EV = d(HP*Def)/dDef_EV

    This works out to roughly: final_HP ≈ final_Def (with adjustments for nature)

    Args:
        base_hp: Base HP stat
        base_def: Base Defense stat
        nature_mod_def: Nature modifier for defense (0.9, 1.0, or 1.1)
        total_evs: Total EVs to distribute between HP and Def

    Returns:
        Tuple of (hp_evs, def_evs)
    """
    best_bulk = 0
    best_hp_evs = 0
    best_def_evs = 0

    # Try all valid EV distributions (level 50 breakpoints: 0, 4, 12, 20, 28...)
    for hp_evs in EV_BREAKPOINTS_LV50:
        if hp_evs > min(252, total_evs):
            break
        def_evs = normalize_evs(total_evs - hp_evs)
        if def_evs < 0 or def_evs > 252:
            continue

        hp = calculate_hp(base_hp, hp_evs)
        defense = calculate_defense_stat(base_def, def_evs, nature_mod_def)
        bulk = calculate_effective_bulk(hp, defense)

        if bulk > best_bulk:
            best_bulk = bulk
            best_hp_evs = hp_evs
            best_def_evs = def_evs

    return best_hp_evs, best_def_evs


def calculate_optimal_bulk_distribution(
    base_hp: int,
    base_def: int,
    base_spd: int,
    nature: str,
    total_bulk_evs: int = 252,
    defense_weight: float = 0.5,
    existing_hp_evs: int = 0,
    existing_def_evs: int = 0,
    existing_spd_evs: int = 0
) -> BulkOptimizationResult:
    """
    Find mathematically optimal HP/Def/SpD distribution using diminishing returns.

    The key insight is that effective bulk = HP * Defense, so we want to
    maximize this product. Due to diminishing returns, dumping all EVs into
    one stat is suboptimal.

    Mathematical principle:
    - If base HP is high, invest more in defenses (HP has diminishing returns)
    - If base Def is high, invest more in HP (Def has diminishing returns)
    - Nature boosts reduce the need for EVs in that stat

    Args:
        base_hp: Base HP stat
        base_def: Base Defense stat
        base_spd: Base Special Defense stat
        nature: Nature name (e.g., "Bold", "Calm")
        total_bulk_evs: Total EVs to distribute (default 252)
        defense_weight: 0.0 = all SpD, 0.5 = balanced, 1.0 = all Def
        existing_hp_evs: EVs already invested in HP
        existing_def_evs: EVs already invested in Defense
        existing_spd_evs: EVs already invested in Special Defense

    Returns:
        BulkOptimizationResult with optimal distribution and analysis
    """
    nature_mod_def = get_nature_modifier(nature, "defense")
    nature_mod_spd = get_nature_modifier(nature, "special_defense")

    # Calculate how much to allocate to physical vs special bulk
    phys_evs = int(total_bulk_evs * defense_weight)
    spec_evs = total_bulk_evs - phys_evs

    # Find optimal HP/Def split for physical bulk
    # We need to decide how much HP goes to physical vs special
    # The mathematically optimal split shares HP between both

    best_result = None
    best_total_bulk = 0

    # Try different HP allocations (level 50 breakpoints: 0, 4, 12, 20, 28...)
    for hp_evs in EV_BREAKPOINTS_LV50:
        if hp_evs > min(252, total_bulk_evs):
            break
        remaining = total_bulk_evs - hp_evs

        # Split remaining between Def and SpD based on weight
        def_evs = int(remaining * defense_weight)
        spd_evs = remaining - def_evs

        # Ensure valid EV amounts (level 50 breakpoints, max 252)
        def_evs = normalize_evs(def_evs)
        spd_evs = normalize_evs(spd_evs)
        hp_evs = min(252, hp_evs)

        # Recalculate to ensure total is correct
        actual_total = hp_evs + def_evs + spd_evs

        # Calculate stats
        hp = calculate_hp(base_hp, hp_evs + existing_hp_evs)
        defense = calculate_defense_stat(base_def, def_evs + existing_def_evs, nature_mod_def)
        sp_defense = calculate_defense_stat(base_spd, spd_evs + existing_spd_evs, nature_mod_spd)

        # Calculate bulk scores
        phys_bulk = calculate_effective_bulk(hp, defense)
        spec_bulk = calculate_effective_bulk(hp, sp_defense)

        # Combined bulk (weighted)
        total_bulk = int(phys_bulk * defense_weight + spec_bulk * (1 - defense_weight))

        if total_bulk > best_total_bulk:
            best_total_bulk = total_bulk
            best_result = {
                "hp_evs": hp_evs,
                "def_evs": def_evs,
                "spd_evs": spd_evs,
                "final_hp": hp,
                "final_def": defense,
                "final_spd": sp_defense,
                "phys_bulk": phys_bulk,
                "spec_bulk": spec_bulk
            }

    if not best_result:
        # Fallback to simple split
        hp_evs = total_bulk_evs // 2
        def_evs = int((total_bulk_evs - hp_evs) * defense_weight)
        spd_evs = total_bulk_evs - hp_evs - def_evs

        best_result = {
            "hp_evs": hp_evs,
            "def_evs": def_evs,
            "spd_evs": spd_evs,
            "final_hp": calculate_hp(base_hp, hp_evs),
            "final_def": calculate_defense_stat(base_def, def_evs, nature_mod_def),
            "final_spd": calculate_defense_stat(base_spd, spd_evs, nature_mod_spd),
            "phys_bulk": 0,
            "spec_bulk": 0
        }
        best_result["phys_bulk"] = best_result["final_hp"] * best_result["final_def"]
        best_result["spec_bulk"] = best_result["final_hp"] * best_result["final_spd"]

    # Calculate comparison to naive distribution (all HP or all Def)
    naive_hp = calculate_hp(base_hp, total_bulk_evs)
    naive_hp_def = calculate_defense_stat(base_def, 0, nature_mod_def)
    naive_hp_bulk = naive_hp * naive_hp_def

    naive_def = calculate_defense_stat(base_def, total_bulk_evs, nature_mod_def)
    naive_def_hp = calculate_hp(base_hp, 0)
    naive_def_bulk = naive_def_hp * naive_def

    optimal_bulk = best_result["phys_bulk"]
    naive_best = max(naive_hp_bulk, naive_def_bulk)

    efficiency = optimal_bulk / naive_best if naive_best > 0 else 1.0

    # Generate explanation
    hp_ratio = best_result["final_hp"] / best_result["final_def"] if best_result["final_def"] > 0 else 1
    explanation_parts = []

    if base_hp > base_def + 20:
        explanation_parts.append(f"High base HP ({base_hp}) means investing more in Defense is efficient")
    elif base_def > base_hp + 20:
        explanation_parts.append(f"High base Defense ({base_def}) means investing more in HP is efficient")
    else:
        explanation_parts.append(f"Balanced bases ({base_hp} HP, {base_def} Def) benefit from split investment")

    if nature_mod_def == 1.1:
        explanation_parts.append("Defense-boosting nature reduces need for Defense EVs")
    elif nature_mod_spd == 1.1:
        explanation_parts.append("SpD-boosting nature reduces need for SpD EVs")

    if efficiency > 1.05:
        explanation_parts.append(f"Optimal distribution is {(efficiency-1)*100:.1f}% more efficient than single-stat investment")

    comparison = {
        "all_hp_bulk": naive_hp_bulk,
        "all_def_bulk": naive_def_bulk,
        "optimal_bulk": optimal_bulk,
        "efficiency_gain_vs_all_hp": round((optimal_bulk / naive_hp_bulk - 1) * 100, 1) if naive_hp_bulk > 0 else 0,
        "efficiency_gain_vs_all_def": round((optimal_bulk / naive_def_bulk - 1) * 100, 1) if naive_def_bulk > 0 else 0
    }

    return BulkOptimizationResult(
        hp_evs=best_result["hp_evs"],
        def_evs=best_result["def_evs"],
        spd_evs=best_result["spd_evs"],
        final_hp=best_result["final_hp"],
        final_def=best_result["final_def"],
        final_spd=best_result["final_spd"],
        physical_bulk=best_result["phys_bulk"],
        special_bulk=best_result["spec_bulk"],
        total_bulk=int(best_result["phys_bulk"] * defense_weight + best_result["spec_bulk"] * (1 - defense_weight)),
        efficiency_score=round(efficiency, 3),
        explanation=" | ".join(explanation_parts),
        comparison=comparison
    )


def optimize_for_survival(
    base_hp: int,
    base_def: int,
    base_spd: int,
    nature: str,
    incoming_damage: int,
    is_physical: bool = True,
    total_evs: int = 508
) -> BulkOptimizationResult:
    """
    Optimize bulk EVs to survive a specific damage amount.

    Finds the minimum EVs needed to survive, leaving remaining EVs
    for other stats.

    Args:
        base_hp: Base HP stat
        base_def: Base Defense stat
        base_spd: Base Special Defense stat
        nature: Nature name
        incoming_damage: The damage amount to survive
        is_physical: If True, optimize for physical bulk; else special
        total_evs: Total EVs available to use

    Returns:
        BulkOptimizationResult with survival-optimized distribution
    """
    nature_mod_def = get_nature_modifier(nature, "defense")
    nature_mod_spd = get_nature_modifier(nature, "special_defense")

    base_defense = base_def if is_physical else base_spd
    nature_mod = nature_mod_def if is_physical else nature_mod_spd

    # Find minimum EVs to survive
    # Survival requires: HP > incoming_damage
    # But effective HP = HP * (1 + Defense/X) approximately

    min_hp_evs = 0
    min_def_evs = 0
    found = False

    for hp_evs in EV_BREAKPOINTS_LV50:
        if hp_evs > min(252, total_evs):
            break
        for def_evs in EV_BREAKPOINTS_LV50:
            if def_evs > min(252, total_evs - hp_evs):
                break
            hp = calculate_hp(base_hp, hp_evs)
            defense = calculate_defense_stat(base_defense, def_evs, nature_mod)

            # Rough survival check (actual formula is more complex)
            if hp > incoming_damage:
                min_hp_evs = hp_evs
                min_def_evs = def_evs
                found = True
                break
        if found:
            break

    # Use remaining EVs optimally
    remaining_evs = total_evs - min_hp_evs - min_def_evs

    if is_physical:
        return calculate_optimal_bulk_distribution(
            base_hp, base_def, base_spd, nature,
            total_bulk_evs=remaining_evs,
            defense_weight=1.0,  # Focus on physical
            existing_hp_evs=min_hp_evs,
            existing_def_evs=min_def_evs
        )
    else:
        return calculate_optimal_bulk_distribution(
            base_hp, base_def, base_spd, nature,
            total_bulk_evs=remaining_evs,
            defense_weight=0.0,  # Focus on special
            existing_hp_evs=min_hp_evs,
            existing_spd_evs=min_def_evs
        )


def calculate_marginal_gain(
    base_stat: int,
    current_evs: int,
    stat_type: str,
    nature_mod: float = 1.0
) -> float:
    """
    Calculate marginal gain from adding 4 more EVs.

    This shows the diminishing returns as EVs increase.

    Args:
        base_stat: Base stat value
        current_evs: Current EV investment
        stat_type: "hp", "defense", or "special_defense"
        nature_mod: Nature modifier for defense stats

    Returns:
        The stat increase from adding 4 more EVs
    """
    if stat_type == "hp":
        current = calculate_hp(base_stat, current_evs)
        next_val = calculate_hp(base_stat, min(252, current_evs + 4))
    else:
        current = calculate_defense_stat(base_stat, current_evs, nature_mod)
        next_val = calculate_defense_stat(base_stat, min(252, current_evs + 4), nature_mod)

    return next_val - current


def analyze_diminishing_returns(
    base_hp: int,
    base_def: int,
    base_spd: int,
    nature: str
) -> dict:
    """
    Analyze diminishing returns for HP, Def, and SpD.

    Shows the "efficiency breakpoints" where investing in
    different stats becomes more/less valuable.

    Returns:
        Dict with marginal gain analysis for each stat
    """
    nature_mod_def = get_nature_modifier(nature, "defense")
    nature_mod_spd = get_nature_modifier(nature, "special_defense")

    analysis = {
        "hp_gains": [],
        "def_gains": [],
        "spd_gains": [],
        "recommendations": []
    }

    # Calculate marginal gains at different EV thresholds
    thresholds = [0, 52, 100, 148, 196, 244, 252]

    for evs in thresholds:
        hp_gain = calculate_marginal_gain(base_hp, evs, "hp")
        def_gain = calculate_marginal_gain(base_def, evs, "defense", nature_mod_def)
        spd_gain = calculate_marginal_gain(base_spd, evs, "special_defense", nature_mod_spd)

        analysis["hp_gains"].append({"evs": evs, "gain": hp_gain})
        analysis["def_gains"].append({"evs": evs, "gain": def_gain})
        analysis["spd_gains"].append({"evs": evs, "gain": spd_gain})

    # Generate recommendations based on base stats
    if base_hp > 100:
        analysis["recommendations"].append(
            f"High base HP ({base_hp}): Consider investing more in defenses"
        )
    elif base_hp < 70:
        analysis["recommendations"].append(
            f"Low base HP ({base_hp}): HP investment is efficient early"
        )

    if base_def > 100 or nature_mod_def == 1.1:
        analysis["recommendations"].append(
            "High Defense: HP investment has better marginal returns"
        )

    if base_spd > 100 or nature_mod_spd == 1.1:
        analysis["recommendations"].append(
            "High SpD: HP investment has better marginal returns"
        )

    return analysis
