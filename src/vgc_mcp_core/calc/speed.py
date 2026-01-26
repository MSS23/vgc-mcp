"""Speed comparison and tier utilities."""

from dataclasses import dataclass
from typing import Optional

from ..models.pokemon import Nature, PokemonBuild
from .stats import calculate_speed, calculate_all_stats, find_speed_evs
from ..config import EV_BREAKPOINTS_LV50


@dataclass
class SpeedComparison:
    """Result of comparing two Pokemon speeds."""
    pokemon1_name: str
    pokemon1_speed: int
    pokemon2_name: str
    pokemon2_speed: int
    difference: int
    result: str  # "pokemon1 outspeeds", "pokemon2 outspeeds", "speed tie"
    notes: list[str]


def compare_speeds(
    pokemon1: PokemonBuild,
    pokemon2: PokemonBuild,
    trick_room: bool = False,
    tailwind_pokemon1: bool = False,
    tailwind_pokemon2: bool = False,
    paralysis_pokemon1: bool = False,
    paralysis_pokemon2: bool = False,
) -> SpeedComparison:
    """
    Compare speeds between two Pokemon with modifiers.

    Args:
        pokemon1: First Pokemon
        pokemon2: Second Pokemon
        trick_room: If True, slower Pokemon moves first
        tailwind_pokemon1: If True, pokemon1 has 2x speed
        tailwind_pokemon2: If True, pokemon2 has 2x speed
        paralysis_pokemon1: If True, pokemon1 has 0.5x speed
        paralysis_pokemon2: If True, pokemon2 has 0.5x speed

    Returns:
        SpeedComparison with result and notes
    """
    stats1 = calculate_all_stats(pokemon1)
    stats2 = calculate_all_stats(pokemon2)

    speed1 = stats1["speed"]
    speed2 = stats2["speed"]

    notes = []

    # Apply modifiers
    effective_speed1 = speed1
    effective_speed2 = speed2

    if tailwind_pokemon1:
        effective_speed1 *= 2
        notes.append(f"{pokemon1.name} has Tailwind (2x)")

    if tailwind_pokemon2:
        effective_speed2 *= 2
        notes.append(f"{pokemon2.name} has Tailwind (2x)")

    if paralysis_pokemon1:
        effective_speed1 = int(effective_speed1 * 0.5)
        notes.append(f"{pokemon1.name} is paralyzed (0.5x)")

    if paralysis_pokemon2:
        effective_speed2 = int(effective_speed2 * 0.5)
        notes.append(f"{pokemon2.name} is paralyzed (0.5x)")

    # Determine result
    if trick_room:
        notes.append("Trick Room is active")
        if effective_speed1 < effective_speed2:
            result = f"{pokemon1.name} moves first (slower in Trick Room)"
        elif effective_speed2 < effective_speed1:
            result = f"{pokemon2.name} moves first (slower in Trick Room)"
        else:
            result = "Speed tie (50/50 in Trick Room)"
    else:
        if effective_speed1 > effective_speed2:
            result = f"{pokemon1.name} outspeeds {pokemon2.name}"
        elif effective_speed2 > effective_speed1:
            result = f"{pokemon2.name} outspeeds {pokemon1.name}"
        else:
            result = "Speed tie (50/50 chance)"

    return SpeedComparison(
        pokemon1_name=pokemon1.name,
        pokemon1_speed=speed1,
        pokemon2_name=pokemon2.name,
        pokemon2_speed=speed2,
        difference=abs(effective_speed1 - effective_speed2),
        result=result,
        notes=notes
    )


def find_speed_evs_to_outspeed(
    base_speed: int,
    target_speed: int,
    nature: Nature = Nature.SERIOUS,
    iv: int = 31,
    level: int = 50,
    by: int = 1
) -> Optional[int]:
    """
    Find minimum EVs to outspeed a target by at least 'by' points.

    Args:
        base_speed: Your Pokemon's base Speed
        target_speed: Target Speed stat to outspeed
        nature: Your Pokemon's nature
        iv: Speed IV
        level: Pokemon level
        by: Minimum points to outspeed by (default 1)

    Returns:
        Minimum EVs needed, or None if impossible
    """
    return find_speed_evs(base_speed, target_speed + by, nature, iv, level)


