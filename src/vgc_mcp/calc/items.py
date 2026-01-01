"""Item effect calculations for VGC damage and stat modifications.

This module handles competitive item mechanics including:
- Stat modifying items (Choice items, Assault Vest, Eviolite)
- Booster Energy for Paradox Pokemon
- Damage modifying items (Life Orb, Expert Belt)
- Berry activation thresholds
- Focus Sash survival checks
"""

from dataclasses import dataclass
from typing import Optional


# Paradox Pokemon that can use Booster Energy
PARADOX_POKEMON = {
    # Past Paradox (Great Tusk, etc.)
    "great-tusk", "scream-tail", "brute-bonnet", "flutter-mane",
    "slither-wing", "sandy-shocks", "roaring-moon", "walking-wake",
    "gouging-fire", "raging-bolt",
    # Future Paradox (Iron Treads, etc.)
    "iron-treads", "iron-bundle", "iron-hands", "iron-jugulis",
    "iron-moth", "iron-thorns", "iron-valiant", "iron-leaves",
    "iron-boulder", "iron-crown",
}

# Pokemon that are Not Fully Evolved (can use Eviolite)
# This is a subset - full list would be much longer
NFE_POKEMON = {
    "chansey", "porygon2", "dusclops", "rhydon", "magmar", "electabuzz",
    "scyther", "pikachu", "clefairy", "haunter", "kadabra", "machoke",
    "graveler", "magneton", "slowpoke", "shellder", "onix", "lickitung",
    "tangela", "seadra", "murkrow", "misdreavus", "gligar", "sneasel",
    "togetic", "vigoroth", "nosepass", "roselia", "duskull", "snorunt",
}


@dataclass
class ItemEffect:
    """Result of an item effect calculation."""
    item: str
    applies: bool
    stat_modifiers: dict[str, float]  # stat_name -> multiplier
    damage_modifier: float  # Multiplier for damage dealt
    description: str
    notes: list[str]


def calculate_booster_energy_boost(
    pokemon_name: str,
    base_stats: dict[str, int],
    nature_modifiers: dict[str, float] = None
) -> ItemEffect:
    """
    Calculate Booster Energy stat boost for Paradox Pokemon.

    Booster Energy boosts the highest stat by 30% (50% for Speed).
    If a terrain/weather already provides the boost, it won't consume the item.

    Args:
        pokemon_name: Name of the Pokemon
        base_stats: Dict with hp, attack, defense, special_attack, special_defense, speed
        nature_modifiers: Optional dict of nature stat modifiers

    Returns:
        ItemEffect with the boosted stat and multiplier
    """
    normalized_name = pokemon_name.lower().replace(" ", "-")

    if normalized_name not in PARADOX_POKEMON:
        return ItemEffect(
            item="Booster Energy",
            applies=False,
            stat_modifiers={},
            damage_modifier=1.0,
            description=f"{pokemon_name} is not a Paradox Pokemon",
            notes=["Booster Energy only works on Paradox Pokemon"]
        )

    # Find highest stat (excluding HP)
    stats_to_check = {
        "attack": base_stats.get("attack", 0),
        "defense": base_stats.get("defense", 0),
        "special_attack": base_stats.get("special_attack", 0),
        "special_defense": base_stats.get("special_defense", 0),
        "speed": base_stats.get("speed", 0),
    }

    # Apply nature modifiers if provided
    if nature_modifiers:
        for stat, mod in nature_modifiers.items():
            if stat in stats_to_check:
                stats_to_check[stat] = int(stats_to_check[stat] * mod)

    highest_stat = max(stats_to_check, key=stats_to_check.get)
    # Speed gets 1.5x, other stats get 1.3x
    boost = 1.5 if highest_stat == "speed" else 1.3

    stat_display = {
        "attack": "Attack",
        "defense": "Defense",
        "special_attack": "Sp. Atk",
        "special_defense": "Sp. Def",
        "speed": "Speed"
    }

    return ItemEffect(
        item="Booster Energy",
        applies=True,
        stat_modifiers={highest_stat: boost},
        damage_modifier=1.0,
        description=f"Booster Energy: +{int((boost-1)*100)}% {stat_display[highest_stat]}",
        notes=[
            f"Boosts {stat_display[highest_stat]} from {stats_to_check[highest_stat]} to {int(stats_to_check[highest_stat] * boost)}",
            "Won't activate if weather/terrain already provides Protosynthesis/Quark Drive"
        ]
    )


