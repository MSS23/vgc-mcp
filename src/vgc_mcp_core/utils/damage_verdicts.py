"""Accurate damage verdict generation for VGC MCP tools.

This module provides mathematically correct KO analysis descriptions,
avoiding misleading statements like "clean 2HKO" when the math doesn't add up.
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class DamageVerdict:
    """Structured damage analysis result."""
    min_percent: float
    max_percent: float
    verdict: str           # Short label: "Guaranteed OHKO", "2HKO", "3HKO", "Chip"
    description: str       # Full explanation
    chip_needed: Optional[float] = None  # How much prior damage needed for KO
    is_guaranteed: bool = False


@dataclass
class KOProbability:
    """Detailed KO probability analysis."""
    ohko_chance: float
    twohko_chance: float
    threehko_chance: float
    fourhko_chance: float
    guaranteed_ko: Optional[int]  # 1=OHKO, 2=2HKO, etc. None if >4HKO
    rolls_that_ohko: int
    verdict: str  # e.g., "87.5% chance to 2HKO"
    total_combinations: int = 16  # 16 for single-hit, 16^n for multi-hit


def calculate_ko_probability(
    damage_rolls: list[int],
    defender_hp: int,
    max_hits: int = 4
) -> KOProbability:
    """
    Calculate actual KO probabilities based on damage roll distribution.

    Pokemon uses 16 damage rolls (0.85x to 1.00x), each equally likely.
    This function calculates exact probabilities by checking all combinations.

    Args:
        damage_rolls: List of 16 damage values (one per roll)
        defender_hp: Defender's HP
        max_hits: Maximum hits to calculate (default 4)

    Returns:
        KOProbability with exact chances for OHKO, 2HKO, 3HKO, 4HKO
    """
    n_rolls = len(damage_rolls)
    if n_rolls == 0:
        return KOProbability(
            ohko_chance=0, twohko_chance=0, threehko_chance=0, fourhko_chance=0,
            guaranteed_ko=None, rolls_that_ohko=0, verdict="No damage"
        )

    # OHKO: Count rolls that deal >= HP
    ohko_count = sum(1 for r in damage_rolls if r >= defender_hp)
    ohko_chance = (ohko_count / n_rolls) * 100

    # 2HKO: Check all 256 combinations (16 x 16)
    twohko_count = 0
    for r1 in damage_rolls:
        for r2 in damage_rolls:
            if r1 + r2 >= defender_hp:
                twohko_count += 1
    twohko_chance = (twohko_count / (n_rolls ** 2)) * 100

    # 3HKO: Check all 4096 combinations (16^3)
    threehko_count = 0
    for r1 in damage_rolls:
        for r2 in damage_rolls:
            for r3 in damage_rolls:
                if r1 + r2 + r3 >= defender_hp:
                    threehko_count += 1
    threehko_chance = (threehko_count / (n_rolls ** 3)) * 100

    # 4HKO: Check all 65536 combinations (16^4)
    fourhko_count = 0
    for r1 in damage_rolls:
        for r2 in damage_rolls:
            for r3 in damage_rolls:
                for r4 in damage_rolls:
                    if r1 + r2 + r3 + r4 >= defender_hp:
                        fourhko_count += 1
    fourhko_chance = (fourhko_count / (n_rolls ** 4)) * 100

    # Determine guaranteed KO (using minimum roll)
    min_damage = min(damage_rolls)
    guaranteed_ko = None
    if min_damage >= defender_hp:
        guaranteed_ko = 1
    elif min_damage * 2 >= defender_hp:
        guaranteed_ko = 2
    elif min_damage * 3 >= defender_hp:
        guaranteed_ko = 3
    elif min_damage * 4 >= defender_hp:
        guaranteed_ko = 4

    # Generate human-readable verdict
    verdict = _format_ko_verdict(
        ohko_chance, twohko_chance, threehko_chance, fourhko_chance, guaranteed_ko
    )

    return KOProbability(
        ohko_chance=round(ohko_chance, 2),
        twohko_chance=round(twohko_chance, 2),
        threehko_chance=round(threehko_chance, 2),
        fourhko_chance=round(fourhko_chance, 2),
        guaranteed_ko=guaranteed_ko,
        rolls_that_ohko=ohko_count,
        verdict=verdict
    )


def calculate_multi_hit_ko_probability(
    damages_per_hit: list[int],
    hit_count: int,
    defender_hp: int
) -> KOProbability:
    """
    Calculate exact KO probability for multi-hit moves.

    Each hit has independent random roll, so we must check all
    16^hit_count combinations.

    Args:
        damages_per_hit: 16 possible damage values per hit (one per random factor)
        hit_count: Number of hits
        defender_hp: Defender's HP

    Returns:
        KOProbability with exact percentages
    """
    from itertools import product

    combos_that_ko = 0
    total_combos = len(damages_per_hit) ** hit_count

    # Generate all possible damage combinations
    for combo in product(damages_per_hit, repeat=hit_count):
        total_damage = sum(combo)
        if total_damage >= defender_hp:
            combos_that_ko += 1

    ohko_chance = (combos_that_ko / total_combos) * 100

    # Determine if it's a guaranteed KO
    guaranteed_ko = 1 if combos_that_ko == total_combos else None

    # Generate verdict
    if guaranteed_ko == 1:
        verdict = "Guaranteed OHKO"
    elif ohko_chance >= 99.9:
        verdict = "Guaranteed OHKO"
    elif ohko_chance > 0:
        verdict = f"{ohko_chance:.2f}% chance to OHKO"
    else:
        verdict = "Does not KO"

    # For multi-hit moves, 2HKO/3HKO don't apply (it's all-or-nothing)
    return KOProbability(
        ohko_chance=round(ohko_chance, 2),
        twohko_chance=0.0,
        threehko_chance=0.0,
        fourhko_chance=0.0,
        guaranteed_ko=guaranteed_ko,
        rolls_that_ohko=combos_that_ko,
        verdict=verdict,
        total_combinations=total_combos
    )


def _format_ko_verdict(
    ohko: float,
    twohko: float,
    threehko: float,
    fourhko: float,
    guaranteed: Optional[int]
) -> str:
    """Format KO probabilities into a human-readable verdict."""
    if guaranteed == 1:
        return "Guaranteed OHKO"
    elif ohko >= 99.9:
        return "Guaranteed OHKO"
    elif ohko > 0:
        return f"{ohko:.2f}% chance to OHKO"
    elif guaranteed == 2:
        return "Guaranteed 2HKO"
    elif twohko >= 99.9:
        return "Guaranteed 2HKO"
    elif twohko > 0:
        return f"{twohko:.2f}% chance to 2HKO"
    elif guaranteed == 3:
        return "Guaranteed 3HKO"
    elif threehko >= 99.9:
        return "Guaranteed 3HKO"
    elif threehko > 0:
        return f"{threehko:.2f}% chance to 3HKO"
    elif guaranteed == 4:
        return "Guaranteed 4HKO"
    elif fourhko >= 99.9:
        return "Guaranteed 4HKO"
    elif fourhko > 0:
        return f"{fourhko:.2f}% chance to 4HKO"
    else:
        return "5+ HKO"


def calculate_ko_verdict(
    min_percent: float,
    max_percent: float,
    include_prior_damage_calc: bool = True
) -> DamageVerdict:
    """
    Generate accurate KO verdict based on damage percentages.

    The math:
    - Guaranteed OHKO: min_percent >= 100%
    - Possible OHKO: max_percent >= 100% but min_percent < 100%
    - Guaranteed 2HKO: min_percent >= 50% (two min rolls >= 100%)
    - Possible 2HKO: max_percent >= 50% but min_percent < 50%
    - Guaranteed 3HKO: min_percent >= 34% (three min rolls >= 102%)
    - etc.

    Args:
        min_percent: Minimum damage roll percentage
        max_percent: Maximum damage roll percentage
        include_prior_damage_calc: Whether to calculate chip damage needed

    Returns:
        DamageVerdict with accurate description
    """
    # OHKO analysis
    if min_percent >= 100:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Guaranteed OHKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Guaranteed OHKO",
            is_guaranteed=True
        )

    if max_percent >= 100:
        # Calculate OHKO chance (simplified - assumes uniform distribution)
        ohko_chance = ((max_percent - 100) / (max_percent - min_percent)) * 100 if max_percent > min_percent else 100
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Possible OHKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - {ohko_chance:.0f}% chance to OHKO",
            chip_needed=100 - min_percent if include_prior_damage_calc else None,
            is_guaranteed=False
        )

    # 2HKO analysis
    two_hit_min = min_percent * 2
    two_hit_max = max_percent * 2

    if min_percent >= 50:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Guaranteed 2HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Guaranteed 2HKO",
            is_guaranteed=True
        )

    if max_percent >= 50:
        # Can 2HKO with good rolls, calculate chip needed for guarantee
        chip_for_2hko = 100 - two_hit_min if include_prior_damage_calc else None
        if chip_for_2hko and chip_for_2hko > 0:
            return DamageVerdict(
                min_percent=min_percent,
                max_percent=max_percent,
                verdict="Possible 2HKO",
                description=f"{min_percent:.0f}-{max_percent:.0f}% - 2HKO with good rolls, needs ~{chip_for_2hko:.0f}% chip to guarantee",
                chip_needed=chip_for_2hko,
                is_guaranteed=False
            )
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Possible 2HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Possible 2HKO with high rolls",
            is_guaranteed=False
        )

    # 3HKO analysis
    three_hit_min = min_percent * 3
    three_hit_max = max_percent * 3

    if min_percent >= 34:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Guaranteed 3HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Guaranteed 3HKO",
            is_guaranteed=True
        )

    if max_percent >= 34:
        chip_for_3hko = 100 - three_hit_min if include_prior_damage_calc else None
        if chip_for_3hko and chip_for_3hko > 0:
            return DamageVerdict(
                min_percent=min_percent,
                max_percent=max_percent,
                verdict="Possible 3HKO",
                description=f"{min_percent:.0f}-{max_percent:.0f}% - 3HKO range, needs ~{chip_for_3hko:.0f}% prior damage to guarantee",
                chip_needed=chip_for_3hko,
                is_guaranteed=False
            )
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="Possible 3HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - Possible 3HKO",
            is_guaranteed=False
        )

    # 4HKO or worse - just chip damage
    if max_percent >= 25:
        return DamageVerdict(
            min_percent=min_percent,
            max_percent=max_percent,
            verdict="4HKO",
            description=f"{min_percent:.0f}-{max_percent:.0f}% - 4HKO range, chip damage",
            is_guaranteed=False
        )

    # Minimal chip
    return DamageVerdict(
        min_percent=min_percent,
        max_percent=max_percent,
        verdict="Chip",
        description=f"{min_percent:.0f}-{max_percent:.0f}% - Minor chip damage only",
        is_guaranteed=False
    )


def format_matchup_verdict(
    min_percent: float,
    max_percent: float,
    attacker_faster: bool = False,
    defender_survives_counter: bool = True,
    move_name: Optional[str] = None
) -> str:
    """
    Generate a comprehensive matchup verdict for display.

    Args:
        min_percent: Minimum damage percentage
        max_percent: Maximum damage percentage
        attacker_faster: Whether the attacker outspeeds
        defender_survives_counter: Whether attacker survives the counterattack
        move_name: Name of the move used

    Returns:
        Human-readable matchup summary
    """
    verdict = calculate_ko_verdict(min_percent, max_percent)

    parts = []
    if move_name:
        parts.append(move_name)

    parts.append(verdict.description)

    if attacker_faster and verdict.verdict in ["Guaranteed OHKO", "Possible OHKO"]:
        parts.append("(you move first)")
    elif not attacker_faster and verdict.verdict in ["Guaranteed OHKO", "Possible OHKO"]:
        parts.append("(but they move first)")

    if not defender_survives_counter and verdict.verdict not in ["Guaranteed OHKO"]:
        parts.append("- WARNING: You get KO'd back")

    return " ".join(parts)


# Commonly misused descriptions to avoid
MISLEADING_TERMS = {
    "clean 2HKO": "Use 'Guaranteed 2HKO' only when min% >= 50",
    "solid 2HKO": "Use 'Guaranteed 2HKO' only when min% >= 50",
    "easy 2HKO": "Use 'Guaranteed 2HKO' only when min% >= 50",
    "clean OHKO": "Use 'Guaranteed OHKO' only when min% >= 100",
}


def format_secondary_effect_note(
    move_name: str,
    effect: str,
    chance: int,
    is_relevant: bool = True
) -> str:
    """
    Generate a note about a move's secondary effect.

    Args:
        move_name: Name of the move
        effect: Effect type (burn, paralysis, etc.)
        chance: Effect chance percentage
        is_relevant: Whether the effect matters in context

    Returns:
        Human-readable note about the effect
    """
    effect_impact = {
        "burn": "halves physical damage output",
        "paralysis": "25% full paralysis chance, halves Speed",
        "freeze": "target cannot act until thawed",
        "poison": "1/8 HP damage per turn",
        "badly_poison": "increasing damage each turn",
        "flinch": "target loses their turn (if you're faster)",
        "confusion": "50% chance to hit self",
        "sleep": "target cannot act for 1-3 turns",
        "stat_drop": "affects future damage calculations",
    }

    impact = effect_impact.get(effect, "")

    if chance == 100:
        return f"[!] {move_name.title()} always {effect}s - {impact}"
    elif chance >= 30:
        return f"[!] {move_name.title()} has {chance}% {effect} chance - {impact}"
    else:
        return f"Note: {move_name.title()} has {chance}% {effect} chance"


def enhance_verdict_with_effect(
    base_verdict: DamageVerdict,
    move_name: str,
    secondary_effect: Optional[tuple[str, int]] = None
) -> DamageVerdict:
    """
    Enhance a damage verdict with secondary effect info.

    Args:
        base_verdict: The base damage verdict
        move_name: Name of the move
        secondary_effect: Tuple of (effect_type, chance) or None

    Returns:
        Enhanced DamageVerdict with effect note in description
    """
    if not secondary_effect:
        return base_verdict

    effect_type, chance = secondary_effect

    # Add effect note to description
    effect_note = format_secondary_effect_note(move_name, effect_type, chance)

    enhanced_desc = f"{base_verdict.description}. {effect_note}"

    return DamageVerdict(
        min_percent=base_verdict.min_percent,
        max_percent=base_verdict.max_percent,
        verdict=base_verdict.verdict,
        description=enhanced_desc,
        chip_needed=base_verdict.chip_needed,
        is_guaranteed=base_verdict.is_guaranteed
    )


def format_terrain_note(
    terrain: str,
    move_type: str,
    attacker_grounded: bool = True,
    defender_grounded: bool = True
) -> Optional[str]:
    """
    Generate a note about terrain impact on damage.

    Args:
        terrain: Active terrain (electric, grassy, psychic, misty)
        move_type: Type of the move
        attacker_grounded: Whether attacker is grounded
        defender_grounded: Whether defender is grounded

    Returns:
        Note about terrain effect, or None if no impact
    """
    terrain = terrain.lower() if terrain else None
    move_type = move_type.lower() if move_type else None

    if not terrain:
        return None

    # Attacker must be grounded for offensive terrain boosts
    if terrain == "electric" and move_type == "electric":
        if attacker_grounded:
            return "[TERRAIN] Electric Terrain: +30% Electric damage"
        return "Note: Electric Terrain active but attacker not grounded"

    if terrain == "grassy" and move_type == "grass":
        if attacker_grounded:
            return "[TERRAIN] Grassy Terrain: +30% Grass damage"
        return "Note: Grassy Terrain active but attacker not grounded"

    if terrain == "psychic" and move_type == "psychic":
        if attacker_grounded:
            return "[TERRAIN] Psychic Terrain: +30% Psychic damage"
        return "Note: Psychic Terrain active but attacker not grounded"

    # Misty terrain affects defender
    if terrain == "misty" and move_type == "dragon":
        if defender_grounded:
            return "[TERRAIN] Misty Terrain: -50% Dragon damage (defender grounded)"
        return "Note: Misty Terrain active but defender not grounded"

    # Grassy terrain reduces ground moves
    if terrain == "grassy" and move_type in ["ground"]:
        if defender_grounded:
            return "[TERRAIN] Grassy Terrain: -50% Earthquake/Bulldoze damage"

    return None