def find_speed_evs_to_underspeed(
    base_speed: int,
    target_speed: int,
    nature: Nature = Nature.SERIOUS,
    iv: int = 31,
    level: int = 50
) -> Optional[int]:
    """
    Find maximum EVs while staying slower than target (for Trick Room).

    Args:
        base_speed: Your Pokemon's base Speed
        target_speed: Target Speed stat to stay under
        nature: Your Pokemon's nature
        iv: Speed IV
        level: Pokemon level

    Returns:
        Maximum EVs while staying slower, or None if impossible
    """
    # Start from 252 and work down (level 50 breakpoints: 252, 244, 236...)
    for ev in reversed(EV_BREAKPOINTS_LV50):
        speed = calculate_speed(base_speed, iv, ev, level, nature)
        if speed < target_speed:
            return ev

    # Even 0 EVs is too fast, try 0 IV
    speed_0iv = calculate_speed(base_speed, 0, 0, level, nature)
    if speed_0iv < target_speed:
        return 0  # Need to use 0 IV

    return None  # Cannot underspeed


# Common speed benchmarks for VGC - only base speeds stored, calculated dynamically
# All speed values are calculated using the speed formula, not hardcoded
SPEED_BENCHMARKS = {
    # Base speeds only - all other values calculated dynamically
    "regieleki": {"base": 200},
    "electrode-hisui": {"base": 150},
    "dragapult": {"base": 142},
    "iron-bundle": {"base": 136},
    "flutter-mane": {"base": 135},
    "miraidon": {"base": 135},
    "koraidon": {"base": 135},
    "raging-bolt": {"base": 110},
    "chi-yu": {"base": 100},
    "urshifu": {"base": 97},
    "urshifu-rapid-strike": {"base": 97},
    "palafin-hero": {"base": 100},
    "tornadus": {"base": 111},
    "landorus": {"base": 101},
    "landorus-therian": {"base": 91},
    "gholdengo": {"base": 84},
    "rillaboom": {"base": 85},
    "incineroar": {"base": 60},
    "kingambit": {"base": 50},
    "iron-hands": {"base": 50},
    "amoonguss": {"base": 30},
    "dondozo": {"base": 35},
    "ting-lu": {"base": 45},
}


def get_speed_benchmark(pokemon_name: str, benchmark_type: str = "max_positive") -> Optional[int]:
    """
    Get a speed benchmark for a Pokemon, calculated dynamically.
    
    Args:
        pokemon_name: Pokemon name (normalized, e.g., "rillaboom")
        benchmark_type: Type of benchmark:
            - "max_positive": Max speed with +Speed nature (Jolly/Timid), 252 EVs, 31 IV
            - "max_neutral": Max speed with neutral nature, 252 EVs, 31 IV
            - "neutral_0ev": Speed with neutral nature, 0 EVs, 31 IV
            - "min_negative": Min speed with -Speed nature (Brave/Quiet), 0 EVs, 0 IV
    
    Returns:
        Speed stat value or None if Pokemon not found
    """
    data = SPEED_BENCHMARKS.get(pokemon_name.lower().replace(" ", "-"))
    if not data:
        return None
    
    base = data["base"]
    
    if benchmark_type == "max_positive":
        # Use Jolly for physical attackers, Timid for special - default to Jolly
        return calculate_speed(base, 31, 252, 50, Nature.JOLLY)
    elif benchmark_type == "max_neutral":
        return calculate_speed(base, 31, 252, 50, Nature.SERIOUS)
    elif benchmark_type == "neutral_0ev":
        return calculate_speed(base, 31, 0, 50, Nature.SERIOUS)
    elif benchmark_type == "min_negative":
        return calculate_speed(base, 0, 0, 50, Nature.BRAVE)
    
    return None


