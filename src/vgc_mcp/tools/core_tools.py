"""MCP tools for core building and team suggestions."""

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.team.core_builder import (
    suggest_partners,
    find_popular_cores,
    analyze_core_synergy,
    complete_team,
    get_pokemon_role,
    POKEMON_ROLES,
)


def register_core_tools(
    mcp: FastMCP,
    team_manager: TeamManager,
    smogon_client: SmogonStatsClient
):
    """Register core building tools with the MCP server."""

    @mcp.tool()
    async def suggest_partners_with_synergy(pokemon_name: str, limit: int = 10) -> dict:
        """
        Suggest Pokemon that pair well with a given Pokemon (enhanced analysis).

        Uses Smogon usage data combined with type synergy, role complementarity,
        and team context analysis for better suggestions than raw usage data.

        Args:
            pokemon_name: The Pokemon to find partners for
            limit: Maximum number of suggestions (default 10)

        Returns:
            Ranked list of suggested teammates with synergy scores and reasoning
        """
        try:
            # Normalize name
            pokemon_name = pokemon_name.lower().replace(" ", "-")

            suggestions = await suggest_partners(
                pokemon_name,
                smogon_client,
                existing_team=team_manager.team if team_manager.size > 0 else None,
                limit=limit
            )

            if not suggestions:
                return {
                    "error": f"Could not find teammate data for {pokemon_name}",
                    "suggestion": "Check spelling or try a more common Pokemon"
                }

            return {
                "pokemon": pokemon_name,
                "suggestions": [
                    {
                        "name": s.pokemon_name,
                        "synergy_score": round(s.synergy_score, 1),
                        "usage_correlation": s.usage_correlation,
                        "reasons": s.reasons
                    }
                    for s in suggestions
                ],
                "current_team": team_manager.team.get_pokemon_names() if team_manager.size > 0 else []
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_popular_cores(limit: int = 10) -> dict:
        """
        Get popular 2-Pokemon cores from the current metagame.

        Analyzes Smogon usage data to find Pokemon that are frequently
        used together in top teams.

        Args:
            limit: Maximum number of cores to return (default 10)

        Returns:
            List of popular cores with usage data
        """
        try:
            cores = await find_popular_cores(smogon_client, size=2, limit=limit)

            if not cores:
                return {
                    "error": "Could not fetch core data",
                    "suggestion": "Smogon stats may be temporarily unavailable"
                }

            return {
                "core_count": len(cores),
                "cores": [
                    {
                        "pokemon": c["pokemon"],
                        "pairing_rate": f"{c['pairing_rate']:.1f}%",
                        "primary_usage": f"{c['primary_usage']:.1f}%",
                        "roles": c["roles"]
                    }
                    for c in cores
                ]
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_team_synergy() -> dict:
        """
        Analyze how well the current team members work together.

        Evaluates:
        - Type coverage and resistances
        - Role coverage (speed control, support, etc.)
        - Shared weaknesses
        - Missing elements

        Returns:
            Synergy analysis with score and recommendations
        """
        try:
            if team_manager.size < 2:
                return {
                    "error": "Need at least 2 Pokemon to analyze synergy",
                    "current_size": team_manager.size
                }

            analysis = analyze_core_synergy(team_manager.team)

            return {
                "pokemon": analysis.pokemon,
                "synergy_score": analysis.synergy_score,
                "rating": _get_synergy_rating(analysis.synergy_score),
                "strengths": analysis.strengths,
                "weaknesses": analysis.weaknesses,
                "recommendations": analysis.recommendations,
                "type_resistances": {
                    k: v for k, v in analysis.type_coverage.items() if v >= 2
                }
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def suggest_team_completion(limit: int = 5) -> dict:
        """
        Suggest Pokemon to complete the current team.

        Analyzes the current team composition and suggests Pokemon
        that would fill gaps in coverage, roles, and synergy.

        Args:
            limit: Number of suggestions to return (default 5)

        Returns:
            Suggested Pokemon with reasoning
        """
        try:
            if team_manager.size == 0:
                return {
                    "error": "No Pokemon on team. Add some Pokemon first.",
                    "suggestion": "Try adding 1-2 Pokemon you want to build around"
                }

            if team_manager.is_full:
                return {
                    "message": "Team is already full (6 Pokemon)",
                    "team": team_manager.team.get_pokemon_names(),
                    "suggestion": "Use analyze_team_synergy to check team quality"
                }

            suggestions = await complete_team(
                team_manager.team,
                smogon_client,
                limit=limit
            )

            if not suggestions:
                return {
                    "error": "Could not generate suggestions",
                    "team": team_manager.team.get_pokemon_names()
                }

            # Also get current analysis for context
            current_analysis = analyze_core_synergy(team_manager.team)

            return {
                "current_team": team_manager.team.get_pokemon_names(),
                "slots_remaining": 6 - team_manager.size,
                "current_weaknesses": current_analysis.weaknesses[:3],
                "suggestions": [
                    {
                        "name": s.pokemon_name,
                        "synergy_score": round(s.synergy_score, 1),
                        "usage_correlation": s.usage_correlation,
                        "reasons": s.reasons
                    }
                    for s in suggestions
                ]
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_pokemon_roles(pokemon_name: str) -> dict:
        """
        Get the competitive roles a Pokemon can fill.

        Roles include things like Tailwind setter, Trick Room setter,
        Intimidate support, weather setter, etc.

        Args:
            pokemon_name: The Pokemon to check

        Returns:
            List of roles this Pokemon can fill
        """
        try:
            pokemon_name = pokemon_name.lower().replace(" ", "-")
            roles = get_pokemon_role(pokemon_name)

            return {
                "pokemon": pokemon_name,
                "roles": roles if roles else ["No specific VGC role identified"],
                "note": "Pokemon without specific roles can still be valuable attackers/defenders"
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def list_role_pokemon(role: str) -> dict:
        """
        List Pokemon that can fill a specific role.

        Available roles:
        - tailwind_setter, trick_room_setter
        - sun_setter, rain_setter, sand_setter, snow_setter
        - grassy_terrain, electric_terrain, psychic_terrain, misty_terrain
        - intimidate, fake_out, redirection
        - restricted

        Args:
            role: The role to look up

        Returns:
            List of Pokemon that fill this role
        """
        try:
            role = role.lower().replace(" ", "_").replace("-", "_")

            if role not in POKEMON_ROLES:
                return {
                    "error": f"Unknown role: {role}",
                    "available_roles": list(POKEMON_ROLES.keys())
                }

            pokemon_list = POKEMON_ROLES[role]

            return {
                "role": role,
                "pokemon": pokemon_list,
                "count": len(pokemon_list)
            }

        except Exception as e:
            return {"error": str(e)}


def _get_synergy_rating(score: float) -> str:
    """Convert synergy score to a human-readable rating."""
    if score >= 80:
        return "Excellent"
    elif score >= 65:
        return "Good"
    elif score >= 50:
        return "Average"
    elif score >= 35:
        return "Below Average"
    else:
        return "Poor"
