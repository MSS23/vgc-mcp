"""Priority move and turn order analysis for VGC."""

from dataclasses import dataclass
from typing import Optional
from enum import IntEnum


class PriorityBracket(IntEnum):
    """Priority bracket values for moves."""
    HELPING_HAND = 5
    PROTECT = 4
    FAKE_OUT = 3
    EXTREME_SPEED = 2
    PRIORITY = 1
    NORMAL = 0
    VITAL_THROW = -1
    FOCUS_PUNCH = -3
    REVENGE = -4
    AFTER_YOU = -5
    COUNTER = -6
    TRICK_ROOM = -7


# Complete priority move database
PRIORITY_MOVES: dict[str, int] = {
    # +5 Priority
    "helping-hand": 5,

    # +4 Priority (Protection moves)
    "protect": 4,
    "detect": 4,
    "endure": 4,
    "kings-shield": 4,
    "spiky-shield": 4,
    "baneful-bunker": 4,
    "silk-trap": 4,
    "burning-bulwark": 4,
    "obstruct": 4,
    "max-guard": 4,

    # +3 Priority
    "fake-out": 3,
    "quick-guard": 3,
    "wide-guard": 3,
    "crafty-shield": 3,
    "mat-block": 3,

    # +2 Priority
    "extreme-speed": 2,
    "first-impression": 2,
    "feint": 2,

    # +1 Priority
    "aqua-jet": 1,
    "bullet-punch": 1,
    "ice-shard": 1,
    "mach-punch": 1,
    "quick-attack": 1,
    "shadow-sneak": 1,
    "sucker-punch": 1,
    "water-shuriken": 1,
    "accelerock": 1,
    "jet-punch": 1,
    "vacuum-wave": 1,
    "grassy-glide": 1,  # Only in Grassy Terrain

    # 0 Priority (most moves - not listed)

    # -1 Priority
    "vital-throw": -1,

    # -3 Priority
    "focus-punch": -3,
    "shell-trap": -3,
    "beak-blast": -3,

    # -4 Priority
    "avalanche": -4,
    "revenge": -4,

    # -5 Priority
    "after-you": -5,

    # -6 Priority
    "counter": -6,
    "mirror-coat": -6,
    "metal-burst": -6,

    # -7 Priority
    "trick-room": -7,
    "teleport": -7,
    "roar": -6,
    "whirlwind": -6,
    "dragon-tail": -6,
    "circle-throw": -6,
}

# Moves that are conditionally priority
CONDITIONAL_PRIORITY: dict[str, dict] = {
    "grassy-glide": {
        "base_priority": 0,
        "boosted_priority": 1,
        "condition": "grassy_terrain",
        "description": "+1 priority only in Grassy Terrain"
    },
    "gale-wings-moves": {
        "type": "Flying",
        "base_priority": 0,
        "boosted_priority": 1,
        "condition": "gale_wings_full_hp",
        "description": "+1 priority for Flying moves at full HP with Gale Wings"
    },
}

# Abilities that affect priority
PRIORITY_ABILITIES: dict[str, dict] = {
    "prankster": {
        "effect": "+1 priority to status moves",
        "boost": 1,
        "move_filter": "status",
        "dark_immune": True,  # Dark types immune to Prankster-boosted moves
    },
    "gale-wings": {
        "effect": "+1 priority to Flying moves at full HP",
        "boost": 1,
        "move_filter": "flying",
        "hp_requirement": "full",
    },
    "triage": {
        "effect": "+3 priority to healing moves",
        "boost": 3,
        "move_filter": "healing",
    },
    "stall": {
        "effect": "Always moves last in priority bracket",
        "modifier": "last",
    },
    "mycelium-might": {
        "effect": "Status moves ignore abilities but always go last",
        "modifier": "last_for_status",
    },
}

# Common Prankster users in VGC
PRANKSTER_POKEMON: list[str] = [
    "whimsicott", "grimmsnarl", "sableye", "murkrow", "tornadus",
    "thundurus", "klefki", "meowstic", "liepard", "illumise",
]

# Common Gale Wings users
GALE_WINGS_POKEMON: list[str] = [
    "talonflame", "fletchinder",
]

# Common Fake Out users in VGC
FAKE_OUT_POKEMON: list[str] = [
    "incineroar", "rillaboom", "mienshao", "hitmontop", "ambipom",
    "persian", "persian-alola", "weavile", "scrafty", "ludicolo",
    "kangaskhan", "infernape", "medicham", "lopunny", "mienfoo",
    "sneasel", "sneasel-hisui", "meowth", "meowth-alola", "meowth-galar",
]


@dataclass
class TurnOrderResult:
    """Result of turn order analysis."""
    pokemon1_name: str
    pokemon1_move: str
    pokemon1_priority: int
    pokemon1_speed: int
    pokemon2_name: str
    pokemon2_move: str
    pokemon2_priority: int
    pokemon2_speed: int
    first_mover: str
    reason: str
    speed_tie: bool = False
    trick_room_active: bool = False