# VGC Meta Speed Tiers - Common competitive speeds for VGC Pokemon
# This data tracks what speed investments are commonly used in VGC
# paradox_type: "ancient" (Protosynthesis - Sun) or "future" (Quark Drive - Electric Terrain)
# spreads: list of common spreads with nature, evs, and usage percentage
META_SPEED_TIERS = {
    # Ultra fast (200+)
    "regieleki": {
        "base": 200,
        "common_speeds": [277, 252, 200],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 60},
            {"nature": "Modest", "evs": 252, "usage": 30},
            {"nature": "Timid", "evs": 0, "usage": 10},
        ]
    },

    # Very fast (135-150)
    "electrode-hisui": {
        "base": 150,
        "common_speeds": [222, 202],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 70},
            {"nature": "Modest", "evs": 252, "usage": 30},
        ]
    },
    "dragapult": {
        "base": 142,
        "common_speeds": [213, 194],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 50},
            {"nature": "Timid", "evs": 252, "usage": 30},
            {"nature": "Adamant", "evs": 252, "usage": 20},
        ]
    },
    "iron-bundle": {
        "base": 136,
        "paradox_type": "future",
        "common_speeds": [205, 187, 136],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 40},
            {"nature": "Modest", "evs": 0, "usage": 10},
        ]
    },
    "flutter-mane": {
        "base": 135,
        "paradox_type": "ancient",
        "common_speeds": [205, 187, 157],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 44},
            {"nature": "Modest", "evs": 252, "usage": 30},
            {"nature": "Timid", "evs": 100, "usage": 18},
            {"nature": "Timid", "evs": 0, "usage": 8},
        ]
    },
    "miraidon": {
        "base": 135,
        "common_speeds": [205, 187],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 60},
            {"nature": "Modest", "evs": 252, "usage": 40},
        ]
    },
    "koraidon": {
        "base": 135,
        "common_speeds": [205, 187],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "meowscarada": {
        "base": 123,
        "common_speeds": [192, 175],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 80},
            {"nature": "Adamant", "evs": 252, "usage": 20},
        ]
    },
    "chien-pao": {
        "base": 135,
        "common_speeds": [205, 187],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 70},
            {"nature": "Adamant", "evs": 252, "usage": 30},
        ]
    },
    "calyrex-shadow": {
        "base": 150,
        "common_speeds": [222, 202],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 70},
            {"nature": "Modest", "evs": 252, "usage": 30},
        ]
    },

    # Fast (100-120)
    "iron-moth": {
        "base": 110,
        "paradox_type": "future",
        "common_speeds": [178, 162],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 50},
        ]
    },
    "raging-bolt": {
        "base": 110,
        "paradox_type": "ancient",
        "common_speeds": [178, 162, 110],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 25},
            {"nature": "Modest", "evs": 252, "usage": 40},
            {"nature": "Modest", "evs": 0, "usage": 25},
            {"nature": "Quiet", "evs": 0, "usage": 10},
        ]
    },
    "gouging-fire": {
        "base": 110,
        "paradox_type": "ancient",
        "common_speeds": [178, 162],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 100, "usage": 20},
        ]
    },
    "walking-wake": {
        "base": 109,
        "paradox_type": "ancient",
        "common_speeds": [177, 161],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 40},
            {"nature": "Modest", "evs": 252, "usage": 60},
        ]
    },
    "ogerpon": {
        "base": 110,
        "common_speeds": [178, 162],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "ogerpon-wellspring": {
        "base": 110,
        "common_speeds": [178, 162],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "ogerpon-hearthflame": {
        "base": 110,
        "common_speeds": [178, 162],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "ogerpon-cornerstone": {
        "base": 110,
        "common_speeds": [178, 162],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 60},
        ]
    },
    "tornadus": {
        "base": 111,
        "common_speeds": [179, 163],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 70},
            {"nature": "Modest", "evs": 252, "usage": 30},
        ]
    },
    "entei": {
        "base": 100,
        "common_speeds": [167, 152, 136],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 44},
            {"nature": "Adamant", "evs": 252, "usage": 30},
            {"nature": "Jolly", "evs": 0, "usage": 8},
            {"nature": "Adamant", "evs": 0, "usage": 5},
        ]
    },
    "urshifu": {
        "base": 97,
        "common_speeds": [163, 148],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "urshifu-rapid-strike": {
        "base": 97,
        "common_speeds": [163, 148],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "landorus": {
        "base": 101,
        "common_speeds": [168, 153],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 50},
        ]
    },
    "landorus-therian": {
        "base": 91,
        "common_speeds": [157, 143],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 50},
            {"nature": "Adamant", "evs": 100, "usage": 10},
        ]
    },
    "garchomp": {
        "base": 102,
        "common_speeds": [169, 154],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 50},
            {"nature": "Adamant", "evs": 252, "usage": 50},
        ]
    },
    "arcanine": {
        "base": 95,
        "common_speeds": [161, 146, 95],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 30},
            {"nature": "Adamant", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 0, "usage": 30},
        ]
    },
    "arcanine-hisui": {
        "base": 90,
        "common_speeds": [156, 141, 90],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 25},
            {"nature": "Adamant", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 0, "usage": 35},
        ]
    },
    "palafin": {
        "base": 100,
        "common_speeds": [167, 152],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "indeedee-f": {
        "base": 95,
        "common_speeds": [161, 146],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 30},
            {"nature": "Modest", "evs": 252, "usage": 40},
            {"nature": "Bold", "evs": 0, "usage": 30},
        ]
    },

    # Medium (70-95)
    "annihilape": {
        "base": 90,
        "common_speeds": [156, 142],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 60},
        ]
    },
    "gholdengo": {
        "base": 84,
        "common_speeds": [150, 136],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 40},
            {"nature": "Modest", "evs": 252, "usage": 60},
        ]
    },
    "rillaboom": {
        "base": 85,
        "common_speeds": [150, 137, 85],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 20},
            {"nature": "Adamant", "evs": 252, "usage": 50},
            {"nature": "Adamant", "evs": 0, "usage": 30},
        ]
    },
    "dragonite": {
        "base": 80,
        "common_speeds": [145, 132, 80],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 20},
            {"nature": "Adamant", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 0, "usage": 20},
        ]
    },
    "gyarados": {
        "base": 81,
        "common_speeds": [146, 133],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 60},
        ]
    },
    "kyogre": {
        "base": 90,
        "common_speeds": [156, 142],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 30},
            {"nature": "Modest", "evs": 252, "usage": 70},
        ]
    },
    "groudon": {
        "base": 90,
        "common_speeds": [156, 142],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 30},
            {"nature": "Adamant", "evs": 252, "usage": 70},
        ]
    },
    "glimmora": {
        "base": 70,
        "common_speeds": [134, 122],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 50},
        ]
    },
    "great-tusk": {
        "base": 87,
        "paradox_type": "ancient",
        "common_speeds": [152, 139],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 50},
            {"nature": "Adamant", "evs": 252, "usage": 50},
        ]
    },
    "roaring-moon": {
        "base": 119,
        "paradox_type": "ancient",
        "common_speeds": [187, 170],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "iron-valiant": {
        "base": 116,
        "paradox_type": "future",
        "common_speeds": [183, 167],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Timid", "evs": 252, "usage": 30},
            {"nature": "Naive", "evs": 252, "usage": 30},
        ]
    },

    # Slow (50-70)
    "pelipper": {
        "base": 65,
        "common_speeds": [126, 85],
        "spreads": [
            {"nature": "Bold", "evs": 252, "usage": 30},
            {"nature": "Modest", "evs": 0, "usage": 70},
        ]
    },
    "incineroar": {
        "base": 60,
        "common_speeds": [123, 92, 60],
        "spreads": [
            {"nature": "Adamant", "evs": 252, "usage": 20},
            {"nature": "Careful", "evs": 100, "usage": 40},
            {"nature": "Careful", "evs": 0, "usage": 40},
        ]
    },
    "porygon2": {
        "base": 60,
        "common_speeds": [92, 60],
        "spreads": [
            {"nature": "Relaxed", "evs": 0, "usage": 50},
            {"nature": "Sassy", "evs": 0, "usage": 50},
        ]
    },
    "farigiraf": {
        "base": 60,
        "common_speeds": [123, 60],
        "spreads": [
            {"nature": "Modest", "evs": 252, "usage": 30},
            {"nature": "Calm", "evs": 0, "usage": 70},
        ]
    },

    # Very Slow / Trick Room (under 50)
    "kingambit": {
        "base": 50,
        "common_speeds": [70, 50],
        "spreads": [
            {"nature": "Adamant", "evs": 0, "usage": 80},
            {"nature": "Brave", "evs": 0, "usage": 20},
        ]
    },
    "iron-hands": {
        "base": 50,
        "paradox_type": "future",
        "common_speeds": [70, 50],
        "spreads": [
            {"nature": "Adamant", "evs": 0, "usage": 70},
            {"nature": "Brave", "evs": 0, "usage": 30},
        ]
    },
    "ursaluna": {
        "base": 50,
        "common_speeds": [70, 50],
        "spreads": [
            {"nature": "Adamant", "evs": 0, "usage": 60},
            {"nature": "Brave", "evs": 0, "usage": 40},
        ]
    },
    "ursaluna-bloodmoon": {
        "base": 52,
        "common_speeds": [73, 52],
        "spreads": [
            {"nature": "Modest", "evs": 0, "usage": 60},
            {"nature": "Quiet", "evs": 0, "usage": 40},
        ]
    },
    "calyrex-ice": {
        "base": 50,
        "common_speeds": [70, 50, 36],
        "spreads": [
            {"nature": "Adamant", "evs": 0, "usage": 50},
            {"nature": "Brave", "evs": 0, "usage": 50},
        ]
    },
    "dondozo": {
        "base": 35,
        "common_speeds": [75, 35],
        "spreads": [
            {"nature": "Adamant", "evs": 252, "usage": 30},
            {"nature": "Careful", "evs": 0, "usage": 70},
        ]
    },
    "amoonguss": {
        "base": 30,
        "common_speeds": [31, 30],
        "spreads": [
            {"nature": "Relaxed", "evs": 0, "usage": 50},
            {"nature": "Sassy", "evs": 0, "usage": 50},
        ]
    },
    "hatterene": {
        "base": 29,
        "common_speeds": [49, 29],
        "spreads": [
            {"nature": "Quiet", "evs": 0, "usage": 80},
            {"nature": "Modest", "evs": 0, "usage": 20},
        ]
    },
    "torkoal": {
        "base": 20,
        "common_speeds": [40, 20],
        "spreads": [
            {"nature": "Quiet", "evs": 0, "usage": 80},
            {"nature": "Modest", "evs": 0, "usage": 20},
        ]
    },
    "iron-treads": {
        "base": 106,
        "paradox_type": "future",
        "common_speeds": [172, 157],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 50},
            {"nature": "Adamant", "evs": 252, "usage": 50},
        ]
    },
    "iron-thorns": {
        "base": 72,
        "paradox_type": "future",
        "common_speeds": [137, 125],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 60},
        ]
    },
    "iron-jugulis": {
        "base": 108,
        "paradox_type": "future",
        "common_speeds": [175, 159],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 50},
        ]
    },
    "scream-tail": {
        "base": 111,
        "paradox_type": "ancient",
        "common_speeds": [179, 163],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 30},
            {"nature": "Calm", "evs": 252, "usage": 70},
        ]
    },
    "brute-bonnet": {
        "base": 55,
        "paradox_type": "ancient",
        "common_speeds": [108, 75],
        "spreads": [
            {"nature": "Adamant", "evs": 252, "usage": 60},
            {"nature": "Brave", "evs": 0, "usage": 40},
        ]
    },
    "sandy-shocks": {
        "base": 101,
        "paradox_type": "ancient",
        "common_speeds": [168, 153],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 50},
        ]
    },
    "slither-wing": {
        "base": 81,
        "paradox_type": "ancient",
        "common_speeds": [146, 133],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 40},
            {"nature": "Adamant", "evs": 252, "usage": 60},
        ]
    },
    "iron-leaves": {
        "base": 108,
        "paradox_type": "future",
        "common_speeds": [175, 159],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "iron-boulder": {
        "base": 108,
        "paradox_type": "future",
        "common_speeds": [175, 159],
        "spreads": [
            {"nature": "Jolly", "evs": 252, "usage": 60},
            {"nature": "Adamant", "evs": 252, "usage": 40},
        ]
    },
    "iron-crown": {
        "base": 108,
        "paradox_type": "future",
        "common_speeds": [175, 159],
        "spreads": [
            {"nature": "Timid", "evs": 252, "usage": 50},
            {"nature": "Modest", "evs": 252, "usage": 50},
        ]
    },
}


