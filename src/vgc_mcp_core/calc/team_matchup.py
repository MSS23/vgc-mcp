"""Team vs team matchup analysis with scoring algorithm."""

from dataclasses import dataclass, field
from typing import Optional

from ..models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread, IVSpread
from ..models.move import Move, MoveCategory
from ..models.team import Team
from .damage import calculate_damage, DamageResult
from .stats import calculate_all_stats
from .modifiers import DamageModifiers, get_type_effectiveness


@dataclass
class MatchupScore:
    """Score for a single 1v1 Pokemon matchup (0-100 scale)."""
    pokemon1_name: str
    pokemon2_name: str
    damage_score: float = 0.0      # 0-40 (OHKO=40, 2HKO=30, 3HKO=20, 4HKO+=10)
    speed_score: float = 0.0       # 0-25 (outspeeds=25, tie=12.5, priority=15)
    defensive_score: float = 0.0   # 0-25 (survives=25, takes 1 hit=15, OHKO'd=0)
    type_score: float = 0.0        # 0-10 (SE STAB=10, neutral=5, resisted=0)

    best_move: Optional[str] = None
    damage_range: str = ""
    ko_chance: str = ""
    outspeeds: bool = False
    survives_hit: bool = False

    @property
    def total(self) -> float:
        """Total matchup score (0-100)."""
        return self.damage_score + self.speed_score + self.defensive_score + self.type_score

    @property
    def net_advantage(self) -> float:
        """Net advantage (-100 to +100, positive = pokemon1 favored)."""
        return self.total - 50  # 50 is neutral


@dataclass
class LeadMatchup:
    """Analysis of a potential lead pair vs opponent's lead pair."""
    your_lead1: str
    your_lead2: str
    their_lead1: str
    their_lead2: str
    advantage_score: float  # -100 to +100
    reasoning: str
    recommended: bool = False


@dataclass
class ThreatInfo:
    """Information about a key threat on opponent's team."""
    pokemon_name: str
    danger_level: str  # "HIGH", "MEDIUM", "LOW"
    reason: str
    your_best_answer: str
    answer_move: str
    answer_damage: str


@dataclass
class TeamMatchupResult:
    """Full result of team vs team matchup analysis."""
    your_team_name: str
    opponent_team_name: str
    overall_advantage: float  # 0-100%, 50% = even
    matchup_matrix: list[list[float]]  # 6x6 net advantage scores
    your_pokemon_names: list[str]
    opponent_pokemon_names: list[str]
    key_threats: list[ThreatInfo]
    your_key_pokemon: list[str]  # Most important Pokemon to preserve
    recommended_leads: list[LeadMatchup]
    speed_advantages: dict  # Your Pokemon -> list of opponent Pokemon they outspeed
    game_plan: str
    detailed_matchups: list[MatchupScore]


# Role weights for calculating overall team advantage
ROLE_WEIGHTS = {
    # Restricted legendaries
    "koraidon": 1.5, "miraidon": 1.5, "calyrex-shadow": 1.5, "calyrex-ice": 1.5,
    "zacian": 1.5, "zacian-crowned": 1.5, "kyogre": 1.5, "groudon": 1.5,
    "rayquaza": 1.5, "dialga": 1.5, "palkia": 1.5, "giratina": 1.5,
    "reshiram": 1.5, "zekrom": 1.5, "kyurem-white": 1.5, "kyurem-black": 1.5,
    "xerneas": 1.5, "yveltal": 1.5, "necrozma-dusk-mane": 1.5, "necrozma-dawn-wings": 1.5,
    "solgaleo": 1.5, "lunala": 1.5, "eternatus": 1.5, "terapagos": 1.5,

    # High-impact Pokemon (sweepers/wallbreakers)
    "flutter-mane": 1.3, "chi-yu": 1.3, "iron-bundle": 1.3, "chien-pao": 1.3,
    "urshifu": 1.3, "urshifu-rapid-strike": 1.3, "urshifu-single-strike": 1.3,
    "dragapult": 1.2, "iron-hands": 1.2, "raging-bolt": 1.2, "gouging-fire": 1.2,

    # Support Pokemon (still important but less weight)
    "incineroar": 1.0, "rillaboom": 1.0, "amoonguss": 0.9, "tornadus": 1.0,
    "whimsicott": 0.9, "grimmsnarl": 0.9, "indeedee-f": 0.9,
}


