"""Chip damage calculations for weather, status, and terrain effects.

This module handles damage/healing over time:
- Weather damage (Sandstorm, Hail/Snow)
- Status damage (Burn, Poison, Toxic)
- Terrain healing (Grassy Terrain)
- Leftover/Black Sludge recovery
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChipDamageResult:
    """Result of chip damage calculation for one turn."""
    source: str
    damage: int
    damage_percent: float
    is_healing: bool
    immune: bool
    immunity_reason: Optional[str]
    hp_after: int
    notes: list[str]


# Types immune to Sandstorm
SANDSTORM_IMMUNE_TYPES = {"rock", "ground", "steel"}

# Types immune to Hail/Snow
HAIL_IMMUNE_TYPES = {"ice"}

# Abilities that grant weather immunity
WEATHER_IMMUNE_ABILITIES = {
    "magic-guard": ["sandstorm", "hail", "snow"],
    "overcoat": ["sandstorm", "hail", "snow"],
    "sand-veil": ["sandstorm"],
    "sand-rush": ["sandstorm"],
    "sand-force": ["sandstorm"],
    "ice-body": ["hail", "snow"],
    "snow-cloak": ["hail", "snow"],
}

# Abilities affected by status
STATUS_MODIFYING_ABILITIES = {
    "poison-heal": "poison",  # Heals instead of damage
    "guts": "burn",  # Ignores Attack drop (but still takes damage)
    "magic-guard": "all",  # Immune to all indirect damage
    "water-veil": "burn",  # Immune to burn
    "immunity": "poison",  # Immune to poison
}


def calculate_weather_chip(
    weather: str,
    current_hp: int,
    max_hp: int,
    pokemon_types: list[str],
    ability: Optional[str] = None
) -> ChipDamageResult:
    """
    Calculate weather damage/effect for one turn.

    Args:
        weather: Current weather (sandstorm, hail, snow, sun, rain)
        current_hp: Current HP
        max_hp: Maximum HP
        pokemon_types: List of Pokemon types
        ability: Pokemon's ability (optional)

    Returns:
        ChipDamageResult with damage/healing info
    """
    weather = weather.lower() if weather else ""
    normalized_types = [t.lower() for t in pokemon_types]
    normalized_ability = ability.lower().replace(" ", "-") if ability else ""

    # Sun and Rain don't deal damage
    if weather in ["sun", "rain", "harsh-sun", "heavy-rain", "none", ""]:
        return ChipDamageResult(
            source=weather.title() if weather else "No Weather",
            damage=0,
            damage_percent=0,
            is_healing=False,
            immune=True,
            immunity_reason="This weather doesn't deal damage",
            hp_after=current_hp,
            notes=[]
        )

    # Sandstorm damage (6.25% = 1/16)
    if weather == "sandstorm":
        # Check type immunity
        if any(t in SANDSTORM_IMMUNE_TYPES for t in normalized_types):
            immune_type = next(t for t in normalized_types if t in SANDSTORM_IMMUNE_TYPES)
            return ChipDamageResult(
                source="Sandstorm",
                damage=0,
                damage_percent=0,
                is_healing=False,
                immune=True,
                immunity_reason=f"{immune_type.title()}-type is immune to Sandstorm",
                hp_after=current_hp,
                notes=[]
            )

        # Check ability immunity
        if normalized_ability in WEATHER_IMMUNE_ABILITIES:
            if "sandstorm" in WEATHER_IMMUNE_ABILITIES.get(normalized_ability, []):
                return ChipDamageResult(
                    source="Sandstorm",
                    damage=0,
                    damage_percent=0,
                    is_healing=False,
                    immune=True,
                    immunity_reason=f"{ability} grants Sandstorm immunity",
                    hp_after=current_hp,
                    notes=[]
                )

        # Calculate damage
        damage = max_hp // 16
        damage_percent = (damage / max_hp) * 100

        return ChipDamageResult(
            source="Sandstorm",
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=["6.25% damage per turn", "Rock/Ground/Steel types immune"]
        )

    # Hail/Snow damage (6.25% = 1/16)
    if weather in ["hail", "snow"]:
        # Check type immunity
        if "ice" in normalized_types:
            return ChipDamageResult(
                source=weather.title(),
                damage=0,
                damage_percent=0,
                is_healing=False,
                immune=True,
                immunity_reason="Ice-type is immune to Hail/Snow",
                hp_after=current_hp,
                notes=[]
            )

        # Check ability immunity
        if normalized_ability in WEATHER_IMMUNE_ABILITIES:
            if weather in WEATHER_IMMUNE_ABILITIES.get(normalized_ability, []):
                return ChipDamageResult(
                    source=weather.title(),
                    damage=0,
                    damage_percent=0,
                    is_healing=False,
                    immune=True,
                    immunity_reason=f"{ability} grants {weather.title()} immunity",
                    hp_after=current_hp,
                    notes=[]
                )

        # Ice Body heals in Hail/Snow instead
        if normalized_ability == "ice-body":
            healing = max_hp // 16
            return ChipDamageResult(
                source=weather.title(),
                damage=-healing,
                damage_percent=-round((healing / max_hp) * 100, 2),
                is_healing=True,
                immune=False,
                immunity_reason=None,
                hp_after=min(max_hp, current_hp + healing),
                notes=["Ice Body heals 6.25% HP in Hail/Snow"]
            )

        damage = max_hp // 16
        damage_percent = (damage / max_hp) * 100

        return ChipDamageResult(
            source=weather.title(),
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=["6.25% damage per turn", "Ice types immune"]
        )

    return ChipDamageResult(
        source=weather,
        damage=0,
        damage_percent=0,
        is_healing=False,
        immune=True,
        immunity_reason="Unknown weather condition",
        hp_after=current_hp,
        notes=[]
    )


def calculate_status_damage(
    status: str,
    current_hp: int,
    max_hp: int,
    toxic_counter: int = 1,
    ability: Optional[str] = None
) -> ChipDamageResult:
    """
    Calculate status condition damage for one turn.

    Args:
        status: Status condition (burn, poison, toxic)
        current_hp: Current HP
        max_hp: Maximum HP
        toxic_counter: For Toxic, which turn of poison (1-15)
        ability: Pokemon's ability (optional)

    Returns:
        ChipDamageResult with damage info
    """
    status = status.lower() if status else ""
    normalized_ability = ability.lower().replace(" ", "-") if ability else ""

    # Magic Guard blocks all indirect damage
    if normalized_ability == "magic-guard":
        return ChipDamageResult(
            source=status.title(),
            damage=0,
            damage_percent=0,
            is_healing=False,
            immune=True,
            immunity_reason="Magic Guard blocks indirect damage",
            hp_after=current_hp,
            notes=[]
        )

    # Burn damage (6.25% = 1/16)
    if status == "burn":
        damage = max_hp // 16
        damage_percent = (damage / max_hp) * 100

        notes = [
            "6.25% damage per turn",
            "Halves physical attack damage"
        ]

        if normalized_ability == "guts":
            notes.append("Guts: Attack is boosted by 50% instead of halved")

        return ChipDamageResult(
            source="Burn",
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=notes
        )

    # Regular Poison (12.5% = 1/8)
    if status == "poison":
        # Poison Heal heals instead
        if normalized_ability == "poison-heal":
            healing = max_hp // 8
            return ChipDamageResult(
                source="Poison",
                damage=-healing,
                damage_percent=-round((healing / max_hp) * 100, 2),
                is_healing=True,
                immune=False,
                immunity_reason=None,
                hp_after=min(max_hp, current_hp + healing),
                notes=["Poison Heal: Heals 12.5% HP instead of damage"]
            )

        damage = max_hp // 8
        damage_percent = (damage / max_hp) * 100

        return ChipDamageResult(
            source="Poison",
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=["12.5% damage per turn"]
        )

    # Toxic (badly poisoned) - increases each turn
    if status in ["toxic", "badly_poisoned", "badly-poisoned"]:
        # Poison Heal heals instead
        if normalized_ability == "poison-heal":
            healing = max_hp // 8
            return ChipDamageResult(
                source="Toxic",
                damage=-healing,
                damage_percent=-round((healing / max_hp) * 100, 2),
                is_healing=True,
                immune=False,
                immunity_reason=None,
                hp_after=min(max_hp, current_hp + healing),
                notes=["Poison Heal: Heals 12.5% HP instead of Toxic damage"]
            )

        # Toxic does N/16 damage where N is the turn counter (max 15)
        effective_counter = min(15, toxic_counter)
        damage = (max_hp * effective_counter) // 16
        damage_percent = (damage / max_hp) * 100

        return ChipDamageResult(
            source=f"Toxic (turn {effective_counter})",
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=[
                f"Turn {effective_counter}: {effective_counter}/16 = {round(effective_counter/16*100, 1)}% damage",
                "Increases each turn, caps at 15/16 (93.75%)"
            ]
        )

    return ChipDamageResult(
        source=status or "None",
        damage=0,
        damage_percent=0,
        is_healing=False,
        immune=True,
        immunity_reason="No damaging status" if not status else "Unknown status",
        hp_after=current_hp,
        notes=[]
    )


def calculate_terrain_healing(
    terrain: str,
    current_hp: int,
    max_hp: int,
    is_grounded: bool = True
) -> ChipDamageResult:
    """
    Calculate terrain healing effect (Grassy Terrain).

    Args:
        terrain: Current terrain
        current_hp: Current HP
        max_hp: Maximum HP
        is_grounded: Whether Pokemon is grounded (Flying/Levitate aren't)

    Returns:
        ChipDamageResult with healing info
    """
    terrain = terrain.lower() if terrain else ""

    if terrain != "grassy":
        return ChipDamageResult(
            source=terrain.title() if terrain else "No Terrain",
            damage=0,
            damage_percent=0,
            is_healing=False,
            immune=True,
            immunity_reason="Only Grassy Terrain provides healing",
            hp_after=current_hp,
            notes=[]
        )

    if not is_grounded:
        return ChipDamageResult(
            source="Grassy Terrain",
            damage=0,
            damage_percent=0,
            is_healing=False,
            immune=True,
            immunity_reason="Not grounded (Flying-type or Levitate)",
            hp_after=current_hp,
            notes=["Must be grounded to receive Grassy Terrain healing"]
        )

    # Grassy Terrain heals 1/16 HP
    healing = max_hp // 16
    healing_percent = (healing / max_hp) * 100

    return ChipDamageResult(
        source="Grassy Terrain",
        damage=-healing,
        damage_percent=-round(healing_percent, 2),
        is_healing=True,
        immune=False,
        immunity_reason=None,
        hp_after=min(max_hp, current_hp + healing),
        notes=[
            "Heals 6.25% HP per turn",
            "Also reduces Earthquake/Bulldoze damage by 50%"
        ]
    )


def calculate_salt_cure_damage(
    current_hp: int,
    max_hp: int,
    pokemon_types: list[str],
    ability: Optional[str] = None
) -> ChipDamageResult:
    """
    Calculate Salt Cure damage for one turn.

    Salt Cure is Garganacl's signature move that inflicts a residual damage condition:
    - Normally deals 1/8 (12.5%) max HP per turn
    - Deals 1/4 (25%) max HP per turn if target is Steel or Water type

    Args:
        current_hp: Current HP
        max_hp: Maximum HP
        pokemon_types: Target's types
        ability: Target's ability (optional)

    Returns:
        ChipDamageResult with damage info
    """
    normalized_ability = ability.lower().replace(" ", "-") if ability else ""
    normalized_types = [t.lower() for t in pokemon_types]

    # Magic Guard blocks all indirect damage
    if normalized_ability == "magic-guard":
        return ChipDamageResult(
            source="Salt Cure",
            damage=0,
            damage_percent=0,
            is_healing=False,
            immune=True,
            immunity_reason="Magic Guard blocks indirect damage",
            hp_after=current_hp,
            notes=[]
        )

    # Check for Steel or Water type (double damage)
    is_vulnerable = "steel" in normalized_types or "water" in normalized_types

    if is_vulnerable:
        # 1/4 (25%) max HP damage for Steel/Water types
        damage = max_hp // 4
        damage_percent = (damage / max_hp) * 100
        vulnerable_type = "Steel" if "steel" in normalized_types else "Water"

        return ChipDamageResult(
            source="Salt Cure",
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=[
                f"25% damage per turn ({vulnerable_type}-type takes double damage)",
                "Garganacl's signature residual effect"
            ]
        )
    else:
        # 1/8 (12.5%) max HP damage normally
        damage = max_hp // 8
        damage_percent = (damage / max_hp) * 100

        return ChipDamageResult(
            source="Salt Cure",
            damage=damage,
            damage_percent=round(damage_percent, 2),
            is_healing=False,
            immune=False,
            immunity_reason=None,
            hp_after=max(0, current_hp - damage),
            notes=[
                "12.5% damage per turn",
                "Deals 25% to Steel/Water types"
            ]
        )


def calculate_leftovers_recovery(
    current_hp: int,
    max_hp: int,
    item: str = "leftovers"
) -> ChipDamageResult:
    """
    Calculate Leftovers/Black Sludge recovery.

    Args:
        current_hp: Current HP
        max_hp: Maximum HP
        item: "leftovers" or "black-sludge"

    Returns:
        ChipDamageResult with recovery info
    """
    item = item.lower().replace(" ", "-")

    if item not in ["leftovers", "black-sludge"]:
        return ChipDamageResult(
            source=item,
            damage=0,
            damage_percent=0,
            is_healing=False,
            immune=True,
            immunity_reason="Not a recovery item",
            hp_after=current_hp,
            notes=[]
        )

    # Both heal 1/16 HP
    healing = max_hp // 16
    healing_percent = (healing / max_hp) * 100

    notes = ["Recovers 6.25% HP per turn"]
    if item == "black-sludge":
        notes.append("Note: Damages non-Poison types for 12.5%")

    return ChipDamageResult(
        source=item.replace("-", " ").title(),
        damage=-healing,
        damage_percent=-round(healing_percent, 2),
        is_healing=True,
        immune=False,
        immunity_reason=None,
        hp_after=min(max_hp, current_hp + healing),
        notes=notes
    )


def calculate_total_chip_damage(
    current_hp: int,
    max_hp: int,
    turns: int,
    weather: Optional[str] = None,
    status: Optional[str] = None,
    terrain: Optional[str] = None,
    item: Optional[str] = None,
    pokemon_types: list[str] = None,
    ability: Optional[str] = None,
    is_grounded: bool = True
) -> dict:
    """
    Calculate total chip damage over multiple turns.

    Args:
        current_hp: Starting HP
        max_hp: Maximum HP
        turns: Number of turns to simulate
        weather: Active weather
        status: Status condition
        terrain: Active terrain
        item: Held item (for Leftovers/Black Sludge)
        pokemon_types: Pokemon's types
        ability: Pokemon's ability
        is_grounded: Whether Pokemon is grounded

    Returns:
        Dict with turn-by-turn breakdown and total
    """
    if pokemon_types is None:
        pokemon_types = []

    hp = current_hp
    turn_breakdown = []
    total_damage = 0
    total_healing = 0

    for turn in range(1, turns + 1):
        turn_effects = []
        turn_net = 0

        # Weather damage
        if weather:
            weather_result = calculate_weather_chip(
                weather, hp, max_hp, pokemon_types, ability
            )
            if not weather_result.immune:
                turn_effects.append(weather_result)
                if weather_result.is_healing:
                    total_healing += abs(weather_result.damage)
                else:
                    total_damage += weather_result.damage
                turn_net += weather_result.damage if not weather_result.is_healing else -weather_result.damage

        # Status damage
        if status:
            status_result = calculate_status_damage(
                status, hp, max_hp,
                toxic_counter=turn if status.lower() in ["toxic", "badly_poisoned"] else 1,
                ability=ability
            )
            if not status_result.immune:
                turn_effects.append(status_result)
                if status_result.is_healing:
                    total_healing += abs(status_result.damage)
                else:
                    total_damage += status_result.damage
                turn_net += status_result.damage if not status_result.is_healing else -status_result.damage

        # Terrain healing
        if terrain:
            terrain_result = calculate_terrain_healing(terrain, hp, max_hp, is_grounded)
            if not terrain_result.immune and terrain_result.is_healing:
                turn_effects.append(terrain_result)
                total_healing += abs(terrain_result.damage)
                turn_net -= abs(terrain_result.damage)

        # Item recovery
        if item and item.lower().replace(" ", "-") in ["leftovers", "black-sludge"]:
            item_result = calculate_leftovers_recovery(hp, max_hp, item)
            if item_result.is_healing:
                turn_effects.append(item_result)
                total_healing += abs(item_result.damage)
                turn_net -= abs(item_result.damage)

        # Update HP
        hp = max(0, min(max_hp, hp - turn_net))

        turn_breakdown.append({
            "turn": turn,
            "effects": [
                {
                    "source": e.source,
                    "damage": e.damage,
                    "healing": e.is_healing
                }
                for e in turn_effects
            ],
            "net_change": -turn_net,
            "hp_after": hp,
            "hp_percent": round((hp / max_hp) * 100, 1)
        })

        if hp <= 0:
            break

    return {
        "starting_hp": current_hp,
        "max_hp": max_hp,
        "turns_simulated": len(turn_breakdown),
        "total_damage": total_damage,
        "total_healing": total_healing,
        "net_change": total_healing - total_damage,
        "final_hp": hp,
        "final_hp_percent": round((hp / max_hp) * 100, 1),
        "fainted": hp <= 0,
        "turn_breakdown": turn_breakdown
    }
