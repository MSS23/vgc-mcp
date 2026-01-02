"""Chip damage tools for VGC MCP server.

Tools for calculating passive damage and healing over time:
- Weather damage (Sandstorm, Hail/Snow)
- Status damage (Burn, Poison, Toxic)
- Terrain healing (Grassy Terrain)
- Item recovery (Leftovers, Black Sludge)
- Multi-turn survival calculations
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional

from vgc_mcp_core.calc.chip_damage import (
    calculate_weather_chip,
    calculate_status_damage,
    calculate_terrain_healing,
    calculate_leftovers_recovery,
    calculate_total_chip_damage,
    SANDSTORM_IMMUNE_TYPES,
    HAIL_IMMUNE_TYPES,
)
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.utils.errors import error_response, success_response


def register_chip_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register chip damage calculation tools."""

    @mcp.tool()
    async def calculate_weather_damage(
        pokemon_name: str,
        weather: str,
        hp_evs: int = 0,
        hp_ivs: int = 31,
        ability: str = ""
    ) -> dict:
        """
        Calculate weather chip damage for a Pokemon.

        Sandstorm: 6.25% damage per turn (Rock/Ground/Steel immune)
        Hail/Snow: 6.25% damage per turn (Ice immune)
        Sun/Rain: No passive damage

        Args:
            pokemon_name: Pokemon name
            weather: Weather condition (sandstorm, hail, snow, sun, rain)
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            ability: Pokemon's ability (for immunity check)

        Returns:
            Damage per turn, immunity status, and turns until faint from weather alone
        """
        try:
            # Get Pokemon data
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            if not pokemon_data:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("stats_not_found", f"Could not get stats for: {pokemon_name}")

            # Get types
            types = [t["type"]["name"] for t in pokemon_data.get("types", [])]

            # Calculate HP
            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10

            result = calculate_weather_chip(weather, max_hp, max_hp, types, ability)

            turns_to_faint = None
            if not result.immune and result.damage > 0:
                turns_to_faint = max_hp // result.damage

            # Build summary table
            status_str = "Immune" if result.immune else f"{result.damage} ({result.damage_percent}%)"
            faint_str = str(turns_to_faint) if turns_to_faint else "N/A (immune)"
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Weather          | {weather.title() if weather else 'None'}   |",
                f"| Max HP           | {max_hp}                                   |",
                f"| Damage/Turn      | {status_str}                               |",
                f"| Turns to KO      | {faint_str}                                |",
            ]

            return {
                "pokemon": pokemon_name,
                "types": types,
                "weather": weather.title() if weather else "None",
                "max_hp": max_hp,
                "damage_per_turn": result.damage,
                "damage_percent": result.damage_percent,
                "immune": result.immune,
                "immunity_reason": result.immunity_reason,
                "turns_to_faint": turns_to_faint,
                "notes": result.notes,
                "immune_types": {
                    "sandstorm": list(SANDSTORM_IMMUNE_TYPES),
                    "hail": list(HAIL_IMMUNE_TYPES),
                }.get(weather.lower(), []) if weather else [],
                "summary_table": "\n".join(table_lines)
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_status_chip(
        pokemon_name: str,
        status: str,
        toxic_turn: int = 1,
        hp_evs: int = 0,
        hp_ivs: int = 31,
        ability: str = ""
    ) -> dict:
        """
        Calculate status condition damage for a Pokemon.

        Burn: 6.25% damage per turn (also halves physical attack)
        Poison: 12.5% damage per turn
        Toxic: N/16 damage per turn (N = turn counter, caps at 15)

        Args:
            pokemon_name: Pokemon name
            status: Status condition (burn, poison, toxic)
            toxic_turn: For Toxic, which turn of poison (1-15)
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            ability: Pokemon's ability (Poison Heal, Magic Guard, Guts)

        Returns:
            Damage per turn, special ability interactions
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            # Calculate HP
            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10

            result = calculate_status_damage(status, max_hp, max_hp, toxic_turn, ability)

            turns_to_faint = None
            if not result.immune and result.damage > 0:
                if status.lower() in ["toxic", "badly_poisoned"]:
                    # Toxic increases - need to sum damage
                    hp_remaining = max_hp
                    turns = 0
                    for i in range(1, 16):
                        damage = (max_hp * i) // 16
                        hp_remaining -= damage
                        turns += 1
                        if hp_remaining <= 0:
                            break
                    turns_to_faint = turns
                else:
                    turns_to_faint = max_hp // result.damage

            return {
                "pokemon": pokemon_name,
                "status": status.title(),
                "max_hp": max_hp,
                "damage_per_turn": abs(result.damage),
                "damage_percent": abs(result.damage_percent),
                "is_healing": result.is_healing,
                "immune": result.immune,
                "immunity_reason": result.immunity_reason,
                "turns_to_faint": turns_to_faint,
                "notes": result.notes,
                "toxic_progression": [
                    {"turn": i, "damage": (max_hp * i) // 16, "percent": round(i / 16 * 100, 1)}
                    for i in range(1, 6)
                ] if status.lower() in ["toxic", "badly_poisoned"] else None
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_grassy_terrain_healing(
        pokemon_name: str,
        hp_evs: int = 0,
        hp_ivs: int = 31,
        is_flying: bool = False,
        has_levitate: bool = False
    ) -> dict:
        """
        Calculate Grassy Terrain healing for a Pokemon.

        Grassy Terrain heals grounded Pokemon for 6.25% HP per turn.
        Also reduces Earthquake/Bulldoze/Magnitude damage by 50%.

        Args:
            pokemon_name: Pokemon name
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            is_flying: Whether Pokemon is Flying-type (not grounded)
            has_levitate: Whether Pokemon has Levitate (not grounded)

        Returns:
            Healing per turn, grounded status
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            # Check if Flying type from API
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            types = [t["type"]["name"] for t in pokemon_data.get("types", [])] if pokemon_data else []
            is_grounded = "flying" not in types and not has_levitate

            # Calculate HP
            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10

            result = calculate_terrain_healing("grassy", max_hp, max_hp, is_grounded)

            return {
                "pokemon": pokemon_name,
                "types": types,
                "terrain": "Grassy Terrain",
                "max_hp": max_hp,
                "healing_per_turn": abs(result.damage) if result.is_healing else 0,
                "healing_percent": abs(result.damage_percent) if result.is_healing else 0,
                "is_grounded": is_grounded,
                "receives_healing": result.is_healing,
                "reason": result.immunity_reason if result.immune else "Grounded and receives healing",
                "notes": result.notes,
                "additional_effects": [
                    "Earthquake damage reduced by 50%",
                    "Bulldoze damage reduced by 50%",
                    "Magnitude damage reduced by 50%"
                ]
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_leftovers_healing(
        pokemon_name: str,
        item: str = "leftovers",
        hp_evs: int = 0,
        hp_ivs: int = 31,
        is_poison_type: bool = False
    ) -> dict:
        """
        Calculate Leftovers or Black Sludge recovery.

        Leftovers: Heals 6.25% HP per turn (any Pokemon)
        Black Sludge: Heals 6.25% for Poison-types, damages 12.5% for others

        Args:
            pokemon_name: Pokemon name
            item: "leftovers" or "black-sludge"
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            is_poison_type: Override for Poison-type check (Black Sludge)

        Returns:
            Recovery per turn, item-specific notes
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            # Check if Poison type from API
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            types = [t["type"]["name"] for t in pokemon_data.get("types", [])] if pokemon_data else []
            is_poison = is_poison_type or "poison" in types

            # Calculate HP
            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10

            item_lower = item.lower().replace(" ", "-")

            # Black Sludge damages non-Poison types
            if item_lower == "black-sludge" and not is_poison:
                damage = max_hp // 8  # 12.5% damage
                return {
                    "pokemon": pokemon_name,
                    "types": types,
                    "item": "Black Sludge",
                    "max_hp": max_hp,
                    "effect": "DAMAGE",
                    "damage_per_turn": damage,
                    "damage_percent": 12.5,
                    "warning": "Black Sludge damages non-Poison types!",
                    "recommendation": "Use Leftovers instead for non-Poison types"
                }

            result = calculate_leftovers_recovery(max_hp, max_hp, item)

            return {
                "pokemon": pokemon_name,
                "types": types,
                "item": item.replace("-", " ").title(),
                "max_hp": max_hp,
                "effect": "HEALING",
                "healing_per_turn": abs(result.damage),
                "healing_percent": abs(result.damage_percent),
                "turns_to_full_heal": max_hp // abs(result.damage) if result.damage != 0 else None,
                "notes": result.notes,
                "black_sludge_note": "Safe to use - Pokemon is Poison-type" if item_lower == "black-sludge" and is_poison else None
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def simulate_chip_over_turns(
        pokemon_name: str,
        turns: int = 5,
        weather: str = "",
        status: str = "",
        terrain: str = "",
        item: str = "",
        hp_evs: int = 0,
        hp_ivs: int = 31,
        ability: str = "",
        starting_hp_percent: float = 100.0
    ) -> dict:
        """
        Simulate chip damage/healing over multiple turns.

        Combines weather, status, terrain, and item effects to project
        HP changes over time. Essential for planning long battles.

        Args:
            pokemon_name: Pokemon name
            turns: Number of turns to simulate (1-20)
            weather: Active weather (sandstorm, hail, snow, sun, rain)
            status: Status condition (burn, poison, toxic)
            terrain: Active terrain (grassy, electric, psychic, misty)
            item: Held item (leftovers, black-sludge)
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            ability: Pokemon's ability
            starting_hp_percent: Starting HP as percentage (0-100)

        Returns:
            Turn-by-turn HP breakdown, when Pokemon would faint
        """
        try:
            turns = min(20, max(1, turns))

            # Get Pokemon data
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            if not pokemon_data:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("stats_not_found", f"Could not get stats for: {pokemon_name}")

            # Get types
            types = [t["type"]["name"] for t in pokemon_data.get("types", [])]
            is_grounded = "flying" not in types and ability.lower() not in ["levitate"]

            # Calculate HP
            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10
            starting_hp = int(max_hp * starting_hp_percent / 100)

            result = calculate_total_chip_damage(
                current_hp=starting_hp,
                max_hp=max_hp,
                turns=turns,
                weather=weather if weather else None,
                status=status if status else None,
                terrain=terrain if terrain else None,
                item=item if item else None,
                pokemon_types=types,
                ability=ability if ability else None,
                is_grounded=is_grounded
            )

            # Add strategic insights
            insights = []
            if result["fainted"]:
                insights.append(f"[!] Pokemon faints from chip damage on turn {result['turns_simulated']}")
            if result["total_healing"] > result["total_damage"]:
                insights.append(f"Net healing: Pokemon recovers {result['net_change']} HP over {turns} turns")
            if result["total_damage"] > result["total_healing"]:
                insights.append(f"Net damage: Pokemon loses {-result['net_change']} HP over {turns} turns")
            if status.lower() == "toxic" and not result["fainted"]:
                insights.append("Toxic damage accelerates - consider switching to reset counter")

            # Build summary table
            sources_str = ", ".join([s for s in [weather, status, terrain, item] if s]) or "None"
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Starting HP      | {starting_hp} ({starting_hp_percent}%)     |",
                f"| After {turns} turns  | {result['final_hp']} ({result['final_hp_percent']}%) |",
                f"| Net Change       | {result['net_change']} HP                  |",
                f"| Sources          | {sources_str}                              |",
            ]
            if result["fainted"]:
                table_lines.append(f"| Faints On        | Turn {result['turns_simulated']}           |")

            return {
                "pokemon": pokemon_name,
                "types": types,
                "conditions": {
                    "weather": weather or "None",
                    "status": status or "None",
                    "terrain": terrain or "None",
                    "item": item or "None"
                },
                **result,
                "insights": insights,
                "summary_table": "\n".join(table_lines)
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_survival_with_chip(
        pokemon_name: str,
        incoming_damage_percent: float,
        weather: str = "",
        status: str = "",
        terrain: str = "",
        item: str = "",
        hp_evs: int = 0,
        hp_ivs: int = 31,
        ability: str = ""
    ) -> dict:
        """
        Calculate if a Pokemon survives an attack plus chip damage.

        Useful for determining if you can afford to take a hit and still
        survive end-of-turn effects.

        Args:
            pokemon_name: Pokemon name
            incoming_damage_percent: Damage from attack as % of max HP
            weather: Active weather
            status: Status condition
            terrain: Active terrain
            item: Held item
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            ability: Pokemon's ability

        Returns:
            HP after attack, HP after chip, survival status
        """
        try:
            # Get Pokemon data
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            if not pokemon_data:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            types = [t["type"]["name"] for t in pokemon_data.get("types", [])]
            is_grounded = "flying" not in types and ability.lower() not in ["levitate"]

            # Calculate HP
            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10

            # Calculate damage from attack
            attack_damage = int(max_hp * incoming_damage_percent / 100)
            hp_after_attack = max(0, max_hp - attack_damage)

            if hp_after_attack == 0:
                return {
                    "pokemon": pokemon_name,
                    "max_hp": max_hp,
                    "attack_damage": attack_damage,
                    "hp_after_attack": 0,
                    "survives_attack": False,
                    "hp_after_chip": 0,
                    "survives_turn": False,
                    "verdict": "KO'd by attack before chip damage applies"
                }

            # Calculate chip damage for one turn
            result = calculate_total_chip_damage(
                current_hp=hp_after_attack,
                max_hp=max_hp,
                turns=1,
                weather=weather if weather else None,
                status=status if status else None,
                terrain=terrain if terrain else None,
                item=item if item else None,
                pokemon_types=types,
                ability=ability if ability else None,
                is_grounded=is_grounded
            )

            survives_turn = result["final_hp"] > 0
            hp_after_attack_percent = round((hp_after_attack / max_hp) * 100, 1)

            verdict_str = (
                "Survives attack and end-of-turn effects" if survives_turn
                else "Survives attack but faints to chip damage"
            )

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Max HP           | {max_hp}                                   |",
                f"| Attack Damage    | {attack_damage} ({incoming_damage_percent}%) |",
                f"| HP After Attack  | {hp_after_attack} ({hp_after_attack_percent}%) |",
                f"| Chip Change      | {result['net_change']} HP                  |",
                f"| HP After Chip    | {result['final_hp']} ({result['final_hp_percent']}%) |",
                f"| Verdict          | {verdict_str}                              |",
            ]

            return {
                "pokemon": pokemon_name,
                "max_hp": max_hp,
                "attack_damage": attack_damage,
                "attack_damage_percent": incoming_damage_percent,
                "hp_after_attack": hp_after_attack,
                "hp_after_attack_percent": hp_after_attack_percent,
                "survives_attack": True,
                "chip_change": result["net_change"],
                "hp_after_chip": result["final_hp"],
                "hp_after_chip_percent": result["final_hp_percent"],
                "survives_turn": survives_turn,
                "verdict": verdict_str,
                "chip_breakdown": result["turn_breakdown"][0] if result["turn_breakdown"] else None,
                "summary_table": "\n".join(table_lines)
            }

        except Exception as e:
            return error_response("calculation_error", str(e))