def calculate_assault_vest_boost(base_spd: int) -> ItemEffect:
    """
    Calculate Assault Vest Special Defense boost.

    Assault Vest gives 1.5x Special Defense but prevents status moves.

    Args:
        base_spd: Base Special Defense stat value

    Returns:
        ItemEffect with the SpD multiplier
    """
    boosted = int(base_spd * 1.5)

    return ItemEffect(
        item="Assault Vest",
        applies=True,
        stat_modifiers={"special_defense": 1.5},
        damage_modifier=1.0,
        description=f"Assault Vest: Sp. Def {base_spd} -> {boosted} (1.5x)",
        notes=[
            "Cannot use status moves (Protect, Taunt, etc.)",
            "Only affects Special Defense, not Defense"
        ]
    )


def calculate_eviolite_boost(
    pokemon_name: str,
    base_def: int,
    base_spd: int
) -> ItemEffect:
    """
    Calculate Eviolite defensive boosts for NFE Pokemon.

    Eviolite gives 1.5x Defense AND Special Defense to not-fully-evolved Pokemon.

    Args:
        pokemon_name: Name of the Pokemon
        base_def: Base Defense stat value
        base_spd: Base Special Defense stat value

    Returns:
        ItemEffect with both defensive multipliers
    """
    normalized_name = pokemon_name.lower().replace(" ", "-")

    if normalized_name not in NFE_POKEMON:
        return ItemEffect(
            item="Eviolite",
            applies=False,
            stat_modifiers={},
            damage_modifier=1.0,
            description=f"{pokemon_name} is fully evolved - Eviolite has no effect",
            notes=["Eviolite only works on Pokemon that can still evolve"]
        )

    boosted_def = int(base_def * 1.5)
    boosted_spd = int(base_spd * 1.5)

    return ItemEffect(
        item="Eviolite",
        applies=True,
        stat_modifiers={"defense": 1.5, "special_defense": 1.5},
        damage_modifier=1.0,
        description=f"Eviolite: Def {base_def}->{boosted_def}, Sp.Def {base_spd}->{boosted_spd} (1.5x)",
        notes=[
            "Boosts both Defense and Special Defense",
            f"{pokemon_name} can still evolve"
        ]
    )


def calculate_choice_item_boost(
    item: str,
    base_stat: int
) -> ItemEffect:
    """
    Calculate Choice item stat boost.

    Choice Band: 1.5x Attack
    Choice Specs: 1.5x Special Attack
    Choice Scarf: 1.5x Speed

    Args:
        item: "choice-band", "choice-specs", or "choice-scarf"
        base_stat: The relevant base stat value

    Returns:
        ItemEffect with the stat multiplier
    """
    item_data = {
        "choice-band": ("attack", "Attack"),
        "choice-specs": ("special_attack", "Sp. Atk"),
        "choice-scarf": ("speed", "Speed"),
    }

    normalized_item = item.lower().replace(" ", "-")

    if normalized_item not in item_data:
        return ItemEffect(
            item=item,
            applies=False,
            stat_modifiers={},
            damage_modifier=1.0,
            description="Not a Choice item",
            notes=[]
        )

    stat_key, stat_name = item_data[normalized_item]
    boosted = int(base_stat * 1.5)

    return ItemEffect(
        item=item.title(),
        applies=True,
        stat_modifiers={stat_key: 1.5},
        damage_modifier=1.0,
        description=f"{item.title()}: {stat_name} {base_stat} -> {boosted} (1.5x)",
        notes=[
            "Locked into first move used",
            "Switching out allows choosing a different move"
        ]
    )


def calculate_life_orb_effect(damage: int, attacker_hp: int) -> dict:
    """
    Calculate Life Orb damage boost and recoil.

    Life Orb: 1.3x damage, costs 10% max HP per attack.

    Args:
        damage: Base damage dealt
        attacker_hp: Attacker's max HP

    Returns:
        Dict with boosted damage and recoil
    """
    boosted_damage = int(damage * 1.3)
    recoil = attacker_hp // 10  # 10% max HP

    return {
        "item": "Life Orb",
        "original_damage": damage,
        "boosted_damage": boosted_damage,
        "damage_multiplier": 1.3,
        "recoil": recoil,
        "recoil_percent": 10,
        "description": f"Life Orb: {damage} -> {boosted_damage} damage, -{recoil} HP recoil"
    }