def get_role_weight(pokemon_name: str) -> float:
    """Get the role weight for a Pokemon (default 1.0)."""
    normalized = pokemon_name.lower().replace(" ", "-")
    return ROLE_WEIGHTS.get(normalized, 1.0)


def _create_generic_moves(pokemon: PokemonBuild) -> list[Move]:
    """Create generic STAB moves for damage calculation."""
    moves = []

    # Determine if Pokemon is physical or special based on stats
    is_physical = pokemon.base_stats.attack >= pokemon.base_stats.special_attack
    primary_category = MoveCategory.PHYSICAL if is_physical else MoveCategory.SPECIAL

    for poke_type in pokemon.types:
        moves.append(Move(
            name=f"{poke_type.lower()}-stab",
            type=poke_type,
            category=primary_category,
            power=90,  # Average strong STAB move
            accuracy=100
        ))

    return moves


def score_1v1_matchup(
    pokemon1: PokemonBuild,
    pokemon2: PokemonBuild,
    pokemon1_moves: list[Move] = None,
    pokemon2_moves: list[Move] = None
) -> MatchupScore:
    """
    Calculate matchup score for pokemon1 attacking pokemon2.

    Scoring:
    - Damage (40 max): OHKO=40, 2HKO=30, 3HKO=20, 4HKO+=10
    - Speed (25 max): Outspeeds=25, Tie=12.5, Priority=15, Slower=0
    - Defense (25 max): Survives their best=25, Takes 1 hit=15, Gets OHKO'd=0
    - Type (10 max): SE STAB=10, Neutral=5, Resisted=0

    Returns:
        MatchupScore with individual and total scores
    """
    if pokemon1_moves is None:
        pokemon1_moves = _create_generic_moves(pokemon1)
    if pokemon2_moves is None:
        pokemon2_moves = _create_generic_moves(pokemon2)

    modifiers = DamageModifiers(is_doubles=True)

    # Calculate stats
    p1_stats = calculate_all_stats(pokemon1)
    p2_stats = calculate_all_stats(pokemon2)

    p1_speed = p1_stats["speed"]
    p2_speed = p2_stats["speed"]

    # === DAMAGE SCORE (0-40) ===
    best_damage_pct = 0
    best_move_name = None
    best_result = None

    for move in pokemon1_moves:
        if move.power == 0:
            continue
        try:
            result = calculate_damage(pokemon1, pokemon2, move, modifiers)
            if result.max_percent > best_damage_pct:
                best_damage_pct = result.max_percent
                best_move_name = move.name
                best_result = result
        except Exception:
            continue

    if best_result is None:
        damage_score = 0
        ko_chance = "No damaging moves"
        damage_range = "0-0%"
    else:
        # Score based on KO potential
        if best_result.min_percent >= 100:
            damage_score = 40  # Guaranteed OHKO
        elif best_result.max_percent >= 100:
            damage_score = 35  # Possible OHKO
        elif best_result.min_percent >= 50:
            damage_score = 30  # Guaranteed 2HKO
        elif best_result.max_percent >= 50:
            damage_score = 25  # Possible 2HKO
        elif best_result.min_percent >= 34:
            damage_score = 20  # Guaranteed 3HKO
        elif best_result.max_percent >= 34:
            damage_score = 15  # Possible 3HKO
        else:
            damage_score = 10  # 4HKO or worse

        ko_chance = best_result.ko_chance
        damage_range = f"{best_result.min_percent:.1f}-{best_result.max_percent:.1f}%"

    # === SPEED SCORE (0-25) ===
    if p1_speed > p2_speed:
        speed_score = 25
        outspeeds = True
    elif p1_speed == p2_speed:
        speed_score = 12.5
        outspeeds = False  # Speed tie
    else:
        speed_score = 0
        outspeeds = False
        # Check for priority moves (simplified - check for common priority)
        priority_moves = ["extreme-speed", "aqua-jet", "mach-punch", "bullet-punch",
                        "ice-shard", "quick-attack", "sucker-punch", "grassy-glide",
                        "fake-out", "first-impression", "accelerock"]
        has_priority = any(m.name.lower() in priority_moves for m in pokemon1_moves)
        if has_priority:
            speed_score = 15

    # === DEFENSIVE SCORE (0-25) ===
    # Check if pokemon1 survives pokemon2's best attack
    opponent_best_damage = 0
    for move in pokemon2_moves:
        if move.power == 0:
            continue
        try:
            result = calculate_damage(pokemon2, pokemon1, move, modifiers)
            opponent_best_damage = max(opponent_best_damage, result.max_percent)
        except Exception:
            continue

    survives_hit = opponent_best_damage < 100
    if opponent_best_damage < 50:
        defensive_score = 25  # Survives comfortably
    elif opponent_best_damage < 75:
        defensive_score = 20  # Takes a hit well
    elif opponent_best_damage < 100:
        defensive_score = 15  # Survives but hurt
    else:
        defensive_score = 0   # Gets OHKO'd

    # === TYPE SCORE (0-10) ===
    # Check if pokemon1 has super effective STAB
    best_type_eff = 1.0
    for poke_type in pokemon1.types:
        eff = get_type_effectiveness(poke_type, pokemon2.types)
        best_type_eff = max(best_type_eff, eff)

    if best_type_eff >= 4.0:
        type_score = 10  # 4x SE
    elif best_type_eff >= 2.0:
        type_score = 8   # 2x SE
    elif best_type_eff >= 1.0:
        type_score = 5   # Neutral
    elif best_type_eff >= 0.5:
        type_score = 2   # Resisted
    else:
        type_score = 0   # Double resisted or immune

    return MatchupScore(
        pokemon1_name=pokemon1.name,
        pokemon2_name=pokemon2.name,
        damage_score=damage_score,
        speed_score=speed_score,
        defensive_score=defensive_score,
        type_score=type_score,
        best_move=best_move_name,
        damage_range=damage_range,
        ko_chance=ko_chance,
        outspeeds=outspeeds,
        survives_hit=survives_hit
    )


