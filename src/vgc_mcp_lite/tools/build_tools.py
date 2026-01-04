# -*- coding: utf-8 -*-
"""MCP tools for build state management.

These tools enable bidirectional state sync between UI cards and chat:
- Create/modify builds via chat commands
- Sync UI state back to server
- Reference builds by Pokemon name (natural language)
"""

from typing import Optional, Any
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.state import BuildStateManager
from ..ui.components import create_pokemon_build_card_ui
from ..ui.resources import add_ui_metadata

# MCP-UI support
HAS_UI = True


def register_build_tools(
    mcp: FastMCP,
    build_manager: BuildStateManager,
    pokeapi: PokeAPIClient
):
    """Register build state management tools with the MCP server."""

    @mcp.tool()
    async def create_build_card(
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
        Create an interactive Pokemon build card with state tracking.

        The card supports:
        - EV sliders with wasted EV detection
        - Nature/ability/item/tera dropdowns
        - Move selection
        - Speed tier comparison
        - Auto-save for bidirectional sync

        Args:
            pokemon_name: Name of the Pokemon
            nature: Pokemon's nature
            ability: Selected ability
            item: Held item
            tera_type: Tera type
            move1-move4: The four moves
            hp_evs through spe_evs: EV spread

        Returns:
            Build card UI with state tracking enabled
        """
        try:
            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
            abilities = await pokeapi.get_abilities(pokemon_name)
            all_moves = await pokeapi.get_moves(pokemon_name)

            # Build moves list
            moves = [m for m in [move1, move2, move3, move4] if m]

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
                "evs": {
                    "hp": hp_evs,
                    "attack": atk_evs,
                    "defense": def_evs,
                    "special_attack": spa_evs,
                    "special_defense": spd_evs,
                    "speed": spe_evs,
                },
                "nature": nature,
                "ability": ability or (abilities[0] if abilities else None),
                "item": item,
                "tera_type": tera_type or (types[0] if types else None),
                "moves": moves,
                "abilities": abilities,
                "all_moves": all_moves[:50],  # Limit for UI
            }

            # Register build with state manager
            build_id = build_manager.create_build(pokemon_data)

            # Generate UI card
            html = create_pokemon_build_card_ui(
                pokemon_name=pokemon_name,
                base_stats=pokemon_data["base_stats"],
                types=types,
                abilities=abilities,
                moves=all_moves[:50],
                initial_evs=pokemon_data["evs"],
                initial_nature=nature,
                initial_ability=pokemon_data["ability"],
                initial_item=item,
                initial_tera=pokemon_data["tera_type"],
                initial_moves=moves if moves else all_moves[:4],
                build_id=build_id,
            )

            result = {
                "success": True,
                "message": f"Created build card for {pokemon_name}",
                "pokemon": pokemon_name,
                "build_id": build_id,
            }

            # Add UI metadata
            return add_ui_metadata(
                result,
                {"uri": f"ui://vgc/build/{pokemon_name.lower()}", "content": {"type": "rawHtml", "htmlString": html}},
                display_type="inline",
                name="Pokemon Build"
            )

        except Exception as e:
            return {"success": False, "error": str(e)}

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
        spe_evs: Optional[int] = None,
        ui_state: Optional[dict] = None
    ) -> dict:
        """
        Modify an existing Pokemon build and return updated card.

        Can be called with just the changes you want to make.
        If ui_state is provided (from auto-save), it will be merged first.

        Args:
            pokemon_name: Name of Pokemon to modify
            nature: New nature (if changing)
            ability: New ability (if changing)
            item: New item (if changing)
            tera_type: New tera type (if changing)
            hp_evs through spe_evs: New EVs (if changing)
            ui_state: Serialized state from UI auto-save (for sync)

        Returns:
            Updated build card UI
        """
        try:
            # Find build by name
            build = build_manager.get_build_by_name(pokemon_name)
            if not build:
                return {"success": False, "error": f"No build found for '{pokemon_name}'"}

            build_id = build["build_id"]

            # Sync UI state first if provided
            if ui_state:
                build_manager.sync_from_ui(build_id, ui_state)
                build = build_manager.get_build(build_id)

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

            # EV changes
            ev_changes = {}
            if hp_evs is not None:
                ev_changes["hp"] = hp_evs
            if atk_evs is not None:
                ev_changes["attack"] = atk_evs
            if def_evs is not None:
                ev_changes["defense"] = def_evs
            if spa_evs is not None:
                ev_changes["special_attack"] = spa_evs
            if spd_evs is not None:
                ev_changes["special_defense"] = spd_evs
            if spe_evs is not None:
                ev_changes["speed"] = spe_evs

            if ev_changes:
                changes["evs"] = ev_changes

            if changes:
                build_manager.update_build(build_id, changes)
                build = build_manager.get_build(build_id)

            # Re-render card with current state
            html = create_pokemon_build_card_ui(
                pokemon_name=build["pokemon"],
                base_stats=build["base_stats"],
                types=build["types"],
                abilities=build.get("abilities", []),
                moves=build.get("all_moves", []),
                initial_evs=build["evs"],
                initial_nature=build["nature"],
                initial_ability=build["ability"],
                initial_item=build["item"],
                initial_tera=build["tera_type"],
                initial_moves=build["moves"],
                build_id=build_id,
            )

            result = {
                "success": True,
                "message": f"Updated {build['pokemon']}",
                "changes": list(changes.keys()) if changes else ["synced from UI"],
                "build_id": build_id,
            }

            return add_ui_metadata(
                result,
                {"uri": f"ui://vgc/build/{build['pokemon'].lower()}", "content": {"type": "rawHtml", "htmlString": html}},
                display_type="inline",
                name="Pokemon Build"
            )

        except Exception as e:
            return {"success": False, "error": str(e)}

    @mcp.tool()
    async def change_move(
        pokemon_name: str,
        old_move: str,
        new_move: str,
        ui_state: Optional[dict] = None
    ) -> dict:
        """
        Change a specific move on a Pokemon build.

        User-friendly wrapper for modifying moves. Finds the old move
        and replaces it with the new one.

        Args:
            pokemon_name: Name of Pokemon to modify
            old_move: Move to replace
            new_move: New move to use
            ui_state: Serialized state from UI auto-save (for sync)

        Returns:
            Updated build card UI
        """
        try:
            build = build_manager.get_build_by_name(pokemon_name)
            if not build:
                return {"success": False, "error": f"No build found for '{pokemon_name}'"}

            build_id = build["build_id"]

            # Sync UI state first if provided
            if ui_state:
                build_manager.sync_from_ui(build_id, ui_state)
                build = build_manager.get_build(build_id)

            # Change the move
            success, message = build_manager.change_move(build_id, old_move, new_move)
            if not success:
                return {"success": False, "error": message}

            # Get updated build
            build = build_manager.get_build(build_id)

            # Re-render card
            html = create_pokemon_build_card_ui(
                pokemon_name=build["pokemon"],
                base_stats=build["base_stats"],
                types=build["types"],
                abilities=build.get("abilities", []),
                moves=build.get("all_moves", []),
                initial_evs=build["evs"],
                initial_nature=build["nature"],
                initial_ability=build["ability"],
                initial_item=build["item"],
                initial_tera=build["tera_type"],
                initial_moves=build["moves"],
                build_id=build_id,
            )

            result = {
                "success": True,
                "message": message,
                "build_id": build_id,
            }

            return add_ui_metadata(
                result,
                {"uri": f"ui://vgc/build/{build['pokemon'].lower()}", "content": {"type": "rawHtml", "htmlString": html}},
                display_type="inline",
                name="Pokemon Build"
            )

        except Exception as e:
            return {"success": False, "error": str(e)}

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
            return {"success": False, "error": f"No build found for '{pokemon_name}'"}

        return {
            "success": True,
            "build": {
                "pokemon": build["pokemon"],
                "nature": build["nature"],
                "ability": build["ability"],
                "item": build["item"],
                "tera_type": build["tera_type"],
                "evs": build["evs"],
                "moves": build["moves"],
            },
        }
