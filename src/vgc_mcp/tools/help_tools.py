"""MCP tools for interactive help and guidance."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.utils.errors import api_error


def register_help_tools(mcp: FastMCP):
    """Register help and guidance tools."""

    @mcp.tool()
    async def get_help(topic: Optional[str] = None) -> dict:
        """
        Get help on using this tool. Shows available commands and examples.
        
        Args:
            topic: Optional specific topic to get help on (e.g., "damage", "team building", "speed")
            
        Returns:
            Help menu with available commands and examples
        """
        try:
            if topic is None:
                # Main help menu
                markdown_lines = [
                    "## VGC MCP Server - Help Menu",
                    "",
                    "### What Can I Do?",
                    "",
                    "| Task | Example Question |",
                    "|------|------------------|",
                    "| **Build a Team** | \"Help me build a Rain team\" |",
                    "| **Check Damage** | \"Does my Flutter Mane OHKO Incineroar?\" |",
                    "| **Optimize EVs** | \"What EVs does Amoonguss need to survive Flutter Mane?\" |",
                    "| **Analyze Team** | \"What are my team's weaknesses?\" |",
                    "| **Compare Speed** | \"Is my Landorus faster than Tornadus?\" |",
                    "| **Learn VGC** | \"Explain what EVs are\" |",
                    "",
                    "### Quick Start (New Users)",
                    "1. Say: \"Show me a beginner-friendly team\"",
                    "2. Say: \"Explain [Pokemon name]\" to learn about a Pokemon",
                    "3. Say: \"Explain [term]\" if you don't know a word",
                    "",
                    "### Popular Commands",
                    "- `explain_pokemon(\"Flutter Mane\")` - Learn about a Pokemon",
                    "- `explain_vgc_term(\"EVs\")` - Learn competitive terms",
                    "- `get_sample_team(\"beginner\")` - Get a starter team",
                    "- `calculate_damage(...)` - Check if you KO something",
                    "- `analyze_team_weaknesses(...)` - Find team problems",
                    "",
                    "### Need More Help?",
                    "- Say \"help damage\" for damage calculation help",
                    "- Say \"help team building\" for team building help",
                    "- Say \"help speed\" for speed comparison help"
                ]
                
                response = {
                    "help_type": "main_menu",
                    "markdown_summary": "\n".join(markdown_lines),
                    "available_topics": [
                        "damage", "team building", "speed", "evs", "natures",
                        "types", "abilities", "items", "moves"
                    ]
                }
                
            elif topic.lower() == "damage":
                markdown_lines = [
                    "## Help: Damage Calculations",
                    "",
                    "### What is a Damage Calculation?",
                    "A damage calculation shows how much damage one Pokemon's move does to another.",
                    "",
                    "### Common Questions",
                    "- \"Does my Flutter Mane OHKO Incineroar?\"",
                    "- \"What EVs does Amoonguss need to survive Flutter Mane Moonblast?\"",
                    "- \"How much damage does Landorus Earthquake do to Rillaboom?\"",
                    "",
                    "### Key Terms",
                    "- **OHKO**: One-Hit Knock Out (KO in one hit)",
                    "- **2HKO**: Two-Hit Knock Out (KO in two hits)",
                    "- **Survive**: Pokemon lives after taking the hit",
                    "",
                    "### Example",
                    "Use `calculate_damage_output()` to check damage between two Pokemon."
                ]
                response = {
                    "help_type": "topic",
                    "topic": "damage",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif topic.lower() in ["team building", "team", "teambuilding"]:
                markdown_lines = [
                    "## Help: Team Building",
                    "",
                    "### How to Build a Team",
                    "1. Choose your core Pokemon (what you want to build around)",
                    "2. Add support Pokemon (help your core succeed)",
                    "3. Add counters (answer common threats)",
                    "4. Test and adjust",
                    "",
                    "### Common Team Types",
                    "- **Hyper Offense**: Fast, aggressive teams",
                    "- **Balance**: Mix of offense and defense",
                    "- **Trick Room**: Slow, powerful teams",
                    "- **Weather**: Teams built around Rain, Sun, etc.",
                    "",
                    "### Tools to Help",
                    "- `get_sample_team()` - Get example teams",
                    "- `analyze_team_matchup()` - Check team weaknesses",
                    "- `check_tournament_readiness()` - See if team is ready"
                ]
                response = {
                    "help_type": "topic",
                    "topic": "team building",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif topic.lower() == "speed":
                markdown_lines = [
                    "## Help: Speed and Speed Control",
                    "",
                    "### What is Speed?",
                    "Speed determines who attacks first. Higher Speed = attacks first.",
                    "",
                    "### Speed Control",
                    "- **Tailwind**: Doubles your team's Speed",
                    "- **Trick Room**: Slower Pokemon move first",
                    "- **Priority Moves**: Always go first (Fake Out, Extreme Speed)",
                    "",
                    "### Tools",
                    "- `visualize_speed_tiers()` - See speed comparisons",
                    "- `compare_speed()` - Compare two Pokemon's speeds"
                ]
                response = {
                    "help_type": "topic",
                    "topic": "speed",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            else:
                response = {
                    "help_type": "unknown_topic",
                    "topic": topic,
                    "message": f"Help topic '{topic}' not found. Try: damage, team building, speed",
                    "available_topics": ["damage", "team building", "speed"]
                }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in get_help: {e}", exc_info=True)
            return api_error(str(e))