def build_matchup_matrix(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild]
) -> tuple[list[list[float]], list[MatchupScore]]:
    """
    Build a 6x6 matchup matrix showing net advantage for each pairing.

    Returns:
        Tuple of (matrix of net scores, list of detailed MatchupScore objects)
    """
    matrix = []
    detailed = []

    for p1 in team1:
        row = []
        for p2 in team2:
            # Score from both sides
            score_1v2 = score_1v1_matchup(p1, p2)
            score_2v1 = score_1v1_matchup(p2, p1)

            # Net advantage (positive = team1 pokemon favored)
            net = score_1v2.total - score_2v1.total
            row.append(round(net, 1))
            detailed.append(score_1v2)
        matrix.append(row)

    return matrix, detailed


def calculate_team_advantage(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild]
) -> float:
    """
    Calculate overall team advantage percentage.

    Uses weighted matchup scoring where:
    - Each Pokemon's best matchup is weighted by role importance
    - Returns 0-100% where 50% = even matchup
    """
    matrix, _ = build_matchup_matrix(team1, team2)

    total_weighted_advantage = 0
    total_weight = 0

    for i, p1 in enumerate(team1):
        # Find this Pokemon's best matchup against opponent team
        best_matchup = max(matrix[i])
        weight = get_role_weight(p1.name)

        total_weighted_advantage += best_matchup * weight
        total_weight += weight

    # Also factor in opponent's best matchups against us (defensive consideration)
    for j, p2 in enumerate(team2):
        # Opponent's best matchup = our worst defensive matchup
        opponent_best = max(matrix[i][j] for i in range(len(team1)))
        # This is actually from team1's perspective, so negative opponent advantage
        # Skip this for now to keep it simpler

    # Normalize to 0-100% scale
    if total_weight == 0:
        return 50.0

    avg_advantage = total_weighted_advantage / total_weight

    # Map from typical range (-50 to +50) to (0% to 100%)
    # With clamping
    normalized = 50 + (avg_advantage / 2)
    return max(0, min(100, normalized))


