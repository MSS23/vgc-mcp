"""MCP tools for matchup analysis."""

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.calc.matchup import (
    COMMON_THREATS,
    analyze_defensive_matchup,
    analyze_threat_matchup,
    check_type_coverage,
    find_team_threats,
)
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_matchup_tools(mcp: FastMCP, team_manager: TeamManager):
    """Register matchup analysis tools with the MCP server."""

    @mcp.tool(
        title="Analyze Threat Matchup",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_matchup(
        threat_name: Annotated[str, Field(
            description="Threat Pokemon name from the common-threats list (e.g. 'flutter-mane', 'dragapult'); use get_available_threats to list valid names",
            min_length=1,
        )],
    ) -> dict:
        """Analyze how the current team handles a specific common threat Pokemon.

        Shows which team members can OHKO/2HKO the threat, which are checks
        (outspeed + KO) or counters (survive + KO), and which are threatened by
        it. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, "No Pokemon on team. Add Pokemon first.")

            # Normalize name
            threat_name = threat_name.lower().replace(" ", "-")

            if threat_name not in COMMON_THREATS:
                return error_response(
                    ErrorCodes.INVALID_PARAMETER,
                    f"Unknown threat: {threat_name}",
                    available_threats=list(COMMON_THREATS.keys()),
                )

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

            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Find Threats to Team",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def find_threats_to_team() -> dict:
        """Identify the biggest metagame threats to the current team.

        Scans all common threats and reports major threats (OHKO 4+ team
        members), moderate threats (OHKO 2-3), coverage gaps, and the checks
        and counters available for each. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, "No Pokemon on team. Add Pokemon first.")

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Check Offensive Type Coverage",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_offensive_coverage(
        target_type: Annotated[str, Field(
            description="Defending type to check coverage against (e.g. 'Steel', 'Fairy')",
            min_length=1,
        )],
    ) -> dict:
        """Check whether the current team can hit a specific type super effectively.

        Useful for ensuring answers to common defensive types like Steel or
        Fairy. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, "No Pokemon on team. Add Pokemon first.")

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Check Defensive Type Matchup",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_defensive_matchup(
        attacking_type: Annotated[str, Field(
            description="Attacking type to check the team against (e.g. 'Ground', 'Water')",
            min_length=1,
        )],
    ) -> dict:
        """Check how well the current team resists a specific attacking type.

        Shows immunities, resistances, weaknesses, and safe switch-ins across
        the team. Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, "No Pokemon on team. Add Pokemon first.")

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="List Available Threats",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_available_threats() -> dict:
        """List all common threat Pokemon available for matchup analysis.

        Returns each threat's name, types, item, and ability — use these names
        with analyze_matchup.
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

    @mcp.tool(
        title="Full Matchup Report",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def full_matchup_report() -> dict:
        """Generate a comprehensive matchup report for the current team.

        Combines major/moderate threats, coverage gaps, defensive weaknesses
        against common attacking types, and actionable recommendations.
        Requires Pokemon on the current team.
        """
        try:
            if team_manager.size == 0:
                return error_response(ErrorCodes.TEAM_EMPTY, "No Pokemon on team. Add Pokemon first.")

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
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
