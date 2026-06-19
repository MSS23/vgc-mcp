"""MCP tools for comprehensive team matchup analysis."""

from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.calc.matchup import COMMON_THREATS, analyze_threat_matchup
from vgc_mcp_core.utils.errors import api_error, error_response, ErrorCodes
from vgc_mcp_core.rules.regulation_loader import get_regulation_config


def _detect_champions(pokemon_names: Optional[List[str]] = None) -> bool:
    """Return True when the active session is the Champions (Reg MA) SP system.

    Optionally runs Pokemon-name inference first so a Mega/Reg MA team
    auto-selects Champions without the user having to set it explicitly.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(*(pokemon_names or []))


def register_team_matchup_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient], team_manager: TeamManager):
    """Register comprehensive team matchup analysis tools."""

    @mcp.tool()
    async def analyze_team_matchup(
        team_pokemon: List[str],
        opponent_pokemon: Optional[List[str]] = None,
        vs_meta: bool = True,
        format: str = "reg_h"
    ) -> dict:
        """
        Analyze how your full team matches up against opponents.
        
        Args:
            team_pokemon: List of your 6 Pokemon names
            opponent_pokemon: Optional specific opponent team (6 Pokemon)
            vs_meta: If True, compare against top 20 meta threats
            format: VGC format (default: "reg_h")
            
        Returns:
            Comprehensive matchup analysis with ratings and recommendations
        """
        try:
            if len(team_pokemon) != 6:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Team must have exactly 6 Pokemon')

            # Detect format once. Champions team members use the SP system so
            # matchup stats/speed are correct; meta threats stay mainline.
            is_champions = _detect_champions(team_pokemon)

            # Analyze against meta threats if requested
            threat_coverage = {}
            weaknesses = []
            strengths = []

            if vs_meta:
                from vgc_mcp_core.models.team import Team, TeamSlot
                from vgc_mcp_core.models.pokemon import PokemonBuild, EVSpread, StatPointSpread, Nature

                team_slots = []
                for pokemon_name in team_pokemon:
                    # Prefer a stored build (carries the user's real spread/sps).
                    try:
                        stored = team_manager.get_pokemon_by_name(pokemon_name)
                    except Exception:
                        stored = None
                    if isinstance(stored, PokemonBuild):
                        team_slots.append(stored)
                        continue
                    try:
                        base_stats = await pokeapi.get_base_stats(pokemon_name)
                        types = await pokeapi.get_pokemon_types(pokemon_name)
                        if is_champions:
                            team_slots.append(PokemonBuild(
                                name=pokemon_name,
                                base_stats=base_stats,
                                types=types,
                                nature=Nature.SERIOUS,
                                format_system="champions",
                                sps=StatPointSpread(),
                            ))
                        else:
                            team_slots.append(PokemonBuild(
                                name=pokemon_name,
                                base_stats=base_stats,
                                types=types,
                                nature=Nature.SERIOUS,
                                evs=EVSpread()
                            ))
                    except Exception:
                        continue

                if len(team_slots) < 6:
                    return error_response(ErrorCodes.API_ERROR, f'Failed to fetch data for some Pokemon: {team_pokemon}')

                temp_team = Team(slots=[TeamSlot(pokemon=p, slot_index=i) for i, p in enumerate(team_slots)])

                # Analyze against top meta threats
                top_threats = list(COMMON_THREATS.keys())[:20]

                for threat_name in top_threats:
                    try:
                        analysis = analyze_threat_matchup(temp_team, threat_name)
                        
                        # Determine matchup quality
                        if len(analysis.counters) >= 2:
                            matchup = "Favorable"
                        elif len(analysis.checks) >= 1 or len(analysis.counters) >= 1:
                            matchup = "Even"
                        elif len(analysis.threatened) >= 3:
                            matchup = "Unfavorable"
                        else:
                            matchup = "Neutral"
                        
                        threat_coverage[threat_name] = {
                            "matchup": matchup,
                            "best_answer": analysis.counters[0] if analysis.counters else (analysis.checks[0] if analysis.checks else "None"),
                            "threatened_count": len(analysis.threatened)
                        }
                    except Exception as e:
                        logger.warning(f"Failed to analyze {threat_name}: {e}")
                        continue
            
            # Calculate overall rating
            favorable_count = sum(1 for t in threat_coverage.values() if t["matchup"] == "Favorable")
            unfavorable_count = sum(1 for t in threat_coverage.values() if t["matchup"] == "Unfavorable")
            
            if favorable_count > unfavorable_count * 2:
                overall_rating = "A"
            elif favorable_count > unfavorable_count:
                overall_rating = "B+"
            elif favorable_count == unfavorable_count:
                overall_rating = "B"
            elif unfavorable_count > favorable_count:
                overall_rating = "C+"
            else:
                overall_rating = "C"
            
            # Build markdown summary
            markdown_lines = [
                "## Team Matchup Analysis",
                "",
                "### Your Team",
                " | ".join([p.title() for p in team_pokemon]),
                "",
                "### Matchup Summary",
                "| Rating | Description |",
                "|--------|-------------|",
                f"| **{overall_rating}** | {'Good matchup vs current meta' if overall_rating in ['A', 'B+'] else 'Needs improvement'} |",
                "",
                "### Threat Coverage",
                "| Meta Threat | Best Answer | Matchup |",
                "|-------------|-------------|---------|"
            ]
            
            for threat_name, data in list(threat_coverage.items())[:10]:  # Top 10
                markdown_lines.append(
                    f"| {threat_name.title()} | {data['best_answer']} | {data['matchup']} |"
                )
            
            # Identify weaknesses
            if unfavorable_count > 0:
                markdown_lines.extend([
                    "",
                    "### Weaknesses Identified",
                ])
                weak_threats = [t for t, d in threat_coverage.items() if d["matchup"] == "Unfavorable"]
                for i, threat in enumerate(weak_threats[:3], 1):
                    markdown_lines.append(f"{i}. **{threat.title()} problematic** - Consider adding checks")
            
            response = {
                "team": team_pokemon,
                "overall_rating": overall_rating,
                "threat_coverage": threat_coverage,
                "favorable_matchups": favorable_count,
                "unfavorable_matchups": unfavorable_count,
                "markdown_summary": "\n".join(markdown_lines)
            }
            if is_champions:
                response["format_system"] = "champions"

            return response
            
        except Exception as e:
            logger.error(f"Error in analyze_team_matchup: {e}", exc_info=True)
            return api_error(str(e))
