"""MCP tools for team management."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.champions_optimization import validate_sp_allocation
from vgc_mcp_core.calc.conversion import coerce_champions_allocation
from vgc_mcp_core.models.pokemon import (
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.rules.regulation_router import auto_detect_regulation
from vgc_mcp_core.team.analysis import TeamAnalyzer
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def _detect_champions(pokemon_name: str) -> bool:
    """Resolve session format, falling back to name-based inference.

    Returns True when the active regulation uses the Champions (Reg MA)
    Stat-Point system. Mainline behavior is unchanged.
    """
    cfg = get_regulation_config()
    try:
        auto_detect_regulation([pokemon_name], cfg)
    except Exception:
        pass
    return (cfg.get_format_system() or "mainline") == "champions"


def register_team_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    team_manager: TeamManager,
    analyzer: TeamAnalyzer
):
    """Register team management tools with the MCP server."""

    @mcp.tool(
        title="Add Pokemon to Team",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def add_to_team(
        pokemon_name: Annotated[str, Field(description="Name of the Pokemon to add (e.g. 'flutter-mane')", min_length=1)],
        nature: Annotated[str, Field(description="Pokemon's nature (e.g. 'adamant', 'timid')")] = "serious",
        ability: Annotated[Optional[str], Field(description="Pokemon's ability")] = None,
        item: Annotated[Optional[str], Field(description="Held item")] = None,
        tera_type: Annotated[Optional[str], Field(description="Tera type")] = None,
        move1: Annotated[Optional[str], Field(description="First move")] = None,
        move2: Annotated[Optional[str], Field(description="Second move")] = None,
        move3: Annotated[Optional[str], Field(description="Third move")] = None,
        move4: Annotated[Optional[str], Field(description="Fourth move")] = None,
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        atk_evs: Annotated[int, Field(ge=0, le=252, description="Attack EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        def_evs: Annotated[int, Field(ge=0, le=252, description="Defense EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        spa_evs: Annotated[int, Field(ge=0, le=252, description="Special Attack EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Special Defense EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        spe_evs: Annotated[int, Field(ge=0, le=252, description="Speed EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0
    ) -> dict:
        """Add a Pokemon to the current team (max 6, species clause enforced).

        Returns success/failure status and the current team state. In a
        Champions (Reg MA/MB) session the EV inputs are interpreted as Stat
        Points; when EV-scale values are auto-converted the response includes
        an `sp_conversion` note.
        """
        try:
            is_champions = _detect_champions(pokemon_name)
            sp_conversion_note = None

            # Validate stat investment against the active format's caps.
            if is_champions:
                alloc = {
                    "hp": hp_evs, "attack": atk_evs, "defense": def_evs,
                    "special_attack": spa_evs, "special_defense": spd_evs,
                    "speed": spe_evs,
                }
                # Users porting mainline sets often pass EV-scale numbers
                # (252 SpA, ...). Any stat > 32 is unambiguously EV-scale:
                # convert to SPs instead of failing the 32/stat cap.
                alloc, sp_conversion_note = coerce_champions_allocation(alloc)
                hp_evs, atk_evs, def_evs = alloc["hp"], alloc["attack"], alloc["defense"]
                spa_evs, spd_evs, spe_evs = (
                    alloc["special_attack"], alloc["special_defense"], alloc["speed"]
                )
                validation = validate_sp_allocation(alloc)
                if not validation["is_valid"]:
                    detail = (
                        "; ".join(validation["per_stat_violations"])
                        or f"Total Stat Points ({validation['total']}) exceed 66"
                    )
                    return error_response(ErrorCodes.INVALID_EVS, detail)
            else:
                total_evs = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
                if total_evs > 508:
                    return error_response(ErrorCodes.INVALID_EVS, f'Total EVs ({total_evs}) exceed 508')

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Parse nature
            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

            # Build moves list
            moves = [m for m in [move1, move2, move3, move4] if m]

            # Create Pokemon build (format-aware)
            if is_champions:
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=parsed_nature,
                    format_system="champions",
                    sps=StatPointSpread(
                        hp=hp_evs,
                        attack=atk_evs,
                        defense=def_evs,
                        special_attack=spa_evs,
                        special_defense=spd_evs,
                        speed=spe_evs
                    ),
                    ability=ability,
                    item=item,
                    tera_type=tera_type,
                    moves=moves
                )
            else:
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=parsed_nature,
                    evs=EVSpread(
                        hp=hp_evs,
                        attack=atk_evs,
                        defense=def_evs,
                        special_attack=spa_evs,
                        special_defense=spd_evs,
                        speed=spe_evs
                    ),
                    ability=ability,
                    item=item,
                    tera_type=tera_type,
                    moves=moves
                )

            success, message, data = team_manager.add_pokemon(pokemon)

            result = {
                "success": success,
                "message": message,
                **data
            }
            if sp_conversion_note:
                result["sp_conversion"] = sp_conversion_note
            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Remove Pokemon by Slot",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def remove_from_team(
        slot: Annotated[int, Field(ge=1, le=6, description="Slot number of the Pokemon to remove (1-6)")],
    ) -> dict:
        """Remove a Pokemon from the team by slot number.

        Returns success status and the updated team.
        """
        try:
            # Convert to 0-indexed
            success, message, data = team_manager.remove_pokemon(slot - 1)
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Remove Pokemon by Name",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def remove_pokemon_by_name(
        name: Annotated[str, Field(description="Name of the Pokemon to remove from the team", min_length=1)],
    ) -> dict:
        """Remove a Pokemon from the team by name.

        Returns success status and the updated team.
        """
        try:
            success, message, data = team_manager.remove_by_name(name)
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Replace Pokemon in Slot",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def swap_team_pokemon(
        slot: Annotated[int, Field(ge=1, le=6, description="Slot number to replace (1-6); the existing Pokemon in that slot is overwritten")],
        pokemon_name: Annotated[str, Field(description="New Pokemon's name", min_length=1)],
        nature: Annotated[str, Field(description="Pokemon's nature (e.g. 'adamant', 'timid')")] = "serious",
        ability: Annotated[Optional[str], Field(description="Pokemon's ability")] = None,
        item: Annotated[Optional[str], Field(description="Held item")] = None,
        tera_type: Annotated[Optional[str], Field(description="Tera type")] = None,
        move1: Annotated[Optional[str], Field(description="First move")] = None,
        move2: Annotated[Optional[str], Field(description="Second move")] = None,
        move3: Annotated[Optional[str], Field(description="Third move")] = None,
        move4: Annotated[Optional[str], Field(description="Fourth move")] = None,
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        atk_evs: Annotated[int, Field(ge=0, le=252, description="Attack EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        def_evs: Annotated[int, Field(ge=0, le=252, description="Defense EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        spa_evs: Annotated[int, Field(ge=0, le=252, description="Special Attack EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Special Defense EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0,
        spe_evs: Annotated[int, Field(ge=0, le=252, description="Speed EVs (0-252, total max 508); in Champions sessions treated as Stat Points (0-32, total max 66), EV-scale values (>32) auto-convert at 1 SP = 8 EVs")] = 0
    ) -> dict:
        """Replace the Pokemon in a specific team slot with a new one.

        Returns success status with the old and new Pokemon. In a Champions
        (Reg MA/MB) session the EV inputs are interpreted as Stat Points; when
        EV-scale values are auto-converted the response includes an
        `sp_conversion` note.
        """
        try:
            is_champions = _detect_champions(pokemon_name)
            sp_conversion_note = None

            # Validate stat investment against the active format's caps.
            if is_champions:
                alloc = {
                    "hp": hp_evs, "attack": atk_evs, "defense": def_evs,
                    "special_attack": spa_evs, "special_defense": spd_evs,
                    "speed": spe_evs,
                }
                # Users porting mainline sets often pass EV-scale numbers
                # (252 SpA, ...). Any stat > 32 is unambiguously EV-scale:
                # convert to SPs instead of failing the 32/stat cap.
                alloc, sp_conversion_note = coerce_champions_allocation(alloc)
                hp_evs, atk_evs, def_evs = alloc["hp"], alloc["attack"], alloc["defense"]
                spa_evs, spd_evs, spe_evs = (
                    alloc["special_attack"], alloc["special_defense"], alloc["speed"]
                )
                validation = validate_sp_allocation(alloc)
                if not validation["is_valid"]:
                    detail = (
                        "; ".join(validation["per_stat_violations"])
                        or f"Total Stat Points ({validation['total']}) exceed 66"
                    )
                    return error_response(ErrorCodes.INVALID_EVS, detail)
            else:
                total_evs = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
                if total_evs > 508:
                    return error_response(ErrorCodes.INVALID_EVS, f'Total EVs ({total_evs}) exceed 508')

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Parse nature
            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

            moves = [m for m in [move1, move2, move3, move4] if m]

            if is_champions:
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=parsed_nature,
                    format_system="champions",
                    sps=StatPointSpread(
                        hp=hp_evs,
                        attack=atk_evs,
                        defense=def_evs,
                        special_attack=spa_evs,
                        special_defense=spd_evs,
                        speed=spe_evs
                    ),
                    ability=ability,
                    item=item,
                    tera_type=tera_type,
                    moves=moves
                )
            else:
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=parsed_nature,
                    evs=EVSpread(
                        hp=hp_evs,
                        attack=atk_evs,
                        defense=def_evs,
                        special_attack=spa_evs,
                        special_defense=spd_evs,
                        speed=spe_evs
                    ),
                    ability=ability,
                    item=item,
                    tera_type=tera_type,
                    moves=moves
                )

            success, message, data = team_manager.swap_pokemon(slot - 1, pokemon)
            result = {"success": success, "message": message, **data}
            if sp_conversion_note:
                result["sp_conversion"] = sp_conversion_note
            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Reorder Team Slots",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=False,
        ),
    )
    async def reorder_team(
        slot1: Annotated[int, Field(ge=1, le=6, description="First slot number (1-6)")],
        slot2: Annotated[int, Field(ge=1, le=6, description="Second slot number (1-6)")],
    ) -> dict:
        """Swap the positions of two Pokemon in the team.

        Returns success status and the new team order.
        """
        try:
            success, message, data = team_manager.reorder(slot1 - 1, slot2 - 1)
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="View Current Team",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def view_team() -> dict:
        """View the current team with full details.

        Returns complete team information including all Pokemon builds.
        """
        try:
            result = team_manager.get_team_summary()
            return result
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Clear Team",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def clear_team() -> dict:
        """Clear all Pokemon from the current team.

        Returns confirmation that the team was cleared.
        """
        try:
            success, message, data = team_manager.clear()
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Analyze Current Team",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_team() -> dict:
        """Perform comprehensive analysis of the current team.

        Returns type weaknesses/resistances, offensive coverage, speed tiers,
        and role analysis. Requires at least one Pokemon on the team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team to analyze. Add Pokemon first.')

            return analyzer.get_summary(team_manager.team)
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

