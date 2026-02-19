"""Team vs team matchup analysis with scoring algorithm and game plan generation."""

from dataclasses import dataclass, field
from typing import Optional

from ..models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread, IVSpread
from ..models.move import Move, MoveCategory
from ..models.team import Team
from .damage import calculate_damage, DamageResult
from .stats import calculate_all_stats
from .modifiers import DamageModifiers, get_type_effectiveness
from .priority import (
    get_move_priority, determine_turn_order, check_prankster_immunity,
    FAKE_OUT_POKEMON, PRANKSTER_POKEMON, PRIORITY_MOVES, normalize_move_name,
    TurnOrderResult,
)
from .abilities import (
    WEATHER_SETTERS, INTIMIDATE_POKEMON,
    INTIMIDATE_BLOCKERS, INTIMIDATE_PUNISHERS,
    TERRAIN_SETTERS,
)

# ============================================================================
# VGC BATTLE MECHANIC CONSTANTS
# ============================================================================

# Abilities that block Fake Out flinch
FLINCH_IMMUNE_ABILITIES = {"inner-focus", "shield-dust", "own-tempo"}

# Items that block Fake Out flinch (secondary effect)
FLINCH_IMMUNE_ITEMS = {"covert-cloak"}

# Redirect moves
REDIRECT_MOVES = {"follow-me", "rage-powder"}

# Powder moves (blocked by Grass type, Overcoat, Safety Goggles)
POWDER_MOVES = {"spore", "sleep-powder", "stun-spore", "poison-powder", "rage-powder"}

# Spread moves (blocked by Wide Guard)
SPREAD_MOVES = {
    "heat-wave", "rock-slide", "earthquake", "blizzard", "muddy-water",
    "dazzling-gleam", "icy-wind", "snarl", "breaking-swipe", "electroweb",
    "lava-plume", "discharge", "surf", "brutal-swing", "hyper-voice",
    "make-it-rain", "bleakwind-storm", "wildbolt-storm", "sandsear-storm",
    "glaciate", "land-s-wrath",
}

# Abilities that bypass defender abilities (relevant for prediction notes)
MOLD_BREAKER_ABILITIES_SET = {"mold-breaker", "teravolt", "turboblaze"}


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


# ============================================================================
# PRIORITY-AWARE GAME PLAN GENERATION
# ============================================================================


@dataclass
class PokemonProfile:
    """Competitive profile of a Pokemon for game plan analysis."""
    name: str
    build: PokemonBuild
    moves: list[Move]
    ability: str
    speed_stat: int
    has_fake_out: bool
    has_protect: bool
    is_prankster: bool
    prankster_moves: list[str]  # Status moves that get +1 priority from Prankster
    is_intimidate: bool
    priority_moves: list[dict]  # [{name, priority, is_status}]
    is_trick_room_setter: bool
    is_tailwind_setter: bool
    is_weather_setter: bool
    weather_type: Optional[str]
    role: str  # "sweeper", "support", "tank", "speed_control"
    # VGC interaction awareness fields
    is_ghost_type: bool = False       # Immune to Fake Out (Normal move)
    is_dark_type: bool = False        # Immune to Prankster-boosted status moves
    is_flinch_immune: bool = False    # Inner Focus / Shield Dust / Covert Cloak
    intimidate_reaction: str = "normal"  # "blocked", "punished", "normal"
    has_follow_me: bool = False       # Follow Me / Rage Powder redirect
    has_quick_guard: bool = False     # Blocks priority moves for a turn
    has_wide_guard: bool = False      # Blocks spread moves for a turn
    is_grounded: bool = True          # For Psychic Terrain priority blocking
    is_terrain_setter: bool = False
    terrain_type: Optional[str] = None
    is_mold_breaker: bool = False     # Bypasses defender abilities
    has_safety_goggles: bool = False   # Blocks powder moves + Rage Powder redirect


@dataclass
class GamePlanLeadRec:
    """A recommended lead pair against a specific opponent."""
    pokemon_1: str
    pokemon_2: str
    score: float
    reasoning: list[str]
    fake_out_note: Optional[str] = None
    prankster_note: Optional[str] = None


@dataclass
class Turn1Action:
    """A single action in the turn 1 priority order."""
    pokemon: str
    move: str
    priority: int
    speed: int
    side: str  # "yours" or "theirs"
    note: str  # e.g. "Prankster boost", "Fake Out flinch"


@dataclass
class GamePlanThreat:
    """Opponent Pokemon ranked by threat level."""
    pokemon_name: str
    threat_level: str  # "CRITICAL", "HIGH", "MEDIUM", "LOW"
    reason: str
    your_answers: list[str]
    is_priority_threat: bool  # Has priority moves that threaten you


@dataclass
class BringRec:
    """Which 4 Pokemon to bring."""
    bring: list[str]
    leave_behind: list[str]
    reasoning: list[str]


@dataclass
class FullGamePlan:
    """Complete game plan output."""
    your_team: list[str]
    opponent_team: list[str]
    overall_matchup: str  # "Favorable", "Even", "Unfavorable"
    overall_score: float
    lead_recommendations: list[GamePlanLeadRec]
    turn_1_priority_order: list[Turn1Action]
    threat_assessment: list[GamePlanThreat]
    win_condition: str
    win_condition_detail: list[str]
    speed_control_notes: list[str]
    bring_recommendation: BringRec
    markdown_summary: str


