"""MCP tools for speed comparisons and calculations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..api.pokeapi import PokeAPIClient
from ..calc.stats import calculate_speed, find_speed_evs
from ..calc.speed import SPEED_BENCHMARKS, calculate_speed_tier
from ..models.pokemon import Nature


def register_speed_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register speed-related tools with the MCP server."""

    @mcp.tool()
    async def compare_speed(
        pokemon1_name: str,
        pokemon2_name: str,
        pokemon1_nature: str = "serious",
        pokemon1_speed_evs: int = 0,
        pokemon2_nature: str = "serious",
        pokemon2_speed_evs: int = 0
    ) -> dict:
        """
        Compare speed between two Pokemon to determine who moves first.

        Args:
            pokemon1_name: First Pokemon's name
            pokemon1_nature: First Pokemon's nature
            pokemon1_speed_evs: First Pokemon's Speed EVs
            pokemon2_name: Second Pokemon's name
            pokemon2_nature: Second Pokemon's nature
            pokemon2_speed_evs: Second Pokemon's Speed EVs

        Returns:
            Speed comparison with who outspeeds whom
        """
        try:
            # Fetch base stats
            base1 = await pokeapi.get_base_stats(pokemon1_name)
            base2 = await pokeapi.get_base_stats(pokemon2_name)

            # Parse natures
            try:
                nature1 = Nature(pokemon1_nature.lower())
                nature2 = Nature(pokemon2_nature.lower())
            except ValueError as e:
                return {"error": f"Invalid nature: {e}"}

            # Calculate speeds
            speed1 = calculate_speed(base1.speed, 31, pokemon1_speed_evs, 50, nature1)
            speed2 = calculate_speed(base2.speed, 31, pokemon2_speed_evs, 50, nature2)

            # Determine result
            if speed1 > speed2:
                result = f"{pokemon1_name} outspeeds {pokemon2_name}"
                winner = pokemon1_name
            elif speed2 > speed1:
                result = f"{pokemon2_name} outspeeds {pokemon1_name}"
                winner = pokemon2_name
            else:
                result = "Speed tie - 50/50 chance to move first"
                winner = "tie"

            return {
                "pokemon1": {
                    "name": pokemon1_name,
                    "base_speed": base1.speed,
                    "nature": pokemon1_nature,
                    "evs": pokemon1_speed_evs,
                    "final_speed": speed1
                },
                "pokemon2": {
                    "name": pokemon2_name,
                    "base_speed": base2.speed,
                    "nature": pokemon2_nature,
                    "evs": pokemon2_speed_evs,
                    "final_speed": speed2
                },
                "difference": abs(speed1 - speed2),
                "result": result,
                "winner": winner
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def find_speed_evs_to_outspeed(
        pokemon_name: str,
        target_speed: int,
        nature: str = "serious"
    ) -> dict:
        """
        Find minimum Speed EVs needed to reach or exceed a target Speed stat.

        Args:
            pokemon_name: Your Pokemon's name
            target_speed: The Speed stat you want to reach/exceed
            nature: Your Pokemon's nature

        Returns:
            Required EVs or indication if target is unreachable
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            evs_needed = find_speed_evs(
                base_stats.speed,
                target_speed,
                parsed_nature,
                31,  # Assume 31 IV
                50   # Level 50
            )

            if evs_needed is None:
                # Calculate max possible
                max_speed = calculate_speed(base_stats.speed, 31, 252, 50, parsed_nature)
                return {
                    "pokemon": pokemon_name,
                    "target_speed": target_speed,
                    "achievable": False,
                    "max_speed_with_252_evs": max_speed,
                    "suggestion": "Try a +Speed nature (Timid/Jolly) or lower your target"
                }

            actual_speed = calculate_speed(base_stats.speed, 31, evs_needed, 50, parsed_nature)

            return {
                "pokemon": pokemon_name,
                "target_speed": target_speed,
                "achievable": True,
                "evs_needed": evs_needed,
                "actual_speed": actual_speed,
                "evs_remaining": 508 - evs_needed
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_speed_tiers(
        min_base_speed: int = 50,
        max_base_speed: int = 200,
        investment: str = "max"
    ) -> dict:
        """
        Get speed tier benchmarks for common VGC Pokemon.

        Args:
            min_base_speed: Minimum base speed to include
            max_base_speed: Maximum base speed to include
            investment: "max" (252 EVs, +nature), "neutral" (0 EVs, neutral), or "min" (0 EVs, -nature, 0 IV)

        Returns:
            List of Pokemon with their speed stats at the specified investment level
        """
        try:
            tiers = []

            for mon_name, data in SPEED_BENCHMARKS.items():
                base = data.get("base", 0)

                if not (min_base_speed <= base <= max_base_speed):
                    continue

                if investment == "max":
                    speed = data.get("max_positive", calculate_speed(base, 31, 252, 50, Nature.JOLLY))
                    config = "+Speed nature, 252 EVs, 31 IV"
                elif investment == "neutral":
                    speed = data.get("max_neutral", calculate_speed(base, 31, 252, 50, Nature.SERIOUS))
                    config = "Neutral nature, 252 EVs, 31 IV"
                elif investment == "min":
                    speed = data.get("min_negative", calculate_speed(base, 0, 0, 50, Nature.BRAVE))
                    config = "-Speed nature, 0 EVs, 0 IV"
                else:
                    speed = data.get("neutral_0ev", calculate_speed(base, 31, 0, 50, Nature.SERIOUS))
                    config = "Neutral nature, 0 EVs, 31 IV"

                tiers.append({
                    "pokemon": mon_name.replace("-", " ").title(),
                    "base_speed": base,
                    "final_speed": speed,
                    "config": config
                })

            # Sort by final speed descending
            tiers.sort(key=lambda x: x["final_speed"], reverse=True)

            return {
                "investment": investment,
                "speed_tiers": tiers
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_speed_spread(
        pokemon_name: str,
        nature: str = "serious",
        speed_evs: int = 0
    ) -> dict:
        """
        Analyze what a specific speed spread outspeeds and underspeeds.

        Args:
            pokemon_name: Pokemon name
            nature: Nature
            speed_evs: Speed EVs

        Returns:
            Analysis of what this spread outspeeds/underspeeds
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            tier_info = calculate_speed_tier(
                base_stats.speed,
                parsed_nature,
                speed_evs,
                31,
                50
            )

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "speed_evs": speed_evs,
                "final_speed": tier_info["speed"],
                "outspeeds": tier_info["outspeeds"],
                "ties_with": tier_info["ties_with"],
                "underspeeds": tier_info["underspeeds"]
            }

        except Exception as e:
            return {"error": str(e)}
