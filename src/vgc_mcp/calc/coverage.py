"""Move-based coverage analysis for VGC teams.

This module provides advanced coverage analysis based on actual moves,
not just Pokemon types (STAB). It can identify coverage holes,
suggest coverage moves, and detect quad weaknesses.
"""

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .modifiers import TYPE_CHART, get_type_effectiveness


# All Pokemon types
ALL_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
]


# Common VGC coverage moves by type with their base power
# Used for suggesting coverage options
COVERAGE_MOVES = {
    "Normal": [
        {"name": "Hyper Voice", "power": 90, "category": "special", "spread": True},
        {"name": "Body Slam", "power": 85, "category": "physical"},
        {"name": "Return", "power": 102, "category": "physical"},
        {"name": "Facade", "power": 70, "category": "physical"},
        {"name": "Extreme Speed", "power": 80, "category": "physical", "priority": 2},
    ],
    "Fire": [
        {"name": "Heat Wave", "power": 95, "category": "special", "spread": True},
        {"name": "Flamethrower", "power": 90, "category": "special"},
        {"name": "Fire Blast", "power": 110, "category": "special"},
        {"name": "Overheat", "power": 130, "category": "special"},
        {"name": "Flare Blitz", "power": 120, "category": "physical", "recoil": True},
        {"name": "Sacred Fire", "power": 100, "category": "physical"},
    ],
    "Water": [
        {"name": "Muddy Water", "power": 90, "category": "special", "spread": True},
        {"name": "Surf", "power": 90, "category": "special", "spread": True},
        {"name": "Scald", "power": 80, "category": "special"},
        {"name": "Hydro Pump", "power": 110, "category": "special"},
        {"name": "Liquidation", "power": 85, "category": "physical"},
        {"name": "Aqua Jet", "power": 40, "category": "physical", "priority": 1},
        {"name": "Surging Strikes", "power": 25, "category": "physical", "multi_hit": 3},
    ],
    "Electric": [
        {"name": "Discharge", "power": 80, "category": "special", "spread": True},
        {"name": "Electroweb", "power": 55, "category": "special", "spread": True},
        {"name": "Thunderbolt", "power": 90, "category": "special"},
        {"name": "Thunder", "power": 110, "category": "special"},
        {"name": "Volt Switch", "power": 70, "category": "special"},
        {"name": "Wild Charge", "power": 90, "category": "physical", "recoil": True},
    ],
    "Grass": [
        {"name": "Leaf Storm", "power": 130, "category": "special"},
        {"name": "Energy Ball", "power": 90, "category": "special"},
        {"name": "Giga Drain", "power": 75, "category": "special"},
        {"name": "Wood Hammer", "power": 120, "category": "physical", "recoil": True},
        {"name": "Power Whip", "power": 120, "category": "physical"},
        {"name": "Grassy Glide", "power": 55, "category": "physical", "priority": 1, "conditional": "Grassy Terrain"},
    ],
    "Ice": [
        {"name": "Blizzard", "power": 110, "category": "special", "spread": True},
        {"name": "Ice Beam", "power": 90, "category": "special"},
        {"name": "Freeze-Dry", "power": 70, "category": "special", "note": "Super effective vs Water"},
        {"name": "Icicle Crash", "power": 85, "category": "physical"},
        {"name": "Ice Shard", "power": 40, "category": "physical", "priority": 1},
        {"name": "Triple Axel", "power": 120, "category": "physical", "multi_hit": 3},
    ],
    "Fighting": [
        {"name": "Close Combat", "power": 120, "category": "physical"},
        {"name": "Drain Punch", "power": 75, "category": "physical"},
        {"name": "Mach Punch", "power": 40, "category": "physical", "priority": 1},
        {"name": "Focus Blast", "power": 120, "category": "special"},
        {"name": "Aura Sphere", "power": 80, "category": "special"},
        {"name": "Sacred Sword", "power": 90, "category": "physical"},
    ],
    "Poison": [
        {"name": "Sludge Bomb", "power": 90, "category": "special"},
        {"name": "Gunk Shot", "power": 120, "category": "physical"},
        {"name": "Poison Jab", "power": 80, "category": "physical"},
        {"name": "Venoshock", "power": 65, "category": "special"},
    ],
    "Ground": [
        {"name": "Earthquake", "power": 100, "category": "physical", "spread": True},
        {"name": "Bulldoze", "power": 60, "category": "physical", "spread": True},
        {"name": "Earth Power", "power": 90, "category": "special"},
        {"name": "High Horsepower", "power": 95, "category": "physical"},
        {"name": "Stomping Tantrum", "power": 75, "category": "physical"},
        {"name": "Precipice Blades", "power": 120, "category": "physical", "spread": True},
    ],
    "Flying": [
        {"name": "Air Slash", "power": 75, "category": "special"},
        {"name": "Hurricane", "power": 110, "category": "special"},
        {"name": "Brave Bird", "power": 120, "category": "physical", "recoil": True},
        {"name": "Acrobatics", "power": 55, "category": "physical", "note": "110 BP without item"},
        {"name": "Tailwind", "power": 0, "category": "status", "note": "Speed control"},
    ],
    "Psychic": [
        {"name": "Psychic", "power": 90, "category": "special"},
        {"name": "Psyshock", "power": 80, "category": "special", "note": "Targets Defense"},
        {"name": "Expanding Force", "power": 80, "category": "special", "note": "120 BP in Psychic Terrain"},
        {"name": "Zen Headbutt", "power": 80, "category": "physical"},
        {"name": "Trick Room", "power": 0, "category": "status", "note": "Speed control"},
    ],
    "Bug": [
        {"name": "Bug Buzz", "power": 90, "category": "special"},
        {"name": "U-turn", "power": 70, "category": "physical"},
        {"name": "First Impression", "power": 90, "category": "physical", "priority": 2, "note": "First turn only"},
        {"name": "X-Scissor", "power": 80, "category": "physical"},
        {"name": "Leech Life", "power": 80, "category": "physical"},
    ],
    "Rock": [
        {"name": "Rock Slide", "power": 75, "category": "physical", "spread": True},
        {"name": "Stone Edge", "power": 100, "category": "physical"},
        {"name": "Power Gem", "power": 80, "category": "special"},
        {"name": "Head Smash", "power": 150, "category": "physical", "recoil": True},
        {"name": "Accelerock", "power": 40, "category": "physical", "priority": 1},
    ],
    "Ghost": [
        {"name": "Shadow Ball", "power": 80, "category": "special"},
        {"name": "Poltergeist", "power": 110, "category": "physical"},
        {"name": "Shadow Sneak", "power": 40, "category": "physical", "priority": 1},
        {"name": "Phantom Force", "power": 90, "category": "physical"},
        {"name": "Astral Barrage", "power": 120, "category": "special", "spread": True},
    ],
    "Dragon": [
        {"name": "Draco Meteor", "power": 130, "category": "special"},
        {"name": "Dragon Pulse", "power": 85, "category": "special"},
        {"name": "Dragon Claw", "power": 80, "category": "physical"},
        {"name": "Outrage", "power": 120, "category": "physical"},
        {"name": "Breaking Swipe", "power": 60, "category": "physical", "spread": True},
        {"name": "Dragon Darts", "power": 50, "category": "physical", "multi_hit": 2},
    ],
    "Dark": [
        {"name": "Snarl", "power": 55, "category": "special", "spread": True},
        {"name": "Dark Pulse", "power": 80, "category": "special"},
        {"name": "Knock Off", "power": 65, "category": "physical", "note": "97.5 BP with item"},
        {"name": "Sucker Punch", "power": 70, "category": "physical", "priority": 1, "conditional": True},
        {"name": "Crunch", "power": 80, "category": "physical"},
        {"name": "Foul Play", "power": 95, "category": "physical", "note": "Uses target's Attack"},
    ],
    "Steel": [
        {"name": "Iron Head", "power": 80, "category": "physical"},
        {"name": "Flash Cannon", "power": 80, "category": "special"},
        {"name": "Steel Beam", "power": 140, "category": "special", "recoil": True},
        {"name": "Bullet Punch", "power": 40, "category": "physical", "priority": 1},
        {"name": "Heavy Slam", "power": 0, "category": "physical", "note": "Weight-based"},
        {"name": "Behemoth Blade", "power": 100, "category": "physical"},
    ],
    "Fairy": [
        {"name": "Dazzling Gleam", "power": 80, "category": "special", "spread": True},
        {"name": "Moonblast", "power": 95, "category": "special"},
        {"name": "Play Rough", "power": 90, "category": "physical"},
        {"name": "Spirit Break", "power": 75, "category": "physical"},
        {"name": "Draining Kiss", "power": 50, "category": "special"},
    ],
}