def build_pokemon_profile(
    build: PokemonBuild,
    moves: list[Move],
    ability_name: str,
    item_name: str = "",
) -> PokemonProfile:
    """Build a competitive profile for a Pokemon, integrating priority data.

    Correctly identifies Fake Out (as a move, not ability), Prankster status
    moves, Intimidate, speed control setters, priority moves, and VGC
    interaction-aware fields (Ghost/Dark type, flinch immunity, Intimidate
    reaction, redirect/guard moves, terrain, grounded status).
    """
    name_normalized = build.name.lower().replace(" ", "-")
    ability_normalized = ability_name.lower().replace(" ", "-") if ability_name else ""
    item_normalized = item_name.lower().replace(" ", "-") if item_name else ""

    stats = calculate_all_stats(build)
    speed_stat = stats["speed"]

    # Normalize types for consistent checking
    types_lower = [t.lower() for t in build.types]

    # Check moves for Fake Out and Protect
    move_names_normalized = [normalize_move_name(m.name) for m in moves]
    has_fake_out = "fake-out" in move_names_normalized
    # Secondary: if no moves known, check FAKE_OUT_POKEMON list
    if not moves and name_normalized in FAKE_OUT_POKEMON:
        has_fake_out = True

    has_protect = any(
        normalize_move_name(m.name) in ("protect", "detect", "silk-trap", "kings-shield",
                                         "spiky-shield", "baneful-bunker", "burning-bulwark", "obstruct")
        for m in moves
    )

    # Prankster analysis
    is_prankster = ability_normalized == "prankster"
    prankster_moves = []
    if is_prankster:
        for m in moves:
            if m.category == MoveCategory.STATUS:
                prankster_moves.append(m.name)

    # Intimidate
    is_intimidate = ability_normalized == "intimidate"

    # Priority moves
    priority_moves = []
    for m in moves:
        mn = normalize_move_name(m.name)
        is_status = m.category == MoveCategory.STATUS
        prio = get_move_priority(mn, ability_normalized, is_status=is_status)
        if prio != 0:
            priority_moves.append({
                "name": m.name,
                "priority": prio,
                "is_status": is_status,
            })

    # Speed control
    is_trick_room_setter = "trick-room" in move_names_normalized
    is_tailwind_setter = "tailwind" in move_names_normalized

    # Weather
    is_weather_setter = ability_normalized in WEATHER_SETTERS
    weather_type = WEATHER_SETTERS.get(ability_normalized)

    # --- VGC interaction awareness ---

    # Type-based immunities
    is_ghost_type = "ghost" in types_lower
    is_dark_type = "dark" in types_lower

    # Flinch immunity (Inner Focus, Shield Dust, Own Tempo, or Covert Cloak)
    is_flinch_immune = (
        ability_normalized in FLINCH_IMMUNE_ABILITIES
        or item_normalized in FLINCH_IMMUNE_ITEMS
    )

    # Intimidate reaction
    if ability_normalized in [a.lower() for a in INTIMIDATE_PUNISHERS]:
        intimidate_reaction = "punished"
    elif ability_normalized in [a.lower() for a in INTIMIDATE_BLOCKERS]:
        intimidate_reaction = "blocked"
    else:
        intimidate_reaction = "normal"

    # Redirect and guard moves
    has_follow_me = any(
        normalize_move_name(m.name) in REDIRECT_MOVES for m in moves
    )
    has_quick_guard = "quick-guard" in move_names_normalized
    has_wide_guard = "wide-guard" in move_names_normalized

    # Grounded status (for Psychic Terrain priority blocking)
    # Not grounded if: Flying type, Levitate ability, or Air Balloon item
    is_grounded = (
        "flying" not in types_lower
        and ability_normalized != "levitate"
        and item_normalized != "air-balloon"
    )

    # Terrain setter
    is_terrain_setter = ability_normalized in TERRAIN_SETTERS
    terrain_type = TERRAIN_SETTERS.get(ability_normalized)

    # Mold Breaker (bypasses defender abilities)
    is_mold_breaker = ability_normalized in MOLD_BREAKER_ABILITIES_SET

    # Safety Goggles (blocks powder moves and Rage Powder redirect)
    has_safety_goggles = item_normalized == "safety-goggles"

    # Role classification
    atk = max(build.base_stats.attack, build.base_stats.special_attack)
    bulk = build.base_stats.hp + build.base_stats.defense + build.base_stats.special_defense
    has_support_moves = any(m.category == MoveCategory.STATUS for m in moves)

    if is_trick_room_setter or is_tailwind_setter:
        role = "speed_control"
    elif is_intimidate or (has_support_moves and atk < 90):
        role = "support"
    elif bulk > 300 and atk < 100:
        role = "tank"
    else:
        role = "sweeper"

    return PokemonProfile(
        name=build.name,
        build=build,
        moves=moves,
        ability=ability_name or "",
        speed_stat=speed_stat,
        has_fake_out=has_fake_out,
        has_protect=has_protect,
        is_prankster=is_prankster,
        prankster_moves=prankster_moves,
        is_intimidate=is_intimidate,
        priority_moves=priority_moves,
        is_trick_room_setter=is_trick_room_setter,
        is_tailwind_setter=is_tailwind_setter,
        is_weather_setter=is_weather_setter,
        weather_type=weather_type,
        role=role,
        is_ghost_type=is_ghost_type,
        is_dark_type=is_dark_type,
        is_flinch_immune=is_flinch_immune,
        intimidate_reaction=intimidate_reaction,
        has_follow_me=has_follow_me,
        has_quick_guard=has_quick_guard,
        has_wide_guard=has_wide_guard,
        is_grounded=is_grounded,
        is_terrain_setter=is_terrain_setter,
        terrain_type=terrain_type,
        is_mold_breaker=is_mold_breaker,
        has_safety_goggles=has_safety_goggles,
    )


def _analyze_fake_out_war(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
) -> list[str]:
    """Analyze Fake Out speed interactions between both teams.

    Accounts for Ghost-type immunity, flinch-immune abilities/items,
    Quick Guard as a counter, and Psychic Terrain blocking.
    """
    notes = []
    your_fo = [p for p in your_profiles if p.has_fake_out]
    their_fo = [p for p in their_profiles if p.has_fake_out]

    if not your_fo and not their_fo:
        return []

    # Note Ghost-type Pokemon immune to Fake Out on each side
    your_ghosts = [p for p in your_profiles if p.is_ghost_type]
    their_ghosts = [p for p in their_profiles if p.is_ghost_type]

    if your_ghosts and their_fo:
        ghost_names = ", ".join(p.name for p in your_ghosts)
        notes.append(f"Your {ghost_names} is Ghost-type - immune to opponent's Fake Out")
    if their_ghosts and your_fo:
        ghost_names = ", ".join(p.name for p in their_ghosts)
        notes.append(f"Their {ghost_names} is Ghost-type - immune to your Fake Out")

    # Note flinch-immune Pokemon
    your_flinch_immune = [p for p in your_profiles if p.is_flinch_immune and not p.is_ghost_type]
    their_flinch_immune = [p for p in their_profiles if p.is_flinch_immune and not p.is_ghost_type]

    if your_flinch_immune and their_fo:
        for p in your_flinch_immune:
            reason = "Covert Cloak" if p.has_safety_goggles is False and p.ability.lower().replace(" ", "-") not in FLINCH_IMMUNE_ABILITIES else p.ability
            notes.append(f"Your {p.name} resists Fake Out flinch ({reason})")
    if their_flinch_immune and your_fo:
        for p in their_flinch_immune:
            notes.append(f"Their {p.name} resists Fake Out flinch (ability/item)")

    # Note Quick Guard users as Fake Out counters
    your_qg = [p for p in your_profiles if p.has_quick_guard]
    their_qg = [p for p in their_profiles if p.has_quick_guard]
    if your_qg and their_fo:
        qg_names = ", ".join(p.name for p in your_qg)
        notes.append(f"Your {qg_names} has Quick Guard - can block opponent's Fake Out")
    if their_qg and your_fo:
        qg_names = ", ".join(p.name for p in their_qg)
        notes.append(f"Their {qg_names} has Quick Guard - can block your Fake Out")

    # Note Psychic Terrain blocking
    your_psychic_terrain = any(
        p.is_terrain_setter and p.terrain_type == "psychic" for p in your_profiles
    )
    their_psychic_terrain = any(
        p.is_terrain_setter and p.terrain_type == "psychic" for p in their_profiles
    )
    if your_psychic_terrain and their_fo:
        notes.append("Your Psychic Terrain blocks opponent's Fake Out on grounded allies")
    if their_psychic_terrain and your_fo:
        notes.append("Their Psychic Terrain blocks your Fake Out on grounded targets")

    # Speed comparison
    if your_fo and not their_fo:
        fastest = max(your_fo, key=lambda p: p.speed_stat)
        notes.append(f"You have Fake Out ({fastest.name}, speed {fastest.speed_stat}) - opponent has none")
        return notes

    if their_fo and not your_fo:
        fastest = max(their_fo, key=lambda p: p.speed_stat)
        notes.append(f"Opponent has Fake Out ({fastest.name}, speed {fastest.speed_stat}) - you have none")
        return notes

    # Both sides have Fake Out
    for yp in your_fo:
        for tp in their_fo:
            if yp.speed_stat > tp.speed_stat:
                notes.append(
                    f"Your {yp.name} Fake Outs FIRST vs their {tp.name} "
                    f"(speed {yp.speed_stat} > {tp.speed_stat})"
                )
            elif tp.speed_stat > yp.speed_stat:
                notes.append(
                    f"Their {tp.name} Fake Outs FIRST vs your {yp.name} "
                    f"(speed {tp.speed_stat} > {yp.speed_stat})"
                )
            else:
                notes.append(
                    f"Fake Out SPEED TIE: {yp.name} vs {tp.name} (both {yp.speed_stat}) - 50/50"
                )
    return notes


