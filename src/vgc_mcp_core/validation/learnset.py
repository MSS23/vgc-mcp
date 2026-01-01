"""Move legality and learnset validation."""

from typing import Optional
from dataclasses import dataclass


@dataclass
class MoveValidationResult:
    """Result of validating a single move."""
    move: str
    legal: bool
    methods: list[str]  # How the move can be learned
    reason: str


@dataclass
class MovesetValidationResult:
    """Result of validating a full moveset."""
    pokemon: str
    all_legal: bool
    moves: list[MoveValidationResult]
    illegal_moves: list[str]


def normalize_move_name(move: str) -> str:
    """Normalize move name for comparison."""
    return move.lower().replace(" ", "-").replace("'", "").strip()


async def get_learnable_moves(
    pokemon_name: str,
    pokeapi,
    method: Optional[str] = None
) -> dict:
    """
    Get all moves a Pokemon can learn.

    Args:
        pokemon_name: Name of the Pokemon
        pokeapi: PokeAPI client instance
        method: Optional filter by learn method (level-up, machine, egg, tutor)

    Returns:
        Dict mapping move names to their learn methods
    """
    try:
        # Fetch Pokemon data which includes moves
        pokemon_name = pokemon_name.lower().replace(" ", "-")
        data = await pokeapi._fetch(f"pokemon/{pokemon_name}")

        if not data:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        moves = {}
        for move_entry in data.get("moves", []):
            move_name = move_entry["move"]["name"]
            methods = []

            for version_detail in move_entry.get("version_group_details", []):
                learn_method = version_detail.get("move_learn_method", {}).get("name", "")
                if learn_method and learn_method not in methods:
                    methods.append(learn_method)

            # Filter by method if specified
            if method:
                if method.lower() in [m.lower() for m in methods]:
                    moves[move_name] = methods
            else:
                moves[move_name] = methods

        return {
            "pokemon": pokemon_name,
            "move_count": len(moves),
            "moves": moves
        }

    except Exception as e:
        return {"error": str(e)}


async def validate_moveset(
    pokemon_name: str,
    moves: list[str],
    pokeapi
) -> MovesetValidationResult:
    """
    Validate that all moves are legal for a Pokemon.

    Args:
        pokemon_name: Name of the Pokemon
        moves: List of move names to validate
        pokeapi: PokeAPI client instance

    Returns:
        MovesetValidationResult with details for each move
    """
    learnable = await get_learnable_moves(pokemon_name, pokeapi)

    if "error" in learnable:
        return MovesetValidationResult(
            pokemon=pokemon_name,
            all_legal=False,
            moves=[],
            illegal_moves=moves
        )

    learnable_moves = learnable.get("moves", {})
    results = []
    illegal = []

    for move in moves:
        if not move:
            continue

        normalized = normalize_move_name(move)

        if normalized in learnable_moves:
            methods = learnable_moves[normalized]
            results.append(MoveValidationResult(
                move=move,
                legal=True,
                methods=methods,
                reason=f"Learnable via: {', '.join(methods)}"
            ))
        else:
            results.append(MoveValidationResult(
                move=move,
                legal=False,
                methods=[],
                reason="Not learnable by this Pokemon"
            ))
            illegal.append(move)

    return MovesetValidationResult(
        pokemon=pokemon_name,
        all_legal=len(illegal) == 0,
        moves=results,
        illegal_moves=illegal
    )


async def validate_team_movesets(team, pokeapi) -> list[dict]:
    """
    Validate movesets for all Pokemon on a team.

    Args:
        team: Team object with Pokemon
        pokeapi: PokeAPI client instance

    Returns:
        List of validation results for each Pokemon
    """
    results = []

    for slot in team.slots:
        pokemon = slot.pokemon
        if pokemon.moves:
            validation = await validate_moveset(
                pokemon.name,
                pokemon.moves,
                pokeapi
            )
            results.append({
                "pokemon": pokemon.name,
                "all_legal": validation.all_legal,
                "illegal_moves": validation.illegal_moves,
                "details": [
                    {
                        "move": m.move,
                        "legal": m.legal,
                        "methods": m.methods,
                        "reason": m.reason
                    }
                    for m in validation.moves
                ]
            })

    return results


def categorize_learn_method(method: str) -> str:
    """
    Categorize a learn method into a user-friendly category.

    Args:
        method: Raw learn method from PokeAPI

    Returns:
        User-friendly category name
    """
    method = method.lower()

    if method == "level-up":
        return "Level Up"
    elif method == "machine":
        return "TM/TR"
    elif method == "egg":
        return "Egg Move (breeding required)"
    elif method == "tutor":
        return "Move Tutor"
    elif method == "stadium-surfing-pikachu":
        return "Special Event"
    elif method == "light-ball-egg":
        return "Special Breeding"
    elif method == "colosseum-purification":
        return "Colosseum Purification"
    elif method == "xd-shadow":
        return "XD Shadow"
    elif method == "xd-purification":
        return "XD Purification"
    elif method == "form-change":
        return "Form Change"
    elif method == "zygarde-cube":
        return "Zygarde Cube"
    else:
        return method.replace("-", " ").title()


async def suggest_legal_moves(
    pokemon_name: str,
    pokeapi,
    smogon_client=None,
    limit: int = 10
) -> dict:
    """
    Suggest legal competitive moves for a Pokemon.

    Combines learnset data with Smogon usage if available.

    Args:
        pokemon_name: Name of the Pokemon
        pokeapi: PokeAPI client instance
        smogon_client: Optional Smogon client for usage data
        limit: Max suggestions to return

    Returns:
        Dict with suggested moves and their info
    """
    learnable = await get_learnable_moves(pokemon_name, pokeapi)

    if "error" in learnable:
        return {"error": learnable["error"]}

    all_moves = list(learnable.get("moves", {}).keys())
    suggestions = []

    # If Smogon data is available, prioritize popular moves
    if smogon_client:
        try:
            usage = await smogon_client.get_pokemon_usage(pokemon_name)
            if usage and "moves" in usage:
                popular_moves = list(usage["moves"].keys())

                # Add popular moves that are also learnable
                for move in popular_moves:
                    normalized = normalize_move_name(move)
                    if normalized in learnable["moves"]:
                        methods = learnable["moves"][normalized]
                        suggestions.append({
                            "move": move,
                            "usage": usage["moves"].get(move, 0),
                            "methods": methods,
                            "source": "Smogon usage + verified legal"
                        })

                        if len(suggestions) >= limit:
                            break
        except Exception:
            pass

    # Fill remaining slots with other learnable moves
    if len(suggestions) < limit:
        for move in all_moves:
            if not any(s["move"].lower().replace(" ", "-") == move for s in suggestions):
                suggestions.append({
                    "move": move.replace("-", " ").title(),
                    "usage": None,
                    "methods": learnable["moves"][move],
                    "source": "Learnable"
                })

                if len(suggestions) >= limit:
                    break

    return {
        "pokemon": pokemon_name,
        "suggestions": suggestions
    }
