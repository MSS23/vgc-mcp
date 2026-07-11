"""MCP tools for core building and team suggestions."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.team.core_builder import (
    POKEMON_ROLES,
    analyze_core_synergy,
    complete_team,
    find_popular_cores,
    get_pokemon_role,
    suggest_partners,
)
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.utils.errors import ErrorCodes, error_response, success_response


def register_core_tools(
    mcp: FastMCP,
    team_manager: TeamManager,
    smogon_client: SmogonStatsClient
):
    """Register core building tools with the MCP server."""

    @mcp.tool(
        title="Suggest Partners With Synergy",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_partners_with_synergy(
        pokemon_name: Annotated[str, Field(description="The Pokemon to find partners for", min_length=1)],
        limit: Annotated[int, Field(ge=1, description="Maximum number of suggestions")] = 10
    ) -> dict:
        """Suggest Pokemon that pair well with a given Pokemon (enhanced analysis).

        Uses Smogon usage data combined with type synergy, role
        complementarity, and current-team context for better suggestions than
        raw usage data. Returns a ranked list of teammates with synergy
        scores and reasoning.
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
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Could not find teammate data for {pokemon_name}",
                    suggestions=["Check spelling or try a more common Pokemon"],
                )

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Get Popular Cores",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_popular_cores(
        limit: Annotated[int, Field(ge=1, description="Maximum number of cores to return")] = 10
    ) -> dict:
        """Get popular 2-Pokemon cores from the current metagame.

        Analyzes Smogon usage data to find Pokemon that are frequently used
        together in top teams. Returns cores with pairing rates and roles.
        """
        try:
            cores = await find_popular_cores(smogon_client, size=2, limit=limit)

            if not cores:
                return error_response(
                    ErrorCodes.API_ERROR,
                    "Could not fetch core data",
                    suggestions=["Smogon stats may be temporarily unavailable"],
                )

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Analyze Team Synergy",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_team_synergy() -> dict:
        """Analyze how well the current team members work together.

        Evaluates type coverage and resistances, role coverage (speed
        control, support, etc.), shared weaknesses, and missing elements.
        Requires at least 2 Pokemon on the current team. Returns a synergy
        score with strengths, weaknesses, and recommendations.
        """
        try:
            if team_manager.size < 2:
                return error_response(
                    ErrorCodes.INVALID_PARAMETER,
                    "Need at least 2 Pokemon to analyze synergy",
                    current_size=team_manager.size,
                )

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Suggest Team Completion",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_team_completion(
        limit: Annotated[int, Field(ge=1, description="Number of suggestions to return")] = 5
    ) -> dict:
        """Suggest Pokemon to complete the current team.

        Analyzes the current team composition and suggests Pokemon that
        would fill gaps in coverage, roles, and synergy. Requires at least
        one Pokemon on the team and open slots.
        """
        try:
            if team_manager.size == 0:
                return error_response(
                    ErrorCodes.TEAM_EMPTY,
                    "No Pokemon on team. Add some Pokemon first.",
                    suggestions=["Try adding 1-2 Pokemon you want to build around"],
                )

            if team_manager.is_full:
                return success_response(
                    "Team is already full (6 Pokemon)",
                    team=team_manager.team.get_pokemon_names(),
                    suggestions=["Use analyze_team_synergy to check team quality"],
                )

            suggestions = await complete_team(
                team_manager.team,
                smogon_client,
                limit=limit
            )

            if not suggestions:
                return error_response(
                    ErrorCodes.INTERNAL_ERROR,
                    "Could not generate suggestions",
                    team=team_manager.team.get_pokemon_names(),
                )

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Get Pokemon Roles",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_pokemon_roles(
        pokemon_name: Annotated[str, Field(description="The Pokemon to check", min_length=1)]
    ) -> dict:
        """Get the competitive roles a Pokemon can fill.

        Roles include Tailwind setter, Trick Room setter, Intimidate support,
        weather setter, etc. Returns the list of roles this Pokemon can fill.
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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="List Role Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_role_pokemon(
        role: Annotated[str, Field(
            description=(
                "The role to look up: tailwind_setter, trick_room_setter, "
                "sun_setter, rain_setter, sand_setter, snow_setter, "
                "grassy_terrain, electric_terrain, psychic_terrain, "
                "misty_terrain, intimidate, fake_out, redirection, restricted"
            ),
            min_length=1,
        )]
    ) -> dict:
        """List Pokemon that can fill a specific role.

        Returns the Pokemon that fill the given role; unknown roles return
        an error listing the available roles.
        """
        try:
            role = role.lower().replace(" ", "_").replace("-", "_")

            if role not in POKEMON_ROLES:
                return error_response(
                    ErrorCodes.INVALID_PARAMETER,
                    f"Unknown role: {role}",
                    available_roles=list(POKEMON_ROLES.keys()),
                )

            pokemon_list = POKEMON_ROLES[role]

            return {
                "role": role,
                "pokemon": pokemon_list,
                "count": len(pokemon_list)
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


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
