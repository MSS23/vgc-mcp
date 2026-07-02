# -*- coding: utf-8 -*-
"""MCP tools for build state management.

These tools enable state management for Pokemon builds:
- Create/modify builds via chat commands
- Reference builds by Pokemon name (natural language)
- Returns JSON state (rendered as tables by the agent per presentation rules)
"""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.champions_optimization import validate_sp_allocation
from vgc_mcp_core.calc.conversion import coerce_champions_allocation
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.rules.regulation_router import auto_detect_regulation
from vgc_mcp_core.state import BuildStateManager
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


def register_build_tools(
    mcp: FastMCP,
    build_manager: BuildStateManager,
    pokeapi: PokeAPIClient
):
    """Register build state management tools with the MCP server.

    This is the non-UI version that returns JSON state instead of HTML cards.
    """

    @mcp.tool()
    async def create_build(
        pokemon_name: str,
        nature: str = "Serious",
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
        Create a Pokemon build with state tracking.

        Args:
            pokemon_name: Name of the Pokemon
            nature: Pokemon's nature
            ability: Selected ability
            item: Held item
            tera_type: Tera type
            move1-move4: The four moves
            hp_evs through spe_evs: EV spread

        Returns:
            Build state with build_id for future reference
        """
        try:
            is_champions = _detect_champions(pokemon_name)

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
            abilities = await pokeapi.get_pokemon_abilities(pokemon_name)

            # Build moves list
            moves = [m for m in [move1, move2, move3, move4] if m]

            # Stat investment dict (interpreted as EVs or SPs by format)
            stat_invest = {
                "hp": hp_evs,
                "attack": atk_evs,
                "defense": def_evs,
                "special_attack": spa_evs,
                "special_defense": spd_evs,
                "speed": spe_evs,
            }

            # Create build data
            pokemon_data = {
                "name": pokemon_name,
                "base_stats": {
                    "hp": base_stats.hp,
                    "attack": base_stats.attack,
                    "defense": base_stats.defense,
                    "special_attack": base_stats.special_attack,
                    "special_defense": base_stats.special_defense,
                    "speed": base_stats.speed,
                },
                "types": types,
                "nature": nature,
                "ability": ability or (abilities[0] if abilities else None),
                "item": item,
                "tera_type": tera_type or (types[0] if types else None),
                "moves": moves,
                "abilities": abilities,
            }

            sp_conversion_note = None
            if is_champions:
                # EV-scale numbers (any stat > 32) are auto-converted to SPs.
                stat_invest, sp_conversion_note = coerce_champions_allocation(stat_invest)
                validation = validate_sp_allocation(stat_invest)
                if not validation["is_valid"]:
                    detail = (
                        "; ".join(validation["per_stat_violations"])
                        or f"Total Stat Points ({validation['total']}) exceed 66"
                    )
                    return error_response(ErrorCodes.INVALID_EVS, detail)
                pokemon_data["format_system"] = "champions"
                pokemon_data["sps"] = stat_invest
            else:
                total_evs = sum(stat_invest.values())
                if total_evs > 508:
                    return error_response(ErrorCodes.INVALID_EVS, f'Total EVs ({total_evs}) exceed 508')
                pokemon_data["evs"] = stat_invest

            # Register build with state manager
            build_id = build_manager.create_build(pokemon_data)

            build_payload = {
                "pokemon": pokemon_name,
                "types": types,
                "nature": nature,
                "ability": pokemon_data["ability"],
                "item": item,
                "tera_type": pokemon_data["tera_type"],
                "moves": moves,
            }
            if is_champions:
                build_payload["format_system"] = "champions"
                build_payload["sps"] = stat_invest
            else:
                build_payload["evs"] = stat_invest

            result = {
                "success": True,
                "message": f"Created build for {pokemon_name}",
                "build_id": build_id,
                "build": build_payload,
            }
            if sp_conversion_note:
                result["sp_conversion"] = sp_conversion_note
            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def modify_build(
        pokemon_name: str,
        nature: Optional[str] = None,
        ability: Optional[str] = None,
        item: Optional[str] = None,
        tera_type: Optional[str] = None,
        hp_evs: Optional[int] = None,
        atk_evs: Optional[int] = None,
        def_evs: Optional[int] = None,
        spa_evs: Optional[int] = None,
        spd_evs: Optional[int] = None,
        spe_evs: Optional[int] = None
    ) -> dict:
        """
        Modify an existing Pokemon build.

        Can be called with just the changes you want to make.

        Args:
            pokemon_name: Name of Pokemon to modify
            nature: New nature (if changing)
            ability: New ability (if changing)
            item: New item (if changing)
            tera_type: New tera type (if changing)
            hp_evs through spe_evs: New EVs (if changing). In a Champions
                session these are Stat Points; EV-scale values (any stat > 32)
                are auto-converted (1 SP = 8 EVs).

        Returns:
            Updated build state
        """
        try:
            sp_conversion_note = None

            # Find build by name
            build = build_manager.get_build_by_name(pokemon_name)
            if not build:
                return error_response(ErrorCodes.INTERNAL_ERROR, f"No build found for '{pokemon_name}'")

            build_id = build["build_id"]
            is_champions = build.get("format_system") == "champions"

            # Apply requested changes
            changes = {}
            if nature is not None:
                changes["nature"] = nature
            if ability is not None:
                changes["ability"] = ability
            if item is not None:
                changes["item"] = item
            if tera_type is not None:
                changes["tera_type"] = tera_type

            # Stat changes (interpreted as EVs or SPs by the stored format)
            stat_changes = {}
            if hp_evs is not None:
                stat_changes["hp"] = hp_evs
            if atk_evs is not None:
                stat_changes["attack"] = atk_evs
            if def_evs is not None:
                stat_changes["defense"] = def_evs
            if spa_evs is not None:
                stat_changes["special_attack"] = spa_evs
            if spd_evs is not None:
                stat_changes["special_defense"] = spd_evs
            if spe_evs is not None:
                stat_changes["speed"] = spe_evs

            if stat_changes:
                if is_champions:
                    # EV-scale edits (any stat > 32) convert to SPs first, so
                    # they merge with existing SP values on the same scale.
                    coerced, sp_conversion_note = coerce_champions_allocation(stat_changes)
                    if sp_conversion_note:
                        stat_changes = {
                            k: v for k, v in coerced.items() if k in stat_changes
                        }
                    # Validate the merged SP allocation against 32/66.
                    merged = dict(build.get("sps", {}))
                    merged.update(stat_changes)
                    validation = validate_sp_allocation(merged)
                    if not validation["is_valid"]:
                        detail = (
                            "; ".join(validation["per_stat_violations"])
                            or f"Total Stat Points ({validation['total']}) exceed 66"
                        )
                        return error_response(ErrorCodes.INVALID_EVS, detail)
                    changes["sps"] = stat_changes
                else:
                    changes["evs"] = stat_changes

            if changes:
                build_manager.update_build(build_id, changes)
                build = build_manager.get_build(build_id)

            build_payload = {
                "pokemon": build["pokemon"],
                "nature": build["nature"],
                "ability": build["ability"],
                "item": build["item"],
                "tera_type": build["tera_type"],
                "moves": build["moves"],
            }
            if is_champions:
                build_payload["format_system"] = "champions"
                build_payload["sps"] = build.get("sps", {})
            else:
                build_payload["evs"] = build["evs"]

            result = {
                "success": True,
                "message": f"Updated {build['pokemon']}",
                "changes": list(changes.keys()) if changes else [],
                "build_id": build_id,
                "build": build_payload,
            }
            if sp_conversion_note:
                result["sp_conversion"] = sp_conversion_note
            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def change_move(
        pokemon_name: str,
        old_move: str,
        new_move: str
    ) -> dict:
        """
        Change a specific move on a Pokemon build.

        User-friendly wrapper for modifying moves. Finds the old move
        and replaces it with the new one.

        Args:
            pokemon_name: Name of Pokemon to modify
            old_move: Move to replace
            new_move: New move to use

        Returns:
            Updated build state
        """
        try:
            build = build_manager.get_build_by_name(pokemon_name)
            if not build:
                return error_response(ErrorCodes.INTERNAL_ERROR, f"No build found for '{pokemon_name}'")

            build_id = build["build_id"]

            # Change the move
            success, message = build_manager.change_move(build_id, old_move, new_move)
            if not success:
                return error_response(ErrorCodes.INTERNAL_ERROR, message)

            # Get updated build
            build = build_manager.get_build(build_id)

            return {
                "success": True,
                "message": message,
                "build_id": build_id,
                "moves": build["moves"],
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def list_builds() -> dict:
        """
        List all active Pokemon builds in the current session.

        Returns:
            List of builds with pokemon name, item, and nature
        """
        builds = build_manager.list_builds()
        active = build_manager.active_pokemon_name

        return {
            "success": True,
            "builds": builds,
            "active_pokemon": active,
            "count": len(builds),
        }

    @mcp.tool()
    async def get_build_state(pokemon_name: str) -> dict:
        """
        Get the current state of a Pokemon build.

        Useful for debugging or exporting build details.

        Args:
            pokemon_name: Name of Pokemon to get

        Returns:
            Full build state including EVs, nature, moves, etc.
        """
        build = build_manager.get_build_by_name(pokemon_name)
        if not build:
            return error_response(ErrorCodes.INTERNAL_ERROR, f"No build found for '{pokemon_name}'")

        build_payload = {
            "pokemon": build["pokemon"],
            "nature": build["nature"],
            "ability": build["ability"],
            "item": build["item"],
            "tera_type": build["tera_type"],
            "moves": build["moves"],
        }
        if build.get("format_system") == "champions":
            build_payload["format_system"] = "champions"
            build_payload["sps"] = build.get("sps", {})
        else:
            build_payload["evs"] = build["evs"]

        return {
            "success": True,
            "build": build_payload,
        }
