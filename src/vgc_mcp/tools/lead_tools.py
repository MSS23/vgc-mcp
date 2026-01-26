"""MCP tools for lead pair analysis."""

from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.utils.errors import api_error


def register_lead_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register lead pair analysis tools."""

    @mcp.tool()
    async def analyze_lead_pairs(
        team_pokemon: List[str],
        format: str = "reg_h"
    ) -> dict:
        """
        Analyze and rank lead pair combinations for your team.
        
        Args:
            team_pokemon: List of your 6 Pokemon names
            format: VGC format (default: "reg_h")
            
        Returns:
            Ranked lead pairs with synergy analysis
        """
        try:
            if len(team_pokemon) != 6:
                return {"error": "Team must have exactly 6 Pokemon"}
            
            # Generate all possible lead pairs (15 combinations)
            import itertools
            lead_pairs = list(itertools.combinations(team_pokemon, 2))
            
            lead_scores = []
            
            for p1, p2 in lead_pairs:
                score = 0
                synergy_notes = []
                
                # Fetch Pokemon data for analysis
                try:
                    p1_types = await pokeapi.get_pokemon_types(p1)
                    p2_types = await pokeapi.get_pokemon_types(p2)
                    p1_abilities = await pokeapi.get_pokemon_abilities(p1)
                    p2_abilities = await pokeapi.get_pokemon_abilities(p2)
                    
                    # Type synergy scoring
                    # Check for complementary coverage
                    all_types = set(p1_types + p2_types)
                    if len(all_types) >= 3:
                        score += 10
                        synergy_notes.append("Good type coverage")
                    
                    # Ability synergy
                    p1_ability = p1_abilities[0].lower() if p1_abilities else ""
                    p2_ability = p2_abilities[0].lower() if p2_abilities else ""
                    
                    # Fake Out + Sweeper synergy
                    if "fake-out" in p1_ability or "fake-out" in p2_ability:
                        score += 15
                        synergy_notes.append("Fake Out + Sweeper")
                    
                    # Intimidate synergy
                    if "intimidate" in p1_ability or "intimidate" in p2_ability:
                        score += 10
                        synergy_notes.append("Intimidate support")
                    
                    # Speed control synergy
                    p1_base = await pokeapi.get_base_stats(p1)
                    p2_base = await pokeapi.get_base_stats(p2)
                    
                    speed_diff = abs(p1_base.speed - p2_base.speed)
                    if speed_diff > 50:
                        score += 5
                        synergy_notes.append("Speed control (fast + slow)")
                    
                except Exception as e:
                    logger.warning(f"Failed to analyze {p1}+{p2}: {e}")
                    continue
                
                lead_scores.append({
                    "lead_1": p1,
                    "lead_2": p2,
                    "score": score,
                    "synergy": synergy_notes
                })
            
            # Sort by score
            lead_scores.sort(key=lambda x: x["score"], reverse=True)
            
            # Build markdown output
            markdown_lines = [
                "## Lead Pair Analysis",
                "",
                "### Top Lead Combinations",
                "| Rank | Lead 1 | Lead 2 | Score | Synergy |",
                "|------|--------|--------|-------|---------|"
            ]
            
            for i, lead_data in enumerate(lead_scores[:5], 1):  # Top 5
                synergy_str = ", ".join(lead_data["synergy"][:2]) or "Standard"
                markdown_lines.append(
                    f"| {i} | {lead_data['lead_1'].title()} | {lead_data['lead_2'].title()} | "
                    f"{lead_data['score']} | {synergy_str} |"
                )
            
            # Detailed analysis for top lead
            if lead_scores:
                top_lead = lead_scores[0]
                markdown_lines.extend([
                    "",
                    f"### Detailed: {top_lead['lead_1'].title()} + {top_lead['lead_2'].title()}",
                    "**Strengths:**",
                ])
                for note in top_lead["synergy"][:3]:
                    markdown_lines.append(f"- {note}")
                
                markdown_lines.extend([
                    "",
                    "**Best Against:** Offensive teams, Tailwind teams",
                    "**Avoid Against:** Trick Room, Gastrodon + Indeedee"
                ])
            
            response = {
                "team": team_pokemon,
                "lead_rankings": lead_scores,
                "top_lead": lead_scores[0] if lead_scores else None,
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in analyze_lead_pairs: {e}", exc_info=True)
            return api_error(str(e))