@dataclass
class MoveCoverage:
    """Coverage data for a single move."""
    move_name: str
    move_type: str
    pokemon: str
    is_stab: bool
    super_effective_vs: list[str] = field(default_factory=list)
    effectiveness_map: dict[str, float] = field(default_factory=dict)


@dataclass
class TypeCoverageResult:
    """Coverage analysis for a single type."""
    type_name: str
    covered_by: list[MoveCoverage] = field(default_factory=list)
    stab_coverage: list[MoveCoverage] = field(default_factory=list)
    non_stab_coverage: list[MoveCoverage] = field(default_factory=list)

    @property
    def is_covered(self) -> bool:
        return len(self.covered_by) > 0

    @property
    def coverage_count(self) -> int:
        return len(self.covered_by)


@dataclass
class QuadWeakness:
    """A 4x type weakness for a Pokemon."""
    pokemon: str
    weak_to: str
    multiplier: float
    types: list[str]


@dataclass
class CoverageAnalysisResult:
    """Complete coverage analysis for a team."""
    team_pokemon: list[str]
    type_coverage: dict[str, TypeCoverageResult]
    coverage_holes: list[str]  # Types with no SE coverage
    quad_weaknesses: list[QuadWeakness]
    coverage_summary: dict[str, int]  # Type -> count of Pokemon that can hit SE
    best_coverage: list[str]  # Top 5 types with most coverage
    worst_coverage: list[str]  # Types with least/no coverage


