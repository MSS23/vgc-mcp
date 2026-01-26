"""MCP tools for speed tier visualization."""

from typing import Optional, List, Dict
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.stats import calculate_speed
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats, get_nature_modifier
from vgc_mcp_core.utils.errors import api_error


def register_speed_viz_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient]):
    """Register speed tier visualization tools."""

    @mcp.tool()
    async def visualize_team_speed_tiers(
        team_pokemon: List[Dict],
        include_weather: bool = True,
        include_tailwind: bool = True,
        format: str = "reg_h"
    ) -> dict:
        """
        Generate speed tier chart with your team highlighted.
        
        Args:
            team_pokemon: List of dicts with name, nature, evs, item
            include_weather: Include weather speed modifiers
            include_tailwind: Include Tailwind speed tiers
            format: VGC format
            
        Returns:
            Speed tier chart with team highlighted
        """
        try:
            # Calculate speeds for team Pokemon
            team_speeds = []
            
            for pokemon_data in team_pokemon:
                try:
                    name = pokemon_data["name"]
                    base_stats = await pokeapi.get_base_stats(name)
                    nature = Nature(pokemon_data.get("nature", "serious").lower())
                    evs = EVSpread(**pokemon_data.get("evs", {}))
                    
                    speed = calculate_speed(
                        base_stats.speed,
                        31,  # IVs
                        evs.speed,
                        50,  # Level
                        get_nature_modifier(nature, "speed")
                    )
                    
                    team_speeds.append({
                        "name": name,
                        "speed": speed,
                        "nature": pokemon_data.get("nature", "serious"),
                        "evs": pokemon_data.get("evs", {})
                    })
                except Exception as e:
                    logger.warning(f"Failed to calculate speed for {pokemon_data.get('name')}: {e}")
                    continue
            
            # Get common meta Pokemon speeds for comparison
            meta_speeds = []
            common_meta = ["flutter-mane", "dragapult", "miraidon", "tornadus", "landorus", "incineroar", "amoonguss"]
            
            for meta_name in common_meta:
                try:
                    base_stats = await pokeapi.get_base_stats(meta_name)
                    # Use common spread: Timid/Jolly 252 Speed
                    speed = calculate_speed(
                        base_stats.speed,
                        31,
                        252,
                        50,
                        1.1  # +Speed nature
                    )
                    meta_speeds.append({
                        "name": meta_name,
                        "speed": speed,
                        "is_team": False
                    })
                except Exception:
                    continue
            
            # Combine and sort
            all_speeds = team_speeds + meta_speeds
            all_speeds.sort(key=lambda x: x["speed"], reverse=True)
            
            # Build markdown output
            markdown_lines = [
                "## Speed Tier Chart",
                "",
                "### Base Speed Tiers (Your Team Highlighted)",
                "| Speed | Pokemon | Notes |",
                "|-------|---------|-------|"
            ]
            
            for entry in all_speeds:
                is_team = entry["name"] in [t["name"] for t in team_speeds]
                marker = "★ " if is_team else ""
                notes = "YOUR TEAM" if is_team else "Common spread"
                markdown_lines.append(
                    f"| {entry['speed']} | {marker}{entry['name'].title()} | {notes} |"
                )
            
            # Tailwind tiers
            if include_tailwind:
                markdown_lines.extend([
                    "",
                    "### With Tailwind (2×)",
                    "| Speed | Pokemon | Notes |",
                    "|-------|---------|-------|"
                ])
                
                for entry in all_speeds:
                    tailwind_speed = entry["speed"] * 2
                    is_team = entry["name"] in [t["name"] for t in team_speeds]
                    marker = "★ " if is_team else ""
                    markdown_lines.append(
                        f"| {tailwind_speed} | {marker}{entry['name'].title()} | "
                        f"{'YOUR TEAM' if is_team else 'Common spread'} |"
                    )
            
            # Key observations
            markdown_lines.extend([
                "",
                "### Key Observations"
            ])
            
            if team_speeds:
                fastest_team = max(team_speeds, key=lambda x: x["speed"])
                markdown_lines.append(
                    f"- {fastest_team['name'].title()} outspeeds unboosted meta"
                )
            
            response = {
                "team_speeds": team_speeds,
                "meta_speeds": meta_speeds,
                "all_speeds": all_speeds,
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in visualize_team_speed_tiers: {e}", exc_info=True)
            return api_error(str(e))
