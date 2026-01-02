"""MCP tools for stat calculations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.stats import calculate_all_stats, calculate_speed, get_max_speed, get_min_speed
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread
from vgc_mcp_core.utils.errors import error_response, ErrorCodes, pokemon_not_found_error, invalid_nature_error, invalid_evs_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name, suggest_nature

# MCP-UI support (enabled in vgc-mcp-lite)
from ..ui.resources import create_summary_table_resource, create_stats_card_resource, add_ui_metadata
HAS_UI = True


def register_stats_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register stat calculation tools with the MCP server."""

    @mcp.tool()
    async def get_pokemon_stats(
        pokemon_name: str,
        nature: str = "serious",
        hp_evs: int = 0,
        atk_evs: int = 0,
        def_evs: int = 0,
        spa_evs: int = 0,
        spd_evs: int = 0,
        spe_evs: int = 0,
        level: int = 50
    ) -> dict:
        """
        Calculate all stats for a Pokemon at level 50 (VGC standard).

        Args:
            pokemon_name: Pokemon name (e.g., "flutter-mane", "dragapult", "urshifu-rapid-strike")
            nature: Pokemon's nature (e.g., "timid", "jolly", "modest", "adamant")
            hp_evs: HP EVs (0-252)
            atk_evs: Attack EVs (0-252)
            def_evs: Defense EVs (0-252)
            spa_evs: Special Attack EVs (0-252)
            spd_evs: Special Defense EVs (0-252)
            spe_evs: Speed EVs (0-252)
            level: Pokemon level (default 50 for VGC)

        Returns:
            Dict with base stats, EVs, and calculated final stats
        """
        try:
            # Validate EVs
            total_evs = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
            if total_evs > 508:
                return invalid_evs_error("total", total_evs, f"Total EVs ({total_evs}) exceed maximum of 508", total=total_evs)

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Parse nature
            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                suggestions = suggest_nature(nature)
                return invalid_nature_error(nature, suggestions if suggestions else [n.value for n in Nature])

            # Create Pokemon build
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
                ivs=IVSpread(),
                level=level
            )

            # Calculate stats
            stats = calculate_all_stats(pokemon)

            # Build summary table with base, EVs, and final stats
            table_lines = [
                "| Stat           | Base | EVs  | Final |",
                "|----------------|------|------|-------|",
                f"| HP             | {base_stats.hp:<4} | {hp_evs:<4} | {stats['hp']:<5} |",
                f"| Attack         | {base_stats.attack:<4} | {atk_evs:<4} | {stats['attack']:<5} |",
                f"| Defense        | {base_stats.defense:<4} | {def_evs:<4} | {stats['defense']:<5} |",
                f"| Sp. Attack     | {base_stats.special_attack:<4} | {spa_evs:<4} | {stats['special_attack']:<5} |",
                f"| Sp. Defense    | {base_stats.special_defense:<4} | {spd_evs:<4} | {stats['special_defense']:<5} |",
                f"| Speed          | {base_stats.speed:<4} | {spe_evs:<4} | {stats['speed']:<5} |",
            ]

            # Build analysis prose
            analysis_str = f"{pokemon_name} at Lv{level}: {stats['hp']} HP / {stats['attack']} Atk / {stats['defense']} Def / {stats['special_attack']} SpA / {stats['special_defense']} SpD / {stats['speed']} Spe ({nature} nature)"

            result = {
                "pokemon": pokemon_name,
                "level": level,
                "nature": nature,
                "types": types,
                "base_stats": {
                    "hp": base_stats.hp,
                    "attack": base_stats.attack,
                    "defense": base_stats.defense,
                    "special_attack": base_stats.special_attack,
                    "special_defense": base_stats.special_defense,
                    "speed": base_stats.speed
                },
                "evs": {
                    "hp": hp_evs,
                    "attack": atk_evs,
                    "defense": def_evs,
                    "special_attack": spa_evs,
                    "special_defense": spd_evs,
                    "speed": spe_evs,
                    "total": total_evs,
                    "remaining": 508 - total_evs
                },
                "final_stats": stats,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

            # Add MCP-UI stats card visualization
            if HAS_UI:
                try:
                    ui_resource = create_stats_card_resource(
                        pokemon_name=pokemon_name,
                        base_stats={
                            "hp": base_stats.hp,
                            "attack": base_stats.attack,
                            "defense": base_stats.defense,
                            "special_attack": base_stats.special_attack,
                            "special_defense": base_stats.special_defense,
                            "speed": base_stats.speed,
                        },
                        evs={
                            "hp": hp_evs,
                            "attack": atk_evs,
                            "defense": def_evs,
                            "special_attack": spa_evs,
                            "special_defense": spd_evs,
                            "speed": spe_evs,
                        },
                        final_stats=stats,
                        nature=nature,
                        level=level,
                        types=types,
                    )
                    result = add_ui_metadata(result, ui_resource)
                except Exception:
                    pass  # UI is optional

            return result

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions if suggestions else None)
            return api_error("PokeAPI", str(e), is_retryable=True)

    @mcp.tool()
    async def get_pokemon_speed(
        pokemon_name: str,
        nature: str = "serious",
        speed_evs: int = 0,
        speed_iv: int = 31,
        level: int = 50
    ) -> dict:
        """
        Calculate the Speed stat for a Pokemon.

        Args:
            pokemon_name: Pokemon name
            nature: Nature affecting speed (+Spe: timid/jolly, -Spe: brave/quiet/relaxed/sassy)
            speed_evs: Speed EVs (0-252)
            speed_iv: Speed IV (0-31, default 31)
            level: Pokemon level (default 50)

        Returns:
            Speed stat value with calculation details
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            base_speed = base_stats.speed

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                suggestions = suggest_nature(nature)
                return invalid_nature_error(nature, suggestions if suggestions else [n.value for n in Nature])

            speed = calculate_speed(base_speed, speed_iv, speed_evs, level, parsed_nature)

            # Also calculate min/max for reference
            max_speed = get_max_speed(base_speed, Nature.JOLLY, 31, level)
            min_speed = get_min_speed(base_speed, Nature.BRAVE, 0, level)

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Base Speed       | {base_speed}                               |",
                f"| Nature           | {nature}                                   |",
                f"| Speed EVs        | {speed_evs}                                |",
                f"| Speed IV         | {speed_iv}                                 |",
                f"| Final Speed      | {speed}                                    |",
                f"| Max (Jolly 252)  | {max_speed}                                |",
                f"| Min (Brave 0 IV) | {min_speed}                                |",
            ]

            # Build analysis prose
            analysis_str = f"{pokemon_name} reaches {speed} Speed ({min_speed} min, {max_speed} max possible)"

            result = {
                "pokemon": pokemon_name,
                "base_speed": base_speed,
                "nature": nature,
                "evs": speed_evs,
                "iv": speed_iv,
                "calculated_speed": speed,
                "reference": {
                    "max_speed_jolly_252ev": max_speed,
                    "min_speed_brave_0iv_0ev": min_speed
                },
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

            # Add MCP-UI summary table
            if HAS_UI:
                try:
                    table_rows = [
                        {"metric": "Pokemon", "value": pokemon_name},
                        {"metric": "Base Speed", "value": str(base_speed)},
                        {"metric": "Nature", "value": nature},
                        {"metric": "Speed EVs", "value": str(speed_evs)},
                        {"metric": "Speed IV", "value": str(speed_iv)},
                        {"metric": "Final Speed", "value": str(speed)},
                        {"metric": "Max (Jolly 252)", "value": str(max_speed)},
                        {"metric": "Min (Brave 0 IV)", "value": str(min_speed)},
                    ]
                    ui_resource = create_summary_table_resource(
                        title="Speed Calculation",
                        rows=table_rows,
                        highlight_rows=["Final Speed"],
                        analysis=f"{pokemon_name} reaches {speed} Speed ({min_speed} min, {max_speed} max possible)",
                    )
                    result = add_ui_metadata(result, ui_resource)
                except Exception:
                    pass  # UI is optional

            return result

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions if suggestions else None)
            return api_error("PokeAPI", str(e), is_retryable=True)