def get_speed_tier_info(pokemon_name: str) -> Optional[dict]:
    """
    Get speed benchmark info for a Pokemon with dynamically calculated values.
    
    Returns dict with base speed and calculated benchmarks.
    """
    name = pokemon_name.lower().replace(" ", "-")
    data = SPEED_BENCHMARKS.get(name)
    if not data:
        return None
    
    base = data["base"]
    return {
        "base": base,
        "max_positive": get_speed_benchmark(name, "max_positive"),
        "max_neutral": get_speed_benchmark(name, "max_neutral"),
        "neutral_0ev": get_speed_benchmark(name, "neutral_0ev"),
        "min_negative": get_speed_benchmark(name, "min_negative"),
    }


def get_meta_speed_tier(pokemon_name: str) -> Optional[dict]:
    """
    Get VGC meta speed tier info for a Pokemon with dynamically calculated speeds.
    
    Calculates common_speeds from spreads data instead of using hardcoded values.
    """
    name = pokemon_name.lower().replace(" ", "-")

    # Normalize Ogerpon mask form names (e.g., "ogerpon-wellspring-mask" -> "ogerpon-wellspring")
    if name.endswith("-mask"):
        name = name.replace("-mask", "")

    data = META_SPEED_TIERS.get(name)
    if not data:
        return None
    
    # Calculate common_speeds dynamically from spreads if available
    if "spreads" in data and "base" in data:
        base = data["base"]
        calculated_speeds = []
        speed_set = set()
        
        # Nature name -> Nature enum mapping
        NATURE_MAP = {
            "adamant": Nature.ADAMANT, "bashful": Nature.BASHFUL, "bold": Nature.BOLD,
            "brave": Nature.BRAVE, "calm": Nature.CALM, "careful": Nature.CAREFUL,
            "docile": Nature.DOCILE, "gentle": Nature.GENTLE, "hardy": Nature.HARDY,
            "hasty": Nature.HASTY, "impish": Nature.IMPISH, "jolly": Nature.JOLLY,
            "lax": Nature.LAX, "lonely": Nature.LONELY, "mild": Nature.MILD,
            "modest": Nature.MODEST, "naive": Nature.NAIVE, "naughty": Nature.NAUGHTY,
            "quiet": Nature.QUIET, "quirky": Nature.QUIRKY, "rash": Nature.RASH,
            "relaxed": Nature.RELAXED, "sassy": Nature.SASSY, "serious": Nature.SERIOUS,
            "timid": Nature.TIMID,
        }
        
        for spread in data["spreads"]:
            nature_str = spread.get("nature", "Serious").lower()
            speed_evs = spread.get("evs", 0)
            nature = NATURE_MAP.get(nature_str, Nature.SERIOUS)
            speed = calculate_speed(base, 31, speed_evs, 50, nature)
            if speed not in speed_set:
                speed_set.add(speed)
                calculated_speeds.append(speed)
        
        # Sort descending and return copy with calculated speeds
        calculated_speeds.sort(reverse=True)
        result = data.copy()
        result["common_speeds"] = calculated_speeds
        return result
    
    return data