def _analyze_prankster_interactions(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
) -> list[str]:
    """Analyze Prankster move interactions including Dark-type immunity."""
    notes = []

    # Check their Prankster users
    for tp in their_profiles:
        if not tp.is_prankster:
            continue
        for move_name in tp.prankster_moves:
            prio = get_move_priority(
                normalize_move_name(move_name), "prankster", is_status=True
            )
            notes.append(
                f"Their {tp.name} has Prankster {move_name} (priority +{prio}) - "
                f"goes before normal-priority moves regardless of speed"
            )
            # Check if any of your Pokemon are Dark type (immune)
            for yp in your_profiles:
                if "Dark" in yp.build.types or "dark" in yp.build.types:
                    notes.append(
                        f"  -> Your {yp.name} (Dark type) is IMMUNE to Prankster {move_name}"
                    )

    # Check your Prankster users
    for yp in your_profiles:
        if not yp.is_prankster:
            continue
        for move_name in yp.prankster_moves:
            prio = get_move_priority(
                normalize_move_name(move_name), "prankster", is_status=True
            )
            notes.append(
                f"Your {yp.name} has Prankster {move_name} (priority +{prio}) - "
                f"goes before normal-priority moves regardless of speed"
            )
            # Check if any opponent Pokemon are Dark type (immune)
            for tp in their_profiles:
                if "Dark" in tp.build.types or "dark" in tp.build.types:
                    notes.append(
                        f"  -> Their {tp.name} (Dark type) is IMMUNE to your Prankster {move_name}"
                    )

    return notes


