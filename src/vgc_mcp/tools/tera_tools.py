"""MCP tools for Tera type optimization."""

from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats
from vgc_mcp_core.models.move import Move
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name

# All 18 Pokemon types
ALL_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
]


def register_tera_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register Tera type optimization tools."""

    @mcp.tool()
    async def optimize_tera_type(
        pokemon_name: str,
        spread: dict,
        role: str = "attacker",
        team_pokemon: Optional[List[str]] = None,
        meta_threats: Optional[List[str]] = None
    ) -> dict:
        """
        Find the optimal Tera type for a Pokemon build.
        
        Args:
            pokemon_name: Pokemon name
            spread: Dict with nature, evs, item, ability
            role: "attacker", "support", or "tank"
            team_pokemon: Optional list of team members for synergy
            meta_threats: Optional list of meta threats to optimize against
            
        Returns:
            Ranked list of Tera types with scores and reasoning
        """
        try:
            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
            
            # Parse spread
            nature = Nature(spread.get("nature", "serious").lower())
            evs = EVSpread(**spread.get("evs", {}))
            item = spread.get("item")
            ability = spread.get("ability")
            
            # Build Pokemon
            pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=nature,
                evs=evs,
                item=item,
                ability=ability
            )
            
            # Score each Tera type
            tera_scores = []
            
            for tera_type in ALL_TYPES:
                score = 0
                reasoning = []
                
                # Offensive scoring (STAB boost)
                if role == "attacker":
                    # Check if Tera type matches any moves
                    # For now, give bonus for matching original types (STAB boost)
                    if tera_type in [t.title() for t in types]:
                        score += 30
                        reasoning.append("STAB boost on original type moves")
                    else:
                        score += 15
                        reasoning.append("New STAB option")
                
                # Defensive scoring
                from vgc_mcp_core.calc.modifiers import get_type_effectiveness
                
                # Check defensive utility against common threats
                if meta_threats:
                    for threat_name in meta_threats[:5]:  # Top 5 threats
                        try:
                            threat_types = await pokeapi.get_pokemon_types(threat_name)
                            # Check if Tera type resists common threat moves
                            # Simplified: give bonus for resisting common types
                            for threat_type in threat_types:
                                eff = get_type_effectiveness(threat_type, [tera_type])
                                if eff < 1.0:
                                    score += 5
                                    reasoning.append(f"Resists {threat_type}")
                        except Exception:
                            continue
                
                # Type synergy scoring
                if team_pokemon:
                    # Give bonus for covering team weaknesses
                    team_types = []
                    for team_member in team_pokemon[:3]:  # Check first 3
                        try:
                            member_types = await pokeapi.get_pokemon_types(team_member)
                            team_types.extend(member_types)
                        except Exception:
                            continue
                    
                    # If team is weak to a type, Tera that resists it gets bonus
                    # Simplified scoring
                    score += 5
                
                tera_scores.append({
                    "type": tera_type,
                    "score": score,
                    "reasoning": reasoning[:3]  # Top 3 reasons
                })
            
            # Sort by score
            tera_scores.sort(key=lambda x: x["score"], reverse=True)
            
            # Build markdown output
            markdown_lines = [
                f"## Tera Type Analysis: {pokemon_name.title()}",
                "",
                "### Current Build",
                f"{spread.get('nature', 'Serious').title()} | "
                f"{spread.get('evs', {}).get('hp', 0)}/"
                f"{spread.get('evs', {}).get('attack', 0)}/"
                f"{spread.get('evs', {}).get('defense', 0)}/"
                f"{spread.get('evs', {}).get('special_attack', 0)}/"
                f"{spread.get('evs', {}).get('special_defense', 0)}/"
                f"{spread.get('evs', {}).get('speed', 0)} | "
                f"{item or 'No item'}",
                "",
                "### Tera Rankings",
                "| Rank | Type | Score | Reasoning |",
                "|------|------|-------|-----------|"
            ]
            
            for i, tera_data in enumerate(tera_scores[:5], 1):  # Top 5
                reasoning_str = "; ".join(tera_data["reasoning"]) or "General utility"
                markdown_lines.append(
                    f"| {i} | **{tera_data['type']}** | {tera_data['score']} | {reasoning_str} |"
                )
            
            response = {
                "pokemon": pokemon_name,
                "role": role,
                "tera_rankings": tera_scores[:10],  # Top 10
                "recommended": tera_scores[0]["type"] if tera_scores else None,
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in optimize_tera_type: {e}", exc_info=True)
            error_str = str(e).lower()
            if "not found" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions)
            return api_error(str(e))
