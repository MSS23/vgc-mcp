"""MCP tools for speed comparisons, calculations, and tier visualization."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
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
from ..ui.components import create_interactive_speed_histogram_ui
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


def register_speed_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
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
                    result_dict = add_ui_metadata(
                        result_dict, ui_resource,
                        display_type="inline",
                        name="Speed Comparison"
                    )
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
                        result_dict = add_ui_metadata(
                            result_dict, ui_resource,
                            display_type="inline",
                            name="Speed EVs"
                        )
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
                    result_dict = add_ui_metadata(
                        result_dict, ui_resource,
                        display_type="inline",
                        name="Speed EVs"
                    )
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
            compare_to_meta: Include common meta Pokemon for reference (uses Smogon data)

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

        # Add meta Pokemon for reference - try Smogon first, fallback to hardcoded
        if compare_to_meta:
            meta_pokemon_added = set()  # Track added Pokemon to avoid duplicates

            # Try to fetch real data from Smogon
            if smogon:
                try:
                    usage_data = await smogon.get_usage_stats()
                    if usage_data and "data" in usage_data:
                        # Get top 20 Pokemon by usage
                        pokemon_data = usage_data["data"]
                        sorted_pokemon = sorted(
                            pokemon_data.items(),
                            key=lambda x: x[1].get("usage", 0),
                            reverse=True
                        )[:20]

                        for mon_name, mon_data in sorted_pokemon:
                            if mon_name.lower() in meta_pokemon_added:
                                continue

                            try:
                                # Get base stats from PokeAPI
                                base_stats = await pokeapi.get_base_stats(mon_name)
                                if not base_stats:
                                    continue

                                # Get speed distribution from Smogon
                                speed_dist = await smogon.get_speed_distribution(
                                    mon_name, base_stats.speed
                                )

                                if speed_dist and speed_dist.get("distribution"):
                                    # Use top 2 most common speeds
                                    dist = sorted(
                                        speed_dist["distribution"],
                                        key=lambda x: x.get("usage", 0),
                                        reverse=True
                                    )[:2]

                                    for entry in dist:
                                        all_pokemon.append({
                                            "name": mon_name,
                                            "speed": entry["speed"],
                                            "is_yours": False,
                                            "base_speed": base_stats.speed,
                                            "tailwind_speed": entry["speed"] * 2 if include_tailwind else None
                                        })

                                    meta_pokemon_added.add(mon_name.lower())
                            except Exception:
                                # Skip Pokemon that fail to load
                                continue
                except Exception:
                    # Smogon fetch failed, use fallback
                    pass

            # Fallback to hardcoded data if Smogon didn't provide enough Pokemon
            if len(meta_pokemon_added) < 10:
                for mon, data in META_SPEED_TIERS.items():
                    if mon.lower() in meta_pokemon_added:
                        continue
                    for speed in data["common_speeds"][:2]:  # Top 2 common speeds
                        all_pokemon.append({
                            "name": mon,
                            "speed": speed,
                            "is_yours": False,
                            "base_speed": data["base"],
                            "tailwind_speed": speed * 2 if include_tailwind else None
                        })
                    meta_pokemon_added.add(mon.lower())

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
                    # Build speed tiers list for UI (exclude user's Pokemon - it's added separately)
                    speed_tier_list = [
                        {"name": p["name"], "speed": p["speed"], "common": not p["is_yours"]}
                        for p in all_pokemon
                        if not p["is_yours"]
                    ]
                    ui_resource = create_speed_tier_resource(
                        pokemon_name=primary["name"],
                        pokemon_speed=primary["speed"],
                        speed_tiers=speed_tier_list,
                        modifiers={
                            "tailwind": include_tailwind,
                            "trick_room": include_trick_room,
                        },
                        user_base_speed=primary["speed"],  # Use current speed as base for JS
                    )
                    result = add_ui_metadata(
                        result, ui_resource,
                        display_type="inline",
                        name="Speed Tiers"
                    )
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
        speed_evs: int = 0,
        speed_stat: Optional[int] = None
    ) -> dict:
        """
        Analyze what percentage of a target Pokemon's common spreads you outspeed.
        Uses real Smogon usage data when available, falls back to hardcoded meta tiers.

        Args:
            pokemon_name: Your Pokemon's name
            target_pokemon: The target Pokemon to compare against
            nature: Your Pokemon's nature (ignored if speed_stat provided)
            speed_evs: Your Pokemon's Speed EVs (ignored if speed_stat provided)
            speed_stat: Your Pokemon's final Speed stat (overrides nature/EVs calculation)

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

            # Calculate your speed - use speed_stat directly if provided
            if speed_stat is not None:
                your_speed = speed_stat
            else:
                your_speed = calculate_speed(base_stats.speed, 31, speed_evs, 50, parsed_nature)

            # Normalize target name
            target_lower = target_pokemon.lower().replace(" ", "-")
            if target_lower.endswith("-mask"):
                target_lower = target_lower.replace("-mask", "")

            target_spreads = None
            target_base_speed = None
            target_stats = None
            data_source = "fallback"

            # Try Smogon data first
            if smogon:
                try:
                    target_base = await pokeapi.get_base_stats(target_pokemon)
                    speed_dist = await smogon.get_speed_distribution(
                        target_pokemon,
                        target_base.speed
                    )
                    if speed_dist and speed_dist.get("distribution"):
                        target_spreads = speed_dist["distribution"]
                        target_base_speed = speed_dist["base_speed"]
                        target_stats = speed_dist.get("stats", {})
                        data_source = "smogon"
                except Exception:
                    pass  # Fall through to fallbacks

            # Fallback 1: META_SPEED_TIERS (hardcoded)
            if not target_spreads:
                target_data = META_SPEED_TIERS.get(target_lower)
                if target_data:
                    common_speeds = target_data["common_speeds"]
                    usage_per = 100 // len(common_speeds) if common_speeds else 100
                    target_spreads = [
                        {"speed": s, "usage": usage_per}
                        for s in common_speeds
                    ]
                    target_base_speed = target_data["base"]
                    data_source = "meta_tiers"

            # Fallback 2: Calculate standard spreads from base stats
            if not target_spreads:
                try:
                    target_base = await pokeapi.get_base_stats(target_pokemon)
                    target_spreads = [
                        {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.JOLLY), "usage": 35},
                        {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.SERIOUS), "usage": 25},
                        {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.SERIOUS), "usage": 20},
                        {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.BRAVE), "usage": 20},
                    ]
                    target_base_speed = target_base.speed
                    data_source = "calculated"
                except Exception:
                    return {"error": f"Could not find data for {target_pokemon}"}

            # Calculate outspeed percentage with interpolation for speeds between known tiers
            total_usage = sum(s["usage"] for s in target_spreads)
            sorted_by_speed = sorted(target_spreads, key=lambda s: s["speed"])
            speeds = [s["speed"] for s in sorted_by_speed]

            # Base calculation: speeds we definitively outspeed or tie
            outsped_usage = sum(
                s["usage"] for s in target_spreads
                if your_speed > s["speed"]
            )
            tied_usage = sum(
                s["usage"] for s in target_spreads
                if your_speed == s["speed"]
            )

            # Interpolation: if user speed is between two known tiers, estimate partial credit
            # This accounts for unknown spreads that likely exist between reported tiers
            interpolation_bonus = 0.0
            if your_speed not in speeds and len(speeds) >= 2:
                # Find the two tiers we're between
                lower_tier = None
                upper_tier = None
                for i, spd in enumerate(speeds):
                    if spd > your_speed:
                        upper_tier = sorted_by_speed[i]
                        if i > 0:
                            lower_tier = sorted_by_speed[i - 1]
                        break

                # If we're between two tiers, interpolate
                if lower_tier and upper_tier:
                    lower_speed = lower_tier["speed"]
                    upper_speed = upper_tier["speed"]
                    upper_usage = upper_tier["usage"]
                    # How far through the gap are we? (0 = at lower tier, 1 = at upper tier)
                    gap_progress = (your_speed - lower_speed) / (upper_speed - lower_speed)
                    # Estimate that gap_progress % of the upper tier's "hidden neighbors" are below us
                    # Use a fraction of the upper tier's usage as the "gap pool"
                    interpolation_bonus = upper_usage * gap_progress * 0.5  # Conservative estimate

            outsped_usage += interpolation_bonus
            outspeed_percent = (outsped_usage / total_usage * 100) if total_usage > 0 else 0
            tie_percent = (tied_usage / total_usage * 100) if total_usage > 0 else 0
            outsped_by_percent = round(100 - outspeed_percent - tie_percent, 1)

            # Flag if interpolation was used
            used_interpolation = interpolation_bonus > 0

            # Determine result description
            if outspeed_percent >= 100:
                result_text = f"{pokemon_name} outspeeds all common {target_pokemon} spreads"
            elif outspeed_percent > 50:
                result_text = f"{pokemon_name} outspeeds most common {target_pokemon} spreads"
            elif outspeed_percent > 0:
                result_text = f"{pokemon_name} outspeeds some common {target_pokemon} spreads"
            else:
                result_text = f"{pokemon_name} is outsped by all common {target_pokemon} spreads"

            # Build compact summary with full breakdown
            if speed_stat is not None:
                speed_source = f"At {your_speed} Speed:"
            else:
                speed_source = f"At {your_speed} Speed ({nature}, {speed_evs} EVs):"

            # Add disclaimer about estimation
            disclaimer = "(Estimated from Smogon usage data)"

            summary_lines = [
                speed_source,
                f"You outspeed: {round(outspeed_percent, 1)}% | Tie: {round(tie_percent, 1)}% | They outspeed you: {outsped_by_percent}%",
                disclaimer,
                "",
                "Speed Tier Breakdown:",
            ]
            # Sort spreads by speed for cleaner display
            sorted_spreads = sorted(target_spreads, key=lambda s: s["speed"])
            # Normalize percentages so they add up to 100%
            raw_total = sum(s["usage"] for s in sorted_spreads)
            for spread in sorted_spreads:
                speed = spread["speed"]
                raw_usage = spread["usage"]
                # Normalize to 100% of known spreads
                normalized_usage = (raw_usage / raw_total * 100) if raw_total > 0 else 0
                if your_speed > speed:
                    result_label = "faster"
                elif your_speed == speed:
                    result_label = "tie"
                else:
                    result_label = "slower"
                summary_lines.append(f"{speed} Spe ({normalized_usage:.1f}%) - {result_label}")

            # Build analysis string with disclaimer
            analysis_str = f"{pokemon_name} at {your_speed} Speed: You outspeed {round(outspeed_percent, 1)}% | Tie {round(tie_percent, 1)}% | They outspeed you {outsped_by_percent}% {disclaimer}"

            result_dict = {
                "pokemon": pokemon_name,
                "your_speed": your_speed,
                "nature": nature if speed_stat is None else None,
                "speed_evs": speed_evs if speed_stat is None else None,
                "speed_stat": speed_stat,
                "target_pokemon": target_pokemon,
                "target_base_speed": target_base_speed,
                "target_spreads": target_spreads,
                "target_stats": target_stats,
                "outspeed_percent": round(outspeed_percent, 1),
                "tie_percent": round(tie_percent, 1),
                "outsped_by_percent": outsped_by_percent,
                "used_interpolation": used_interpolation,
                "result": result_text,
                "data_source": data_source,
                "summary_table": "\n".join(summary_lines),
                "analysis": analysis_str
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
                    result_dict = add_ui_metadata(
                        result_dict, ui_resource,
                        display_type="inline",
                        name="Outspeed Chart"
                    )
                except Exception:
                    pass  # UI is optional

            return result_dict

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def visualize_speed_histogram(
        pokemon_name: str,
        targets: list[str] | None = None,
        nature: str = "serious",
        speed_evs: int = 0,
    ) -> str:
        """
        Visualize speed distribution histogram comparing your Pokemon against meta targets.
        Uses real Smogon usage data for accurate speed tier analysis.

        Args:
            pokemon_name: Your Pokemon's name
            targets: List of target Pokemon to load (e.g., ["Flutter Mane", "Rillaboom"]).
                    If None, auto-loads top 30 meta Pokemon from Smogon usage.
            nature: Your Pokemon's nature (default "serious")
            speed_evs: Your Pokemon's Speed EVs (default 0)

        Returns:
            Interactive HTML speed histogram with:
            - Searchable dropdown to compare against any loaded Pokemon
            - Your speed marker on the distribution
            - Real-time speed controls (nature, EVs, modifiers like Tailwind/Scarf)
            - Outspeed percentage calculation
        """
        try:
            # Get your Pokemon's base stats
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            base_speed = base_stats.speed

            # Parse nature
            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return f"Error: Invalid nature '{nature}'"

            # Calculate your speed
            your_speed = calculate_speed(base_speed, 31, speed_evs, 50, parsed_nature)

            # Determine targets to load
            if targets:
                target_list = targets
            else:
                # Auto-load top 30 Pokemon from Smogon usage
                if smogon:
                    try:
                        usage_data = await smogon.get_usage_stats()
                        if usage_data and "data" in usage_data:
                            # Get top 30 Pokemon by usage
                            pokemon_data = usage_data["data"]
                            sorted_pokemon = sorted(
                                pokemon_data.items(),
                                key=lambda x: x[1].get("usage", 0),
                                reverse=True
                            )[:30]
                            target_list = [name for name, _ in sorted_pokemon]
                        else:
                            target_list = list(META_SPEED_TIERS.keys())[:30]
                    except Exception:
                        target_list = list(META_SPEED_TIERS.keys())[:30]
                else:
                    target_list = list(META_SPEED_TIERS.keys())[:30]

            # Fetch speed distributions for all targets
            all_targets_data = {}
            all_pokemon_names = []

            for target in target_list:
                try:
                    # Get target's base speed
                    target_base = await pokeapi.get_base_stats(target)

                    # Get speed distribution from Smogon
                    if smogon:
                        speed_dist = await smogon.get_speed_distribution(
                            target,
                            target_base.speed
                        )
                        if speed_dist and speed_dist.get("distribution"):
                            # Normalize name for key
                            key = target.lower().replace(" ", "-")
                            all_targets_data[key] = {
                                "base_speed": target_base.speed,
                                "distribution": speed_dist["distribution"],
                                "stats": speed_dist.get("stats", {}),
                            }
                            all_pokemon_names.append(target)
                            continue

                    # Fallback: use META_SPEED_TIERS or calculate standard spreads
                    target_lower = target.lower().replace(" ", "-")
                    if target_lower in META_SPEED_TIERS:
                        meta_data = META_SPEED_TIERS[target_lower]
                        common_speeds = meta_data["common_speeds"]
                        usage_per = 100 // len(common_speeds)
                        all_targets_data[target_lower] = {
                            "base_speed": meta_data["base"],
                            "distribution": [
                                {"speed": s, "usage": usage_per}
                                for s in common_speeds
                            ],
                            "stats": {
                                "min": min(common_speeds),
                                "max": max(common_speeds),
                                "median": common_speeds[len(common_speeds) // 2],
                                "mean": sum(common_speeds) / len(common_speeds),
                            },
                        }
                        all_pokemon_names.append(target)
                    else:
                        # Calculate standard spreads
                        dist = [
                            {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.JOLLY), "usage": 35},
                            {"speed": calculate_speed(target_base.speed, 31, 252, 50, Nature.SERIOUS), "usage": 25},
                            {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.SERIOUS), "usage": 20},
                            {"speed": calculate_speed(target_base.speed, 31, 0, 50, Nature.BRAVE), "usage": 20},
                        ]
                        speeds = [d["speed"] for d in dist]
                        all_targets_data[target_lower] = {
                            "base_speed": target_base.speed,
                            "distribution": dist,
                            "stats": {
                                "min": min(speeds),
                                "max": max(speeds),
                                "median": speeds[1],
                                "mean": sum(speeds) / len(speeds),
                            },
                        }
                        all_pokemon_names.append(target)

                except Exception:
                    continue  # Skip Pokemon that fail

            if not all_targets_data:
                return "Error: Could not load speed distributions for any targets"

            # Get all Pokemon names from Smogon for the dropdown
            # This allows searching any Pokemon even if not pre-loaded
            if smogon:
                try:
                    usage_data = await smogon.get_usage_stats()
                    if usage_data and "data" in usage_data:
                        all_pokemon_names = list(usage_data["data"].keys())
                except Exception:
                    pass  # Use the list we already have

            # Determine initial target (first in list)
            initial_target = list(all_targets_data.keys())[0]

            # Generate the interactive histogram UI
            html = create_interactive_speed_histogram_ui(
                pokemon_name=pokemon_name,
                pokemon_speed=your_speed,
                initial_target=initial_target,
                all_targets_data=all_targets_data,
                base_speed=base_speed,
                nature=nature.title(),
                speed_evs=speed_evs,
                all_pokemon_names=all_pokemon_names,
            )

            return html

        except Exception as e:
            return f"Error: {str(e)}"
