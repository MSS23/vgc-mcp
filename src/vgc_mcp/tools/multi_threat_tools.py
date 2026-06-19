"""MCP tools for multi-threat bulk calculations."""

from typing import Optional, List, Dict
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, StatPointSpread, BaseStats
from vgc_mcp_core.models.move import Move
from vgc_mcp_core.tools.ability_helpers import (
    resolve_ability,
    compute_intimidate_attack_stage,
)
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error, error_response, ErrorCodes
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50
from vgc_mcp_core.calc.stats_champions import SP_BREAKPOINTS_LV50
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


def _detect_champions(pokemon_name: Optional[str] = None) -> bool:
    """Return True when the active session is the Champions (Reg MA) SP system.

    Mirrors spread_tools._detect_champions: reads the session regulation's
    format system, optionally running Pokemon-name inference first so a Mega /
    Reg MA mention auto-selects Champions. Mainline path is taken when False.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(pokemon_name)


def register_multi_threat_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon_client=None):
    """Register multi-threat bulk calculation tools with the MCP server."""

    @mcp.tool()
    async def find_multi_threat_bulk_evs(
        pokemon_name: str,
        threats: List[Dict],
        nature: str = "bold",
        item: Optional[str] = None,
        ability: Optional[str] = None,
        target_survival_chance: float = 100.0
    ) -> dict:
        """
        Find minimum EVs to survive multiple threats simultaneously.
        
        This tool calculates the optimal HP and defensive EV distribution
        that allows a Pokemon to survive all specified threats.
        
        Args:
            pokemon_name: Name of the Pokemon to optimize
            threats: List of threat dicts, each with:
                - name: Attacker Pokemon name
                - move: Move name
                - spread (optional): Dict with nature, evs, item, ability
                    If not provided, uses most common Smogon spread
            nature: Nature for the defender (default: "bold")
            item: Item for the defender (optional)
            ability: Ability for the defender (optional, auto-detected if None)
            target_survival_chance: Target survival % (100 = guaranteed survive)
            
        Returns:
            Dict with recommended spread and survival results for each threat
        """
        try:
            # Fetch defender Pokemon data
            def_base = await pokeapi.get_base_stats(pokemon_name)
            def_types = await pokeapi.get_pokemon_types(pokemon_name)
            
            ability, ability_source = await resolve_ability(
                pokemon_name, pokeapi=pokeapi, smogon_client=smogon_client,
                user_override=ability,
            )
            
            try:
                def_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')
            
            # Parse and validate threats
            parsed_threats = []
            for i, threat in enumerate(threats):
                if not isinstance(threat, dict):
                    return error_response(ErrorCodes.INVALID_PARAMETER, f"Threat {i + 1} must be a dict with 'name' and 'move' keys")
                
                threat_name = threat.get("name")
                threat_move = threat.get("move")
                if not threat_name or not threat_move:
                    return error_response(ErrorCodes.INTERNAL_ERROR, f"Threat {i + 1} missing 'name' or 'move'")
                
                parsed_threats.append({
                    "name": threat_name,
                    "move": threat_move,
                    "spread": threat.get("spread")  # Optional custom spread
                })
            
            # Fetch threat data and build attacker Pokemon
            threat_builds = []
            for threat in parsed_threats:
                try:
                    atk_base = await pokeapi.get_base_stats(threat["name"])
                    atk_types = await pokeapi.get_pokemon_types(threat["name"])
                    move = await pokeapi.get_move(threat["move"])
                    
                    # Use custom spread if provided, otherwise use defaults
                    spread = threat.get("spread") or {}
                    threat_nature = Nature(spread.get("nature", "serious").lower())
                    threat_evs = spread.get("evs", {})
                    threat_item = spread.get("item")
                    threat_ability = spread.get("ability")
                    
                    threat_ability, _ = await resolve_ability(
                        threat["name"], pokeapi=pokeapi, smogon_client=smogon_client,
                        user_override=threat_ability,
                    )

                    threat_build = PokemonBuild(
                        name=threat["name"],
                        base_stats=atk_base,
                        types=atk_types,
                        nature=threat_nature,
                        evs=EVSpread(**threat_evs),
                        item=threat_item,
                        ability=threat_ability
                    )

                    is_physical = move.category.value == "physical"
                    intim_stage, intim_note = compute_intimidate_attack_stage(
                        defender_ability=ability,
                        attacker_ability=threat_ability,
                        is_physical=is_physical,
                    )

                    threat_builds.append({
                        "build": threat_build,
                        "move": move,
                        "name": threat["name"],
                        "move_name": threat["move"],
                        "is_physical": is_physical,
                        "intimidate_stage": intim_stage,
                        "intimidate_note": intim_note,
                        "attacker_ability": threat_ability,
                        "attacker_item": threat_item,
                    })
                except Exception as e:
                    logger.warning(f"Failed to build threat {threat['name']}: {e}")
                    return error_response(ErrorCodes.INTERNAL_ERROR, f"Failed to process threat {threat['name']}: {str(e)}")
            
            # Champions: the USER'S defender becomes a Champions SP build and we
            # sweep the SP grain (0-32 per stat, 66 total). The threats above
            # stay mainline (their user-supplied / Smogon EV spreads).
            # calculate_damage reads each build's own format_system, so a
            # champions defender vs mainline attackers is correct. Mainline keeps
            # the EV sweep (0-252 per stat, 508 total) byte-for-byte. Loop vars
            # stay named *_ev but hold SP units in the champions branch.
            is_champions = _detect_champions(pokemon_name)
            breakpoints = SP_BREAKPOINTS_LV50 if is_champions else EV_BREAKPOINTS_LV50
            total_budget = 66 if is_champions else 508

            # Try different EV/SP combinations to find minimum that survives all threats
            best_spread = None
            best_results = None

            # Try all valid breakpoint combinations
            for hp_ev in breakpoints:
                for def_ev in breakpoints:
                    for spd_ev in breakpoints:
                        total_evs = hp_ev + def_ev + spd_ev
                        if total_evs > total_budget:
                            continue

                        # Create test defender build
                        if is_champions:
                            test_defender = PokemonBuild(
                                name=pokemon_name,
                                base_stats=def_base,
                                types=def_types,
                                nature=def_nature,
                                format_system="champions",
                                sps=StatPointSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                                item=item,
                                ability=ability
                            )
                        else:
                            test_defender = PokemonBuild(
                                name=pokemon_name,
                                base_stats=def_base,
                                types=def_types,
                                nature=def_nature,
                                evs=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                                item=item,
                                ability=ability
                            )
                        
                        # Test against all threats
                        threat_results = []
                        all_survive = True
                        
                        for threat_data in threat_builds:
                            mods = DamageModifiers(
                                is_doubles=True,
                                attack_stage=threat_data["intimidate_stage"] if threat_data["is_physical"] else 0,
                                attacker_ability=threat_data["attacker_ability"],
                                attacker_item=threat_data["attacker_item"],
                            )
                            result = calculate_damage(
                                threat_data["build"],
                                test_defender,
                                threat_data["move"],
                                mods,
                            )
                            
                            # Calculate survival chance
                            survives = sum(1 for r in result.rolls if r < result.defender_hp)
                            survival_pct = (survives / 16) * 100
                            
                            threat_results.append({
                                "threat_name": threat_data["name"],
                                "move_name": threat_data["move_name"],
                                "damage_range": result.damage_range,
                                "survival_chance": survival_pct,
                                "survives": survival_pct >= target_survival_chance
                            })
                            
                            if survival_pct < target_survival_chance:
                                all_survive = False
                                break
                        
                        # If this spread survives all threats, check if it's better (fewer EVs)
                        if all_survive:
                            if best_spread is None or total_evs < sum([
                                best_spread["hp_evs"],
                                best_spread["def_evs"],
                                best_spread["spd_evs"]
                            ]):
                                best_spread = {
                                    "hp_evs": hp_ev,
                                    "def_evs": def_ev,
                                    "spd_evs": spd_ev,
                                    "total_evs": total_evs
                                }
                                best_results = threat_results
                                
                                # Early exit if we found a minimal spread (0 EVs)
                                if total_evs == 0:
                                    break
                        
                        # Early exit optimization: if we found a good spread, stop searching
                        if best_spread and total_evs > best_spread["total_evs"] + 100:
                            break
                
                # Early exit optimization
                if best_spread and hp_ev > best_spread["hp_evs"] + 100:
                    break
            
            if best_spread is None:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, 'Could not find a spread that survives all threats with the given constraints', threats=[t['name'] for t in parsed_threats])
            
            # Recommended defender build for the showdown paste. Champions emits
            # an 'SPs:' paste (32/stat, 66 total); mainline keeps the EVs paste.
            if is_champions:
                recommended_defender = PokemonBuild(
                    name=pokemon_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    format_system="champions",
                    sps=StatPointSpread(
                        hp=best_spread["hp_evs"],
                        defense=best_spread["def_evs"],
                        special_defense=best_spread["spd_evs"],
                    ),
                    item=item,
                    ability=ability
                )
                recommended_spread = {
                    "hp_sps": best_spread["hp_evs"],
                    "def_sps": best_spread["def_evs"],
                    "spd_sps": best_spread["spd_evs"],
                    "total_sps": best_spread["total_evs"],
                    "leftover_sps": 66 - best_spread["total_evs"],
                }
            else:
                recommended_defender = PokemonBuild(
                    name=pokemon_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    evs=EVSpread(
                        hp=best_spread["hp_evs"],
                        defense=best_spread["def_evs"],
                        special_defense=best_spread["spd_evs"],
                    ),
                    item=item,
                    ability=ability
                )
                recommended_spread = {
                    "hp_evs": best_spread["hp_evs"],
                    "def_evs": best_spread["def_evs"],
                    "spd_evs": best_spread["spd_evs"],
                    "total_evs": best_spread["total_evs"],
                    "leftover_evs": 508 - best_spread["total_evs"]
                }

            # Format response
            response = {
                "pokemon": pokemon_name,
                "nature": nature.title(),
                "item": item or "None",
                "ability": ability.replace("-", " ").title() if ability else "None",
                "ability_source": ability_source,
                "format_system": "champions" if is_champions else "mainline",
                "units": "Stat Points" if is_champions else "EVs",
                "intimidate_active_against": [
                    t["name"] for t in threat_builds if t["intimidate_note"]
                ],
                "recommended_spread": recommended_spread,
                "showdown_paste": pokemon_build_to_showdown(recommended_defender),
                "survival_results": best_results,
                "all_survive": all(r["survives"] for r in best_results)
            }
            
            # Build markdown summary
            markdown_lines = [
                f"## Multi-Threat Bulk Analysis: {pokemon_name.title()}",
                "",
                "### Threats to Survive",
                "| # | Attacker | Move | Their Spread |",
                "|---|----------|------|--------------|"
            ]
            
            for i, threat_data in enumerate(threat_builds, 1):
                threat_name = threat_data["name"]
                move_name = threat_data["move_name"]
                spread_info = parsed_threats[i-1].get("spread", {})
                if spread_info:
                    spread_str = f"{spread_info.get('nature', 'Serious')} {spread_info.get('evs', {})}"
                else:
                    spread_str = "Common Smogon"
                markdown_lines.append(f"| {i} | {threat_name.title()} | {move_name.title()} | {spread_str} |")
            
            markdown_lines.extend([
                "",
                "### Recommended Spread",
                "| Nature | HP | Atk | Def | SpA | SpD | Spe |",
                "|--------|-----|-----|-----|-----|-----|-----|",
                f"| {nature.title()} | {best_spread['hp_evs']} | 0 | {best_spread['def_evs']} | 0 | {best_spread['spd_evs']} | 0 |",
                "",
                "### Survival Results",
                "| Threat | Damage | Survives? |",
                "|--------|--------|-----------|"
            ])
            
            for result in best_results:
                checkmark = "✓" if result["survives"] else "✗"
                markdown_lines.append(
                    f"| {result['threat_name'].title()} {result['move_name'].title()} | "
                    f"{result['damage_range']} | {checkmark} |"
                )
            
            if is_champions:
                markdown_lines.extend([
                    "",
                    f"**SP Used:** {best_spread['total_evs']}/66",
                    f"**Leftover SP:** {66 - best_spread['total_evs']}"
                ])
            else:
                markdown_lines.extend([
                    "",
                    f"**EVs Used:** {best_spread['total_evs']}/508",
                    f"**Leftover EVs:** {508 - best_spread['total_evs']}"
                ])

            response["markdown_summary"] = "\n".join(markdown_lines)
            
            return response
            
        except Exception as e:
            logger.error(f"Error in find_multi_threat_bulk_evs: {e}", exc_info=True)
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions)
            return api_error(str(e))