def _score_lead_pair(
    pair: tuple[PokemonProfile, PokemonProfile],
    their_profiles: list[PokemonProfile],
    matrix: list[list[float]],
    your_profiles: list[PokemonProfile],
) -> GamePlanLeadRec:
    """Score a lead pair against the opponent team, considering priority interactions.

    Accounts for VGC mechanics:
    - Fake Out vs Ghost types (immune - Normal move), flinch-immune abilities/items
    - Prankster vs Dark types (immune to Prankster-boosted status moves)
    - Intimidate vs blockers (Clear Body, Inner Focus) and punishers (Defiant, Competitive)
    - Follow Me / Rage Powder redirect support
    - Quick Guard as Fake Out / priority counter
    - Psychic Terrain blocking priority on grounded targets
    - Wide Guard vs spread-heavy teams
    """
    p1, p2 = pair
    reasoning = []
    score = 50.0  # Base score

    # Find indices in your_profiles
    idx1 = next(i for i, p in enumerate(your_profiles) if p.name == p1.name)
    idx2 = next(i for i, p in enumerate(your_profiles) if p.name == p2.name)

    # Predict opponent's likely leads for interaction checks
    predicted_opp_leads = _predict_opponent_leads(their_profiles)

    # --- Matchup matrix score (biggest factor) ---
    avg_adv = 0
    for j in range(len(their_profiles)):
        avg_adv += (matrix[idx1][j] + matrix[idx2][j]) / 2
    avg_adv /= max(len(their_profiles), 1)
    score += avg_adv * 0.4
    if avg_adv > 10:
        reasoning.append("Strong type/damage matchup advantage")
    elif avg_adv < -10:
        reasoning.append("Unfavorable type matchup")

    # --- Fake Out bonus (with Ghost/flinch immunity awareness) ---
    fake_out_note = None
    fo_users = [p for p in (p1, p2) if p.has_fake_out]
    their_fo = [p for p in their_profiles if p.has_fake_out]

    if fo_users:
        fastest_ours = max(fo_users, key=lambda p: p.speed_stat)

        # Check how many predicted opponent leads are valid Fake Out targets
        ghost_leads = [p for p in predicted_opp_leads if p.is_ghost_type]
        flinch_immune_leads = [
            p for p in predicted_opp_leads
            if p.is_flinch_immune and not p.is_ghost_type
        ]
        valid_targets = [
            p for p in predicted_opp_leads
            if not p.is_ghost_type and not p.is_flinch_immune
        ]

        # Check if opponent has Quick Guard (blocks Fake Out entirely)
        opp_quick_guard = [p for p in predicted_opp_leads if p.has_quick_guard]

        # Check if opponent has Psychic Terrain setter (blocks priority on grounded)
        opp_psychic_terrain = any(
            p.is_terrain_setter and p.terrain_type == "psychic"
            for p in their_profiles
        )

        if ghost_leads and not valid_targets:
            # All predicted leads are Ghost - Fake Out is useless
            fake_out_note = (
                f"Your {fastest_ours.name} has Fake Out but opponent leads are "
                f"Ghost type ({', '.join(p.name for p in ghost_leads)}) - IMMUNE"
            )
            reasoning.append("Fake Out blocked by Ghost-type leads")
        elif opp_psychic_terrain and all(p.is_grounded for p in predicted_opp_leads):
            fake_out_note = (
                f"Opponent has Psychic Terrain - blocks Fake Out on grounded targets"
            )
            reasoning.append("Psychic Terrain blocks Fake Out")
        elif opp_quick_guard:
            score += 5  # Reduced from 15 - Quick Guard threatens to block it
            fake_out_note = (
                f"Your {fastest_ours.name} has Fake Out but their "
                f"{opp_quick_guard[0].name} has Quick Guard (blocks priority moves)"
            )
            reasoning.append("Fake Out contested by Quick Guard")
        elif their_fo:
            fastest_theirs = max(their_fo, key=lambda p: p.speed_stat)
            if fastest_ours.speed_stat > fastest_theirs.speed_stat:
                score += 15
                fake_out_note = (
                    f"Your {fastest_ours.name} Fake Outs FIRST "
                    f"(speed {fastest_ours.speed_stat} > {fastest_theirs.speed_stat})"
                )
                reasoning.append("Faster Fake Out pressure")
            else:
                score += 5
                fake_out_note = (
                    f"Their {fastest_theirs.name} Fake Outs first "
                    f"(speed {fastest_theirs.speed_stat} > {fastest_ours.speed_stat})"
                )
        else:
            # Unopposed Fake Out - but check for immunity
            if flinch_immune_leads:
                score += 8  # Reduced from 15 - some targets resist flinch
                immune_names = ", ".join(p.name for p in flinch_immune_leads)
                fake_out_note = (
                    f"Fake Out from {fastest_ours.name} (but {immune_names} "
                    f"resists flinch via ability/item)"
                )
                reasoning.append("Fake Out partially effective (flinch immunity)")
            else:
                score += 15
                fake_out_note = f"Fake Out from {fastest_ours.name} (opponent has none)"
                reasoning.append("Unopposed Fake Out")

        # Note Ghost-type immunity if some leads are Ghost
        if ghost_leads and valid_targets:
            ghost_names = ", ".join(p.name for p in ghost_leads)
            fake_out_note = (fake_out_note or "") + (
                f" (Note: {ghost_names} is Ghost-type, immune to Fake Out)"
            )

    # --- Prankster Tailwind/Taunt bonus (with Dark-type awareness) ---
    prankster_note = None
    # Check if opponent's predicted leads include Dark types (immune to Prankster status)
    opp_dark_leads = [p for p in predicted_opp_leads if p.is_dark_type]

    for p in (p1, p2):
        if p.is_prankster and p.is_tailwind_setter:
            # Tailwind targets your own side, not the opponent - Dark type doesn't block it
            score += 10
            prankster_note = (
                f"{p.name} Prankster Tailwind is priority +1 - "
                f"goes before opponent's non-Prankster moves"
            )
            reasoning.append(f"Prankster Tailwind from {p.name}")
            break
        if p.is_prankster and any("taunt" in m.lower() for m in p.prankster_moves):
            # Taunt TARGETS opponents - Dark types are immune
            if opp_dark_leads:
                dark_names = ", ".join(dp.name for dp in opp_dark_leads)
                # Taunt still works on non-Dark leads
                non_dark_leads = [lp for lp in predicted_opp_leads if not lp.is_dark_type]
                if non_dark_leads:
                    score += 4  # Reduced from 8 - partially effective
                    prankster_note = (
                        f"{p.name} Prankster Taunt (+1 priority) but {dark_names} "
                        f"is Dark-type (immune to Prankster moves)"
                    )
                    reasoning.append(f"Prankster Taunt from {p.name} (partially blocked by Dark type)")
                else:
                    # All opponent leads are Dark - Prankster Taunt useless
                    prankster_note = (
                        f"{p.name} has Prankster Taunt but ALL opponent leads are "
                        f"Dark-type ({dark_names}) - IMMUNE"
                    )
                    reasoning.append("Prankster Taunt blocked by Dark-type leads")
            else:
                score += 8
                prankster_note = (
                    f"{p.name} Prankster Taunt is priority +1 - "
                    f"shuts down opponent's setup before they move"
                )
                reasoning.append(f"Prankster Taunt from {p.name}")
            break

    # --- Intimidate vs physical attackers (with blocker/punisher awareness) ---
    intimidate_users = [p for p in (p1, p2) if p.is_intimidate]
    if intimidate_users:
        # Check for Intimidate punishers on opponent team (Defiant, Competitive)
        punishers = [tp for tp in their_profiles if tp.intimidate_reaction == "punished"]
        blockers = [tp for tp in their_profiles if tp.intimidate_reaction == "blocked"]

        if punishers:
            # Intimidate is DANGEROUS here - Defiant/Competitive gets +2
            punisher_names = ", ".join(p.name for p in punishers)
            score -= 8
            reasoning.append(
                f"WARNING: Intimidate from {intimidate_users[0].name} triggers "
                f"{punisher_names}'s counter-ability (+2 stat boost)"
            )
        else:
            # Count effective physical threats (excluding blocked)
            physical_threats = sum(
                1 for tp in their_profiles
                if tp.build.base_stats.attack > tp.build.base_stats.special_attack
                and tp.intimidate_reaction != "blocked"
            )
            blocked_count = sum(
                1 for tp in their_profiles
                if tp.build.base_stats.attack > tp.build.base_stats.special_attack
                and tp.intimidate_reaction == "blocked"
            )

            if physical_threats >= 3:
                score += 8
                reasoning.append(f"Intimidate from {intimidate_users[0].name} vs physical-heavy team")
            elif physical_threats >= 1:
                score += 4
                reasoning.append(f"Intimidate from {intimidate_users[0].name}")

            if blockers:
                blocked_names = ", ".join(p.name for p in blockers)
                reasoning.append(f"Note: {blocked_names} blocks Intimidate")

    # --- Dark type blocking their Prankster ---
    their_prankster = [p for p in their_profiles if p.is_prankster]
    if their_prankster:
        for p in (p1, p2):
            if p.is_dark_type:
                score += 5
                reasoning.append(
                    f"{p.name} (Dark type) blocks their Prankster {their_prankster[0].name}"
                )
                break

    # --- Follow Me / Rage Powder redirect support ---
    redirect_user = None
    for p in (p1, p2):
        if p.has_follow_me:
            redirect_user = p
            break

    if redirect_user:
        partner = p2 if redirect_user == p1 else p1
        # Redirect is valuable when partner needs protection for setup
        if partner.is_trick_room_setter:
            score += 10
            reasoning.append(
                f"{redirect_user.name} redirects attacks while {partner.name} sets Trick Room"
            )
        elif partner.is_tailwind_setter:
            score += 6
            reasoning.append(
                f"{redirect_user.name} redirects attacks while {partner.name} sets Tailwind"
            )
        else:
            score += 4
            reasoning.append(f"{redirect_user.name} provides redirect support")

        # Check if opponent has Safety Goggles (bypasses Rage Powder)
        if any(normalize_move_name(m.name) == "rage-powder" for m in redirect_user.moves):
            goggles_users = [tp for tp in their_profiles if tp.has_safety_goggles]
            if goggles_users:
                goggles_names = ", ".join(p.name for p in goggles_users)
                reasoning.append(
                    f"Note: {goggles_names} has Safety Goggles (ignores Rage Powder)"
                )

    # --- Psychic Terrain blocking opponent priority ---
    for p in (p1, p2):
        if p.is_terrain_setter and p.terrain_type == "psychic":
            partner = p2 if p == p1 else p1
            # Check if opponent has priority threats
            opp_priority_users = [
                tp for tp in their_profiles
                if any(pm["priority"] > 0 and not pm["is_status"] for pm in tp.priority_moves)
            ]
            if opp_priority_users:
                prio_names = ", ".join(tp.name for tp in opp_priority_users)
                score += 8
                reasoning.append(
                    f"{p.name} sets Psychic Terrain - blocks {prio_names}'s "
                    f"priority moves on grounded allies"
                )
            elif their_fo:
                score += 6
                fo_names = ", ".join(tp.name for tp in their_fo)
                reasoning.append(
                    f"{p.name} sets Psychic Terrain - blocks {fo_names}'s Fake Out"
                )
            break

    # --- Wide Guard vs spread-heavy teams ---
    wide_guard_user = None
    for p in (p1, p2):
        if p.has_wide_guard:
            wide_guard_user = p
            break
    if wide_guard_user:
        # Count opponent spread moves
        opp_spread_moves = 0
        for tp in their_profiles:
            for m in tp.moves:
                if normalize_move_name(m.name) in SPREAD_MOVES:
                    opp_spread_moves += 1
        if opp_spread_moves >= 3:
            score += 6
            reasoning.append(
                f"{wide_guard_user.name} has Wide Guard vs spread-move-heavy team"
            )
        elif opp_spread_moves >= 1:
            score += 3
            reasoning.append(f"{wide_guard_user.name} has Wide Guard option")

    # --- Speed control matching ---
    has_tr = p1.is_trick_room_setter or p2.is_trick_room_setter
    has_tw = p1.is_tailwind_setter or p2.is_tailwind_setter
    their_tr = any(tp.is_trick_room_setter for tp in their_profiles)
    their_tw = any(tp.is_tailwind_setter for tp in their_profiles)

    if has_tw and not their_tw:
        score += 5
        reasoning.append("Tailwind advantage (they have none)")
    if has_tr and not their_tr:
        score += 5
        reasoning.append("Trick Room option (they can't match)")

    # --- Penalties ---
    types_1 = set(p1.build.types)
    types_2 = set(p2.build.types)
    if types_1 & types_2:
        score -= 5
        reasoning.append("Shared typing - vulnerable to same coverage")

    if p1.speed_stat < 80 and p2.speed_stat < 80 and not has_tr:
        score -= 8
        reasoning.append("Both leads are slow without Trick Room")

    return GamePlanLeadRec(
        pokemon_1=p1.name,
        pokemon_2=p2.name,
        score=round(score, 1),
        reasoning=reasoning,
        fake_out_note=fake_out_note,
        prankster_note=prankster_note,
    )


