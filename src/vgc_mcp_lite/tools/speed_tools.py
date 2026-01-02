"""MCP tools for speed comparisons, calculations, and tier visualization."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.stats import calculate_speed, find_speed_evs
from vgc_mcp_core.calc.speed import SPEED_BENCHMARKS, calculate_speed_tier
from vgc_mcp_core.models.pokemon import Nature

# MCP-UI support (enabled in vgc-mcp-lite)
from ..ui.resources import (
    create_speed_tier_resource,
    create_summary_table_resource,
    create_speed_outspeed_graph_resource,
    add_ui_metadata,
)
HAS_UI = True


# Common VGC Pokemon with their base speeds and common speed investments
META_SPEED_TIERS = {
    # Ultra fast (200+)
    "regieleki": {"base": 200, "common_speeds": [277, 252, 200]},

    # Very fast (135-150)
    "electrode-hisui": {"base": 150, "common_speeds": [222, 202]},
    "dragapult": {"base": 142, "common_speeds": [213, 194]},
    "iron-bundle": {"base": 136, "common_speeds": [205, 187, 136]},
    "flutter-mane": {"base": 135, "common_speeds": [205, 187, 157]},
    "miraidon": {"base": 135, "common_speeds": [205, 187]},
    "koraidon": {"base": 135, "common_speeds": [205, 187]},
    "meowscarada": {"base": 123, "common_speeds": [192, 175]},

    # Fast (100-120)
    "chien-pao": {"base": 135, "common_speeds": [205, 187]},
    "iron-moth": {"base": 110, "common_speeds": [178, 162]},
    "raging-bolt": {"base": 110, "common_speeds": [178, 162, 110]},
    "gouging-fire": {"base": 110, "common_speeds": [178, 162]},
    "walking-wake": {"base": 109, "common_speeds": [177, 161]},
    "entei": {"base": 100, "common_speeds": [167, 152, 157]},
    "urshifu": {"base": 97, "common_speeds": [163, 148]},
    "urshifu-rapid-strike": {"base": 97, "common_speeds": [163, 148]},
    "landorus": {"base": 101, "common_speeds": [168, 153]},
    "garchomp": {"base": 102, "common_speeds": [169, 154]},
    "arcanine": {"base": 95, "common_speeds": [161, 146, 95]},
    "arcanine-hisui": {"base": 90, "common_speeds": [156, 141, 90]},

    # Medium (70-95)
    "ogerpon": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-wellspring": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-hearthflame": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-cornerstone": {"base": 110, "common_speeds": [178, 162]},
    "kingambit": {"base": 50, "common_speeds": [70, 50]},
    "gholdengo": {"base": 84, "common_speeds": [150, 136]},
    "palafin": {"base": 100, "common_speeds": [167, 152]},
    "annihilape": {"base": 90, "common_speeds": [156, 142]},
    "dragonite": {"base": 80, "common_speeds": [145, 132, 80]},
    "gyarados": {"base": 81, "common_speeds": [146, 133]},
    "pelipper": {"base": 65, "common_speeds": [126, 85]},

    # Slow (50-70)
    "rillaboom": {"base": 85, "common_speeds": [150, 137, 85]},
    "incineroar": {"base": 60, "common_speeds": [123, 92, 60]},
    "amoonguss": {"base": 30, "common_speeds": [31, 30]},
    "porygon2": {"base": 60, "common_speeds": [92, 60]},
    "dondozo": {"base": 35, "common_speeds": [75, 35]},
    "torkoal": {"base": 20, "common_speeds": [40, 20]},

    # Very Slow / Trick Room (under 50)
    "iron-hands": {"base": 50, "common_speeds": [70, 50]},
    "ursaluna": {"base": 50, "common_speeds": [70, 50]},
    "ursaluna-bloodmoon": {"base": 52, "common_speeds": [73, 52]},
    "calyrex-ice": {"base": 50, "common_speeds": [70, 50, 36]},
    "calyrex-shadow": {"base": 150, "common_speeds": [222, 202]},
    "glimmora": {"base": 70, "common_speeds": [134, 122]},
    "hatterene": {"base": 29, "common_speeds": [49, 29]},
    "indeedee-f": {"base": 95, "common_speeds": [161, 146]},
    "farigiraf": {"base": 60, "common_speeds": [123, 60]},
    "kyogre": {"base": 90, "common_speeds": [156, 142]},
    "groudon": {"base": 90, "common_speeds": [156, 142]},
}


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

            diff = abs(speed1 - speed2)

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon 1        | {pokemon1_name} (Speed: {speed1})          |",
                f"| Pokemon 2        | {pokemon2_name} (Speed: {speed2})          |",
                f"| Result           | {result}                                   |",
                f"| Difference       | {'+' if speed1 != speed2 else ''}{diff} speed |",
            ]

            # Build analysis prose
            if winner == "tie":
                analysis_str = f"Speed tie between {pokemon1_name} and {pokemon2_name} at {speed1}"
            else:
                faster = pokemon1_name if speed1 > speed2 else pokemon2_name
                faster_speed = max(speed1, speed2)
                slower_speed = min(speed1, speed2)
                analysis_str = f"{faster} outspeeds ({faster_speed} vs {slower_speed})"

            result_dict = {
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
                "difference": diff,
                "result": result,
                "winner": winner,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

            # Add MCP-UI summary table
            if HAS_UI:
                try:
                    table_rows = [
                        {"metric": "Pokemon 1", "value": f"{pokemon1_name} ({speed1} Spe)"},
                        {"metric": "Pokemon 2", "value": f"{pokemon2_name} ({speed2} Spe)"},
                        {"metric": "Speed Difference", "value": str(abs(speed1 - speed2))},
                        {"metric": "Result", "value": result},
                    ]
                    ui_resource = create_summary_table_resource(
                        title="Speed Comparison",
                        rows=table_rows,
                        highlight_rows=["Result"],
                        analysis=result,
                    )
                    result_dict = add_ui_metadata(result_dict, ui_resource)
                except Exception:
                    pass  # UI is optional

            return result_dict

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

                # Build summary table
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Pokemon          | {pokemon_name}                             |",
                    f"| Target Speed     | {target_speed}                             |",
                    f"| Nature           | {nature}                                   |",
                    f"| Max Achievable   | {max_speed} (252 EVs)                      |",
                    f"| Result           | Cannot reach target                        |",
                ]

                result_dict = {
                    "pokemon": pokemon_name,
                    "target_speed": target_speed,
                    "achievable": False,
                    "max_speed_with_252_evs": max_speed,
                    "suggestion": "Try a +Speed nature (Timid/Jolly) or lower your target",
                    "summary_table": "\n".join(table_lines),
                    "analysis": f"{pokemon_name} cannot reach {target_speed} Speed with {nature} nature. Max achievable is {max_speed}."
                }

                # Add MCP-UI summary table
                if HAS_UI:
                    try:
                        table_rows = [
                            {"metric": "Pokemon", "value": pokemon_name},
                            {"metric": "Target Speed", "value": str(target_speed)},
                            {"metric": "Nature", "value": nature},
                            {"metric": "Max Achievable", "value": f"{max_speed} (252 EVs)"},
                            {"metric": "Result", "value": "Cannot reach target"},
                        ]
                        ui_resource = create_summary_table_resource(
                            title="Speed EV Calculation",
                            rows=table_rows,
                            highlight_rows=["Result"],
                            analysis=f"{pokemon_name} cannot reach {target_speed} Speed with {nature} nature. Max achievable is {max_speed}.",
                        )
                        result_dict = add_ui_metadata(result_dict, ui_resource)
                    except Exception:
                        pass

                return result_dict

            actual_speed = calculate_speed(base_stats.speed, 31, evs_needed, 50, parsed_nature)

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Target Speed     | {target_speed}                             |",
                f"| Nature           | {nature}                                   |",
                f"| EVs Needed       | {evs_needed}                               |",
                f"| Actual Speed     | {actual_speed}                             |",
                f"| EVs Remaining    | {508 - evs_needed}                         |",
            ]

            result_dict = {
                "pokemon": pokemon_name,
                "target_speed": target_speed,
                "achievable": True,
                "evs_needed": evs_needed,
                "actual_speed": actual_speed,
                "evs_remaining": 508 - evs_needed,
                "summary_table": "\n".join(table_lines),
                "analysis": f"Need {evs_needed} Speed EVs to reach {actual_speed}, outspeeding target speed {target_speed}"
            }

            # Add MCP-UI summary table
            if HAS_UI:
                try:
                    table_rows = [
                        {"metric": "Pokemon", "value": pokemon_name},
                        {"metric": "Target Speed", "value": str(target_speed)},
                        {"metric": "Nature", "value": nature},
                        {"metric": "EVs Needed", "value": str(evs_needed)},
                        {"metric": "Actual Speed", "value": str(actual_speed)},
                        {"metric": "EVs Remaining", "value": str(508 - evs_needed)},
                    ]
                    ui_resource = create_summary_table_resource(
                        title="Speed EV Calculation",
                        rows=table_rows,
                        highlight_rows=["EVs Needed", "Actual Speed"],
                        analysis=f"{pokemon_name} needs {evs_needed} Speed EVs to reach {actual_speed} Speed (target: {target_speed}).",
                    )
                    result_dict = add_ui_metadata(result_dict, ui_resource)
                except Exception:
                    pass

            return result_dict

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

    # ========== Speed Tier Visualization Tools (merged from speed_tier_tools.py) ==========

    @mcp.tool()
    async def visualize_speed_tiers(
        pokemon_speeds: list[dict],
        include_tailwind: bool = False,
        include_trick_room: bool = False,
        compare_to_meta: bool = True
    ) -> dict:
        """
        Visualize speed tiers as a text-based chart.

        Args:
            pokemon_speeds: List of dicts with 'name' and 'speed' keys
                           e.g., [{"name": "Entei", "speed": 157}, {"name": "Flutter Mane", "speed": 205}]
            include_tailwind: Show doubled speeds
            include_trick_room: Show order reversed (slowest first)
            compare_to_meta: Include common meta Pokemon for reference

        Returns:
            Text-based speed tier visualization
        """
        all_pokemon = []

        # Add user's Pokemon
        for p in pokemon_speeds:
            all_pokemon.append({
                "name": p["name"],
                "speed": p["speed"],
                "is_yours": True,
                "tailwind_speed": p["speed"] * 2 if include_tailwind else None
            })

        # Add meta Pokemon for reference
        if compare_to_meta:
            for mon, data in META_SPEED_TIERS.items():
                for speed in data["common_speeds"][:2]:  # Top 2 common speeds
                    all_pokemon.append({
                        "name": mon,
                        "speed": speed,
                        "is_yours": False,
                        "base_speed": data["base"],
                        "tailwind_speed": speed * 2 if include_tailwind else None
                    })

        # Sort by speed (descending for normal, ascending for TR)
        if include_trick_room:
            all_pokemon.sort(key=lambda x: x["speed"])
        else:
            all_pokemon.sort(key=lambda x: -x["speed"])

        # Build visualization
        lines = []
        mode = "Trick Room" if include_trick_room else "Normal"
        lines.append(f"=== SPEED TIERS ({mode}) ===")
        lines.append("")

        current_tier = None
        for p in all_pokemon:
            speed = p["speed"]

            # Determine tier
            if speed >= 200:
                tier = "ULTRA FAST"
            elif speed >= 150:
                tier = "VERY FAST"
            elif speed >= 120:
                tier = "FAST"
            elif speed >= 90:
                tier = "MEDIUM"
            elif speed >= 60:
                tier = "SLOW"
            else:
                tier = "VERY SLOW"

            if tier != current_tier:
                lines.append(f"--- {tier} ---")
                current_tier = tier

            marker = ">>>" if p["is_yours"] else "   "
            tw_info = f" (TW: {p['tailwind_speed']})" if p.get("tailwind_speed") else ""
            lines.append(f"{marker} {speed:3d} | {p['name']}{tw_info}")

        # Summary
        your_pokemon = [p for p in all_pokemon if p["is_yours"]]
        if your_pokemon:
            lines.append("")
            lines.append("=== YOUR TEAM SUMMARY ===")
            fastest = max(your_pokemon, key=lambda x: x["speed"])
            slowest = min(your_pokemon, key=lambda x: x["speed"])
            lines.append(f"Fastest: {fastest['name']} ({fastest['speed']})")
            lines.append(f"Slowest: {slowest['name']} ({slowest['speed']})")

            # What you outspeed/underspeed
            outspeeds = []
            underspeeds = []
            for p in all_pokemon:
                if not p["is_yours"]:
                    if fastest["speed"] > p["speed"]:
                        outspeeds.append(p["name"])
                    elif slowest["speed"] < p["speed"]:
                        underspeeds.append(p["name"])

            if outspeeds:
                lines.append(f"Your fastest outspeeds: {', '.join(set(outspeeds)[:5])}")
            if underspeeds:
                lines.append(f"Faster than your slowest: {', '.join(set(underspeeds)[:5])}")

        result = {
            "visualization": "\n".join(lines),
            "your_pokemon": your_pokemon,
            "mode": mode
        }

        # Add MCP-UI resource for interactive speed tier display (only in vgc-mcp-lite)
        if HAS_UI:
            try:
                if your_pokemon:
                    # Get the first user Pokemon as the primary one
                    primary = your_pokemon[0]
                    # Build speed tiers list for UI
                    speed_tier_list = [
                        {"name": p["name"], "speed": p["speed"], "common": not p["is_yours"]}
                        for p in all_pokemon
                    ]
                    ui_resource = create_speed_tier_resource(
                        pokemon_name=primary["name"],
                        pokemon_speed=primary["speed"],
                        speed_tiers=speed_tier_list,
                        modifiers={
                            "tailwind": include_tailwind,
                            "trick_room": include_trick_room,
                        },
                    )
                    result = add_ui_metadata(result, ui_resource)
            except Exception:
                # UI is optional
                pass

        return result

    @mcp.tool()
    async def get_meta_speed_tiers(
        format_type: str = "general",
        tier: Optional[str] = None
    ) -> dict:
        """
        Get common speed tiers in the current VGC metagame.

        Args:
            format_type: "general", "trick_room", or "tailwind"
            tier: Optional filter - "fast", "medium", "slow"

        Returns:
            Speed tier information for meta Pokemon
        """
        result = []

        for mon, data in META_SPEED_TIERS.items():
            base = data["base"]
            speeds = data["common_speeds"]

            entry = {
                "pokemon": mon,
                "base_speed": base,
                "common_speeds": speeds,
                "max_speed_positive": calculate_speed(base, 31, 252, 50, Nature.JOLLY),
                "max_speed_neutral": calculate_speed(base, 31, 252, 50, Nature.HARDY),
                "min_speed": calculate_speed(base, 0, 0, 50, Nature.BRAVE),
            }

            # Categorize
            if base >= 120:
                entry["tier"] = "fast"
            elif base >= 80:
                entry["tier"] = "medium"
            else:
                entry["tier"] = "slow"

            # Filter by tier if specified
            if tier and entry["tier"] != tier.lower():
                continue

            result.append(entry)

        # Sort by base speed
        result.sort(key=lambda x: -x["base_speed"])

        # Add tailwind/TR info if requested
        if format_type == "tailwind":
            for entry in result:
                entry["tailwind_max"] = entry["max_speed_positive"] * 2
        elif format_type == "trick_room":
            result.sort(key=lambda x: x["base_speed"])  # Reverse order

        return {
            "format": format_type,
            "tier_filter": tier,
            "pokemon_count": len(result),
            "speed_tiers": result
        }

    @mcp.tool()
    async def find_speed_benchmark(
        target_speed: int,
        nature: str = "jolly",
        pokemon_name: Optional[str] = None
    ) -> dict:
        """
        Find what Pokemon/spreads hit a specific speed stat.

        Args:
            target_speed: The speed stat to analyze
            nature: Nature to assume for calculations
            pokemon_name: Optional - find EVs needed for this Pokemon to hit target

        Returns:
            Analysis of what Pokemon hit this speed tier
        """
        results = {
            "target_speed": target_speed,
            "pokemon_at_this_speed": [],
            "pokemon_above": [],
            "pokemon_below": []
        }

        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            nature_enum = Nature.JOLLY

        # If specific Pokemon requested, calculate EVs needed
        if pokemon_name:
            try:
                data = await pokeapi.get_pokemon(pokemon_name)
                base_speed = data["base_stats"]["speed"]

                from ..config import EV_BREAKPOINTS_LV50

                evs_needed = None
                for ev in EV_BREAKPOINTS_LV50:
                    speed = calculate_speed(base_speed, 31, ev, 50, nature_enum)
                    if speed >= target_speed:
                        evs_needed = ev
                        break

                results["your_pokemon"] = {
                    "name": pokemon_name,
                    "base_speed": base_speed,
                    "evs_needed": evs_needed,
                    "resulting_speed": calculate_speed(base_speed, 31, evs_needed or 252, 50, nature_enum) if evs_needed else None,
                    "can_reach": evs_needed is not None
                }
            except Exception as e:
                results["your_pokemon"] = {"error": str(e)}

        # Check meta Pokemon
        for mon, data in META_SPEED_TIERS.items():
            max_speed = calculate_speed(data["base"], 31, 252, 50, Nature.JOLLY)
            neutral_max = calculate_speed(data["base"], 31, 252, 50, Nature.HARDY)

            if max_speed == target_speed or neutral_max == target_speed:
                results["pokemon_at_this_speed"].append({
                    "pokemon": mon,
                    "base": data["base"],
                    "investment": "252 EVs" + (" +Speed" if max_speed == target_speed else " neutral")
                })
            elif max_speed > target_speed:
                results["pokemon_above"].append({
                    "pokemon": mon,
                    "max_speed": max_speed
                })
            else:
                results["pokemon_below"].append({
                    "pokemon": mon,
                    "max_speed": max_speed
                })

        # Sort
        results["pokemon_above"].sort(key=lambda x: x["max_speed"])
        results["pokemon_below"].sort(key=lambda x: -x["max_speed"])

        # Trim to top 10
        results["pokemon_above"] = results["pokemon_above"][:10]
        results["pokemon_below"] = results["pokemon_below"][:10]

        return results

    @mcp.tool()
    async def analyze_outspeed_probability(
        pokemon_name: str,
        target_pokemon: str,
        nature: str = "serious",
        speed_evs: int = 0
    ) -> dict:
        """
        Analyze what percentage of a target Pokemon's common spreads you outspeed.
        Shows a cumulative distribution graph of outspeed probability.

        Args:
            pokemon_name: Your Pokemon's name
            target_pokemon: The target Pokemon to compare against
            nature: Your Pokemon's nature
            speed_evs: Your Pokemon's Speed EVs

        Returns:
            Analysis showing what percentage of target spreads you outspeed
        """
        try:
            # Get base stats for your Pokemon
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Calculate your speed
            your_speed = calculate_speed(base_stats.speed, 31, speed_evs, 50, parsed_nature)

            # Get target Pokemon's common spreads from META_SPEED_TIERS
            target_lower = target_pokemon.lower().replace(" ", "-")
            target_data = META_SPEED_TIERS.get(target_lower)

            if not target_data:
                # If not in meta tiers, calculate standard spreads
                try:
                    target_base = await pokeapi.get_base_stats(target_pokemon)
                    target_spreads = [
                        {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.JOLLY), "usage": 35},
                        {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.SERIOUS), "usage": 25},
                        {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.SERIOUS), "usage": 20},
                        {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.BRAVE), "usage": 20},
                    ]
                except Exception:
                    return {"error": f"Could not find data for {target_pokemon}"}
            else:
                # Build spreads from common_speeds
                common_speeds = target_data["common_speeds"]
                usage_per = 100 // len(common_speeds) if common_speeds else 100
                target_spreads = [
                    {"speed": s, "usage": usage_per}
                    for s in common_speeds
                ]

            # Calculate outspeed percentage
            total_usage = sum(s["usage"] for s in target_spreads)
            outsped_usage = sum(
                s["usage"] for s in target_spreads
                if your_speed > s["speed"]
            )
            tied_usage = sum(
                s["usage"] for s in target_spreads
                if your_speed == s["speed"]
            )

            outspeed_percent = (outsped_usage / total_usage * 100) if total_usage > 0 else 0
            tie_percent = (tied_usage / total_usage * 100) if total_usage > 0 else 0

            # Determine result description
            if outspeed_percent >= 100:
                result_text = f"{pokemon_name} outspeeds all common {target_pokemon} spreads"
            elif outspeed_percent > 50:
                result_text = f"{pokemon_name} outspeeds most common {target_pokemon} spreads"
            elif outspeed_percent > 0:
                result_text = f"{pokemon_name} outspeeds some common {target_pokemon} spreads"
            else:
                result_text = f"{pokemon_name} is outsped by all common {target_pokemon} spreads"

            # Build summary table
            spreads_str = ", ".join([str(s["speed"]) for s in target_spreads[:3]])
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Your Pokemon     | {pokemon_name} ({your_speed} Spe)          |",
                f"| Target Pokemon   | {target_pokemon}                           |",
                f"| Target Spreads   | {spreads_str}...                           |",
                f"| Outspeed %       | {round(outspeed_percent, 1)}%              |",
                f"| Tie %            | {round(tie_percent, 1)}%                   |",
                f"| Result           | {result_text}                              |",
            ]

            result_dict = {
                "pokemon": pokemon_name,
                "your_speed": your_speed,
                "nature": nature,
                "speed_evs": speed_evs,
                "target_pokemon": target_pokemon,
                "target_spreads": target_spreads,
                "outspeed_percent": round(outspeed_percent, 1),
                "tie_percent": round(tie_percent, 1),
                "result": result_text,
                "summary_table": "\n".join(table_lines),
                "analysis": f"{pokemon_name} ({your_speed} Speed) outspeeds {round(outspeed_percent, 1)}% of {target_pokemon} spreads"
            }

            # Add MCP-UI outspeed graph
            if HAS_UI:
                try:
                    ui_resource = create_speed_outspeed_graph_resource(
                        pokemon_name=pokemon_name,
                        pokemon_speed=your_speed,
                        target_pokemon=target_pokemon,
                        target_spreads=target_spreads,
                        outspeed_percent=outspeed_percent,
                    )
                    result_dict = add_ui_metadata(result_dict, ui_resource)
                except Exception:
                    pass  # UI is optional

            return result_dict

        except Exception as e:
            return {"error": str(e)}
