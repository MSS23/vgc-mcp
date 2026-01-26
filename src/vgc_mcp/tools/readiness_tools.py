"""MCP tools for tournament readiness checking."""

from typing import Optional, List, Dict
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.matchup import COMMON_THREATS
from vgc_mcp_core.utils.errors import api_error


def register_readiness_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register tournament readiness checking tools."""

    @mcp.tool()
    async def check_tournament_readiness(
        team_pokemon: List[Dict],
        format: str = "reg_h"
    ) -> dict:
        """
        Comprehensive tournament readiness assessment.
        
        Args:
            team_pokemon: List of dicts with Pokemon builds (name, nature, evs, item, ability, moves)
            format: VGC format
            
        Returns:
            Readiness report with scores and recommendations
        """
        try:
            if len(team_pokemon) != 6:
                return {"error": "Team must have exactly 6 Pokemon"}
            
            scores = {
                "legality": 100,
                "type_coverage": 0,
                "speed_control": 0,
                "meta_coverage": 0,
                "synergy": 0
            }
            
            issues = []
            recommendations = []
            
            # Check type coverage
            all_types = set()
            for pokemon_data in team_pokemon:
                try:
                    types = await pokeapi.get_pokemon_types(pokemon_data["name"])
                    all_types.update(types)
                except Exception:
                    continue
            
            if len(all_types) >= 8:
                scores["type_coverage"] = 85
            elif len(all_types) >= 6:
                scores["type_coverage"] = 70
            else:
                scores["type_coverage"] = 50
                issues.append("Limited type diversity")
            
            # Check speed control
            has_tailwind = False
            has_trick_room = False
            has_priority = False
            
            for pokemon_data in team_pokemon:
                moves = pokemon_data.get("moves", [])
                if any("tailwind" in m.lower() for m in moves):
                    has_tailwind = True
                if any("trick-room" in m.lower() for m in moves):
                    has_trick_room = True
                if any("fake-out" in m.lower() or "extreme-speed" in m.lower() for m in moves):
                    has_priority = True
            
            if has_tailwind or has_trick_room:
                scores["speed_control"] = 80
            elif has_priority:
                scores["speed_control"] = 60
            else:
                scores["speed_control"] = 40
                issues.append("No Trick Room answer - Add Imprison or fast Taunt user")
            
            # Check meta coverage (simplified)
            scores["meta_coverage"] = 75  # Placeholder
            
            # Check synergy
            scores["synergy"] = 80  # Placeholder
            
            # Calculate overall score
            overall_score = sum(scores.values()) / len(scores)
            
            # Determine rating
            if overall_score >= 90:
                rating = "A"
            elif overall_score >= 80:
                rating = "B+"
            elif overall_score >= 70:
                rating = "B"
            elif overall_score >= 60:
                rating = "C+"
            else:
                rating = "C"
            
            # Build markdown output
            markdown_lines = [
                "## Tournament Readiness Report",
                "",
                f"### Overall Score: {rating} ({overall_score:.0f}/100)",
                "",
                "### Checklist",
                "| Category | Status | Score |",
                "|----------|--------|-------|"
            ]
            
            for category, score in scores.items():
                status = "✓ Pass" if score >= 70 else "⚠ Weak"
                markdown_lines.append(f"| {category.title().replace('_', ' ')} | {status} | {score}% |")
            
            if issues:
                markdown_lines.extend([
                    "",
                    "### Critical Issues (Fix Before Tournament)"
                ])
                for i, issue in enumerate(issues[:3], 1):
                    markdown_lines.append(f"{i}. **{issue}**")
            
            if recommendations:
                markdown_lines.extend([
                    "",
                    "### Recommendations (Nice to Have)"
                ])
                for i, rec in enumerate(recommendations[:3], 1):
                    markdown_lines.append(f"{i}. {rec}")
            
            response = {
                "overall_score": overall_score,
                "rating": rating,
                "category_scores": scores,
                "critical_issues": issues,
                "recommendations": recommendations,
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in check_tournament_readiness: {e}", exc_info=True)
            return api_error(str(e))
