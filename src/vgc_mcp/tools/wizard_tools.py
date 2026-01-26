"""MCP tools for team building wizard."""

from typing import Optional, Dict
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.utils.errors import api_error


def register_wizard_tools(mcp: FastMCP):
    """Register team building wizard tools."""

    @mcp.tool()
    async def team_building_wizard(
        step: int = 1,
        previous_choices: Optional[Dict] = None
    ) -> dict:
        """
        Interactive step-by-step team building guide for beginners.
        
        Args:
            step: Current step (1-5)
            previous_choices: Dict with previous step choices
            
        Returns:
            Current step instructions and options
        """
        try:
            if previous_choices is None:
                previous_choices = {}
            
            if step == 1:
                # Step 1: Choose playstyle
                markdown_lines = [
                    "## Team Building Wizard - Step 1 of 5",
                    "",
                    "### Choose Your Playstyle",
                    "",
                    "What kind of team do you want to play?",
                    "",
                    "| Option | Description | Difficulty |",
                    "|--------|-------------|------------|",
                    "| **A. Hyper Offense** | Fast, aggressive, KO before they KO you | Beginner |",
                    "| **B. Balance** | Mix of offense and defense | Intermediate |",
                    "| **C. Trick Room** | Slow Pokemon move first | Intermediate |",
                    "| **D. Weather (Rain/Sun)** | Use weather to boost your team | Intermediate |",
                    "| **E. I don't know** | I'll suggest something based on your favorite Pokemon | Beginner |",
                    "",
                    "Reply with A, B, C, D, or E to continue."
                ]
                
                response = {
                    "step": 1,
                    "total_steps": 5,
                    "question": "Choose your playstyle",
                    "options": {
                        "A": "Hyper Offense",
                        "B": "Balance",
                        "C": "Trick Room",
                        "D": "Weather",
                        "E": "I don't know"
                    },
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif step == 2:
                # Step 2: Choose core Pokemon
                playstyle = previous_choices.get("playstyle", "Hyper Offense")
                
                if playstyle == "Hyper Offense":
                    suggestions = [
                        "Flutter Mane (Fast special attacker)",
                        "Koraidon (Powerful physical attacker)",
                        "Chi-Yu (Fire-type sweeper)"
                    ]
                elif playstyle == "Balance":
                    suggestions = [
                        "Incineroar (Support + offense)",
                        "Landorus (Versatile attacker)",
                        "Rillaboom (Priority + offense)"
                    ]
                elif playstyle == "Trick Room":
                    suggestions = [
                        "Amoonguss (Slow support)",
                        "Torkoal (Slow sun setter)",
                        "Indeedee (Trick Room setter)"
                    ]
                else:
                    suggestions = [
                        "Your favorite Pokemon",
                        "A Pokemon you want to build around"
                    ]
                
                markdown_lines = [
                    "## Team Building Wizard - Step 2 of 5",
                    "",
                    f"### Step 2: Choose Your Core Pokemon",
                    f"Based on your choice of {playstyle}...",
                    "",
                    "Which Pokemon do you want to build around?",
                    ""
                ]
                
                for i, suggestion in enumerate(suggestions, 1):
                    markdown_lines.append(f"- {suggestion}")
                
                markdown_lines.extend([
                    "",
                    "Or tell me your favorite Pokemon and I'll help you build around it!"
                ])
                
                response = {
                    "step": 2,
                    "total_steps": 5,
                    "question": "Choose your core Pokemon",
                    "suggestions": suggestions,
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif step == 3:
                # Step 3: Add support
                markdown_lines = [
                    "## Team Building Wizard - Step 3 of 5",
                    "",
                    "### Step 3: Add Support Pokemon",
                    "",
                    "Now add Pokemon that help your core succeed:",
                    "",
                    "- **Fake Out users**: Incineroar, Rillaboom (give free turns)",
                    "- **Speed control**: Tornadus (Tailwind), Indeedee (Trick Room)",
                    "- **Intimidate**: Incineroar, Landorus (weaken opponents)",
                    "",
                    "Which support Pokemon do you want to add?"
                ]
                
                response = {
                    "step": 3,
                    "total_steps": 5,
                    "question": "Add support Pokemon",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif step == 4:
                # Step 4: Add counters
                markdown_lines = [
                    "## Team Building Wizard - Step 4 of 5",
                    "",
                    "### Step 4: Add Counters",
                    "",
                    "Add Pokemon that answer common threats:",
                    "",
                    "- **Flutter Mane counter**: Incineroar, Gholdengo",
                    "- **Ground weak answer**: Flying types, Air Balloon",
                    "- **Speed control answer**: Imprison, Taunt",
                    "",
                    "What threats do you need to counter?"
                ]
                
                response = {
                    "step": 4,
                    "total_steps": 5,
                    "question": "Add counters",
                    "markdown_summary": "\n".join(markdown_lines)
                }
                
            elif step == 5:
                # Step 5: Finalize
                markdown_lines = [
                    "## Team Building Wizard - Step 5 of 5",
                    "",
                    "### Step 5: Finalize Your Team",
                    "",
                    "Review your team and make final adjustments:",
                    "",
                    "- Check type coverage",
                    "- Ensure speed control",
                    "- Test against common threats",
                    "",
                    "Your team is ready! Use `analyze_team_matchup()` to check for weaknesses."
                ]
                
                response = {
                    "step": 5,
                    "total_steps": 5,
                    "question": "Finalize team",
                    "markdown_summary": "\n".join(markdown_lines),
                    "complete": True
                }
                
            else:
                return {"error": f"Invalid step: {step}. Must be 1-5."}
            
            return response
            
        except Exception as e:
            logger.error(f"Error in team_building_wizard: {e}", exc_info=True)
            return api_error(str(e))
