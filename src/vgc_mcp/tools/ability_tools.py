"""MCP tools for ability synergy and interaction analysis."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.calc.abilities import (
    analyze_intimidate_matchup,
    analyze_weather_synergy as _analyze_weather_synergy,
    analyze_terrain_synergy as _analyze_terrain_synergy,
    find_redirect_abilities,
    find_partner_abilities,
    find_ability_conflicts as _find_ability_conflicts,
    analyze_full_ability_synergy,
    get_speed_ability_effect,
    suggest_ability_additions as _suggest_ability_additions,
    INTIMIDATE_POKEMON,
    INTIMIDATE_BLOCKERS,
    INTIMIDATE_PUNISHERS,
    WEATHER_SETTERS,
    WEATHER_ABUSERS,
    TERRAIN_SETTERS,
    REDIRECT_ABILITIES,
    PARTNER_ABILITIES,
)


def register_ability_tools(mcp: FastMCP, team_manager):
    """Register ability synergy analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_team_abilities() -> dict:
        """
        Perform full ability synergy analysis for the current team.

        Analyzes:
        - Weather setters and abusers
        - Terrain setters
        - Intimidate presence and protection
        - Redirect abilities
        - Partner-supporting abilities
        - Ability conflicts

        Returns:
            Comprehensive ability synergy report
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "error": "No Pokemon on team",
                "message": "Add Pokemon to analyze ability synergy"
            }

        # Gather team data
        abilities = []
        pokemon_names = []
        for slot in team.slots:
            pokemon = slot.pokemon
            if pokemon.ability:
                abilities.append(pokemon.ability)
            pokemon_names.append(pokemon.name)

        result = analyze_full_ability_synergy(abilities, pokemon_names)

        return {
            "weather": {
                "has_setter": result.has_weather_setter,
                "type": result.weather_type,
                "abusers": result.weather_abusers
            },
            "terrain": {
                "has_setter": result.has_terrain_setter,
                "type": result.terrain_type
            },
            "intimidate": {
                "has_intimidate": result.has_intimidate,
                "answers": result.intimidate_answers,
                "punishers": result.intimidate_punishers
            },
            "redirect_abilities": result.redirect_abilities,
            "partner_abilities": result.partner_abilities,
            "conflicts": result.conflicts,
            "recommendations": result.recommendations,
            "message": (
                "Ability synergy analysis complete"
                if not result.conflicts
                else f"Found {len(result.conflicts)} ability conflict(s)"
            )
        }

    @mcp.tool()
    async def check_intimidate_answers() -> dict:
        """
        Check if the team has answers to opposing Intimidate.

        Intimidate is one of the most common abilities in VGC.
        Teams should have Pokemon that block or punish it.

        Returns:
            Intimidate protection analysis
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "protected": False,
                "message": "No Pokemon on team"
            }

        abilities = []
        pokemon_names = []
        for slot in team.slots:
            pokemon = slot.pokemon
            if pokemon.ability:
                abilities.append(pokemon.ability)
            pokemon_names.append(pokemon.name)

        result = analyze_intimidate_matchup(abilities, pokemon_names)

        return {
            "has_intimidate": result.has_intimidate,
            "intimidate_users": result.intimidate_users,
            "blockers": result.blockers,
            "punishers": result.punishers,
            "vulnerable_count": result.vulnerable_count,
            "is_protected": result.is_protected,
            "recommendation": result.recommendation,
            "blocker_examples": ["Clear Body", "Inner Focus", "Oblivious"],
            "punisher_examples": ["Defiant", "Competitive", "Contrary"],
            "message": (
                "Team has Intimidate protection"
                if result.is_protected
                else f"Warning: {result.vulnerable_count} Pokemon vulnerable to Intimidate"
            )
        }

    @mcp.tool()
    async def analyze_weather_synergy() -> dict:
        """
        Analyze team's weather setting and abuse potential.

        Checks for:
        - Weather setters (Drought, Drizzle, Sand Stream, Snow Warning)
        - Weather abusers (Chlorophyll, Swift Swim, Sand Rush, etc.)
        - Conflicting weather setters

        Returns:
            Weather synergy analysis
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "has_weather": False,
                "message": "No Pokemon on team"
            }

        abilities = [slot.pokemon.ability for slot in team.slots if slot.pokemon.ability]
        result = _analyze_weather_synergy(abilities)

        return {
            "has_setter": result.has_setter,
            "weather_type": result.weather_type,
            "setters": result.setters,
            "abusers": result.abusers,
            "synergy_score": result.synergy_score,
            "conflicts": result.conflicts,
            "message": (
                f"Team runs {result.weather_type} with {len(result.abusers)} abuser(s)"
                if result.has_setter and result.abusers
                else f"Team has {result.weather_type} but no abusers"
                if result.has_setter
                else "No weather strategy detected"
            )
        }

    @mcp.tool()
    async def analyze_terrain_synergy() -> dict:
        """
        Analyze team's terrain setting potential.

        Checks for terrain setters like Grassy Surge, Electric Surge,
        Psychic Surge, and Misty Surge.

        Returns:
            Terrain synergy analysis
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "has_terrain": False,
                "message": "No Pokemon on team"
            }

        abilities = [slot.pokemon.ability for slot in team.slots if slot.pokemon.ability]
        result = _analyze_terrain_synergy(abilities)

        terrain_benefits = {
            "grassy": [
                "Grassy Glide gets +1 priority",
                "Grass Pelt gives +50% Defense",
                "Ground moves weakened by 50%",
                "Grounded Pokemon recover HP each turn"
            ],
            "electric": [
                "Electric moves boosted 30%",
                "Prevents Sleep",
                "Surge Surfer doubles Speed",
                "Quark Drive activates"
            ],
            "psychic": [
                "Psychic moves boosted 30%",
                "Blocks priority moves against grounded Pokemon"
            ],
            "misty": [
                "Dragon moves halved vs grounded Pokemon",
                "Prevents status conditions"
            ]
        }

        return {
            "has_setter": result["has_setter"],
            "terrain_type": result["terrain_type"],
            "setters": result["setters"],
            "conflicts": result["conflicts"],
            "terrain_benefits": terrain_benefits.get(result["terrain_type"], []),
            "message": (
                f"Team sets {result['terrain_type']} terrain"
                if result["has_setter"]
                else "No terrain setter on team"
            )
        }

    @mcp.tool()
    async def find_ability_conflicts() -> dict:
        """
        Check for conflicting abilities on the team.

        Identifies:
        - Multiple different weather setters
        - Multiple different terrain setters
        - Weather/Terrain nullifiers vs weather/terrain teams

        Returns:
            List of ability conflicts
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "conflicts": [],
                "message": "No Pokemon on team"
            }

        abilities = [slot.pokemon.ability for slot in team.slots if slot.pokemon.ability]
        conflicts = _find_ability_conflicts(abilities)

        return {
            "conflicts": conflicts,
            "has_conflicts": len(conflicts) > 0,
            "message": (
                f"Found {len(conflicts)} ability conflict(s)"
                if conflicts
                else "No ability conflicts detected"
            )
        }

    @mcp.tool()
    async def suggest_ability_additions(
        team_style: Optional[str] = None
    ) -> dict:
        """
        Suggest abilities that would improve team synergy.

        Args:
            team_style: Optional team archetype ("rain", "sun", "trick-room", etc.)

        Returns:
            List of suggested abilities with reasons
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "suggestions": [],
                "message": "No Pokemon on team"
            }

        abilities = [slot.pokemon.ability for slot in team.slots if slot.pokemon.ability]
        suggestions = _suggest_ability_additions(abilities, team_style)

        return {
            "team_style": team_style or "general",
            "suggestions": suggestions,
            "message": f"Found {len(suggestions)} ability suggestion(s)"
        }

    @mcp.tool()
    async def check_redirect_abilities() -> dict:
        """
        Check for redirection abilities on the team.

        Redirect abilities protect partners by drawing in specific types:
        - Lightning Rod: Draws Electric moves
        - Storm Drain: Draws Water moves
        - Flash Fire: Draws Fire moves

        Returns:
            Redirect abilities and their protection
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "redirects": [],
                "message": "No Pokemon on team"
            }

        abilities = [slot.pokemon.ability for slot in team.slots if slot.pokemon.ability]
        redirects = find_redirect_abilities(abilities)

        types_protected = list(set(r["redirects_type"] for r in redirects))

        return {
            "redirects": redirects,
            "types_protected": types_protected,
            "has_redirect": len(redirects) > 0,
            "message": (
                f"Team has redirect protection for: {', '.join(types_protected)}"
                if redirects
                else "No redirect abilities on team"
            )
        }

    @mcp.tool()
    async def check_partner_abilities() -> dict:
        """
        Check for abilities that benefit partner Pokemon.

        Partner abilities include:
        - Friend Guard: -25% damage to allies
        - Power Spot: +30% power to allies' moves
        - Battery: +30% to allies' special moves
        - Steely Spirit: +50% to allies' Steel moves

        Returns:
            Partner-supporting abilities on team
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "partner_abilities": [],
                "message": "No Pokemon on team"
            }

        abilities = [slot.pokemon.ability for slot in team.slots if slot.pokemon.ability]
        partners = find_partner_abilities(abilities)

        return {
            "partner_abilities": partners,
            "has_partner_support": len(partners) > 0,
            "message": (
                f"Team has {len(partners)} partner-supporting ability(ies)"
                if partners
                else "No partner-supporting abilities on team"
            )
        }

    @mcp.tool()
    async def get_common_intimidate_pokemon() -> dict:
        """
        Get list of common Intimidate Pokemon in VGC.

        Returns:
            List of popular Intimidate users to watch for
        """
        return {
            "intimidate_pokemon": INTIMIDATE_POKEMON,
            "common_vgc_users": [
                {"name": "Incineroar", "note": "Most common - Fake Out + Parting Shot"},
                {"name": "Landorus-Therian", "note": "High stats, U-turn pivot"},
                {"name": "Arcanine", "note": "Bulky with good coverage"},
                {"name": "Hitmontop", "note": "Fake Out + Wide Guard"},
            ],
            "counters": {
                "blockers": [a.replace("-", " ").title() for a in INTIMIDATE_BLOCKERS[:6]],
                "punishers": [a.replace("-", " ").title() for a in INTIMIDATE_PUNISHERS]
            },
            "message": "Common Intimidate Pokemon to prepare for"
        }

    @mcp.tool()
    async def get_weather_ability_info() -> dict:
        """
        Get information about all weather-related abilities.

        Returns:
            Weather setters and abusers for each weather type
        """
        setters = {
            weather: ability.replace("-", " ").title()
            for ability, weather in WEATHER_SETTERS.items()
        }

        abusers = {
            weather: [a.replace("-", " ").title() for a in abilities]
            for weather, abilities in WEATHER_ABUSERS.items()
        }

        return {
            "weather_setters": setters,
            "weather_abusers": abusers,
            "notes": [
                "Weather lasts 5 turns (8 with Weather Rock items)",
                "Only one weather can be active at a time",
                "Stronger weather effects (Primal) override normal weather"
            ],
            "message": "Weather ability reference"
        }
