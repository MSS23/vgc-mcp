"""MCP tools for Life Orb optimization and item comparison.

Tools for comparing items (Life Orb vs Choice items) and analyzing
EV-item trade-offs for competitive VGC optimization.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.item_optimization import (
    compare_items_damage,
    analyze_life_orb_sustainability,
    calculate_ev_tradeoff
)
from vgc_mcp_core.calc.damage import calculate_damage, format_percent
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread, BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name
from vgc_mcp_core.utils.synergies import get_synergy_ability

# Import META_SYNERGIES from spread_tools
from .spread_tools import META_SYNERGIES


# Module-level Smogon client reference
_smogon_client: Optional[SmogonStatsClient] = None


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Fetch the most common spread for a Pokemon from Smogon usage stats."""
    if _smogon_client is None:
        return None
    try:
        usage = await _smogon_client.get_pokemon_usage(pokemon_name)
        if usage and usage.get("spreads"):
            top_spread = usage["spreads"][0]
            items = usage.get("items", {})
            abilities = usage.get("abilities", {})
            top_item = list(items.keys())[0] if items else None
            
            # Get ability based on item synergy
            top_ability, _ = get_synergy_ability(top_item, abilities)
            
            return {
                "nature": top_spread.get("nature", "Serious"),
                "evs": top_spread.get("evs", {}),
                "usage": top_spread.get("usage", 0),
                "item": top_item,
                "ability": top_ability,
            }
    except Exception as e:
        pass
    return None