def normalize_move_name(move_name: str) -> str:
    """Normalize move name for lookups."""
    return move_name.lower().replace(" ", "-").replace("'", "")


def get_move_type_from_name(move_name: str, move_data: Optional[dict] = None) -> Optional[str]:
    """
    Get move type from move name.
    Uses move_data if provided, otherwise searches COVERAGE_MOVES.
    """
    if move_data and "type" in move_data:
        return move_data["type"].capitalize()

    normalized = normalize_move_name(move_name)

    # Search through coverage moves
    for move_type, moves in COVERAGE_MOVES.items():
        for move in moves:
            if normalize_move_name(move["name"]) == normalized:
                return move_type

    return None


def analyze_move_coverage(
    team_data: list[dict],
    move_types: Optional[dict[str, dict[str, str]]] = None
) -> CoverageAnalysisResult:
    """
    Analyze team's move-based coverage.

    Args:
        team_data: List of Pokemon dicts with 'name', 'types', and 'moves' keys
        move_types: Optional dict mapping move names to their types
                   {move_name: {"type": "Fire", "category": "special"}}

    Returns:
        CoverageAnalysisResult with complete coverage analysis
    """
    move_types = move_types or {}

    # Initialize type coverage tracking
    type_coverage: dict[str, TypeCoverageResult] = {
        t: TypeCoverageResult(type_name=t) for t in ALL_TYPES
    }

    team_pokemon = []
    quad_weaknesses = []

    for pokemon_data in team_data:
        pokemon_name = pokemon_data.get("name", "Unknown")
        pokemon_types = [t.capitalize() for t in pokemon_data.get("types", [])]
        moves = pokemon_data.get("moves", [])

        team_pokemon.append(pokemon_name)

        # Check for quad weaknesses
        for attack_type in ALL_TYPES:
            eff = get_type_effectiveness(attack_type, pokemon_types)
            if eff >= 4.0:
                quad_weaknesses.append(QuadWeakness(
                    pokemon=pokemon_name,
                    weak_to=attack_type,
                    multiplier=eff,
                    types=pokemon_types
                ))

        # Analyze each move's coverage
        for move_name in moves:
            if not move_name:
                continue

            # Get move type
            move_type = None
            if move_name in move_types:
                move_type = move_types[move_name].get("type", "").capitalize()
            else:
                move_type = get_move_type_from_name(move_name)

            if not move_type:
                continue

            # Check if STAB
            is_stab = move_type in pokemon_types

            # Calculate what this move hits super-effectively
            super_effective = []
            for target_type in ALL_TYPES:
                eff = get_type_effectiveness(move_type, [target_type])
                if eff >= 2.0:
                    super_effective.append(target_type)

            # Create coverage entry
            coverage = MoveCoverage(
                move_name=move_name,
                move_type=move_type,
                pokemon=pokemon_name,
                is_stab=is_stab,
                super_effective_vs=super_effective
            )

            # Add to type coverage
            for target_type in super_effective:
                type_coverage[target_type].covered_by.append(coverage)
                if is_stab:
                    type_coverage[target_type].stab_coverage.append(coverage)
                else:
                    type_coverage[target_type].non_stab_coverage.append(coverage)

    # Calculate coverage holes
    coverage_holes = [
        t for t, cov in type_coverage.items()
        if not cov.is_covered
    ]

    # Calculate coverage summary
    coverage_summary = {
        t: len(set(c.pokemon for c in cov.covered_by))
        for t, cov in type_coverage.items()
    }

    # Sort types by coverage
    sorted_coverage = sorted(
        coverage_summary.items(),
        key=lambda x: x[1],
        reverse=True
    )

    best_coverage = [t for t, c in sorted_coverage[:5] if c > 0]
    worst_coverage = [t for t, c in sorted_coverage if c == 0]

    return CoverageAnalysisResult(
        team_pokemon=team_pokemon,
        type_coverage=type_coverage,
        coverage_holes=coverage_holes,
        quad_weaknesses=quad_weaknesses,
        coverage_summary=coverage_summary,
        best_coverage=best_coverage,
        worst_coverage=worst_coverage
    )


