"""MCP tools for user onboarding and discoverability."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.utils.errors import api_error


def register_onboarding_tools(mcp: FastMCP):
    """Register onboarding and discoverability tools."""

    @mcp.tool()
    async def show_capabilities(category: Optional[str] = None) -> dict:
        """
        Show what this tool can do with example prompts.
        
        Args:
            category: Filter by "damage", "team", "evs", "speed", "learn", or None for all
            
        Returns:
            Capabilities overview with example prompts
        """
        try:
            if category is None:
                # Main capabilities overview
                markdown_lines = [
                    "## What Can I Do?",
                    "",
                    "I'm a VGC team building assistant. Ask me anything!",
                    "",
                    "### Quick Examples (Try These!)",
                    "",
                    "| Category | Example Prompt |",
                    "|----------|----------------|",
                    "| **Damage** | \"Does Flutter Mane OHKO Incineroar?\" |",
                    "| **Team** | \"Help me build a Rain team\" |",
                    "| **EVs** | \"What EVs to survive Flutter Mane?\" |",
                    "| **Speed** | \"Is Landorus faster than Tornadus?\" |",
                    "| **Learn** | \"Explain what EVs are\" |",
                    "",
                    "### How to Use Me",
                    "",
                    "**Just ask naturally!** Examples:",
                    "- \"I want to build a team around Koraidon\"",
                    "- \"My Incineroar keeps dying, what can I do?\"",
                    "- \"Does my Flutter Mane OHKO Incineroar?\"",
                    "",
                    "**Paste Showdown Teams** - I'll analyze them:",
                    "```",
                    "Flutter Mane @ Choice Specs",
                    "Ability: Protosynthesis",
                    "EVs: 252 SpA / 4 SpD / 252 Spe",
                    "...",
                    "```",
                    "",
                    "### More Help",
                    "Say \"help damage\", \"help team\", \"help evs\" for category-specific examples."
                ]
                
                response = {
                    "capabilities_type": "overview",
                    "markdown_summary": "\n".join(markdown_lines),
                    "categories": ["damage", "team", "evs", "speed", "learn"]
                }
                
            elif category.lower() == "damage":
                markdown_lines = [
                    "## Damage Calculations",
                    "",
                    "### What I Can Do",
                    "- Calculate damage between any two Pokemon",
                    "- Show if you OHKO, 2HKO, or survive attacks",
                    "- Include all modifiers (STAB, items, weather, etc.)",
                    "",
                    "### Example Prompts",
                    "- \"Does Flutter Mane OHKO Incineroar?\"",
                    "- \"Can Amoonguss survive Flutter Mane's Moonblast?\"",
                    "- \"What's the damage range for Landorus EQ vs Rillaboom?\"",
                    "- \"Check damage with Tera Fairy active\"",
                    "",
                    "### Tools Available",
                    "- `calculate_damage_output()` - Full damage calculation",
                    "- `check_survival()` - Can Pokemon survive an attack?",
                    "- `find_bulk_evs()` - EVs needed to survive"
                ]
                response = {
                    "capabilities_type": "category",
                    "category": "damage",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif category.lower() in ["team", "teambuilding", "team building"]:
                markdown_lines = [
                    "## Team Building",
                    "",
                    "### What I Can Do",
                    "- Help build teams from scratch",
                    "- Analyze team weaknesses",
                    "- Suggest Pokemon partners",
                    "- Check team matchups vs meta",
                    "",
                    "### Example Prompts",
                    "- \"Help me build a Rain team\"",
                    "- \"What Pokemon pair well with Flutter Mane?\"",
                    "- \"Analyze my team: [paste Showdown team]\"",
                    "- \"What are my team's weaknesses?\"",
                    "",
                    "### Tools Available",
                    "- `analyze_team_matchup()` - Full team analysis",
                    "- `check_tournament_readiness()` - Is team ready?",
                    "- `analyze_lead_pairs()` - Best lead combinations"
                ]
                response = {
                    "capabilities_type": "category",
                    "category": "team",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif category.lower() in ["evs", "ev", "spread"]:
                markdown_lines = [
                    "## EV Optimization",
                    "",
                    "### What I Can Do",
                    "- Find EVs to survive specific attacks",
                    "- Optimize bulk for multiple threats",
                    "- Suggest nature changes to save EVs",
                    "- Check spread efficiency",
                    "",
                    "### Example Prompts",
                    "- \"What EVs does Incineroar need to survive Flutter Mane?\"",
                    "- \"Is my spread efficient? Suggest a better nature\"",
                    "- \"Find bulk EVs to survive multiple threats\"",
                    "- \"Can I save EVs with a different nature?\"",
                    "",
                    "### Tools Available",
                    "- `find_bulk_evs()` - EVs to survive one attack",
                    "- `find_multi_threat_bulk_evs()` - Survive multiple threats",
                    "- `suggest_nature_optimization()` - Save EVs with better nature",
                    "- `check_spread_efficiency()` - Check for wasted EVs"
                ]
                response = {
                    "capabilities_type": "category",
                    "category": "evs",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif category.lower() == "speed":
                markdown_lines = [
                    "## Speed Analysis",
                    "",
                    "### What I Can Do",
                    "- Compare speeds between Pokemon",
                    "- Show speed tiers with your team highlighted",
                    "- Calculate speed under Tailwind/Trick Room",
                    "- Find EVs to outspeed threats",
                    "",
                    "### Example Prompts",
                    "- \"Is my Landorus faster than Tornadus?\"",
                    "- \"What speed tier is 252 Spe Timid Flutter Mane?\"",
                    "- \"Show speed tiers under Tailwind\"",
                    "- \"What EVs to outspeed Dragapult?\"",
                    "",
                    "### Tools Available",
                    "- `compare_speed()` - Compare two Pokemon speeds",
                    "- `visualize_speed_tiers()` - Speed tier chart",
                    "- `find_speed_evs()` - EVs to outspeed target"
                ]
                response = {
                    "capabilities_type": "category",
                    "category": "speed",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif category.lower() in ["learn", "learning", "education"]:
                markdown_lines = [
                    "## Learning VGC",
                    "",
                    "### What I Can Do",
                    "- Explain VGC terms (EVs, STAB, OHKO, etc.)",
                    "- Explain Pokemon roles and builds",
                    "- Explain type matchups",
                    "- Check builds for common mistakes",
                    "",
                    "### Example Prompts",
                    "- \"Explain what EVs are\"",
                    "- \"What makes Flutter Mane good?\"",
                    "- \"Explain Fire type matchups\"",
                    "- \"Check my build for mistakes\"",
                    "",
                    "### Tools Available",
                    "- `explain_vgc_term()` - Explain competitive terms",
                    "- `explain_pokemon()` - Learn about a Pokemon",
                    "- `explain_type_matchup()` - Type effectiveness",
                    "- `check_build_for_mistakes()` - Find build errors"
                ]
                response = {
                    "capabilities_type": "category",
                    "category": "learn",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            else:
                response = {
                    "capabilities_type": "unknown",
                    "category": category,
                    "message": f"Unknown category: {category}. Try: damage, team, evs, speed, learn",
                    "available_categories": ["damage", "team", "evs", "speed", "learn"]
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in show_capabilities: {e}", exc_info=True)
            return api_error(str(e))