def analyze_key_threats(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild]
) -> list[ThreatInfo]:
    """
    Identify key threats on team2 that team1 needs to address.
    """
    threats = []
    matrix, detailed = build_matchup_matrix(team1, team2)

    for j, p2 in enumerate(team2):
        # Count how many of team1's Pokemon this threatens
        threatened_count = 0
        for i in range(len(team1)):
            if matrix[i][j] < -10:  # Significant disadvantage
                threatened_count += 1

        # Find team1's best answer
        best_answer_idx = 0
        best_answer_score = matrix[0][j]
        for i in range(len(team1)):
            if matrix[i][j] > best_answer_score:
                best_answer_score = matrix[i][j]
                best_answer_idx = i

        # Determine danger level
        if threatened_count >= 4:
            danger = "HIGH"
            reason = f"Threatens {threatened_count}/6 of your team"
        elif threatened_count >= 2:
            danger = "MEDIUM"
            reason = f"Threatens {threatened_count}/6 of your team"
        else:
            danger = "LOW"
            reason = "Manageable threat"

        # Get the detailed matchup for the best answer
        answer_matchup = None
        for d in detailed:
            if d.pokemon1_name == team1[best_answer_idx].name and d.pokemon2_name == p2.name:
                answer_matchup = d
                break

        threats.append(ThreatInfo(
            pokemon_name=p2.name,
            danger_level=danger,
            reason=reason,
            your_best_answer=team1[best_answer_idx].name,
            answer_move=answer_matchup.best_move if answer_matchup else "STAB",
            answer_damage=answer_matchup.damage_range if answer_matchup else "Unknown"
        ))

    # Sort by danger level
    danger_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
    threats.sort(key=lambda t: danger_order[t.danger_level])

    return threats


def analyze_lead_matchups(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild],
    top_n: int = 3
) -> list[LeadMatchup]:
    """
    Analyze potential lead combinations and recommend the best ones.
    """
    leads = []
    matrix, _ = build_matchup_matrix(team1, team2)

    # Generate all possible lead pairs for team1
    for i in range(len(team1)):
        for j in range(i + 1, len(team1)):
            p1a, p1b = team1[i], team1[j]

            # Score against likely opponent leads (first 4 Pokemon as potential leads)
            opponent_leads = team2[:min(4, len(team2))]

            total_advantage = 0
            for oi in range(len(opponent_leads)):
                for oj in range(oi + 1, len(opponent_leads)):
                    # Our lead pair vs their lead pair
                    # Simplified: sum of our matchups
                    adv = (matrix[i][oi] + matrix[i][oj] + matrix[j][oi] + matrix[j][oj]) / 4
                    total_advantage += adv

            avg_advantage = total_advantage / max(1, len(opponent_leads) * (len(opponent_leads) - 1) / 2)

            # Generate reasoning
            if avg_advantage > 15:
                reasoning = "Strong offensive pressure from turn 1"
            elif avg_advantage > 5:
                reasoning = "Solid lead with good coverage"
            elif avg_advantage > -5:
                reasoning = "Flexible lead, can adapt"
            else:
                reasoning = "Defensive lead, may need to switch"

            leads.append(LeadMatchup(
                your_lead1=p1a.name,
                your_lead2=p1b.name,
                their_lead1="Various",
                their_lead2="Various",
                advantage_score=round(avg_advantage, 1),
                reasoning=reasoning,
                recommended=False
            ))

    # Sort by advantage and mark top N as recommended
    leads.sort(key=lambda l: l.advantage_score, reverse=True)
    for i in range(min(top_n, len(leads))):
        leads[i].recommended = True

    return leads[:top_n * 2]  # Return top N recommended + some alternatives


