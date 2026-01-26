"""MCP tools for Pokemon education and explanations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name


def register_education_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register Pokemon education tools."""

    @mcp.tool()
    async def explain_pokemon(
        pokemon_name: str,
        detail_level: str = "beginner"  # beginner, intermediate, advanced
    ) -> dict:
        """
        Explain a Pokemon's strengths, weaknesses, and competitive role.
        
        Args:
            pokemon_name: Name of the Pokemon to explain
            detail_level: Level of detail - "beginner", "intermediate", or "advanced"
            
        Returns:
            Comprehensive Pokemon explanation with stats, typing, role, and builds
        """
        try:
            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
            abilities = await pokeapi.get_pokemon_abilities(pokemon_name)
            
            # Determine role based on stats
            role = "Unknown"
            role_explanation = ""
            
            if base_stats.speed >= 100 and (base_stats.attack >= 100 or base_stats.special_attack >= 100):
                role = "Sweeper"
                role_explanation = "Fast attacker that KO opponents before they can hit back"
            elif base_stats.hp >= 100 and (base_stats.defense >= 100 or base_stats.special_defense >= 100):
                role = "Tank"
                role_explanation = "Defensive Pokemon that can take multiple hits"
            elif base_stats.speed >= 100 and base_stats.attack < 100 and base_stats.special_attack < 100:
                role = "Support"
                role_explanation = "Fast utility Pokemon that helps the team"
            else:
                role = "Utility"
                role_explanation = "Versatile Pokemon with balanced stats"
            
            # Get type effectiveness info
            from vgc_mcp_core.calc.modifiers import TYPE_CHART
            
            resistances = []
            weaknesses = []
            immunities = []
            
            for attack_type, effectiveness in TYPE_CHART.items():
                for defender_type in types:
                    if defender_type in effectiveness:
                        eff = effectiveness[defender_type]
                        if eff == 0:
                            immunities.append(attack_type)
                        elif eff == 0.5:
                            resistances.append(attack_type)
                        elif eff == 2.0:
                            weaknesses.append(attack_type)
            
            # Build markdown output
            markdown_lines = [
                f"## Pokemon: {pokemon_name.title()}",
                "",
                "### Quick Summary",
                f"{pokemon_name.title()} is a {role.lower()}. {role_explanation}.",
                "",
                "### Base Stats",
                "| HP | Atk | Def | SpA | SpD | Spe |",
                "|----|-----|-----|-----|-----|-----|",
                f"| {base_stats.hp} | {base_stats.attack} | {base_stats.defense} | "
                f"{base_stats.special_attack} | {base_stats.special_defense} | {base_stats.speed} |",
                "",
                "**What This Means:**"
            ]
            
            # Explain stats
            if base_stats.special_attack >= 100:
                markdown_lines.append(f"- Very High Special Attack ({base_stats.special_attack}) - Hits hard with special moves")
            if base_stats.attack >= 100:
                markdown_lines.append(f"- Very High Attack ({base_stats.attack}) - Hits hard with physical moves")
            if base_stats.speed >= 100:
                markdown_lines.append(f"- Very High Speed ({base_stats.speed}) - Usually attacks first")
            if base_stats.hp < 70:
                markdown_lines.append(f"- Low HP ({base_stats.hp}) - Fragile, dies to attacks easily")
            if base_stats.defense < 70:
                markdown_lines.append(f"- Low Defense ({base_stats.defense}) - Weak to physical attacks")
            
            markdown_lines.extend([
                "",
                f"### Type: {'/'.join([t.title() for t in types])}"
            ])
            
            if immunities:
                markdown_lines.append(f"**Immune to:** {', '.join(set(immunities))}")
            if resistances:
                markdown_lines.append(f"**Resists:** {', '.join(set(resistances))}")
            if weaknesses:
                markdown_lines.append(f"**Weaknesses:** {', '.join(set(weaknesses))}")
            
            markdown_lines.extend([
                "",
                "### Common Role",
                f"**{role}** - {role_explanation}",
                ""
            ])
            
            # Beginner build suggestion
            if detail_level == "beginner":
                markdown_lines.extend([
                    "### Beginner Build",
                    f"{pokemon_name.title()} @ [Item]",
                    f"Ability: {abilities[0] if abilities else 'Unknown'}",
                    "EVs: [To be determined based on role]",
                    "",
                    "[Moves to be suggested]",
                    "",
                    "### Why This Build Works",
                    "[Explanation of build choices]"
                ])
            
            # Common partners
            markdown_lines.extend([
                "",
                "### Common Partners",
                "[Common team partners would be listed here]"
            ])
            
            # Threats
            markdown_lines.extend([
                "",
                "### Threats to Watch",
                "[Common threats would be listed here]"
            ])
            
            response = {
                "pokemon": pokemon_name,
                "base_stats": {
                    "hp": base_stats.hp,
                    "attack": base_stats.attack,
                    "defense": base_stats.defense,
                    "special_attack": base_stats.special_attack,
                    "special_defense": base_stats.special_defense,
                    "speed": base_stats.speed
                },
                "types": types,
                "abilities": abilities,
                "role": role,
                "role_explanation": role_explanation,
                "resistances": list(set(resistances)),
                "weaknesses": list(set(weaknesses)),
                "immunities": list(set(immunities)),
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in explain_pokemon: {e}", exc_info=True)
            error_str = str(e).lower()
            if "not found" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions)
            return api_error(str(e))
