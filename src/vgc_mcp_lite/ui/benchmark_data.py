# -*- coding: utf-8 -*-
"""Generate defensive benchmark data from Smogon VGC usage stats.

This module fetches real usage data from Smogon and generates the data
structures needed for the defensive benchmark UI.
"""

from typing import Optional
import asyncio

from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.meta_threats import calculate_simple_damage, get_ruinous_info
from vgc_mcp_core.calc.stats import calculate_stat, calculate_all_stats
from vgc_mcp_core.calc.modifiers import get_type_effectiveness
from vgc_mcp_core.models.pokemon import Nature, EVSpread, BaseStats


# Common VGC threat moves to analyze (expanded for move selection)
COMMON_THREAT_MOVES = {
    "chien-pao": [
        {"name": "Icicle Crash", "power": 85, "type": "Ice", "category": "physical"},
        {"name": "Ice Shard", "power": 40, "type": "Ice", "category": "physical"},
        {"name": "Sucker Punch", "power": 70, "type": "Dark", "category": "physical"},
        {"name": "Crunch", "power": 80, "type": "Dark", "category": "physical"},
        {"name": "Sacred Sword", "power": 90, "type": "Fighting", "category": "physical"},
        {"name": "Ice Spinner", "power": 80, "type": "Ice", "category": "physical"},
    ],
    "rillaboom": [
        {"name": "Grassy Glide", "power": 55, "type": "Grass", "category": "physical"},
        {"name": "Wood Hammer", "power": 120, "type": "Grass", "category": "physical"},
        {"name": "Drum Beating", "power": 80, "type": "Grass", "category": "physical"},
        {"name": "Knock Off", "power": 65, "type": "Dark", "category": "physical"},
        {"name": "U-turn", "power": 70, "type": "Bug", "category": "physical"},
        {"name": "High Horsepower", "power": 95, "type": "Ground", "category": "physical"},
    ],
    "incineroar": [
        {"name": "Flare Blitz", "power": 120, "type": "Fire", "category": "physical"},
        {"name": "Knock Off", "power": 65, "type": "Dark", "category": "physical"},
        {"name": "Darkest Lariat", "power": 85, "type": "Dark", "category": "physical"},
        {"name": "U-turn", "power": 70, "type": "Bug", "category": "physical"},
        {"name": "Drain Punch", "power": 75, "type": "Fighting", "category": "physical"},
        {"name": "Fake Out", "power": 40, "type": "Normal", "category": "physical"},
    ],
    "urshifu-rapid-strike": [
        {"name": "Surging Strikes", "power": 25, "type": "Water", "category": "physical"},
        {"name": "Close Combat", "power": 120, "type": "Fighting", "category": "physical"},
        {"name": "Aqua Jet", "power": 40, "type": "Water", "category": "physical"},
        {"name": "U-turn", "power": 70, "type": "Bug", "category": "physical"},
        {"name": "Ice Punch", "power": 75, "type": "Ice", "category": "physical"},
    ],
    "flutter mane": [
        {"name": "Moonblast", "power": 95, "type": "Fairy", "category": "special"},
        {"name": "Shadow Ball", "power": 80, "type": "Ghost", "category": "special"},
        {"name": "Dazzling Gleam", "power": 80, "type": "Fairy", "category": "special", "spread": True},
        {"name": "Mystical Fire", "power": 75, "type": "Fire", "category": "special"},
        {"name": "Thunderbolt", "power": 90, "type": "Electric", "category": "special"},
        {"name": "Psyshock", "power": 80, "type": "Psychic", "category": "special"},
    ],
    "tornadus": [
        {"name": "Bleakwind Storm", "power": 100, "type": "Flying", "category": "special", "spread": True},
        {"name": "Hurricane", "power": 110, "type": "Flying", "category": "special"},
        {"name": "Heat Wave", "power": 95, "type": "Fire", "category": "special", "spread": True},
        {"name": "Icy Wind", "power": 55, "type": "Ice", "category": "special", "spread": True},
    ],
    "landorus": [
        {"name": "Earth Power", "power": 90, "type": "Ground", "category": "special"},
        {"name": "Sludge Bomb", "power": 90, "type": "Poison", "category": "special"},
        {"name": "Sandsear Storm", "power": 100, "type": "Ground", "category": "special", "spread": True},
        {"name": "Psychic", "power": 90, "type": "Psychic", "category": "special"},
    ],
    "kingambit": [
        {"name": "Kowtow Cleave", "power": 85, "type": "Dark", "category": "physical"},
        {"name": "Iron Head", "power": 80, "type": "Steel", "category": "physical"},
        {"name": "Sucker Punch", "power": 70, "type": "Dark", "category": "physical"},
        {"name": "Low Kick", "power": 60, "type": "Fighting", "category": "physical"},
    ],
    "gholdengo": [
        {"name": "Make It Rain", "power": 120, "type": "Steel", "category": "special", "spread": True},
        {"name": "Shadow Ball", "power": 80, "type": "Ghost", "category": "special"},
        {"name": "Thunderbolt", "power": 90, "type": "Electric", "category": "special"},
        {"name": "Nasty Plot", "power": 0, "type": "Dark", "category": "status"},
    ],
    "iron hands": [
        {"name": "Close Combat", "power": 120, "type": "Fighting", "category": "physical"},
        {"name": "Wild Charge", "power": 90, "type": "Electric", "category": "physical"},
        {"name": "Fake Out", "power": 40, "type": "Normal", "category": "physical"},
        {"name": "Ice Punch", "power": 75, "type": "Ice", "category": "physical"},
        {"name": "Drain Punch", "power": 75, "type": "Fighting", "category": "physical"},
    ],
}