def find_coverage_holes(team_data: list[dict]) -> list[str]:
    """
    Find types that no team member can hit super-effectively.

    Args:
        team_data: List of Pokemon dicts with 'name', 'types', and 'moves' keys

    Returns:
        List of type names with no super-effective coverage
    """
    result = analyze_move_coverage(team_data)
    return result.coverage_holes


def check_quad_weaknesses(team_data: list[dict]) -> list[dict]:
    """
    Find all 4x type weaknesses on the team.

    Args:
        team_data: List of Pokemon dicts with 'name' and 'types' keys

    Returns:
        List of dicts with pokemon, weak_to, and multiplier
    """
    result = analyze_move_coverage(team_data)
    return [
        {
            "pokemon": qw.pokemon,
            "weak_to": qw.weak_to,
            "multiplier": qw.multiplier,
            "types": qw.types
        }
        for qw in result.quad_weaknesses
    ]


def check_coverage_vs_pokemon(
    team_data: list[dict],
    target_types: list[str]
) -> dict:
    """
    Check if team has super-effective coverage against a specific Pokemon type.

    Args:
        team_data: List of Pokemon dicts with moves and types
        target_types: The types of the target Pokemon

    Returns:
        Dict with coverage info against the target
    """
    target_types = [t.capitalize() for t in target_types]

    coverage_options = []

    for pokemon_data in team_data:
        pokemon_name = pokemon_data.get("name", "Unknown")
        pokemon_types = [t.capitalize() for t in pokemon_data.get("types", [])]
        moves = pokemon_data.get("moves", [])

        for move_name in moves:
            if not move_name:
                continue

            move_type = get_move_type_from_name(move_name)
            if not move_type:
                continue

            eff = get_type_effectiveness(move_type, target_types)

            if eff >= 2.0:
                is_stab = move_type in pokemon_types
                coverage_options.append({
                    "pokemon": pokemon_name,
                    "move": move_name,
                    "move_type": move_type,
                    "effectiveness": eff,
                    "is_stab": is_stab,
                    "effective_power_bonus": 1.5 if is_stab else 1.0
                })

    # Sort by effectiveness (4x before 2x), then by STAB
    coverage_options.sort(
        key=lambda x: (x["effectiveness"], x["is_stab"]),
        reverse=True
    )

    return {
        "target_types": target_types,
        "has_coverage": len(coverage_options) > 0,
        "coverage_count": len(coverage_options),
        "options": coverage_options,
        "best_option": coverage_options[0] if coverage_options else None
    }


