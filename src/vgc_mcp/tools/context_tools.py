"""MCP tools for Pokemon context persistence.

This module allows users to store Pokemon builds for reference in
subsequent calculations. For example, after setting "my Entei" with
a specific spread, future queries can reference "my Entei" to use
that stored build automatically.
"""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.models.pokemon import EVSpread, Nature, PokemonBuild
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_context_tools(mcp: FastMCP, pokeapi, team_manager):
    """Register Pokemon context management tools with the MCP server."""

    @mcp.tool(
        title="Store My Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def set_my_pokemon(
        pokemon_name: Annotated[str, Field(description="Name of the Pokemon (e.g. 'Entei', 'Landorus-Therian')", min_length=1)],
        nature: Annotated[str, Field(description="Nature name (e.g. 'Adamant', 'Timid', 'Jolly')", min_length=1)],
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252)")] = 0,
        atk_evs: Annotated[int, Field(ge=0, le=252, description="Attack EVs (0-252)")] = 0,
        def_evs: Annotated[int, Field(ge=0, le=252, description="Defense EVs (0-252)")] = 0,
        spa_evs: Annotated[int, Field(ge=0, le=252, description="Special Attack EVs (0-252)")] = 0,
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Special Defense EVs (0-252)")] = 0,
        spe_evs: Annotated[int, Field(ge=0, le=252, description="Speed EVs (0-252)")] = 0,
        ability: Annotated[Optional[str], Field(description="Pokemon's ability (defaults to the Pokemon's first ability)")] = None,
        item: Annotated[Optional[str], Field(description="Held item")] = None,
        tera_type: Annotated[Optional[str], Field(description="Tera type")] = None
    ) -> dict:
        """Store a Pokemon spread for future calculations.

        After storing, you can reference this Pokemon as "my <pokemon>" in
        other tools (e.g. "my Entei", "my Landorus"). Returns a confirmation
        with the calculated final stats.
        """
        # Validate EVs
        total_evs = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
        if total_evs > 508:
            return error_response(ErrorCodes.INVALID_PARAMETER, f'Total EVs ({total_evs}) exceeds maximum of 508')

        # Validate nature
        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            valid_natures = [n.value.title() for n in Nature]
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}', valid_natures=valid_natures[:10])

        # Get Pokemon data from API
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
            abilities = await pokeapi.get_pokemon_abilities(pokemon_name)
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
        except Exception:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {pokemon_name}')

        if not pokemon_data:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f'Pokemon not found: {pokemon_name}')

        evs = EVSpread(
            hp=hp_evs,
            attack=atk_evs,
            defense=def_evs,
            special_attack=spa_evs,
            special_defense=spd_evs,
            speed=spe_evs
        )

        pokemon_build = PokemonBuild(
            name=pokemon_data["name"],
            base_stats=base_stats,
            types=types,
            nature=nature_enum,
            evs=evs,
            ability=ability or (abilities[0] if abilities else None),
            item=item,
            tera_type=tera_type,
            level=50
        )

        # Store in context
        success, message = team_manager.set_pokemon_context(pokemon_name, pokemon_build)

        # Calculate actual stats
        final_stats = calculate_all_stats(pokemon_build)

        return {
            "success": success,
            "message": message,
            "pokemon": pokemon_build.name,
            "reference": f"my {pokemon_build.name.lower()}",
            "nature": nature_enum.value.title(),
            "evs": {
                "hp": hp_evs,
                "attack": atk_evs,
                "defense": def_evs,
                "special_attack": spa_evs,
                "special_defense": spd_evs,
                "speed": spe_evs,
                "total": total_evs
            },
            "final_stats": final_stats,
            "ability": pokemon_build.ability,
            "item": item,
            "tera_type": tera_type,
            "usage": f"You can now use 'my {pokemon_build.name.lower()}' in other tools"
        }

    @mcp.tool(
        title="Get My Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_my_pokemon(
        reference: Annotated[Optional[str], Field(description="Reference name (e.g. 'my Entei', 'Entei'); omit for the most recently used Pokemon")] = None
    ) -> dict:
        """Get details of a stored Pokemon.

        Returns the stored Pokemon's full details with calculated stats, or
        the list of stored references if the requested one is not found.
        """
        pokemon = team_manager.get_pokemon_context(reference)

        if not pokemon:
            stored = team_manager.list_pokemon_context()
            if stored:
                return {
                    "found": False,
                    "message": f"No Pokemon found for '{reference}'" if reference else "No active Pokemon",
                    "stored_pokemon": [p["reference"] for p in stored]
                }
            return {
                "found": False,
                "message": "No Pokemon stored. Use set_my_pokemon to store one.",
                "stored_pokemon": []
            }

        # Calculate stats
        final_stats = calculate_all_stats(pokemon)

        return {
            "found": True,
            "name": pokemon.name,
            "types": pokemon.types,
            "nature": pokemon.nature.value.title(),
            "base_stats": {
                "hp": pokemon.base_stats.hp,
                "attack": pokemon.base_stats.attack,
                "defense": pokemon.base_stats.defense,
                "special_attack": pokemon.base_stats.special_attack,
                "special_defense": pokemon.base_stats.special_defense,
                "speed": pokemon.base_stats.speed
            },
            "evs": {
                "hp": pokemon.evs.hp,
                "attack": pokemon.evs.attack,
                "defense": pokemon.evs.defense,
                "special_attack": pokemon.evs.special_attack,
                "special_defense": pokemon.evs.special_defense,
                "speed": pokemon.evs.speed,
                "total": pokemon.evs.total
            },
            "final_stats": final_stats,
            "ability": pokemon.ability,
            "item": pokemon.item,
            "tera_type": pokemon.tera_type,
            "level": pokemon.level
        }

    @mcp.tool(
        title="List My Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_my_pokemon() -> dict:
        """List all stored Pokemon with their key stats (nature, Speed, HP)."""
        stored = team_manager.list_pokemon_context()

        if not stored:
            return {
                "count": 0,
                "message": "No Pokemon stored. Use set_my_pokemon to store one.",
                "pokemon": []
            }

        # Get base stats for each stored Pokemon
        pokemon_list = []
        for entry in stored:
            pokemon = team_manager.get_pokemon_context(entry["reference"])
            if pokemon:
                final_stats = calculate_all_stats(pokemon)
                pokemon_list.append({
                    "reference": entry["reference"],
                    "name": entry["name"],
                    "nature": entry["nature"],
                    "speed_stat": final_stats["speed"],
                    "hp_stat": final_stats["hp"],
                    "is_active": entry["is_active"]
                })

        return {
            "count": len(pokemon_list),
            "active": team_manager.active_pokemon_name,
            "pokemon": pokemon_list
        }

    @mcp.tool(
        title="Clear My Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def clear_my_pokemon(
        reference: Annotated[Optional[str], Field(description="Specific Pokemon to clear (e.g. 'my Entei'); omit to clear ALL stored Pokemon")] = None
    ) -> dict:
        """Clear stored Pokemon context.

        Returns a confirmation and the count of remaining stored Pokemon.
        """
        success, message = team_manager.clear_pokemon_context(reference)

        return {
            "success": success,
            "message": message,
            "remaining": len(team_manager.list_pokemon_context())
        }

    @mcp.tool(
        title="Update My Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def update_my_pokemon(
        reference: Annotated[str, Field(description="Reference name (e.g. 'my Entei', 'Entei')", min_length=1)],
        nature: Annotated[Optional[str], Field(description="New nature (if changing)")] = None,
        hp_evs: Annotated[Optional[int], Field(ge=0, le=252, description="New HP EVs (if changing)")] = None,
        atk_evs: Annotated[Optional[int], Field(ge=0, le=252, description="New Attack EVs (if changing)")] = None,
        def_evs: Annotated[Optional[int], Field(ge=0, le=252, description="New Defense EVs (if changing)")] = None,
        spa_evs: Annotated[Optional[int], Field(ge=0, le=252, description="New Special Attack EVs (if changing)")] = None,
        spd_evs: Annotated[Optional[int], Field(ge=0, le=252, description="New Special Defense EVs (if changing)")] = None,
        spe_evs: Annotated[Optional[int], Field(ge=0, le=252, description="New Speed EVs (if changing)")] = None,
        ability: Annotated[Optional[str], Field(description="New ability (if changing)")] = None,
        item: Annotated[Optional[str], Field(description="New item (if changing)")] = None,
        tera_type: Annotated[Optional[str], Field(description="New tera type (if changing)")] = None
    ) -> dict:
        """Update an existing stored Pokemon's spread or attributes.

        Only updates the specified parameters, keeping others unchanged.
        Returns the updated Pokemon details with recalculated stats.
        """
        pokemon = team_manager.get_pokemon_context(reference)

        if not pokemon:
            return error_response(ErrorCodes.INTERNAL_ERROR, f"No Pokemon found for '{reference}'", stored_pokemon=[p['reference'] for p in team_manager.list_pokemon_context()])

        # Update nature if provided
        if nature:
            try:
                pokemon.nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

        # Update EVs if provided
        new_evs = {
            "hp": hp_evs if hp_evs is not None else pokemon.evs.hp,
            "attack": atk_evs if atk_evs is not None else pokemon.evs.attack,
            "defense": def_evs if def_evs is not None else pokemon.evs.defense,
            "special_attack": spa_evs if spa_evs is not None else pokemon.evs.special_attack,
            "special_defense": spd_evs if spd_evs is not None else pokemon.evs.special_defense,
            "speed": spe_evs if spe_evs is not None else pokemon.evs.speed
        }

        total = sum(new_evs.values())
        if total > 508:
            return error_response(ErrorCodes.INVALID_PARAMETER, f'Total EVs ({total}) exceeds maximum of 508')

        pokemon.evs = EVSpread(**new_evs)

        # Update other attributes
        if ability is not None:
            pokemon.ability = ability
        if item is not None:
            pokemon.item = item
        if tera_type is not None:
            pokemon.tera_type = tera_type

        # Calculate updated stats
        final_stats = calculate_all_stats(pokemon)

        return {
            "success": True,
            "message": f"Updated {pokemon.name}",
            "pokemon": pokemon.name,
            "nature": pokemon.nature.value.title(),
            "evs": new_evs,
            "ev_total": total,
            "final_stats": final_stats,
            "ability": pokemon.ability,
            "item": pokemon.item,
            "tera_type": pokemon.tera_type
        }

    @mcp.tool(
        title="Reset Session",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def reset_session() -> dict:
        """Start fresh by clearing all stored Pokemon and team data.

        Clears all stored "my Pokemon" builds, the current team, and any
        active Pokemon reference. Use when starting a new teambuilding
        session, clearing old data from a previous conversation, or switching
        between team projects. Returns a confirmation of what was cleared.
        """
        # Get counts before clearing for user feedback
        stored_count = len(team_manager.list_pokemon_context())
        team_size = team_manager.size

        # Clear Pokemon context
        team_manager.clear_pokemon_context(None)  # None clears all

        # Clear the team
        team_manager.clear()  # Returns (success, message, data)

        return {
            "success": True,
            "message": "Session reset complete - ready for a fresh start!",
            "cleared": {
                "stored_pokemon": f"{stored_count} Pokemon cleared" if stored_count > 0 else "None (was empty)",
                "team": f"{team_size} Pokemon cleared" if team_size > 0 else "None (was empty)"
            },
            "next_steps": [
                "Use 'set_my_pokemon' to store a Pokemon spread for analysis",
                "Use 'add_to_team' to start building a team",
                "Use 'import_showdown_paste' to import from Pokemon Showdown"
            ]
        }

    @mcp.tool(
        title="Get Session Status",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def session_status() -> dict:
        """Check what's currently stored in this session.

        Shows all stored "my Pokemon" builds, the current team composition,
        and whether there's leftover data from a previous conversation
        (useful at the start of a conversation).
        """
        stored_pokemon = team_manager.list_pokemon_context()
        team = team_manager.get_current_team()

        # Build Pokemon summary
        pokemon_summary = []
        for entry in stored_pokemon:
            pokemon = team_manager.get_pokemon_context(entry["reference"])
            if pokemon:
                final_stats = calculate_all_stats(pokemon)
                pokemon_summary.append({
                    "reference": f"my {entry['reference']}",
                    "pokemon": entry["name"],
                    "nature": entry["nature"].title(),
                    "speed": final_stats["speed"],
                    "hp": final_stats["hp"]
                })

        # Build team summary
        team_summary = []
        if team:
            for slot in team.slots:
                team_summary.append({
                    "slot": slot.position,
                    "pokemon": slot.pokemon.name,
                    "item": slot.pokemon.item or "None"
                })

        has_existing_data = len(pokemon_summary) > 0 or len(team_summary) > 0

        result = {
            "has_existing_data": has_existing_data,
            "stored_pokemon": {
                "count": len(pokemon_summary),
                "pokemon": pokemon_summary
            },
            "team": {
                "size": len(team_summary),
                "pokemon": team_summary
            }
        }

        # Add contextual message for users
        if has_existing_data:
            result["note"] = (
                "There's existing data from a previous session. "
                "Use 'reset_session' if you want to start fresh, "
                "or continue working with the current data."
            )
        else:
            result["note"] = (
                "Session is empty - ready to start! "
                "Use 'set_my_pokemon' to store a Pokemon, or 'add_to_team' to build a team."
            )

        return result