def check_berry_activation(
    berry: str,
    current_hp: int,
    max_hp: int,
    stat_to_boost: Optional[str] = None
) -> dict:
    """
    Check if a berry would activate and what it does.

    Args:
        berry: Berry name
        current_hp: Current HP
        max_hp: Maximum HP
        stat_to_boost: For stat-boosting berries, which stat to check

    Returns:
        Dict with activation threshold and effect
    """
    hp_percent = (current_hp / max_hp) * 100

    # Sitrus Berry: Heals 25% HP when below 50%
    if berry.lower() in ["sitrus", "sitrus-berry"]:
        threshold = 50
        activates = hp_percent <= threshold
        heal = max_hp // 4
        return {
            "berry": "Sitrus Berry",
            "threshold": f"{threshold}% HP",
            "current_hp_percent": round(hp_percent, 1),
            "would_activate": activates,
            "effect": f"Heals {heal} HP (25%)",
            "hp_after": min(max_hp, current_hp + heal) if activates else current_hp
        }

    # Pinch berries (Figy, Wiki, etc.): Heal 33% at 25% HP
    pinch_berries = ["figy", "wiki", "mago", "aguav", "iapapa"]
    if any(berry.lower().startswith(b) for b in pinch_berries):
        threshold = 25
        activates = hp_percent <= threshold
        heal = max_hp // 3
        return {
            "berry": berry.title() + " Berry",
            "threshold": f"{threshold}% HP",
            "current_hp_percent": round(hp_percent, 1),
            "would_activate": activates,
            "effect": f"Heals {heal} HP (33%)",
            "hp_after": min(max_hp, current_hp + heal) if activates else current_hp,
            "note": "May cause confusion if Pokemon dislikes the flavor"
        }

    # Stat boosting berries (Liechi, Petaya, etc.): +1 stage at 25% HP
    stat_berries = {
        "liechi": "attack",
        "petaya": "special_attack",
        "salac": "speed",
        "ganlon": "defense",
        "apicot": "special_defense"
    }
    for berry_name, stat in stat_berries.items():
        if berry.lower().startswith(berry_name):
            threshold = 25
            activates = hp_percent <= threshold
            return {
                "berry": berry_name.title() + " Berry",
                "threshold": f"{threshold}% HP",
                "current_hp_percent": round(hp_percent, 1),
                "would_activate": activates,
                "effect": f"+1 {stat.replace('_', ' ').title()} stage",
                "note": "Consumed after use"
            }

    return {
        "berry": berry,
        "error": "Unknown berry type",
        "supported_berries": ["Sitrus", "Figy/Wiki/Mago/Aguav/Iapapa", "Liechi/Petaya/Salac/Ganlon/Apicot"]
    }


def check_focus_sash_survival(
    damage: int,
    current_hp: int,
    max_hp: int
) -> dict:
    """
    Check if Focus Sash would save the Pokemon.

    Focus Sash prevents OHKO when at full HP, leaving 1 HP.

    Args:
        damage: Incoming damage
        current_hp: Current HP
        max_hp: Maximum HP

    Returns:
        Dict with survival analysis
    """
    at_full_hp = current_hp == max_hp
    would_ko = damage >= current_hp
    sash_activates = at_full_hp and would_ko

    return {
        "item": "Focus Sash",
        "at_full_hp": at_full_hp,
        "incoming_damage": damage,
        "would_ko_without_sash": would_ko,
        "sash_activates": sash_activates,
        "hp_after": 1 if sash_activates else max(0, current_hp - damage),
        "description": (
            "Focus Sash activates! Survives with 1 HP" if sash_activates
            else "Sash won't activate" if not at_full_hp
            else "Damage doesn't KO, Sash preserved"
        ),
        "notes": [
            "Only works at full HP",
            "Consumed after activation",
            "Multi-hit moves can bypass (hits after first)"
        ] if sash_activates else []
    }


# Item damage modifiers for damage calculation
DAMAGE_MODIFYING_ITEMS = {
    "life-orb": 1.3,
    "expert-belt": 1.2,  # Only on super effective moves
    "metronome": 1.0,  # Increases with consecutive use
    "muscle-band": 1.1,  # Physical only
    "wise-glasses": 1.1,  # Special only
    "choice-band": 1.5,  # Physical attack stat
    "choice-specs": 1.5,  # Special attack stat
}


def get_item_damage_modifier(
    item: str,
    is_physical: bool = True,
    is_super_effective: bool = False,
    consecutive_uses: int = 1
) -> float:
    """
    Get the damage multiplier for an item.

    Args:
        item: Item name
        is_physical: Whether the move is physical
        is_super_effective: Whether the move is super effective
        consecutive_uses: For Metronome item, how many times move used in a row

    Returns:
        Damage multiplier
    """
    normalized = item.lower().replace(" ", "-")

    if normalized == "life-orb":
        return 1.3

    if normalized == "expert-belt" and is_super_effective:
        return 1.2

    if normalized == "muscle-band" and is_physical:
        return 1.1

    if normalized == "wise-glasses" and not is_physical:
        return 1.1

    if normalized == "metronome":
        # Caps at 2.0x after 5 uses
        return min(2.0, 1.0 + (consecutive_uses - 1) * 0.2)

    return 1.0
