"""MCP tools for priority move and turn order analysis."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.calc.priority import (
    FAKE_OUT_POKEMON,
    PRANKSTER_POKEMON,
    PRIORITY_MOVES,
    analyze_fake_out_matchup,
    categorize_priority_move,
    determine_turn_order,
    find_team_priority_moves,
    get_priority_bracket_summary,
    get_priority_moves_by_bracket,
)


def register_priority_tools(mcp: FastMCP, team_manager):
    """Register priority move analysis tools with the MCP server."""

    @mcp.tool(
        title="Analyze Turn Order",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_turn_order(
        pokemon1_name: Annotated[str, Field(description="First Pokemon's name", min_length=1)],
        pokemon1_move: Annotated[str, Field(description="Move being used by the first Pokemon", min_length=1)],
        pokemon1_speed: Annotated[int, Field(description="First Pokemon's final speed stat")],
        pokemon2_name: Annotated[str, Field(description="Second Pokemon's name", min_length=1)],
        pokemon2_move: Annotated[str, Field(description="Move being used by the second Pokemon", min_length=1)],
        pokemon2_speed: Annotated[int, Field(description="Second Pokemon's final speed stat")],
        pokemon1_ability: Annotated[Optional[str], Field(description="First Pokemon's ability (for Prankster, etc.)")] = None,
        pokemon2_ability: Annotated[Optional[str], Field(description="Second Pokemon's ability")] = None,
        trick_room: Annotated[bool, Field(description="Whether Trick Room is active")] = False,
        terrain: Annotated[Optional[str], Field(description="Active terrain: 'grassy', 'electric', 'psychic', or 'misty'")] = None,
    ) -> dict:
        """Determine which Pokemon moves first considering priority.

        Accounts for move priority brackets (+5 to -7), speed stats, Trick Room
        (reverses speed order), Prankster (+1 to status moves), and terrain
        effects (Grassy Glide). Returns the first mover with reasoning.
        """
        result = determine_turn_order(
            pokemon1_name=pokemon1_name,
            pokemon1_move=pokemon1_move,
            pokemon1_speed=pokemon1_speed,
            pokemon2_name=pokemon2_name,
            pokemon2_move=pokemon2_move,
            pokemon2_speed=pokemon2_speed,
            pokemon1_ability=pokemon1_ability,
            pokemon2_ability=pokemon2_ability,
            terrain=terrain,
            trick_room=trick_room
        )

        return {
            "first_mover": result.first_mover,
            "reason": result.reason,
            "speed_tie": result.speed_tie,
            "trick_room_active": result.trick_room_active,
            "pokemon1": {
                "name": result.pokemon1_name,
                "move": result.pokemon1_move,
                "priority": result.pokemon1_priority,
                "speed": result.pokemon1_speed
            },
            "pokemon2": {
                "name": result.pokemon2_name,
                "move": result.pokemon2_move,
                "priority": result.pokemon2_priority,
                "speed": result.pokemon2_speed
            },
            "message": f"{result.first_mover} moves first - {result.reason}"
        }

    @mcp.tool(
        title="Get Move Priority Info",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_move_priority_info(
        move_name: Annotated[str, Field(description="Name of the move", min_length=1)],
    ) -> dict:
        """Get priority information for a specific move.

        Returns the move's priority value, bracket, and category.
        """
        info = categorize_priority_move(move_name)

        return {
            "move": info.move,
            "priority": info.priority,
            "category": info.category,
            "description": info.description,
            "priority_bracket": (
                f"+{info.priority}" if info.priority > 0
                else str(info.priority) if info.priority < 0
                else "Normal (0)"
            )
        }

    @mcp.tool(
        title="List Team Priority Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_team_priority_moves() -> dict:
        """List all priority moves available on the current team.

        Reads the session's current team and returns priority moves per member.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "priority_moves": {},
                "message": "No Pokemon on team"
            }

        # Build move dict
        team_moves = {}
        for slot in team.slots:
            pokemon = slot.pokemon
            if pokemon.moves:
                team_moves[pokemon.name] = pokemon.moves

        results = find_team_priority_moves(team_moves)

        # Format for output
        formatted = {}
        for pokemon, moves in results.items():
            formatted[pokemon] = [
                {
                    "move": m.move,
                    "priority": m.priority,
                    "category": m.category
                }
                for m in moves
            ]

        total_priority = sum(len(moves) for moves in results.values())

        return {
            "priority_moves": formatted,
            "total_count": total_priority,
            "message": (
                f"Team has {total_priority} priority move(s)"
                if total_priority > 0 else "No priority moves on team"
            )
        }

    @mcp.tool(
        title="Check Fake Out Interaction",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_fake_out_interaction(
        your_speed: Annotated[int, Field(description="Your Fake Out user's final speed stat")],
        opponent_pokemon: Annotated[str, Field(description="Opponent's Pokemon name", min_length=1)],
        opponent_speed: Annotated[int, Field(description="Opponent's final speed stat (relevant if they also have Fake Out)")],
        trick_room: Annotated[bool, Field(description="Whether Trick Room is active")] = False,
    ) -> dict:
        """Analyze Fake Out speed interaction with an opponent.

        Fake Out is a +3 priority move that only works on turn 1; speed
        determines who Fake Outs first if both Pokemon have it.
        """
        return analyze_fake_out_matchup(your_speed, opponent_pokemon, opponent_speed, trick_room)

    @mcp.tool(
        title="List Priority Bracket Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_priority_bracket(
        bracket: Annotated[int, Field(description="Priority bracket, -7 to +5 (e.g. +5 Helping Hand, +4 Protect, +3 Fake Out, +2 Extreme Speed, +1 Aqua Jet, 0 most moves, -7 Trick Room)")],
    ) -> dict:
        """List all moves at a specific priority bracket.

        Returns the moves at that priority level along with a count.
        """
        moves = get_priority_moves_by_bracket(bracket)

        return {
            "bracket": bracket,
            "bracket_display": f"+{bracket}" if bracket > 0 else str(bracket),
            "moves": [move.replace("-", " ").title() for move in moves],
            "count": len(moves),
            "message": f"Found {len(moves)} moves at priority {bracket}"
        }

    @mcp.tool(
        title="Get Priority Overview",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_priority_overview() -> dict:
        """Get a complete overview of all priority brackets and their moves.

        Useful for understanding the full priority system.
        """
        brackets = get_priority_bracket_summary()

        formatted = {}
        for priority, moves in brackets.items():
            bracket_name = f"+{priority}" if priority > 0 else str(priority)
            formatted[bracket_name] = [m.replace("-", " ").title() for m in moves]

        return {
            "brackets": formatted,
            "total_priority_moves": len(PRIORITY_MOVES),
            "notes": [
                "Higher priority always moves first regardless of speed",
                "Within same priority, faster Pokemon moves first",
                "Trick Room reverses speed order but not priority",
                "Prankster adds +1 priority to status moves"
            ]
        }

    @mcp.tool(
        title="Find Priority Threats",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def find_priority_threats() -> dict:
        """Identify common priority move threats in the VGC meta.

        Returns Fake Out users, Prankster users, and common priority attackers.
        """
        threats = {
            "fake_out_users": {
                "pokemon": FAKE_OUT_POKEMON[:10],
                "move": "Fake Out",
                "priority": 3,
                "effect": "Flinches on turn 1"
            },
            "prankster_users": {
                "pokemon": PRANKSTER_POKEMON,
                "ability": "Prankster",
                "effect": "+1 priority to status moves",
                "common_moves": ["Thunder Wave", "Tailwind", "Trick Room", "Taunt"]
            },
            "common_priority_attackers": [
                {"pokemon": "Rillaboom", "move": "Grassy Glide", "priority": 1, "condition": "Grassy Terrain"},
                {"pokemon": "Urshifu", "move": "Aqua Jet", "priority": 1},
                {"pokemon": "Dragonite", "move": "Extreme Speed", "priority": 2},
                {"pokemon": "Scizor", "move": "Bullet Punch", "priority": 1},
                {"pokemon": "Weavile", "move": "Ice Shard", "priority": 1},
                {"pokemon": "Lucario", "move": "Bullet Punch", "priority": 1},
                {"pokemon": "Raging Bolt", "move": "Thunderclap", "priority": 1, "condition": "Attacking move only"},
            ]
        }

        return {
            "threats": threats,
            "message": "Common priority threats in VGC meta"
        }

    @mcp.tool(
        title="Check Prankster Interaction",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_prankster_interaction(
        target_types: Annotated[list[str], Field(description="Types of the target Pokemon")],
        move_name: Annotated[str, Field(description="Name of the move being used", min_length=1)],
        user_ability: Annotated[str, Field(description="Ability of the user (should be Prankster)", min_length=1)],
    ) -> dict:
        """Check if a Prankster-boosted move will affect the target.

        Dark-type Pokemon are immune to moves that gained priority from
        Prankster. Returns whether the move is blocked.
        """
        is_prankster = user_ability.lower().replace(" ", "-") == "prankster"
        has_dark = "dark" in [t.lower() for t in target_types]

        if not is_prankster:
            return {
                "ability_is_prankster": False,
                "move_blocked": False,
                "message": f"{user_ability} is not Prankster - normal interaction"
            }

        if has_dark:
            return {
                "ability_is_prankster": True,
                "target_is_dark": True,
                "move_blocked": True,
                "message": f"Dark-type is immune to Prankster-boosted {move_name}!"
            }

        return {
            "ability_is_prankster": True,
            "target_is_dark": False,
            "move_blocked": False,
            "priority_boosted": True,
            "message": f"{move_name} gets +1 priority from Prankster and will hit"
        }
