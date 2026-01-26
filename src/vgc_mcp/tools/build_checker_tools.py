"""MCP tools for checking Pokemon builds for common mistakes."""

from typing import Optional, List
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.models.pokemon import Nature, get_nature_modifier
from vgc_mcp_core.models.move import MoveCategory
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name


def register_build_checker_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register build checker tools."""

    @mcp.tool()
    async def check_build_for_mistakes(
        pokemon_name: str,
        nature: str,
        evs: dict,
        moves: List[str],
        item: Optional[str] = None,
        ability: Optional[str] = None
    ) -> dict:
        """
        Check a Pokemon build for common beginner mistakes.
        
        Args:
            pokemon_name: Pokemon name
            nature: Nature (e.g., "timid", "adamant")
            evs: Dict with hp, attack, defense, special_attack, special_defense, speed
            moves: List of move names
            item: Optional item name
            ability: Optional ability name
            
        Returns:
            Build analysis with issues found and recommendations
        """
        try:
            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            
            # Parse nature
            try:
                nature_enum = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}
            
            # Fetch move data
            move_data = []
            physical_moves = 0
            special_moves = 0
            
            for move_name in moves:
                try:
                    move = await pokeapi.get_move(move_name)
                    move_data.append(move)
                    if move.category == MoveCategory.PHYSICAL:
                        physical_moves += 1
                    elif move.category == MoveCategory.SPECIAL:
                        special_moves += 1
                except Exception:
                    continue
            
            issues = []
            recommendations = []
            rating_score = 100
            
            # Check 1: Nature/Move mismatch
            nature_mod_atk = get_nature_modifier(nature_enum, "attack")
            nature_mod_spa = get_nature_modifier(nature_enum, "special_attack")
            
            if nature_mod_atk < 1.0 and physical_moves > 0 and special_moves == 0:
                # Nature lowers Attack but only physical moves
                issues.append({
                    "severity": "CRITICAL",
                    "type": "nature_move_mismatch",
                    "message": f"You have {nature.title()} nature (+{nature_enum.value.split('_')[0].title()}, -{nature_enum.value.split('_')[1].title() if '_' in nature_enum.value else 'Atk'}) but all your moves are Physical.",
                    "fix": "Change nature to Jolly (+Spe, -SpA) or Adamant (+Atk, -SpA)"
                })
                rating_score -= 30
            
            if nature_mod_spa < 1.0 and special_moves > 0 and physical_moves == 0:
                # Nature lowers SpA but only special moves
                issues.append({
                    "severity": "CRITICAL",
                    "type": "nature_move_mismatch",
                    "message": f"You have {nature.title()} nature but all your moves are Special.",
                    "fix": "Change nature to Timid (+Spe, -Atk) or Modest (+SpA, -Atk)"
                })
                rating_score -= 30
            
            # Check 2: EVs not in multiples of 4
            wasted_evs = []
            for stat_name, ev_value in evs.items():
                if ev_value > 0 and ev_value % 4 != 0:
                    wasted = ev_value % 4
                    wasted_evs.append({
                        "stat": stat_name,
                        "current": ev_value,
                        "wasted": wasted,
                        "suggestion": ev_value - wasted
                    })
            
            if wasted_evs:
                issues.append({
                    "severity": "MINOR",
                    "type": "wasted_evs",
                    "message": f"EVs not in multiples of 4: {', '.join([f'{w['stat']}: {w['wasted']} wasted' for w in wasted_evs])}",
                    "fix": f"Adjust EVs to multiples of 4: {', '.join([f'{w['stat']}: {w['suggestion']}' for w in wasted_evs])}"
                })
                rating_score -= 5 * len(wasted_evs)
            
            # Check 3: No Protect on non-Choice Pokemon
            has_protect = any("protect" in m.lower() for m in moves)
            is_choice_item = item and ("choice" in item.lower() or item.lower() in ["choice-band", "choice-specs", "choice-scarf"])
            
            if not has_protect and not is_choice_item and len(moves) == 4:
                recommendations.append({
                    "type": "missing_protect",
                    "message": "Consider adding Protect - it's essential for scouting and avoiding damage",
                    "priority": "MEDIUM"
                })
            
            # Check 4: Total EVs
            total_evs = sum(evs.values())
            if total_evs > 508:
                issues.append({
                    "severity": "CRITICAL",
                    "type": "too_many_evs",
                    "message": f"Total EVs ({total_evs}) exceed maximum of 508",
                    "fix": "Reduce EVs to total 508 or less"
                })
                rating_score -= 20
            elif total_evs < 508:
                recommendations.append({
                    "type": "unused_evs",
                    "message": f"You have {508 - total_evs} unused EVs. Consider investing them.",
                    "priority": "LOW"
                })
            
            # Determine rating
            if rating_score >= 90:
                rating = "A"
            elif rating_score >= 80:
                rating = "B+"
            elif rating_score >= 70:
                rating = "B"
            elif rating_score >= 60:
                rating = "C+"
            else:
                rating = "C"
            
            # Build markdown output
            markdown_lines = [
                f"## Build Check: {pokemon_name.title()}",
                ""
            ]
            
            if issues:
                markdown_lines.append(f"### Issues Found: {len(issues)}")
                markdown_lines.append("")
                
                for i, issue in enumerate(issues, 1):
                    severity_emoji = "🔴" if issue["severity"] == "CRITICAL" else "🟡"
                    markdown_lines.extend([
                        f"#### Issue {i}: {issue['type'].replace('_', ' ').title()} ({issue['severity']})",
                        f"{severity_emoji} {issue['message']}",
                        "",
                        f"**Fix:** {issue['fix']}",
                        ""
                    ])
            else:
                markdown_lines.append("### ✅ No Critical Issues Found!")
                markdown_lines.append("")
            
            if recommendations:
                markdown_lines.extend([
                    "### Recommendations",
                    ""
                ])
                for i, rec in enumerate(recommendations, 1):
                    markdown_lines.append(f"{i}. {rec['message']}")
                markdown_lines.append("")
            
            markdown_lines.extend([
                f"### Build Rating: {rating} ({rating_score}/100)",
                ""
            ])
            
            # Good things
            good_things = []
            if nature_mod_atk > 1.0 and physical_moves > 0:
                good_things.append("Nature matches your physical moves")
            if nature_mod_spa > 1.0 and special_moves > 0:
                good_things.append("Nature matches your special moves")
            if total_evs == 508:
                good_things.append("All EVs are allocated efficiently")
            
            if good_things:
                markdown_lines.extend([
                    "### Good Things About This Build",
                    ""
                ])
                for thing in good_things:
                    markdown_lines.append(f"- {thing}")
            
            response = {
                "pokemon": pokemon_name,
                "rating": rating,
                "rating_score": rating_score,
                "issues": issues,
                "recommendations": recommendations,
                "good_things": good_things,
                "markdown_summary": "\n".join(markdown_lines)
            }
            
            return response
            
        except Exception as e:
            logger.error(f"Error in check_build_for_mistakes: {e}", exc_info=True)
            error_str = str(e).lower()
            if "not found" in error_str:
                suggestions = suggest_pokemon_name(pokemon_name)
                return pokemon_not_found_error(pokemon_name, suggestions)
            return api_error(str(e))
