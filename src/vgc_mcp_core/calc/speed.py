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


# Common speed benchmarks for VGC (updated for current meta)
SPEED_BENCHMARKS = {
    # Base speeds for quick reference
    "regieleki": {"base": 200, "max_positive": 277, "max_neutral": 252},
    "electrode-hisui": {"base": 150, "max_positive": 222, "max_neutral": 202},
    "dragapult": {"base": 142, "max_positive": 213, "max_neutral": 194},
    "iron-bundle": {"base": 136, "max_positive": 205, "max_neutral": 187},
    "flutter-mane": {"base": 135, "max_positive": 205, "max_neutral": 187},
    "miraidon": {"base": 135, "max_positive": 205, "max_neutral": 187},
    "koraidon": {"base": 135, "max_positive": 205, "max_neutral": 187},
    "raging-bolt": {"base": 91, "max_positive": 139, "max_neutral": 127},
    "chi-yu": {"base": 100, "max_positive": 152, "max_neutral": 138},
    "urshifu": {"base": 97, "max_positive": 148, "max_neutral": 135},
    "urshifu-rapid-strike": {"base": 97, "max_positive": 148, "max_neutral": 135},
    "palafin-hero": {"base": 100, "max_positive": 152, "max_neutral": 138},
    "tornadus": {"base": 111, "max_positive": 167, "max_neutral": 152},
    "landorus": {"base": 101, "max_positive": 154, "max_neutral": 140},
    "landorus-therian": {"base": 91, "max_positive": 139, "max_neutral": 127},
    "gholdengo": {"base": 84, "max_positive": 130, "max_neutral": 119},
    "rillaboom": {"base": 85, "max_positive": 132, "max_neutral": 120},
    "incineroar": {"base": 60, "neutral_0ev": 80, "min_negative": 58},
    "kingambit": {"base": 50, "neutral_0ev": 70, "min_negative": 49},
    "iron-hands": {"base": 50, "neutral_0ev": 70, "min_negative": 49},
    "amoonguss": {"base": 30, "neutral_0ev": 50, "min_negative": 31},
    "dondozo": {"base": 35, "neutral_0ev": 55, "min_negative": 36},
    "ting-lu": {"base": 45, "neutral_0ev": 65, "min_negative": 45},
}


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
    """Get speed benchmark info for a Pokemon."""
    name = pokemon_name.lower().replace(" ", "-")
    return SPEED_BENCHMARKS.get(name)


def get_meta_speed_tier(pokemon_name: str) -> Optional[dict]:
    """Get VGC meta speed tier info for a Pokemon (includes common speeds)."""
    name = pokemon_name.lower().replace(" ", "-")

    # Normalize Ogerpon mask form names (e.g., "ogerpon-wellspring-mask" -> "ogerpon-wellspring")
    if name.endswith("-mask"):
        name = name.replace("-mask", "")

    return META_SPEED_TIERS.get(name)


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
        if "max_positive" in data:
            if speed > data["max_positive"]:
                outspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")
            elif speed == data["max_positive"]:
                ties_with.append(f"Max Speed {mon.replace('-', ' ').title()}")

        if "max_neutral" in data:
            if speed > data["max_neutral"]:
                if speed <= data.get("max_positive", 999):
                    outspeeds.append(f"Neutral Speed {mon.replace('-', ' ').title()}")

        if "neutral_0ev" in data:
            if speed < data["neutral_0ev"]:
                underspeeds.append(f"Base {mon.replace('-', ' ').title()}")

    return {
        "speed": speed,
        "outspeeds": outspeeds[:5],  # Limit for readability
        "ties_with": ties_with,
        "underspeeds": underspeeds[:5],
    }
