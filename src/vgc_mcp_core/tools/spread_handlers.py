"""Handlers for the spread optimization tools (efficiency, nature, bulk, role spreads, HP numbers)."""

from typing import Any, Optional

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.bulk_optimization import (
    analyze_diminishing_returns,
)
from vgc_mcp_core.calc.champions_optimization import (
    SP_TOTAL_MAX,
)
from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat, find_speed_evs
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50, logger, normalize_evs
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.move import MoveCategory
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
    Nature,
    get_nature_modifier,
)
from vgc_mcp_core.rules.format_detect import detect_champions_format
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.spread_champions import (
    _check_spread_efficiency_champions,
    _optimize_bulk_champions,
    _suggest_nature_optimization_champions,
    _suggest_spread_champions,
)
from vgc_mcp_core.tools.spread_common import (
    _find_min_evs_for_hp,
    _find_min_evs_for_stat,
    slash_values,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


async def check_spread_efficiency(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    nature: str,
    hp_evs: int = 0,
    atk_evs: int = 0,
    def_evs: int = 0,
    spa_evs: int = 0,
    spd_evs: int = 0,
    spe_evs: int = 0,
    spread: Optional[str] = None,
) -> dict[str, Any]:
    if spread:
        try:
            hp_evs, atk_evs, def_evs, spa_evs, spd_evs, spe_evs = slash_values(spread)
        except ValueError as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(e))
    try:
        base_stats = await pokeapi.get_base_stats(pokemon_name)

        try:
            parsed_nature = Nature(nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        # In a Champions session the *_evs args carry SP-scale numbers
        # (0-32/stat, <=66 total). Validate on the SP grain instead of 508/4.
        if detect_champions_format(pokemon_name):
            return await _check_spread_efficiency_champions(pokeapi,
                pokemon_name, base_stats, parsed_nature, nature,
                hp_evs, atk_evs, def_evs, spa_evs, spd_evs, spe_evs,
            )

        total = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
        issues = []
        suggestions = []

        # Check total EVs
        if total > 508:
            issues.append(f"Total EVs ({total}) exceed maximum of 508")
        elif total < 508:
            suggestions.append(f"You have {508 - total} EVs remaining to allocate")

        # Check for non-multiples of 4 (wasted EVs)
        evs = {
            "HP": hp_evs, "Attack": atk_evs, "Defense": def_evs,
            "Sp.Atk": spa_evs, "Sp.Def": spd_evs, "Speed": spe_evs
        }

        for stat_name, ev in evs.items():
            if ev % 4 != 0 and ev != 0:
                wasted = ev % 4
                issues.append(f"{stat_name}: {wasted} wasted EVs (not multiple of 4)")

        # Check for conflicting nature/EV investment
        nature_mods = {
            "attack": get_nature_modifier(parsed_nature, "attack"),
            "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
            "speed": get_nature_modifier(parsed_nature, "speed"),
        }

        if nature_mods["attack"] < 1.0 and atk_evs > 0:
            suggestions.append(f"Investing in Attack with -{nature} nature. Consider a neutral or +Atk nature.")

        if nature_mods["special_attack"] < 1.0 and spa_evs > 0:
            suggestions.append(f"Investing in Sp.Atk with -{nature} nature. Consider a neutral or +SpA nature.")

        # Calculate final stats
        final_stats = {
            "hp": calculate_hp(base_stats.hp, 31, hp_evs, 50),
            "attack": calculate_stat(base_stats.attack, 31, atk_evs, 50, nature_mods.get("attack", 1.0)),
            "defense": calculate_stat(base_stats.defense, 31, def_evs, 50, get_nature_modifier(parsed_nature, "defense")),
            "special_attack": calculate_stat(base_stats.special_attack, 31, spa_evs, 50, nature_mods.get("special_attack", 1.0)),
            "special_defense": calculate_stat(base_stats.special_defense, 31, spd_evs, 50, get_nature_modifier(parsed_nature, "special_defense")),
            "speed": calculate_stat(base_stats.speed, 31, spe_evs, 50, nature_mods.get("speed", 1.0)),
        }

        # Build summary table
        efficiency = "Valid" if total <= 508 and not any("wasted" in i for i in issues) else "Issues found"
        table_lines = [
            "| Metric           | Value                                      |",
            "|------------------|---------------------------------------------|",
            f"| Pokemon          | {pokemon_name}                             |",
            f"| Nature           | {nature}                                   |",
            f"| Total EVs        | {total}/508                                |",
            f"| EVs Remaining    | {max(0, 508 - total)}                      |",
            f"| Efficiency       | {efficiency}                               |",
        ]
        if issues and issues != ["No issues found"]:
            table_lines.append(f"| Issues           | {len(issues)} found                        |")

        # Build analysis prose
        issue_count = len([i for i in issues if "wasted" in i.lower() or "exceed" in i.lower()])
        if issue_count > 0:
            analysis_str = f"{pokemon_name}'s spread uses {total}/508 EVs — {issue_count} issue(s) found"
        else:
            analysis_str = f"{pokemon_name}'s spread uses {total}/508 EVs — {max(0, 508 - total)} remaining"

        # Generate Showdown paste for the analyzed spread
        types = await pokeapi.get_pokemon_types(pokemon_name)
        analyzed_pokemon = build_pokemon(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=parsed_nature,
            spread=EVSpread(
                hp=hp_evs,
                attack=atk_evs,
                defense=def_evs,
                special_attack=spa_evs,
                special_defense=spd_evs,
                speed=spe_evs
            ),
        )
        showdown_paste = pokemon_build_to_showdown(analyzed_pokemon)

        return {
            "pokemon": pokemon_name,
            "nature": nature,
            "total_evs": total,
            "remaining_evs": max(0, 508 - total),
            "final_stats": final_stats,
            "issues": issues if issues else ["No issues found"],
            "suggestions": suggestions if suggestions else ["Spread looks efficient!"],
            "is_valid": total <= 508 and not any("wasted" in i for i in issues),
            "showdown_paste": showdown_paste,
            "summary_table": "\n".join(table_lines),
            "analysis": analysis_str
        }

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def suggest_nature_optimization(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    current_nature: str,
    hp_evs: int = 0,
    atk_evs: int = 0,
    def_evs: int = 0,
    spa_evs: int = 0,
    spd_evs: int = 0,
    spe_evs: int = 0,
    moves: Optional[list[str]] = None,
    spread: Optional[str] = None,
) -> dict[str, Any]:
    if spread:
        try:
            hp_evs, atk_evs, def_evs, spa_evs, spd_evs, spe_evs = slash_values(spread)
        except ValueError as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(e))
    try:
        base_stats = await pokeapi.get_base_stats(pokemon_name)

        # Parse current nature
        try:
            current_nature_enum = Nature(current_nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {current_nature}')

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        # In a Champions session the *_evs args carry SP-scale numbers
        # (0-32/stat). Search for a nature that hits the same stats on the SP
        # grain with fewer total Stat Points.
        if detect_champions_format(pokemon_name):
            return await _suggest_nature_optimization_champions(pokeapi,
                pokemon_name, base_stats, current_nature, current_nature_enum,
                hp_evs, atk_evs, def_evs, spa_evs, spd_evs, spe_evs, moves,
            )

        # Calculate current final stats
        current_stats = {
            "hp": calculate_hp(base_stats.hp, 31, hp_evs, 50),
            "attack": calculate_stat(base_stats.attack, 31, atk_evs, 50, get_nature_modifier(current_nature_enum, "attack")),
            "defense": calculate_stat(base_stats.defense, 31, def_evs, 50, get_nature_modifier(current_nature_enum, "defense")),
            "special_attack": calculate_stat(base_stats.special_attack, 31, spa_evs, 50, get_nature_modifier(current_nature_enum, "special_attack")),
            "special_defense": calculate_stat(base_stats.special_defense, 31, spd_evs, 50, get_nature_modifier(current_nature_enum, "special_defense")),
            "speed": calculate_stat(base_stats.speed, 31, spe_evs, 50, get_nature_modifier(current_nature_enum, "speed"))
        }

        current_total_evs = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs

        # Determine if Pokemon is physical or special attacker
        is_physical = False
        is_special = False
        if moves:
            for move_name in moves:
                try:
                    move = await pokeapi.get_move(move_name)
                    if move.category == MoveCategory.PHYSICAL:
                        is_physical = True
                    elif move.category == MoveCategory.SPECIAL:
                        is_special = True
                except Exception:
                    continue

        # Try all natures and find the one that uses fewest EVs
        best_nature = None
        best_evs = None
        best_total_evs = current_total_evs
        best_stats = None

        for nature in Nature:
            # Skip current nature
            if nature == current_nature_enum:
                continue

            # Don't suggest -Atk for physical attackers
            if is_physical and get_nature_modifier(nature, "attack") < 1.0:
                continue

            # Don't suggest -SpA for special attackers
            if is_special and get_nature_modifier(nature, "special_attack") < 1.0:
                continue

            # Calculate minimum EVs needed to reach same stats
            new_hp_evs = _find_min_evs_for_hp(base_stats.hp, 31, current_stats["hp"], 50)
            new_atk_evs = _find_min_evs_for_stat(base_stats.attack, 31, current_stats["attack"], get_nature_modifier(nature, "attack"), 50)
            new_def_evs = _find_min_evs_for_stat(base_stats.defense, 31, current_stats["defense"], get_nature_modifier(nature, "defense"), 50)
            new_spa_evs = _find_min_evs_for_stat(base_stats.special_attack, 31, current_stats["special_attack"], get_nature_modifier(nature, "special_attack"), 50)
            new_spd_evs = _find_min_evs_for_stat(base_stats.special_defense, 31, current_stats["special_defense"], get_nature_modifier(nature, "special_defense"), 50)
            new_spe_evs = _find_min_evs_for_stat(base_stats.speed, 31, current_stats["speed"], get_nature_modifier(nature, "speed"), 50)

            new_total_evs = new_hp_evs + new_atk_evs + new_def_evs + new_spa_evs + new_spd_evs + new_spe_evs

            # Verify stats match (should be same or better)
            new_stats = {
                "hp": calculate_hp(base_stats.hp, 31, new_hp_evs, 50),
                "attack": calculate_stat(base_stats.attack, 31, new_atk_evs, 50, get_nature_modifier(nature, "attack")),
                "defense": calculate_stat(base_stats.defense, 31, new_def_evs, 50, get_nature_modifier(nature, "defense")),
                "special_attack": calculate_stat(base_stats.special_attack, 31, new_spa_evs, 50, get_nature_modifier(nature, "special_attack")),
                "special_defense": calculate_stat(base_stats.special_defense, 31, new_spd_evs, 50, get_nature_modifier(nature, "special_defense")),
                "speed": calculate_stat(base_stats.speed, 31, new_spe_evs, 50, get_nature_modifier(nature, "speed"))
            }

            # Check if stats are same or better in important stats
            # For physical attackers, Attack and Speed must be same or better
            # For special attackers, SpA and Speed must be same or better
            # HP and defenses should generally be same or better
            stats_match = True

            # HP should be same or better
            if new_stats["hp"] < current_stats["hp"]:
                stats_match = False

            # Attack must be same or better for physical attackers
            if is_physical and new_stats["attack"] < current_stats["attack"]:
                stats_match = False

            # Special Attack must be same or better for special attackers
            if is_special and new_stats["special_attack"] < current_stats["special_attack"]:
                stats_match = False

            # Speed should generally be same or better (unless Trick Room)
            if new_stats["speed"] < current_stats["speed"]:
                stats_match = False

            # Defenses can be slightly worse if it saves significant EVs
            # But only if the loss is minimal (1-2 points)
            if new_stats["defense"] < current_stats["defense"] - 2:
                stats_match = False
            if new_stats["special_defense"] < current_stats["special_defense"] - 2:
                stats_match = False

            if stats_match and new_total_evs < best_total_evs:
                best_nature = nature
                best_evs = {
                    "hp": new_hp_evs,
                    "attack": new_atk_evs,
                    "defense": new_def_evs,
                    "special_attack": new_spa_evs,
                    "special_defense": new_spd_evs,
                    "speed": new_spe_evs
                }
                best_total_evs = new_total_evs
                best_stats = new_stats

        # If no better nature found
        if best_nature is None:
            return {
                "pokemon": pokemon_name,
                "current_nature": current_nature,
                "optimization_found": False,
                "message": "Your nature is already optimal! No EV savings possible.",
                "markdown_summary": f"## Nature Optimization: {pokemon_name.title()}\n\n### Result\nYour current nature ({current_nature.title()}) is already optimal. No EV savings possible with a different nature."
            }

        ev_savings = current_total_evs - best_total_evs

        # Build markdown output
        markdown_lines = [
            f"## Nature Optimization: {pokemon_name.title()}",
            "",
            "### Current Build",
            "| Nature | HP | Atk | Def | SpA | SpD | Spe | Total EVs |",
            "|--------|-----|-----|-----|-----|-----|-----|-----------|",
            f"| {current_nature.title()} | {hp_evs} | {atk_evs} | {def_evs} | {spa_evs} | {spd_evs} | {spe_evs} | **{current_total_evs}** |",
            "",
            "### Final Stats (Current)",
            "| HP | Atk | Def | SpA | SpD | Spe |",
            "|----|-----|-----|-----|-----|-----|",
            f"| {current_stats['hp']} | {current_stats['attack']} | {current_stats['defense']} | "
            f"{current_stats['special_attack']} | {current_stats['special_defense']} | {current_stats['speed']} |",
            "",
            "---",
            "",
            "### Suggested Optimization",
            "",
            f"**Use {best_nature.value.title().replace('_', ' ')} ({best_nature.value.split('_')[0].title() if '_' in best_nature.value else best_nature.value.title()}, "
            f"-{best_nature.value.split('_')[1].title() if '_' in best_nature.value else 'Atk'}) to save {ev_savings} EVs!**",
            "",
            "| Nature | HP | Atk | Def | SpA | SpD | Spe | Total EVs |",
            "|--------|-----|-----|-----|-----|-----|-----|-----------|",
            f"| {best_nature.value.title().replace('_', ' ')} | {best_evs['hp']} | **{best_evs['attack']}** | {best_evs['defense']} | "
            f"{best_evs['special_attack']} | {best_evs['special_defense']} | **{best_evs['speed']}** | **{best_total_evs}** |",
            "",
            "### Final Stats (Optimized) - SAME OR BETTER",
            "| HP | Atk | Def | SpA | SpD | Spe |",
            "|----|-----|-----|-----|-----|-----|",
            f"| {best_stats['hp']} | **{best_stats['attack']}** | {best_stats['defense']} | "
            f"{best_stats['special_attack']} | {best_stats['special_defense']} | {best_stats['speed']} |",
            "",
            "### What Changed"
        ]

        # Show what changed
        if best_stats['attack'] != current_stats['attack']:
            diff = best_stats['attack'] - current_stats['attack']
            markdown_lines.append(f"- Attack: {current_stats['attack']} → {best_stats['attack']} ({'+' if diff > 0 else ''}{diff}) - Nature boost compensates for fewer EVs")

        if best_stats['special_attack'] != current_stats['special_attack']:
            diff = best_stats['special_attack'] - current_stats['special_attack']
            spa_reason = "Not used for special moves" if is_physical else "Nature adjustment"
            markdown_lines.append(f"- Sp.Atk: {current_stats['special_attack']} → {best_stats['special_attack']} ({'+' if diff > 0 else ''}{diff}) - {spa_reason}")

        if best_stats['speed'] != current_stats['speed']:
            diff = best_stats['speed'] - current_stats['speed']
            markdown_lines.append(f"- Speed: {current_stats['speed']} → {best_stats['speed']} ({'+' if diff > 0 else ''}{diff}) - Nature adjustment")

        markdown_lines.extend([
            f"- **{ev_savings} EVs freed up** for other stats!",
            "",
            "### Where to Invest Saved EVs",
            f"With {ev_savings} extra EVs, you could:"
        ])

        # Suggest where to invest saved EVs
        if best_stats['hp'] < 400:  # Reasonable HP cap
            hp_gain = calculate_hp(base_stats.hp, 31, best_evs['hp'] + ev_savings, 50) - best_stats['hp']
            markdown_lines.append(f"- Add {ev_savings} to HP ({best_stats['hp']} → {best_stats['hp'] + hp_gain}) for more bulk")

        if best_stats['defense'] < 300:
            def_gain = calculate_stat(base_stats.defense, 31, best_evs['defense'] + ev_savings, 50, get_nature_modifier(best_nature, "defense")) - best_stats['defense']
            markdown_lines.append(f"- Add {ev_savings} to Def ({best_stats['defense']} → {best_stats['defense'] + def_gain}) to survive physical hits")

        if best_stats['special_defense'] < 300:
            spd_gain = calculate_stat(base_stats.special_defense, 31, best_evs['special_defense'] + ev_savings, 50, get_nature_modifier(best_nature, "special_defense")) - best_stats['special_defense']
            markdown_lines.append(f"- Add {ev_savings} to SpD ({best_stats['special_defense']} → {best_stats['special_defense'] + spd_gain}) to survive special hits")

        # Generate Showdown pastes for both current and optimized spreads
        types = await pokeapi.get_pokemon_types(pokemon_name)

        # Build current Pokemon
        current_pokemon = build_pokemon(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=current_nature_enum,
            spread=EVSpread(
                hp=hp_evs,
                attack=atk_evs,
                defense=def_evs,
                special_attack=spa_evs,
                special_defense=spd_evs,
                speed=spe_evs
            ),
        )
        current_showdown = pokemon_build_to_showdown(current_pokemon)

        # Build optimized Pokemon
        optimized_pokemon = build_pokemon(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=best_nature,
            spread=EVSpread(
                hp=best_evs["hp"],
                attack=best_evs["attack"],
                defense=best_evs["defense"],
                special_attack=best_evs["special_attack"],
                special_defense=best_evs["special_defense"],
                speed=best_evs["speed"]
            ),
        )
        optimized_showdown = pokemon_build_to_showdown(optimized_pokemon)

        response = {
            "pokemon": pokemon_name,
            "current_nature": current_nature,
            "current_evs": {
                "hp": hp_evs,
                "attack": atk_evs,
                "defense": def_evs,
                "special_attack": spa_evs,
                "special_defense": spd_evs,
                "speed": spe_evs
            },
            "current_total_evs": current_total_evs,
            "current_stats": current_stats,
            "current_showdown_paste": current_showdown,
            "suggested_nature": best_nature.value,
            "suggested_evs": best_evs,
            "suggested_total_evs": best_total_evs,
            "suggested_stats": best_stats,
            "optimized_showdown_paste": optimized_showdown,
            "ev_savings": ev_savings,
            "optimization_found": True,
            "markdown_summary": "\n".join(markdown_lines)
        }

        return response

    except Exception as e:
        logger.error(f"Error in suggest_nature_optimization: {e}", exc_info=True)
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def optimize_bulk(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    nature: str,
    total_bulk_evs: int = 252,
    defense_bias: float = 0.5,
    item: Optional[str] = None,
    include_analysis: bool = False,
) -> dict[str, Any]:
    try:
        base_stats = await pokeapi.get_base_stats(pokemon_name)

        try:
            parsed_nature = Nature(nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        if detect_champions_format(pokemon_name):
            # Default EV budget (252) maps to the full SP bulk budget (66);
            # an explicit smaller request is clamped onto the SP scale.
            total_bulk_sps = SP_TOTAL_MAX if total_bulk_evs == 252 else min(SP_TOTAL_MAX, total_bulk_evs)
            return await _optimize_bulk_champions(pokeapi,
                pokemon_name, base_stats, parsed_nature, total_bulk_sps, defense_bias, item
            )

        # Simple optimization: balance HP with defenses based on bias
        # General rule: invest in HP until it's ~2x each defense stat

        best_spread = None
        best_bulk = 0

        # Try different distributions (level 50 breakpoints: 0, 4, 12, 20, 28...)
        for hp_ev in EV_BREAKPOINTS_LV50:
            if hp_ev > min(252, total_bulk_evs):
                break
            remaining = total_bulk_evs - hp_ev
            for def_ev in EV_BREAKPOINTS_LV50:
                if def_ev > min(252, remaining):
                    break
                spd_ev = normalize_evs(remaining - def_ev)
                if spd_ev < 0:
                    continue

                hp = calculate_hp(base_stats.hp, 31, hp_ev, 50)
                def_stat = calculate_stat(
                    base_stats.defense, 31, def_ev, 50,
                    get_nature_modifier(parsed_nature, "defense")
                )
                spd_stat = calculate_stat(
                    base_stats.special_defense, 31, spd_ev, 50,
                    get_nature_modifier(parsed_nature, "special_defense")
                )

                # Calculate effective bulk (HP * Def for physical, HP * SpD for special)
                phys_bulk = hp * def_stat
                spec_bulk = hp * spd_stat
                total_bulk = phys_bulk * defense_bias + spec_bulk * (1 - defense_bias)

                if total_bulk > best_bulk:
                    best_bulk = total_bulk
                    best_spread = {
                        "hp_evs": hp_ev,
                        "def_evs": def_ev,
                        "spd_evs": spd_ev,
                        "final_hp": hp,
                        "final_def": def_stat,
                        "final_spd": spd_stat,
                        "physical_bulk": phys_bulk,
                        "special_bulk": spec_bulk
                    }

        # HP number optimization for item
        hp_optimization = None
        if item and best_spread:
            from vgc_mcp_core.calc.hp_optimization import adjust_hp_evs_for_item
            hp_adj = adjust_hp_evs_for_item(base_stats.hp, best_spread["hp_evs"], item)
            if hp_adj["adjusted_evs"] != best_spread["hp_evs"]:
                best_spread["hp_evs"] = hp_adj["adjusted_evs"]
                best_spread["final_hp"] = hp_adj["adjusted_hp"]
                best_spread["physical_bulk"] = hp_adj["adjusted_hp"] * best_spread["final_def"]
                best_spread["special_bulk"] = hp_adj["adjusted_hp"] * best_spread["final_spd"]
                hp_optimization = hp_adj

        # Build summary table
        if best_spread:
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Pokemon          | {pokemon_name}                             |",
                f"| Nature           | {nature}                                   |",
                f"| HP EVs           | {best_spread['hp_evs']}                    |",
                f"| Defense EVs      | {best_spread['def_evs']}                   |",
                f"| SpDef EVs        | {best_spread['spd_evs']}                   |",
                f"| Final HP         | {best_spread['final_hp']}                  |",
                f"| Final Def        | {best_spread['final_def']}                 |",
                f"| Final SpD        | {best_spread['final_spd']}                 |",
                f"| Physical Bulk    | {best_spread['physical_bulk']}             |",
                f"| Special Bulk     | {best_spread['special_bulk']}              |",
            ]
        else:
            table_lines = ["| No optimal spread found |"]

        # Build analysis prose
        if best_spread:
            analysis_str = f"Optimal bulk: {best_spread['hp_evs']} HP / {best_spread['def_evs']} Def / {best_spread['spd_evs']} SpD for {pokemon_name}"
        else:
            analysis_str = f"No optimal spread found for {pokemon_name}"

        # Generate Showdown paste if spread found
        showdown_paste = None
        if best_spread:
            types = await pokeapi.get_pokemon_types(pokemon_name)
            optimized_pokemon = build_pokemon(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=parsed_nature,
                spread=EVSpread(
                    hp=best_spread["hp_evs"],
                    attack=0,
                    defense=best_spread["def_evs"],
                    special_attack=0,
                    special_defense=best_spread["spd_evs"],
                    speed=0
                ),
            )
            showdown_paste = pokemon_build_to_showdown(optimized_pokemon)

        result = {
            "pokemon": pokemon_name,
            "nature": nature,
            "total_bulk_evs": total_bulk_evs,
            "defense_bias": defense_bias,
            "optimal_spread": best_spread,
            "showdown_paste": showdown_paste,
            "summary_table": "\n".join(table_lines),
            "analysis": analysis_str,
        }
        if hp_optimization:
            result["hp_optimization"] = hp_optimization
        if include_analysis and best_spread:
            result.update(_bulk_analysis(base_stats, parsed_nature, total_bulk_evs, best_spread, defense_bias))
        return result

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def suggest_spread(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    role: str = 'offensive',
    speed_target: Optional[int] = None,
    item: Optional[str] = None,
) -> dict[str, Any]:
    try:
        base_stats = await pokeapi.get_base_stats(pokemon_name)

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        if detect_champions_format(pokemon_name):
            return await _suggest_spread_champions(pokeapi,
                pokemon_name, base_stats, role, speed_target, item
            )

        # Determine if physical or special attacker
        is_physical = base_stats.attack > base_stats.special_attack
        is_special = base_stats.special_attack > base_stats.attack
        offensive_stat = "Attack" if is_physical else "Sp. Atk"

        # Use intelligent nature selection for offensive role
        nature_name = "Jolly" if is_physical else "Timid"  # Default fallback
        nature_reasoning = None

        if role == "offensive":
            from vgc_mcp_core.calc.nature_optimization import find_optimal_nature_for_benchmarks

            benchmarks = {
                "speed_target": speed_target,
                "prioritize": "offense",
                "offensive_evs": 252,
                "speed_evs": 252
            }

            nature_result = find_optimal_nature_for_benchmarks(
                base_stats=base_stats,
                benchmarks=benchmarks,
                is_physical=is_physical,
                is_special=is_special,
                role="offensive"
            )

            if nature_result:
                nature_name = nature_result.best_nature.value.title()
                nature_reasoning = nature_result.reasoning

        spreads = {
            "offensive": {
                "description": f"Max {offensive_stat} and Speed for maximum damage output",
                "nature": nature_name,
                "evs": {
                    "hp": 0,
                    "attack": 252 if is_physical else 0,
                    "defense": 0,
                    "special_attack": 0 if is_physical else 252,
                    "special_defense": 4,
                    "speed": 252
                }
            },
            "bulky": {
                "description": "Maximum HP with balanced defenses",
                "nature": "Calm" if base_stats.special_defense > base_stats.defense else "Bold",
                "evs": {
                    "hp": 252,
                    "attack": 0,
                    "defense": 128,
                    "special_attack": 0,
                    "special_defense": 128,
                    "speed": 0
                }
            },
            "bulky_offense": {
                "description": f"Some bulk while maintaining {offensive_stat}",
                "nature": "Adamant" if is_physical else "Modest",
                "evs": {
                    "hp": 252,
                    "attack": 252 if is_physical else 0,
                    "defense": 0,
                    "special_attack": 0 if is_physical else 252,
                    "special_defense": 4,
                    "speed": 0
                }
            },
            "support": {
                "description": "Maximum bulk for supporting the team",
                "nature": "Bold",
                "evs": {
                    "hp": 252,
                    "attack": 0,
                    "defense": 252,
                    "special_attack": 0,
                    "special_defense": 4,
                    "speed": 0
                }
            }
        }

        if role not in spreads:
            return error_response(ErrorCodes.INTERNAL_ERROR, f'Unknown role: {role}. Use: offensive, bulky, bulky_offense, support')

        spread = spreads[role]

        # If speed target specified, adjust
        if speed_target and role == "offensive":
            # Calculate EVs needed
            nature = Nature(spread["nature"].lower())
            needed = find_speed_evs(base_stats.speed, speed_target, nature)

            if needed is not None and needed < 252:
                leftover = normalize_evs(252 - needed)
                spread["evs"]["speed"] = normalize_evs(needed)
                spread["evs"]["hp"] = leftover
                spread["description"] += f" (Speed creep to {speed_target})"

        # HP number optimization for item
        hp_optimization = None
        if item and spread["evs"]["hp"] > 0:
            from vgc_mcp_core.calc.hp_optimization import adjust_hp_evs_for_item
            hp_adj = adjust_hp_evs_for_item(base_stats.hp, spread["evs"]["hp"], item)
            if hp_adj["adjusted_evs"] != spread["evs"]["hp"]:
                spread["evs"]["hp"] = hp_adj["adjusted_evs"]
                hp_optimization = hp_adj

        # Generate Showdown paste for suggested spread
        types = await pokeapi.get_pokemon_types(pokemon_name)
        nature_enum = Nature(spread["nature"].lower())

        suggested_pokemon = build_pokemon(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=nature_enum,
            spread=EVSpread(
                hp=spread["evs"]["hp"],
                attack=spread["evs"]["attack"],
                defense=spread["evs"]["defense"],
                special_attack=spread["evs"]["special_attack"],
                special_defense=spread["evs"]["special_defense"],
                speed=spread["evs"]["speed"]
            ),
        )
        showdown_paste = pokemon_build_to_showdown(suggested_pokemon)

        result = {
            "pokemon": pokemon_name,
            "role": role,
            "suggestion": spread,
            "base_stats": {
                "hp": base_stats.hp,
                "attack": base_stats.attack,
                "defense": base_stats.defense,
                "special_attack": base_stats.special_attack,
                "special_defense": base_stats.special_defense,
                "speed": base_stats.speed
            },
            "showdown_paste": showdown_paste
        }

        if nature_reasoning:
            result["nature_selection_reasoning"] = nature_reasoning
        if hp_optimization:
            result["hp_optimization"] = hp_optimization

        return result

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def optimize_bulk_math(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    nature: str,
    total_bulk_evs: int = 252,
    defense_weight: float = 0.5,
    item: Optional[str] = None,
) -> dict[str, Any]:
    """Deprecated alias: optimize_bulk with the analysis block included."""
    result = await optimize_bulk(
        pokeapi, pokemon_name, nature, total_bulk_evs, defense_bias=defense_weight,
        item=item, include_analysis=True,
    )
    if "error" not in result:
        result["defense_weight"] = defense_weight
    return result


def _bulk_analysis(base_stats: BaseStats, nature: Nature, total_bulk_evs: int,
                   spread: dict[str, Any], weight: float) -> dict[str, Any]:
    """Final stats, weighted bulk and gain vs single-stat investment for a spread."""
    hp, def_stat, spd_stat = spread["final_hp"], spread["final_def"], spread["final_spd"]
    phys, spec = hp * def_stat, hp * spd_stat
    def_mod = get_nature_modifier(nature, "defense")
    spd_mod = get_nature_modifier(nature, "special_defense")
    naive_evs = min(252, total_bulk_evs)
    all_hp = calculate_hp(base_stats.hp, 31, naive_evs, 50) * calculate_stat(base_stats.defense, 31, 0, 50, def_mod)
    all_def = calculate_hp(base_stats.hp, 31, 0, 50) * calculate_stat(base_stats.defense, 31, naive_evs, 50, def_mod)
    efficiency = phys / max(all_hp, all_def) if max(all_hp, all_def) else 1.0
    if base_stats.hp > base_stats.defense + 20:
        parts = [f"High base HP ({base_stats.hp}) means investing more in Defense is efficient"]
    elif base_stats.defense > base_stats.hp + 20:
        parts = [f"High base Defense ({base_stats.defense}) means investing more in HP is efficient"]
    else:
        parts = [f"Balanced bases ({base_stats.hp} HP, {base_stats.defense} Def) benefit from split investment"]
    if def_mod > 1:
        parts.append("Defense-boosting nature reduces need for Defense EVs")
    elif spd_mod > 1:
        parts.append("SpD-boosting nature reduces need for SpD EVs")
    if efficiency > 1.05:
        parts.append(f"Optimal distribution is {(efficiency - 1) * 100:.1f}% more efficient than single-stat investment")
    return {
        "base_stats": {"hp": base_stats.hp, "defense": base_stats.defense,
                       "special_defense": base_stats.special_defense},
        "final_stats": {"hp": hp, "defense": def_stat, "special_defense": spd_stat},
        "bulk_scores": {"physical_bulk": phys, "special_bulk": spec,
                        "total_bulk": int(phys * weight + spec * (1 - weight))},
        "efficiency_score": round(efficiency, 3),
        "explanation": " | ".join(parts),
        "comparison_vs_naive": {
            "all_hp_bulk": all_hp,
            "all_def_bulk": all_def,
            "optimal_bulk": phys,
            "efficiency_gain_vs_all_hp": round((phys / all_hp - 1) * 100, 1) if all_hp else 0,
            "efficiency_gain_vs_all_def": round((phys / all_def - 1) * 100, 1) if all_def else 0,
        },
    }


async def analyze_bulk_diminishing_returns(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    nature: str,
) -> dict[str, Any]:
    try:
        base_stats = await pokeapi.get_base_stats(pokemon_name)

        try:
            Nature(nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

        analysis = analyze_diminishing_returns(
            base_hp=base_stats.hp,
            base_def=base_stats.defense,
            base_spd=base_stats.special_defense,
            nature=nature
        )

        return {
            "pokemon": pokemon_name,
            "nature": nature,
            "base_stats": {
                "hp": base_stats.hp,
                "defense": base_stats.defense,
                "special_defense": base_stats.special_defense
            },
            "marginal_gains": {
                "hp": analysis["hp_gains"],
                "defense": analysis["def_gains"],
                "special_defense": analysis["spd_gains"]
            },
            "recommendations": analysis["recommendations"],
            "interpretation": (
                "Higher marginal gain means better EV efficiency at that threshold. "
                "Invest where marginal gains are highest, then balance."
            )
        }

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def analyze_hp_number(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    item: str,
    current_hp_evs: int = 0,
) -> dict[str, Any]:
    try:
        from vgc_mcp_core.calc.hp_optimization import (
            adjust_hp_evs_for_item,
            find_optimal_hp_evs,
            score_hp_for_item,
        )

        base = await pokeapi.get_base_stats(pokemon_name)
        current_hp = calculate_hp(base.hp, 31, current_hp_evs, 50)
        current_score = score_hp_for_item(current_hp, item)

        # Get all optimal EV options
        all_options = find_optimal_hp_evs(base.hp, item)

        # Filter to show only the best options (score == 1.0)
        optimal_options = [o for o in all_options if o["score"] == 1.0]

        # Get adjustment recommendation
        adjustment = adjust_hp_evs_for_item(base.hp, current_hp_evs, item)

        # Build recommendation text
        if current_score == 1.0:
            recommendation = (
                f"Your current {current_hp_evs} HP EVs ({current_hp} HP) "
                f"is already optimal for {item}!"
            )
        elif optimal_options:
            closest = min(
                optimal_options,
                key=lambda o: abs(o["ev"] - current_hp_evs),
            )
            ev_diff = closest["ev"] - current_hp_evs
            direction = "more" if ev_diff > 0 else "fewer"
            recommendation = (
                f"Use {closest['ev']} HP EVs ({closest['hp_stat']} HP) "
                f"for optimal {item} number. "
                f"That's {abs(ev_diff)} {direction} EVs than current."
            )
        else:
            recommendation = f"No specific HP optimization applies for {item}."

        # Calculate item-specific info
        item_lower = item.lower().replace(" ", "-")
        item_info = {}
        if item_lower in ("leftovers", "black-sludge"):
            item_info["recovery_per_turn"] = current_hp // 16
            item_info["recovery_percent"] = round((current_hp // 16) / current_hp * 100, 2) if current_hp > 0 else 0
        elif item_lower == "life-orb":
            item_info["recoil_per_attack"] = current_hp // 10
            item_info["recoil_percent"] = round((current_hp // 10) / current_hp * 100, 2) if current_hp > 0 else 0
            item_info["attacks_before_ko"] = current_hp // max(1, current_hp // 10)
        elif item_lower == "sitrus-berry":
            item_info["heal_amount"] = current_hp // 4
            item_info["heal_percent"] = round((current_hp // 4) / current_hp * 100, 2) if current_hp > 0 else 0

        return {
            "pokemon": pokemon_name,
            "item": item,
            "base_hp": base.hp,
            "current_hp_evs": current_hp_evs,
            "current_hp_stat": current_hp,
            "current_score": round(current_score, 3),
            "item_info": item_info,
            "optimal_hp_options": optimal_options[:8],
            "adjustment": adjustment,
            "recommendation": recommendation,
        }

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
