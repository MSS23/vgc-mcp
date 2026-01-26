"""MCP tools for multi-threat bulk calculations."""

from typing import Optional, List, Dict
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats
from vgc_mcp_core.models.move import Move
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50


def register_multi_threat_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
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
            
            if ability is None:
                def_abilities = await pokeapi.get_pokemon_abilities(pokemon_name)
                if def_abilities:
                    ability = def_abilities[0].lower().replace(" ", "-")
            
            try:
                def_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}
            
            # Parse and validate threats
            parsed_threats = []
            for i, threat in enumerate(threats):
                if not isinstance(threat, dict):
                    return {"error": f"Threat {i+1} must be a dict with 'name' and 'move' keys"}
                
                threat_name = threat.get("name")
                threat_move = threat.get("move")
                if not threat_name or not threat_move:
                    return {"error": f"Threat {i+1} missing 'name' or 'move'"}
                
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
                    spread = threat.get("spread", {})
                    threat_nature = Nature(spread.get("nature", "serious").lower())
                    threat_evs = spread.get("evs", {})
                    threat_item = spread.get("item")
                    threat_ability = spread.get("ability")
                    
                    if threat_ability is None:
                        threat_abilities = await pokeapi.get_pokemon_abilities(threat["name"])
                        if threat_abilities:
                            threat_ability = threat_abilities[0].lower().replace(" ", "-")
                    
                    threat_build = PokemonBuild(
                        name=threat["name"],
                        base_stats=atk_base,
                        types=atk_types,
                        nature=threat_nature,
                        evs=EVSpread(**threat_evs),
                        item=threat_item,
                        ability=threat_ability
                    )
                    
                    threat_builds.append({
                        "build": threat_build,
                        "move": move,
                        "name": threat["name"],
                        "move_name": threat["move"]
                    })
                except Exception as e:
                    logger.warning(f"Failed to build threat {threat['name']}: {e}")
                    return {"error": f"Failed to process threat {threat['name']}: {str(e)}"}
            
            # Try different EV combinations to find minimum that survives all threats
            best_spread = None
            best_results = None
            
            # Try all valid EV breakpoint combinations
            for hp_ev in EV_BREAKPOINTS_LV50:
                for def_ev in EV_BREAKPOINTS_LV50:
                    for spd_ev in EV_BREAKPOINTS_LV50:
                        total_evs = hp_ev + def_ev + spd_ev
                        if total_evs > 508:
                            continue
                        
                        # Create test defender build
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
                            result = calculate_damage(
                                threat_data["build"],
                                test_defender,
                                threat_data["move"],
                                DamageModifiers(is_doubles=True)
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
                return {
                    "error": "Could not find a spread that survives all threats with the given constraints",
                    "threats": [t["name"] for t in parsed_threats]
                }
            
            # Format response
            response = {
                "pokemon": pokemon_name,
                "nature": nature.title(),
                "item": item or "None",
                "ability": ability or "None",
                "recommended_spread": {
                    "hp_evs": best_spread["hp_evs"],
                    "def_evs": best_spread["def_evs"],
                    "spd_evs": best_spread["spd_evs"],
                    "total_evs": best_spread["total_evs"],
                    "leftover_evs": 508 - best_spread["total_evs"]
                },
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
