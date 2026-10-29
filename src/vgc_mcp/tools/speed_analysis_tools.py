"""MCP tools for speed analysis, comparisons, tiers, and speed control.

This module consolidates:
- Basic speed calculations and comparisons
- Speed tier visualization and meta analysis
- Speed control analysis (Trick Room, Tailwind, drops)
"""

from typing import Annotated, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.speed import (
    META_SPEED_TIERS,
    SPEED_BENCHMARKS,
    calculate_speed_tier,
    get_competitive_speed_benchmarks,
)
from vgc_mcp_core.calc.speed_control import (
    analyze_paralysis,
    analyze_speed_drop,
    analyze_tailwind,
    analyze_trick_room,
    apply_speed_modifier,
    apply_stage_modifier,
    get_speed_control_summary,
)
from vgc_mcp_core.calc.stats import calculate_speed, find_speed_evs
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50
from vgc_mcp_core.models.pokemon import Nature
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.tools import speed_handlers
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_speed_analysis_tools(mcp: FastMCP, pokeapi: PokeAPIClient, team_manager: TeamManager, smogon_client: SmogonStatsClient):
    """Register all speed analysis tools with the MCP server."""

    # ========== Basic Speed Calculations ==========

    @mcp.tool(
        title="Compare Pokemon Speed",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def compare_speed(
        pokemon1_name: Annotated[str, Field(description="First Pokemon's name", min_length=1)],
        pokemon2_name: Annotated[str, Field(description="Second Pokemon's name", min_length=1)],
        pokemon1_nature: Annotated[str, Field(description="First Pokemon's nature")] = "serious",
        pokemon1_speed_evs: Annotated[Union[Annotated[int, Field(ge=0, le=252)], str], Field(description="First Pokemon's Speed EVs (0-252); Stat Points 0-32 in Champions sessions. Also accepts the full 'HP/Atk/Def/SpA/SpD/Spe' slash string (its Spe value is used).")] = 0,
        pokemon2_nature: Annotated[str, Field(description="Second Pokemon's nature")] = "serious",
        pokemon2_speed_evs: Annotated[Union[Annotated[int, Field(ge=0, le=252)], str], Field(description="Second Pokemon's Speed EVs (0-252); Stat Points 0-32 in Champions sessions. Also accepts the full 'HP/Atk/Def/SpA/SpD/Spe' slash string (its Spe value is used).")] = 0
    ) -> dict:
        """Compare speed between two Pokemon to determine who moves first.

        In a Pokemon Champions (Reg MA) session the ``*_speed_evs`` arguments are
        interpreted as Speed Stat Points (0-32, 66-point budget) and Speed uses
        the SP formula (e.g. Flutter Mane Timid 32 Spe SP -> 205). The per-mon
        investment field is labelled ``sps`` instead of ``evs`` in that case.
        """
        try:
            pokemon1_speed_evs = speed_handlers.speed_investment(pokemon1_speed_evs)
            pokemon2_speed_evs = speed_handlers.speed_investment(pokemon2_speed_evs)
        except ValueError as ve:
            return error_response(ErrorCodes.INVALID_PARAMETER, f"speed_evs: {ve}")
        try:
            # Fetch base stats
            base1 = await pokeapi.get_base_stats(pokemon1_name)
            base2 = await pokeapi.get_base_stats(pokemon2_name)

            # Parse natures
            try:
                nature1 = Nature(pokemon1_nature.lower())
                nature2 = Nature(pokemon2_nature.lower())
            except ValueError as e:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {e}')

            # Detect Champions vs mainline. In a Champions session the Speed
            # investment is Stat Points (0-32, 66 budget) and uses the SP path;
            # otherwise it's EVs and the mainline path is byte-for-byte unchanged.
            from vgc_mcp_core.rules.format_detect import detect_champions_format
            is_champions = detect_champions_format(pokemon1_name, pokemon2_name)

            if is_champions:
                from vgc_mcp_core.calc.stats_champions import calculate_speed_sp
                speed1 = calculate_speed_sp(base1.speed, 31, pokemon1_speed_evs, 50, nature1)
                speed2 = calculate_speed_sp(base2.speed, 31, pokemon2_speed_evs, 50, nature2)
                invest_key = "sps"
                stat_units = "Stat Points (SPs)"
            else:
                speed1 = calculate_speed(base1.speed, 31, pokemon1_speed_evs, 50, nature1)
                speed2 = calculate_speed(base2.speed, 31, pokemon2_speed_evs, 50, nature2)
                invest_key = "evs"
                stat_units = None

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

            response = {
                "pokemon1": {
                    "name": pokemon1_name,
                    "base_speed": base1.speed,
                    "nature": pokemon1_nature,
                    invest_key: pokemon1_speed_evs,
                    "final_speed": speed1
                },
                "pokemon2": {
                    "name": pokemon2_name,
                    "base_speed": base2.speed,
                    "nature": pokemon2_nature,
                    invest_key: pokemon2_speed_evs,
                    "final_speed": speed2
                },
                "difference": diff,
                "result": result,
                "winner": winner,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

            if is_champions:
                response["format_system"] = "champions"
                response["stat_units"] = stat_units
                response["note"] = (
                    "Champions Reg MA Stat Points (0-32 per stat, 66 total); "
                    "32 SP saturates to the same stat as 252 EVs"
                )

            return response

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Find Speed EVs to Outspeed",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_speed_evs_to_outspeed(
        pokemon_name: Annotated[str, Field(description="Your Pokemon's name", min_length=1)],
        target_speed: Annotated[int, Field(description="The Speed stat you want to reach or exceed")],
        nature: Annotated[str, Field(description="Your Pokemon's nature")] = "serious"
    ) -> dict:
        """Find minimum Speed EVs needed to reach or exceed a target Speed stat.

        Returns the required EVs (or Stat Points in a Champions Reg MA session)
        and the resulting Speed, or flags the target as unreachable with the
        max achievable Speed.
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

            # Detect Champions vs mainline. In a Champions session we report on
            # the Stat-Point grain (0-32 per stat, 66-point budget) instead of
            # EVs (0-252, 508 budget). Mainline path is byte-for-byte unchanged.
            from vgc_mcp_core.rules.format_detect import detect_champions_format
            is_champions = detect_champions_format(pokemon_name)

            if is_champions:
                from vgc_mcp_core.calc.champions_optimization import (
                    find_speed_sps_to_outspeed,
                )
                from vgc_mcp_core.calc.stats_champions import calculate_speed_sp

                # find_speed_sps_to_outspeed targets target_speed + 1 (strict
                # outspeed). To "reach OR exceed" the target stat we pass
                # target_speed - 1 so the helper's +1 lands on target_speed.
                sps_needed = find_speed_sps_to_outspeed(
                    base_stats.speed, target_speed - 1, parsed_nature, 31, 50
                )

                if sps_needed is None:
                    max_speed = calculate_speed_sp(base_stats.speed, 31, 32, 50, parsed_nature)
                    table_lines = [
                        "| Metric           | Value                                      |",
                        "|------------------|---------------------------------------------|",
                        f"| Pokemon          | {pokemon_name}                             |",
                        f"| Target Speed     | {target_speed}                             |",
                        f"| Max with 32 SPs  | {max_speed}                                |",
                        "| Result           | Cannot reach target                        |",
                    ]
                    return {
                        "pokemon": pokemon_name,
                        "target_speed": target_speed,
                        "achievable": False,
                        "format_system": "champions",
                        "stat_units": "Stat Points (SPs)",
                        "max_speed_with_32_sps": max_speed,
                        "suggestion": "Try a +Speed nature (Timid/Jolly) or lower your target",
                        "summary_table": "\n".join(table_lines),
                    }

                actual_speed = calculate_speed_sp(base_stats.speed, 31, sps_needed, 50, parsed_nature)
                sps_remaining = max(0, 66 - sps_needed)
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Pokemon          | {pokemon_name}                             |",
                    f"| Target Speed     | {target_speed}                             |",
                    f"| Required SPs     | {sps_needed} Speed                         |",
                    f"| Resulting Speed  | {actual_speed}                             |",
                    f"| Nature           | {nature}                                   |",
                    f"| SPs Remaining    | {sps_remaining}                            |",
                ]
                return {
                    "pokemon": pokemon_name,
                    "target_speed": target_speed,
                    "achievable": True,
                    "format_system": "champions",
                    "stat_units": "Stat Points (SPs)",
                    "sps_needed": sps_needed,
                    "actual_speed": actual_speed,
                    "sps_remaining": sps_remaining,
                    "summary_table": "\n".join(table_lines),
                    "analysis": (
                        f"Need {sps_needed} Speed SP ({sps_needed} SP, "
                        f"{sps_remaining} remaining of 66) to reach {actual_speed}, "
                        f"outspeeding target speed {target_speed}"
                    ),
                }

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
                    "| Result           | Cannot reach target                        |",
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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    # ========== Speed Tier Analysis ==========

    @mcp.tool(
        title="Get Speed Tiers",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_speed_tiers(
        min_base_speed: Annotated[int, Field(description="Minimum base speed to include")] = 50,
        max_base_speed: Annotated[int, Field(description="Maximum base speed to include")] = 200,
        investment: Annotated[str, Field(
            description="'max' (252 EVs, +nature), 'neutral' (252 EVs, neutral nature), 'min' (0 EVs, -nature, 0 IV), or 'meta' (the current metagame's real Smogon speed spreads per Pokemon, falling back to theoretical meta tiers)",
        )] = "max",
        format_type: Annotated[str, Field(
            description="'general', 'trick_room' (slowest first), or 'tailwind' (adds doubled speeds)",
        )] = "general",
    ) -> dict:
        """Get speed tier benchmarks for common VGC Pokemon.

        Returns a list of benchmark Pokemon with their final Speed stats at the
        specified investment level, sorted fastest first. investment='meta'
        returns the live metagame's competitive speed spreads instead.
        """
        return await speed_handlers.speed_tiers(
            pokeapi,
            smogon_client,
            min_base_speed=min_base_speed,
            max_base_speed=max_base_speed,
            investment=investment,
            format_type=format_type,
        )

    @mcp.tool(
        title="Analyze Speed Spread",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def analyze_speed_spread(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        nature: Annotated[str, Field(description="Nature")] = "serious",
        speed_evs: Annotated[int, Field(ge=0, le=252, description="Speed EVs (0-252)")] = 0,
        use_competitive_data: Annotated[bool, Field(
            description="Use Smogon competitive spreads for benchmarks; if False (or Smogon is unavailable), uses theoretical max speeds",
        )] = True
    ) -> dict:
        """Analyze what a specific speed spread outspeeds and underspeeds.

        Benchmarks come from real Smogon competitive usage data when available,
        otherwise from theoretical max speeds.
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Visualize Speed Tiers",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def visualize_speed_tiers(
        pokemon_speeds: Annotated[list[dict], Field(
            description=(
                "List of dicts with 'name' and either 'speed' (final Speed stat) or "
                "'nature' + 'evs' (EV dict, 'HP/Atk/Def/SpA/SpD/Spe' slash string, or Speed EVs int), "
                "e.g. [{\"name\": \"Entei\", \"speed\": 157}, {\"name\": \"Flutter Mane\", \"nature\": \"timid\", \"evs\": \"0/0/0/252/4/252\"}]"
            ),
        )],
        include_tailwind: Annotated[bool, Field(description="Also show doubled (Tailwind) speeds")] = False,
        include_trick_room: Annotated[bool, Field(description="Reverse the order (slowest first) for Trick Room")] = False,
        compare_to_meta: Annotated[bool, Field(description="Include common meta Pokemon for reference")] = True
    ) -> dict:
        """Visualize speed tiers as a text-based chart.

        Your Pokemon are marked in the chart; optionally interleaves common
        meta Pokemon and shows Tailwind or Trick Room ordering.
        """
        return await speed_handlers.visualize_speed_tiers(
            pokeapi,
            pokemon_speeds=pokemon_speeds,
            include_tailwind=include_tailwind,
            include_trick_room=include_trick_room,
            compare_to_meta=compare_to_meta,
        )

    @mcp.tool(
        title="Get Meta Speed Tiers",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_meta_speed_tiers(
        format_type: Annotated[str, Field(
            description="'general', 'trick_room' (slowest first), or 'tailwind' (adds doubled max speeds)",
        )] = "general",
        tier: Annotated[Optional[str], Field(
            description="Optional filter: 'fast' (base 120+), 'medium' (base 80+), or 'slow'",
        )] = None,
        use_competitive_data: Annotated[bool, Field(
            description="Use Smogon competitive spreads; if False (or Smogon is unavailable), uses theoretical meta speed tiers",
        )] = True
    ) -> dict:
        """Deprecated alias of `get_speed_tiers`; will be removed in the next release.
        Call `get_speed_tiers(investment="meta", format_type=..., min_base_speed=..., max_base_speed=...)` instead.

        Returns speed tier information for meta Pokemon based on real
        competitive usage data, with theoretical max/min speeds for reference.
        """
        return await speed_handlers.meta_speed_tiers(
            pokeapi,
            smogon_client,
            format_type=format_type,
            tier=tier,
            use_competitive_data=use_competitive_data,
        )

    @mcp.tool(
        title="Find Speed Benchmark",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_speed_benchmark(
        target_speed: Annotated[int, Field(description="The speed stat to analyze")],
        nature: Annotated[str, Field(
            description="Nature to assume for calculations (invalid values fall back to jolly)",
        )] = "jolly",
        pokemon_name: Annotated[Optional[str], Field(
            description="Optional: also compute the EVs this Pokemon needs to hit the target",
        )] = None
    ) -> dict:
        """Find what Pokemon/spreads hit a specific speed stat.

        Returns meta Pokemon at, above, and below the target speed tier, and
        optionally the EV investment your Pokemon needs to reach it.
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
                    # `is not None` — 0 EVs is a valid answer (target already met)
                    "resulting_speed": calculate_speed(base_speed, 31, evs_needed, 50, nature_enum) if evs_needed is not None else None,
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

    @mcp.tool(
        title="Analyze Team Trick Room",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_team_trick_room() -> dict:
        """Analyze how the current team performs under Trick Room.

        Shows the move order in Trick Room (slowest first), which Pokemon
        benefit, what each Pokemon "outspeeds" in TR, and whether the team has
        TR setters. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team. Add Pokemon first.')

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Analyze Team Tailwind",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_team_tailwind() -> dict:
        """Analyze how the current team performs with Tailwind active.

        Tailwind doubles Speed for 4 turns. Shows speeds after the 2x boost,
        what each Pokemon outspeeds with Tailwind, and whether the team has
        Tailwind setters. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team. Add Pokemon first.')

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Analyze Speed Drops",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_speed_drops(
        stages: Annotated[int, Field(
            description=(
                "Speed stages dropped on the opponent: -1 = Icy Wind/Electroweb/Rock Tomb, "
                "-2 = Scary Face/Cotton Spore (values are clamped to -6..0)"
            ),
        )] = -1
    ) -> dict:
        """Analyze what your team can outspeed after using Icy Wind/Electroweb.

        Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team. Add Pokemon first.')

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Analyze Paralysis Matchup",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_paralysis_matchup() -> dict:
        """Analyze what your team outspeeds when opponents are paralyzed.

        Paralysis halves Speed. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team. Add Pokemon first.')

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Get Full Speed Analysis",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_full_speed_analysis() -> dict:
        """Get comprehensive speed control analysis for the current team.

        Covers base speed tiers, Trick Room, Tailwind, and Icy Wind/Electroweb
        impact in one breakdown. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team. Add Pokemon first.')

            return get_speed_control_summary(team_manager.team)

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Calculate Speed After Modifier",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def calculate_speed_after_modifier(
        base_speed: Annotated[int, Field(description="The Pokemon's current Speed stat")],
        modifier_type: Annotated[str, Field(
            description="'tailwind' (2x), 'paralysis' (0.5x), 'stage' (uses stages), or 'none'",
            min_length=1,
        )],
        stages: Annotated[int, Field(
            description="Stat stages when modifier_type is 'stage' (values are clamped to -6..+6)",
        )] = 0
    ) -> dict:
        """Calculate what a speed stat becomes after various modifiers.

        Returns the modified speed plus which max-Speed meta benchmarks it
        outspeeds and underspeeds.
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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