def format_spread_string(nature: str, evs: dict) -> str:
    """Format EVs into a readable string like 'Adamant 252/116/60/76'."""
    parts = []
    if evs.get("hp", 0) > 0:
        parts.append(f"{evs['hp']} HP")
    if evs.get("attack", 0) > 0:
        parts.append(f"{evs['attack']} Atk")
    if evs.get("defense", 0) > 0:
        parts.append(f"{evs['defense']} Def")
    if evs.get("special_attack", 0) > 0:
        parts.append(f"{evs['special_attack']} SpA")
    if evs.get("special_defense", 0) > 0:
        parts.append(f"{evs['special_defense']} SpD")
    if evs.get("speed", 0) > 0:
        parts.append(f"{evs['speed']} Spe")

    if parts:
        return f"{nature} {' / '.join(parts)}"
    return nature


def get_ko_result(min_pct: float, max_pct: float) -> str:
    """Get KO result string from damage percentages."""
    if min_pct >= 100:
        return "OHKO"
    if max_pct >= 100:
        # Calculate OHKO chance based on rolls
        rolls = 16
        ko_rolls = 0
        for i in range(rolls):
            roll_mult = 0.85 + (i / (rolls - 1)) * 0.15
            if (min_pct / 0.85) * roll_mult >= 100:
                ko_rolls += 1
        chance = round(ko_rolls / rolls * 100, 2)
        return f"{chance}% OHKO"
    if min_pct >= 50:
        return "2HKO"
    if min_pct >= 33.4:
        return "3HKO"
    if min_pct >= 25:
        return "4HKO"
    return "Survives"