@dataclass
class PriorityMoveInfo:
    """Information about a priority move."""
    move: str
    priority: int
    category: str  # "offensive", "defensive", "support"
    description: str


def normalize_move_name(move: str) -> str:
    """Normalize move name for lookup."""
    return move.lower().replace(" ", "-").replace("'", "").strip()


def get_move_priority(
    move: str,
    ability: Optional[str] = None,
    terrain: Optional[str] = None,
    is_status: bool = False,
    move_type: Optional[str] = None,
    hp_percent: float = 100.0
) -> int:
    """
    Get the priority of a move considering ability and terrain effects.

    Args:
        move: Name of the move
        ability: Pokemon's ability (for Prankster, Gale Wings, etc.)
        terrain: Active terrain (for Grassy Glide)
        is_status: Whether the move is a status move
        move_type: Type of the move (for Gale Wings)
        hp_percent: Current HP percentage (for Gale Wings)

    Returns:
        Priority value of the move
    """
    normalized = normalize_move_name(move)
    base_priority = PRIORITY_MOVES.get(normalized, 0)

    # Grassy Glide in Grassy Terrain
    if normalized == "grassy-glide" and terrain and terrain.lower() == "grassy":
        return 1
    elif normalized == "grassy-glide":
        return 0  # No priority without terrain

    # Prankster boost for status moves
    if ability and ability.lower() == "prankster" and is_status:
        return base_priority + 1

    # Gale Wings boost for Flying moves at full HP
    if ability and ability.lower() == "gale-wings":
        if move_type and move_type.lower() == "flying" and hp_percent >= 100:
            return base_priority + 1

    # Triage boost for healing moves
    if ability and ability.lower() == "triage":
        healing_moves = ["drain-punch", "giga-drain", "draining-kiss", "leech-life",
                        "horn-leech", "oblivion-wing", "parabolic-charge", "absorb",
                        "mega-drain", "strength-sap"]
        if normalized in healing_moves:
            return base_priority + 3

    return base_priority


def determine_turn_order(
    pokemon1_name: str,
    pokemon1_move: str,
    pokemon1_speed: int,
    pokemon2_name: str,
    pokemon2_move: str,
    pokemon2_speed: int,
    pokemon1_ability: Optional[str] = None,
    pokemon2_ability: Optional[str] = None,
    pokemon1_move_is_status: bool = False,
    pokemon2_move_is_status: bool = False,
    terrain: Optional[str] = None,
    trick_room: bool = False
) -> TurnOrderResult:
    """
    Determine which Pokemon moves first.

    Args:
        pokemon1_name: First Pokemon's name
        pokemon1_move: First Pokemon's move
        pokemon1_speed: First Pokemon's speed stat
        pokemon2_name: Second Pokemon's name
        pokemon2_move: Second Pokemon's move
        pokemon2_speed: Second Pokemon's speed stat
        pokemon1_ability: First Pokemon's ability
        pokemon2_ability: Second Pokemon's ability
        pokemon1_move_is_status: Whether Pokemon 1's move is status
        pokemon2_move_is_status: Whether Pokemon 2's move is status
        terrain: Active terrain
        trick_room: Whether Trick Room is active

    Returns:
        TurnOrderResult with analysis
    """
    # Get priorities
    p1_priority = get_move_priority(
        pokemon1_move, pokemon1_ability, terrain, pokemon1_move_is_status
    )
    p2_priority = get_move_priority(
        pokemon2_move, pokemon2_ability, terrain, pokemon2_move_is_status
    )

    # Determine first mover
    speed_tie = False

    if p1_priority != p2_priority:
        # Higher priority moves first
        if p1_priority > p2_priority:
            first = pokemon1_name
            reason = f"{pokemon1_move} has higher priority ({p1_priority} vs {p2_priority})"
        else:
            first = pokemon2_name
            reason = f"{pokemon2_move} has higher priority ({p2_priority} vs {p1_priority})"
    else:
        # Same priority - check speed
        if trick_room:
            # Trick Room: slower Pokemon moves first
            if pokemon1_speed < pokemon2_speed:
                first = pokemon1_name
                reason = f"Slower in Trick Room ({pokemon1_speed} vs {pokemon2_speed})"
            elif pokemon2_speed < pokemon1_speed:
                first = pokemon2_name
                reason = f"Slower in Trick Room ({pokemon2_speed} vs {pokemon1_speed})"
            else:
                first = "50/50"
                reason = f"Speed tie in Trick Room ({pokemon1_speed})"
                speed_tie = True
        else:
            # Normal: faster Pokemon moves first
            if pokemon1_speed > pokemon2_speed:
                first = pokemon1_name
                reason = f"Faster ({pokemon1_speed} vs {pokemon2_speed})"
            elif pokemon2_speed > pokemon1_speed:
                first = pokemon2_name
                reason = f"Faster ({pokemon2_speed} vs {pokemon1_speed})"
            else:
                first = "50/50"
                reason = f"Speed tie ({pokemon1_speed})"
                speed_tie = True

    return TurnOrderResult(
        pokemon1_name=pokemon1_name,
        pokemon1_move=pokemon1_move,
        pokemon1_priority=p1_priority,
        pokemon1_speed=pokemon1_speed,
        pokemon2_name=pokemon2_name,
        pokemon2_move=pokemon2_move,
        pokemon2_priority=p2_priority,
        pokemon2_speed=pokemon2_speed,
        first_mover=first,
        reason=reason,
        speed_tie=speed_tie,
        trick_room_active=trick_room
    )