def _recommend_leads(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
    matrix: list[list[float]],
    top_n: int = 3,
) -> list[GamePlanLeadRec]:
    """Score all possible lead pairs and return top N."""
    pairs = []
    for i in range(len(your_profiles)):
        for j in range(i + 1, len(your_profiles)):
            pairs.append((your_profiles[i], your_profiles[j]))

    scored = [
        _score_lead_pair(pair, their_profiles, matrix, your_profiles)
        for pair in pairs
    ]
    scored.sort(key=lambda r: r.score, reverse=True)
    return scored[:top_n]


def _predict_opponent_leads(
    their_profiles: list[PokemonProfile],
) -> list[PokemonProfile]:
    """Predict opponent's most likely lead pair using VGC common patterns.

    Scores each Pokemon by lead likelihood: Fake Out users, Prankster support,
    Intimidate, and speed control setters are much more likely to lead than
    pure sweepers.
    """
    scored = []
    for p in their_profiles:
        score = 0.0
        # Fake Out users almost always lead
        if p.has_fake_out:
            score += 30
        # Prankster support leads very often (Tailwind/Taunt turn 1)
        if p.is_prankster and (p.is_tailwind_setter or p.prankster_moves):
            score += 25
        # Intimidate users commonly lead
        if p.is_intimidate:
            score += 15
        # Speed control setters often lead
        if p.is_tailwind_setter and not p.is_prankster:
            score += 10
        if p.is_trick_room_setter:
            score += 10
        # Fast Pokemon are more likely leads than slow ones (minor factor)
        score += p.speed_stat * 0.05
        scored.append((p, score))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [p for p, s in scored[:2]]


def _build_turn_1_priority_order(
    your_lead: GamePlanLeadRec,
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
) -> list[Turn1Action]:
    """Build the turn 1 priority order for the recommended lead vs opponent's likely leads.

    Shows all 4 Pokemon on the field sorted by priority bracket then speed.
    Passes opponent lead context to _best_turn1_move for interaction awareness.
    """
    # Get lead profiles
    lead_names = {your_lead.pokemon_1, your_lead.pokemon_2}
    your_leads = [p for p in your_profiles if p.name in lead_names]

    # Predict opponent's most likely leads using VGC patterns
    their_leads = _predict_opponent_leads(their_profiles)

    actions: list[Turn1Action] = []

    # Build actions for each Pokemon using their most impactful move
    # Pass opponent leads as context for interaction-aware move selection
    for p in your_leads:
        move, prio, note = _best_turn1_move(p, opponent_leads=their_leads)
        actions.append(Turn1Action(
            pokemon=p.name, move=move, priority=prio,
            speed=p.speed_stat, side="yours", note=note,
        ))

    for p in their_leads:
        move, prio, note = _best_turn1_move(p, opponent_leads=your_leads)
        actions.append(Turn1Action(
            pokemon=p.name, move=move, priority=prio,
            speed=p.speed_stat, side="theirs", note=note,
        ))

    # Sort: higher priority first, then faster first within same bracket
    actions.sort(key=lambda a: (-a.priority, -a.speed))
    return actions


def _best_turn1_move(
    profile: PokemonProfile,
    opponent_leads: list[PokemonProfile] = None,
) -> tuple[str, int, str]:
    """Pick the most likely turn 1 move for a Pokemon and return (move, priority, note).

    When opponent_leads are provided, considers:
    - Fake Out vs Ghost-type opponents (Normal move - immune)
    - Fake Out vs flinch-immune opponents (Inner Focus, Covert Cloak)
    - Prankster Taunt vs Dark-type opponents (immune to Prankster status)
    """
    opponent_leads = opponent_leads or []

    # Fake Out is almost always used turn 1 - but check for immunities
    if profile.has_fake_out:
        if opponent_leads:
            all_ghost = all(p.is_ghost_type for p in opponent_leads)
            any_ghost = any(p.is_ghost_type for p in opponent_leads)
            all_flinch_immune = all(
                p.is_ghost_type or p.is_flinch_immune for p in opponent_leads
            )

            if all_ghost:
                # All opponents are Ghost - skip Fake Out entirely
                pass  # Fall through to other moves
            elif all_flinch_immune:
                # All opponents resist flinch - Fake Out is mostly wasted
                note = "Fake Out flinch (turn 1 only) - but all targets resist flinch"
                return "Fake Out", 3, note
            elif any_ghost:
                ghost_names = ", ".join(
                    p.name for p in opponent_leads if p.is_ghost_type
                )
                note = f"Fake Out flinch (turn 1) - target non-Ghost ({ghost_names} immune)"
                return "Fake Out", 3, note
            else:
                return "Fake Out", 3, "Fake Out flinch (turn 1 only)"
        else:
            return "Fake Out", 3, "Fake Out flinch (turn 1 only)"

    # Prankster Tailwind (targets own side - Dark immunity doesn't apply)
    if profile.is_prankster and profile.is_tailwind_setter:
        prio = get_move_priority("tailwind", "prankster", is_status=True)
        return "Tailwind", prio, f"Prankster boost (+{prio} priority)"

    # Prankster Taunt (targets opponent - Dark types immune)
    if profile.is_prankster:
        for m in profile.prankster_moves:
            if "taunt" in m.lower():
                prio = get_move_priority("taunt", "prankster", is_status=True)
                if opponent_leads:
                    all_dark = all(p.is_dark_type for p in opponent_leads)
                    any_dark = any(p.is_dark_type for p in opponent_leads)
                    if all_dark:
                        # All opponents are Dark - Prankster Taunt useless, skip
                        continue
                    elif any_dark:
                        dark_names = ", ".join(
                            p.name for p in opponent_leads if p.is_dark_type
                        )
                        return "Taunt", prio, (
                            f"Prankster boost (+{prio} priority) - "
                            f"target non-Dark ({dark_names} immune)"
                        )
                return "Taunt", prio, f"Prankster boost (+{prio} priority)"

    # Follow Me / Rage Powder (redirect to protect partner)
    if profile.has_follow_me:
        return "Follow Me", 2, "Redirects attacks to protect partner"

    # Tailwind (non-Prankster)
    if profile.is_tailwind_setter:
        return "Tailwind", 0, "Standard priority"

    # Trick Room
    if profile.is_trick_room_setter:
        return "Trick Room", -7, "Negative priority (-7)"

    # Protect is common turn 1
    if profile.has_protect:
        return "Protect", 4, "Scouting / safe turn 1"

    # Default: strongest attacking move
    best_move = None
    best_power = 0
    for m in profile.moves:
        if m.power and m.power > best_power:
            best_power = m.power
            best_move = m
    if best_move:
        mn = normalize_move_name(best_move.name)
        prio = PRIORITY_MOVES.get(mn, 0)
        note = f"Priority +{prio}" if prio > 0 else "Standard priority"
        return best_move.name, prio, note

    return "Attack", 0, "Standard priority"


