"""MCP tools for generating opponent-aware game plans.

Provides a single tool that takes your team + opponent team and produces
a comprehensive game plan with priority-aware lead recommendations,
turn 1 analysis, threat assessment, and bring-4 recommendations.
"""

import asyncio
from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.calc.team_matchup import (
    build_pokemon_profile, generate_full_game_plan, PokemonProfile,
)
from vgc_mcp_core.calc.priority import normalize_move_name
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.utils.errors import pokemon_not_found_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name

# Import helpers from damage_tools for Smogon data fetching
from .damage_tools import _get_common_spread, _normalize_smogon_name

# Module-level references
_smogon_client: Optional[SmogonStatsClient] = None


async def _build_profile(
    pokemon_name: str,
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    known_item: Optional[str] = None,
    known_ability: Optional[str] = None,
    existing_build: Optional[PokemonBuild] = None,
) -> PokemonProfile:
    """Build a PokemonProfile from PokeAPI + Smogon data.

    If existing_build is provided (from team_manager), uses that directly.
    Otherwise builds from Smogon's most common spread.
    """
    if existing_build:
        build = existing_build
        ability = known_ability or build.ability or ""
    else:
        # Fetch base data from PokeAPI
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
        except Exception:
            raise ValueError(f"Could not find Pokemon: {pokemon_name}")

        # Get Smogon spread data
        nature_str = "serious"
        evs_dict = {}
        item = known_item
        ability = known_ability or ""

        if smogon:
            smogon_spread = await _get_common_spread(pokemon_name)
            if smogon_spread:
                nature_str = smogon_spread.get("nature", "serious")
                evs_dict = smogon_spread.get("evs", {})
                if not item:
                    raw_item = smogon_spread.get("item")
                    item = _normalize_smogon_name(raw_item) if raw_item else None
                if not ability:
                    raw_ability = smogon_spread.get("ability")
                    ability = _normalize_smogon_name(raw_ability) if raw_ability else ""

        try:
            nature_enum = Nature(nature_str.lower())
        except ValueError:
            nature_enum = Nature.SERIOUS

        build = PokemonBuild(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=nature_enum,
            evs=EVSpread(
                hp=evs_dict.get("hp", 0),
                attack=evs_dict.get("attack", 0),
                defense=evs_dict.get("defense", 0),
                special_attack=evs_dict.get("special_attack", 0),
                special_defense=evs_dict.get("special_defense", 0),
                speed=evs_dict.get("speed", 0),
            ),
            item=item,
            ability=ability,
        )

    # Fetch top 4 moves from Smogon
    moves: list[Move] = []
    if smogon:
        try:
            usage = await smogon.get_pokemon_usage(pokemon_name)
            if usage and usage.get("moves"):
                top_move_names = list(usage["moves"].keys())[:4]
                # Also grab ability if not set
                if not ability and usage.get("abilities"):
                    raw_ability = list(usage["abilities"].keys())[0]
                    ability = _normalize_smogon_name(raw_ability)

                # Fetch move objects in parallel
                move_tasks = []
                for mn in top_move_names:
                    normalized = mn.lower().replace(" ", "-")
                    move_tasks.append(pokeapi.get_move(normalized, user_name=pokemon_name))

                results = await asyncio.gather(*move_tasks, return_exceptions=True)
                for result in results:
                    if isinstance(result, Move):
                        moves.append(result)
        except Exception:
            pass

    # Use build's move names as fallback
    if not moves and build.moves:
        for mn in build.moves:
            try:
                normalized = mn.lower().replace(" ", "-")
                move = await pokeapi.get_move(normalized, user_name=pokemon_name)
                moves.append(move)
            except Exception:
                pass

    return build_pokemon_profile(build, moves, ability, item_name=item or "")