def register_item_optimization_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register Life Orb optimization and item comparison tools."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def compare_item_damage_output(
        pokemon_name: str,
        move_name: str,
        target_name: str,
        items_to_compare: Optional[list[str]] = None,
        num_turns: int = 3,
        attacker_nature: Optional[str] = None,
        attacker_evs: Optional[dict] = None,
        target_nature: Optional[str] = None,
        target_evs: Optional[dict] = None,
        use_smogon_spreads: bool = True
    ) -> dict:
        """
        Compare damage output across multiple items (Life Orb vs Choice items vs Expert Belt).

        Shows damage, recoil, and sustainability for each item to help optimize item choice.

        Args:
            pokemon_name: Attacker Pokemon (e.g., "landorus-therian")
            move_name: Move to use (e.g., "earth-power")
            target_name: Defender Pokemon (e.g., "rillaboom")
            items_to_compare: List of items to compare (default: ["life-orb", "choice-band", "choice-specs", "expert-belt"])
            num_turns: Number of turns for recoil accumulation analysis (default: 3)
            attacker_nature: Attacker's nature (auto-fetched from Smogon if not specified)
            attacker_evs: Attacker's EVs dict (auto-fetched from Smogon if not specified)
            target_nature: Defender's nature (auto-fetched from Smogon if not specified)
            target_evs: Defender's EVs dict (auto-fetched from Smogon if not specified)
            use_smogon_spreads: Auto-fetch common spreads from Smogon (default: True)

        Returns:
            Comparison of all items with damage, recoil, and recommendations
        """
        try:
            if items_to_compare is None:
                items_to_compare = ["life-orb", "choice-band", "choice-specs", "expert-belt"]

            # Fetch Pokemon data
            attacker_base = await pokeapi.get_base_stats(pokemon_name)
            attacker_types = await pokeapi.get_pokemon_types(pokemon_name)
            defender_base = await pokeapi.get_base_stats(target_name)
            defender_types = await pokeapi.get_pokemon_types(target_name)
            move = await pokeapi.get_move(move_name, user_name=pokemon_name)

            # Auto-fetch Smogon spreads if requested
            attacker_spread = None
            defender_spread = None
            if use_smogon_spreads:
                attacker_spread = await _get_common_spread(pokemon_name)
                defender_spread = await _get_common_spread(target_name)

            # Build attacker
            if attacker_spread and attacker_nature is None:
                attacker_nature = attacker_spread.get("nature", "serious")
            if attacker_spread and attacker_evs is None:
                attacker_evs = attacker_spread.get("evs", {})

            attacker_nature_enum = Nature(attacker_nature.lower() if attacker_nature else "serious")
            attacker_evs_dict = attacker_evs or {}
            
            # Check for Sheer Force synergy
            attacker_key = pokemon_name.lower().replace(" ", "-")
            has_sheer_force = False
            if attacker_key in META_SYNERGIES:
                _, ability = META_SYNERGIES[attacker_key]
                if ability.lower() == "sheer-force":
                    has_sheer_force = True

            attacker = PokemonBuild(
                name=pokemon_name,
                base_stats=attacker_base,
                types=attacker_types,
                nature=attacker_nature_enum,
                evs=EVSpread(
                    hp=attacker_evs_dict.get("hp", 0),
                    attack=attacker_evs_dict.get("attack", 0),
                    defense=attacker_evs_dict.get("defense", 0),
                    special_attack=attacker_evs_dict.get("special_attack", 0),
                    special_defense=attacker_evs_dict.get("special_defense", 0),
                    speed=attacker_evs_dict.get("speed", 0)
                )
            )

            # Build defender
            if defender_spread and target_nature is None:
                target_nature = defender_spread.get("nature", "serious")
            if defender_spread and target_evs is None:
                target_evs = defender_spread.get("evs", {})

            defender_nature_enum = Nature(target_nature.lower() if target_nature else "serious")
            defender_evs_dict = target_evs or {}

            defender = PokemonBuild(
                name=target_name,
                base_stats=defender_base,
                types=defender_types,
                nature=defender_nature_enum,
                evs=EVSpread(
                    hp=defender_evs_dict.get("hp", 0),
                    attack=defender_evs_dict.get("attack", 0),
                    defense=defender_evs_dict.get("defense", 0),
                    special_attack=defender_evs_dict.get("special_attack", 0),
                    special_defense=defender_evs_dict.get("special_defense", 0),
                    speed=defender_evs_dict.get("speed", 0)
                )
            )

            # Create modifiers
            modifiers = DamageModifiers(is_doubles=True)

            # Compare items
            comparison_results = compare_items_damage(
                attacker, defender, move, items_to_compare, modifiers, has_sheer_force
            )

            # Format results
            item_comparison = []
            for result in comparison_results:
                item_comparison.append({
                    "item": result.item,
                    "damage": result.damage_range,
                    "damage_percent": result.damage_percent,
                    "recoil_per_attack": result.recoil_per_attack,
                    "recoil_percent": result.recoil_percent,
                    "turns_sustainable": result.turns_sustainable,
                    "recommendation": result.recommendation,
                    "notes": result.notes
                })

            # Generate key takeaways
            key_takeaways = []
            best_item = max(comparison_results, key=lambda x: (
                999 if x.turns_sustainable == 999 else x.turns_sustainable,
                float(x.damage_percent.split("-")[1].replace("%", ""))
            ))
            
            key_takeaways.append(f"{best_item.item.title()} provides best damage-to-sustainability ratio")
            if has_sheer_force and "life-orb" in items_to_compare:
                key_takeaways.append("Sheer Force negates Life Orb recoil - Life Orb is optimal")
            elif "life-orb" in items_to_compare:
                life_orb_result = next((r for r in comparison_results if r.item == "life-orb"), None)
                if life_orb_result:
                    key_takeaways.append(f"Life Orb recoil: {life_orb_result.recoil_percent}% per attack ({life_orb_result.turns_sustainable} attacks sustainable)")

            # Generate Showdown paste for attacker
            attacker_dict = attacker.model_dump()
            attacker_dict["item"] = best_item.item
            attacker_with_best_item = PokemonBuild(**attacker_dict)
            showdown_paste = pokemon_build_to_showdown(attacker_with_best_item)

            return {
                "attacker": pokemon_name,
                "move": move_name,
                "target": target_name,
                "item_comparison": item_comparison,
                "key_takeaways": key_takeaways,
                "showdown_paste": showdown_paste,
                "sheer_force_detected": has_sheer_force
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def optimize_life_orb_sustainability(
        pokemon_name: str,
        hp_investment: str = "full",
        recovery_sources: Optional[list[str]] = None,
        moves_per_game: int = 4,
        nature: Optional[str] = None,
        use_smogon_spread: bool = True
    ) -> dict:
        """
        Analyze Life Orb sustainability with different HP investments.

        Compares 0 HP EVs vs 252 HP EVs to determine if HP investment is worth it
        for Life Orb users. Shows attacks before fainting and net HP after multiple attacks.

        Args:
            pokemon_name: Pokemon to analyze (e.g., "flutter-mane")
            hp_investment: "full" (252), "minimal" (0), or specific EV value
            recovery_sources: List like ["grassy-terrain", "leftovers"] (default: [])
            moves_per_game: Expected number of attacks before fainting (default: 4)
            nature: Pokemon's nature (auto-fetched from Smogon if not specified)
            use_smogon_spread: Auto-fetch common spread from Smogon (default: True)

        Returns:
            Sustainability analysis comparing different HP investments
        """
        try:
            if recovery_sources is None:
                recovery_sources = []

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Auto-fetch Smogon spread if requested
            smogon_spread = None
            if use_smogon_spread:
                smogon_spread = await _get_common_spread(pokemon_name)

            # Determine HP EVs to test
            if hp_investment == "full":
                hp_evs_to_test = [0, 252]
            elif hp_investment == "minimal":
                hp_evs_to_test = [0]
            else:
                try:
                    hp_evs_to_test = [int(hp_investment)]
                except ValueError:
                    hp_evs_to_test = [0, 252]

            # Get nature and other EVs from Smogon if available
            if smogon_spread and nature is None:
                nature = smogon_spread.get("nature", "serious")
            nature_enum = Nature(nature.lower() if nature else "serious")

            # Analyze each HP investment
            sustainability_results = []
            for hp_evs in hp_evs_to_test:
                pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=types,
                    nature=nature_enum,
                    evs=EVSpread(hp=hp_evs)
                )

                analysis = analyze_life_orb_sustainability(
                    pokemon, hp_evs, recovery_sources, moves_per_game
                )

                sustainability_results.append({
                    "hp_evs": analysis.hp_evs,
                    "max_hp": analysis.max_hp,
                    "attacks_before_faint": analysis.attacks_before_faint,
                    "net_hp_after_attacks": analysis.net_hp_after_attacks,
                    "recommendation": analysis.recommendation
                })

            # Generate recommendation
            if len(sustainability_results) == 2:
                zero_evs = sustainability_results[0]
                max_evs = sustainability_results[1]
                
                if zero_evs["attacks_before_faint"] == max_evs["attacks_before_faint"]:
                    recommendation = "Invest 0 HP EVs - same sustainability as 252 HP EVs"
                else:
                    recommendation = f"252 HP EVs provides {max_evs['attacks_before_faint'] - zero_evs['attacks_before_faint']} more sustainable attacks"
            else:
                result = sustainability_results[0]
                recommendation = result["recommendation"]

            # Generate sustainability table
            table_lines = ["| HP EVs | Max HP | Attacks Before Faint |"]
            table_lines.append("|--------|--------|---------------------|")
            for result in sustainability_results:
                table_lines.append(
                    f"| {result['hp_evs']} | {result['max_hp']} | {result['attacks_before_faint']} |"
                )
            sustainability_table = "\n".join(table_lines)

            return {
                "pokemon": pokemon_name,
                "life_orb_analysis": {
                    "attacks_before_faint_0_evs": sustainability_results[0]["attacks_before_faint"],
                    "attacks_before_faint_252_evs": sustainability_results[-1]["attacks_before_faint"] if len(sustainability_results) > 1 else sustainability_results[0]["attacks_before_faint"],
                    "net_hp_after_4_attacks": sustainability_results[0]["net_hp_after_attacks"]
                },
                "recommendation": recommendation,
                "sustainability_table": sustainability_table,
                "recovery_sources": recovery_sources
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_item_ev_tradeoff(
        pokemon_name: str,
        offensive_stat: str = "auto",
        target_benchmark: Optional[dict] = None,
        items_to_test: Optional[list[str]] = None,
        use_smogon_spread: bool = True
    ) -> dict:
        """
        Find optimal item + EV distribution to maximize stats.

        Compares different items to see which saves the most EVs while meeting benchmarks.
        Useful for deciding between Life Orb (needs full EVs) vs Choice items (needs fewer EVs).

        Args:
            pokemon_name: Pokemon to optimize (e.g., "flutter-mane")
            offensive_stat: "attack", "special-attack", or "auto" (default: "auto")
            target_benchmark: Dict with benchmark requirements (e.g., {"speed_target": 200})
            items_to_test: List of items to compare (default: ["life-orb", "choice-band", "choice-specs"])
            use_smogon_spread: Auto-fetch common spread from Smogon (default: True)

        Returns:
            Trade-off analysis showing EVs saved and total useful stats for each item
        """
        try:
            if items_to_test is None:
                items_to_test = ["life-orb", "choice-band", "choice-specs"]
            if target_benchmark is None:
                target_benchmark = {}

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Auto-fetch Smogon spread if requested
            smogon_spread = None
            if use_smogon_spread:
                smogon_spread = await _get_common_spread(pokemon_name)

            # Build base Pokemon
            nature = "serious"
            if smogon_spread:
                nature = smogon_spread.get("nature", "serious")

            pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=Nature(nature.lower())
            )

            # Determine offensive stat
            if offensive_stat == "auto":
                if base_stats.attack > base_stats.special_attack:
                    offensive_stat = "attack"
                else:
                    offensive_stat = "special_attack"

            # Calculate trade-offs
            tradeoff_results = calculate_ev_tradeoff(
                pokemon, target_benchmark, items_to_test, offensive_stat
            )

            # Format results
            tradeoff_analysis = []
            for result in tradeoff_results:
                tradeoff_analysis.append({
                    "item": result.item,
                    "evs": result.evs,
                    "evs_saved": result.evs_saved,
                    "total_useful_stats": result.total_useful_stats,
                    "rank": result.rank
                })

            # Get best item
            best_result = tradeoff_results[0]

            return {
                "pokemon": pokemon_name,
                "offensive_stat": offensive_stat,
                "tradeoff_analysis": tradeoff_analysis,
                "recommendation": {
                    "best_item": best_result.item,
                    "evs_saved": best_result.evs_saved,
                    "showdown_paste": best_result.showdown_paste
                }
            }

        except Exception as e:
            return {"error": str(e)}
