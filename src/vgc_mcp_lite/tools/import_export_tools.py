"""MCP tools for importing/exporting Pokemon Showdown format."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.pokepaste import PokePasteClient, PokePasteError
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.formats.showdown import (
    parse_showdown_pokemon,
    parse_showdown_team,
    export_pokemon_to_showdown,
    export_team_to_showdown,
    parsed_to_ev_spread,
    parsed_to_iv_spread,
    parsed_to_nature,
    ShowdownParseError,
)
from vgc_mcp_core.models.pokemon import PokemonBuild
from vgc_mcp_lite.ui.components import create_pokepaste_team_grid_ui


def register_import_export_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    team_manager: TeamManager
):
    """Register import/export tools with the MCP server."""

    @mcp.tool()
    async def import_showdown_pokemon(paste: str, add_to_team: bool = True) -> dict:
        """
        Parse a Pokemon from Showdown paste format.

        Example paste:
        ```
        Urshifu-Rapid-Strike @ Choice Scarf
        Ability: Unseen Fist
        Level: 50
        Tera Type: Water
        EVs: 4 HP / 252 Atk / 252 Spe
        Jolly Nature
        - Surging Strikes
        - Close Combat
        - U-turn
        - Aqua Jet
        ```

        Args:
            paste: The Showdown paste text for one Pokemon
            add_to_team: If True, automatically add to current team

        Returns:
            Parsed Pokemon data and team status if added
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
                return {
                    "success": False,
                    "error": "api_error",
                    "message": f"Could not fetch Pokemon data: {e}",
                    "parsed": {
                        "species": parsed.species,
                        "nickname": parsed.nickname
                    }
                }

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
                    "ivs": parsed.ivs,
                    "moves": parsed.moves,
                    "shiny": parsed.shiny,
                    "gender": parsed.gender,
                },
                "types": types
            }

            if add_to_team:
                # Create PokemonBuild and add to team
                pokemon = PokemonBuild(
                    name=species_name,
                    base_stats=base_stats,
                    types=types,
                    nature=parsed_to_nature(parsed),
                    evs=parsed_to_ev_spread(parsed),
                    ivs=parsed_to_iv_spread(parsed),
                    level=parsed.level,
                    ability=parsed.ability,
                    item=parsed.item,
                    tera_type=parsed.tera_type,
                    moves=parsed.moves[:4]
                )

                success, message, data = team_manager.add_pokemon(pokemon)
                result["team"] = {
                    "added": success,
                    "message": message,
                    "team_size": data.get("team_size", team_manager.size)
                }

            return result

        except ShowdownParseError as e:
            return {
                "success": False,
                "error": "parse_error",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "unknown_error",
                "message": str(e)
            }

    @mcp.tool()
    async def import_showdown_team(paste: str, clear_existing: bool = False) -> dict:
        """
        Parse a full team from Showdown paste format.

        Pokemon should be separated by blank lines. Up to 6 Pokemon will be imported.

        Args:
            paste: The full team paste text
            clear_existing: If True, clear current team before importing

        Returns:
            List of imported Pokemon and team status
        """
        try:
            if clear_existing:
                team_manager.clear()

            parsed_team = parse_showdown_team(paste)

            if not parsed_team:
                return {
                    "success": False,
                    "error": "parse_error",
                    "message": "No Pokemon found in paste"
                }

            results = []
            added_count = 0
            failed_count = 0

            for parsed in parsed_team:
                species_name = parsed.species.lower().replace(" ", "-")

                try:
                    base_stats = await pokeapi.get_base_stats(species_name)
                    types = await pokeapi.get_pokemon_types(species_name)

                    pokemon = PokemonBuild(
                        name=species_name,
                        base_stats=base_stats,
                        types=types,
                        nature=parsed_to_nature(parsed),
                        evs=parsed_to_ev_spread(parsed),
                        ivs=parsed_to_iv_spread(parsed),
                        level=parsed.level,
                        ability=parsed.ability,
                        item=parsed.item,
                        tera_type=parsed.tera_type,
                        moves=parsed.moves[:4]
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

            return {
                "success": added_count > 0,
                "imported_count": added_count,
                "failed_count": failed_count,
                "results": results,
                "team_size": team_manager.size,
                "team": team_manager.team.get_pokemon_names()
            }

        except Exception as e:
            return {
                "success": False,
                "error": "unknown_error",
                "message": str(e)
            }

    @mcp.tool()
    async def export_team_to_paste() -> dict:
        """
        Export the current team to Showdown paste format.

        Returns:
            Showdown paste text that can be imported into Pokemon Showdown
        """
        try:
            if team_manager.size == 0:
                return {
                    "success": False,
                    "error": "empty_team",
                    "message": "No Pokemon on team to export"
                }

            team_data = []

            for slot in team_manager.team.slots:
                pokemon = slot.pokemon
                team_data.append({
                    "species": pokemon.name.replace("-", " ").title(),
                    "item": pokemon.item,
                    "ability": pokemon.ability,
                    "level": pokemon.level,
                    "tera_type": pokemon.tera_type,
                    "evs": {
                        "hp": pokemon.evs.hp,
                        "atk": pokemon.evs.attack,
                        "def": pokemon.evs.defense,
                        "spa": pokemon.evs.special_attack,
                        "spd": pokemon.evs.special_defense,
                        "spe": pokemon.evs.speed,
                    },
                    "ivs": {
                        "hp": pokemon.ivs.hp,
                        "atk": pokemon.ivs.attack,
                        "def": pokemon.ivs.defense,
                        "spa": pokemon.ivs.special_attack,
                        "spd": pokemon.ivs.special_defense,
                        "spe": pokemon.ivs.speed,
                    },
                    "nature": pokemon.nature.value.title(),
                    "moves": pokemon.moves,
                })

            paste = export_team_to_showdown(team_data)

            return {
                "success": True,
                "team_size": team_manager.size,
                "paste": paste
            }

        except Exception as e:
            return {
                "success": False,
                "error": "export_error",
                "message": str(e)
            }

    @mcp.tool()
    async def export_pokemon_to_paste(slot: int) -> dict:
        """
        Export a single Pokemon from the team to Showdown paste format.

        Args:
            slot: Slot number (1-6)

        Returns:
            Showdown paste text for the Pokemon
        """
        try:
            pokemon = team_manager.get_pokemon(slot - 1)

            if not pokemon:
                return {
                    "success": False,
                    "error": "invalid_slot",
                    "message": f"No Pokemon in slot {slot}"
                }

            paste = export_pokemon_to_showdown(
                species=pokemon.name.replace("-", " ").title(),
                item=pokemon.item,
                ability=pokemon.ability,
                level=pokemon.level,
                tera_type=pokemon.tera_type,
                evs={
                    "hp": pokemon.evs.hp,
                    "atk": pokemon.evs.attack,
                    "def": pokemon.evs.defense,
                    "spa": pokemon.evs.special_attack,
                    "spd": pokemon.evs.special_defense,
                    "spe": pokemon.evs.speed,
                },
                ivs={
                    "hp": pokemon.ivs.hp,
                    "atk": pokemon.ivs.attack,
                    "def": pokemon.ivs.defense,
                    "spa": pokemon.ivs.special_attack,
                    "spd": pokemon.ivs.special_defense,
                    "spe": pokemon.ivs.speed,
                },
                nature=pokemon.nature.value.title(),
                moves=pokemon.moves,
            )

            return {
                "success": True,
                "pokemon": pokemon.name,
                "paste": paste
            }

        except Exception as e:
            return {
                "success": False,
                "error": "export_error",
                "message": str(e)
            }

    @mcp.tool()
    async def render_pokepaste_team(
        url_or_id: str,
        team_name: Optional[str] = None
    ) -> dict:
        """
        Fetch a Pokepaste and render it as a team grid card UI.

        Takes a pokepast.es URL or paste ID and generates an HTML visualization
        showing all Pokemon with their full build details:
        - Sprites, types, tera type
        - Item, ability, nature
        - Full EV spread (all 6 stats)
        - Non-default IVs
        - All moves
        - Calculated final stats at Lv50

        Args:
            url_or_id: Pokepaste URL (e.g., "https://pokepast.es/abc123") or paste ID
            team_name: Optional display name for the team header

        Returns:
            Dict with HTML content or error message
        """
        try:
            # Fetch the paste
            pokepaste_client = PokePasteClient()
            paste_id = pokepaste_client.extract_paste_id(url_or_id)
            if not paste_id:
                return {
                    "success": False,
                    "error": "invalid_url",
                    "message": f"Could not extract paste ID from: {url_or_id}"
                }

            raw_paste = await pokepaste_client.get_paste(url_or_id)
            paste_url = f"https://pokepast.es/{paste_id}"

            # Parse the team
            parsed_team = parse_showdown_team(raw_paste)
            if not parsed_team:
                return {
                    "success": False,
                    "error": "parse_error",
                    "message": "No Pokemon found in paste"
                }

            # Build pokemon list with full data
            pokemon_list = []
            for parsed in parsed_team:
                species_name = parsed.species.lower().replace(" ", "-")

                # Fetch base stats and types from API
                try:
                    base_stats = await pokeapi.get_base_stats(species_name)
                    types = await pokeapi.get_pokemon_types(species_name)
                except Exception:
                    # Use fallback if API fails
                    base_stats = {"hp": 80, "atk": 80, "def": 80, "spa": 80, "spd": 80, "spe": 80}
                    types = ["Normal"]

                # Convert base_stats to short keys if needed
                base_stats_short = {
                    "hp": base_stats.get("hp", base_stats.get("hp", 80)),
                    "atk": base_stats.get("attack", base_stats.get("atk", 80)),
                    "def": base_stats.get("defense", base_stats.get("def", 80)),
                    "spa": base_stats.get("special_attack", base_stats.get("spa", 80)),
                    "spd": base_stats.get("special_defense", base_stats.get("spd", 80)),
                    "spe": base_stats.get("speed", base_stats.get("spe", 80)),
                }

                # Convert EVs dict keys from showdown format
                evs_short = {
                    "hp": parsed.evs.get("hp", 0),
                    "atk": parsed.evs.get("atk", 0),
                    "def": parsed.evs.get("def", 0),
                    "spa": parsed.evs.get("spa", 0),
                    "spd": parsed.evs.get("spd", 0),
                    "spe": parsed.evs.get("spe", 0),
                }

                # IVs - only include non-31 values
                ivs_short = {}
                for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
                    iv_val = parsed.ivs.get(stat, 31)
                    if iv_val != 31:
                        ivs_short[stat] = iv_val

                pokemon_list.append({
                    "species": parsed.species,
                    "types": types,
                    "item": parsed.item,
                    "ability": parsed.ability,
                    "nature": parsed.nature,
                    "evs": evs_short,
                    "ivs": ivs_short,
                    "moves": parsed.moves,
                    "tera_type": parsed.tera_type,
                    "level": parsed.level,
                    "base_stats": base_stats_short,
                })

            # Generate HTML
            html = create_pokepaste_team_grid_ui(
                pokemon_list=pokemon_list,
                team_name=team_name,
                paste_url=paste_url,
            )

            return {
                "success": True,
                "paste_id": paste_id,
                "paste_url": paste_url,
                "pokemon_count": len(pokemon_list),
                "pokemon_names": [p["species"] for p in pokemon_list],
                "ui": {
                    "type": "html",
                    "content": html
                }
            }

        except PokePasteError as e:
            return {
                "success": False,
                "error": "fetch_error",
                "message": str(e)
            }
        except ShowdownParseError as e:
            return {
                "success": False,
                "error": "parse_error",
                "message": str(e)
            }
        except Exception as e:
            return {
                "success": False,
                "error": "unknown_error",
                "message": str(e)
            }
