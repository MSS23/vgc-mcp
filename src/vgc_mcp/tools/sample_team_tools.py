"""MCP tools for sample teams database."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.data.sample_teams import (
    ALL_SAMPLE_TEAMS,
    get_teams_by_archetype,
    get_teams_with_pokemon,
    get_teams_by_regulation,
    get_teams_by_difficulty,
    get_all_archetypes,
    SampleTeam,
)


def register_sample_team_tools(mcp: FastMCP):
    """Register sample team tools."""

    @mcp.tool()
    async def get_sample_team(
        archetype: Optional[str] = None,
        pokemon: Optional[str] = None,
        regulation: Optional[str] = None,
        difficulty: Optional[str] = None
    ) -> dict:
        """
        Get sample tournament-proven teams.

        Args:
            archetype: Team style - "rain", "sun", "trick_room", "hyper_offense", "goodstuffs", "balance"
            pokemon: Find teams containing this Pokemon
            regulation: VGC regulation (e.g., "G", "H")
            difficulty: "beginner", "intermediate", or "advanced"

        Returns:
            Sample teams with full Showdown pastes, descriptions, strengths/weaknesses
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
            return {
                "error": "No teams match your criteria",
                "available_archetypes": get_all_archetypes(),
                "suggestion": "Try a different archetype or remove some filters"
            }

        return {
            "count": len(teams),
            "teams": [_format_team(t) for t in teams]
        }

    @mcp.tool()
    async def list_sample_team_archetypes() -> dict:
        """
        List all available team archetypes in the sample database.

        Returns:
            List of archetypes with descriptions
        """
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

    @mcp.tool()
    async def get_team_paste(
        team_name: str
    ) -> dict:
        """
        Get the full Showdown paste for a sample team by name.

        Args:
            team_name: Name of the sample team

        Returns:
            Full Showdown-importable paste
        """
        for team in ALL_SAMPLE_TEAMS:
            if team.name.lower() == team_name.lower():
                return {
                    "name": team.name,
                    "archetype": team.archetype,
                    "paste": team.paste,
                    "usage_tip": "Copy the paste above and import into Pokemon Showdown or your team builder"
                }

        return {
            "error": f"Team '{team_name}' not found",
            "available_teams": [t.name for t in ALL_SAMPLE_TEAMS]
        }

    @mcp.tool()
    async def suggest_team_for_playstyle(
        playstyle: str,
        experience_level: str = "intermediate"
    ) -> dict:
        """
        Suggest a sample team based on your preferred playstyle.

        Args:
            playstyle: How you like to play - "aggressive", "defensive", "weather", "speed_control", "flexible"
            experience_level: "beginner", "intermediate", or "advanced"

        Returns:
            Recommended team(s) for your playstyle
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
