"""MCP tools for team vs team matchup analysis against tournament teams."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokepaste import PokePasteClient, PokePasteError
from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.formats.showdown import parse_showdown_team, parse_showdown_pokemon, ShowdownParseError
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers, get_type_effectiveness
from vgc_mcp_core.data.sample_teams import ALL_SAMPLE_TEAMS, SampleTeam
from vgc_mcp_core.calc.team_matchup import (
    full_team_matchup_analysis,
    TeamMatchupResult,
    score_1v1_matchup,
)
from vgc_mcp_core.models.pokemon import (
    PokemonBuild, BaseStats, Nature, EVSpread, IVSpread
)
from vgc_mcp_core.models.move import Move, MoveCategory


# Priority moves that Armor Tail / Queenly Majesty / Dazzling block
PRIORITY_MOVES = {
    # +4 protection moves (not usually attacking)
    # +3
    "fake-out",
    # +2
    "extreme-speed", "first-impression", "feint",
    # +1
    "aqua-jet", "bullet-punch", "ice-shard", "mach-punch",
    "quick-attack", "shadow-sneak", "sucker-punch", "water-shuriken",
    "accelerock", "jet-punch", "vacuum-wave", "grassy-glide",
    "thunderclap",  # Raging Bolt's +1 priority move
}

# Abilities that block priority moves
PRIORITY_BLOCKING_ABILITIES = {
    "armor-tail", "queenly-majesty", "dazzling"
}


def _parse_nature(nature_str: str) -> Nature:
    """Convert nature string to Nature enum."""
    try:
        return Nature[nature_str.upper()]
    except KeyError:
        return Nature.SERIOUS


def _create_move(move_name: str, pokemon_types: list[str], is_physical: bool) -> Move:
    """Create a Move object from a move name."""
    # Simplified move creation - estimate power based on common moves
    move_lower = move_name.lower().replace(" ", "-")

    # Common move power mappings
    move_powers = {
        # Physical moves
        "surging-strikes": 25,  # Multi-hit
        "wicked-blow": 75,
        "close-combat": 120,
        "collision-course": 100,
        "flare-blitz": 120,
        "stone-edge": 100,
        "earthquake": 100,
        "earth-power": 90,
        "wood-hammer": 120,
        "grassy-glide": 55,
        "knock-off": 65,
        "u-turn": 70,
        "aqua-jet": 40,
        "ice-shard": 40,
        "fake-out": 40,
        "extreme-speed": 80,
        "glacial-lance": 120,
        "sacred-sword": 90,
        "ice-spinner": 80,
        "outrage": 120,
        "high-horsepower": 95,
        "crunch": 80,
        "wild-charge": 90,
        "drain-punch": 75,
        "heavy-slam": 0,  # Variable
        "sucker-punch": 70,
        # Special moves
        "moonblast": 95,
        "shadow-ball": 80,
        "thunderbolt": 90,
        "thunder": 110,
        "mystical-fire": 75,
        "dazzling-gleam": 80,
        "draco-meteor": 130,
        "electro-drift": 100,
        "volt-switch": 70,
        "water-spout": 150,
        "origin-pulse": 110,
        "ice-beam": 90,
        "heat-wave": 95,
        "dark-pulse": 80,
        "overheat": 130,
        "psychic": 90,
        "sludge-bomb": 90,
        "hyper-voice": 90,
        "bleakwind-storm": 100,
        "pollen-puff": 90,
        "tera-blast": 80,
    }

    # Determine category and type (simplified)
    power = move_powers.get(move_lower, 80)

    # Guess move type from name
    type_keywords = {
        "fire": ["flare", "fire", "heat", "mystical-fire", "overheat"],
        "water": ["water", "aqua", "surging", "origin-pulse"],
        "grass": ["grass", "wood", "grassy"],
        "electric": ["thunder", "electro", "volt", "wild-charge"],
        "ice": ["ice", "glacial", "blizzard"],
        "fighting": ["close-combat", "sacred-sword", "collision", "drain-punch"],
        "dark": ["wicked", "knock", "crunch", "dark-pulse", "sucker"],
        "psychic": ["psychic", "psych"],
        "ghost": ["shadow"],
        "fairy": ["moonblast", "dazzling", "play"],
        "ground": ["earthquake", "earth", "high-horsepower"],
        "rock": ["stone", "rock"],
        "steel": ["iron", "heavy-slam"],
        "poison": ["sludge", "poison"],
        "flying": ["bleakwind", "hurricane"],
        "dragon": ["draco", "outrage", "dragon"],
        "bug": ["u-turn", "pollen"],
        "normal": ["hyper-voice", "extreme-speed", "fake-out", "tera-blast"],
    }

    move_type = "Normal"
    for ptype, keywords in type_keywords.items():
        if any(kw in move_lower for kw in keywords):
            move_type = ptype.capitalize()
            break

    # Determine category based on move name patterns
    physical_keywords = ["strike", "blow", "combat", "collision", "blitz", "edge",
                        "quake", "hammer", "glide", "knock", "turn", "jet", "shard",
                        "lance", "sword", "spinner", "crunch", "charge", "punch", "slam",
                        "outrage", "horsepower", "sucker"]
    is_physical_move = any(kw in move_lower for kw in physical_keywords)
    category = MoveCategory.PHYSICAL if is_physical_move else MoveCategory.SPECIAL

    return Move(
        name=move_name,
        type=move_type,
        category=category,
        power=power,
        accuracy=100
    )


async def _parsed_to_build(parsed_mon, pokeapi: PokeAPIClient) -> Optional[PokemonBuild]:
    """Convert a ParsedPokemon to a PokemonBuild."""
    try:
        # Get base stats from PokeAPI
        base_stats = await pokeapi.get_base_stats(parsed_mon.species)
        types = await pokeapi.get_pokemon_types(parsed_mon.species)

        # Convert EVs dict to EVSpread
        evs = EVSpread(
            hp=parsed_mon.evs.get("hp", 0),
            attack=parsed_mon.evs.get("atk", 0),
            defense=parsed_mon.evs.get("def", 0),
            special_attack=parsed_mon.evs.get("spa", 0),
            special_defense=parsed_mon.evs.get("spd", 0),
            speed=parsed_mon.evs.get("spe", 0)
        )

        # Convert IVs dict to IVSpread
        ivs = IVSpread(
            hp=parsed_mon.ivs.get("hp", 31),
            attack=parsed_mon.ivs.get("atk", 31),
            defense=parsed_mon.ivs.get("def", 31),
            special_attack=parsed_mon.ivs.get("spa", 31),
            special_defense=parsed_mon.ivs.get("spd", 31),
            speed=parsed_mon.ivs.get("spe", 31)
        )

        nature = _parse_nature(parsed_mon.nature)

        return PokemonBuild(
            name=parsed_mon.species,
            base_stats=base_stats,
            nature=nature,
            evs=evs,
            ivs=ivs,
            types=types,
            level=parsed_mon.level or 50,
            item=parsed_mon.item,
            ability=parsed_mon.ability,
            tera_type=parsed_mon.tera_type,
            moves=parsed_mon.moves
        )
    except Exception as e:
        return None


def _format_matchup_matrix(result: TeamMatchupResult) -> str:
    """Format the 6x6 matchup matrix as a markdown table."""
    lines = []

    # Header row
    header = "| |"
    for name in result.opponent_pokemon_names:
        # Truncate long names
        short_name = name[:8] if len(name) > 8 else name
        header += f" {short_name} |"
    lines.append(header)

    # Separator
    sep = "|---|" + "|".join(":---:" for _ in result.opponent_pokemon_names) + "|"
    lines.append(sep)

    # Data rows
    for i, your_name in enumerate(result.your_pokemon_names):
        short_name = your_name[:8] if len(your_name) > 8 else your_name
        row = f"| **{short_name}** |"
        for j, score in enumerate(result.matchup_matrix[i]):
            if score > 15:
                row += f" +{score:.0f} |"
            elif score < -15:
                row += f" {score:.0f} |"
            else:
                row += f" {score:.0f} |"
        lines.append(row)

    return "\n".join(lines)


def _format_threats(threats) -> str:
    """Format key threats as a markdown table."""
    lines = [
        "| Threat | Danger | Reason | Your Answer | Damage |",
        "|--------|:------:|--------|-------------|--------|"
    ]

    for t in threats:
        danger_emoji = {"HIGH": "🔴", "MEDIUM": "🟡", "LOW": "🟢"}.get(t.danger_level, "")
        lines.append(
            f"| {t.pokemon_name} | {danger_emoji} {t.danger_level} | {t.reason} | "
            f"{t.your_best_answer} | {t.answer_damage} |"
        )

    return "\n".join(lines)


def _format_leads(leads) -> str:
    """Format lead recommendations."""
    lines = []
    for lead in leads:
        if lead.recommended:
            lines.append(f"✅ **{lead.your_lead1} + {lead.your_lead2}** (Score: {lead.advantage_score:+.0f})")
            lines.append(f"   {lead.reasoning}")
        else:
            lines.append(f"• {lead.your_lead1} + {lead.your_lead2} (Score: {lead.advantage_score:+.0f})")
    return "\n".join(lines)


def _format_speed_comparison(speed_data: dict) -> str:
    """Format speed tier comparison."""
    lines = []
    for mon_name, data in speed_data.items():
        outspeeds_count = len(data["outspeeds"])
        underspeeds_count = len(data["underspeeds"])
        lines.append(f"**{mon_name}** (Speed: {data['speed']})")
        if data["outspeeds"]:
            lines.append(f"  • Outspeeds: {', '.join(data['outspeeds'][:3])}" +
                        (f" +{len(data['outspeeds'])-3} more" if len(data["outspeeds"]) > 3 else ""))
        if data["underspeeds"]:
            lines.append(f"  • Outsped by: {', '.join(data['underspeeds'][:3])}" +
                        (f" +{len(data['underspeeds'])-3} more" if len(data["underspeeds"]) > 3 else ""))
    return "\n".join(lines)


def _format_full_result(result: TeamMatchupResult) -> str:
    """Format the full matchup result as markdown."""
    lines = []

    # Header
    lines.append(f"## {result.your_team_name} vs {result.opponent_team_name}")
    lines.append("")

    # Overall advantage
    if result.overall_advantage >= 60:
        verdict = "✅ FAVORABLE"
    elif result.overall_advantage >= 55:
        verdict = "👍 SLIGHT ADVANTAGE"
    elif result.overall_advantage >= 45:
        verdict = "⚖️ EVEN"
    elif result.overall_advantage >= 40:
        verdict = "👎 SLIGHT DISADVANTAGE"
    else:
        verdict = "❌ UNFAVORABLE"

    lines.append(f"### Overall: {result.overall_advantage:.0f}% ({verdict})")
    lines.append("")

    # Matchup matrix
    lines.append("### Matchup Matrix")
    lines.append("*(Positive = your Pokemon favored)*")
    lines.append("")
    lines.append(_format_matchup_matrix(result))
    lines.append("")

    # Key threats
    lines.append("### Key Threats")
    lines.append(_format_threats(result.key_threats))
    lines.append("")

    # Lead recommendations
    lines.append("### Recommended Leads")
    lines.append(_format_leads(result.recommended_leads))
    lines.append("")

    # Speed comparison (condensed)
    lines.append("### Speed Tiers")
    lines.append(_format_speed_comparison(result.speed_advantages))
    lines.append("")

    # Game plan
    lines.append("### Game Plan")
    lines.append(result.game_plan)

    return "\n".join(lines)


def register_tournament_tools(mcp: FastMCP, pokepaste: PokePasteClient, pokeapi: PokeAPIClient, smogon: SmogonStatsClient = None):
    """Register tournament matchup analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_team_vs_meta(
        pokepaste_url: str,
        top_n: int = 5
    ) -> dict:
        """
        Analyze your team against top tournament meta teams.

        Provides comprehensive matchup analysis including:
        - Overall advantage percentage vs each meta team
        - 6x6 matchup matrix showing who beats who
        - Key threats and your best answers
        - Recommended leads
        - Speed tier comparison
        - Game plan summary

        Args:
            pokepaste_url: PokePaste URL of your team (e.g., "https://pokepast.es/abc123")
            top_n: Number of meta teams to analyze against (default 5)

        Returns:
            Full matchup report for each meta team
        """
        try:
            # Fetch and parse user's team
            raw_paste = await pokepaste.get_paste(pokepaste_url)
            parsed_team = parse_showdown_team(raw_paste)

            if not parsed_team:
                return {"error": "Could not parse any Pokemon from the paste"}

            # Convert to PokemonBuild objects
            user_team = []
            for parsed_mon in parsed_team:
                build = await _parsed_to_build(parsed_mon, pokeapi)
                if build:
                    user_team.append(build)

            if len(user_team) < 4:
                return {
                    "error": f"Only parsed {len(user_team)} Pokemon. Need at least 4 for matchup analysis.",
                    "parsed_pokemon": [p.name for p in user_team]
                }

            # Analyze against each sample team
            results = []
            for sample_team in ALL_SAMPLE_TEAMS[:top_n]:
                # Parse the sample team's paste
                sample_parsed = parse_showdown_team(sample_team.paste)
                opponent_team = []
                for parsed_mon in sample_parsed:
                    build = await _parsed_to_build(parsed_mon, pokeapi)
                    if build:
                        opponent_team.append(build)

                if len(opponent_team) < 4:
                    continue

                # Run matchup analysis
                matchup_result = full_team_matchup_analysis(
                    user_team,
                    opponent_team,
                    team1_name="Your Team",
                    team2_name=f"{sample_team.name} ({sample_team.archetype})"
                )

                results.append({
                    "opponent_name": sample_team.name,
                    "archetype": sample_team.archetype,
                    "regulation": sample_team.regulation,
                    "overall_advantage": matchup_result.overall_advantage,
                    "formatted_report": _format_full_result(matchup_result)
                })

            # Sort by most challenging (lowest advantage first)
            results.sort(key=lambda r: r["overall_advantage"])

            # Summary
            avg_advantage = sum(r["overall_advantage"] for r in results) / len(results) if results else 50

            return {
                "success": True,
                "your_team": [p.name for p in user_team],
                "teams_analyzed": len(results),
                "average_advantage": round(avg_advantage, 1),
                "summary": f"Your team has an average {avg_advantage:.0f}% advantage across {len(results)} meta teams.",
                "worst_matchup": results[0]["opponent_name"] if results else None,
                "best_matchup": results[-1]["opponent_name"] if results else None,
                "matchup_reports": results
            }

        except PokePasteError as e:
            return {"error": f"Failed to fetch paste: {e}"}
        except ShowdownParseError as e:
            return {"error": f"Failed to parse paste: {e}"}
        except Exception as e:
            return {"error": f"Analysis failed: {e}"}

    @mcp.tool()
    async def compare_two_teams(
        team1_url: str,
        team2_url: str
    ) -> dict:
        """
        Compare two teams head-to-head with detailed matchup analysis.

        Analyzes both teams against each other, showing:
        - Who has the overall advantage
        - Individual Pokemon matchups (6x6 matrix)
        - Key threats from each side
        - Best lead combinations
        - Recommended game plan

        Args:
            team1_url: PokePaste URL for first team
            team2_url: PokePaste URL for second team

        Returns:
            Detailed head-to-head matchup report
        """
        try:
            # Fetch and parse both teams
            raw1 = await pokepaste.get_paste(team1_url)
            raw2 = await pokepaste.get_paste(team2_url)

            parsed1 = parse_showdown_team(raw1)
            parsed2 = parse_showdown_team(raw2)

            if not parsed1 or not parsed2:
                return {"error": "Could not parse one or both teams"}

            # Convert to PokemonBuild
            team1 = []
            for p in parsed1:
                build = await _parsed_to_build(p, pokeapi)
                if build:
                    team1.append(build)

            team2 = []
            for p in parsed2:
                build = await _parsed_to_build(p, pokeapi)
                if build:
                    team2.append(build)

            if len(team1) < 4 or len(team2) < 4:
                return {"error": "Both teams need at least 4 Pokemon for analysis"}

            # Run analysis
            result = full_team_matchup_analysis(
                team1, team2,
                team1_name="Team 1",
                team2_name="Team 2"
            )

            return {
                "success": True,
                "team1": [p.name for p in team1],
                "team2": [p.name for p in team2],
                "team1_advantage": result.overall_advantage,
                "team2_advantage": 100 - result.overall_advantage,
                "formatted_report": _format_full_result(result)
            }

        except Exception as e:
            return {"error": f"Comparison failed: {e}"}

    @mcp.tool()
    async def get_meta_teams() -> dict:
        """
        List available tournament meta teams for matchup analysis.

        Returns:
            List of meta teams with names, archetypes, and Pokemon
        """
        teams = []
        for team in ALL_SAMPLE_TEAMS:
            teams.append({
                "name": team.name,
                "archetype": team.archetype,
                "pokemon": team.pokemon,
                "regulation": team.regulation,
                "difficulty": team.difficulty,
                "description": team.description,
                "strengths": team.strengths,
                "weaknesses": team.weaknesses
            })

        return {
            "total_teams": len(teams),
            "archetypes": list(set(t["archetype"] for t in teams)),
            "teams": teams
        }

    @mcp.tool()
    async def analyze_vs_specific_team(
        pokepaste_url: str,
        opponent_archetype: str
    ) -> dict:
        """
        Analyze your team against a specific meta archetype.

        Args:
            pokepaste_url: PokePaste URL of your team
            opponent_archetype: Archetype to analyze against (rain, sun, trick_room, goodstuffs, hyper_offense)

        Returns:
            Detailed matchup analysis against that archetype
        """
        try:
            # Find matching archetype
            matching_team = None
            for team in ALL_SAMPLE_TEAMS:
                if team.archetype.lower() == opponent_archetype.lower():
                    matching_team = team
                    break

            if not matching_team:
                available = list(set(t.archetype for t in ALL_SAMPLE_TEAMS))
                return {
                    "error": f"Unknown archetype: {opponent_archetype}",
                    "available_archetypes": available
                }

            # Parse user team
            raw_paste = await pokepaste.get_paste(pokepaste_url)
            parsed = parse_showdown_team(raw_paste)

            if not parsed:
                return {"error": "Could not parse your team"}

            user_team = []
            for p in parsed:
                build = await _parsed_to_build(p, pokeapi)
                if build:
                    user_team.append(build)

            # Parse opponent team
            opponent_parsed = parse_showdown_team(matching_team.paste)
            opponent_team = []
            for p in opponent_parsed:
                build = await _parsed_to_build(p, pokeapi)
                if build:
                    opponent_team.append(build)

            # Run analysis
            result = full_team_matchup_analysis(
                user_team, opponent_team,
                team1_name="Your Team",
                team2_name=f"{matching_team.name} ({matching_team.archetype})"
            )

            return {
                "success": True,
                "your_team": [p.name for p in user_team],
                "opponent": {
                    "name": matching_team.name,
                    "archetype": matching_team.archetype,
                    "pokemon": matching_team.pokemon,
                    "strengths": matching_team.strengths,
                    "weaknesses": matching_team.weaknesses
                },
                "your_advantage": result.overall_advantage,
                "formatted_report": _format_full_result(result)
            }

        except Exception as e:
            return {"error": f"Analysis failed: {e}"}

    @mcp.tool()
    async def analyze_paste_bulk(
        pokemon_paste: str,
        top_threats: int = 12
    ) -> dict:
        """
        Analyze what attacks a Pokemon survives based on its paste.

        Paste a Pokemon in Showdown format and see what common
        meta attacks it can survive with its current spread.

        Example paste:
        ```
        Farigiraf @ Throat Spray
        Ability: Armor Tail
        EVs: 236 HP / 52 Def / 140 SpD
        Modest Nature
        - Trick Room
        ```

        Args:
            pokemon_paste: Pokemon in Showdown paste format (raw text, not URL)
            top_threats: Number of top meta Pokemon to check (default 12)

        Returns:
            Bulk analysis with survival benchmarks against meta threats
        """
        if smogon is None:
            return {"error": "Smogon client not available for meta threat analysis"}

        try:
            # Parse the paste
            parsed = parse_showdown_pokemon(pokemon_paste)
            if not parsed:
                return {"error": "Could not parse Pokemon paste"}

            # Get base stats and types
            base_stats = await pokeapi.get_base_stats(parsed.species)
            pokemon_types = await pokeapi.get_pokemon_types(parsed.species)

            # Build the Pokemon
            evs = EVSpread(
                hp=parsed.evs.get("hp", 0),
                attack=parsed.evs.get("atk", 0),
                defense=parsed.evs.get("def", 0),
                special_attack=parsed.evs.get("spa", 0),
                special_defense=parsed.evs.get("spd", 0),
                speed=parsed.evs.get("spe", 0)
            )
            ivs = IVSpread(
                hp=parsed.ivs.get("hp", 31),
                attack=parsed.ivs.get("atk", 31),
                defense=parsed.ivs.get("def", 31),
                special_attack=parsed.ivs.get("spa", 31),
                special_defense=parsed.ivs.get("spd", 31),
                speed=parsed.ivs.get("spe", 31)
            )
            nature = _parse_nature(parsed.nature)

            your_pokemon = PokemonBuild(
                name=parsed.species,
                base_stats=base_stats,
                nature=nature,
                evs=evs,
                ivs=ivs,
                types=pokemon_types,
                level=parsed.level or 50,
                item=parsed.item,
                ability=parsed.ability
            )

            your_stats = calculate_all_stats(your_pokemon)
            final_hp = your_stats["hp"]
            final_def = your_stats["defense"]
            final_spd = your_stats["special_defense"]

            # Calculate bulk products
            physical_bulk = final_hp * final_def
            special_bulk = final_hp * final_spd

            # Get meta threats from Smogon
            usage_stats = await smogon.get_usage_stats()
            usage_data = usage_stats.get("data", {})

            sorted_pokemon = sorted(
                usage_data.items(),
                key=lambda x: x[1].get("usage", 0),
                reverse=True
            )[:top_threats]

            # Check if defender has priority-blocking ability
            defender_ability = (parsed.ability or "").lower().replace(" ", "-")
            blocks_priority = defender_ability in PRIORITY_BLOCKING_ABILITIES

            # Analyze damage from each threat
            survives_physical = []
            survives_special = []
            does_not_survive = []
            blocked_moves = []  # Moves blocked by ability
            modifiers = DamageModifiers(is_doubles=True)

            for threat_name, threat_usage_data in sorted_pokemon:
                # Skip if it's the same Pokemon
                if threat_name.lower() == parsed.species.lower():
                    continue

                try:
                    threat_base_stats = await pokeapi.get_base_stats(threat_name)
                    threat_types = await pokeapi.get_pokemon_types(threat_name)
                except Exception:
                    continue

                # Get threat's common spread and moves from Smogon
                threat_usage = await smogon.get_pokemon_usage(threat_name)
                if not threat_usage:
                    continue

                # Get threat's spread
                threat_spread = None
                threat_spread_str = ""
                if threat_usage.get("spreads"):
                    top_spread = threat_usage["spreads"][0]
                    try:
                        threat_nature = Nature(top_spread["nature"].lower())
                        threat_evs = EVSpread(
                            hp=top_spread["evs"].get("hp", 0),
                            attack=top_spread["evs"].get("attack", 0),
                            defense=top_spread["evs"].get("defense", 0),
                            special_attack=top_spread["evs"].get("special_attack", 0),
                            special_defense=top_spread["evs"].get("special_defense", 0),
                            speed=top_spread["evs"].get("speed", 0)
                        )
                        threat_spread = {"nature": threat_nature, "evs": threat_evs}
                        # Build spread string for output
                        threat_spread_str = threat_nature.name.title()
                    except Exception:
                        threat_nature = Nature.SERIOUS
                        threat_evs = EVSpread()
                        threat_spread_str = "Neutral"
                else:
                    threat_nature = Nature.SERIOUS
                    threat_evs = EVSpread()
                    threat_spread_str = "Neutral"

                threat_pokemon = PokemonBuild(
                    name=threat_name,
                    base_stats=threat_base_stats,
                    nature=threat_nature if threat_spread else Nature.SERIOUS,
                    evs=threat_evs if threat_spread else EVSpread(),
                    types=threat_types,
                    level=50
                )

                # Get threat's top attacking moves
                threat_moves_raw = list(threat_usage.get("moves", {}).items())[:4]

                for move_name, move_usage in threat_moves_raw:
                    try:
                        move = await pokeapi.get_move(move_name, threat_name)
                        if not move or not move.power or move.power == 0:
                            continue

                        # Check if this is a priority move blocked by ability
                        move_normalized = move.name.lower().replace(" ", "-")
                        if blocks_priority and move_normalized in PRIORITY_MOVES:
                            blocked_moves.append({
                                "attacker": threat_name,
                                "move": move.name,
                                "reason": f"Priority blocked by {parsed.ability}"
                            })
                            continue

                        # Calculate damage
                        result = calculate_damage(threat_pokemon, your_pokemon, move, modifiers)

                        # Format the attacker description with full spread (all non-zero EVs)
                        is_physical = move.category == MoveCategory.PHYSICAL

                        # Build full EV string for attacker showing all non-zero EVs
                        threat_ev_parts = []
                        if threat_evs.hp: threat_ev_parts.append(f"{threat_evs.hp} HP")
                        if threat_evs.attack: threat_ev_parts.append(f"{threat_evs.attack} Atk")
                        if threat_evs.defense: threat_ev_parts.append(f"{threat_evs.defense} Def")
                        if threat_evs.special_attack: threat_ev_parts.append(f"{threat_evs.special_attack} SpA")
                        if threat_evs.special_defense: threat_ev_parts.append(f"{threat_evs.special_defense} SpD")
                        if threat_evs.speed: threat_ev_parts.append(f"{threat_evs.speed} Spe")
                        threat_ev_str = " / ".join(threat_ev_parts) if threat_ev_parts else "No EVs"

                        damage_range = f"{result.min_percent:.0f}-{result.max_percent:.0f}%"

                        entry = {
                            "attacker": threat_name,
                            "spread": f"{threat_spread_str} {threat_ev_str}",
                            "move": move.name,
                            "damage": damage_range,
                            "min_pct": result.min_percent,
                            "max_pct": result.max_percent
                        }

                        if result.max_percent < 100:
                            # Survives
                            if result.max_percent >= 87.5:
                                entry["result"] = "Survives (close)"
                            else:
                                entry["result"] = "Survives"

                            if is_physical:
                                survives_physical.append(entry)
                            else:
                                survives_special.append(entry)
                        elif result.min_percent >= 100:
                            # OHKO guaranteed
                            entry["result"] = "OHKO"
                            entry["notes"] = "Guaranteed KO"
                            does_not_survive.append(entry)
                        else:
                            # Roll-dependent
                            rolls_that_ko = sum(1 for r in result.damage_rolls if r >= final_hp)
                            ko_chance = (rolls_that_ko / 16) * 100
                            entry["result"] = f"{ko_chance:.0f}% OHKO"

                            if ko_chance > 50:
                                entry["notes"] = "Likely KO"
                                does_not_survive.append(entry)
                            else:
                                entry["result"] = f"Survives ({100-ko_chance:.0f}%)"
                                if is_physical:
                                    survives_physical.append(entry)
                                else:
                                    survives_special.append(entry)

                    except Exception:
                        continue

            # Sort by damage (most dangerous first for does_not_survive)
            survives_physical.sort(key=lambda x: x["max_pct"], reverse=True)
            survives_special.sort(key=lambda x: x["max_pct"], reverse=True)
            does_not_survive.sort(key=lambda x: x["min_pct"], reverse=True)

            # Format the report
            lines = []
            lines.append(f"## {parsed.species} Bulk Analysis")
            lines.append("")

            # Your spread summary - show ALL non-zero EVs
            ev_parts = []
            if evs.hp: ev_parts.append(f"{evs.hp} HP")
            if evs.attack: ev_parts.append(f"{evs.attack} Atk")
            if evs.defense: ev_parts.append(f"{evs.defense} Def")
            if evs.special_attack: ev_parts.append(f"{evs.special_attack} SpA")
            if evs.special_defense: ev_parts.append(f"{evs.special_defense} SpD")
            if evs.speed: ev_parts.append(f"{evs.speed} Spe")
            ev_str = " / ".join(ev_parts) if ev_parts else "No EVs"
            ability_str = f" | {parsed.ability}" if parsed.ability else ""
            item_str = f" | {parsed.item}" if parsed.item else ""
            lines.append(f"**Your Spread:** {nature.name.title()} {ev_str}{ability_str}{item_str}")
            lines.append("")

            # Stats table
            lines.append("### Stats")
            lines.append("| Stat | Base | EVs | Final |")
            lines.append("|------|------|-----|-------|")
            lines.append(f"| HP   | {base_stats.hp} | {evs.hp} | {final_hp} |")
            lines.append(f"| Def  | {base_stats.defense} | {evs.defense} | {final_def} |")
            lines.append(f"| SpD  | {base_stats.special_defense} | {evs.special_defense} | {final_spd} |")
            lines.append("")
            lines.append(f"**Physical Bulk:** {physical_bulk:,} (HP x Def)")
            lines.append(f"**Special Bulk:** {special_bulk:,} (HP x SpD)")
            lines.append("")

            # Survives Physical
            if survives_physical:
                lines.append("### Survives (Physical)")
                lines.append("| Attacker | Their Spread | Move | Damage | Result |")
                lines.append("|----------|--------------|------|--------|--------|")
                for entry in survives_physical[:8]:
                    lines.append(f"| {entry['attacker']} | {entry['spread']} | {entry['move']} | {entry['damage']} | {entry['result']} |")
                lines.append("")

            # Survives Special
            if survives_special:
                lines.append("### Survives (Special)")
                lines.append("| Attacker | Their Spread | Move | Damage | Result |")
                lines.append("|----------|--------------|------|--------|--------|")
                for entry in survives_special[:8]:
                    lines.append(f"| {entry['attacker']} | {entry['spread']} | {entry['move']} | {entry['damage']} | {entry['result']} |")
                lines.append("")

            # Does NOT survive
            if does_not_survive:
                lines.append("### Does NOT Survive")
                lines.append("| Attacker | Their Spread | Move | Damage | Result |")
                lines.append("|----------|--------------|------|--------|--------|")
                for entry in does_not_survive[:8]:
                    lines.append(f"| {entry['attacker']} | {entry['spread']} | {entry['move']} | {entry['damage']} | {entry['result']} |")
                lines.append("")

            # Blocked by Ability
            if blocked_moves:
                lines.append(f"### Blocked by {parsed.ability}")
                for blocked in blocked_moves:
                    lines.append(f"- {blocked['move']} ({blocked['attacker']}) - Priority blocked")
                lines.append("")

            return {
                "success": True,
                "pokemon": parsed.species,
                "nature": parsed.nature,
                "evs": {
                    "hp": evs.hp,
                    "def": evs.defense,
                    "spd": evs.special_defense
                },
                "final_stats": {
                    "hp": final_hp,
                    "defense": final_def,
                    "special_defense": final_spd
                },
                "physical_bulk": physical_bulk,
                "special_bulk": special_bulk,
                "survives_physical_count": len(survives_physical),
                "survives_special_count": len(survives_special),
                "does_not_survive_count": len(does_not_survive),
                "formatted_report": "\n".join(lines)
            }

        except ShowdownParseError as e:
            return {"error": f"Failed to parse paste: {e}"}
        except Exception as e:
            return {"error": f"Bulk analysis failed: {e}"}
