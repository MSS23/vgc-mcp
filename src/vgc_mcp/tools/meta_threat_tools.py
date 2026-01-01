"""MCP tools for meta threat analysis.

This module provides tools to analyze a Pokemon's spread against
the top threats in the metagame, including damage calculations
and matchup assessments.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..calc.stats import calculate_all_stats
from ..calc.speed_probability import calculate_speed_stat
from ..calc.meta_threats import (
    analyze_single_threat,
    generate_spread_suggestions,
    create_empty_threat_report,
    MetaThreatReport,
    ThreatDamageResult
)
from ..models.pokemon import PokemonBuild, BaseStats, EVSpread, Nature
from ..config import EV_BREAKPOINTS_LV50


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
        # Get your Pokemon's data
        your_data = await pokeapi.get_pokemon(pokemon_name)
        if not your_data:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        # Validate nature
        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {nature}"}

        # Create your Pokemon build
        base_stats = BaseStats(
            hp=your_data["base_stats"]["hp"],
            attack=your_data["base_stats"]["attack"],
            defense=your_data["base_stats"]["defense"],
            special_attack=your_data["base_stats"]["special_attack"],
            special_defense=your_data["base_stats"]["special_defense"],
            speed=your_data["base_stats"]["speed"]
        )

        evs = EVSpread(
            hp=hp_evs,
            attack=atk_evs,
            defense=def_evs,
            special_attack=spa_evs,
            special_defense=spd_evs,
            speed=spe_evs
        )

        your_pokemon = PokemonBuild(
            name=your_data["name"],
            base_stats=base_stats,
            types=your_data.get("types", []),
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

            threat_api_data = await pokeapi.get_pokemon(threat_name)
            if not threat_api_data:
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
                            "power": move_data.get("power", 0),
                            "type": move_data.get("type", "normal"),
                            "category": move_data.get("category", "physical")
                        })

            # Build threat stats dict
            threat_stats = {
                "hp": threat_api_data["base_stats"]["hp"] + 75,  # Rough estimate with EVs
                "attack": threat_api_data["base_stats"]["attack"] + 40,
                "defense": threat_api_data["base_stats"]["defense"] + 40,
                "special_attack": threat_api_data["base_stats"]["special_attack"] + 40,
                "special_defense": threat_api_data["base_stats"]["special_defense"] + 40,
                "speed": threat_api_data["base_stats"]["speed"] + 40
            }

            result = analyze_single_threat(
                your_pokemon=your_pokemon,
                your_stats=your_stats,
                threat_name=threat_name,
                threat_stats=threat_stats,
                threat_types=threat_api_data.get("types", []),
                threat_usage_pct=round(threat_usage_data.get("usage", 0) * 100, 2),
                threat_common_moves=threat_moves,
                your_common_moves=your_moves,
                your_speed=your_stats["speed"]
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
            "favorable_matchups": [
                {
                    "threat": r.threat_name,
                    "usage": r.threat_usage_pct,
                    "verdict": r.matchup_verdict,
                    "speed": r.speed_comparison,
                    "your_damage": r.your_damage_to_threat,
                    "their_damage": r.threat_damage_to_you
                }
                for r in favorable[:5]
            ],
            "unfavorable_matchups": [
                {
                    "threat": r.threat_name,
                    "usage": r.threat_usage_pct,
                    "verdict": r.matchup_verdict,
                    "speed": r.speed_comparison,
                    "your_damage": r.your_damage_to_threat,
                    "their_damage": r.threat_damage_to_you
                }
                for r in unfavorable[:5]
            ],
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

            threat_api_data = await pokeapi.get_pokemon(threat_name)
            if not threat_api_data:
                continue

            threat_usage = await smogon.get_pokemon_usage(threat_name)

            threat_moves = []
            if threat_usage:
                for move_name, usage in list(threat_usage.get("moves", {}).items())[:4]:
                    move_data = await pokeapi.get_move(move_name)
                    if move_data:
                        threat_moves.append({
                            "name": move_name,
                            "power": move_data.get("power", 0),
                            "type": move_data.get("type", "normal"),
                            "category": move_data.get("category", "physical")
                        })

            threat_stats = {
                "hp": threat_api_data["base_stats"]["hp"] + 75,
                "attack": threat_api_data["base_stats"]["attack"] + 40,
                "defense": threat_api_data["base_stats"]["defense"] + 40,
                "special_attack": threat_api_data["base_stats"]["special_attack"] + 40,
                "special_defense": threat_api_data["base_stats"]["special_defense"] + 40,
                "speed": threat_api_data["base_stats"]["speed"] + 40
            }

            result = analyze_single_threat(
                your_pokemon=pokemon,
                your_stats=your_stats,
                threat_name=threat_name,
                threat_stats=threat_stats,
                threat_types=threat_api_data.get("types", []),
                threat_usage_pct=round(threat_usage_data.get("usage", 0) * 100, 2),
                threat_common_moves=threat_moves,
                your_common_moves=your_moves,
                your_speed=your_stats["speed"]
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
            "favorable_matchups": [
                {
                    "threat": r.threat_name,
                    "usage": r.threat_usage_pct,
                    "speed": r.speed_comparison,
                    "your_damage": r.your_damage_to_threat.get("ko_chance", "N/A"),
                    "their_damage": r.threat_damage_to_you.get("ko_chance", "N/A")
                }
                for r in favorable[:5]
            ],
            "unfavorable_matchups": [
                {
                    "threat": r.threat_name,
                    "usage": r.threat_usage_pct,
                    "speed": r.speed_comparison,
                    "your_damage": r.your_damage_to_threat.get("ko_chance", "N/A"),
                    "their_damage": r.threat_damage_to_you.get("ko_chance", "N/A")
                }
                for r in unfavorable[:5]
            ],
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
        threat_move: str
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

        Returns:
            Survival analysis with damage range
        """
        # Get your Pokemon's data
        your_data = await pokeapi.get_pokemon(pokemon_name)
        if not your_data:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {nature}"}

        # Get threat data
        threat_data = await pokeapi.get_pokemon(threat_pokemon)
        if not threat_data:
            return {"error": f"Pokemon not found: {threat_pokemon}"}

        move_data = await pokeapi.get_move(threat_move)
        if not move_data:
            return {"error": f"Move not found: {threat_move}"}

        # Build your Pokemon
        base_stats = BaseStats(
            hp=your_data["base_stats"]["hp"],
            attack=your_data["base_stats"]["attack"],
            defense=your_data["base_stats"]["defense"],
            special_attack=your_data["base_stats"]["special_attack"],
            special_defense=your_data["base_stats"]["special_defense"],
            speed=your_data["base_stats"]["speed"]
        )

        evs = EVSpread(
            hp=hp_evs,
            defense=def_evs,
            special_defense=spd_evs
        )

        your_pokemon = PokemonBuild(
            name=your_data["name"],
            base_stats=base_stats,
            types=your_data.get("types", []),
            nature=nature_enum,
            evs=evs,
            level=50
        )

        your_stats = calculate_all_stats(your_pokemon)

        # Estimate threat stats (max offensive investment)
        is_physical = move_data.get("category", "physical").lower() == "physical"
        threat_stats = {
            "hp": threat_data["base_stats"]["hp"] + 75,
            "attack": threat_data["base_stats"]["attack"] + 80 if is_physical else threat_data["base_stats"]["attack"] + 40,
            "defense": threat_data["base_stats"]["defense"] + 40,
            "special_attack": threat_data["base_stats"]["special_attack"] + 80 if not is_physical else threat_data["base_stats"]["special_attack"] + 40,
            "special_defense": threat_data["base_stats"]["special_defense"] + 40,
            "speed": threat_data["base_stats"]["speed"] + 40
        }

        from ..calc.meta_threats import calculate_simple_damage, _get_simple_effectiveness

        # Check if STAB
        stab = move_data.get("type", "normal").lower() in [t.lower() for t in threat_data.get("types", [])]

        # Calculate type effectiveness
        type_eff = _get_simple_effectiveness(
            move_data.get("type", "normal"),
            your_data.get("types", [])
        )

        damage = calculate_simple_damage(
            threat_stats, your_stats,
            move_data.get("power", 80),
            is_physical,
            stab=stab,
            type_effectiveness=type_eff
        )

        survives = your_stats["hp"] > damage["max_damage"]
        survives_min = your_stats["hp"] > damage["min_damage"]

        return {
            "your_pokemon": pokemon_name,
            "your_hp": your_stats["hp"],
            "threat_pokemon": threat_pokemon,
            "threat_move": threat_move,
            "move_type": move_data.get("type"),
            "move_category": move_data.get("category"),
            "damage_range": f"{damage['min_damage']}-{damage['max_damage']}",
            "damage_percent": f"{damage['min_percent']:.1f}%-{damage['max_percent']:.1f}%",
            "survives_guaranteed": survives,
            "survives_sometimes": survives_min and not survives,
            "ko_result": damage["ko_chance"],
            "type_effectiveness": type_eff,
            "analysis": (
                f"Your {pokemon_name} {'survives' if survives else 'does NOT survive'} "
                f"{threat_pokemon}'s {threat_move} ({damage['min_percent']:.0f}%-{damage['max_percent']:.0f}%)"
            )
        }

    @mcp.tool()
    async def find_survival_evs(
        pokemon_name: str,
        nature: str,
        threat_pokemon: str,
        threat_move: str,
        is_physical: Optional[bool] = None
    ) -> dict:
        """
        Find minimum bulk EVs needed to survive a specific attack.

        Args:
            pokemon_name: Your Pokemon
            nature: Your nature
            threat_pokemon: Attacking Pokemon
            threat_move: Move name
            is_physical: Override move category detection

        Returns:
            Minimum HP and defensive EVs needed to survive
        """
        # Get Pokemon data
        your_data = await pokeapi.get_pokemon(pokemon_name)
        if not your_data:
            return {"error": f"Pokemon not found: {pokemon_name}"}

        try:
            nature_enum = Nature(nature.lower())
        except ValueError:
            return {"error": f"Invalid nature: {nature}"}

        threat_data = await pokeapi.get_pokemon(threat_pokemon)
        if not threat_data:
            return {"error": f"Pokemon not found: {threat_pokemon}"}

        move_data = await pokeapi.get_move(threat_move)
        if not move_data:
            return {"error": f"Move not found: {threat_move}"}

        move_is_physical = is_physical if is_physical is not None else (
            move_data.get("category", "physical").lower() == "physical"
        )

        # Threat stats (max offensive)
        threat_stats = {
            "hp": threat_data["base_stats"]["hp"] + 75,
            "attack": threat_data["base_stats"]["attack"] + 80 if move_is_physical else threat_data["base_stats"]["attack"] + 40,
            "defense": threat_data["base_stats"]["defense"] + 40,
            "special_attack": threat_data["base_stats"]["special_attack"] + 80 if not move_is_physical else threat_data["base_stats"]["special_attack"] + 40,
            "special_defense": threat_data["base_stats"]["special_defense"] + 40,
            "speed": threat_data["base_stats"]["speed"] + 40
        }

        stab = move_data.get("type", "normal").lower() in [t.lower() for t in threat_data.get("types", [])]

        from ..calc.meta_threats import calculate_simple_damage, _get_simple_effectiveness

        type_eff = _get_simple_effectiveness(
            move_data.get("type", "normal"),
            your_data.get("types", [])
        )

        # Try different EV combinations
        base_stats = BaseStats(
            hp=your_data["base_stats"]["hp"],
            attack=your_data["base_stats"]["attack"],
            defense=your_data["base_stats"]["defense"],
            special_attack=your_data["base_stats"]["special_attack"],
            special_defense=your_data["base_stats"]["special_defense"],
            speed=your_data["base_stats"]["speed"]
        )

        best_spread = None
        min_total_evs = 999

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
                    name=your_data["name"],
                    base_stats=base_stats,
                    types=your_data.get("types", []),
                    nature=nature_enum,
                    evs=evs,
                    level=50
                )

                test_stats = calculate_all_stats(test_pokemon)

                damage = calculate_simple_damage(
                    threat_stats, test_stats,
                    move_data.get("power", 80),
                    move_is_physical,
                    stab=stab,
                    type_effectiveness=type_eff
                )

                if test_stats["hp"] > damage["max_damage"]:
                    total = hp_evs + def_evs
                    if total < min_total_evs:
                        min_total_evs = total
                        best_spread = {
                            "hp_evs": hp_evs,
                            "def_evs": def_evs if move_is_physical else 0,
                            "spd_evs": 0 if move_is_physical else def_evs,
                            "total_evs": total,
                            "resulting_hp": test_stats["hp"],
                            "damage_taken": f"{damage['min_percent']:.0f}%-{damage['max_percent']:.0f}%"
                        }
                        break  # Found minimum for this HP level
            if best_spread and best_spread["total_evs"] == min_total_evs:
                # Check if we can do better with less HP
                if hp_evs > 0:
                    continue
                break

        if not best_spread:
            return {
                "pokemon": pokemon_name,
                "threat": threat_pokemon,
                "move": threat_move,
                "impossible": True,
                "message": f"Cannot survive {threat_pokemon}'s {threat_move} even with max bulk investment"
            }

        return {
            "pokemon": pokemon_name,
            "nature": nature,
            "threat": threat_pokemon,
            "move": threat_move,
            "move_type": move_data.get("type"),
            "move_category": "Physical" if move_is_physical else "Special",
            "minimum_evs": best_spread,
            "analysis": (
                f"Minimum {best_spread['total_evs']} total EVs needed: "
                f"{best_spread['hp_evs']} HP / "
                f"{best_spread['def_evs']} Def / "
                f"{best_spread['spd_evs']} SpD"
            )
        }