def register_game_plan_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    team_manager: TeamManager,
    smogon: Optional[SmogonStatsClient] = None,
):
    """Register game plan MCP tools."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def generate_game_plan(
        opponent_team: list[str],
        your_team: Optional[list[str]] = None,
        format: str = "reg_h",
        known_items: Optional[dict[str, str]] = None,
        known_abilities: Optional[dict[str, str]] = None,
    ) -> dict:
        """Generate a comprehensive game plan against a specific opponent team.

        Produces an opponent-aware strategy with:
        - Lead recommendations considering Fake Out speed, Prankster priority, Intimidate
        - Turn 1 priority order (correctly handles Prankster +1, Fake Out +3, etc.)
        - Threat assessment ranked by danger to YOUR team
        - Win condition analysis
        - Speed control matchup (Tailwind, Trick Room, Prankster interactions)
        - Bring 4 / Leave 2 recommendations

        Args:
            opponent_team: 4-6 opponent Pokemon names (from team preview)
            your_team: Your 6 Pokemon names. If omitted, uses your loaded team.
            format: VGC format (default "reg_h")
            known_items: Optional items you've seen (e.g. {"tornadus": "covert-cloak"})
            known_abilities: Optional abilities you've identified (e.g. {"tornadus": "prankster"})

        Returns:
            Complete game plan with markdown_summary for display
        """
        known_items = known_items or {}
        known_abilities = known_abilities or {}

        # Resolve your team
        your_builds: list[PokemonBuild] = []
        your_names: list[str] = []

        if your_team:
            your_names = your_team
        else:
            # Try team_manager
            current_team = team_manager.get_current_team()
            if current_team:
                for slot in current_team.slots:
                    your_builds.append(slot.pokemon)
                    your_names.append(slot.pokemon.name)
            else:
                return {
                    "error": "No team provided. Either pass your_team names or load a team first.",
                    "hint": "Use import_showdown_paste to load your team, or pass your_team=['pokemon1', 'pokemon2', ...]"
                }

        if len(your_names) < 2:
            return {"error": "Your team needs at least 2 Pokemon."}
        if len(opponent_team) < 2:
            return {"error": "Opponent team needs at least 2 Pokemon."}

        # Build profiles for all Pokemon in parallel
        try:
            your_tasks = []
            for name in your_names:
                existing = next((b for b in your_builds if b.name.lower().replace(" ", "-") == name.lower().replace(" ", "-")), None)
                your_tasks.append(_build_profile(
                    name, pokeapi, smogon,
                    known_item=known_items.get(name.lower()),
                    known_ability=known_abilities.get(name.lower()),
                    existing_build=existing,
                ))

            their_tasks = []
            for name in opponent_team:
                their_tasks.append(_build_profile(
                    name, pokeapi, smogon,
                    known_item=known_items.get(name.lower()),
                    known_ability=known_abilities.get(name.lower()),
                ))

            all_results = await asyncio.gather(
                *your_tasks, *their_tasks, return_exceptions=True
            )

            # Split results
            your_profiles: list[PokemonProfile] = []
            their_profiles: list[PokemonProfile] = []
            errors = []

            for i, result in enumerate(all_results):
                if isinstance(result, Exception):
                    if i < len(your_names):
                        name = your_names[i]
                    else:
                        name = opponent_team[i - len(your_names)]
                    suggestions = suggest_pokemon_name(name)
                    errors.append(pokemon_not_found_error(name, suggestions))
                elif i < len(your_names):
                    your_profiles.append(result)
                else:
                    their_profiles.append(result)

            if errors:
                return {
                    "error": "Could not find some Pokemon",
                    "details": errors,
                }

            if len(your_profiles) < 2 or len(their_profiles) < 2:
                return {"error": "Need at least 2 valid Pokemon on each side."}

        except Exception as e:
            return api_error("game plan generation", str(e))

        # Generate the game plan
        plan = generate_full_game_plan(your_profiles, their_profiles)

        # Convert to dict for MCP response
        return {
            "your_team": plan.your_team,
            "opponent_team": plan.opponent_team,
            "overall_matchup": plan.overall_matchup,
            "overall_score": plan.overall_score,
            "lead_recommendations": [
                {
                    "pokemon_1": lr.pokemon_1,
                    "pokemon_2": lr.pokemon_2,
                    "score": lr.score,
                    "reasoning": lr.reasoning,
                    "fake_out_note": lr.fake_out_note,
                    "prankster_note": lr.prankster_note,
                }
                for lr in plan.lead_recommendations
            ],
            "turn_1_priority_order": [
                {
                    "pokemon": a.pokemon,
                    "move": a.move,
                    "priority": a.priority,
                    "speed": a.speed,
                    "side": a.side,
                    "note": a.note,
                }
                for a in plan.turn_1_priority_order
            ],
            "threat_assessment": [
                {
                    "pokemon_name": t.pokemon_name,
                    "threat_level": t.threat_level,
                    "reason": t.reason,
                    "your_answers": t.your_answers,
                    "is_priority_threat": t.is_priority_threat,
                }
                for t in plan.threat_assessment
            ],
            "win_condition": plan.win_condition,
            "win_condition_detail": plan.win_condition_detail,
            "speed_control_notes": plan.speed_control_notes,
            "bring_recommendation": {
                "bring": plan.bring_recommendation.bring,
                "leave_behind": plan.bring_recommendation.leave_behind,
                "reasoning": plan.bring_recommendation.reasoning,
            },
            "markdown_summary": plan.markdown_summary,
        }