def calculate_speed_tier(
    base_speed: int,
    nature: Nature,
    evs: int,
    iv: int = 31,
    level: int = 50
) -> dict:
    """
    Calculate speed tier information for a specific spread.

    Returns dict with speed stat and what it outspeeds/underspeeds.
    """
    speed = calculate_speed(base_speed, iv, evs, level, nature)

    outspeeds = []
    ties_with = []
    underspeeds = []

    for mon, data in SPEED_BENCHMARKS.items():
        base = data["base"]
        max_positive = get_speed_benchmark(mon, "max_positive")
        max_neutral = get_speed_benchmark(mon, "max_neutral")
        neutral_0ev = get_speed_benchmark(mon, "neutral_0ev")
        
        if max_positive:
            if speed > max_positive:
                outspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")
            elif speed == max_positive:
                ties_with.append(f"Max Speed {mon.replace('-', ' ').title()}")

        if max_neutral:
            if speed > max_neutral:
                if speed <= (max_positive or 999):
                    outspeeds.append(f"Neutral Speed {mon.replace('-', ' ').title()}")

        if neutral_0ev:
            if speed < neutral_0ev:
                underspeeds.append(f"Base {mon.replace('-', ' ').title()}")

    return {
        "speed": speed,
        "outspeeds": outspeeds[:5],  # Limit for readability
        "ties_with": ties_with,
        "underspeeds": underspeeds[:5],
    }
