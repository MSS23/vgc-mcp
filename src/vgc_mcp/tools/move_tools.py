"""MCP tools for move legality and learnset validation."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.validation.learnset import (
    categorize_learn_method,
    get_learnable_moves,
    suggest_legal_moves,
    validate_moveset,
    validate_team_movesets,
)


def register_move_tools(mcp: FastMCP, pokeapi, smogon, team_manager):
    """Register move validation tools with the MCP server."""

    @mcp.tool(
        title="Validate Pokemon Moveset",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def validate_pokemon_moveset(
        pokemon_name: Annotated[str, Field(
            description="Name of the Pokemon (e.g. 'rillaboom')",
            min_length=1,
        )],
        moves: Annotated[list[str], Field(
            description="Moves to validate (up to 4, e.g. ['fake-out', 'grassy-glide'])",
        )],
    ) -> dict:
        """Check if all moves are legal for a Pokemon.

        Validates against PokeAPI learnset data. Returns a per-move validation
        result with learn methods and a list of any illegal moves.
        """
        result = await validate_moveset(pokemon_name, moves, pokeapi)

        # Format for cleaner output
        return {
            "pokemon": result.pokemon,
            "all_legal": result.all_legal,
            "moves": [
                {
                    "move": m.move,
                    "legal": m.legal,
                    "methods": [categorize_learn_method(method) for method in m.methods],
                    "reason": m.reason
                }
                for m in result.moves
            ],
            "illegal_moves": result.illegal_moves,
            "message": (
                "All moves are legal!" if result.all_legal
                else f"Illegal moves found: {', '.join(result.illegal_moves)}"
            )
        }

    @mcp.tool(
        title="Get Pokemon Learnable Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_pokemon_learnable_moves(
        pokemon_name: Annotated[str, Field(
            description="Name of the Pokemon",
            min_length=1,
        )],
        method: Annotated[Optional[str], Field(
            description="Optional filter by learn method: 'level-up', 'machine', 'egg', or 'tutor'",
        )] = None,
    ) -> dict:
        """Get all moves a Pokemon can learn, grouped by learn method.

        Returns the total move count and moves categorized by how they are learned.
        """
        result = await get_learnable_moves(pokemon_name, pokeapi, method)

        if "error" in result:
            return result

        # Categorize moves by method for easier reading
        moves_by_method = {}
        for move_name, methods in result.get("moves", {}).items():
            for m in methods:
                category = categorize_learn_method(m)
                if category not in moves_by_method:
                    moves_by_method[category] = []
                if move_name not in moves_by_method[category]:
                    moves_by_method[category].append(move_name.replace("-", " ").title())

        return {
            "pokemon": result["pokemon"],
            "total_moves": result["move_count"],
            "filter": method or "all",
            "moves_by_method": moves_by_method,
            "message": f"{result['pokemon']} can learn {result['move_count']} moves"
        }

    @mcp.tool(
        title="Suggest Competitive Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_competitive_moves(
        pokemon_name: Annotated[str, Field(
            description="Name of the Pokemon",
            min_length=1,
        )],
        limit: Annotated[int, Field(
            ge=1,
            description="Number of suggestions to return",
        )] = 10,
    ) -> dict:
        """Suggest competitive moves for a Pokemon based on usage data.

        Combines Smogon usage data with learnset validation so suggested moves
        are both popular AND legal. Returns moves with usage rates and learn
        methods.
        """
        result = await suggest_legal_moves(pokemon_name, pokeapi, smogon, limit)

        if "error" in result:
            return result

        # Format suggestions nicely
        formatted_suggestions = []
        for suggestion in result.get("suggestions", []):
            formatted_suggestions.append({
                "move": suggestion["move"].replace("-", " ").title(),
                "usage_percent": suggestion.get("usage"),
                "learn_methods": [categorize_learn_method(m) for m in suggestion.get("methods", [])],
                "source": suggestion.get("source", "")
            })

        return {
            "pokemon": result["pokemon"],
            "suggestions": formatted_suggestions,
            "message": f"Top {len(formatted_suggestions)} competitive moves for {result['pokemon']}"
        }

    @mcp.tool(
        title="Check Team Movesets",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_team_movesets() -> dict:
        """Validate movesets for all Pokemon on the current team.

        Checks that every move on every team member is actually learnable by
        that Pokemon. Returns per-member validation results.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "valid": True,
                "message": "No Pokemon on team to validate"
            }

        results = await validate_team_movesets(team, pokeapi)

        all_legal = all(r["all_legal"] for r in results)

        return {
            "all_legal": all_legal,
            "pokemon_results": results,
            "message": (
                "All team movesets are legal!"
                if all_legal
                else "Some Pokemon have illegal moves"
            )
        }

    @mcp.tool(
        title="Check Egg Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_egg_moves(
        pokemon_name: Annotated[str, Field(
            description="Name of the Pokemon",
            min_length=1,
        )],
    ) -> dict:
        """Check which moves require breeding (egg moves) for a Pokemon.

        Egg moves require specific breeding setups and cannot be learned
        through TMs or level-up.
        """
        result = await get_learnable_moves(pokemon_name, pokeapi, method="egg")

        if "error" in result:
            return result

        egg_moves = list(result.get("moves", {}).keys())

        return {
            "pokemon": result["pokemon"],
            "egg_move_count": len(egg_moves),
            "egg_moves": [move.replace("-", " ").title() for move in egg_moves],
            "note": "Egg moves require breeding to obtain. Check compatible parents.",
            "message": f"{result['pokemon']} has {len(egg_moves)} egg moves"
        }

    @mcp.tool(
        title="Check TM Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_tm_moves(
        pokemon_name: Annotated[str, Field(
            description="Name of the Pokemon",
            min_length=1,
        )],
    ) -> dict:
        """Check which moves a Pokemon can learn via TM/TR.

        TM/TR moves are the most accessible competitive moves.
        """
        result = await get_learnable_moves(pokemon_name, pokeapi, method="machine")

        if "error" in result:
            return result

        tm_moves = list(result.get("moves", {}).keys())

        return {
            "pokemon": result["pokemon"],
            "tm_move_count": len(tm_moves),
            "tm_moves": [move.replace("-", " ").title() for move in tm_moves],
            "message": f"{result['pokemon']} can learn {len(tm_moves)} moves via TM/TR"
        }

    @mcp.tool(
        title="Find Move Learners",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_move_learners(
        move_name: Annotated[str, Field(
            description="Name of the move to search for (e.g. 'fake-out')",
            min_length=1,
        )],
        team_only: Annotated[bool, Field(
            description="If True, only check current team members; a full-dex search is not supported, so False returns guidance instead",
        )] = False,
    ) -> dict:
        """Find which Pokemon can learn a specific move.

        With team_only=True, checks each current team member's learnset and
        returns the learners with their learn methods. Without it, returns
        guidance on how to search instead.
        """
        if team_only:
            team = team_manager.get_current_team()

            if not team or len(team.slots) == 0:
                return {
                    "move": move_name,
                    "learners": [],
                    "message": "No Pokemon on team"
                }

            learners = []
            for slot in team.slots:
                pokemon_name = slot.pokemon.name
                learnable = await get_learnable_moves(pokemon_name, pokeapi)

                if "error" not in learnable:
                    normalized_move = move_name.lower().replace(" ", "-")
                    if normalized_move in learnable.get("moves", {}):
                        methods = learnable["moves"][normalized_move]
                        learners.append({
                            "pokemon": pokemon_name,
                            "methods": [categorize_learn_method(m) for m in methods]
                        })

            return {
                "move": move_name,
                "learners": learners,
                "message": (
                    f"{len(learners)} team member(s) can learn {move_name}"
                    if learners else f"No team member can learn {move_name}"
                )
            }
        else:
            # This would require searching all Pokemon - return guidance instead
            return {
                "move": move_name,
                "message": "Use team_only=True to check your team, or use Smogon data to find common users",
                "suggestion": "Try searching for Pokemon that commonly use this move in the meta"
            }
