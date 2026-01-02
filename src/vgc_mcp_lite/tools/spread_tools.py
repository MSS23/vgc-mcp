"""MCP tools for EV spread optimization."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.stats import calculate_speed, calculate_stat, calculate_hp, find_speed_evs
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.bulk_optimization import (
    calculate_optimal_bulk_distribution,
    analyze_diminishing_returns
)
from vgc_mcp_core.models.pokemon import Nature, get_nature_modifier, PokemonBuild, BaseStats, EVSpread
from vgc_mcp_core.models.move import Move, MoveCategory
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50, normalize_evs


# Module-level Smogon client reference (set during registration)
_smogon_client: Optional[SmogonStatsClient] = None


def _get_synergy_ability(item: str, abilities: dict) -> tuple[str, float]:
    """Get the best ability to pair with an item based on known synergies.

    Args:
        item: The item being used
        abilities: Dict of ability_name -> usage_percent

    Returns:
        Tuple of (ability_name, usage_percent)
    """
    if not abilities:
        return (None, 0)

    # Normalize item name for matching
    item_lower = (item or "").lower().replace("-", " ").replace("_", " ")

    # Known synergies: item -> preferred abilities (in order of preference)
    synergies = {
        "life orb": ["Sheer Force"],  # Sheer Force cancels Life Orb recoil
        "choice band": ["Huge Power", "Pure Power", "Gorilla Tactics"],
        "choice specs": ["Adaptability"],
        "assault vest": ["Regenerator"],
        "rocky helmet": ["Rough Skin", "Iron Barbs"],
        "leftovers": ["Regenerator", "Poison Heal"],
        "black sludge": ["Regenerator", "Poison Heal"],
        "flame orb": ["Guts", "Marvel Scale"],
        "toxic orb": ["Poison Heal", "Guts", "Marvel Scale"],
        "booster energy": ["Protosynthesis", "Quark Drive"],
    }

    # Check if this item has known synergies
    preferred_abilities = synergies.get(item_lower, [])

    for preferred in preferred_abilities:
        preferred_lower = preferred.lower()
        for ability, usage in abilities.items():
            if ability.lower() == preferred_lower:
                return (ability, usage)

    # No synergy found - return the most common ability
    top_ability = list(abilities.keys())[0]
    return (top_ability, abilities[top_ability])


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Fetch the most common spread for a Pokemon from Smogon usage stats.

    Returns:
        dict with 'nature', 'evs', 'item', 'ability' keys, or None if not found
    """
    if _smogon_client is None:
        return None
    try:
        usage = await _smogon_client.get_pokemon_usage(pokemon_name)
        if usage and usage.get("spreads"):
            top_spread = usage["spreads"][0]
            items = usage.get("items", {})
            abilities = usage.get("abilities", {})
            top_item = list(items.keys())[0] if items else None

            # Get ability based on item synergy (e.g., Life Orb -> Sheer Force)
            top_ability, _ = _get_synergy_ability(top_item, abilities)

            return {
                "nature": top_spread.get("nature", "Serious"),
                "evs": top_spread.get("evs", {}),
                "usage": top_spread.get("usage", 0),
                "item": top_item,
                "ability": top_ability,
            }
    except Exception:
        pass
    return None


