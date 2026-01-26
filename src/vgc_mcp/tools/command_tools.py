"""MCP tools for slash commands (power user shortcuts)."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.utils.errors import api_error


def register_command_tools(mcp: FastMCP):
    """Register slash command tools for power users."""

    @mcp.tool()
    async def run_slash_command(command: str) -> dict:
        """
        Execute slash commands for power users.
        
        Commands:
            /help [category] - Show help for category
            /damage <attacker> <defender> <move> - Quick damage calc
            /speed <pokemon1> <pokemon2> - Compare speeds
            /explain <term> - Explain VGC term
            /capabilities [category] - Show capabilities
            /prompts - Show starter prompts
            
        Args:
            command: Slash command string (e.g., "/help damage", "/damage flutter-mane incineroar moonblast")
            
        Returns:
            Command result or help message
        """
        try:
            parts = command.strip().split()
            if not parts or not parts[0].startswith("/"):
                return {
                    "error": "Invalid command format. Commands must start with '/'",
                    "available_commands": [
                        "/help [category]",
                        "/damage <attacker> <defender> <move>",
                        "/speed <pokemon1> <pokemon2>",
                        "/explain <term>",
                        "/capabilities [category]",
                        "/prompts"
                    ]
                }
            
            cmd = parts[0].lower()
            args = parts[1:] if len(parts) > 1 else []
            
            if cmd == "/help":
                category = args[0] if args else None
                # Redirect to get_help tool
                return {
                    "command": "help",
                    "category": category,
                    "message": "Use get_help() tool for detailed help",
                    "redirect": f"get_help(topic={category})"
                }
            
            elif cmd == "/damage":
                if len(args) < 3:
                    return {
                        "error": "Usage: /damage <attacker> <defender> <move>",
                        "example": "/damage flutter-mane incineroar moonblast"
                    }
                attacker, defender, move = args[0], args[1], args[2]
                return {
                    "command": "damage",
                    "attacker": attacker,
                    "defender": defender,
                    "move": move,
                    "message": "Use calculate_damage_output() tool",
                    "redirect": f"calculate_damage_output(attacker_name='{attacker}', defender_name='{defender}', move_name='{move}')"
                }
            
            elif cmd == "/speed":
                if len(args) < 2:
                    return {
                        "error": "Usage: /speed <pokemon1> <pokemon2>",
                        "example": "/speed landorus tornadus"
                    }
                pokemon1, pokemon2 = args[0], args[1]
                return {
                    "command": "speed",
                    "pokemon1": pokemon1,
                    "pokemon2": pokemon2,
                    "message": "Use compare_speed() tool",
                    "redirect": f"compare_speed(pokemon1='{pokemon1}', pokemon2='{pokemon2}')"
                }
            
            elif cmd == "/explain":
                if not args:
                    return {
                        "error": "Usage: /explain <term>",
                        "example": "/explain EVs"
                    }
                term = " ".join(args)
                return {
                    "command": "explain",
                    "term": term,
                    "message": "Use explain_vgc_term() tool",
                    "redirect": f"explain_vgc_term(term='{term}')"
                }
            
            elif cmd == "/capabilities":
                category = args[0] if args else None
                return {
                    "command": "capabilities",
                    "category": category,
                    "message": "Use show_capabilities() tool",
                    "redirect": f"show_capabilities(category={category})"
                }
            
            elif cmd == "/prompts":
                from vgc_mcp_core.data.starter_prompts import STARTER_PROMPTS
                return {
                    "command": "prompts",
                    "prompts": STARTER_PROMPTS,
                    "message": "Available starter prompts",
                    "markdown_summary": "\n".join([
                        "## Starter Prompts",
                        "",
                        "| Title | Prompt | Category |",
                        "|-------|--------|----------|"
                    ] + [
                        f"| {p['title']} | {p['prompt']} | {p['category']} |"
                        for p in STARTER_PROMPTS
                    ])
                }
            
            else:
                return {
                    "error": f"Unknown command: {cmd}",
                    "available_commands": [
                        "/help [category]",
                        "/damage <attacker> <defender> <move>",
                        "/speed <pokemon1> <pokemon2>",
                        "/explain <term>",
                        "/capabilities [category]",
                        "/prompts"
                    ]
                }
            
        except Exception as e:
            logger.error(f"Error in run_slash_command: {e}", exc_info=True)
            return api_error(str(e))