def _rank_threats(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
    matrix: list[list[float]],
) -> list[GamePlanThreat]:
    """Rank opponent Pokemon by threat level to your team."""
    threats = []
    for j, tp in enumerate(their_profiles):
        # Count how many of your team this Pokemon threatens
        threatened_count = 0
        your_answers = []
        for i, yp in enumerate(your_profiles):
            # Negative net advantage = tp threatens yp
            if matrix[i][j] < -10:
                threatened_count += 1
            # Positive net advantage = yp answers tp
            if matrix[i][j] > 10:
                your_answers.append(yp.name)

        # Check for priority threats
        is_priority_threat = bool(tp.priority_moves) and any(
            pm["priority"] > 0 and not pm["is_status"] for pm in tp.priority_moves
        )

        # Determine threat level
        if threatened_count >= 4:
            level = "CRITICAL"
            reason = f"Threatens {threatened_count}/{len(your_profiles)} of your team"
        elif threatened_count >= 2:
            level = "HIGH"
            reason = f"Threatens {threatened_count}/{len(your_profiles)} of your team"
        elif threatened_count >= 1:
            level = "MEDIUM"
            reason = f"Threatens {threatened_count}/{len(your_profiles)} of your team"
        else:
            level = "LOW"
            reason = "Manageable threat"

        if is_priority_threat:
            prio_names = [pm["name"] for pm in tp.priority_moves if pm["priority"] > 0 and not pm["is_status"]]
            reason += f" + has priority ({', '.join(prio_names)})"

        if tp.is_prankster:
            reason += " + Prankster status moves"

        threats.append(GamePlanThreat(
            pokemon_name=tp.name,
            threat_level=level,
            reason=reason,
            your_answers=your_answers if your_answers else ["No clear answer"],
            is_priority_threat=is_priority_threat,
        ))

    # Sort by threat level
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    threats.sort(key=lambda t: order[t.threat_level])
    return threats


def _determine_win_condition(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
    threats: list[GamePlanThreat],
    overall_score: float,
) -> tuple[str, list[str]]:
    """Determine how you win this matchup."""
    details = []

    your_tw = any(p.is_tailwind_setter for p in your_profiles)
    their_tw = any(p.is_tailwind_setter for p in their_profiles)
    your_tr = any(p.is_trick_room_setter for p in your_profiles)
    their_tr = any(p.is_trick_room_setter for p in their_profiles)
    your_prankster_tw = any(p.is_prankster and p.is_tailwind_setter for p in your_profiles)

    # Fast team with Tailwind
    avg_speed = sum(p.speed_stat for p in your_profiles) / len(your_profiles)
    their_avg_speed = sum(p.speed_stat for p in their_profiles) / len(their_profiles)

    if your_tr and their_avg_speed > avg_speed:
        strategy = "Trick Room reversal"
        details.append("Set up Trick Room to reverse their speed advantage")
        tr_setters = [p.name for p in your_profiles if p.is_trick_room_setter]
        details.append(f"Trick Room setter(s): {', '.join(tr_setters)}")
        if their_tw:
            details.append("Deny their Tailwind by setting TR first or KO their setter")
    elif your_prankster_tw:
        strategy = "Prankster Tailwind offense"
        tw_user = next(p for p in your_profiles if p.is_prankster and p.is_tailwind_setter)
        details.append(f"Set Prankster Tailwind with {tw_user.name} (priority +1 - goes first)")
        details.append("Double into their biggest threat under Tailwind speed")
    elif your_tw and not their_tw:
        strategy = "Tailwind speed control"
        tw_users = [p.name for p in your_profiles if p.is_tailwind_setter]
        details.append(f"Set Tailwind with {tw_users[0]} for speed advantage")
        details.append("Opponent cannot match your speed control")
    elif overall_score >= 60:
        strategy = "Offensive pressure"
        details.append("Strong matchup advantage - apply pressure from turn 1")
    elif overall_score <= 40:
        strategy = "Defensive pivoting"
        details.append("Unfavorable matchup - play cautiously and look for openings")
        if any(p.is_intimidate for p in your_profiles):
            details.append("Use Intimidate cycling to weaken their physical attackers")
    else:
        strategy = "Balanced play"
        details.append("Even matchup - outplay through smart positioning and reads")

    # Key KOs to secure
    critical_threats = [t for t in threats if t.threat_level in ("CRITICAL", "HIGH")]
    for t in critical_threats[:2]:
        answers = t.your_answers[0] if t.your_answers and t.your_answers[0] != "No clear answer" else None
        if answers:
            details.append(f"KO their {t.pokemon_name} with {answers}")

    # Pokemon to preserve
    important_answers = set()
    for t in critical_threats:
        for a in t.your_answers:
            if a != "No clear answer":
                important_answers.add(a)
    if important_answers:
        details.append(f"Preserve: {', '.join(list(important_answers)[:3])}")

    return strategy, details


