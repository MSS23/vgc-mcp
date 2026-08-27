"""MCP tools for speed probability analysis.

This module provides tools to calculate the probability of outspeeding
opponents based on current Smogon usage data. It accounts for the
distribution of spreads used by players in the meta.
"""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.calc.speed_probability import (
    calculate_meta_outspeed_rate,
    calculate_outspeed_from_distribution,
    calculate_outspeed_probability,
    calculate_speed_creep_evs,
)
from vgc_mcp_core.calc.stats import calculate_speed
from vgc_mcp_core.models.pokemon import Nature
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_speed_probability_tools(mcp: FastMCP, smogon, pokeapi, team_manager):
    """Register speed probability analysis tools with the MCP server."""

    @mcp.tool(
        title="Calculate Outspeed Probability",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def outspeed_probability(
        your_pokemon: Annotated[str, Field(description="Your Pokemon's name (e.g. 'Entei')", min_length=1)],
        your_speed_evs: Annotated[int, Field(ge=0, le=252, description="Your Speed EVs (0-252)")],
        your_nature: Annotated[str, Field(description="Your nature (e.g. 'Adamant', 'Jolly')", min_length=1)],
        target_pokemon: Annotated[str, Field(description="Opponent's Pokemon (e.g. 'Landorus-Therian')", min_length=1)]
    ) -> dict:
        """Calculate the probability of outspeeding a specific opponent.

        Uses live Smogon usage data to determine what percentage of the
        target's common spreads you will outspeed, tie, or underspeed.
        Example: "What's the probability my Entei outspeeds Landorus?"
        """
        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(your_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {your_pokemon}')

        your_base_speed = your_base_stats.speed

        # Parse nature to get speed modifier
        try:
            nature_enum = Nature(your_nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {your_nature}')

        # Calculate your speed stat
        your_speed = calculate_speed(your_base_speed, ev=your_speed_evs, nature=nature_enum)

        # Get target Pokemon's base stats
        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {target_pokemon}')

        target_base_speed = target_base_stats.speed

        # Try to use get_speed_distribution() first (more efficient)
        speed_dist = await smogon.get_speed_distribution(target_pokemon, target_base_speed)

        if speed_dist and speed_dist.get("distribution"):
            # Use the new optimized path with pre-calculated speeds
            distribution = speed_dist["distribution"]

            result = calculate_outspeed_from_distribution(
                your_speed,
                distribution,
                target_pokemon,
                target_base_speed
            )

            meta_info = {"data_source": "speed_distribution"}
        else:
            # Fallback to raw spreads
            target_usage = await smogon.get_pokemon_usage(target_pokemon)
            if not target_usage:
                return error_response(ErrorCodes.INTERNAL_ERROR, f'No usage data found for {target_pokemon}', note='Target may not be common enough in the current meta')

            target_spreads = target_usage.get("spreads", [])
            meta_info = target_usage.get("_meta", {})

            result = calculate_outspeed_probability(
                your_speed,
                target_base_speed,
                target_spreads,
                target_pokemon
            )

        return {
            "your_pokemon": your_pokemon,
            "your_speed": your_speed,
            "your_build": {
                "nature": your_nature,
                "speed_evs": your_speed_evs,
                "base_speed": your_base_speed
            },
            "target_pokemon": target_pokemon,
            "target_base_speed": target_base_speed,
            "outspeed_probability": result.outspeed_probability,
            "speed_tie_probability": result.speed_tie_probability,
            "underspeed_probability": result.underspeed_probability,
            "analysis": result.analysis,
            "target_speed_breakdown": result.target_speed_distribution[:5],  # Top 5 spreads
            "meta_info": {
                "format": meta_info.get("format"),
                "month": meta_info.get("month")
            }
        }

    @mcp.tool(
        title="Outspeed Probability (Stored Pokemon)",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def outspeed_probability_stored(
        target_pokemon: Annotated[str, Field(description="Opponent's Pokemon (e.g. 'Landorus-Therian')", min_length=1)],
        your_pokemon_reference: Annotated[Optional[str], Field(
            description="Reference to a stored Pokemon (e.g. 'my Entei'); None uses the most recently stored",
        )] = None
    ) -> dict:
        """Calculate outspeed probability using a Pokemon previously stored with set_my_pokemon."""
        # Get stored Pokemon
        pokemon = team_manager.get_pokemon_context(your_pokemon_reference)
        if not pokemon:
            stored = team_manager.list_pokemon_context()
            return error_response(ErrorCodes.INTERNAL_ERROR, 'No stored Pokemon found', hint='Use set_my_pokemon first to store a Pokemon', stored_pokemon=[p['reference'] for p in stored])

        your_base_speed = pokemon.base_stats.speed
        # Format-aware (Champions builds carry SPs, not EVs)
        from vgc_mcp_core.calc.stats import calculate_all_stats
        your_speed = calculate_all_stats(pokemon)["speed"]

        # Get target Pokemon's base stats
        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {target_pokemon}')

        target_base_speed = target_base_stats.speed

        # Try to use get_speed_distribution() first (more efficient)
        speed_dist = await smogon.get_speed_distribution(target_pokemon, target_base_speed)

        if speed_dist and speed_dist.get("distribution"):
            # Use the new optimized path with pre-calculated speeds
            distribution = speed_dist["distribution"]

            result = calculate_outspeed_from_distribution(
                your_speed,
                distribution,
                target_pokemon,
                target_base_speed
            )

            meta_info = {"data_source": "speed_distribution"}
        else:
            # Fallback to raw spreads
            target_usage = await smogon.get_pokemon_usage(target_pokemon)
            if not target_usage:
                return error_response(ErrorCodes.INTERNAL_ERROR, f'No usage data found for {target_pokemon}')

            target_spreads = target_usage.get("spreads", [])
            meta_info = target_usage.get("_meta", {})

            result = calculate_outspeed_probability(
                your_speed,
                target_base_speed,
                target_spreads,
                target_pokemon
            )

        return {
            "your_pokemon": pokemon.name,
            "your_speed": your_speed,
            "your_build": {
                "nature": pokemon.nature.value.title(),
                "speed_evs": pokemon.evs.speed,
                "base_speed": your_base_speed
            },
            "target_pokemon": target_pokemon,
            "target_base_speed": target_base_speed,
            "outspeed_probability": result.outspeed_probability,
            "speed_tie_probability": result.speed_tie_probability,
            "underspeed_probability": result.underspeed_probability,
            "analysis": result.analysis,
            "target_speed_breakdown": result.target_speed_distribution[:5],
            "meta_info": meta_info
        }

    @mcp.tool(
        title="Analyze Meta Outspeed Rate",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def meta_outspeed_analysis(
        your_pokemon: Annotated[str, Field(description="Your Pokemon's name", min_length=1)],
        your_speed_evs: Annotated[int, Field(ge=0, le=252, description="Your Speed EVs (0-252)")],
        your_nature: Annotated[str, Field(description="Your nature (e.g. 'Timid', 'Jolly')", min_length=1)],
        top_n: Annotated[int, Field(ge=1, description="Number of top usage Pokemon to analyze")] = 20
    ) -> dict:
        """Analyze what percentage of the top meta Pokemon you outspeed.

        Provides a comprehensive view of your speed tier relative to the
        entire metagame, weighted by Pokemon usage.
        """
        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(your_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {your_pokemon}')

        your_base_speed = your_base_stats.speed

        try:
            nature_enum = Nature(your_nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {your_nature}')

        your_speed = calculate_speed(your_base_speed, ev=your_speed_evs, nature=nature_enum)

        # Get meta usage stats
        usage_stats = await smogon.get_usage_stats()
        meta_info = usage_stats.get("_meta", {})

        # Get top N Pokemon data
        usage_data = usage_stats.get("data", {})
        sorted_pokemon = sorted(
            usage_data.items(),
            key=lambda x: x[1].get("usage", 0),
            reverse=True
        )[:top_n]

        top_pokemon_data = []
        for mon_name, mon_data in sorted_pokemon:
            # Get base stats for each Pokemon
            try:
                mon_base_stats = await pokeapi.get_base_stats(mon_name)
            except Exception:
                continue

            mon_usage = await smogon.get_pokemon_usage(mon_name)
            spreads = mon_usage.get("spreads", []) if mon_usage else []

            top_pokemon_data.append({
                "name": mon_name,
                "base_speed": mon_base_stats.speed,
                "usage_percent": round(mon_data.get("usage", 0) * 100, 2),
                "spreads": spreads
            })

        # Calculate meta outspeed rate
        result = calculate_meta_outspeed_rate(
            your_speed,
            your_pokemon,
            top_pokemon_data
        )

        return {
            "your_pokemon": your_pokemon,
            "your_speed": your_speed,
            "your_build": {
                "nature": your_nature,
                "speed_evs": your_speed_evs,
                "base_speed": your_base_speed
            },
            "meta_outspeed_rate": result.total_outspeed_rate,
            "summary": result.speed_tier_summary,
            "threats": result.threats,
            "outspeeds": result.outspeeds,
            "pokemon_breakdown": result.pokemon_analysis[:10],
            "meta_info": {
                "format": meta_info.get("format"),
                "month": meta_info.get("month"),
                "pokemon_analyzed": len(top_pokemon_data)
            }
        }

    @mcp.tool(
        title="Calculate Speed Creep EVs",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def speed_creep_calculator(
        your_pokemon: Annotated[str, Field(description="Your Pokemon's name", min_length=1)],
        your_nature: Annotated[str, Field(description="Your nature (e.g. 'Jolly', 'Timid')", min_length=1)],
        target_pokemon: Annotated[str, Field(description="Pokemon to outspeed", min_length=1)],
        desired_outspeed_pct: Annotated[float, Field(ge=0, le=100, description="Percentage of the target's spread distribution to outspeed")] = 100.0
    ) -> dict:
        """Calculate how many Speed EVs are needed to outspeed a target.

        Determines the minimum speed investment needed to outspeed a specific
        percentage of a Pokemon's Smogon spread distribution.
        """
        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(your_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {your_pokemon}')

        your_base_speed = your_base_stats.speed

        # Get target Pokemon's base stats
        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {target_pokemon}')

        target_base_speed = target_base_stats.speed

        # Get target's spread distribution
        target_usage = await smogon.get_pokemon_usage(target_pokemon)
        if not target_usage:
            return error_response(ErrorCodes.INTERNAL_ERROR, f'No usage data found for {target_pokemon}')

        target_spreads = target_usage.get("spreads", [])
        meta_info = target_usage.get("_meta", {})

        # Calculate EVs needed
        result = calculate_speed_creep_evs(
            your_base_speed,
            your_nature,
            target_base_speed,
            target_spreads,
            desired_outspeed_pct
        )

        return {
            "your_pokemon": your_pokemon,
            "your_base_speed": your_base_speed,
            "your_nature": your_nature,
            "target_pokemon": target_pokemon,
            "target_base_speed": target_base_speed,
            "desired_outspeed_pct": desired_outspeed_pct,
            "evs_needed": result.get("evs_needed"),
            "resulting_speed": result.get("resulting_speed"),
            "actual_outspeed_pct": result.get("actual_outspeed_pct"),
            "cannot_achieve": result.get("cannot_achieve", False),
            "analysis": result.get("analysis"),
            "meta_info": meta_info
        }

    @mcp.tool(
        title="Compare Speed Investments",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def compare_speed_investment(
        pokemon_name: Annotated[str, Field(description="Your Pokemon's name", min_length=1)],
        target_pokemon: Annotated[str, Field(description="Target Pokemon to compare against", min_length=1)],
        ev_options: Annotated[Optional[str], Field(
            description="Comma-separated Speed EV values to test (default '0,52,100,156,196,252')",
        )] = None
    ) -> dict:
        """Compare different Speed EV investments against a target.

        Shows outspeed probabilities at each EV threshold (for both Adamant
        and Jolly natures) to help decide the optimal speed investment.
        """
        # Parse EV options
        if ev_options:
            try:
                ev_list = [int(x.strip()) for x in ev_options.split(",")]
            except ValueError:
                return error_response(ErrorCodes.INVALID_EVS, 'Invalid EV options format. Use comma-separated numbers.')
        else:
            ev_list = [0, 52, 100, 156, 196, 252]

        # Get Pokemon base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(pokemon_name)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {pokemon_name}')

        your_base_speed = your_base_stats.speed

        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {target_pokemon}')

        target_base_speed = target_base_stats.speed

        # Get target spreads
        target_usage = await smogon.get_pokemon_usage(target_pokemon)
        if not target_usage:
            return error_response(ErrorCodes.INTERNAL_ERROR, f'No usage data found for {target_pokemon}')

        target_spreads = target_usage.get("spreads", [])

        # Compare at different EV levels
        comparisons = []

        for nature_name in ["Adamant", "Jolly"]:
            try:
                nature = Nature(nature_name.lower())
            except ValueError:
                continue

            for evs in ev_list:
                speed = calculate_speed(your_base_speed, ev=evs, nature=nature)
                result = calculate_outspeed_probability(
                    speed, target_base_speed, target_spreads, target_pokemon
                )

                comparisons.append({
                    "nature": nature_name,
                    "speed_evs": evs,
                    "speed_stat": speed,
                    "outspeed_pct": result.outspeed_probability,
                    "tie_pct": result.speed_tie_probability
                })

        return {
            "your_pokemon": pokemon_name,
            "your_base_speed": your_base_speed,
            "target_pokemon": target_pokemon,
            "target_base_speed": target_base_speed,
            "comparisons": comparisons,
            "recommendation": _get_speed_recommendation(comparisons)
        }


def _get_speed_recommendation(comparisons: list) -> str:
    """Generate a speed investment recommendation based on comparisons."""
    # Find the minimum investment to reach good outspeed rates
    for comp in comparisons:
        if comp["outspeed_pct"] >= 95:
            return f"{comp['speed_evs']} EVs ({comp['nature']}) outspeeds 95%+ of spreads"

    for comp in comparisons:
        if comp["outspeed_pct"] >= 75:
            return f"{comp['speed_evs']} EVs ({comp['nature']}) outspeeds 75%+ of spreads"

    return "May need significant speed investment or speed control"
