"""MCP tools for stat calculations."""

from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.stats import (
    calculate_all_stats,
    calculate_speed,
    get_max_speed,
    get_min_speed,
)
from vgc_mcp_core.calc.stats_champions import calculate_speed_sp
from vgc_mcp_core.models.pokemon import EVSpread, IVSpread, Nature, PokemonBuild, StatPointSpread
from vgc_mcp_core.utils.errors import (
    api_error,
    invalid_evs_error,
    invalid_nature_error,
    pokemon_not_found_error,
)
from vgc_mcp_core.utils.fuzzy import suggest_nature, suggest_pokemon_name


def _detect_champions(pokemon_name: Optional[str] = None) -> bool:
    """Return True when the active session is the Champions (Reg MA) SP system.

    Mirrors spread_tools._detect_champions: optionally runs Pokemon-name
    inference first so a Mega/Reg MA mention auto-selects Champions without the
    user having to set it explicitly. The mainline path is taken whenever this
    returns False.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(pokemon_name)


def _champions_stats_response(
    pokemon_name, base_stats, types, parsed_nature, level, nature,
    hp_sps, atk_sps, def_sps, spa_sps, spd_sps, spe_sps, total_sps,
) -> dict:
    """Build the get_pokemon_stats response for a Champions (SP) subject build."""
    from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown

    sps = StatPointSpread(
        hp=hp_sps, attack=atk_sps, defense=def_sps,
        special_attack=spa_sps, special_defense=spd_sps, speed=spe_sps,
    )
    pokemon = PokemonBuild(
        name=pokemon_name,
        base_stats=base_stats,
        types=types,
        nature=parsed_nature,
        format_system="champions",
        sps=sps,
        ivs=IVSpread(),
        level=level,
    )
    stats = calculate_all_stats(pokemon)

    table_lines = [
        "| Stat           | Base | SPs  | Final |",
        "|----------------|------|------|-------|",
        f"| HP             | {base_stats.hp:<4} | {hp_sps:<4} | {stats['hp']:<5} |",
        f"| Attack         | {base_stats.attack:<4} | {atk_sps:<4} | {stats['attack']:<5} |",
        f"| Defense        | {base_stats.defense:<4} | {def_sps:<4} | {stats['defense']:<5} |",
        f"| Sp. Attack     | {base_stats.special_attack:<4} | {spa_sps:<4} | {stats['special_attack']:<5} |",
        f"| Sp. Defense    | {base_stats.special_defense:<4} | {spd_sps:<4} | {stats['special_defense']:<5} |",
        f"| Speed          | {base_stats.speed:<4} | {spe_sps:<4} | {stats['speed']:<5} |",
    ]

    analysis_str = (
        f"{pokemon_name} at Lv{level}: {stats['hp']} HP / {stats['attack']} Atk / "
        f"{stats['defense']} Def / {stats['special_attack']} SpA / "
        f"{stats['special_defense']} SpD / {stats['speed']} Spe ({nature} nature, Stat Points)"
    )

    return {
        "pokemon": pokemon_name,
        "level": level,
        "nature": nature,
        "types": types,
        "format_system": "champions",
        "base_stats": {
            "hp": base_stats.hp,
            "attack": base_stats.attack,
            "defense": base_stats.defense,
            "special_attack": base_stats.special_attack,
            "special_defense": base_stats.special_defense,
            "speed": base_stats.speed,
        },
        "sps": {
            "hp": hp_sps,
            "attack": atk_sps,
            "defense": def_sps,
            "special_attack": spa_sps,
            "special_defense": spd_sps,
            "speed": spe_sps,
            "total": total_sps,
            "remaining": max(0, 66 - total_sps),
        },
        "final_stats": stats,
        "summary_table": "\n".join(table_lines),
        "analysis": analysis_str,
        "showdown_paste": pokemon_build_to_showdown(pokemon),
    }


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

        In a Pokemon Champions (Reg MA) session the same six inputs are
        interpreted as Stat Points (0-32 per stat, 66 total) and stats use the
        SP formula (e.g. Flutter Mane 32 Spe SP -> 205 Speed).
        """
        try:
            is_champions = _detect_champions(pokemon_name)

            # Validate investment under the active format's cap.
            total_invest = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
            if is_champions:
                over = [
                    (label, val) for label, val in (
                        ("hp", hp_evs), ("attack", atk_evs), ("defense", def_evs),
                        ("special_attack", spa_evs), ("special_defense", spd_evs), ("speed", spe_evs),
                    ) if val > 32
                ]
                if over:
                    stat, val = over[0]
                    return invalid_evs_error(stat, val, f"Stat Points for {stat} ({val}) exceed maximum of 32")
                if total_invest > 66:
                    return invalid_evs_error("total", total_invest, f"Total Stat Points ({total_invest}) exceed maximum of 66", total=total_invest)
            else:
                if total_invest > 508:
                    return invalid_evs_error("total", total_invest, f"Total EVs ({total_invest}) exceed maximum of 508", total=total_invest)

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Parse nature
            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                suggestions = suggest_nature(nature)
                return invalid_nature_error(nature, suggestions if suggestions else [n.value for n in Nature])

            if is_champions:
                return _champions_stats_response(
                    pokemon_name, base_stats, types, parsed_nature, level, nature,
                    hp_evs, atk_evs, def_evs, spa_evs, spd_evs, spe_evs, total_invest,
                )

            # Mainline EV path (unchanged).
            total_evs = total_invest

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

            return {
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

        In a Pokemon Champions (Reg MA) session `speed_evs` is interpreted as
        Speed Stat Points (0-32) and Speed uses the SP formula (e.g. Flutter
        Mane 32 Spe SP -> 205).
        """
        try:
            is_champions = _detect_champions(pokemon_name)
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            base_speed = base_stats.speed

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                suggestions = suggest_nature(nature)
                return invalid_nature_error(nature, suggestions if suggestions else [n.value for n in Nature])

            if is_champions:
                if speed_evs > 32:
                    return invalid_evs_error("speed", speed_evs, f"Speed Stat Points ({speed_evs}) exceed maximum of 32")

                speed = calculate_speed_sp(base_speed, speed_iv, speed_evs, level, parsed_nature)
                max_speed = calculate_speed_sp(base_speed, 31, 32, level, Nature.JOLLY)
                min_speed = calculate_speed_sp(base_speed, 0, 0, level, Nature.BRAVE)

                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Pokemon          | {pokemon_name}                             |",
                    f"| Base Speed       | {base_speed}                               |",
                    f"| Nature           | {nature}                                   |",
                    f"| Speed SPs        | {speed_evs}                                |",
                    f"| Speed IV         | {speed_iv}                                 |",
                    f"| Final Speed      | {speed}                                    |",
                    f"| Max (Jolly 32SP) | {max_speed}                                |",
                    f"| Min (Brave 0 IV) | {min_speed}                                |",
                ]
                analysis_str = f"{pokemon_name} reaches {speed} Speed ({min_speed} min, {max_speed} max possible, Stat Points)"

                return {
                    "pokemon": pokemon_name,
                    "base_speed": base_speed,
                    "nature": nature,
                    "format_system": "champions",
                    "sps": speed_evs,
                    "iv": speed_iv,
                    "calculated_speed": speed,
                    "reference": {
                        "max_speed_jolly_32sp": max_speed,
                        "min_speed_brave_0iv_0sp": min_speed,
                    },
                    "summary_table": "\n".join(table_lines),
                    "analysis": analysis_str,
                }

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

            return {
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

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions if suggestions else None)
            return api_error("PokeAPI", str(e), is_retryable=True)