def calculate_stats_from_spread(base_stats: dict, nature: str, evs: dict, level: int = 50) -> dict:
    """Calculate final stats from base stats, nature, and EVs."""
    # Nature modifiers
    nature_mods = {
        "adamant": {"attack": 1.1, "special_attack": 0.9},
        "bold": {"defense": 1.1, "attack": 0.9},
        "brave": {"attack": 1.1, "speed": 0.9},
        "calm": {"special_defense": 1.1, "attack": 0.9},
        "careful": {"special_defense": 1.1, "special_attack": 0.9},
        "gentle": {"special_defense": 1.1, "defense": 0.9},
        "hasty": {"speed": 1.1, "defense": 0.9},
        "impish": {"defense": 1.1, "special_attack": 0.9},
        "jolly": {"speed": 1.1, "special_attack": 0.9},
        "lax": {"defense": 1.1, "special_defense": 0.9},
        "lonely": {"attack": 1.1, "defense": 0.9},
        "mild": {"special_attack": 1.1, "defense": 0.9},
        "modest": {"special_attack": 1.1, "attack": 0.9},
        "naive": {"speed": 1.1, "special_defense": 0.9},
        "naughty": {"attack": 1.1, "special_defense": 0.9},
        "quiet": {"special_attack": 1.1, "speed": 0.9},
        "rash": {"special_attack": 1.1, "special_defense": 0.9},
        "relaxed": {"defense": 1.1, "speed": 0.9},
        "sassy": {"special_defense": 1.1, "speed": 0.9},
        "serious": {},
        "timid": {"speed": 1.1, "attack": 0.9},
    }

    mods = nature_mods.get(nature.lower(), {})
    stats = {}

    # HP formula
    hp_base = base_stats.get("hp", 80)
    hp_ev = evs.get("hp", 0)
    stats["hp"] = int((2 * hp_base + 31 + hp_ev // 4) * level // 100) + level + 10

    # Other stats
    for stat_name in ["attack", "defense", "special_attack", "special_defense", "speed"]:
        base = base_stats.get(stat_name, 80)
        ev = evs.get(stat_name, 0)
        value = int((2 * base + 31 + ev // 4) * level // 100) + 5
        if stat_name in mods:
            value = int(value * mods[stat_name])
        stats[stat_name] = value

    return stats


async def generate_defensive_benchmark_data(
    pokemon_name: str,
    pokemon_nature: str,
    pokemon_evs: dict,
    pokemon_base_stats: dict,
    pokemon_types: list[str],
    pokemon_item: str = "",
    threats: list[str] = None,
    targets: list[str] = None,
    smogon_client: SmogonStatsClient = None,
    pokeapi_client: PokeAPIClient = None,
) -> dict:
    """
    Generate defensive benchmark data using real Smogon VGC usage stats.

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_nature: Your Pokemon's nature
        pokemon_evs: Your Pokemon's EVs dict
        pokemon_base_stats: Your Pokemon's base stats
        pokemon_types: Your Pokemon's types
        pokemon_item: Your Pokemon's held item
        threats: List of threat Pokemon to analyze (defaults to top meta threats)
        targets: List of target Pokemon for offensive calcs (defaults to top meta)
        smogon_client: Optional SmogonStatsClient instance
        pokeapi_client: Optional PokeAPIClient instance

    Returns:
        Dict with pokemon, defensive_benchmarks, offensive_benchmarks ready for UI
    """
    if smogon_client is None:
        smogon_client = SmogonStatsClient()
    if pokeapi_client is None:
        pokeapi_client = PokeAPIClient()

    # Default threats if not provided
    if threats is None:
        threats = ["chien-pao", "rillaboom", "incineroar", "urshifu-rapid-strike"]
    if targets is None:
        targets = ["rillaboom", "incineroar", "kingambit", "tornadus"]

    # Calculate your Pokemon's stats
    your_stats = calculate_stats_from_spread(pokemon_base_stats, pokemon_nature, pokemon_evs)

    # Build pokemon dict for UI
    pokemon_data = {
        "name": pokemon_name,
        "nature": pokemon_nature,
        "evs": pokemon_evs,
        "item": pokemon_item,
        "stats": your_stats,
        "base_stats": pokemon_base_stats,
        "types": pokemon_types,
    }

    # Generate defensive benchmarks
    defensive_benchmarks = []
    for threat_name in threats:
        threat_key = threat_name.lower().replace(" ", "-")

        # Get Smogon usage data for threat
        try:
            usage_data = await smogon_client.get_pokemon_usage(threat_name)
        except Exception:
            usage_data = None

        if not usage_data:
            continue

        # Get threat's base stats and types from PokeAPI
        try:
            threat_info = await pokeapi_client.get_pokemon(threat_name)
            # Extract base stats from raw API response
            stats_raw = threat_info.get("stats", [])
            threat_base_stats = {}
            for stat in stats_raw:
                stat_name = stat["stat"]["name"].replace("-", "_")
                if stat_name == "special_attack":
                    stat_name = "special_attack"
                elif stat_name == "special_defense":
                    stat_name = "special_defense"
                threat_base_stats[stat_name] = stat["base_stat"]

            # Get types using the helper method
            threat_types = await pokeapi_client.get_pokemon_types(threat_name)
        except Exception as e:
            print(f"Error getting {threat_name} data: {e}")
            continue

        # Get common spreads from Smogon
        spreads = usage_data.get("spreads", [])[:4]  # Top 4 spreads
        items = usage_data.get("items", {})

        # Get moves for this threat
        moves = COMMON_THREAT_MOVES.get(threat_key, [])
        if not moves:
            continue

        # Build common_spreads list with items
        common_spreads = []
        for spread in spreads:
            nature = spread.get("nature", "Serious")
            evs = spread.get("evs", {})
            usage_pct = spread.get("usage", 0)

            # Get most common item for this spread
            top_item = list(items.keys())[0] if items else ""

            common_spreads.append({
                "spread": format_spread_string(nature, evs),
                "item": top_item,
                "usage": usage_pct,
                "nature": nature,
                "evs": evs,
            })

        if not common_spreads:
            continue

        # Use first spread as default
        default_spread = common_spreads[0]
        threat_stats = calculate_stats_from_spread(
            threat_base_stats,
            default_spread["nature"],
            default_spread["evs"]
        )

        # Check for ruinous ability
        ruinous_info = get_ruinous_info(threat_name)
        defense_mod = 1.0
        if ruinous_info and ruinous_info["affected_stat"] == "defense":
            defense_mod = 0.75  # Sword of Ruin

        # Calculate damage for each move
        calcs = []
        for move in moves:
            is_physical = move["category"] == "physical"
            move_type = move["type"]

            # Calculate type effectiveness against your Pokemon
            effectiveness = 1.0
            for your_type in pokemon_types:
                effectiveness *= get_type_effectiveness(move_type, your_type)

            # Check for STAB
            stab = move_type.lower() in [t.lower() for t in threat_types]

            # Calculate damage for each spread
            damage_per_spread = []
            for spread_data in common_spreads:
                spread_stats = calculate_stats_from_spread(
                    threat_base_stats,
                    spread_data["nature"],
                    spread_data["evs"]
                )

                # Item modifier
                item_mod = 1.0
                item = spread_data.get("item", "").lower()
                if "life orb" in item:
                    item_mod = 1.3
                elif "choice band" in item and is_physical:
                    item_mod = 1.5
                elif "choice specs" in item and not is_physical:
                    item_mod = 1.5

                result = calculate_simple_damage(
                    attacker_stats=spread_stats,
                    defender_stats=your_stats,
                    move_power=int(move["power"] * item_mod),
                    is_physical=is_physical,
                    stab=stab,
                    type_effectiveness=effectiveness,
                    is_spread=move.get("spread", False),
                    defense_modifier=defense_mod,
                )

                min_pct = result["min_percent"]
                max_pct = result["max_percent"]
                ko_result = get_ko_result(min_pct, max_pct)

                damage_per_spread.append({
                    "damage": f"{min_pct:.1f}-{max_pct:.1f}%",
                    "result": ko_result,
                })

            calcs.append({
                "move": move["name"],
                "damage": damage_per_spread[0]["damage"],
                "result": damage_per_spread[0]["result"],
                "move_type": move["type"],
                "move_category": move["category"],  # For physical/special check
                "move_power": move["power"],  # For damage recalculation
                "damage_per_spread": damage_per_spread,
            })

        # Build available_moves list for move dropdown
        available_moves = []
        for move in moves:
            if move.get("power", 0) > 0:  # Skip status moves
                available_moves.append({
                    "name": move["name"],
                    "type": move["type"],
                    "power": move["power"],
                    "category": move["category"],
                })

        defensive_benchmarks.append({
            "threat": threat_name.title().replace("-", " "),
            "spread": default_spread["spread"],
            "item": default_spread["item"],
            "common_spreads": common_spreads,
            "calcs": calcs,
            "available_moves": available_moves,  # All moves for dropdown
            "base_stats": threat_base_stats,  # For JS recalculation
            "types": threat_types,  # For STAB calculations
        })

    # Generate offensive benchmarks (your damage to targets)
    offensive_benchmarks = []
    # Similar logic but calculating your damage TO targets
    # (Simplified for now - would mirror the defensive logic)

    return {
        "pokemon": pokemon_data,
        "defensive_benchmarks": defensive_benchmarks,
        "offensive_benchmarks": offensive_benchmarks,
    }


# Synchronous wrapper for easier use
def generate_benchmark_data_sync(
    pokemon_name: str,
    pokemon_nature: str,
    pokemon_evs: dict,
    pokemon_base_stats: dict,
    pokemon_types: list[str],
    pokemon_item: str = "",
    threats: list[str] = None,
    targets: list[str] = None,
) -> dict:
    """Synchronous wrapper for generate_defensive_benchmark_data."""
    return asyncio.run(generate_defensive_benchmark_data(
        pokemon_name=pokemon_name,
        pokemon_nature=pokemon_nature,
        pokemon_evs=pokemon_evs,
        pokemon_base_stats=pokemon_base_stats,
        pokemon_types=pokemon_types,
        pokemon_item=pokemon_item,
        threats=threats,
        targets=targets,
    ))
