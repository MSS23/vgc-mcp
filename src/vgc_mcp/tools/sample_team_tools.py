"""MCP tools for sample teams database."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.data.sample_teams import (
    ALL_SAMPLE_TEAMS,
    SampleTeam,
    get_all_archetypes,
    get_teams_by_archetype,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_sample_team_tools(mcp: FastMCP):
    """Register sample team tools."""

    @mcp.tool(
        title="Get Sample Team",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_sample_team(
        archetype: Annotated[Optional[str], Field(
            description="Team style filter: 'rain', 'sun', 'trick_room', 'hyper_offense', 'goodstuffs', or 'balance'",
        )] = None,
        pokemon: Annotated[Optional[str], Field(
            description="Only return teams containing this Pokemon",
        )] = None,
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation filter (e.g. 'G', 'H')",
        )] = None,
        difficulty: Annotated[Optional[str], Field(
            description="Difficulty filter: 'beginner', 'intermediate', or 'advanced'",
        )] = None
    ) -> dict:
        """Get sample tournament-proven teams matching the given filters.

        Returns teams with Showdown paste previews, descriptions, and
        strengths/weaknesses. All filters are optional and combine.
        """
        teams = ALL_SAMPLE_TEAMS

        if archetype:
            teams = [t for t in teams if t.archetype.lower() == archetype.lower()]
        if pokemon:
            pokemon_lower = pokemon.lower().replace(" ", "-")
            teams = [
                t for t in teams
                if any(pokemon_lower in p.lower().replace(" ", "-") for p in t.pokemon)
            ]
        if regulation:
            teams = [t for t in teams if t.regulation.upper() == regulation.upper()]
        if difficulty:
            teams = [t for t in teams if t.difficulty.lower() == difficulty.lower()]

        if not teams:
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                "No teams match your criteria",
                suggestions=["Try a different archetype or remove some filters"],
                available_archetypes=get_all_archetypes(),
            )

        return {
            "count": len(teams),
            "teams": [_format_team(t) for t in teams]
        }

    @mcp.tool(
        title="List Sample Team Archetypes",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_sample_team_archetypes() -> dict:
        """List all available team archetypes in the sample database, with descriptions."""
        archetype_info = {
            "rain": "Weather teams centered around Drizzle + Swift Swim/Water moves",
            "sun": "Weather teams with Drought/Orichalcum Pulse boosting Fire moves",
            "trick_room": "Speed control teams that reverse turn order",
            "hyper_offense": "All-out attacking teams with minimal defense",
            "goodstuffs": "Flexible teams with individually strong Pokemon",
            "balance": "Teams with both offensive and defensive options"
        }

        available = get_all_archetypes()
        return {
            "archetypes": [
                {"name": a, "description": archetype_info.get(a, "Team archetype")}
                for a in available
            ],
            "total_teams": len(ALL_SAMPLE_TEAMS)
        }

    @mcp.tool(
        title="Get Sample Team Paste",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_team_paste(
        team_name: Annotated[str, Field(
            description="Name of the sample team (case-insensitive exact match)",
            min_length=1,
        )]
    ) -> dict:
        """Get the full Showdown-importable paste for a sample team by name."""
        for team in ALL_SAMPLE_TEAMS:
            if team.name.lower() == team_name.lower():
                return {
                    "name": team.name,
                    "archetype": team.archetype,
                    "paste": team.paste,
                    "usage_tip": "Copy the paste above and import into Pokemon Showdown or your team builder"
                }

        return error_response(
            ErrorCodes.INVALID_PARAMETER,
            f"Team '{team_name}' not found",
            available_teams=[t.name for t in ALL_SAMPLE_TEAMS],
        )

    @mcp.tool(
        title="Suggest Team for Playstyle",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def suggest_team_for_playstyle(
        playstyle: Annotated[str, Field(
            description=(
                "How you like to play: 'aggressive', 'defensive', 'weather', "
                "'speed_control', 'flexible', 'fast', or 'slow' (unknown values fall back to 'goodstuffs')"
            ),
        )],
        experience_level: Annotated[str, Field(
            description="'beginner', 'intermediate', or 'advanced'",
        )] = "intermediate"
    ) -> dict:
        """Suggest a sample team based on your preferred playstyle.

        Returns a recommended team plus up to two alternatives, preferring
        teams that match the given experience level.
        """
        playstyle_map = {
            "aggressive": ["hyper_offense", "sun"],
            "defensive": ["trick_room", "balance"],
            "weather": ["rain", "sun"],
            "speed_control": ["trick_room", "rain"],  # Rain often has Tailwind
            "flexible": ["goodstuffs", "balance"],
            "fast": ["hyper_offense", "rain"],
            "slow": ["trick_room"],
        }

        # Find matching archetypes
        matching_archetypes = playstyle_map.get(
            playstyle.lower(),
            ["goodstuffs"]  # Default
        )

        # Find teams
        candidates = []
        for archetype in matching_archetypes:
            for team in get_teams_by_archetype(archetype):
                if team.difficulty.lower() == experience_level.lower():
                    candidates.append(team)

        # If no exact difficulty match, broaden search
        if not candidates:
            for archetype in matching_archetypes:
                candidates.extend(get_teams_by_archetype(archetype))

        if not candidates:
            candidates = ALL_SAMPLE_TEAMS[:3]

        return {
            "playstyle": playstyle,
            "experience_level": experience_level,
            "recommended": _format_team(candidates[0]) if candidates else None,
            "alternatives": [_format_team(t) for t in candidates[1:3]] if len(candidates) > 1 else []
        }


def _format_team(team: SampleTeam) -> dict:
    """Format a team for output."""
    return {
        "name": team.name,
        "archetype": team.archetype,
        "pokemon": team.pokemon,
        "description": team.description,
        "strengths": team.strengths,
        "weaknesses": team.weaknesses,
        "regulation": team.regulation,
        "difficulty": team.difficulty,
        "source": team.source,
        "paste_preview": team.paste[:500] + "..." if len(team.paste) > 500 else team.paste
    }