def get_priority_moves_by_bracket(bracket: int) -> list[str]:
    """Get all moves at a specific priority bracket."""
    return [move for move, priority in PRIORITY_MOVES.items() if priority == bracket]


def categorize_priority_move(move: str) -> PriorityMoveInfo:
    """Categorize a priority move with description."""
    normalized = normalize_move_name(move)
    priority = PRIORITY_MOVES.get(normalized, 0)

    # Categorize by function
    protection_moves = {"protect", "detect", "endure", "kings-shield", "spiky-shield",
                       "baneful-bunker", "silk-trap", "burning-bulwark", "obstruct", "max-guard"}
    support_moves = {"helping-hand", "quick-guard", "wide-guard", "crafty-shield",
                    "mat-block", "after-you", "trick-room"}

    if normalized in protection_moves:
        category = "defensive"
        description = "Protection move - blocks incoming attacks"
    elif normalized in support_moves:
        category = "support"
        description = "Support move - helps team"
    elif priority > 0:
        category = "offensive"
        description = f"Priority {priority} attacking move"
    elif priority < 0:
        category = "delayed"
        description = f"Negative priority move (moves later)"
    else:
        category = "normal"
        description = "Standard priority"

    return PriorityMoveInfo(
        move=move,
        priority=priority,
        category=category,
        description=description
    )


def find_team_priority_moves(team_moves: dict[str, list[str]]) -> dict[str, list[PriorityMoveInfo]]:
    """
    Find all priority moves on a team.

    Args:
        team_moves: Dict mapping Pokemon names to their move lists

    Returns:
        Dict mapping Pokemon names to their priority moves
    """
    results = {}

    for pokemon, moves in team_moves.items():
        priority_moves = []
        for move in moves:
            normalized = normalize_move_name(move)
            if normalized in PRIORITY_MOVES:
                priority_moves.append(categorize_priority_move(move))

        if priority_moves:
            results[pokemon] = priority_moves

    return results


def analyze_fake_out_matchup(
    your_speed: int,
    opponent_pokemon: str,
    opponent_speed: int,
    trick_room: bool = False
) -> dict:
    """
    Analyze Fake Out speed interaction.

    Args:
        your_speed: Your Fake Out user's speed
        opponent_pokemon: Opponent's Pokemon name
        opponent_speed: Opponent's speed (if they also have Fake Out)
        trick_room: Whether Trick Room is active

    Returns:
        Analysis of Fake Out interaction
    """
    opponent_normalized = opponent_pokemon.lower().replace(" ", "-")
    opponent_has_fake_out = opponent_normalized in FAKE_OUT_POKEMON

    if not opponent_has_fake_out:
        return {
            "opponent_has_fake_out": False,
            "your_fake_out_lands": True,
            "message": f"{opponent_pokemon} cannot use Fake Out"
        }

    # Both have Fake Out - speed matters
    if trick_room:
        if your_speed < opponent_speed:
            result = "You Fake Out first (slower in TR)"
        elif opponent_speed < your_speed:
            result = "Opponent Fake Outs first (slower in TR)"
        else:
            result = "Speed tie - 50/50"
    else:
        if your_speed > opponent_speed:
            result = "You Fake Out first (faster)"
        elif opponent_speed > your_speed:
            result = "Opponent Fake Outs first (faster)"
        else:
            result = "Speed tie - 50/50"

    return {
        "opponent_has_fake_out": True,
        "your_speed": your_speed,
        "opponent_speed": opponent_speed,
        "trick_room": trick_room,
        "result": result,
        "message": f"Both Pokemon have Fake Out. {result}"
    }


def get_priority_bracket_summary() -> dict[int, list[str]]:
    """Get summary of all priority brackets with example moves."""
    brackets: dict[int, list[str]] = {}

    for move, priority in PRIORITY_MOVES.items():
        if priority not in brackets:
            brackets[priority] = []
        brackets[priority].append(move)

    # Sort by priority (highest first)
    return dict(sorted(brackets.items(), reverse=True))


def check_prankster_immunity(
    target_types: list[str],
    move_priority_from_prankster: bool
) -> bool:
    """
    Check if target is immune to Prankster-boosted move.

    Dark types are immune to moves that gained priority from Prankster.
    """
    if not move_priority_from_prankster:
        return False

    return "dark" in [t.lower() for t in target_types]
