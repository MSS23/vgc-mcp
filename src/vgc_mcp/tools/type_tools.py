"""MCP tools for type effectiveness education."""

from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.modifiers import get_type_effectiveness, TYPE_CHART
from vgc_mcp_core.utils.errors import api_error


def register_type_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register type effectiveness education tools."""

    @mcp.tool()
    async def explain_type_matchup(
        attacking_type: Optional[str] = None,
        defending_types: Optional[List[str]] = None,
        pokemon_name: Optional[str] = None
    ) -> dict:
        """
        Explain type effectiveness for attacks or Pokemon matchups.
        
        Args:
            attacking_type: Type of the attacking move
            defending_types: List of defending Pokemon types
            pokemon_name: Optional Pokemon name (will fetch types automatically)
            
        Returns:
            Type matchup explanation with effectiveness and reasoning
        """
        try:
            # If Pokemon name provided, fetch types
            if pokemon_name and not defending_types:
                defending_types = await pokeapi.get_pokemon_types(pokemon_name)
            
            if not attacking_type or not defending_types:
                return {
                    "error": "Must provide either (attacking_type and defending_types) or pokemon_name"
                }
            
            # Calculate effectiveness
            effectiveness = get_type_effectiveness(attacking_type, defending_types)
            
            # Determine result
            if effectiveness == 0:
                result = "NO EFFECT (0x damage)"
                result_emoji = "🚫"
            elif effectiveness == 0.25:
                result = "4x RESISTED (0.25x damage)"
                result_emoji = "🛡️🛡️"
            elif effectiveness == 0.5:
                result = "RESISTED (0.5x damage)"
                result_emoji = "🛡️"
            elif effectiveness == 1.0:
                result = "NEUTRAL (1x damage)"
                result_emoji = "➖"
            elif effectiveness == 2.0:
                result = "SUPER EFFECTIVE (2x damage)"
                result_emoji = "⚡"
            elif effectiveness == 4.0:
                result = "4x SUPER EFFECTIVE (4x damage)"
                result_emoji = "⚡⚡"
            else:
                result = f"{effectiveness}x effectiveness"
                result_emoji = "❓"
            
            # Build explanation
            defending_str = "/".join([t.title() for t in defending_types])
            
            markdown_lines = [
                f"## Type Matchup: {attacking_type.title()} vs {defending_str}",
                "",
                f"### Result: {result_emoji} {result}",
                ""
            ]
            
            # Explain why
            if len(defending_types) == 1:
                def_type = defending_types[0]
                if def_type in TYPE_CHART.get(attacking_type, {}):
                    eff = TYPE_CHART[attacking_type][def_type]
                    if eff == 2.0:
                        markdown_lines.append(f"### Why?")
                        markdown_lines.append(f"- {attacking_type.title()} vs {def_type.title()} = **2x** ({attacking_type.title()} is super effective against {def_type.title()})")
                    elif eff == 0.5:
                        markdown_lines.append(f"### Why?")
                        markdown_lines.append(f"- {attacking_type.title()} vs {def_type.title()} = **0.5x** ({def_type.title()} resists {attacking_type.title()})")
                    elif eff == 0:
                        markdown_lines.append(f"### Why?")
                        markdown_lines.append(f"- {attacking_type.title()} vs {def_type.title()} = **0x** ({def_type.title()} is immune to {attacking_type.title()})")
            else:
                markdown_lines.append("### Why?")
                for def_type in defending_types:
                    if def_type in TYPE_CHART.get(attacking_type, {}):
                        eff = TYPE_CHART[attacking_type][def_type]
                        markdown_lines.append(f"- {attacking_type.title()} vs {def_type.title()} = **{eff}x**")
                markdown_lines.append(f"- Combined: {effectiveness}x total")
            
            # Type cheat sheet
            if attacking_type in TYPE_CHART:
                super_effective = []
                resisted = []
                immune = []
                
                for def_type, eff in TYPE_CHART[attacking_type].items():
                    if eff == 2.0:
                        super_effective.append(def_type)
                    elif eff == 0.5:
                        resisted.append(def_type)
                    elif eff == 0:
                        immune.append(def_type)
                
                markdown_lines.extend([
                    "",
                    f"### {attacking_type.title()} Type Cheat Sheet",
                    "| Super Effective (2x) | Resisted (0.5x) | No Effect (0x) |",
                    "|---------------------|-----------------|----------------|"
                ])
                
                max_rows = max(len(super_effective), len(resisted), len(immune))
                for i in range(max_rows):
                    se = super_effective[i] if i < len(super_effective) else ""
                    res = resisted[i] if i < len(resisted) else ""
                    imm = immune[i] if i < len(immune) else ""
                    markdown_lines.append(f"| {se} | {res} | {imm} |")
            
            # Tips
            markdown_lines.extend([
                "",
                "### Tips"
            ])
            
            if attacking_type == "Fire":
                markdown_lines.append("- Fire is great against Steel types (Gholdengo, Corviknight)")
                markdown_lines.append("- Fire struggles against Water types (Palafin, Urshifu-Rapid)")
                markdown_lines.append("- Rain weather WEAKENS Fire moves by 50%")
            elif attacking_type == "Water":
                markdown_lines.append("- Water is great against Fire and Ground types")
                markdown_lines.append("- Water struggles against Grass types")
                markdown_lines.append("- Rain weather BOOSTS Water moves by 50%")
            elif attacking_type == "Electric":
                markdown_lines.append("- Electric is great against Water and Flying types")
                markdown_lines.append("- Electric has NO EFFECT on Ground types")
                markdown_lines.append("- Electric Terrain BOOSTS Electric moves by 30%")
            
            response = {
                "attacking_type": attacking_type,
                "defending_types": defending_types,
                "effectiveness": effectiveness,
                "result": result,
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in explain_type_matchup: {e}", exc_info=True)
            return api_error(str(e))
