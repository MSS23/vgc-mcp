"""MCP tools for speed control analysis."""

from mcp.server.fastmcp import FastMCP

from ..team.manager import TeamManager
from ..calc.speed_control import (
    analyze_trick_room,
    analyze_tailwind,
    analyze_speed_drop,
    analyze_paralysis,
    get_speed_control_summary,
    get_team_speeds,
    SPEED_BENCHMARKS,
    apply_speed_modifier,
    apply_stage_modifier,
)


def register_speed_control_tools(mcp: FastMCP, team_manager: TeamManager):
    """Register speed control analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_team_trick_room() -> dict:
        """
        Analyze how the current team performs under Trick Room.

        Shows:
        - Move order in Trick Room (slowest first)
        - Which Pokemon benefit from TR
        - What each Pokemon "outspeeds" in TR
        - Whether team has TR setters

        Returns:
            Trick Room analysis with move order and recommendations
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            analysis = analyze_trick_room(team_manager.team)

            return {
                "condition": analysis.condition,
                "move_order": analysis.move_order,
                "speeds": [
                    {
                        "name": t.name,
                        "speed": t.final_speed,
                        "notes": t.notes
                    }
                    for t in analysis.team_speeds
                ],
                "outspeeds_in_tr": {
                    name: targets[:5]  # Limit for readability
                    for name, targets in analysis.outspeeds.items()
                },
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_team_tailwind() -> dict:
        """
        Analyze how the current team performs with Tailwind active.

        Tailwind doubles Speed for 4 turns.

        Shows:
        - Speeds after 2x boost
        - What each Pokemon outspeeds with Tailwind
        - Whether team has Tailwind setters

        Returns:
            Tailwind analysis with boosted speeds
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            analysis = analyze_tailwind(team_manager.team)

            return {
                "condition": analysis.condition,
                "move_order": analysis.move_order,
                "speeds": [
                    {
                        "name": t.name,
                        "base_speed": t.final_speed,
                        "with_tailwind": t.modified_speed
                    }
                    for t in analysis.team_speeds
                ],
                "outspeeds_with_tailwind": {
                    name: targets[:5]
                    for name, targets in analysis.outspeeds.items()
                },
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_speed_drops(stages: int = -1) -> dict:
        """
        Analyze what your team can outspeed after using Icy Wind/Electroweb.

        Args:
            stages: Number of speed stages dropped on opponent (default -1)
                   -1 = Icy Wind, Electroweb, Rock Tomb
                   -2 = Scary Face, Cotton Spore

        Returns:
            Analysis of what your team outspeeds after speed control
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            # Clamp stages
            stages = max(-6, min(0, stages))

            analysis = analyze_speed_drop(team_manager.team, stages)

            return {
                "condition": analysis.condition,
                "your_speeds": [
                    {"name": t.name, "speed": t.final_speed}
                    for t in analysis.team_speeds
                ],
                "outspeeds_after_drop": analysis.outspeeds,
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_paralysis_matchup() -> dict:
        """
        Analyze what your team outspeeds when opponents are paralyzed.

        Paralysis halves Speed.

        Returns:
            Analysis of matchups vs paralyzed opponents
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            analysis = analyze_paralysis(team_manager.team)

            return {
                "condition": analysis.condition,
                "your_speeds": [
                    {"name": t.name, "speed": t.final_speed}
                    for t in analysis.team_speeds
                ],
                "outspeeds_paralyzed": analysis.outspeeds,
                "notes": analysis.notes
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_full_speed_analysis() -> dict:
        """
        Get comprehensive speed control analysis for the team.

        Includes:
        - Base speed tiers
        - Trick Room analysis
        - Tailwind analysis
        - Icy Wind/Electroweb impact

        Returns:
            Complete speed control breakdown
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            return get_speed_control_summary(team_manager.team)

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def calculate_speed_after_modifier(
        base_speed: int,
        modifier_type: str,
        stages: int = 0
    ) -> dict:
        """
        Calculate what a speed stat becomes after various modifiers.

        Args:
            base_speed: The Pokemon's current Speed stat
            modifier_type: "tailwind", "paralysis", "stage", or "none"
            stages: Stat stages (-6 to +6) if modifier_type is "stage"

        Returns:
            Modified speed and what it outspeeds
        """
        try:
            if modifier_type == "tailwind":
                modified = apply_speed_modifier(base_speed, 2.0)
                condition = "with Tailwind (2x)"
            elif modifier_type == "paralysis":
                modified = apply_speed_modifier(base_speed, 0.5)
                condition = "while paralyzed (0.5x)"
            elif modifier_type == "stage":
                stages = max(-6, min(6, stages))
                modified = apply_stage_modifier(base_speed, stages)
                condition = f"at {stages:+d} stages"
            else:
                modified = base_speed
                condition = "unmodified"

            # Find what this outspeeds
            outspeeds = []
            underspeeds = []

            for mon, data in SPEED_BENCHMARKS.items():
                if "max_positive" in data:
                    if modified > data["max_positive"]:
                        outspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")
                    elif modified < data["max_positive"]:
                        underspeeds.append(f"Max Speed {mon.replace('-', ' ').title()}")

            return {
                "original_speed": base_speed,
                "modified_speed": modified,
                "condition": condition,
                "outspeeds": outspeeds[:10],
                "underspeeds": underspeeds[:5]
            }

        except Exception as e:
            return {"error": str(e)}
