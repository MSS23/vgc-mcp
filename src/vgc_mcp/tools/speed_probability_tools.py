"""MCP tools for speed probability analysis.

This module provides tools to calculate the probability of outspeeding
opponents based on current Smogon usage data. It accounts for the
distribution of spreads used by players in the meta.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.calc.stats import calculate_speed
from vgc_mcp_core.calc.speed_probability import (
    calculate_outspeed_probability,
    calculate_outspeed_from_distribution,
    calculate_meta_outspeed_rate,
    calculate_speed_creep_evs,
    parse_spread_to_speed,
    build_speed_distribution_data,
    calculate_speed_stat,
)
# Note: MCP-UI is only available in vgc-mcp-lite, not the full server
HAS_UI = False

from vgc_mcp_core.models.pokemon import Nature


def register_speed_probability_tools(mcp: FastMCP, smogon, pokeapi, team_manager):
    """Register speed probability analysis tools with the MCP server."""

    @mcp.tool()
    async def outspeed_probability(
        your_pokemon: str,
        your_speed_evs: int,
        your_nature: str,
        target_pokemon: str
    ) -> dict:
        """
        Calculate probability of outspeeding a specific opponent.

        Uses live Smogon usage data to determine what percentage of
        the target's common spreads you will outspeed.

        Example: "What's the probability my Entei outspeeds Landorus?"

        Args:
            your_pokemon: Your Pokemon's name (e.g., "Entei")
            your_speed_evs: Your Speed EVs (0-252)
            your_nature: Your nature (e.g., "Adamant", "Jolly")
            target_pokemon: Opponent's Pokemon (e.g., "Landorus-Therian")

        Returns:
            Outspeed probability breakdown with analysis
        """
        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(your_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {your_pokemon}"}

        your_base_speed = your_base_stats.speed

        # Parse nature to get speed modifier
        try:
            nature_enum = Nature(your_nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {your_nature}"}

        # Calculate your speed stat
        your_speed = calculate_speed(your_base_speed, ev=your_speed_evs, nature=nature_enum)

        # Get target Pokemon's base stats
        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {target_pokemon}"}

        target_base_speed = target_base_stats.speed

        # Try to use get_speed_distribution() first (more efficient)
        speed_dist = await smogon.get_speed_distribution(target_pokemon, target_base_speed)

        if speed_dist and speed_dist.get("distribution"):
            # Use the new optimized path with pre-calculated speeds
            distribution = speed_dist["distribution"]
            speed_stats = speed_dist.get("stats", {})

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
                return {
                    "error": f"No usage data found for {target_pokemon}",
                    "note": "Target may not be common enough in the current meta"
                }

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

    @mcp.tool()
    async def outspeed_probability_stored(
        target_pokemon: str,
        your_pokemon_reference: Optional[str] = None
    ) -> dict:
        """
        Calculate outspeed probability using a stored Pokemon.

        Uses a Pokemon previously stored with set_my_pokemon.

        Args:
            target_pokemon: Opponent's Pokemon (e.g., "Landorus-Therian")
            your_pokemon_reference: Reference to stored Pokemon (e.g., "my Entei"),
                                   or None to use most recently stored

        Returns:
            Outspeed probability breakdown
        """
        # Get stored Pokemon
        pokemon = team_manager.get_pokemon_context(your_pokemon_reference)
        if not pokemon:
            stored = team_manager.list_pokemon_context()
            return {
                "error": "No stored Pokemon found",
                "hint": "Use set_my_pokemon first to store a Pokemon",
                "stored_pokemon": [p["reference"] for p in stored]
            }

        your_base_speed = pokemon.base_stats.speed
        your_speed = calculate_speed(
            your_base_speed,
            ev=pokemon.evs.speed,
            nature=pokemon.nature
        )

        # Get target Pokemon's base stats
        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {target_pokemon}"}

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
                return {"error": f"No usage data found for {target_pokemon}"}

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

    @mcp.tool()
    async def meta_outspeed_analysis(
        your_pokemon: str,
        your_speed_evs: int,
        your_nature: str,
        top_n: int = 20
    ) -> dict:
        """
        Analyze what percentage of the top meta Pokemon you outspeed.

        Provides a comprehensive view of your speed tier relative to
        the entire metagame, weighted by Pokemon usage.

        Args:
            your_pokemon: Your Pokemon's name
            your_speed_evs: Your Speed EVs (0-252)
            your_nature: Your nature
            top_n: Number of top Pokemon to analyze (default 20)

        Returns:
            Meta-wide speed analysis with threats and outspeeds
        """
        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(your_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {your_pokemon}"}

        your_base_speed = your_base_stats.speed

        try:
            nature_enum = Nature(your_nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {your_nature}"}

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

    @mcp.tool()
    async def speed_creep_calculator(
        your_pokemon: str,
        your_nature: str,
        target_pokemon: str,
        desired_outspeed_pct: float = 100.0
    ) -> dict:
        """
        Calculate how many Speed EVs needed to outspeed a target.

        Determines the minimum speed investment needed to outspeed
        a specific percentage of a Pokemon's spread distribution.

        Args:
            your_pokemon: Your Pokemon's name
            your_nature: Your nature
            target_pokemon: Pokemon to outspeed
            desired_outspeed_pct: % of target spreads to outspeed (default 100)

        Returns:
            Required Speed EVs and resulting stats
        """
        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(your_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {your_pokemon}"}

        your_base_speed = your_base_stats.speed

        # Get target Pokemon's base stats
        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {target_pokemon}"}

        target_base_speed = target_base_stats.speed

        # Get target's spread distribution
        target_usage = await smogon.get_pokemon_usage(target_pokemon)
        if not target_usage:
            return {"error": f"No usage data found for {target_pokemon}"}

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

    @mcp.tool()
    async def compare_speed_investment(
        pokemon_name: str,
        target_pokemon: str,
        ev_options: Optional[str] = None
    ) -> dict:
        """
        Compare different speed investments against a target.

        Shows outspeed probabilities at different EV thresholds
        to help decide optimal speed investment.

        Args:
            pokemon_name: Your Pokemon's name
            target_pokemon: Target to compare against
            ev_options: Comma-separated EVs to test (default: "0,52,100,156,196,252")

        Returns:
            Comparison of outspeed rates at each EV threshold
        """
        # Parse EV options
        if ev_options:
            try:
                ev_list = [int(x.strip()) for x in ev_options.split(",")]
            except ValueError:
                return {"error": "Invalid EV options format. Use comma-separated numbers."}
        else:
            ev_list = [0, 52, 100, 156, 196, 252]

        # Get Pokemon base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(pokemon_name)
        except Exception:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        your_base_speed = your_base_stats.speed

        try:
            target_base_stats = await pokeapi.get_base_stats(target_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {target_pokemon}"}

        target_base_speed = target_base_stats.speed

        # Get target spreads
        target_usage = await smogon.get_pokemon_usage(target_pokemon)
        if not target_usage:
            return {"error": f"No usage data found for {target_pokemon}"}

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


def _get_outspeed_pct_from_distribution(speed: int, distribution: list[dict]) -> float:
    """Get the outspeed percentage for a given speed from the distribution."""
    cumulative_pct = 0.0
    for entry in distribution:
        if entry["speed"] < speed:
            cumulative_pct = entry["cumulative_outspeed_pct"]
        else:
            break
    return cumulative_pct


def register_visualize_outspeed_tool(mcp: FastMCP, smogon, pokeapi):
    """Register the visualize_outspeed_percentage tool separately."""

    @mcp.tool()
    async def visualize_outspeed_percentage(
        pokemon_name: str,
        speed_evs: int = 0,
        nature: str = "Serious",
        mode: str = "meta",
        target_pokemon: Optional[str] = None,
        top_n: int = 20
    ) -> dict:
        """
        Interactive visualization of outspeed percentages.

        Shows what % of the meta (or a specific target) your Pokemon outspeeds,
        with a slider to adjust Speed EVs in real-time.

        Args:
            pokemon_name: Your Pokemon's name (e.g., "Entei", "Flutter Mane")
            speed_evs: Current Speed EVs (0-252, default 0)
            nature: Nature affecting speed (e.g., "Jolly", "Timid", "Adamant")
            mode: "meta" for meta-wide analysis, "single" for single target
            target_pokemon: Target Pokemon name (required if mode="single")
            top_n: Number of top Pokemon to analyze for meta mode (default 20)

        Returns:
            Outspeed analysis with interactive UI visualization
        """
        # Validate mode
        if mode not in ["meta", "single"]:
            return {"error": f"Invalid mode: {mode}. Use 'meta' or 'single'."}

        if mode == "single" and not target_pokemon:
            return {"error": "target_pokemon is required when mode='single'"}

        # Get your Pokemon's base stats
        try:
            your_base_stats = await pokeapi.get_base_stats(pokemon_name)
        except Exception:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        base_speed = your_base_stats.speed

        # Calculate current speed stat
        current_speed = calculate_speed_stat(base_speed, nature, speed_evs)

        # Get meta usage stats
        usage_stats = await smogon.get_usage_stats()
        meta_info = usage_stats.get("_meta", {})

        if mode == "meta":
            # Build speed distribution from top N Pokemon
            usage_data = usage_stats.get("data", {})
            sorted_pokemon = sorted(
                usage_data.items(),
                key=lambda x: x[1].get("usage", 0),
                reverse=True
            )[:top_n]

            top_pokemon_data = []
            for mon_name, mon_data in sorted_pokemon:
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

            # Build the speed distribution
            speed_distribution = build_speed_distribution_data(top_pokemon_data)

            # Build Pokemon base speed lookup for UI (to calculate theoretical max)
            pokemon_base_speeds = {p["name"]: p["base_speed"] for p in top_pokemon_data}

        else:
            # Single target mode
            try:
                target_base_stats = await pokeapi.get_base_stats(target_pokemon)
            except Exception:
                return {"error": f"Pokemon not found: {target_pokemon}"}

            target_base_speed = target_base_stats.speed

            target_usage = await smogon.get_pokemon_usage(target_pokemon)
            if not target_usage:
                return {"error": f"No usage data for {target_pokemon}"}

            target_spreads = target_usage.get("spreads", [])

            # Build distribution from single target
            single_pokemon_data = [{
                "name": target_pokemon,
                "base_speed": target_base_speed,
                "usage_percent": 100.0,  # Treat as 100% for single target
                "spreads": target_spreads
            }]
            speed_distribution = build_speed_distribution_data(single_pokemon_data)

            # Build Pokemon base speed lookup for single target
            pokemon_base_speeds = {target_pokemon: target_base_speed}

        # Calculate initial outspeed percentage
        outspeed_pct = _get_outspeed_pct_from_distribution(current_speed, speed_distribution)

        # Build result
        result = {
            "pokemon": pokemon_name,
            "base_speed": base_speed,
            "current_speed": current_speed,
            "nature": nature,
            "speed_evs": speed_evs,
            "outspeed_percentage": round(outspeed_pct, 1),
            "mode": mode,
            "analysis": _get_outspeed_analysis(outspeed_pct, pokemon_name, current_speed),
            "meta_info": {
                "format": meta_info.get("format"),
                "month": meta_info.get("month"),
                "pokemon_analyzed": top_n if mode == "meta" else 1
            }
        }

        if mode == "single":
            result["target_pokemon"] = target_pokemon

        # Create UI resource (only in vgc-mcp-lite)
        if HAS_UI:
            ui_resource = create_speed_outspeed_resource(
                pokemon_name=pokemon_name,
                base_speed=base_speed,
                current_speed=current_speed,
                nature=nature,
                speed_evs=speed_evs,
                speed_distribution=speed_distribution,
                outspeed_percentage=outspeed_pct,
                mode=mode,
                target_pokemon=target_pokemon if mode == "single" else None,
                format_info={
                    "format": meta_info.get("format", "VGC"),
                    "month": meta_info.get("month", "")
                },
                pokemon_base_speeds=pokemon_base_speeds,
            )
            return add_ui_metadata(result, ui_resource)

        return result


def _get_outspeed_analysis(pct: float, pokemon: str, speed: int) -> str:
    """Generate analysis text based on outspeed percentage."""
    if pct >= 90:
        return f"{pokemon} at {speed} Speed is extremely fast - outspeeds {pct:.1f}% of the meta"
    elif pct >= 70:
        return f"{pokemon} at {speed} Speed is quite fast - outspeeds {pct:.1f}% of the meta"
    elif pct >= 50:
        return f"{pokemon} at {speed} Speed is average - outspeeds {pct:.1f}% of the meta"
    elif pct >= 30:
        return f"{pokemon} at {speed} Speed is on the slower side - outspeeds only {pct:.1f}% of the meta"
    else:
        return f"{pokemon} at {speed} Speed is slow - outspeeds only {pct:.1f}% of the meta"
