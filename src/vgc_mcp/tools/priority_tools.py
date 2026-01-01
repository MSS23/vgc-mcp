"""MCP tools for priority move and turn order analysis."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.calc.priority import (
    get_move_priority,
    determine_turn_order,
    get_priority_moves_by_bracket,
    categorize_priority_move,
    find_team_priority_moves,
    analyze_fake_out_matchup,
    get_priority_bracket_summary,
    check_prankster_immunity,
    PRIORITY_MOVES,
    FAKE_OUT_POKEMON,
    PRANKSTER_POKEMON,
)


def register_priority_tools(mcp: FastMCP, team_manager):
    """Register priority move analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_turn_order(
        pokemon1_name: str,
        pokemon1_move: str,
        pokemon1_speed: int,
        pokemon2_name: str,
        pokemon2_move: str,
        pokemon2_speed: int,
        pokemon1_ability: Optional[str] = None,
        pokemon2_ability: Optional[str] = None,
        trick_room: bool = False,
        terrain: Optional[str] = None
    ) -> dict:
        """
        Determine which Pokemon moves first considering priority.

        Accounts for:
        - Move priority brackets (+5 to -7)
        - Speed stats
        - Trick Room (reverses speed order)
        - Prankster ability (+1 to status)
        - Terrain effects (Grassy Glide)

        Args:
            pokemon1_name: First Pokemon's name
            pokemon1_move: Move being used by first Pokemon
            pokemon1_speed: First Pokemon's speed stat
            pokemon2_name: Second Pokemon's name
            pokemon2_move: Move being used by second Pokemon
            pokemon2_speed: Second Pokemon's speed stat
            pokemon1_ability: First Pokemon's ability (for Prankster, etc.)
            pokemon2_ability: Second Pokemon's ability
            trick_room: Whether Trick Room is active
            terrain: Active terrain (grassy, electric, psychic, misty)

        Returns:
            Turn order analysis with reasoning
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

    @mcp.tool()
    async def get_move_priority_info(move_name: str) -> dict:
        """
        Get priority information for a specific move.

        Args:
            move_name: Name of the move

        Returns:
            Priority value and category
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

    @mcp.tool()
    async def list_team_priority_moves() -> dict:
        """
        List all priority moves available on the current team.

        Returns:
            Priority moves for each team member
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

    @mcp.tool()
    async def check_fake_out_interaction(
        your_speed: int,
        opponent_pokemon: str,
        opponent_speed: int,
        trick_room: bool = False
    ) -> dict:
        """
        Analyze Fake Out speed interaction with an opponent.

        Fake Out is a +3 priority move that only works on turn 1.
        Speed determines who Fake Outs first if both have it.

        Args:
            your_speed: Your Fake Out user's speed
            opponent_pokemon: Opponent's Pokemon name
            opponent_speed: Opponent's speed (if they have Fake Out)
            trick_room: Whether Trick Room is active

        Returns:
            Fake Out interaction analysis
        """
        return analyze_fake_out_matchup(your_speed, opponent_pokemon, opponent_speed, trick_room)

    @mcp.tool()
    async def list_priority_bracket(bracket: int) -> dict:
        """
        List all moves at a specific priority bracket.

        Common brackets:
        - +5: Helping Hand
        - +4: Protect, Detect
        - +3: Fake Out, Quick Guard
        - +2: Extreme Speed, First Impression
        - +1: Aqua Jet, Bullet Punch, Mach Punch, etc.
        - 0: Most moves
        - Negative: Trick Room (-7), Counter (-6), etc.

        Args:
            bracket: Priority bracket (-7 to +5)

        Returns:
            List of moves at that priority
        """
        moves = get_priority_moves_by_bracket(bracket)

        return {
            "bracket": bracket,
            "bracket_display": f"+{bracket}" if bracket > 0 else str(bracket),
            "moves": [move.replace("-", " ").title() for move in moves],
            "count": len(moves),
            "message": f"Found {len(moves)} moves at priority {bracket}"
        }

    @mcp.tool()
    async def get_priority_overview() -> dict:
        """
        Get a complete overview of all priority brackets and moves.

        Useful for understanding the full priority system.

        Returns:
            All priority brackets with their moves
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

    @mcp.tool()
    async def find_priority_threats() -> dict:
        """
        Identify common priority move threats in the VGC meta.

        Returns:
            List of common priority threats and their moves
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

    @mcp.tool()
    async def check_prankster_interaction(
        target_types: list[str],
        move_name: str,
        user_ability: str
    ) -> dict:
        """
        Check if a Prankster-boosted move will affect the target.

        Dark-type Pokemon are immune to moves that gained priority
        from Prankster.

        Args:
            target_types: Types of the target Pokemon
            move_name: Name of the move being used
            user_ability: Ability of the user (should be Prankster)

        Returns:
            Whether the move will work
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
