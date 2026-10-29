"""MCP tools for bulk offensive damage calculations and export."""

import asyncio
import logging
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

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
from vgc_mcp_core.rules.format_detect import detect_champions_format
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.build_helpers import parse_ev_string as _parse_ev_string
from vgc_mcp_core.tools.build_helpers import parse_sp_string as _parse_sp_string
from vgc_mcp_core.tools.calc_result import CalcResultDict
from vgc_mcp_core.tools.response_contract import (
    apply_contract,
    data_source_from_meta,
    spread_label,
)
from vgc_mcp_core.tools.smogon_helpers import sps_from_smogon_spread
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

from .damage_tools import _get_common_spread
from .multicalc_tools import _build_pokemon_from_smogon

logger = logging.getLogger(__name__)

# Module-level Smogon client reference
_smogon_client: Optional[SmogonStatsClient] = None


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
                sp_spread = sps_from_smogon_spread(smogon_spread)
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

    return build_pokemon(
        name=attacker_name,
        base_stats=base_stats,
        types=types,
        nature=nature_enum,
        champions=True,
        spread=sp_spread,
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

    @mcp.tool(
        title="Calculate Bulk Offensive Damage",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_bulk_offensive_calcs(
        attacker_name: Annotated[str, Field(
            description="Your Pokemon (e.g. 'urshifu-rapid-strike')",
            min_length=1,
        )],
        move_names: Annotated[list[str], Field(
            description="List of 1-4 moves to test (e.g. ['surging-strikes', 'close-combat'])",
        )],
        defender_names: Annotated[Optional[list[str]], Field(
            description="Defenders to test against (max 30, e.g. ['incineroar', 'rillaboom']). If not specified, auto-fetches top 25 Pokemon by Smogon usage.",
        )] = None,
        scenarios: Annotated[Optional[list[str]], Field(
            description="Scenario names to test: 'normal', 'tera', 'rain', 'sun', 'rain_tera', 'sun_tera', 'intimidate', 'helping_hand'. Default: ['normal']",
        )] = None,
        attacker_item: Annotated[Optional[str], Field(
            description="Attacker's held item (auto-fetched from Smogon if not specified)",
        )] = None,
        attacker_ability: Annotated[Optional[str], Field(
            description="Attacker's ability (auto-fetched from Smogon if not specified)",
        )] = None,
        attacker_nature: Annotated[Optional[str], Field(
            description="Attacker's nature (auto-fetched from Smogon if not specified)",
        )] = None,
        attacker_evs: Annotated[Optional[str], Field(
            description="Attacker's spread as an 'HP/Atk/Def/SpA/SpD/Spe' slash string, e.g. '4/252/0/0/0/252'. In Champions sessions it is read as Stat Points (e.g. '0/32/0/0/2/32') when attacker_sps is not given.",
        )] = None,
        attacker_sps: Annotated[Optional[str], Field(
            description="Champions (Reg MA) only. Attacker Stat Points in 'HP/Atk/Def/SpA/SpD/Spe' format (0-32 per stat, 66 total), e.g. '0/0/0/32/0/32'. Ignored outside a Champions session.",
        )] = None,
        attacker_tera_type: Annotated[Optional[str], Field(
            description="Attacker's Tera type (required for 'tera' and '*_tera' scenarios)",
        )] = None,
        defender_tera_types: Annotated[Optional[dict[str, str]], Field(
            description="Map of defender name to their Tera type (e.g. {'incineroar': 'water', 'rillaboom': 'fire'})",
        )] = None,
    ) -> CalcResultDict:
        """Run bulk offensive damage calculations: 1 attacker x N moves x M defenders x K scenarios.

        Replaces running dozens of individual damage calcs. Returns structured
        results with per-scenario markdown tables, Showdown-style calc strings,
        and OHKO/2HKO counts.
        """
        try:
            if len(move_names) > 4:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 4 moves supported.')

            # Resolve the format first: it decides which usage stats the top-20
            # list AND each target's spread come from, so they must agree. Use
            # the current regulation (session choice, else regulations.json),
            # not a guess from the attacker's name: a non-Mega attacker would
            # otherwise pull Reg F usage while Reg MC is live.
            is_champions = detect_champions_format()

            # Auto-fetch top meta defenders if not specified
            if defender_names is None:
                defender_names = await _get_top_meta_pokemon(
                    smogon, count=20, exclude=attacker_name,
                )
                if not defender_names:
                    return error_response(ErrorCodes.API_ERROR, 'Could not fetch top meta Pokemon. Please specify defender_names manually.')

            if len(defender_names) > 30:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 30 defenders supported.')

            # Build attacker (format-aware)
            if is_champions:
                try:
                    # attacker_evs is read on the SP scale in Champions.
                    sp_text = attacker_sps or attacker_evs
                    sp_spread = _parse_sp_string(sp_text) if sp_text else None
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_PARAMETER, str(ve))
                attacker = await _build_champions_attacker(
                    attacker_name, pokeapi,
                    attacker_nature, sp_spread, attacker_item, attacker_ability,
                )
            else:
                # Parse attacker EVs if provided
                try:
                    evs_dict = _parse_ev_string(attacker_evs) if attacker_evs else None
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_PARAMETER, f"attacker_evs: {ve}")
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
                if isinstance(result, BaseException):
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

            first = summary.scenario_names[0]
            ohko = {r.defender_name for r in summary.results if r.scenario_name == first and r.min_pct >= 100}
            meta = None
            if _smogon_client is not None:
                try:
                    meta = (await _smogon_client.get_usage_stats()).get("_meta")
                except Exception:  # noqa: BLE001 - provenance is best effort
                    meta = None
            return apply_contract({
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
            },
                headline=(
                    f"{attacker_name.replace('-', ' ').title()} guarantees an OHKO on "
                    f"{len(ohko)}/{len(defenders)} defenders ({first})"
                ),
                spreads_used={"attacker": spread_label(attacker), **{d.name: spread_label(d) for d in defenders}},
                data_source=data_source_from_meta(meta if isinstance(meta, dict) else None),
                showdown_paste=attacker_paste,
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Export Damage Report",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def export_damage_report(
        attacker_name: Annotated[str, Field(
            description="Your Pokemon (e.g. 'urshifu-rapid-strike')",
            min_length=1,
        )],
        move_names: Annotated[list[str], Field(
            description="List of 1-4 moves to test",
        )],
        defender_names: Annotated[Optional[list[str]], Field(
            description="Defenders to test against (max 30). If not specified, auto-fetches the top 20 by Smogon usage for the session's format.",
        )] = None,
        format: Annotated[str, Field(
            description="Output format: 'excel' for .xlsx or 'pdf' for .pdf",
        )] = "excel",
        scenarios: Annotated[Optional[list[str]], Field(
            description="Scenario names (default: ['normal']). See calculate_bulk_offensive_calcs for options.",
        )] = None,
        attacker_item: Annotated[Optional[str], Field(
            description="Attacker's held item (auto-fetched if not specified)",
        )] = None,
        attacker_ability: Annotated[Optional[str], Field(
            description="Attacker's ability (auto-fetched if not specified)",
        )] = None,
        attacker_nature: Annotated[Optional[str], Field(
            description="Attacker's nature (auto-fetched if not specified)",
        )] = None,
        attacker_evs: Annotated[Optional[str], Field(
            description="Attacker's spread as an 'HP/Atk/Def/SpA/SpD/Spe' slash string, e.g. '4/252/0/0/0/252'. In Champions sessions it is read as Stat Points when attacker_sps is not given.",
        )] = None,
        attacker_sps: Annotated[Optional[str], Field(
            description="Champions (Reg MA) only. Attacker Stat Points in 'HP/Atk/Def/SpA/SpD/Spe' format (0-32 per stat, 66 total)",
        )] = None,
        attacker_tera_type: Annotated[Optional[str], Field(
            description="Attacker's Tera type",
        )] = None,
        defender_tera_types: Annotated[Optional[dict[str, str]], Field(
            description="Map of defender name to their Tera type",
        )] = None,
        output_path: Annotated[Optional[str], Field(
            description="Output file path. Auto-generated if not specified.",
        )] = None,
    ) -> dict:
        """Export bulk damage calculations as an Excel spreadsheet or PDF file on disk.

        Generates a color-coded report (green=OHKO, yellow=2HKO, orange=3HKO,
        red=4HKO+) with one sheet/page per scenario. Each Excel row is one
        target × move: the target's nature and per-stat EVs/SPs, item, move,
        damage roll and % HP. Returns the file path and
        total calc count.
        """
        try:
            if format not in ("excel", "pdf"):
                return error_response(ErrorCodes.INVALID_PARAMETER, f"Unsupported format '{format}'. Use 'excel' or 'pdf'.")

            if len(move_names) > 4:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 4 moves supported.')

            # Resolve the format first: it decides which usage stats the top-20
            # list AND each target's spread come from, so they must agree. Use
            # the current regulation (session choice, else regulations.json),
            # not a guess from the attacker's name: a non-Mega attacker would
            # otherwise pull Reg F usage while Reg MC is live.
            is_champions = detect_champions_format()

            # Auto-fetch top meta defenders if not specified
            if defender_names is None:
                defender_names = await _get_top_meta_pokemon(
                    smogon, count=20, exclude=attacker_name,
                )
                if not defender_names:
                    return error_response(ErrorCodes.API_ERROR, 'Could not fetch top meta Pokemon. Please specify defender_names manually.')

            if len(defender_names) > 30:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 30 defenders supported.')

            # Build attacker (format-aware)
            if is_champions:
                try:
                    # attacker_evs is read on the SP scale in Champions.
                    sp_text = attacker_sps or attacker_evs
                    sp_spread = _parse_sp_string(sp_text) if sp_text else None
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_PARAMETER, str(ve))
                attacker = await _build_champions_attacker(
                    attacker_name, pokeapi,
                    attacker_nature, sp_spread, attacker_item, attacker_ability,
                )
            else:
                # Parse attacker EVs
                try:
                    evs_dict = _parse_ev_string(attacker_evs) if attacker_evs else None
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_PARAMETER, f"attacker_evs: {ve}")
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
