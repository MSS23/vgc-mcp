"""MCP tools for meta threat analysis.

This module provides tools to analyze a Pokemon's spread against
the top threats in the metagame, including damage calculations
and matchup assessments.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.calc.stats import calculate_all_stats
from vgc_mcp_core.calc.speed_probability import calculate_speed_stat
from vgc_mcp_core.calc.meta_threats import (
    analyze_single_threat,
    generate_spread_suggestions,
    create_empty_threat_report,
    MetaThreatReport,
    ThreatDamageResult
)
from vgc_mcp_core.models.pokemon import PokemonBuild, BaseStats, EVSpread, Nature
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50


def _format_matchup_row(r: ThreatDamageResult) -> dict:
    """Format a single threat matchup as a table row with KO probabilities."""
    your_dmg = r.your_damage_to_threat
    their_dmg = r.threat_damage_to_you

    # Format damage strings
    your_dmg_str = (
        f"{your_dmg.get('min_percent', 0):.0f}-{your_dmg.get('max_percent', 0):.0f}%"
        if your_dmg.get('max_percent', 0) > 0
        else "N/A"
    )
    their_dmg_str = (
        f"{their_dmg.get('min_percent', 0):.0f}-{their_dmg.get('max_percent', 0):.0f}%"
        if their_dmg.get('max_percent', 0) > 0
        else "N/A"
    )

    # Get KO verdicts with probabilities
    your_ko = your_dmg.get("ko_chance", "N/A")
    their_ko = their_dmg.get("ko_chance", "N/A")

    # Speed indicator
    if "You outspeed" in r.speed_comparison:
        speed = "faster"
    elif "They outspeed" in r.speed_comparison:
        speed = "slower"
    else:
        speed = "tie"

    return {
        "threat": r.threat_name,
        "usage": f"{r.threat_usage_pct:.1f}%",
        "your_dmg": your_dmg_str,
        "your_ko": your_ko,
        "their_dmg": their_dmg_str,
        "their_ko": their_ko,
        "speed": speed,
        "verdict": r.matchup_verdict,
        # Detailed data
        "your_damage_detail": {
            "range": your_dmg_str,
            "move": your_dmg.get("move", "N/A"),
            "ko_verdict": your_ko,
            "ohko_chance": your_dmg.get("ohko_chance", 0),
            "2hko_chance": your_dmg.get("twohko_chance", 0),
            "3hko_chance": your_dmg.get("threehko_chance", 0),
        },
        "their_damage_detail": {
            "range": their_dmg_str,
            "move": their_dmg.get("move", "N/A"),
            "ko_verdict": their_ko,
            "ohko_chance": their_dmg.get("ohko_chance", 0),
            "2hko_chance": their_dmg.get("twohko_chance", 0),
            "3hko_chance": their_dmg.get("threehko_chance", 0),
        },
        "threat_spread": r.threat_spread,
    }


def _format_results_table(threat_results: list[ThreatDamageResult]) -> dict:
    """Format all threat results into a structured table format."""
    rows = [_format_matchup_row(r) for r in threat_results]

    # Create a text table for display
    table_lines = []
    header = f"{'Threat':<20} {'Usage':>7} {'Your Dmg':>12} {'Your KO':>20} {'Their Dmg':>12} {'Their KO':>20} {'Speed':>7}"
    table_lines.append(header)
    table_lines.append("-" * len(header))

    for row in rows:
        line = (
            f"{row['threat']:<20} "
            f"{row['usage']:>7} "
            f"{row['your_dmg']:>12} "
            f"{row['your_ko']:>20} "
            f"{row['their_dmg']:>12} "
            f"{row['their_ko']:>20} "
            f"{row['speed']:>7}"
        )
        table_lines.append(line)

    return {
        "table_text": "\n".join(table_lines),
        "rows": rows
    }


def register_meta_threat_tools(mcp: FastMCP, smogon, pokeapi, team_manager):
    """Register meta threat analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_spread_vs_threats(
        pokemon_name: str,
        nature: str,
        hp_evs: int = 0,
        atk_evs: int = 0,
        def_evs: int = 0,
        spa_evs: int = 0,
        spd_evs: int = 0,
        spe_evs: int = 0,
        top_threats: int = 10
    ) -> dict:
        """
        Analyze a spread against the top meta threats.

        Checks damage calculations in both directions against the most
        used Pokemon in the current metagame.

        NOTE: EVs default to 0 if not specified. For accurate results,
        specify your full EV spread. Common spreads are 252/252/4.

        Args:
            pokemon_name: Your Pokemon's name
            nature: Nature (e.g., "Adamant", "Timid")
            hp_evs: HP EVs (0-252, default 0 - specify for accurate results)
            atk_evs: Attack EVs (0-252, default 0)
            def_evs: Defense EVs (0-252, default 0)
            spa_evs: Special Attack (Sp. Atk) EVs (0-252, default 0)
            spd_evs: Special Defense (Sp. Def) EVs (0-252, default 0)
            spe_evs: Speed EVs (0-252, default 0)
            top_threats: Number of top threats to analyze (default 10)

        Returns:
            Comprehensive threat analysis with matchup verdicts
        """
        # Validate nature first
        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {nature}"}

        # Get your Pokemon's data
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            your_types = await pokeapi.get_pokemon_types(pokemon_name)
        except Exception as e:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        evs = EVSpread(
            hp=hp_evs,
            attack=atk_evs,
            defense=def_evs,
            special_attack=spa_evs,
            special_defense=spd_evs,
            speed=spe_evs
        )

        your_pokemon = PokemonBuild(
            name=pokemon_name,
            base_stats=base_stats,
            types=your_types,
            nature=nature_enum,
            evs=evs,
            level=50
        )

        your_stats = calculate_all_stats(your_pokemon)

        # Get your common moves (simplified - would need actual moveset data)
        your_usage = await smogon.get_pokemon_usage(pokemon_name)
        your_moves = []
        if your_usage:
            for move_name, usage in list(your_usage.get("moves", {}).items())[:4]:
                move_data = await pokeapi.get_move(move_name)
                if move_data:
                    your_moves.append({
                        "name": move_name,
                        "power": move_data.get("power", 0),
                        "type": move_data.get("type", "normal"),
                        "category": move_data.get("category", "physical")
                    })

        # Get meta usage stats
        usage_stats = await smogon.get_usage_stats()
        meta_info = usage_stats.get("_meta", {})
        usage_data = usage_stats.get("data", {})

        # Get top threats
        sorted_pokemon = sorted(
            usage_data.items(),
            key=lambda x: x[1].get("usage", 0),
            reverse=True
        )[:top_threats]

        # Analyze each threat
        threat_results = []
        for threat_name, threat_usage_data in sorted_pokemon:
            # Skip self
            if threat_name.lower() == pokemon_name.lower():
                continue

            try:
                threat_base_stats = await pokeapi.get_base_stats(threat_name)
                threat_types = await pokeapi.get_pokemon_types(threat_name)
            except Exception:
                continue

            threat_usage = await smogon.get_pokemon_usage(threat_name)

            # Get threat's common moves
            threat_moves = []
            if threat_usage:
                for move_name, usage in list(threat_usage.get("moves", {}).items())[:4]:
                    move_data = await pokeapi.get_move(move_name)
                    if move_data:
                        threat_moves.append({
                            "name": move_name,
                            "power": move_data.power or 0,
                            "type": move_data.type.lower(),
                            "category": move_data.category.value
                        })

            # Use actual Smogon spread if available, otherwise estimate
            threat_spread = None
            if threat_usage and threat_usage.get("spreads"):
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
                    threat_pokemon_build = PokemonBuild(
                        name=threat_name,
                        base_stats=threat_base_stats,
                        types=threat_types,
                        nature=threat_nature,
                        evs=threat_evs,
                        level=50
                    )
                    threat_stats = calculate_all_stats(threat_pokemon_build)
                    threat_spread = {
                        "nature": top_spread["nature"],
                        "evs": top_spread["evs"],
                        "usage": top_spread.get("usage", 0)
                    }
                except (ValueError, KeyError):
                    # Fallback to estimates if spread parsing fails
                    threat_stats = {
                        "hp": threat_base_stats.hp + 75,
                        "attack": threat_base_stats.attack + 40,
                        "defense": threat_base_stats.defense + 40,
                        "special_attack": threat_base_stats.special_attack + 40,
                        "special_defense": threat_base_stats.special_defense + 40,
                        "speed": threat_base_stats.speed + 40
                    }
            else:
                # Fallback to rough estimates if no spread data
                threat_stats = {
                    "hp": threat_base_stats.hp + 75,
                    "attack": threat_base_stats.attack + 40,
                    "defense": threat_base_stats.defense + 40,
                    "special_attack": threat_base_stats.special_attack + 40,
                    "special_defense": threat_base_stats.special_defense + 40,
                    "speed": threat_base_stats.speed + 40
                }

            result = analyze_single_threat(
                your_pokemon=your_pokemon,
                your_stats=your_stats,
                threat_name=threat_name,
                threat_stats=threat_stats,
                threat_types=threat_types,
                threat_usage_pct=round(threat_usage_data.get("usage", 0) * 100, 2),
                threat_common_moves=threat_moves,
                your_common_moves=your_moves,
                your_speed=your_stats["speed"],
                threat_spread=threat_spread
            )

            threat_results.append(result)

        # Categorize results
        favorable = [r for r in threat_results if r.matchup_verdict == "Favorable"]
        unfavorable = [r for r in threat_results if r.matchup_verdict == "Unfavorable"]
        even = [r for r in threat_results if r.matchup_verdict == "Even"]

        # Find OHKOs
        ohko_threats = [r.threat_name for r in threat_results
                        if r.threat_damage_to_you.get("is_guaranteed_ohko", False)]
        ohko_targets = [r.threat_name for r in threat_results
                        if r.your_damage_to_threat.get("is_guaranteed_ohko", False)]

        # Generate suggestions
        suggestions = generate_spread_suggestions(your_pokemon, threat_results)

        # Format results as table
        table_data = _format_results_table(threat_results)

        return {
            "pokemon": pokemon_name,
            "spread": {
                "nature": nature,
                "hp": hp_evs,
                "attack": atk_evs,
                "defense": def_evs,
                "special_attack": spa_evs,
                "special_defense": spd_evs,
                "speed": spe_evs
            },
            "final_stats": your_stats,
            "threats_analyzed": len(threat_results),
            "summary": {
                "favorable": len(favorable),
                "unfavorable": len(unfavorable),
                "even": len(even)
            },
            # Main table output with KO probabilities
            "matchup_table": table_data["table_text"],
            "matchups": table_data["rows"],
            # Legacy format for compatibility
            "favorable_matchups": [_format_matchup_row(r) for r in favorable[:5]],
            "unfavorable_matchups": [_format_matchup_row(r) for r in unfavorable[:5]],
            "ohko_threats": ohko_threats,
            "ohko_targets": ohko_targets,
            "suggestions": suggestions,
            "meta_info": meta_info
        }

    @mcp.tool()
    async def analyze_stored_pokemon_threats(
        pokemon_reference: Optional[str] = None,
        top_threats: int = 10
    ) -> dict:
        """
        Analyze a stored Pokemon's spread against top meta threats.

        Uses a Pokemon previously stored with set_my_pokemon.

        Args:
            pokemon_reference: Reference to stored Pokemon (e.g., "my Entei"),
                              or None to use most recently stored
            top_threats: Number of top threats to analyze (default 10)

        Returns:
            Comprehensive threat analysis
        """
        pokemon = team_manager.get_pokemon_context(pokemon_reference)
        if not pokemon:
            stored = team_manager.list_pokemon_context()
            return {
                "error": "No stored Pokemon found",
                "hint": "Use set_my_pokemon first to store a Pokemon",
                "stored_pokemon": [p["reference"] for p in stored]
            }

        your_stats = calculate_all_stats(pokemon)

        # Get your common moves
        your_usage = await smogon.get_pokemon_usage(pokemon.name)
        your_moves = []
        if your_usage:
            for move_name, usage in list(your_usage.get("moves", {}).items())[:4]:
                move_data = await pokeapi.get_move(move_name)
                if move_data:
                    your_moves.append({
                        "name": move_name,
                        "power": move_data.get("power", 0),
                        "type": move_data.get("type", "normal"),
                        "category": move_data.get("category", "physical")
                    })

        # Get meta usage stats
        usage_stats = await smogon.get_usage_stats()
        meta_info = usage_stats.get("_meta", {})
        usage_data = usage_stats.get("data", {})

        sorted_pokemon = sorted(
            usage_data.items(),
            key=lambda x: x[1].get("usage", 0),
            reverse=True
        )[:top_threats]

        threat_results = []
        for threat_name, threat_usage_data in sorted_pokemon:
            if threat_name.lower() == pokemon.name.lower():
                continue

            try:
                threat_base_stats = await pokeapi.get_base_stats(threat_name)
                threat_types = await pokeapi.get_pokemon_types(threat_name)
            except Exception:
                continue

            threat_usage = await smogon.get_pokemon_usage(threat_name)

            threat_moves = []
            if threat_usage:
                for move_name, usage in list(threat_usage.get("moves", {}).items())[:4]:
                    move_data = await pokeapi.get_move(move_name)
                    if move_data:
                        threat_moves.append({
                            "name": move_name,
                            "power": move_data.power or 0,
                            "type": move_data.type.lower(),
                            "category": move_data.category.value
                        })

            # Use actual Smogon spread if available, otherwise estimate
            threat_spread = None
            if threat_usage and threat_usage.get("spreads"):
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
                    threat_pokemon_build = PokemonBuild(
                        name=threat_name,
                        base_stats=threat_base_stats,
                        types=threat_types,
                        nature=threat_nature,
                        evs=threat_evs,
                        level=50
                    )
                    threat_stats = calculate_all_stats(threat_pokemon_build)
                    threat_spread = {
                        "nature": top_spread["nature"],
                        "evs": top_spread["evs"],
                        "usage": top_spread.get("usage", 0)
                    }
                except (ValueError, KeyError):
                    threat_stats = {
                        "hp": threat_base_stats.hp + 75,
                        "attack": threat_base_stats.attack + 40,
                        "defense": threat_base_stats.defense + 40,
                        "special_attack": threat_base_stats.special_attack + 40,
                        "special_defense": threat_base_stats.special_defense + 40,
                        "speed": threat_base_stats.speed + 40
                    }
            else:
                threat_stats = {
                    "hp": threat_base_stats.hp + 75,
                    "attack": threat_base_stats.attack + 40,
                    "defense": threat_base_stats.defense + 40,
                    "special_attack": threat_base_stats.special_attack + 40,
                    "special_defense": threat_base_stats.special_defense + 40,
                    "speed": threat_base_stats.speed + 40
                }

            result = analyze_single_threat(
                your_pokemon=pokemon,
                your_stats=your_stats,
                threat_name=threat_name,
                threat_stats=threat_stats,
                threat_types=threat_types,
                threat_usage_pct=round(threat_usage_data.get("usage", 0) * 100, 2),
                threat_common_moves=threat_moves,
                your_common_moves=your_moves,
                your_speed=your_stats["speed"],
                threat_spread=threat_spread
            )

            threat_results.append(result)

        favorable = [r for r in threat_results if r.matchup_verdict == "Favorable"]
        unfavorable = [r for r in threat_results if r.matchup_verdict == "Unfavorable"]
        even = [r for r in threat_results if r.matchup_verdict == "Even"]

        ohko_threats = [r.threat_name for r in threat_results
                        if r.threat_damage_to_you.get("is_guaranteed_ohko", False)]
        ohko_targets = [r.threat_name for r in threat_results
                        if r.your_damage_to_threat.get("is_guaranteed_ohko", False)]

        suggestions = generate_spread_suggestions(pokemon, threat_results)

        # Format results as table
        table_data = _format_results_table(threat_results)

        return {
            "pokemon": pokemon.name,
            "spread": {
                "nature": pokemon.nature.value.title(),
                "hp": pokemon.evs.hp,
                "attack": pokemon.evs.attack,
                "defense": pokemon.evs.defense,
                "special_attack": pokemon.evs.special_attack,
                "special_defense": pokemon.evs.special_defense,
                "speed": pokemon.evs.speed
            },
            "final_stats": your_stats,
            "threats_analyzed": len(threat_results),
            "summary": {
                "favorable": len(favorable),
                "unfavorable": len(unfavorable),
                "even": len(even)
            },
            # Main table output with KO probabilities
            "matchup_table": table_data["table_text"],
            "matchups": table_data["rows"],
            # Legacy format for compatibility
            "favorable_matchups": [_format_matchup_row(r) for r in favorable[:5]],
            "unfavorable_matchups": [_format_matchup_row(r) for r in unfavorable[:5]],
            "ohko_threats": ohko_threats,
            "ohko_targets": ohko_targets,
            "suggestions": suggestions,
            "meta_info": meta_info
        }

    @mcp.tool()
    async def check_survival_benchmark(
        pokemon_name: str,
        nature: str,
        hp_evs: int,
        def_evs: int,
        spd_evs: int,
        threat_pokemon: str,
        threat_move: str,
        survival_threshold: float = 100.0
    ) -> dict:
        """
        Check if a spread survives a specific attack from a threat.

        Useful for verifying defensive benchmarks like "survives Koraidon
        Flare Blitz" or "survives Flutter Mane Moonblast".

        Args:
            pokemon_name: Your Pokemon
            nature: Your nature
            hp_evs: HP EVs
            def_evs: Defense EVs
            spd_evs: Special Defense EVs
            threat_pokemon: Attacking Pokemon
            threat_move: Move name
            survival_threshold: Required survival percentage (0-100).
                - 100 = must survive all rolls (default, "always survives")
                - 75 = survive 75% of rolls ("most of the time")
                - 50 = survive 50% of rolls ("sometimes")

        Returns:
            Survival analysis with damage range and survival percentage
        """
        # Validate nature first
        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {nature}"}

        # Get your Pokemon's data
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            your_types = await pokeapi.get_pokemon_types(pokemon_name)
        except Exception:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        # Get threat data
        try:
            threat_base_stats = await pokeapi.get_base_stats(threat_pokemon)
            threat_types = await pokeapi.get_pokemon_types(threat_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {threat_pokemon}"}

        move_data = await pokeapi.get_move(threat_move)
        if not move_data:
            return {"error": f"Move not found: {threat_move}"}

        evs = EVSpread(
            hp=hp_evs,
            defense=def_evs,
            special_defense=spd_evs
        )

        your_pokemon = PokemonBuild(
            name=pokemon_name,
            base_stats=base_stats,
            types=your_types,
            nature=nature_enum,
            evs=evs,
            level=50
        )

        your_stats = calculate_all_stats(your_pokemon)

        # Get threat's actual spread from Smogon if available
        is_physical = move_data.category.value == "physical"
        threat_usage = await smogon.get_pokemon_usage(threat_pokemon)
        threat_spread = None

        if threat_usage and threat_usage.get("spreads"):
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
                threat_pokemon_build = PokemonBuild(
                    name=threat_pokemon,
                    base_stats=threat_base_stats,
                    types=threat_types,
                    nature=threat_nature,
                    evs=threat_evs,
                    level=50
                )
                threat_stats = calculate_all_stats(threat_pokemon_build)
                threat_spread = {
                    "nature": top_spread["nature"],
                    "evs": top_spread["evs"],
                    "usage": top_spread.get("usage", 0)
                }
            except (ValueError, KeyError):
                # Fallback to estimates
                threat_stats = {
                    "hp": threat_base_stats.hp + 75,
                    "attack": threat_base_stats.attack + 80 if is_physical else threat_base_stats.attack + 40,
                    "defense": threat_base_stats.defense + 40,
                    "special_attack": threat_base_stats.special_attack + 80 if not is_physical else threat_base_stats.special_attack + 40,
                    "special_defense": threat_base_stats.special_defense + 40,
                    "speed": threat_base_stats.speed + 40
                }
        else:
            # Fallback to estimated max offensive investment
            threat_stats = {
                "hp": threat_base_stats.hp + 75,
                "attack": threat_base_stats.attack + 80 if is_physical else threat_base_stats.attack + 40,
                "defense": threat_base_stats.defense + 40,
                "special_attack": threat_base_stats.special_attack + 80 if not is_physical else threat_base_stats.special_attack + 40,
                "special_defense": threat_base_stats.special_defense + 40,
                "speed": threat_base_stats.speed + 40
            }

        from vgc_mcp_core.calc.meta_threats import calculate_simple_damage
        from vgc_mcp_core.calc.modifiers import get_type_effectiveness

        # Check if STAB
        stab = move_data.type.lower() in [t.lower() for t in threat_types]

        # Calculate type effectiveness
        type_eff = get_type_effectiveness(
            move_data.type.lower(),
            your_types
        )

        damage = calculate_simple_damage(
            threat_stats, your_stats,
            move_data.power or 80,
            is_physical,
            stab=stab,
            type_effectiveness=type_eff
        )

        # Calculate exact survival percentage from damage rolls
        damage_rolls = damage.get("damage_rolls", [])
        your_hp = your_stats["hp"]

        if damage_rolls:
            survival_count = sum(1 for r in damage_rolls if r < your_hp)
            survival_percent = (survival_count / len(damage_rolls)) * 100
        else:
            # Fallback to binary check if no rolls available
            survival_percent = 100.0 if your_hp > damage["max_damage"] else 0.0
            survival_count = 16 if survival_percent == 100.0 else 0

        # Determine survival status
        survives_guaranteed = survival_percent == 100.0
        survives_sometimes = 0 < survival_percent < 100.0
        meets_threshold = survival_percent >= survival_threshold

        # Calculate HP remaining after taking damage (for clear communication)
        # Use min/max damage to show HP remaining range
        hp_remaining_min = max(0, your_hp - damage["max_damage"])
        hp_remaining_max = max(0, your_hp - damage["min_damage"])
        hp_remaining_min_pct = round((hp_remaining_min / your_hp) * 100, 1)
        hp_remaining_max_pct = round((hp_remaining_max / your_hp) * 100, 1)

        # Check if attacker has Unseen Fist (Urshifu forms)
        normalized_threat = threat_pokemon.lower().replace(" ", "-")
        has_unseen_fist = normalized_threat in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike")

        # Build analysis message with HP remaining for clarity
        if survives_guaranteed:
            analysis_msg = (
                f"Your {pokemon_name} survives all rolls from {threat_pokemon}'s {threat_move}, "
                f"left with {hp_remaining_min_pct}-{hp_remaining_max_pct}% HP"
            )
        elif survival_percent == 0:
            analysis_msg = f"Your {pokemon_name} does NOT survive any rolls from {threat_pokemon}'s {threat_move}"
        else:
            threshold_status = "MEETS" if meets_threshold else "does NOT meet"
            analysis_msg = (
                f"Your {pokemon_name} survives {survival_percent:.1f}% of rolls "
                f"({survival_count}/16) from {threat_pokemon}'s {threat_move}. "
                f"When surviving, left with {hp_remaining_min_pct}-{hp_remaining_max_pct}% HP. "
                f"{threshold_status} {survival_threshold}% threshold."
            )

        result = {
            "your_pokemon": pokemon_name,
            "your_hp": your_hp,
            "threat_pokemon": threat_pokemon,
            "threat_move": threat_move,
            "threat_spread": threat_spread,
            "threat_stats": threat_stats,
            "move_type": move_data.type,
            "move_category": move_data.category.value,
            "damage_range": f"{damage['min_damage']}-{damage['max_damage']}",
            "damage_percent": f"{damage['min_percent']:.1f}%-{damage['max_percent']:.1f}%",
            # HP remaining after taking the hit (clearer than damage percent for survival discussions)
            "hp_remaining_range": f"{hp_remaining_min}-{hp_remaining_max}",
            "hp_remaining_percent": f"{hp_remaining_min_pct}-{hp_remaining_max_pct}%",
            "survival_percent": round(survival_percent, 1),
            "survival_rolls": f"{survival_count}/16",
            "survives_guaranteed": survives_guaranteed,
            "survives_sometimes": survives_sometimes,
            "meets_threshold": meets_threshold,
            "threshold_requested": survival_threshold,
            "ko_result": damage["ko_chance"],
            "type_effectiveness": type_eff,
            "analysis": analysis_msg
        }

        # Build benchmark table for clear display
        survival_status = "Survives" if survives_guaranteed else ("Survives sometimes" if survives_sometimes else "Does not survive")
        threshold_status = "Yes" if meets_threshold else "No"
        table_lines = [
            "| Metric               | Value                                    |",
            "|----------------------|------------------------------------------|",
            f"| Pokemon              | {pokemon_name:<40} |",
            f"| HP                   | {your_hp:<40} |",
            f"| Threat               | {threat_pokemon}'s {threat_move:<20} |",
            f"| Damage Taken         | {damage['min_percent']:.1f}-{damage['max_percent']:.1f}%{' ':<30} |",
            f"| HP Remaining         | {hp_remaining_min_pct}-{hp_remaining_max_pct}%{' ':<30} |",
            f"| Survival Probability | {survival_percent:.1f}% ({survival_count}/16 rolls){' ':<20} |",
            f"| Survival Status      | {survival_status:<40} |",
            f"| Threshold Met        | {threshold_status} ({survival_threshold}% required){' ':<20} |",
        ]
        result["benchmark_table"] = "\n".join(table_lines)

        if has_unseen_fist:
            result["unseen_fist_warning"] = (
                "WARNING: Urshifu has Unseen Fist - contact moves bypass Protect! "
                "You cannot avoid this damage with Protect."
            )

        return result

    @mcp.tool()
    async def find_survival_evs(
        pokemon_name: str,
        nature: str,
        threat_pokemon: str,
        threat_move: str,
        is_physical: Optional[bool] = None,
        survival_threshold: float = 100.0
    ) -> dict:
        """
        Find minimum bulk EVs needed to survive a specific attack.

        Args:
            pokemon_name: Your Pokemon
            nature: Your nature
            threat_pokemon: Attacking Pokemon
            threat_move: Move name
            is_physical: Override move category detection
            survival_threshold: Required survival percentage (0-100).
                - 100 = must survive all rolls (default, "always survives")
                - 75 = survive 75% of rolls ("most of the time")
                - 50 = survive 50% of rolls ("sometimes")

        Returns:
            Minimum HP and defensive EVs needed to achieve the survival threshold
        """
        # Validate nature first
        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {nature}"}

        # Get Pokemon data
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            your_types = await pokeapi.get_pokemon_types(pokemon_name)
        except Exception:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        try:
            threat_base_stats = await pokeapi.get_base_stats(threat_pokemon)
            threat_types = await pokeapi.get_pokemon_types(threat_pokemon)
        except Exception:
            return {"error": f"Pokemon not found: {threat_pokemon}"}

        move_data = await pokeapi.get_move(threat_move)
        if not move_data:
            return {"error": f"Move not found: {threat_move}"}

        move_is_physical = is_physical if is_physical is not None else (
            move_data.category.value == "physical"
        )

        # Get threat's actual spread from Smogon if available
        threat_usage = await smogon.get_pokemon_usage(threat_pokemon)
        threat_spread = None

        if threat_usage and threat_usage.get("spreads"):
            top_spread = threat_usage["spreads"][0]
            try:
                threat_nature = Nature(top_spread["nature"].lower())
                threat_evs_data = EVSpread(
                    hp=top_spread["evs"].get("hp", 0),
                    attack=top_spread["evs"].get("attack", 0),
                    defense=top_spread["evs"].get("defense", 0),
                    special_attack=top_spread["evs"].get("special_attack", 0),
                    special_defense=top_spread["evs"].get("special_defense", 0),
                    speed=top_spread["evs"].get("speed", 0)
                )
                threat_pokemon_build = PokemonBuild(
                    name=threat_pokemon,
                    base_stats=threat_base_stats,
                    types=threat_types,
                    nature=threat_nature,
                    evs=threat_evs_data,
                    level=50
                )
                threat_stats = calculate_all_stats(threat_pokemon_build)
                threat_spread = {
                    "nature": top_spread["nature"],
                    "evs": top_spread["evs"],
                    "usage": top_spread.get("usage", 0)
                }
            except (ValueError, KeyError):
                threat_stats = {
                    "hp": threat_base_stats.hp + 75,
                    "attack": threat_base_stats.attack + 80 if move_is_physical else threat_base_stats.attack + 40,
                    "defense": threat_base_stats.defense + 40,
                    "special_attack": threat_base_stats.special_attack + 80 if not move_is_physical else threat_base_stats.special_attack + 40,
                    "special_defense": threat_base_stats.special_defense + 40,
                    "speed": threat_base_stats.speed + 40
                }
        else:
            # Fallback to estimated max offensive
            threat_stats = {
                "hp": threat_base_stats.hp + 75,
                "attack": threat_base_stats.attack + 80 if move_is_physical else threat_base_stats.attack + 40,
                "defense": threat_base_stats.defense + 40,
                "special_attack": threat_base_stats.special_attack + 80 if not move_is_physical else threat_base_stats.special_attack + 40,
                "special_defense": threat_base_stats.special_defense + 40,
                "speed": threat_base_stats.speed + 40
            }

        stab = move_data.type.lower() in [t.lower() for t in threat_types]

        from vgc_mcp_core.calc.meta_threats import calculate_simple_damage
        from vgc_mcp_core.calc.modifiers import get_type_effectiveness

        type_eff = get_type_effectiveness(
            move_data.type.lower(),
            your_types
        )

        best_spread = None
        min_total_evs = 999
        max_achievable_survival = 0
        max_achievable_spread = None

        for hp_evs in EV_BREAKPOINTS_LV50:
            for def_evs in EV_BREAKPOINTS_LV50:
                if hp_evs + def_evs > 508:
                    continue

                evs = EVSpread(
                    hp=hp_evs,
                    defense=def_evs if move_is_physical else 0,
                    special_defense=0 if move_is_physical else def_evs
                )

                test_pokemon = PokemonBuild(
                    name=pokemon_name,
                    base_stats=base_stats,
                    types=your_types,
                    nature=nature_enum,
                    evs=evs,
                    level=50
                )

                test_stats = calculate_all_stats(test_pokemon)

                damage = calculate_simple_damage(
                    threat_stats, test_stats,
                    move_data.power or 80,
                    move_is_physical,
                    stab=stab,
                    type_effectiveness=type_eff
                )

                # Calculate survival percentage from damage rolls
                damage_rolls = damage.get("damage_rolls", [])
                test_hp = test_stats["hp"]

                if damage_rolls:
                    survival_count = sum(1 for r in damage_rolls if r < test_hp)
                    survival_percent = (survival_count / len(damage_rolls)) * 100
                else:
                    # Fallback to binary check
                    survival_percent = 100.0 if test_hp > damage["max_damage"] else 0.0
                    survival_count = 16 if survival_percent == 100.0 else 0

                # Calculate HP remaining for clearer output
                hp_remaining_min = max(0, test_hp - damage["max_damage"])
                hp_remaining_max = max(0, test_hp - damage["min_damage"])
                hp_remaining_min_pct = round((hp_remaining_min / test_hp) * 100, 1)
                hp_remaining_max_pct = round((hp_remaining_max / test_hp) * 100, 1)

                # Track max achievable survival (for when threshold is impossible)
                if survival_percent > max_achievable_survival:
                    max_achievable_survival = survival_percent
                    max_achievable_spread = {
                        "hp_evs": hp_evs,
                        "def_evs": def_evs if move_is_physical else 0,
                        "spd_evs": 0 if move_is_physical else def_evs,
                        "total_evs": hp_evs + def_evs,
                        "resulting_hp": test_hp,
                        "survival_percent": round(survival_percent, 1),
                        "survival_rolls": f"{survival_count}/16",
                        "damage_taken": f"{damage['min_percent']:.0f}%-{damage['max_percent']:.0f}%",
                        "hp_remaining_percent": f"{hp_remaining_min_pct}-{hp_remaining_max_pct}%"
                    }

                # Check if meets threshold
                if survival_percent >= survival_threshold:
                    total = hp_evs + def_evs
                    if total < min_total_evs:
                        min_total_evs = total
                        best_spread = {
                            "hp_evs": hp_evs,
                            "def_evs": def_evs if move_is_physical else 0,
                            "spd_evs": 0 if move_is_physical else def_evs,
                            "total_evs": total,
                            "resulting_hp": test_hp,
                            "survival_percent": round(survival_percent, 1),
                            "survival_rolls": f"{survival_count}/16",
                            "damage_taken": f"{damage['min_percent']:.0f}%-{damage['max_percent']:.0f}%",
                            "hp_remaining_percent": f"{hp_remaining_min_pct}-{hp_remaining_max_pct}%"
                        }
                        break  # Found minimum for this HP level
            if best_spread and best_spread["total_evs"] == min_total_evs:
                # Check if we can do better with less HP
                if hp_evs > 0:
                    continue
                break

        # Check if attacker has Unseen Fist (Urshifu forms)
        normalized_threat = threat_pokemon.lower().replace(" ", "-")
        has_unseen_fist = normalized_threat in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike")

        if not best_spread:
            # Build message based on what's achievable
            if max_achievable_survival > 0:
                message = (
                    f"Cannot achieve {survival_threshold}% survival against {threat_pokemon}'s {threat_move}. "
                    f"Max achievable is {max_achievable_survival:.1f}% with max bulk investment."
                )
            else:
                message = f"Cannot survive {threat_pokemon}'s {threat_move} even with max bulk investment"

            result = {
                "pokemon": pokemon_name,
                "threat": threat_pokemon,
                "move": threat_move,
                "threat_spread": threat_spread,
                "threat_stats": threat_stats,
                "impossible": True,
                "threshold_requested": survival_threshold,
                "max_achievable_survival": round(max_achievable_survival, 1),
                "max_achievable_spread": max_achievable_spread,
                "message": message
            }
        else:
            # Build analysis message with HP remaining for clarity
            threshold_note = ""
            if survival_threshold < 100:
                threshold_note = f" (meets {survival_threshold}% threshold)"

            result = {
                "pokemon": pokemon_name,
                "nature": nature,
                "threat": threat_pokemon,
                "move": threat_move,
                "threat_spread": threat_spread,
                "threat_stats": threat_stats,
                "move_type": move_data.type,
                "move_category": "Physical" if move_is_physical else "Special",
                "threshold_requested": survival_threshold,
                "minimum_evs": best_spread,
                "analysis": (
                    f"Minimum {best_spread['total_evs']} total EVs needed: "
                    f"{best_spread['hp_evs']} HP / "
                    f"{best_spread['def_evs']} Def / "
                    f"{best_spread['spd_evs']} SpD "
                    f"to survive {best_spread['survival_percent']}% of rolls "
                    f"({best_spread['survival_rolls']}), "
                    f"left with {best_spread['hp_remaining_percent']} HP{threshold_note}"
                )
            }

            # Build spread result table
            table_lines = [
                "| Stat                 | Value                                    |",
                "|----------------------|------------------------------------------|",
                f"| Pokemon              | {pokemon_name:<40} |",
                f"| Nature               | {nature:<40} |",
                f"| Threat               | {threat_pokemon}'s {threat_move:<20} |",
                f"| HP EVs               | {best_spread['hp_evs']:<40} |",
                f"| Def EVs              | {best_spread['def_evs']:<40} |",
                f"| SpD EVs              | {best_spread['spd_evs']:<40} |",
                f"| Total EVs            | {best_spread['total_evs']:<40} |",
                f"| Resulting HP         | {best_spread['resulting_hp']:<40} |",
                f"| Damage Taken         | {best_spread['damage_taken']:<40} |",
                f"| HP Remaining         | {best_spread['hp_remaining_percent']:<40} |",
                f"| Survival Rate        | {best_spread['survival_percent']}% ({best_spread['survival_rolls']}){' ':<20} |",
            ]
            result["spread_table"] = "\n".join(table_lines)

        if has_unseen_fist:
            result["unseen_fist_warning"] = (
                "WARNING: Urshifu has Unseen Fist - contact moves bypass Protect! "
                "You cannot avoid this damage with Protect."
            )

        return result
