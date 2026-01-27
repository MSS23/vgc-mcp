"""MCP tools for speed analysis, comparisons, tiers, and speed control.

This module consolidates:
- Basic speed calculations and comparisons
- Speed tier visualization and meta analysis
- Speed control analysis (Trick Room, Tailwind, drops)
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.calc.stats import calculate_speed, find_speed_evs
from vgc_mcp_core.calc.speed import (
    SPEED_BENCHMARKS,
    META_SPEED_TIERS,
    calculate_speed_tier,
    get_competitive_speed_benchmarks,
)
from vgc_mcp_core.calc.speed_control import (
    analyze_trick_room,
    analyze_tailwind,
    analyze_speed_drop,
    analyze_paralysis,
    get_speed_control_summary,
    get_team_speeds,
    apply_speed_modifier,
    apply_stage_modifier,
)
from vgc_mcp_core.models.pokemon import Nature
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50


def register_speed_analysis_tools(mcp: FastMCP, pokeapi: PokeAPIClient, team_manager: TeamManager, smogon_client: SmogonStatsClient):
    """Register all speed analysis tools with the MCP server."""

    # ========== Basic Speed Calculations ==========

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
                "difference": diff,
                "result": result,
                "winner": winner,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
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
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Pokemon          | {pokemon_name}                             |",
                    f"| Target Speed     | {target_speed}                             |",
                    f"| Max with 252 EVs | {max_speed}                                |",
                    f"| Result           | Cannot reach target                        |",
                ]
                return {
                    "pokemon": pokemon_name,
                    "target_speed": target_speed,
                    "achievable": False,
                    "max_speed_with_252_evs": max_speed,
                    "suggestion": "Try a +Speed nature (Timid/Jolly) or lower your target",
                    "summary_table": "\n".join(table_lines)
                }

            actual_speed = calculate_speed(base_stats.speed, 31, evs_needed, 50, parsed_nature)

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Target Speed     | {target_speed}                             |",
                f"| Required EVs     | {evs_needed} Speed                         |",
                f"| Resulting Speed  | {actual_speed}                             |",
                f"| Nature           | {nature}                                   |",
                f"| EVs Remaining    | {508 - evs_needed}                         |",
            ]

            return {
                "pokemon": pokemon_name,
                "target_speed": target_speed,
                "achievable": True,
                "evs_needed": evs_needed,
                "actual_speed": actual_speed,
                "evs_remaining": 508 - evs_needed,
                "summary_table": "\n".join(table_lines),
                "analysis": f"Need {evs_needed} Speed EVs to reach {actual_speed}, outspeeding target speed {target_speed}"
            }

        except Exception as e:
            return {"error": str(e)}

    # ========== Speed Tier Analysis ==========

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
        speed_evs: int = 0,
        use_competitive_data: bool = True
    ) -> dict:
        """
        Analyze what a specific speed spread outspeeds and underspeeds.

        Args:
            pokemon_name: Pokemon name
            nature: Nature
            speed_evs: Speed EVs
            use_competitive_data: Use Smogon competitive spreads (default True).
                                 If False, uses theoretical max speeds.

        Returns:
            Analysis of what this spread outspeeds/underspeeds based on real
            competitive usage data or theoretical benchmarks
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Fetch competitive benchmarks from Smogon if requested
            competitive_benchmarks = None
            if use_competitive_data:
                try:
                    competitive_benchmarks = await get_competitive_speed_benchmarks(
                        smogon_client,
                        top_n_pokemon=30,
                        top_n_speeds=3
                    )
                except Exception:
                    # Fallback to theoretical benchmarks if Smogon fetch fails
                    competitive_benchmarks = None

            tier_info = calculate_speed_tier(
                base_stats.speed,
                parsed_nature,
                speed_evs,
                31,
                50,
                competitive_benchmarks=competitive_benchmarks
            )

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "speed_evs": speed_evs,
                "final_speed": tier_info["speed"],
                "outspeeds": tier_info["outspeeds"],
                "ties_with": tier_info["ties_with"],
                "underspeeds": tier_info["underspeeds"],
                "data_source": "Smogon competitive usage" if competitive_benchmarks else "Theoretical max speeds"
            }

        except Exception as e:
            return {"error": str(e)}

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
            from vgc_mcp_core.calc.speed import get_meta_speed_tier
            for mon in META_SPEED_TIERS.keys():
                data = get_meta_speed_tier(mon)
                if data:
                    common_speeds = data.get("common_speeds", [])
                    for speed in common_speeds[:2]:  # Top 2 common speeds
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
                lines.append(f"Your fastest outspeeds: {', '.join(list(set(outspeeds))[:5])}")
            if underspeeds:
                lines.append(f"Faster than your slowest: {', '.join(list(set(underspeeds))[:5])}")

        result = {
            "visualization": "\n".join(lines),
            "your_pokemon": your_pokemon,
            "mode": mode
        }

        return result

    @mcp.tool()
    async def get_meta_speed_tiers(
        format_type: str = "general",
        tier: Optional[str] = None,
        use_competitive_data: bool = True
    ) -> dict:
        """
        Get common speed tiers in the current VGC metagame.

        Args:
            format_type: "general", "trick_room", or "tailwind"
            tier: Optional filter - "fast", "medium", "slow"
            use_competitive_data: Use Smogon competitive spreads (default True).
                                 If False, uses theoretical speeds from META_SPEED_TIERS.

        Returns:
            Speed tier information for meta Pokemon based on real competitive usage
        """
        result = []

        if use_competitive_data:
            # Fetch competitive speed benchmarks from Smogon
            try:
                competitive_benchmarks = await get_competitive_speed_benchmarks(
                    smogon_client,
                    top_n_pokemon=30,
                    top_n_speeds=3
                )

                for mon_name, speeds in competitive_benchmarks.items():
                    if not speeds:
                        continue

                    # Get base speed for categorization
                    base = SPEED_BENCHMARKS.get(mon_name, {}).get("base", 0)
                    if base == 0:
                        # Try to fetch from PokeAPI if not in benchmarks
                        try:
                            base_stats = await pokeapi.get_base_stats(mon_name)
                            base = base_stats.speed
                        except Exception:
                            continue

                    entry = {
                        "pokemon": mon_name,
                        "base_speed": base,
                        "competitive_speeds": speeds,  # List of dicts with speed, nature, evs, usage
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

            except Exception:
                # Fallback to META_SPEED_TIERS if Smogon fetch fails
                use_competitive_data = False

        if not use_competitive_data:
            # Fallback to theoretical speeds from META_SPEED_TIERS
            from vgc_mcp_core.calc.speed import get_meta_speed_tier

            for mon in META_SPEED_TIERS.keys():
                data = get_meta_speed_tier(mon)
                if not data:
                    continue
                base = data["base"]
                speeds = data.get("common_speeds", [])

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
        from vgc_mcp_core.calc.speed import get_meta_speed_tier
        for mon in META_SPEED_TIERS.keys():
            data = get_meta_speed_tier(mon)
            if not data:
                continue
            base = data["base"]
            max_speed = calculate_speed(base, 31, 252, 50, Nature.JOLLY)
            neutral_max = calculate_speed(base, 31, 252, 50, Nature.HARDY)

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

    # ========== Speed Control Analysis (Trick Room, Tailwind, etc.) ==========

    @mcp.tool()
    async def analyze_team_trick_room() -> dict:
        """
        Analyze how the current team performs under Trick Room.

        Shows:
        - Move order in Trick Room (slowest first)
        - Which Pokemon benefit from TR
        - What each Pokemon "outspeeds" in TR
        - Whether team has TR setters

        Returns:
            Trick Room analysis with move order and recommendations
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            analysis = analyze_trick_room(team_manager.team)

            return {
                "condition": analysis.condition,
                "move_order": analysis.move_order,
                "speeds": [
                    {
                        "name": t.name,
                        "speed": t.final_speed,
                        "notes": t.notes
                    }
                    for t in analysis.team_speeds
                ],
                "outspeeds_in_tr": {
                    name: targets[:5]  # Limit for readability
                    for name, targets in analysis.outspeeds.items()
                },
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_team_tailwind() -> dict:
        """
        Analyze how the current team performs with Tailwind active.

        Tailwind doubles Speed for 4 turns.

        Shows:
        - Speeds after 2x boost
        - What each Pokemon outspeeds with Tailwind
        - Whether team has Tailwind setters

        Returns:
            Tailwind analysis with boosted speeds
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            analysis = analyze_tailwind(team_manager.team)

            return {
                "condition": analysis.condition,
                "move_order": analysis.move_order,
                "speeds": [
                    {
                        "name": t.name,
                        "base_speed": t.final_speed,
                        "with_tailwind": t.modified_speed
                    }
                    for t in analysis.team_speeds
                ],
                "outspeeds_with_tailwind": {
                    name: targets[:5]
                    for name, targets in analysis.outspeeds.items()
                },
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_speed_drops(stages: int = -1) -> dict:
        """
        Analyze what your team can outspeed after using Icy Wind/Electroweb.

        Args:
            stages: Number of speed stages dropped on opponent (default -1)
                   -1 = Icy Wind, Electroweb, Rock Tomb
                   -2 = Scary Face, Cotton Spore

        Returns:
            Analysis of what your team outspeeds after speed control
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            # Clamp stages
            stages = max(-6, min(0, stages))

            analysis = analyze_speed_drop(team_manager.team, stages)

            return {
                "condition": analysis.condition,
                "your_speeds": [
                    {"name": t.name, "speed": t.final_speed}
                    for t in analysis.team_speeds
                ],
                "outspeeds_after_drop": analysis.outspeeds,
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_paralysis_matchup() -> dict:
        """
        Analyze what your team outspeeds when opponents are paralyzed.

        Paralysis halves Speed.

        Returns:
            Analysis of matchups vs paralyzed opponents
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            analysis = analyze_paralysis(team_manager.team)

            return {
                "condition": analysis.condition,
                "your_speeds": [
                    {"name": t.name, "speed": t.final_speed}
                    for t in analysis.team_speeds
                ],
                "outspeeds_paralyzed": analysis.outspeeds,
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_full_speed_analysis() -> dict:
        """
        Get comprehensive speed control analysis for the team.

        Includes:
        - Base speed tiers
        - Trick Room analysis
        - Tailwind analysis
        - Icy Wind/Electroweb impact

        Returns:
            Complete speed control breakdown
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            return get_speed_control_summary(team_manager.team)

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def calculate_speed_after_modifier(
        base_speed: int,
        modifier_type: str,
        stages: int = 0
    ) -> dict:
        """
        Calculate what a speed stat becomes after various modifiers.

        Args:
            base_speed: The Pokemon's current Speed stat
            modifier_type: "tailwind", "paralysis", "stage", or "none"
            stages: Stat stages (-6 to +6) if modifier_type is "stage"

        Returns:
            Modified speed and what it outspeeds
        """
        try:
            if modifier_type == "tailwind":
                modified = apply_speed_modifier(base_speed, 2.0)
                condition = "with Tailwind (2x)"
            elif modifier_type == "paralysis":
                modified = apply_speed_modifier(base_speed, 0.5)
                condition = "while paralyzed (0.5x)"
            elif modifier_type == "stage":
                stages = max(-6, min(6, stages))
                modified = apply_stage_modifier(base_speed, stages)
                condition = f"at {stages:+d} stages"
            else:
                modified = base_speed
                condition = "unmodified"

            # Find what this outspeeds
            outspeeds = []
            underspeeds = []
            from vgc_mcp_core.calc.speed import get_speed_tier_info

            for mon in SPEED_BENCHMARKS.keys():
                data = get_speed_tier_info(mon)
                if data and data.get("max_positive"):
                    max_positive = data["max_positive"]
                    if modified > max_positive:
                        outspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")
                    elif modified < max_positive:
                        underspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")

            return {
                "original_speed": base_speed,
                "modified_speed": modified,
                "condition": condition,
                "outspeeds": outspeeds[:10],
                "underspeeds": underspeeds[:5]
            }

        except Exception as e:
            return {"error": str(e)}
