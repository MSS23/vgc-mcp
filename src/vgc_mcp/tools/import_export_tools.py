"""MCP tools for importing/exporting Pokemon Showdown format."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.formats.showdown import (
    ShowdownParseError,
    parse_showdown_pokemon,
    parse_showdown_team,
    parsed_to_pokemon_build,
    pokemon_build_to_showdown,
)
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_import_export_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    team_manager: TeamManager
):
    """Register import/export tools with the MCP server."""

    @mcp.tool(
        title="Import Showdown Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def import_showdown_pokemon(
        paste: Annotated[str, Field(
            description=(
                "Showdown paste text for one Pokemon, e.g. "
                "'Urshifu-Rapid-Strike @ Choice Scarf\\nAbility: Unseen Fist\\nLevel: 50\\n"
                "Tera Type: Water\\nEVs: 4 HP / 252 Atk / 252 Spe\\nJolly Nature\\n"
                "- Surging Strikes\\n- Close Combat'. An 'SPs:' line imports as a "
                "Champions (Reg MA) build instead of a mainline EV build."
            ),
            min_length=1,
        )],
        add_to_team: Annotated[bool, Field(
            description="If True (default), also add the parsed Pokemon to the current team",
        )] = True,
    ) -> dict:
        """Parse a single Pokemon from Showdown paste format and optionally add it to the team.

        Returns the parsed build data, types, auto-detected regulation info, and
        team status when added.
        """
        try:
            parsed = parse_showdown_pokemon(paste)

            # Normalize species name for API
            species_name = parsed.species.lower().replace(" ", "-")

            # Fetch base stats from API
            try:
                base_stats = await pokeapi.get_base_stats(species_name)
                types = await pokeapi.get_pokemon_types(species_name)
            except Exception as e:
                return error_response(ErrorCodes.API_ERROR, f'Could not fetch Pokemon data: {e}', parsed={'species': parsed.species, 'nickname': parsed.nickname})

            result = {
                "success": True,
                "parsed": {
                    "species": parsed.species,
                    "nickname": parsed.nickname,
                    "item": parsed.item,
                    "ability": parsed.ability,
                    "level": parsed.level,
                    "tera_type": parsed.tera_type,
                    "nature": parsed.nature,
                    "evs": parsed.evs,
                    "sps": parsed.sps,
                    "ivs": parsed.ivs,
                    "moves": parsed.moves,
                    "shiny": parsed.shiny,
                    "gender": parsed.gender,
                },
                "types": types
            }

            # Zero-config regulation detection from the imported species.
            try:
                from vgc_mcp_core.rules.regulation_loader import get_regulation_config
                from vgc_mcp_core.rules.regulation_router import auto_detect_regulation
                detection = auto_detect_regulation([parsed.species], get_regulation_config())
                result["regulation_auto_detected"] = detection
            except Exception:
                pass

            if add_to_team:
                # Build a FORMAT-AWARE PokemonBuild: SPs paste -> champions+sps,
                # EVs paste -> mainline+evs.
                try:
                    pokemon = parsed_to_pokemon_build(
                        parsed,
                        base_stats,
                        types,
                        extra_kwargs={"name": species_name},
                    )
                except ShowdownParseError as e:
                    return error_response(ErrorCodes.PARSE_ERROR, str(e))

                success, message, data = team_manager.add_pokemon(pokemon)
                result["team"] = {
                    "added": success,
                    "message": message,
                    "team_size": data.get("team_size", team_manager.size)
                }

            return result

        except ShowdownParseError as e:
            return error_response(ErrorCodes.PARSE_ERROR, str(e))
        except Exception as e:
            return error_response(ErrorCodes.UNKNOWN_ERROR, str(e))

    @mcp.tool(
        title="Import Showdown Team",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def import_showdown_team(
        paste: Annotated[str, Field(
            description="Full team Showdown paste; Pokemon separated by blank lines (up to 6 imported)",
            min_length=1,
        )],
        clear_existing: Annotated[bool, Field(
            description="If True, clear the current team before importing (default keeps existing Pokemon)",
        )] = False,
    ) -> dict:
        """Parse a full team from Showdown paste format and add each Pokemon to the team.

        Returns per-Pokemon import results, final team roster, and auto-detected
        regulation info.
        """
        try:
            if clear_existing:
                team_manager.clear()

            parsed_team = parse_showdown_team(paste)

            if not parsed_team:
                return error_response(ErrorCodes.PARSE_ERROR, 'No Pokemon found in paste')

            results = []
            added_count = 0
            failed_count = 0

            for parsed in parsed_team:
                species_name = parsed.species.lower().replace(" ", "-")

                try:
                    base_stats = await pokeapi.get_base_stats(species_name)
                    types = await pokeapi.get_pokemon_types(species_name)

                    # Format-aware: SPs paste -> champions+sps, EVs -> mainline+evs.
                    pokemon = parsed_to_pokemon_build(
                        parsed,
                        base_stats,
                        types,
                        extra_kwargs={"name": species_name},
                    )

                    success, message, _ = team_manager.add_pokemon(pokemon)

                    results.append({
                        "species": parsed.species,
                        "added": success,
                        "message": message if not success else "Added"
                    })

                    if success:
                        added_count += 1
                    else:
                        failed_count += 1

                except Exception as e:
                    results.append({
                        "species": parsed.species,
                        "added": False,
                        "message": f"Error: {e}"
                    })
                    failed_count += 1

            response = {
                "success": added_count > 0,
                "imported_count": added_count,
                "failed_count": failed_count,
                "results": results,
                "team_size": team_manager.size,
                "team": team_manager.team.get_pokemon_names()
            }

            # Zero-config regulation detection from imported species.
            try:
                from vgc_mcp_core.rules.regulation_loader import get_regulation_config
                from vgc_mcp_core.rules.regulation_router import auto_detect_regulation
                names = [p.species for p in parsed_team]
                response["regulation_auto_detected"] = auto_detect_regulation(
                    names, get_regulation_config()
                )
            except Exception:
                pass

            return response

        except Exception as e:
            return error_response(ErrorCodes.UNKNOWN_ERROR, str(e))

    @mcp.tool(
        title="Export Team to Showdown Paste",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def export_team_to_paste() -> dict:
        """Export the current team to Showdown paste format.

        Returns paste text ready to import into Pokemon Showdown's teambuilder
        (Champions builds emit 'SPs:' lines automatically).
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.EMPTY_TEAM, 'No Pokemon on team to export')

            # Delegate per-slot to the format-aware exporter (emits 'SPs:' for
            # champions builds and hyphenated Showdown species).
            paste = "\n\n".join(
                pokemon_build_to_showdown(slot.pokemon)
                for slot in team_manager.team.slots
            )

            return {
                "success": True,
                "team_size": team_manager.size,
                "paste": paste
            }

        except Exception as e:
            return error_response(ErrorCodes.EXPORT_ERROR, str(e))

    @mcp.tool(
        title="Export Pokemon to Showdown Paste",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def export_pokemon_to_paste(
        slot: Annotated[int, Field(ge=1, le=6, description="Team slot number (1-6)")],
    ) -> dict:
        """Export a single Pokemon from the team to Showdown paste format.

        Returns paste text for the Pokemon in the given slot (Champions builds
        emit 'SPs:' lines automatically).
        """
        try:
            pokemon = team_manager.get_pokemon(slot - 1)

            if not pokemon:
                return error_response(ErrorCodes.INVALID_SLOT, f'No Pokemon in slot {slot}')

            # Delegate to the format-aware exporter (emits 'SPs:' for champions
            # builds and hyphenated Showdown species).
            paste = pokemon_build_to_showdown(pokemon)

            return {
                "success": True,
                "pokemon": pokemon.name,
                "paste": paste
            }

        except Exception as e:
            return error_response(ErrorCodes.EXPORT_ERROR, str(e))
