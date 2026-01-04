"""MCP tools for matchup analysis."""

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.calc.matchup import (
    analyze_threat_matchup,
    find_team_threats,
    check_type_coverage,
    analyze_defensive_matchup,
    COMMON_THREATS,
)

# MCP-UI support (enabled in vgc-mcp-lite)
from ..ui.resources import create_threat_analysis_resource, add_ui_metadata
HAS_UI = True


def register_matchup_tools(mcp: FastMCP, team_manager: TeamManager):
    """Register matchup analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_matchup(threat_name: str) -> dict:
        """
        Analyze how the current team handles a specific threat Pokemon.

        Shows:
        - Which team members can OHKO the threat
        - Which team members can 2HKO
        - Which are checks (outspeed + KO)
        - Which are counters (survive + KO)
        - Which team members are threatened by it

        Args:
            threat_name: Name of the threat Pokemon (e.g., "flutter-mane", "dragapult")

        Returns:
            Detailed matchup analysis
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            # Normalize name
            threat_name = threat_name.lower().replace(" ", "-")

            if threat_name not in COMMON_THREATS:
                return {
                    "error": f"Unknown threat: {threat_name}",
                    "available_threats": list(COMMON_THREATS.keys())
                }

            analysis = analyze_threat_matchup(team_manager.team, threat_name)

            result = {
                "threat": analysis.threat_name,
                "threat_speed": analysis.threat_speed,
                "can_ohko": analysis.ohko_by,
                "can_2hko": analysis.twohko_by,
                "checks": analysis.checks,
                "counters": analysis.counters,
                "threatened_by": analysis.threatened,
                "survives_attack": analysis.survives,
                "notes": analysis.notes
            }

            # Add interactive UI (only in vgc-mcp-lite)
            if HAS_UI:
                ui_resource = create_threat_analysis_resource(
                    threat_name=analysis.threat_name,
                    threat_speed=analysis.threat_speed,
                    ohko_by=analysis.ohko_by,
                    twohko_by=analysis.twohko_by,
                    checks=analysis.checks,
                    counters=analysis.counters,
                    threatened=analysis.threatened,
                    survives=analysis.survives,
                    notes=analysis.notes,
                )
                return add_ui_metadata(
                    result, ui_resource,
                    display_type="inline",
                    name="Threat Analysis"
                )
            return result

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def find_threats_to_team() -> dict:
        """
        Identify the biggest threats to the current team.

        Analyzes all common metagame threats and identifies:
        - Major threats (OHKO 4+ team members)
        - Moderate threats (OHKO 2-3 team members)
        - Available checks and counters for each threat

        Returns:
            Team threat summary with severity rankings
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            summary = find_team_threats(team_manager.team)

            return {
                "major_threats": summary.major_threats,
                "moderate_threats": summary.moderate_threats,
                "coverage_gaps": summary.coverage_gaps,
                "checks_available": {
                    threat: checks
                    for threat, checks in summary.checks_available.items()
                    if threat in summary.major_threats or threat in summary.moderate_threats
                },
                "counters_available": {
                    threat: counters
                    for threat, counters in summary.counters_available.items()
                    if threat in summary.major_threats or threat in summary.moderate_threats
                }
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def check_offensive_coverage(target_type: str) -> dict:
        """
        Check if the team can hit a specific type super effectively.

        Useful for ensuring you have answers to common defensive types
        like Steel, Fairy, etc.

        Args:
            target_type: The type to check coverage against (e.g., "Steel", "Fairy")

        Returns:
            Which Pokemon can hit super effectively and with what
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            # Normalize type
            target_type = target_type.capitalize()

            coverage = check_type_coverage(team_manager.team, target_type)

            return {
                "target_type": target_type,
                "super_effective_coverage": coverage["super_effective"],
                "neutral_coverage": coverage["neutral"],
                "resisted_by": coverage["resisted"],
                "has_coverage": coverage["has_coverage"],
                "recommendation": (
                    f"Team has good {target_type} coverage"
                    if coverage["has_coverage"]
                    else f"WARNING: Team lacks super effective coverage vs {target_type}"
                )
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def check_defensive_matchup(attacking_type: str) -> dict:
        """
        Check how well the team resists a specific attacking type.

        Shows immunities, resistances, and weaknesses across the team.

        Args:
            attacking_type: The attacking type to check (e.g., "Ground", "Water")

        Returns:
            Defensive breakdown for the type
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            # Normalize type
            attacking_type = attacking_type.capitalize()

            matchup = analyze_defensive_matchup(team_manager.team, attacking_type)

            return {
                "attacking_type": attacking_type,
                "immune": matchup["immune"],
                "resists": matchup["resists"],
                "neutral": matchup["neutral"],
                "weak": matchup["weak"],
                "safe_switch_ins": matchup["safe_switch_ins"],
                "recommendation": (
                    f"Good {attacking_type} resistance with {matchup['safe_switch_ins']} safe switch-ins"
                    if matchup["safe_switch_ins"] >= 2
                    else f"WARNING: Only {matchup['safe_switch_ins']} Pokemon resist/immune to {attacking_type}"
                )
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_available_threats() -> dict:
        """
        List all common threats available for matchup analysis.

        Returns:
            List of threat Pokemon with basic info
        """
        threats = []
        for name, data in COMMON_THREATS.items():
            threats.append({
                "name": name,
                "types": data["types"],
                "item": data["item"],
                "ability": data["ability"]
            })

        return {
            "threat_count": len(threats),
            "threats": threats
        }

    @mcp.tool()
    async def full_matchup_report() -> dict:
        """
        Generate a comprehensive matchup report for the team.

        Includes:
        - All major and moderate threats
        - Coverage gaps
        - Defensive weaknesses
        - Recommendations

        Returns:
            Full matchup analysis report
        """
        try:
            if team_manager.size == 0:
                return {"error": "No Pokemon on team. Add Pokemon first."}

            # Get threat summary
            threat_summary = find_team_threats(team_manager.team)

            # Analyze common attacking types
            common_attack_types = ["Ground", "Ice", "Fairy", "Fighting", "Fire", "Water"]
            defensive_issues = []

            for attack_type in common_attack_types:
                matchup = analyze_defensive_matchup(team_manager.team, attack_type)
                if matchup["safe_switch_ins"] < 2:
                    defensive_issues.append({
                        "type": attack_type,
                        "safe_switch_ins": matchup["safe_switch_ins"],
                        "weak": matchup["weak"]
                    })

            # Build recommendations
            recommendations = []

            if threat_summary.major_threats:
                recommendations.append(
                    f"Address major threats: {', '.join(threat_summary.major_threats)}"
                )

            if threat_summary.coverage_gaps:
                recommendations.append(
                    f"Add coverage for: {', '.join(threat_summary.coverage_gaps[:5])}"
                )

            for issue in defensive_issues:
                recommendations.append(
                    f"Improve {issue['type']} resistance (currently {issue['safe_switch_ins']} safe switch-ins)"
                )

            return {
                "team": team_manager.team.get_pokemon_names(),
                "major_threats": threat_summary.major_threats,
                "moderate_threats": threat_summary.moderate_threats,
                "coverage_gaps": threat_summary.coverage_gaps,
                "defensive_issues": defensive_issues,
                "recommendations": recommendations,
                "threat_answers": {
                    threat: {
                        "checks": threat_summary.checks_available.get(threat, []),
                        "counters": threat_summary.counters_available.get(threat, [])
                    }
                    for threat in threat_summary.major_threats
                }
            }

        except Exception as e:
            return {"error": str(e)}
