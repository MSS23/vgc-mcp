"""MCP tools for team management."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.team.analysis import TeamAnalyzer
from vgc_mcp_core.models.pokemon import (
    PokemonBuild, Nature, EVSpread, IVSpread, StatPointSpread,
)
from vgc_mcp_core.utils.errors import error_response, ErrorCodes
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.rules.regulation_router import auto_detect_regulation
from vgc_mcp_core.calc.champions_optimization import validate_sp_allocation


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

    @mcp.tool()
    async def add_to_team(
        pokemon_name: str,
        nature: str = "serious",
        ability: Optional[str] = None,
        item: Optional[str] = None,
        tera_type: Optional[str] = None,
        move1: Optional[str] = None,
        move2: Optional[str] = None,
        move3: Optional[str] = None,
        move4: Optional[str] = None,
        hp_evs: int = 0,
        atk_evs: int = 0,
        def_evs: int = 0,
        spa_evs: int = 0,
        spd_evs: int = 0,
        spe_evs: int = 0
    ) -> dict:
        """
        Add a Pokemon to the current team (max 6, species clause enforced).

        Args:
            pokemon_name: Name of the Pokemon to add
            nature: Pokemon's nature (e.g., "adamant", "timid")
            ability: Pokemon's ability
            item: Held item
            tera_type: Tera type
            move1, move2, move3, move4: The four moves
            hp_evs through spe_evs: stat investment. Mainline interprets these as
                EVs (total max 508, 252/stat). In a Champions (Reg MA) session
                they are interpreted as Stat Points (total max 66, 32/stat).

        Returns:
            Success/failure status and current team state
        """
        try:
            is_champions = _detect_champions(pokemon_name)

            # Validate stat investment against the active format's caps.
            if is_champions:
                alloc = {
                    "hp": hp_evs, "attack": atk_evs, "defense": def_evs,
                    "special_attack": spa_evs, "special_defense": spd_evs,
                    "speed": spe_evs,
                }
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

            return {
                "success": success,
                "message": message,
                **data
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def remove_from_team(slot: int) -> dict:
        """
        Remove a Pokemon from the team by slot number.

        Args:
            slot: Slot number (1-6)

        Returns:
            Success status and updated team
        """
        try:
            # Convert to 0-indexed
            success, message, data = team_manager.remove_pokemon(slot - 1)
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def remove_pokemon_by_name(name: str) -> dict:
        """
        Remove a Pokemon from the team by name.

        Args:
            name: Pokemon name to remove

        Returns:
            Success status and updated team
        """
        try:
            success, message, data = team_manager.remove_by_name(name)
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def swap_team_pokemon(
        slot: int,
        pokemon_name: str,
        nature: str = "serious",
        ability: Optional[str] = None,
        item: Optional[str] = None,
        tera_type: Optional[str] = None,
        move1: Optional[str] = None,
        move2: Optional[str] = None,
        move3: Optional[str] = None,
        move4: Optional[str] = None,
        hp_evs: int = 0,
        atk_evs: int = 0,
        def_evs: int = 0,
        spa_evs: int = 0,
        spd_evs: int = 0,
        spe_evs: int = 0
    ) -> dict:
        """
        Replace a Pokemon in a specific slot with a new one.

        Args:
            slot: Slot number to replace (1-6)
            pokemon_name: New Pokemon's name
            (other args same as add_to_team)

        Returns:
            Success status with old and new Pokemon
        """
        try:
            is_champions = _detect_champions(pokemon_name)

            # Validate stat investment against the active format's caps.
            if is_champions:
                alloc = {
                    "hp": hp_evs, "attack": atk_evs, "defense": def_evs,
                    "special_attack": spa_evs, "special_defense": spd_evs,
                    "speed": spe_evs,
                }
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
            return {"success": success, "message": message, **data}

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def reorder_team(slot1: int, slot2: int) -> dict:
        """
        Swap the positions of two Pokemon in the team.

        Args:
            slot1: First slot number (1-6)
            slot2: Second slot number (1-6)

        Returns:
            Success status and new team order
        """
        try:
            success, message, data = team_manager.reorder(slot1 - 1, slot2 - 1)
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def view_team() -> dict:
        """
        View the current team with full details.

        Returns:
            Complete team information including all Pokemon builds
        """
        try:
            result = team_manager.get_team_summary()
            return result
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def clear_team() -> dict:
        """
        Clear all Pokemon from the current team.

        Returns:
            Confirmation of team cleared
        """
        try:
            success, message, data = team_manager.clear()
            return {"success": success, "message": message, **data}
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def analyze_team() -> dict:
        """
        Perform comprehensive analysis of the current team.

        Returns:
            Type weaknesses/resistances, offensive coverage, speed tiers, and role analysis
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, 'No Pokemon on team to analyze. Add Pokemon first.')

            return analyzer.get_summary(team_manager.team)
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