def suggest_coverage_moves(
    coverage_holes: list[str],
    existing_types: Optional[list[str]] = None,
    category_preference: Optional[str] = None,
    prioritize_spread: bool = False
) -> list[dict]:
    """
    Suggest moves to fill coverage gaps.

    Args:
        coverage_holes: Types the team can't hit super-effectively
        existing_types: Types already covered (to avoid redundancy)
        category_preference: "physical", "special", or None for both
        prioritize_spread: If True, prefer spread moves

    Returns:
        List of move suggestions with their coverage info
    """
    existing_types = [t.capitalize() for t in (existing_types or [])]
    suggestions = []

    for hole_type in coverage_holes:
        hole_type = hole_type.capitalize()

        # Find move types that hit this type super-effectively
        effective_types = []
        for attack_type in ALL_TYPES:
            eff = get_type_effectiveness(attack_type, [hole_type])
            if eff >= 2.0:
                effective_types.append(attack_type)

        for attack_type in effective_types:
            if attack_type not in COVERAGE_MOVES:
                continue

            for move in COVERAGE_MOVES[attack_type]:
                # Filter by category preference
                if category_preference:
                    if move.get("category") != category_preference:
                        continue

                # Calculate additional coverage this move provides
                additional_coverage = []
                for target_type in ALL_TYPES:
                    eff = get_type_effectiveness(attack_type, [target_type])
                    if eff >= 2.0:
                        if target_type not in existing_types:
                            additional_coverage.append(target_type)

                suggestion = {
                    "move": move["name"],
                    "type": attack_type,
                    "power": move.get("power", 0),
                    "category": move.get("category", "unknown"),
                    "fills_gap": hole_type,
                    "additional_coverage": additional_coverage,
                    "is_spread": move.get("spread", False),
                    "has_priority": move.get("priority", 0) > 0,
                    "notes": move.get("note", "")
                }

                suggestions.append(suggestion)

    # Sort suggestions
    def sort_key(s):
        score = 0
        score += len(s["additional_coverage"]) * 10  # Prefer multi-coverage
        score += s.get("power", 0) / 10  # Prefer higher power
        if prioritize_spread and s["is_spread"]:
            score += 50
        if s["has_priority"]:
            score += 20
        return score

    suggestions.sort(key=sort_key, reverse=True)

    # Remove duplicates
    seen_moves = set()
    unique_suggestions = []
    for s in suggestions:
        if s["move"] not in seen_moves:
            seen_moves.add(s["move"])
            unique_suggestions.append(s)

    return unique_suggestions[:10]  # Return top 10


def get_coverage_summary(team_data: list[dict]) -> dict:
    """
    Get a quick summary of team coverage.

    Args:
        team_data: List of Pokemon dicts with moves and types

    Returns:
        Summary dict with key coverage stats
    """
    result = analyze_move_coverage(team_data)

    # Count types with coverage
    covered_types = [t for t, c in result.coverage_summary.items() if c > 0]

    return {
        "total_types": len(ALL_TYPES),
        "covered_types": len(covered_types),
        "coverage_holes": result.coverage_holes,
        "hole_count": len(result.coverage_holes),
        "quad_weakness_count": len(result.quad_weaknesses),
        "quad_weaknesses": [
            f"{qw.pokemon} is 4x weak to {qw.weak_to}"
            for qw in result.quad_weaknesses
        ],
        "best_covered_types": result.best_coverage,
        "coverage_percentage": round(len(covered_types) / len(ALL_TYPES) * 100, 1)
    }
