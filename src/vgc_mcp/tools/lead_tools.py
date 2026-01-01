"""Lead selection analysis tools for VGC MCP server.

Tools for analyzing optimal Pokemon selection and lead pairs:
- Bring-4 selection against opponent teams
- Lead pair analysis
- Matchup matrices
- Back-pair recommendations
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
from itertools import combinations

from ..team.manager import TeamManager
from ..calc.matchup import COMMON_THREATS, analyze_threat_matchup
from ..utils.errors import error_response, success_response


def register_lead_tools(mcp: FastMCP, team_manager: TeamManager):
    """Register lead selection analysis tools."""

    @mcp.tool()
    async def analyze_bring_four(
        opponent_pokemon: str,
        my_team_override: Optional[str] = None
    ) -> dict:
        """
        Analyze which 4 Pokemon to bring against an opponent's team.

        In VGC, you see your opponent's 6 Pokemon and choose 4 to bring.
        This tool scores each Pokemon's usefulness against the opponent.

        Args:
            opponent_pokemon: Comma-separated opponent team (e.g., "flutter-mane, iron-hands, incineroar, rillaboom, urshifu, dragapult")
            my_team_override: Optional comma-separated override for your team

        Returns:
            Recommended 4 Pokemon to bring with reasoning
        """
        try:
            if team_manager.size == 0 and not my_team_override:
                return error_response(
                    "no_team",
                    "No team loaded. Add Pokemon first or provide my_team_override.",
                    suggestions=["Use add_pokemon or import_showdown_team first"]
                )

            # Parse opponent Pokemon
            opponents = [p.strip().lower().replace(" ", "-") for p in opponent_pokemon.split(",")]
            if len(opponents) < 2:
                return error_response(
                    "invalid_opponent_team",
                    "Need at least 2 opponent Pokemon for analysis",
                    suggestions=["Format: 'flutter-mane, iron-hands, incineroar'"]
                )

            # Get my team
            if my_team_override:
                my_pokemon = [p.strip().lower().replace(" ", "-") for p in my_team_override.split(",")]
            else:
                my_pokemon = [p.lower().replace(" ", "-") for p in team_manager.team.get_pokemon_names()]

            if len(my_pokemon) < 4:
                return error_response(
                    "team_too_small",
                    f"Need at least 4 Pokemon on team, have {len(my_pokemon)}",
                    suggestions=["Add more Pokemon to team"]
                )

            # Score each Pokemon against opponent team
            pokemon_scores = {}
            pokemon_details = {}

            for mon in my_pokemon:
                score = 0
                details = {
                    "threats_to": [],
                    "threatens": [],
                    "neutral": [],
                    "utility_notes": []
                }

                for opp in opponents:
                    # Check if opponent is a known threat
                    if opp in COMMON_THREATS:
                        threat_data = COMMON_THREATS[opp]
                        opp_types = threat_data["types"]

                        # Simple type-based scoring
                        # This would be more sophisticated with full damage calc
                        score_vs = _estimate_matchup_score(mon, opp, opp_types)

                        if score_vs > 0:
                            details["threatens"].append(opp)
                            score += score_vs
                        elif score_vs < 0:
                            details["threats_to"].append(opp)
                            score += score_vs
                        else:
                            details["neutral"].append(opp)
                    else:
                        # Unknown opponent, treat as neutral
                        details["neutral"].append(opp)

                # Add utility bonuses
                if mon in ["incineroar"]:
                    details["utility_notes"].append("Intimidate + Fake Out support")
                    score += 2
                if mon in ["rillaboom"]:
                    details["utility_notes"].append("Grassy Terrain + priority")
                    score += 1
                if mon in ["amoonguss"]:
                    details["utility_notes"].append("Redirection + Spore")
                    score += 2
                if mon in ["flutter-mane"]:
                    details["utility_notes"].append("High speed + spread damage")
                    score += 1

                pokemon_scores[mon] = score
                pokemon_details[mon] = details

            # Sort by score and recommend top 4
            sorted_pokemon = sorted(pokemon_scores.items(), key=lambda x: x[1], reverse=True)
            recommended = [p[0] for p in sorted_pokemon[:4]]
            bench = [p[0] for p in sorted_pokemon[4:]]

            # Build reasoning
            recommendations = []
            for mon, score in sorted_pokemon[:4]:
                detail = pokemon_details[mon]
                reason_parts = []
                if detail["threatens"]:
                    reason_parts.append(f"threatens {', '.join(detail['threatens'][:2])}")
                if detail["utility_notes"]:
                    reason_parts.append(detail["utility_notes"][0])
                recommendations.append({
                    "pokemon": mon,
                    "score": score,
                    "reason": "; ".join(reason_parts) if reason_parts else "General coverage"
                })

            return {
                "opponent_team": opponents,
                "recommended_4": recommended,
                "leave_behind": bench,
                "selection_details": recommendations,
                "matchup_scores": dict(sorted_pokemon),
                "notes": [
                    "Scores are estimates based on type matchups and utility",
                    "Consider speed control needs when finalizing",
                    "Adjust for known opponent tendencies"
                ]
            }

        except Exception as e:
            return error_response("analysis_error", str(e))

    @mcp.tool()
    async def suggest_lead_pair(
        opponent_pokemon: str,
        bring_four: Optional[str] = None
    ) -> dict:
        """
        Suggest optimal lead pairs for turn 1.

        Analyzes which 2 Pokemon make the best opening combination
        against the opponent's likely leads.

        Args:
            opponent_pokemon: Comma-separated opponent team
            bring_four: Optional comma-separated list of your 4 brought Pokemon

        Returns:
            Recommended lead pairs with reasoning
        """
        try:
            if team_manager.size == 0 and not bring_four:
                return error_response(
                    "no_team",
                    "No team loaded. Provide bring_four or load a team first."
                )

            # Parse opponent
            opponents = [p.strip().lower().replace(" ", "-") for p in opponent_pokemon.split(",")]

            # Get our 4
            if bring_four:
                four = [p.strip().lower().replace(" ", "-") for p in bring_four.split(",")]
            else:
                names = team_manager.team.get_pokemon_names()[:4]
                four = [p.lower().replace(" ", "-") for p in names]

            if len(four) < 2:
                return error_response("need_more_pokemon", "Need at least 2 Pokemon")

            # Evaluate all possible lead pairs
            lead_options = []

            for lead1, lead2 in combinations(four, 2):
                score = 0
                synergies = []
                concerns = []

                # Check for good lead synergies
                # Fake Out support
                if lead1 in ["incineroar", "rillaboom", "iron-hands"] or lead2 in ["incineroar", "rillaboom", "iron-hands"]:
                    fake_out_user = lead1 if lead1 in ["incineroar", "rillaboom", "iron-hands"] else lead2
                    synergies.append(f"{fake_out_user} provides Fake Out pressure")
                    score += 3

                # Speed control pairs
                if _has_speed_control(lead1) and not _has_speed_control(lead2):
                    synergies.append("Speed control + attacker combo")
                    score += 2
                elif _has_speed_control(lead1) and _has_speed_control(lead2):
                    concerns.append("Both have speed control - redundant")
                    score -= 1

                # Redirection
                if lead1 in ["amoonguss", "indeedee-female", "gothitelle"] or lead2 in ["amoonguss", "indeedee-female", "gothitelle"]:
                    synergies.append("Redirection support available")
                    score += 2

                # Offensive pressure
                if lead1 in ["flutter-mane", "chi-yu", "urshifu-rapid-strike"] and lead2 in ["flutter-mane", "chi-yu", "urshifu-rapid-strike"]:
                    synergies.append("Double offensive pressure")
                    score += 2

                # Check for shared weaknesses
                shared_weak = _check_shared_weaknesses(lead1, lead2)
                if shared_weak:
                    concerns.append(f"Shared weakness to {', '.join(shared_weak)}")
                    score -= len(shared_weak)

                # Check vs likely opponent leads
                opponent_lead_threats = opponents[:2] if len(opponents) >= 2 else opponents
                for opp in opponent_lead_threats:
                    if opp in COMMON_THREATS:
                        opp_types = COMMON_THREATS[opp]["types"]
                        if _can_threaten(lead1, opp_types) or _can_threaten(lead2, opp_types):
                            score += 1

                back_pair = [p for p in four if p not in [lead1, lead2]]

                lead_options.append({
                    "lead_pair": [lead1, lead2],
                    "back_pair": back_pair,
                    "score": score,
                    "synergies": synergies,
                    "concerns": concerns
                })

            # Sort by score
            lead_options.sort(key=lambda x: x["score"], reverse=True)

            return {
                "opponent_team": opponents,
                "your_four": four,
                "recommended_lead": lead_options[0] if lead_options else None,
                "alternative_leads": lead_options[1:3] if len(lead_options) > 1 else [],
                "all_options": lead_options,
                "tips": [
                    "Lead Fake Out users when expecting setup or frail leads",
                    "Lead speed control when outsped by opponent",
                    "Consider opponent's likely Protect turn 1"
                ]
            }

        except Exception as e:
            return error_response("analysis_error", str(e))

    @mcp.tool()
    async def generate_matchup_matrix(
        my_team: Optional[str] = None,
        opponent_team: str = ""
    ) -> dict:
        """
        Generate a matchup matrix showing how each of your Pokemon
        fares against each opponent Pokemon.

        Args:
            my_team: Optional comma-separated team (uses loaded team if not provided)
            opponent_team: Comma-separated opponent Pokemon

        Returns:
            Matrix showing favorable/unfavorable matchups
        """
        try:
            # Get my team
            if my_team:
                my_pokemon = [p.strip().lower().replace(" ", "-") for p in my_team.split(",")]
            elif team_manager.size > 0:
                my_pokemon = [p.lower().replace(" ", "-") for p in team_manager.team.get_pokemon_names()]
            else:
                return error_response("no_team", "No team loaded and no my_team provided")

            if not opponent_team:
                return error_response("no_opponent", "No opponent_team provided")

            opponents = [p.strip().lower().replace(" ", "-") for p in opponent_team.split(",")]

            # Build matrix
            matrix = {}
            for mon in my_pokemon:
                matrix[mon] = {}
                for opp in opponents:
                    if opp in COMMON_THREATS:
                        opp_types = COMMON_THREATS[opp]["types"]
                        score = _estimate_matchup_score(mon, opp, opp_types)
                        if score >= 2:
                            matchup = "favorable"
                        elif score >= 1:
                            matchup = "slight_advantage"
                        elif score <= -2:
                            matchup = "unfavorable"
                        elif score <= -1:
                            matchup = "slight_disadvantage"
                        else:
                            matchup = "neutral"
                        matrix[mon][opp] = {
                            "rating": matchup,
                            "score": score
                        }
                    else:
                        matrix[mon][opp] = {
                            "rating": "unknown",
                            "score": 0
                        }

            # Summarize
            best_answers = {}
            for opp in opponents:
                best_for_opp = max(
                    [(mon, matrix[mon][opp]["score"]) for mon in my_pokemon],
                    key=lambda x: x[1]
                )
                best_answers[opp] = best_for_opp[0]

            problem_pokemon = []
            for opp in opponents:
                scores = [matrix[mon][opp]["score"] for mon in my_pokemon]
                if max(scores) <= 0:
                    problem_pokemon.append(opp)

            return {
                "my_team": my_pokemon,
                "opponent_team": opponents,
                "matrix": matrix,
                "best_answers": best_answers,
                "problem_pokemon": problem_pokemon,
                "summary": {
                    "favorable_matchups": sum(
                        1 for mon in my_pokemon for opp in opponents
                        if matrix[mon][opp]["rating"] in ["favorable", "slight_advantage"]
                    ),
                    "unfavorable_matchups": sum(
                        1 for mon in my_pokemon for opp in opponents
                        if matrix[mon][opp]["rating"] in ["unfavorable", "slight_disadvantage"]
                    ),
                    "neutral_matchups": sum(
                        1 for mon in my_pokemon for opp in opponents
                        if matrix[mon][opp]["rating"] == "neutral"
                    )
                }
            }

        except Exception as e:
            return error_response("analysis_error", str(e))

    @mcp.tool()
    async def analyze_back_pair(
        lead_pair: str,
        four_brought: str
    ) -> dict:
        """
        Analyze the back pair options given your lead selection.

        Your back 2 Pokemon should cover weaknesses of your leads
        and provide late-game options.

        Args:
            lead_pair: Comma-separated lead Pokemon (e.g., "incineroar, flutter-mane")
            four_brought: Comma-separated 4 Pokemon you brought

        Returns:
            Analysis of back pair strengths and role
        """
        try:
            leads = [p.strip().lower().replace(" ", "-") for p in lead_pair.split(",")]
            four = [p.strip().lower().replace(" ", "-") for p in four_brought.split(",")]

            if len(leads) != 2:
                return error_response("invalid_leads", "Lead pair must be exactly 2 Pokemon")
            if len(four) != 4:
                return error_response("invalid_four", "Must bring exactly 4 Pokemon")

            # Find back pair
            back = [p for p in four if p not in leads]
            if len(back) != 2:
                return error_response("invalid_selection", "Lead Pokemon must be from your brought 4")

            # Analyze back pair role
            lead_weaknesses = _get_combined_weaknesses(leads[0], leads[1])
            back_coverage = []

            for bp in back:
                covers = []
                for weak in lead_weaknesses:
                    if _resists_type(bp, weak):
                        covers.append(weak)
                if covers:
                    back_coverage.append({
                        "pokemon": bp,
                        "covers_weaknesses": covers
                    })

            # Check for late-game roles
            late_game_roles = []
            for bp in back:
                if bp in ["urshifu-rapid-strike", "dragapult", "flutter-mane"]:
                    late_game_roles.append(f"{bp}: Fast cleaner")
                elif bp in ["iron-hands", "archaludon"]:
                    late_game_roles.append(f"{bp}: Bulky win condition")
                elif bp in ["dondozo", "garganacl"]:
                    late_game_roles.append(f"{bp}: Endgame wall")
                elif bp in ["incineroar"]:
                    late_game_roles.append(f"{bp}: Pivot/cycle Intimidate")

            # Synergy check
            synergy_notes = []
            if _has_speed_control(back[0]) or _has_speed_control(back[1]):
                synergy_notes.append("Speed control available in back")
            if back[0] in ["incineroar"] or back[1] in ["incineroar"]:
                synergy_notes.append("Can cycle Intimidate from back")

            return {
                "lead_pair": leads,
                "back_pair": back,
                "lead_weaknesses": lead_weaknesses,
                "back_coverage": back_coverage,
                "late_game_roles": late_game_roles,
                "synergy_notes": synergy_notes,
                "strategy_suggestions": [
                    "Bring in back Pokemon to handle what leads struggle against",
                    "Preserve back win conditions if leads create early advantage",
                    "Consider double switches if opponent has your lead countered"
                ]
            }

        except Exception as e:
            return error_response("analysis_error", str(e))


# Helper functions for lead analysis

def _estimate_matchup_score(mon: str, opponent: str, opp_types: list) -> int:
    """
    Estimate matchup score based on type matchups.
    Positive = favorable, Negative = unfavorable.
    """
    # Get mon types (simplified - would be better with API lookup)
    mon_types = _get_pokemon_types(mon)

    score = 0

    # Check if we can threaten opponent
    for mon_type in mon_types:
        for opp_type in opp_types:
            eff = _get_effectiveness(mon_type.lower(), opp_type.lower())
            if eff == 2.0:
                score += 2
            elif eff == 0.5:
                score -= 1
            elif eff == 0:
                score -= 2

    # Check if opponent threatens us
    for opp_type in opp_types:
        for mon_type in mon_types:
            eff = _get_effectiveness(opp_type.lower(), mon_type.lower())
            if eff == 2.0:
                score -= 2
            elif eff == 0.5:
                score += 1
            elif eff == 0:
                score += 2

    return score


def _get_pokemon_types(mon: str) -> list:
    """Get Pokemon types (simplified mapping for common VGC Pokemon)."""
    type_map = {
        "flutter-mane": ["Ghost", "Fairy"],
        "dragapult": ["Dragon", "Ghost"],
        "urshifu-rapid-strike": ["Fighting", "Water"],
        "chi-yu": ["Dark", "Fire"],
        "iron-hands": ["Fighting", "Electric"],
        "rillaboom": ["Grass"],
        "incineroar": ["Fire", "Dark"],
        "amoonguss": ["Grass", "Poison"],
        "gholdengo": ["Steel", "Ghost"],
        "landorus": ["Ground", "Flying"],
        "tornadus": ["Flying"],
        "iron-bundle": ["Ice", "Water"],
        "iron-moth": ["Fire", "Poison"],
        "great-tusk": ["Ground", "Fighting"],
        "garganacl": ["Rock"],
        "dondozo": ["Water"],
        "palafin": ["Water"],
        "archaludon": ["Steel", "Dragon"],
        "kingambit": ["Dark", "Steel"],
        "annihilape": ["Fighting", "Ghost"],
        "indeedee-female": ["Psychic", "Normal"],
        "gothitelle": ["Psychic"],
        "ogerpon": ["Grass"],
        "farigiraf": ["Normal", "Psychic"],
        "arcanine": ["Fire"],
        "pelipper": ["Water", "Flying"],
    }
    return type_map.get(mon, ["Normal"])


def _get_effectiveness(attack_type: str, defend_type: str) -> float:
    """Get type effectiveness multiplier."""
    chart = {
        ("fire", "grass"): 2.0, ("fire", "ice"): 2.0, ("fire", "bug"): 2.0, ("fire", "steel"): 2.0,
        ("water", "fire"): 2.0, ("water", "ground"): 2.0, ("water", "rock"): 2.0,
        ("grass", "water"): 2.0, ("grass", "ground"): 2.0, ("grass", "rock"): 2.0,
        ("electric", "water"): 2.0, ("electric", "flying"): 2.0,
        ("ice", "grass"): 2.0, ("ice", "ground"): 2.0, ("ice", "flying"): 2.0, ("ice", "dragon"): 2.0,
        ("fighting", "normal"): 2.0, ("fighting", "ice"): 2.0, ("fighting", "rock"): 2.0, ("fighting", "dark"): 2.0, ("fighting", "steel"): 2.0,
        ("ground", "fire"): 2.0, ("ground", "electric"): 2.0, ("ground", "poison"): 2.0, ("ground", "rock"): 2.0, ("ground", "steel"): 2.0,
        ("flying", "grass"): 2.0, ("flying", "fighting"): 2.0, ("flying", "bug"): 2.0,
        ("psychic", "fighting"): 2.0, ("psychic", "poison"): 2.0,
        ("bug", "grass"): 2.0, ("bug", "psychic"): 2.0, ("bug", "dark"): 2.0,
        ("rock", "fire"): 2.0, ("rock", "ice"): 2.0, ("rock", "flying"): 2.0, ("rock", "bug"): 2.0,
        ("ghost", "ghost"): 2.0, ("ghost", "psychic"): 2.0,
        ("dragon", "dragon"): 2.0,
        ("dark", "psychic"): 2.0, ("dark", "ghost"): 2.0,
        ("steel", "ice"): 2.0, ("steel", "rock"): 2.0, ("steel", "fairy"): 2.0,
        ("fairy", "fighting"): 2.0, ("fairy", "dragon"): 2.0, ("fairy", "dark"): 2.0,
        ("poison", "grass"): 2.0, ("poison", "fairy"): 2.0,
        # Immunities
        ("normal", "ghost"): 0, ("ghost", "normal"): 0,
        ("fighting", "ghost"): 0,
        ("ground", "flying"): 0,
        ("electric", "ground"): 0,
        ("psychic", "dark"): 0,
        ("dragon", "fairy"): 0,
        ("poison", "steel"): 0,
    }
    return chart.get((attack_type, defend_type), 1.0)


def _has_speed_control(mon: str) -> bool:
    """Check if Pokemon commonly runs speed control."""
    speed_controllers = [
        "tornadus", "whimsicott", "murkrow",  # Tailwind
        "indeedee-female", "gothitelle", "porygon2", "dusclops", "cresselia",  # Trick Room
        "pelipper",  # Rain + Tailwind sometimes
    ]
    return mon in speed_controllers


def _check_shared_weaknesses(mon1: str, mon2: str) -> list:
    """Find types both Pokemon are weak to."""
    types1 = _get_pokemon_types(mon1)
    types2 = _get_pokemon_types(mon2)

    all_attack_types = ["fire", "water", "grass", "electric", "ice", "fighting", "ground",
                        "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark",
                        "steel", "fairy", "poison", "normal"]

    shared = []
    for atk in all_attack_types:
        weak1 = any(_get_effectiveness(atk, t.lower()) >= 2.0 for t in types1)
        weak2 = any(_get_effectiveness(atk, t.lower()) >= 2.0 for t in types2)
        if weak1 and weak2:
            shared.append(atk.title())

    return shared


def _can_threaten(mon: str, opp_types: list) -> bool:
    """Check if mon can hit opponent super effectively."""
    mon_types = _get_pokemon_types(mon)
    for mt in mon_types:
        for ot in opp_types:
            if _get_effectiveness(mt.lower(), ot.lower()) >= 2.0:
                return True
    return False


def _get_combined_weaknesses(mon1: str, mon2: str) -> list:
    """Get all weaknesses of both leads."""
    types1 = _get_pokemon_types(mon1)
    types2 = _get_pokemon_types(mon2)
    all_types = types1 + types2

    all_attack_types = ["fire", "water", "grass", "electric", "ice", "fighting", "ground",
                        "flying", "psychic", "bug", "rock", "ghost", "dragon", "dark",
                        "steel", "fairy", "poison"]

    weaknesses = set()
    for atk in all_attack_types:
        for def_type in all_types:
            if _get_effectiveness(atk, def_type.lower()) >= 2.0:
                weaknesses.add(atk.title())

    return list(weaknesses)


def _resists_type(mon: str, attack_type: str) -> bool:
    """Check if Pokemon resists or is immune to a type."""
    mon_types = _get_pokemon_types(mon)
    for mt in mon_types:
        eff = _get_effectiveness(attack_type.lower(), mt.lower())
        if eff <= 0.5:
            return True
    return False