def analyze_speed_tiers(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild]
) -> dict:
    """
    Compare speed tiers between two teams.
    """
    speed_comparison = {}

    for p1 in team1:
        p1_stats = calculate_all_stats(p1)
        p1_speed = p1_stats["speed"]

        outspeeds = []
        ties = []
        underspeeds = []

        for p2 in team2:
            p2_stats = calculate_all_stats(p2)
            p2_speed = p2_stats["speed"]

            if p1_speed > p2_speed:
                outspeeds.append(f"{p2.name} ({p2_speed})")
            elif p1_speed == p2_speed:
                ties.append(f"{p2.name} ({p2_speed})")
            else:
                underspeeds.append(f"{p2.name} ({p2_speed})")

        speed_comparison[p1.name] = {
            "speed": p1_speed,
            "outspeeds": outspeeds,
            "ties": ties,
            "underspeeds": underspeeds
        }

    return speed_comparison


def generate_game_plan(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild],
    overall_advantage: float,
    threats: list[ThreatInfo],
    leads: list[LeadMatchup]
) -> str:
    """
    Generate a text game plan based on the analysis.
    """
    lines = []

    # Overall assessment
    if overall_advantage >= 60:
        lines.append("FAVORABLE MATCHUP - Play aggressively")
    elif overall_advantage >= 55:
        lines.append("SLIGHT ADVANTAGE - Standard game plan should work")
    elif overall_advantage >= 45:
        lines.append("EVEN MATCHUP - Execution and reads will decide this")
    elif overall_advantage >= 40:
        lines.append("SLIGHT DISADVANTAGE - Need to outplay")
    else:
        lines.append("UNFAVORABLE MATCHUP - Look for opponent mistakes")

    # Lead recommendation
    if leads and leads[0].recommended:
        lines.append(f"\nRECOMMENDED LEAD: {leads[0].your_lead1} + {leads[0].your_lead2}")
        lines.append(f"  - {leads[0].reasoning}")

    # Key threats to address
    high_threats = [t for t in threats if t.danger_level == "HIGH"]
    if high_threats:
        lines.append(f"\nPRIORITY TARGETS:")
        for t in high_threats[:2]:
            lines.append(f"  - KO {t.pokemon_name} with {t.your_best_answer} ({t.answer_damage})")

    # Pokemon to preserve
    lines.append(f"\nKEEP ALIVE: Your answers to their biggest threats")

    return "\n".join(lines)


def full_team_matchup_analysis(
    team1: list[PokemonBuild],
    team2: list[PokemonBuild],
    team1_name: str = "Your Team",
    team2_name: str = "Opponent Team"
) -> TeamMatchupResult:
    """
    Perform full matchup analysis between two teams.

    Returns comprehensive TeamMatchupResult with all analysis.
    """
    # Build matchup matrix
    matrix, detailed = build_matchup_matrix(team1, team2)

    # Calculate overall advantage
    overall = calculate_team_advantage(team1, team2)

    # Analyze threats
    threats = analyze_key_threats(team1, team2)

    # Analyze leads
    leads = analyze_lead_matchups(team1, team2)

    # Speed comparison
    speed_data = analyze_speed_tiers(team1, team2)

    # Identify key Pokemon on your team (those with best matchups)
    your_key = []
    for i, p1 in enumerate(team1):
        avg_matchup = sum(matrix[i]) / len(matrix[i])
        if avg_matchup > 5:
            your_key.append(p1.name)

    # Generate game plan
    game_plan = generate_game_plan(team1, team2, overall, threats, leads)

    return TeamMatchupResult(
        your_team_name=team1_name,
        opponent_team_name=team2_name,
        overall_advantage=round(overall, 1),
        matchup_matrix=matrix,
        your_pokemon_names=[p.name for p in team1],
        opponent_pokemon_names=[p.name for p in team2],
        key_threats=threats,
        your_key_pokemon=your_key,
        recommended_leads=leads,
        speed_advantages=speed_data,
        game_plan=game_plan,
        detailed_matchups=detailed
    )