def register_spread_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register EV spread optimization tools with the MCP server."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def check_spread_efficiency(
        pokemon_name: str,
        nature: str,
        hp_evs: int = 0,
        atk_evs: int = 0,
        def_evs: int = 0,
        spa_evs: int = 0,
        spd_evs: int = 0,
        spe_evs: int = 0
    ) -> dict:
        """
        Check an EV spread for efficiency (wasted EVs, optimal distribution).

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature
            hp_evs through spe_evs: Current EV spread

        Returns:
            Analysis of spread efficiency with suggestions
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            total = hp_evs + atk_evs + def_evs + spa_evs + spd_evs + spe_evs
            issues = []
            suggestions = []

            # Check total EVs
            if total > 508:
                issues.append(f"Total EVs ({total}) exceed maximum of 508")
            elif total < 508:
                suggestions.append(f"You have {508 - total} EVs remaining to allocate")

            # Check for non-multiples of 4 (wasted EVs)
            evs = {
                "HP": hp_evs, "Attack": atk_evs, "Defense": def_evs,
                "Sp.Atk": spa_evs, "Sp.Def": spd_evs, "Speed": spe_evs
            }

            for stat_name, ev in evs.items():
                if ev % 4 != 0 and ev != 0:
                    wasted = ev % 4
                    issues.append(f"{stat_name}: {wasted} wasted EVs (not multiple of 4)")

            # Check for conflicting nature/EV investment
            nature_mods = {
                "attack": get_nature_modifier(parsed_nature, "attack"),
                "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
                "speed": get_nature_modifier(parsed_nature, "speed"),
            }

            if nature_mods["attack"] < 1.0 and atk_evs > 0:
                suggestions.append(f"Investing in Attack with -{nature} nature. Consider a neutral or +Atk nature.")

            if nature_mods["special_attack"] < 1.0 and spa_evs > 0:
                suggestions.append(f"Investing in Sp.Atk with -{nature} nature. Consider a neutral or +SpA nature.")

            # Calculate final stats
            final_stats = {
                "hp": calculate_hp(base_stats.hp, 31, hp_evs, 50),
                "attack": calculate_stat(base_stats.attack, 31, atk_evs, 50, nature_mods.get("attack", 1.0)),
                "defense": calculate_stat(base_stats.defense, 31, def_evs, 50, get_nature_modifier(parsed_nature, "defense")),
                "special_attack": calculate_stat(base_stats.special_attack, 31, spa_evs, 50, nature_mods.get("special_attack", 1.0)),
                "special_defense": calculate_stat(base_stats.special_defense, 31, spd_evs, 50, get_nature_modifier(parsed_nature, "special_defense")),
                "speed": calculate_stat(base_stats.speed, 31, spe_evs, 50, nature_mods.get("speed", 1.0)),
            }

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "total_evs": total,
                "remaining_evs": max(0, 508 - total),
                "final_stats": final_stats,
                "issues": issues if issues else ["No issues found"],
                "suggestions": suggestions if suggestions else ["Spread looks efficient!"],
                "is_valid": total <= 508 and not any("wasted" in i for i in issues)
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def optimize_bulk(
        pokemon_name: str,
        nature: str,
        total_bulk_evs: int = 252,
        defense_bias: float = 0.5
    ) -> dict:
        """
        Optimize HP/Def/SpD EVs for maximum bulk.

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature
            total_bulk_evs: Total EVs to allocate to bulk (default 252)
            defense_bias: 0.5 = balanced, 1.0 = physical, 0.0 = special

        Returns:
            Optimal HP/Def/SpD distribution
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Simple optimization: balance HP with defenses based on bias
            # General rule: invest in HP until it's ~2x each defense stat

            best_spread = None
            best_bulk = 0

            # Try different distributions (level 50 breakpoints: 0, 4, 12, 20, 28...)
            for hp_ev in EV_BREAKPOINTS_LV50:
                if hp_ev > min(252, total_bulk_evs):
                    break
                remaining = total_bulk_evs - hp_ev
                for def_ev in EV_BREAKPOINTS_LV50:
                    if def_ev > min(252, remaining):
                        break
                    spd_ev = normalize_evs(remaining - def_ev)
                    if spd_ev < 0:
                        continue

                    hp = calculate_hp(base_stats.hp, 31, hp_ev, 50)
                    def_stat = calculate_stat(
                        base_stats.defense, 31, def_ev, 50,
                        get_nature_modifier(parsed_nature, "defense")
                    )
                    spd_stat = calculate_stat(
                        base_stats.special_defense, 31, spd_ev, 50,
                        get_nature_modifier(parsed_nature, "special_defense")
                    )

                    # Calculate effective bulk (HP * Def for physical, HP * SpD for special)
                    phys_bulk = hp * def_stat
                    spec_bulk = hp * spd_stat
                    total_bulk = phys_bulk * defense_bias + spec_bulk * (1 - defense_bias)

                    if total_bulk > best_bulk:
                        best_bulk = total_bulk
                        best_spread = {
                            "hp_evs": hp_ev,
                            "def_evs": def_ev,
                            "spd_evs": spd_ev,
                            "final_hp": hp,
                            "final_def": def_stat,
                            "final_spd": spd_stat,
                            "physical_bulk": phys_bulk,
                            "special_bulk": spec_bulk
                        }

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "total_bulk_evs": total_bulk_evs,
                "defense_bias": defense_bias,
                "optimal_spread": best_spread
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def suggest_spread(
        pokemon_name: str,
        role: str = "offensive",
        speed_target: Optional[int] = None
    ) -> dict:
        """
        Suggest an EV spread based on role.

        Args:
            pokemon_name: Pokemon name
            role: "offensive" (max offensive stat + speed), "bulky" (HP + defenses),
                  "bulky_offense" (some bulk + offense), "support" (bulk focused)
            speed_target: Optional specific speed stat to hit

        Returns:
            Suggested spread with reasoning
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            # Determine if physical or special attacker
            is_physical = base_stats.attack > base_stats.special_attack
            offensive_stat = "Attack" if is_physical else "Sp. Atk"

            spreads = {
                "offensive": {
                    "description": f"Max {offensive_stat} and Speed for maximum damage output",
                    "nature": "Jolly" if is_physical else "Timid",
                    "evs": {
                        "hp": 0,
                        "attack": 252 if is_physical else 0,
                        "defense": 0,
                        "special_attack": 0 if is_physical else 252,
                        "special_defense": 4,
                        "speed": 252
                    }
                },
                "bulky": {
                    "description": "Maximum HP with balanced defenses",
                    "nature": "Calm" if base_stats.special_defense > base_stats.defense else "Bold",
                    "evs": {
                        "hp": 252,
                        "attack": 0,
                        "defense": 128,
                        "special_attack": 0,
                        "special_defense": 128,
                        "speed": 0
                    }
                },
                "bulky_offense": {
                    "description": f"Some bulk while maintaining {offensive_stat}",
                    "nature": "Adamant" if is_physical else "Modest",
                    "evs": {
                        "hp": 252,
                        "attack": 252 if is_physical else 0,
                        "defense": 0,
                        "special_attack": 0 if is_physical else 252,
                        "special_defense": 4,
                        "speed": 0
                    }
                },
                "support": {
                    "description": "Maximum bulk for supporting the team",
                    "nature": "Bold",
                    "evs": {
                        "hp": 252,
                        "attack": 0,
                        "defense": 252,
                        "special_attack": 0,
                        "special_defense": 4,
                        "speed": 0
                    }
                }
            }

            if role not in spreads:
                return {"error": f"Unknown role: {role}. Use: offensive, bulky, bulky_offense, support"}

            spread = spreads[role]

            # If speed target specified, adjust
            if speed_target and role == "offensive":
                # Calculate EVs needed
                nature = Nature(spread["nature"].lower())
                needed = find_speed_evs(base_stats.speed, speed_target, nature)

                if needed is not None and needed < 252:
                    leftover = normalize_evs(252 - needed)
                    spread["evs"]["speed"] = normalize_evs(needed)
                    spread["evs"]["hp"] = leftover
                    spread["description"] += f" (Speed creep to {speed_target})"

            return {
                "pokemon": pokemon_name,
                "role": role,
                "suggestion": spread,
                "base_stats": {
                    "hp": base_stats.hp,
                    "attack": base_stats.attack,
                    "defense": base_stats.defense,
                    "special_attack": base_stats.special_attack,
                    "special_defense": base_stats.special_defense,
                    "speed": base_stats.speed
                }
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def optimize_bulk_math(
        pokemon_name: str,
        nature: str,
        total_bulk_evs: int = 252,
        defense_weight: float = 0.5
    ) -> dict:
        """
        Find mathematically optimal HP/Def/SpD using diminishing returns analysis.

        This uses the principle that Effective Bulk = HP * Defense, and optimal
        distribution is when marginal gains are equal across stats.

        Key insights:
        - High base HP Pokemon should invest more in defenses
        - High base Def/SpD Pokemon should invest more in HP
        - Nature boosts reduce EV investment needed in that stat

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature (e.g., "Bold", "Calm", "Careful")
            total_bulk_evs: Total EVs to distribute (default 252)
            defense_weight: 0.0 = all SpD, 0.5 = balanced, 1.0 = all Def

        Returns:
            Optimal distribution with efficiency comparison vs naive allocation
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Use the mathematical optimizer
            result = calculate_optimal_bulk_distribution(
                base_hp=base_stats.hp,
                base_def=base_stats.defense,
                base_spd=base_stats.special_defense,
                nature=nature,
                total_bulk_evs=total_bulk_evs,
                defense_weight=defense_weight
            )

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "base_stats": {
                    "hp": base_stats.hp,
                    "defense": base_stats.defense,
                    "special_defense": base_stats.special_defense
                },
                "total_bulk_evs": total_bulk_evs,
                "defense_weight": defense_weight,
                "optimal_spread": {
                    "hp_evs": result.hp_evs,
                    "def_evs": result.def_evs,
                    "spd_evs": result.spd_evs
                },
                "final_stats": {
                    "hp": result.final_hp,
                    "defense": result.final_def,
                    "special_defense": result.final_spd
                },
                "bulk_scores": {
                    "physical_bulk": result.physical_bulk,
                    "special_bulk": result.special_bulk,
                    "total_bulk": result.total_bulk
                },
                "efficiency_score": result.efficiency_score,
                "explanation": result.explanation,
                "comparison_vs_naive": result.comparison
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def analyze_bulk_diminishing_returns(
        pokemon_name: str,
        nature: str
    ) -> dict:
        """
        Analyze diminishing returns for HP, Def, and SpD investment.

        Shows how the value of each additional EV investment decreases
        as you invest more in a stat, helping you understand optimal breakpoints.

        Args:
            pokemon_name: Pokemon name
            nature: Pokemon's nature

        Returns:
            Marginal gain analysis for each stat at different EV thresholds
        """
        try:
            base_stats = await pokeapi.get_base_stats(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            analysis = analyze_diminishing_returns(
                base_hp=base_stats.hp,
                base_def=base_stats.defense,
                base_spd=base_stats.special_defense,
                nature=nature
            )

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "base_stats": {
                    "hp": base_stats.hp,
                    "defense": base_stats.defense,
                    "special_defense": base_stats.special_defense
                },
                "marginal_gains": {
                    "hp": analysis["hp_gains"],
                    "defense": analysis["def_gains"],
                    "special_defense": analysis["spd_gains"]
                },
                "recommendations": analysis["recommendations"],
                "interpretation": (
                    "Higher marginal gain means better EV efficiency at that threshold. "
                    "Invest where marginal gains are highest, then balance."
                )
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def design_spread_with_benchmarks(
        pokemon_name: str,
        nature: str,
        outspeed_pokemon: Optional[str] = None,
        outspeed_pokemon_nature: str = "jolly",
        outspeed_pokemon_evs: int = 252,
        survive_pokemon: Optional[str] = None,
        survive_move: Optional[str] = None,
        survive_pokemon_nature: str = "adamant",
        survive_pokemon_evs: int = 252,
        survive_pokemon_ability: Optional[str] = None,
        survive_pokemon_item: Optional[str] = None,
        survive_pokemon_tera_type: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        prioritize: str = "bulk",
        offensive_evs: int = 0
    ) -> dict:
        """
        Design an EV spread that meets specific speed and survival benchmarks.

        IMPORTANT - ASK ABOUT TERA BEFORE CALLING:
        Before using this tool for survival calculations, ASK the user:
        1. "Is the attacking Pokemon Terastallized? If so, what type?"
        2. "Is your Pokemon Terastallizing? If so, what type?"

        Tera significantly changes damage calculations:
        - Same-type Tera boosts STAB moves by 33% (1.5x -> 2.0x)
        - Tera changes defensive typing (e.g., Tera Normal removes all weaknesses)

        Do NOT assume no Tera - always clarify with the user first.

        Args:
            pokemon_name: Your Pokemon
            nature: Your Pokemon's nature (e.g., "jolly", "adamant")
            outspeed_pokemon: Pokemon to outspeed
            outspeed_pokemon_nature: Target's nature (default: jolly)
            outspeed_pokemon_evs: Target's speed EVs (default: 252)
            survive_pokemon: Attacker to survive
            survive_move: Move to survive
            survive_pokemon_nature: Attacker's nature (default: adamant)
            survive_pokemon_evs: Attacker's offensive EVs (default: 252)
            survive_pokemon_ability: Attacker's ability if relevant
            survive_pokemon_item: Attacker's item (e.g., "choice-band")
            survive_pokemon_tera_type: Attacker's Tera type if Terastallized - ASK USER FIRST!
            defender_tera_type: Your Pokemon's Tera type if Terastallizing - ASK USER FIRST!
            prioritize: "bulk" (max bulk after speed) or "offense" (specified offensive EVs)
            offensive_evs: Attack/SpA EVs if prioritize="offense"

        Returns:
            Complete EV spread with final stats and survival calc
        """
        try:
            # Fetch our Pokemon's data
            my_base = await pokeapi.get_base_stats(pokemon_name)
            my_types = await pokeapi.get_pokemon_types(pokemon_name)
            parsed_nature = Nature(nature.lower())

            results = {
                "pokemon": pokemon_name,
                "nature": nature,
                "benchmarks": {}
            }

            # 1. Calculate speed benchmark
            speed_evs_needed = 0
            target_speed = 0

            if outspeed_pokemon:
                try:
                    target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                    target_nature = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature, "speed")
                    target_speed = calculate_stat(
                        target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )

                    # Find minimum EVs to outspeed (level 50 breakpoints)
                    my_speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(my_base.speed, 31, ev, 50, my_speed_mod)
                        if my_speed > target_speed:
                            speed_evs_needed = ev
                            break
                    else:
                        speed_evs_needed = 252  # Max out if can't outspeed

                    results["benchmarks"]["speed"] = {
                        "target": outspeed_pokemon,
                        "target_speed": target_speed,
                        "evs_needed": speed_evs_needed,
                        "my_speed": calculate_stat(my_base.speed, 31, speed_evs_needed, 50, my_speed_mod),
                        "outspeeds": calculate_stat(my_base.speed, 31, speed_evs_needed, 50, my_speed_mod) > target_speed
                    }
                except Exception as e:
                    results["benchmarks"]["speed"] = {"error": str(e)}

            # 2. Calculate remaining EVs for bulk/offense
            remaining_evs = 508 - speed_evs_needed

            # Auto-fill offensive_evs to 252 when prioritize=offense but no value given
            if prioritize == "offense" and offensive_evs == 0:
                offensive_evs = 252

            if prioritize == "offense" and offensive_evs > 0:
                atk_evs = min(offensive_evs, remaining_evs)
                remaining_evs -= atk_evs
            else:
                atk_evs = 0

            # 3. Distribute remaining EVs to bulk
            # If we have a survival benchmark, optimize for that
            hp_evs = 0
            def_evs = 0
            spd_evs = 0

            if survive_pokemon and survive_move:
                try:
                    atk_base = await pokeapi.get_base_stats(survive_pokemon)
                    atk_types = await pokeapi.get_pokemon_types(survive_pokemon)
                    move = await pokeapi.get_move(survive_move)

                    is_physical = move.category == MoveCategory.PHYSICAL

                    # Fetch attacker's most common spread from Smogon if not specified
                    smogon_spread = await _get_common_spread(survive_pokemon)
                    smogon_used = False

                    if smogon_spread:
                        # Use Smogon spread if user didn't override
                        if survive_pokemon_nature == "adamant":  # default value - replace with Smogon
                            survive_pokemon_nature = smogon_spread.get("nature", survive_pokemon_nature)
                            smogon_used = True
                        if survive_pokemon_evs == 252:  # default value - replace with Smogon
                            evs = smogon_spread.get("evs", {})
                            if is_physical:
                                survive_pokemon_evs = evs.get("attack", 252)
                            else:
                                survive_pokemon_evs = evs.get("special_attack", 252)
                            smogon_used = True
                        if survive_pokemon_item is None:
                            survive_pokemon_item = smogon_spread.get("item")
                            smogon_used = True
                        if survive_pokemon_ability is None:
                            survive_pokemon_ability = smogon_spread.get("ability")
                            smogon_used = True

                    atk_nature = Nature(survive_pokemon_nature.lower())
                    atk_nature_mod = get_nature_modifier(
                        atk_nature,
                        "attack" if is_physical else "special_attack"
                    )

                    # Auto-detect Unseen Fist for Urshifu forms
                    normalized_attacker = survive_pokemon.lower().replace(" ", "-")
                    if normalized_attacker in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                        if not survive_pokemon_ability:
                            survive_pokemon_ability = "unseen-fist"

                    # Create attacker build
                    attacker = PokemonBuild(
                        name=survive_pokemon,
                        base_stats=atk_base,
                        types=atk_types,
                        nature=atk_nature,
                        evs=EVSpread(
                            attack=survive_pokemon_evs if is_physical else 0,
                            special_attack=0 if is_physical else survive_pokemon_evs
                        ),
                        ability=survive_pokemon_ability,
                        item=survive_pokemon_item,
                        tera_type=survive_pokemon_tera_type
                    )

                    # Find optimal bulk distribution to survive
                    best_survival = 0
                    best_spread = {"hp": 0, "def": 0, "spd": 0}

                    # Try different HP/Def distributions (level 50 breakpoints)
                    for hp_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev > min(252, remaining_evs):
                            break
                        def_remaining = remaining_evs - hp_ev
                        def_ev = normalize_evs(min(252, def_remaining)) if is_physical else 0
                        spd_ev = normalize_evs(min(252, def_remaining)) if not is_physical else 0

                        # Create defender build (preserve original types, Tera handled by modifiers)
                        defender = PokemonBuild(
                            name=pokemon_name,
                            base_stats=my_base,
                            types=my_types,
                            nature=parsed_nature,
                            evs=EVSpread(
                                hp=hp_ev,
                                defense=def_ev,
                                special_defense=spd_ev
                            ),
                            tera_type=defender_tera_type
                        )

                        # Calculate damage
                        modifiers = DamageModifiers(
                            is_doubles=True,
                            attacker_ability=survive_pokemon_ability,
                            attacker_item=survive_pokemon_item,
                            # Attacker Tera
                            tera_type=survive_pokemon_tera_type,
                            tera_active=survive_pokemon_tera_type is not None,
                            # Defender Tera
                            defender_tera_type=defender_tera_type,
                            defender_tera_active=defender_tera_type is not None,
                            # Handle always-crit moves like Surging Strikes
                            is_critical=move.always_crit
                        )
                        result = calculate_damage(attacker, defender, move, modifiers)

                        # Check survival (want max damage < 100%)
                        survival_margin = 100 - result.max_percent
                        if survival_margin > best_survival:
                            best_survival = survival_margin
                            best_spread = {"hp": hp_ev, "def": def_ev, "spd": spd_ev}
                            best_result = result

                    hp_evs = best_spread["hp"]
                    def_evs = best_spread["def"]
                    spd_evs = best_spread["spd"]

                    # Check if attacker has Unseen Fist (bypasses Protect)
                    has_unseen_fist = (
                        survive_pokemon_ability and
                        survive_pokemon_ability.lower().replace(" ", "-") == "unseen-fist"
                    )

                    # Calculate attacker's final stats for the spread display
                    atk_nature_mod_atk = get_nature_modifier(atk_nature, "attack")
                    atk_nature_mod_spa = get_nature_modifier(atk_nature, "special_attack")
                    attacker_final_atk = calculate_stat(atk_base.attack, 31, survive_pokemon_evs if is_physical else 0, 50, atk_nature_mod_atk)
                    attacker_final_spa = calculate_stat(atk_base.special_attack, 31, 0 if is_physical else survive_pokemon_evs, 50, atk_nature_mod_spa)
                    attacker_final_hp = calculate_hp(atk_base.hp, 31, 0, 50)

                    # Build attacker spread string (Showdown format: "252+ Atk")
                    stat_name = "Atk" if is_physical else "SpA"
                    nature_boost = "+" if (is_physical and atk_nature_mod_atk > 1.0) or (not is_physical and atk_nature_mod_spa > 1.0) else ""
                    nature_penalty = "-" if (is_physical and atk_nature_mod_atk < 1.0) or (not is_physical and atk_nature_mod_spa < 1.0) else ""
                    nature_indicator = nature_boost or nature_penalty
                    item_str = f" {survive_pokemon_item.replace('-', ' ').title()}" if survive_pokemon_item else ""
                    attacker_spread_str = f"{survive_pokemon_evs}{nature_indicator} {stat_name}{item_str} {survive_pokemon}"

                    # Build defender spread string
                    relevant_def_evs = best_spread["def"] if is_physical else best_spread["spd"]
                    def_stat_name = "Def" if is_physical else "SpD"
                    defender_spread_str = f"{best_spread['hp']} HP / {relevant_def_evs} {def_stat_name} {pokemon_name}"

                    # Build analysis string
                    analysis_str = f"{attacker_spread_str}'s {survive_move} vs {defender_spread_str}: {best_result.min_percent:.1f}-{best_result.max_percent:.1f}%"

                    results["benchmarks"]["survival"] = {
                        "attacker": survive_pokemon,
                        "move": survive_move,
                        "attacker_spread": attacker_spread_str,
                        "attacker_nature": survive_pokemon_nature,
                        "attacker_evs": survive_pokemon_evs,
                        "attacker_ability": survive_pokemon_ability,
                        "attacker_item": survive_pokemon_item,
                        "attacker_tera": survive_pokemon_tera_type,
                        "attacker_final_stats": {
                            "hp": attacker_final_hp,
                            "attack": attacker_final_atk,
                            "special_attack": attacker_final_spa
                        },
                        "smogon_spread_used": smogon_used,
                        "defender_tera": defender_tera_type,
                        "damage_range": best_result.damage_range,
                        "damage_percent": f"{best_result.min_percent:.1f}-{best_result.max_percent:.1f}%",
                        "survives": best_result.max_percent < 100,
                        "hp_remaining": f"{100 - best_result.max_percent:.1f}%",
                        "analysis": analysis_str,
                        "unseen_fist_warning": (
                            "WARNING: Attacker has Unseen Fist - contact moves bypass Protect!"
                            if has_unseen_fist else None
                        )
                    }

                except Exception as e:
                    results["benchmarks"]["survival"] = {"error": str(e)}
                    # Default bulk distribution
                    hp_evs = min(252, remaining_evs)
                    remaining_evs -= hp_evs
                    def_evs = min(252, remaining_evs)
            else:
                # No survival benchmark, just max HP
                hp_evs = normalize_evs(min(252, remaining_evs))
                remaining_evs -= hp_evs
                def_evs = normalize_evs(min(252, remaining_evs // 2))
                spd_evs = normalize_evs(min(252, remaining_evs - def_evs))

            # Ensure EVs total 508 - distribute leftover based on user intent
            total_used = hp_evs + atk_evs + def_evs + spd_evs + speed_evs_needed

            if total_used < 508:
                leftover = 508 - total_used

                # Priority 1: Speed creep (if user provided speed benchmark)
                # User cares about speed - add more to beat others targeting same tier
                if leftover > 0 and outspeed_pokemon and speed_evs_needed < 252:
                    extra_spe = min(252 - speed_evs_needed, leftover)
                    speed_evs_needed += extra_spe
                    leftover -= extra_spe

                # Priority 2 & 3: Optimal bulk distribution based on base stats
                # Use mathematical optimization: effective bulk = HP * Def
                # High base HP → invest more in defenses; High base Def → invest more in HP
                if leftover > 0:
                    # Determine which defense stat to optimize based on survival benchmark
                    optimize_physical = True  # Default to balanced
                    if survive_pokemon and survive_move:
                        try:
                            move_check = await pokeapi.get_move(survive_move)
                            optimize_physical = move_check.category == MoveCategory.PHYSICAL
                        except Exception:
                            pass

                    # Calculate current final stats to determine optimal distribution
                    current_hp = calculate_hp(my_base.hp, 31, hp_evs, 50)
                    def_mod = get_nature_modifier(parsed_nature, "defense")
                    spd_mod = get_nature_modifier(parsed_nature, "special_defense")
                    current_def = calculate_stat(my_base.defense, 31, def_evs, 50, def_mod)
                    current_spd = calculate_stat(my_base.special_defense, 31, spd_evs, 50, spd_mod)

                    # Optimal bulk is when HP ≈ Defense (marginal gains equal)
                    # If HP >> Def, invest in Def; if Def >> HP, invest in HP
                    target_def = current_def if optimize_physical else current_spd

                    while leftover > 0:
                        # Recalculate current stats
                        current_hp = calculate_hp(my_base.hp, 31, hp_evs, 50)
                        if optimize_physical:
                            current_def = calculate_stat(my_base.defense, 31, def_evs, 50, def_mod)
                            target_def = current_def
                            can_add_def = def_evs < 252
                        else:
                            current_spd = calculate_stat(my_base.special_defense, 31, spd_evs, 50, spd_mod)
                            target_def = current_spd
                            can_add_def = spd_evs < 252
                        can_add_hp = hp_evs < 252

                        # If HP > Defense, invest in defense; otherwise invest in HP
                        if current_hp > target_def and can_add_def:
                            if optimize_physical:
                                def_evs = min(252, def_evs + 4)
                            else:
                                spd_evs = min(252, spd_evs + 4)
                            leftover -= 4
                        elif can_add_hp:
                            hp_evs = min(252, hp_evs + 4)
                            leftover -= 4
                        elif can_add_def:
                            if optimize_physical:
                                def_evs = min(252, def_evs + 4)
                            else:
                                spd_evs = min(252, spd_evs + 4)
                            leftover -= 4
                        else:
                            # All relevant stats maxed, put remainder in other defense
                            if optimize_physical:
                                spd_evs = min(252, spd_evs + leftover)
                            else:
                                def_evs = min(252, def_evs + leftover)
                            leftover = 0

            # 4. Calculate final stats
            speed_mod = get_nature_modifier(parsed_nature, "speed")
            atk_mod = get_nature_modifier(parsed_nature, "attack")
            spa_mod = get_nature_modifier(parsed_nature, "special_attack")
            def_mod = get_nature_modifier(parsed_nature, "defense")
            spd_mod = get_nature_modifier(parsed_nature, "special_defense")

            final_stats = {
                "hp": calculate_hp(my_base.hp, 31, hp_evs, 50),
                "attack": calculate_stat(my_base.attack, 31, atk_evs if my_base.attack > my_base.special_attack else 0, 50, atk_mod),
                "defense": calculate_stat(my_base.defense, 31, def_evs, 50, def_mod),
                "special_attack": calculate_stat(my_base.special_attack, 31, atk_evs if my_base.special_attack > my_base.attack else 0, 50, spa_mod),
                "special_defense": calculate_stat(my_base.special_defense, 31, spd_evs, 50, spd_mod),
                "speed": calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_mod)
            }

            # Determine which offensive stat to use
            is_physical = my_base.attack > my_base.special_attack

            results["spread"] = {
                "hp_evs": hp_evs,
                "atk_evs": atk_evs if is_physical else 0,
                "def_evs": def_evs,
                "spa_evs": 0 if is_physical else atk_evs,
                "spd_evs": spd_evs,
                "spe_evs": speed_evs_needed,
                "total": hp_evs + atk_evs + def_evs + spd_evs + speed_evs_needed
            }
            results["final_stats"] = final_stats
            results["summary"] = (
                f"{pokemon_name.title()} @ {nature.title()}: "
                f"{hp_evs} HP / {atk_evs} {'Atk' if is_physical else 'SpA'} / "
                f"{def_evs} Def / {spd_evs} SpD / {speed_evs_needed} Spe"
            )

            return results

        except Exception as e:
            return {"error": str(e)}