def _recommend_bring_4(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
    threats: list[GamePlanThreat],
    lead_rec: GamePlanLeadRec,
    matrix: list[list[float]],
) -> BringRec:
    """Recommend which 4 Pokemon to bring (VGC bring-4 format)."""
    if len(your_profiles) <= 4:
        return BringRec(
            bring=[p.name for p in your_profiles],
            leave_behind=[],
            reasoning=["Team has 4 or fewer Pokemon - bring all"],
        )

    lead_names = {lead_rec.pokemon_1, lead_rec.pokemon_2}
    remaining = [p for p in your_profiles if p.name not in lead_names]

    # Score remaining Pokemon for back slot value
    back_scores: list[tuple[PokemonProfile, float, list[str]]] = []
    for p in remaining:
        score = 0.0
        reasons = []
        idx = next(i for i, yp in enumerate(your_profiles) if yp.name == p.name)

        # Does it answer critical/high threats?
        for t in threats:
            if t.threat_level in ("CRITICAL", "HIGH") and p.name in t.your_answers:
                score += 20
                reasons.append(f"Answers {t.pokemon_name} ({t.threat_level})")

        # Speed control value
        if p.is_trick_room_setter or p.is_tailwind_setter:
            score += 10
            reasons.append("Provides speed control")

        # Overall matchup advantage
        avg_adv = sum(matrix[idx]) / len(matrix[idx]) if matrix[idx] else 0
        score += avg_adv * 0.3
        if avg_adv > 5:
            reasons.append("Good overall matchup spread")

        # Priority moves for cleanup
        if p.priority_moves:
            score += 5
            reasons.append("Has priority moves for late-game cleanup")

        if not reasons:
            reasons.append("Limited value in this matchup")

        back_scores.append((p, score, reasons))

    back_scores.sort(key=lambda x: x[1], reverse=True)

    bring = list(lead_names)
    leave = []
    bring_reasons = [f"{lead_rec.pokemon_1} + {lead_rec.pokemon_2}: recommended lead pair"]

    for p, sc, reasons in back_scores[:2]:
        bring.append(p.name)
        bring_reasons.append(f"{p.name}: {reasons[0]}")

    for p, sc, reasons in back_scores[2:]:
        leave.append(p.name)
        bring_reasons.append(f"Leave {p.name}: {reasons[0] if reasons else 'lower value'}")

    return BringRec(bring=bring, leave_behind=leave, reasoning=bring_reasons)


def _analyze_terrain_interactions(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
) -> list[str]:
    """Analyze terrain-related interactions between both teams.

    Covers:
    - Psychic Terrain blocking priority moves on grounded targets
    - Electric Terrain preventing sleep (blocks Spore)
    - Grassy Terrain enabling Grassy Glide (+1 priority)
    - Misty Terrain halving Dragon damage and preventing status
    """
    notes = []

    your_terrain = [(p, p.terrain_type) for p in your_profiles if p.is_terrain_setter]
    their_terrain = [(p, p.terrain_type) for p in their_profiles if p.is_terrain_setter]

    # Your terrain effects
    for setter, terrain in your_terrain:
        if terrain == "psychic":
            opp_priority = [
                tp for tp in their_profiles
                if any(pm["priority"] > 0 and not pm["is_status"] for pm in tp.priority_moves)
            ]
            opp_fo = [tp for tp in their_profiles if tp.has_fake_out]
            if opp_priority or opp_fo:
                blockers = set()
                for tp in opp_priority:
                    blockers.add(tp.name)
                for tp in opp_fo:
                    blockers.add(tp.name)
                notes.append(
                    f"Your {setter.name} (Psychic Terrain) blocks priority from "
                    f"{', '.join(blockers)} on grounded allies"
                )
        elif terrain == "electric":
            opp_sleep = [
                tp for tp in their_profiles
                if any(normalize_move_name(m.name) in ("spore", "sleep-powder", "yawn", "dark-void", "hypnosis", "sing", "grass-whistle", "lovely-kiss")
                       for m in tp.moves)
            ]
            if opp_sleep:
                sleep_names = ", ".join(tp.name for tp in opp_sleep)
                notes.append(
                    f"Your {setter.name} (Electric Terrain) prevents sleep - "
                    f"blocks {sleep_names}'s sleep moves on grounded targets"
                )
        elif terrain == "grassy":
            your_glide = [
                p for p in your_profiles
                if any(normalize_move_name(m.name) == "grassy-glide" for m in p.moves)
            ]
            if your_glide:
                glide_names = ", ".join(p.name for p in your_glide)
                notes.append(
                    f"Your {setter.name} (Grassy Terrain) enables {glide_names}'s "
                    f"Grassy Glide (+1 priority)"
                )
        elif terrain == "misty":
            notes.append(
                f"Your {setter.name} (Misty Terrain) halves Dragon damage and "
                f"prevents status on grounded Pokemon"
            )

    # Their terrain effects (threats to us)
    for setter, terrain in their_terrain:
        if terrain == "psychic":
            your_priority = [
                p for p in your_profiles
                if any(pm["priority"] > 0 and not pm["is_status"] for pm in p.priority_moves)
            ]
            your_fo = [p for p in your_profiles if p.has_fake_out]
            if your_priority or your_fo:
                blockers = set()
                for p in your_priority:
                    blockers.add(p.name)
                for p in your_fo:
                    blockers.add(p.name)
                notes.append(
                    f"Their {setter.name} (Psychic Terrain) blocks your priority from "
                    f"{', '.join(blockers)} on grounded targets"
                )
        elif terrain == "electric":
            your_sleep = [
                p for p in your_profiles
                if any(normalize_move_name(m.name) in ("spore", "sleep-powder", "yawn", "dark-void", "hypnosis")
                       for m in p.moves)
            ]
            if your_sleep:
                sleep_names = ", ".join(p.name for p in your_sleep)
                notes.append(
                    f"Their {setter.name} (Electric Terrain) prevents sleep - "
                    f"blocks your {sleep_names}'s sleep moves on grounded targets"
                )
        elif terrain == "grassy":
            their_glide = [
                p for p in their_profiles
                if any(normalize_move_name(m.name) == "grassy-glide" for m in p.moves)
            ]
            if their_glide:
                glide_names = ", ".join(p.name for p in their_glide)
                notes.append(
                    f"Their {setter.name} (Grassy Terrain) enables {glide_names}'s "
                    f"Grassy Glide (+1 priority)"
                )

    return notes


def _analyze_redirect_interactions(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
) -> list[str]:
    """Analyze Follow Me / Rage Powder redirect interactions.

    Covers:
    - Redirect users on both sides
    - Safety Goggles bypassing Rage Powder
    - Grass-type immunity to Rage Powder
    - Mold Breaker ignoring redirect abilities
    """
    notes = []

    your_redirect = [p for p in your_profiles if p.has_follow_me]
    their_redirect = [p for p in their_profiles if p.has_follow_me]

    for rp in your_redirect:
        is_rage_powder = any(
            normalize_move_name(m.name) == "rage-powder" for m in rp.moves
        )
        move_name = "Rage Powder" if is_rage_powder else "Follow Me"
        notes.append(f"Your {rp.name} has {move_name} - redirects single-target attacks")

        if is_rage_powder:
            # Grass types and Safety Goggles users ignore Rage Powder
            bypasses = []
            for tp in their_profiles:
                types_lower = [t.lower() for t in tp.build.types]
                if "grass" in types_lower:
                    bypasses.append(f"{tp.name} (Grass type)")
                elif tp.has_safety_goggles:
                    bypasses.append(f"{tp.name} (Safety Goggles)")
            if bypasses:
                notes.append(
                    f"  -> Rage Powder bypassed by: {', '.join(bypasses)}"
                )

    for rp in their_redirect:
        is_rage_powder = any(
            normalize_move_name(m.name) == "rage-powder" for m in rp.moves
        )
        move_name = "Rage Powder" if is_rage_powder else "Follow Me"
        notes.append(f"Their {rp.name} has {move_name} - redirects your single-target attacks")

        if is_rage_powder:
            bypasses = []
            for yp in your_profiles:
                types_lower = [t.lower() for t in yp.build.types]
                if "grass" in types_lower:
                    bypasses.append(f"{yp.name} (Grass type)")
                elif yp.has_safety_goggles:
                    bypasses.append(f"{yp.name} (Safety Goggles)")
            if bypasses:
                notes.append(
                    f"  -> Your {', '.join(bypasses)} ignores Rage Powder"
                )

    return notes


