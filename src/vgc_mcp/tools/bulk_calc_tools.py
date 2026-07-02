"""MCP tools for bulk offensive damage calculations and export."""

import asyncio
import logging
from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.bulk_calc import (
    DEFAULT_SCENARIOS,
    get_results_for_scenario,
    run_bulk_calcs,
)
from vgc_mcp_core.calc.damage import format_percent
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.pokemon import Nature, PokemonBuild, StatPointSpread
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

from .damage_tools import _get_common_spread
from .multicalc_tools import _build_pokemon_from_smogon

logger = logging.getLogger(__name__)

# Module-level Smogon client reference
_smogon_client: Optional[SmogonStatsClient] = None


def _parse_ev_string(ev_string: str) -> dict:
    """Parse '252/0/0/252/0/4' format into EV dict."""
    parts = ev_string.split("/")
    if len(parts) != 6:
        raise ValueError(f"EV string must have 6 values separated by '/', got: {ev_string}")
    stat_names = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
    return {name: int(val) for name, val in zip(stat_names, parts)}


def _detect_champions(*pokemon_names: str) -> bool:
    """Return True when the active session resolves to the Champions (Reg MA)
    Stat-Point format.

    Mirrors the format-detection pattern in the other wave-2 tools: an explicit
    session regulation wins, otherwise Pokemon-name inference (Mega forms, the
    Reg MA allowlist, etc.) sets the session, then we read the resolved format
    system. Inference failures are swallowed so a missing data file never breaks
    the mainline path.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(*pokemon_names)


def _parse_sp_string(sp_string: str) -> StatPointSpread:
    """Parse 'HP/Atk/Def/SpA/SpD/Spe' Stat Points into a StatPointSpread.

    Champions (Reg MA) caps: 0-32 per stat, 66 total (enforced by the model).
    """
    parts = [p.strip() for p in sp_string.replace(",", "/").split("/")]
    if len(parts) != 6:
        raise ValueError(
            "Stat Points must be 'HP/Atk/Def/SpA/SpD/Spe' (six values)"
        )
    vals = [int(p) for p in parts]
    return StatPointSpread(
        hp=vals[0], attack=vals[1], defense=vals[2],
        special_attack=vals[3], special_defense=vals[4], speed=vals[5],
    )


def _sps_from_smogon_spread(spread: Optional[dict]) -> Optional[StatPointSpread]:
    """Build a StatPointSpread from a champions-tagged Smogon spread dict.

    Wave-1's smogon helper carries `sps` (canonical-stat-name dict) +
    `format_system` alongside `evs`. Returns None when the spread isn't a
    champions spread or has no SP data, so callers fall back to the mainline path.
    """
    if not spread or spread.get("format_system") != "champions":
        return None
    sps = spread.get("sps")
    if not sps:
        return None
    return StatPointSpread.from_sps_dict(sps)


async def _build_champions_attacker(
    attacker_name: str,
    pokeapi: PokeAPIClient,
    nature: Optional[str],
    sp_spread: Optional[StatPointSpread],
    item: Optional[str],
    ability: Optional[str],
) -> PokemonBuild:
    """Build the USER's subject attacker as a Champions (Reg MA) Stat-Point build.

    Only the user's subject Pokemon becomes format_system='champions'; opposing
    meta defenders stay mainline (handled separately). Auto-fills nature / SPs /
    item / ability from a champions-tagged Smogon spread when not supplied, then
    falls back to the species' best offensive stat at full investment.
    """
    base_stats = await pokeapi.get_base_stats(attacker_name)
    types = await pokeapi.get_pokemon_types(attacker_name)

    # Auto-fetch from Smogon when nature / SPs are unspecified.
    if nature is None or sp_spread is None:
        smogon_spread = await _get_common_spread(attacker_name)
        if smogon_spread:
            if nature is None:
                nature = smogon_spread.get("nature")
            if sp_spread is None:
                sp_spread = _sps_from_smogon_spread(smogon_spread)
            if item is None:
                item = smogon_spread.get("item")
            if ability is None:
                ability = smogon_spread.get("ability")

    # Resolve ability via the centralised resolver (mega > Smogon > pokeapi).
    if ability is None:
        from vgc_mcp_core.tools.ability_helpers import resolve_ability
        ability, _ = await resolve_ability(
            attacker_name, pokeapi=pokeapi, smogon_client=_smogon_client,
        )

    # Default SP allocation: max out the species' main offensive stat + Speed.
    if sp_spread is None:
        if base_stats.attack >= base_stats.special_attack:
            sp_spread = StatPointSpread(attack=32, speed=32)
        else:
            sp_spread = StatPointSpread(special_attack=32, speed=32)

    nature_enum = Nature(nature.lower() if nature else "serious")

    return PokemonBuild(
        name=attacker_name,
        base_stats=base_stats,
        types=types,
        nature=nature_enum,
        format_system="champions",
        sps=sp_spread,
        item=item,
        ability=ability,
    )


async def _get_top_meta_pokemon(
    smogon_client: SmogonStatsClient,
    count: int = 25,
    exclude: Optional[str] = None,
) -> list[str]:
    """Fetch top Pokemon by usage from Smogon stats.

    Returns a list of Pokemon names sorted by usage, excluding the specified Pokemon.
    """
    try:
        stats = await smogon_client.get_usage_stats()
        data = stats.get("data", {})
        if not data:
            return []

        # Sort by usage descending
        sorted_mons = sorted(
            data.items(),
            key=lambda x: x[1].get("usage", 0),
            reverse=True,
        )

        # Filter and normalize names
        result = []
        exclude_norm = (exclude or "").lower().replace(" ", "").replace("-", "")
        for mon_name, _mon_data in sorted_mons:
            name_norm = mon_name.lower().replace(" ", "").replace("-", "")
            if name_norm == exclude_norm:
                continue
            # Convert to kebab-case for consistency
            result.append(mon_name.lower().replace(" ", "-"))
            if len(result) >= count:
                break
        return result
    except Exception as e:
        logger.warning("Failed to fetch top meta Pokemon: %s", e)
        return []


def register_bulk_calc_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient] = None,
):
    """Register bulk damage calculation and export tools."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def calculate_bulk_offensive_calcs(
        attacker_name: str,
        move_names: list[str],
        defender_names: Optional[list[str]] = None,
        scenarios: Optional[list[str]] = None,
        attacker_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        attacker_nature: Optional[str] = None,
        attacker_evs: Optional[str] = None,
        attacker_sps: Optional[str] = None,
        attacker_tera_type: Optional[str] = None,
        defender_tera_types: Optional[dict[str, str]] = None,
    ) -> dict:
        """
        Run bulk offensive damage calculations: 1 attacker × N moves × M defenders × K scenarios.

        Replaces running dozens of individual damage calcs. Returns structured results
        with calc strings, KO counts, and markdown tables per scenario.

        Args:
            attacker_name: Your Pokemon (e.g., "urshifu-rapid-strike")
            move_names: List of 1-4 moves to test
                (e.g., ["surging-strikes", "close-combat"])
            defender_names: List of defenders to test against
                (e.g., ["incineroar", "rillaboom"]).
                If not specified, auto-fetches top 25 Pokemon by Smogon usage.
            scenarios: List of scenario names to test. Options: "normal", "tera", "rain", "sun",
                       "rain_tera", "sun_tera", "intimidate", "helping_hand". Default: ["normal"]
            attacker_item: Attacker's held item (auto-fetched from Smogon if not specified)
            attacker_ability: Attacker's ability (auto-fetched from Smogon if not specified)
            attacker_nature: Attacker's nature (auto-fetched from Smogon if not specified)
            attacker_evs: Attacker's EVs in "HP/Atk/Def/SpA/SpD/Spe" format, e.g. "4/252/0/0/0/252"
                (mainline only)
            attacker_sps: Champions (Reg MA) only. Attacker Stat Points in
                "HP/Atk/Def/SpA/SpD/Spe" format (0-32 per stat, 66 total),
                e.g. "0/0/0/32/0/32". Ignored outside a Champions session.
            attacker_tera_type: Attacker's Tera type (required for "tera" and "*_tera" scenarios)
            defender_tera_types: Map of defender name to their Tera type
                (e.g., {"incineroar": "water", "rillaboom": "fire"})

        Returns:
            Structured results with per-scenario markdown tables, calc strings, and KO summary
        """
        try:
            if len(move_names) > 4:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 4 moves supported.')

            # Auto-fetch top meta defenders if not specified
            if defender_names is None:
                defender_names = await _get_top_meta_pokemon(
                    smogon, count=25, exclude=attacker_name,
                )
                if not defender_names:
                    return error_response(ErrorCodes.API_ERROR, 'Could not fetch top meta Pokemon. Please specify defender_names manually.')

            if len(defender_names) > 30:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 30 defenders supported.')

            # Detect Champions (Reg MA) session — only the user's subject
            # attacker becomes a Stat-Point build; meta defenders stay mainline.
            is_champions = _detect_champions(attacker_name)

            # Build attacker (format-aware)
            if is_champions:
                try:
                    sp_spread = _parse_sp_string(attacker_sps) if attacker_sps else None
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_PARAMETER, str(ve))
                attacker = await _build_champions_attacker(
                    attacker_name, pokeapi,
                    attacker_nature, sp_spread, attacker_item, attacker_ability,
                )
            else:
                # Parse attacker EVs if provided
                evs_dict = _parse_ev_string(attacker_evs) if attacker_evs else None
                attacker = await _build_pokemon_from_smogon(
                    attacker_name, pokeapi,
                    attacker_nature, evs_dict, attacker_item, attacker_ability,
                )
            if attacker_tera_type:
                attacker.tera_type = attacker_tera_type

            # Fetch moves in parallel
            moves = list(await asyncio.gather(
                *[pokeapi.get_move(m, user_name=attacker_name) for m in move_names]
            ))

            # Build defenders in parallel — up to 30 PokeAPI fetches at once
            # (cached after first request, so subsequent runs are essentially free)
            defender_results = await asyncio.gather(
                *[_build_pokemon_from_smogon(n, pokeapi) for n in defender_names],
                return_exceptions=True,
            )
            defenders = []
            failed_defenders = []
            for name, result in zip(defender_names, defender_results):
                if isinstance(result, Exception):
                    failed_defenders.append({"name": name, "error": str(result)})
                else:
                    defenders.append(result)

            if not defenders:
                return error_response(ErrorCodes.INTERNAL_ERROR, 'Could not build any defenders. Check Pokemon names.')

            # Resolve scenarios
            scenario_configs = []
            scenario_names_used = scenarios or ["normal"]
            for s_name in scenario_names_used:
                if s_name in DEFAULT_SCENARIOS:
                    scenario_configs.append(DEFAULT_SCENARIOS[s_name])
                else:
                    avail = list(DEFAULT_SCENARIOS.keys())
                    return error_response(ErrorCodes.INTERNAL_ERROR, f"Unknown scenario '{s_name}'. Available: {avail}")

            # Run bulk calcs
            summary = run_bulk_calcs(
                attacker, moves, defenders, scenario_configs,
                defender_tera_types=defender_tera_types,
            )

            # Generate attacker Showdown paste
            attacker_paste = pokemon_build_to_showdown(attacker)

            # Build per-scenario markdown tables
            scenario_tables = {}
            for s_name in summary.scenario_names:
                s_results = get_results_for_scenario(summary, s_name)
                if not s_results:
                    continue

                display_name = s_results[0].scenario_display

                # Build table
                move_headers = [m.replace("-", " ").title() for m in summary.move_names]
                header = "| Defender | Spread | Item | " + " | ".join(move_headers) + " |"
                move_seps = "|".join(["------"] * len(summary.move_names))
                separator = f"|----------|--------|------|{move_seps}|"
                rows = [header, separator]

                # Get unique defenders in order
                seen = []
                for r in s_results:
                    if r.defender_name not in seen:
                        seen.append(r.defender_name)

                for def_name in seen:
                    def_display = def_name.replace("-", " ").title()
                    spread = summary.defender_spreads.get(def_name, "")
                    item = summary.defender_items.get(def_name, "None")
                    item_display = item.replace("-", " ").title() if item != "None" else ""

                    move_cells = []
                    for move_name in summary.move_names:
                        matching = [
                            r for r in s_results
                            if r.defender_name == def_name and r.move_name == move_name
                        ]
                        if matching:
                            r = matching[0]
                            min_str = format_percent(r.min_pct)
                            max_str = format_percent(r.max_pct)
                            move_cells.append(f"{min_str}-{max_str}% ({r.ko_chance})")
                        else:
                            move_cells.append("—")

                    moves_str = " | ".join(move_cells)
                    row = (
                        f"| {def_display} | {spread} | "
                        f"{item_display} | {moves_str} |"
                    )
                    rows.append(row)

                scenario_tables[s_name] = {
                    "display_name": display_name,
                    "markdown_table": "\n".join(rows),
                }

            # Build calc strings list
            calc_strings = [r.calc_string for r in summary.results]

            # Build results grouped by defender
            results_by_defender = {}
            for r in summary.results:
                if r.defender_name not in results_by_defender:
                    results_by_defender[r.defender_name] = {}
                if r.move_name not in results_by_defender[r.defender_name]:
                    results_by_defender[r.defender_name][r.move_name] = {}
                results_by_defender[r.defender_name][r.move_name][r.scenario_name] = {
                    "damage_pct": f"{format_percent(r.min_pct)}-{format_percent(r.max_pct)}%",
                    "ko_chance": r.ko_chance,
                    "calc_string": r.calc_string,
                }

            # For a Champions subject the core summary builds its spread string
            # from EVs (all zero on an SP build), so report the SP spread instead.
            if is_champions:
                sp = attacker.sps or StatPointSpread()
                attacker_spread_display = (
                    f"{attacker.nature.value.title()} "
                    f"{sp.hp}/{sp.attack}/{sp.defense}/"
                    f"{sp.special_attack}/{sp.special_defense}/{sp.speed} (SPs)"
                )
            else:
                attacker_spread_display = summary.attacker_spread_str

            return {
                "attacker": {
                    "name": attacker_name,
                    "spread": attacker_spread_display,
                    "format_system": attacker.format_system,
                    "tera_type": attacker_tera_type,
                    "attacker_showdown_paste": attacker_paste,
                },
                "total_calcs": summary.total_calcs,
                "moves": summary.move_names,
                "scenarios": summary.scenario_names,
                "scenario_tables": scenario_tables,
                "results_by_defender": results_by_defender,
                "ohko_summary": summary.ohko_counts,
                "twohko_summary": summary.twohko_counts,
                "calc_strings": calc_strings,
                "failed_defenders": failed_defenders if failed_defenders else None,
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def export_damage_report(
        attacker_name: str,
        move_names: list[str],
        defender_names: Optional[list[str]] = None,
        format: str = "excel",
        scenarios: Optional[list[str]] = None,
        attacker_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        attacker_nature: Optional[str] = None,
        attacker_evs: Optional[str] = None,
        attacker_sps: Optional[str] = None,
        attacker_tera_type: Optional[str] = None,
        defender_tera_types: Optional[dict[str, str]] = None,
        output_path: Optional[str] = None,
    ) -> dict:
        """
        Export bulk damage calculations as an Excel spreadsheet or PDF file.

        Generates a color-coded report (green=OHKO, yellow=2HKO, orange=3HKO, red=4HKO+)
        with one sheet/page per scenario.

        Args:
            attacker_name: Your Pokemon (e.g., "urshifu-rapid-strike")
            move_names: List of 1-4 moves to test
            defender_names: List of defenders to test against.
                If not specified, auto-fetches top 25 by Smogon usage.
            format: Output format - "excel" for .xlsx or "pdf" for .pdf
            scenarios: Scenario names (default: ["normal"]).
                See calculate_bulk_offensive_calcs for options.
            attacker_item: Attacker's held item (auto-fetched if not specified)
            attacker_ability: Attacker's ability (auto-fetched if not specified)
            attacker_nature: Attacker's nature (auto-fetched if not specified)
            attacker_evs: Attacker's EVs in "HP/Atk/Def/SpA/SpD/Spe" format (mainline only)
            attacker_sps: Champions (Reg MA) only. Attacker Stat Points in
                "HP/Atk/Def/SpA/SpD/Spe" format (0-32 per stat, 66 total)
            attacker_tera_type: Attacker's Tera type
            defender_tera_types: Map of defender name to their Tera type
            output_path: Optional output file path. Auto-generated if not specified.

        Returns:
            Dict with file_path and total_calcs
        """
        try:
            if format not in ("excel", "pdf"):
                return error_response(ErrorCodes.INVALID_PARAMETER, f"Unsupported format '{format}'. Use 'excel' or 'pdf'.")

            if len(move_names) > 4:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 4 moves supported.')

            # Auto-fetch top meta defenders if not specified
            if defender_names is None:
                defender_names = await _get_top_meta_pokemon(
                    smogon, count=25, exclude=attacker_name,
                )
                if not defender_names:
                    return error_response(ErrorCodes.API_ERROR, 'Could not fetch top meta Pokemon. Please specify defender_names manually.')

            if len(defender_names) > 30:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 30 defenders supported.')

            # Detect Champions (Reg MA) session — only the user's subject
            # attacker becomes a Stat-Point build; meta defenders stay mainline.
            is_champions = _detect_champions(attacker_name)

            # Build attacker (format-aware)
            if is_champions:
                try:
                    sp_spread = _parse_sp_string(attacker_sps) if attacker_sps else None
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_PARAMETER, str(ve))
                attacker = await _build_champions_attacker(
                    attacker_name, pokeapi,
                    attacker_nature, sp_spread, attacker_item, attacker_ability,
                )
            else:
                # Parse attacker EVs
                evs_dict = _parse_ev_string(attacker_evs) if attacker_evs else None
                attacker = await _build_pokemon_from_smogon(
                    attacker_name, pokeapi,
                    attacker_nature, evs_dict, attacker_item, attacker_ability,
                )
            if attacker_tera_type:
                attacker.tera_type = attacker_tera_type

            # Fetch moves in parallel
            moves = list(await asyncio.gather(
                *[pokeapi.get_move(m, user_name=attacker_name) for m in move_names]
            ))

            # Build defenders
            defenders = []
            for defender_name in defender_names:
                try:
                    defender = await _build_pokemon_from_smogon(defender_name, pokeapi)
                    defenders.append(defender)
                except Exception as e:
                    logger.warning("Failed to build defender %s for export: %s", defender_name, e)

            if not defenders:
                return error_response(ErrorCodes.INTERNAL_ERROR, 'Could not build any defenders.')

            # Resolve scenarios
            scenario_configs = []
            for s_name in (scenarios or ["normal"]):
                if s_name in DEFAULT_SCENARIOS:
                    scenario_configs.append(DEFAULT_SCENARIOS[s_name])
                else:
                    return error_response(ErrorCodes.INTERNAL_ERROR, f"Unknown scenario '{s_name}'.")

            # Run bulk calcs
            summary = run_bulk_calcs(
                attacker, moves, defenders, scenario_configs,
                defender_tera_types=defender_tera_types,
            )

            # Generate report
            if format == "excel":
                from vgc_mcp_core.export.damage_report import generate_excel_report
                file_path = generate_excel_report(summary, output_path)
            else:
                from vgc_mcp_core.export.damage_report import generate_pdf_report
                file_path = generate_pdf_report(summary, output_path)

            return {
                "file_path": file_path,
                "format": format,
                "total_calcs": summary.total_calcs,
                "attacker": attacker_name,
                "defenders_tested": len(defenders),
                "scenarios_tested": len(scenario_configs),
            }

        except ImportError as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