def generate_full_game_plan(
    your_profiles: list[PokemonProfile],
    their_profiles: list[PokemonProfile],
) -> FullGamePlan:
    """Generate a complete, priority-aware game plan.

    Integrates matchup matrix, Fake Out speed war, Prankster interactions,
    lead recommendations, turn 1 analysis, threat assessment, win conditions,
    and bring-4 recommendations.
    """
    # Build matchup matrix using existing builds
    your_builds = [p.build for p in your_profiles]
    their_builds = [p.build for p in their_profiles]

    # Use existing moves if available for more accurate scoring
    your_moves_map = {p.name: p.moves for p in your_profiles}
    their_moves_map = {p.name: p.moves for p in their_profiles}

    matrix, detailed = build_matchup_matrix(your_builds, their_builds)
    overall_score = calculate_team_advantage(your_builds, their_builds)

    if overall_score >= 60:
        overall_matchup = "Favorable"
    elif overall_score >= 45:
        overall_matchup = "Even"
    else:
        overall_matchup = "Unfavorable"

    # Lead recommendations
    leads = _recommend_leads(your_profiles, their_profiles, matrix)

    # Turn 1 analysis (using top lead)
    turn_1 = _build_turn_1_priority_order(
        leads[0], your_profiles, their_profiles
    ) if leads else []

    # Threat assessment
    threats = _rank_threats(your_profiles, their_profiles, matrix)

    # Win condition
    win_strat, win_details = _determine_win_condition(
        your_profiles, their_profiles, threats, overall_score
    )

    # Speed control & interaction notes
    speed_notes = []
    speed_notes.extend(_analyze_fake_out_war(your_profiles, their_profiles))
    speed_notes.extend(_analyze_prankster_interactions(your_profiles, their_profiles))
    speed_notes.extend(_analyze_terrain_interactions(your_profiles, their_profiles))
    speed_notes.extend(_analyze_redirect_interactions(your_profiles, their_profiles))

    your_tw = [p for p in your_profiles if p.is_tailwind_setter]
    their_tw = [p for p in their_profiles if p.is_tailwind_setter]
    your_tr = [p for p in your_profiles if p.is_trick_room_setter]
    their_tr = [p for p in their_profiles if p.is_trick_room_setter]
    if your_tw:
        tw_names = [p.name for p in your_tw]
        speed_notes.append(f"Your Tailwind setters: {', '.join(tw_names)}")
    if their_tw:
        tw_names = [p.name for p in their_tw]
        speed_notes.append(f"Their Tailwind setters: {', '.join(tw_names)}")
    if your_tr:
        tr_names = [p.name for p in your_tr]
        speed_notes.append(f"Your Trick Room setters: {', '.join(tr_names)}")
    if their_tr:
        tr_names = [p.name for p in their_tr]
        speed_notes.append(f"Their Trick Room setters: {', '.join(tr_names)}")

    # Bring 4
    bring_rec = _recommend_bring_4(
        your_profiles, their_profiles, threats, leads[0], matrix
    ) if leads else BringRec(
        bring=[p.name for p in your_profiles[:4]],
        leave_behind=[p.name for p in your_profiles[4:]],
        reasoning=["Default selection"],
    )

    # Build markdown summary
    md = _format_game_plan_markdown(
        your_profiles, their_profiles, overall_matchup, overall_score,
        leads, turn_1, threats, win_strat, win_details, speed_notes, bring_rec,
    )

    return FullGamePlan(
        your_team=[p.name for p in your_profiles],
        opponent_team=[p.name for p in their_profiles],
        overall_matchup=overall_matchup,
        overall_score=round(overall_score, 1),
        lead_recommendations=leads,
        turn_1_priority_order=turn_1,
        threat_assessment=threats,
        win_condition=win_strat,
        win_condition_detail=win_details,
        speed_control_notes=speed_notes,
        bring_recommendation=bring_rec,
        markdown_summary=md,
    )


def _format_game_plan_markdown(
    your_profiles, their_profiles, overall_matchup, overall_score,
    leads, turn_1, threats, win_strat, win_details, speed_notes, bring_rec,
) -> str:
    """Format the game plan as readable markdown."""
    lines = []
    opp_names = ", ".join(p.name for p in their_profiles)
    lines.append(f"## Game Plan vs {opp_names}")
    lines.append("")
    lines.append(f"### Overall Matchup: {overall_matchup} ({overall_score:.0f}%)")
    lines.append("")

    # Lead recommendations
    lines.append("### Lead Recommendations")
    lines.append("")
    for i, lead in enumerate(leads):
        lines.append(f"**#{i+1}: {lead.pokemon_1} + {lead.pokemon_2}** (Score: {lead.score})")
        for r in lead.reasoning:
            lines.append(f"- {r}")
        if lead.fake_out_note:
            lines.append(f"- {lead.fake_out_note}")
        if lead.prankster_note:
            lines.append(f"- {lead.prankster_note}")
        lines.append("")

    # Turn 1 priority order
    if turn_1:
        lines.append("### Turn 1 Priority Order")
        lines.append("")
        for i, action in enumerate(turn_1):
            side_label = "Your" if action.side == "yours" else "Their"
            prio_str = f"+{action.priority}" if action.priority >= 0 else str(action.priority)
            lines.append(
                f"{i+1}. [{prio_str}] {side_label} {action.pokemon} "
                f"{action.move} (speed: {action.speed}) - {action.note}"
            )
        lines.append("")

    # Threat assessment
    lines.append("### Threat Assessment")
    lines.append("")
    lines.append("| Threat | Level | Your Answer(s) | Notes |")
    lines.append("|--------|-------|-----------------|-------|")
    for t in threats:
        answers = ", ".join(t.your_answers[:2])
        lines.append(f"| {t.pokemon_name} | {t.threat_level} | {answers} | {t.reason} |")
    lines.append("")

    # Win condition
    lines.append(f"### Win Condition: {win_strat}")
    lines.append("")
    for d in win_details:
        lines.append(f"- {d}")
    lines.append("")

    # Speed control
    if speed_notes:
        lines.append("### Speed Control & Priority Notes")
        lines.append("")
        for note in speed_notes:
            lines.append(f"- {note}")
        lines.append("")

    # Bring 4
    lines.append("### Bring 4 / Leave 2")
    lines.append("")
    lines.append(f"**Bring:** {', '.join(bring_rec.bring)}")
    if bring_rec.leave_behind:
        lines.append(f"**Leave:** {', '.join(bring_rec.leave_behind)}")
    lines.append("")
    for r in bring_rec.reasoning:
        lines.append(f"- {r}")

    return "\n".join(lines)
