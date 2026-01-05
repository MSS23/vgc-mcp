"""MCP tools for EV spread optimization."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.config import logger
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
from vgc_mcp_core.utils.synergies import get_synergy_ability


# Module-level Smogon client reference (set during registration)
_smogon_client: Optional[SmogonStatsClient] = None


# Known meta synergies: Pokemon -> (item, ability) defaults
# Used as fallback when Smogon data is unavailable
META_SYNERGIES = {
    "landorus": ("Life Orb", "Sheer Force"),
    "landorus-incarnate": ("Life Orb", "Sheer Force"),
    "nidoking": ("Life Orb", "Sheer Force"),
    "nidoqueen": ("Life Orb", "Sheer Force"),
    "toucannon": ("Life Orb", "Sheer Force"),
    "conkeldurr": ("Flame Orb", "Guts"),
    "ursaluna": ("Flame Orb", "Guts"),
    "ursaluna-bloodmoon": ("Life Orb", "Mind's Eye"),
    "urshifu": ("Choice Band", "Unseen Fist"),
    "urshifu-single-strike": ("Choice Band", "Unseen Fist"),
    "urshifu-rapid-strike": ("Choice Band", "Unseen Fist"),
    # Ogerpon forms with their signature masks
    "ogerpon": ("Teal Mask", "Defiant"),
    "ogerpon-teal-mask": ("Teal Mask", "Defiant"),
    "ogerpon-hearthflame": ("Hearthflame Mask", "Mold Breaker"),
    "ogerpon-wellspring": ("Wellspring Mask", "Water Absorb"),
    "ogerpon-cornerstone": ("Cornerstone Mask", "Sturdy"),
    # Treasures of Ruin - auto-detect Ruinous abilities
    "chien-pao": ("Focus Sash", "Sword of Ruin"),
    "chi-yu": ("Choice Specs", "Beads of Ruin"),
    "ting-lu": ("Leftovers", "Vessel of Ruin"),
    "wo-chien": ("Rocky Helmet", "Tablets of Ruin"),
}


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
            top_ability, _ = get_synergy_ability(top_item, abilities)

            return {
                "nature": top_spread.get("nature", "Serious"),
                "evs": top_spread.get("evs", {}),
                "usage": top_spread.get("usage", 0),
                "item": top_item,
                "ability": top_ability,
            }
    except Exception as e:
        logger.warning(f"Failed to fetch Smogon spread for {pokemon_name}: {e}")
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

    # Speed stage multipliers (Gen 9)
    SPEED_STAGE_MULTIPLIERS = {
        -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
        0: 1,
        1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
    }

    @mcp.tool()
    async def design_spread_with_benchmarks(
        pokemon_name: str,
        nature: str,
        outspeed_pokemon: Optional[str] = None,
        outspeed_pokemon_nature: str = "jolly",
        outspeed_pokemon_evs: int = 252,
        outspeed_at_speed_stage: int = 0,
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
        Design an EV spread that meets specific speed and SINGLE survival benchmarks.

        Use this when asked questions like:
        - "I need Entei to survive Surging Strikes and outspeed Chien-Pao"
        - "Make my Flutter Mane live Sacred Sword while being faster than Rillaboom"
        - "Build a max Attack Entei that outspeeds Chien-Pao after Icy Wind"

        For surviving TWO DIFFERENT attacks, use optimize_dual_survival_spread instead.

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
            outspeed_at_speed_stage: Target's speed stage (-1 = after Icy Wind, -2 = after 2x Icy Wind, etc.)
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

                    # Apply speed stage modifier (e.g., -1 for after Icy Wind)
                    original_target_speed = target_speed
                    if outspeed_at_speed_stage != 0:
                        stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                        target_speed = int(target_speed * stage_mult)

                    # Find minimum EVs to outspeed (level 50 breakpoints)
                    my_speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(my_base.speed, 31, ev, 50, my_speed_mod)
                        if my_speed > target_speed:
                            speed_evs_needed = ev
                            break
                    else:
                        speed_evs_needed = 252  # Max out if can't outspeed

                    speed_benchmark = {
                        "target": outspeed_pokemon,
                        "target_speed": target_speed,
                        "evs_needed": speed_evs_needed,
                        "my_speed": calculate_stat(my_base.speed, 31, speed_evs_needed, 50, my_speed_mod),
                        "outspeeds": calculate_stat(my_base.speed, 31, speed_evs_needed, 50, my_speed_mod) > target_speed
                    }
                    # Add speed stage info if applicable
                    if outspeed_at_speed_stage != 0:
                        speed_benchmark["target_base_speed"] = original_target_speed
                        speed_benchmark["target_speed_stage"] = outspeed_at_speed_stage
                        stage_name = "after Icy Wind" if outspeed_at_speed_stage == -1 else f"at {outspeed_at_speed_stage:+d} stage"
                        speed_benchmark["speed_stage_note"] = f"Target at {target_speed} Speed ({stage_name})"
                    results["benchmarks"]["speed"] = speed_benchmark
                except Exception as e:
                    results["benchmarks"]["speed"] = {"error": str(e)}

            # 2. Calculate remaining EVs for bulk/offense
            remaining_evs = 508 - speed_evs_needed

            # Auto-fill offensive_evs to 252 when prioritize=offense but no value given
            if prioritize == "offense" and offensive_evs == 0:
                offensive_evs = 252

            if prioritize == "offense" and offensive_evs > 0:
                atk_evs = normalize_evs(min(offensive_evs, remaining_evs))
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
                    move = await pokeapi.get_move(survive_move, user_name=survive_pokemon)

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

                    # Fallback to known meta synergies if Smogon didn't provide item/ability
                    attacker_key = survive_pokemon.lower().replace(" ", "-")
                    if attacker_key in META_SYNERGIES:
                        default_item, default_ability = META_SYNERGIES[attacker_key]
                        if survive_pokemon_item is None:
                            survive_pokemon_item = default_item
                        if survive_pokemon_ability is None:
                            survive_pokemon_ability = default_ability

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

                    # Auto-detect Ruinous abilities from attacker
                    sword_of_ruin = False
                    beads_of_ruin = False
                    if survive_pokemon_ability:
                        ability_lower = survive_pokemon_ability.lower().replace(" ", "-").replace("_", "-")
                        if ability_lower == "sword-of-ruin":
                            sword_of_ruin = True
                        elif ability_lower == "beads-of-ruin":
                            beads_of_ruin = True
                    else:
                        # If no ability specified, auto-detect from Pokemon
                        atk_abilities = await pokeapi.get_pokemon_abilities(survive_pokemon)
                        if atk_abilities:
                            ability_lower = atk_abilities[0].lower().replace(" ", "-")
                            if ability_lower == "sword-of-ruin":
                                sword_of_ruin = True
                                survive_pokemon_ability = "sword-of-ruin"
                            elif ability_lower == "beads-of-ruin":
                                beads_of_ruin = True
                                survive_pokemon_ability = "beads-of-ruin"

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
                    # Math: Effective Bulk = HP × Defense
                    # When HP stat < Def stat, HP EVs are more efficient (benefits both Def and SpD)
                    # We need to try ALL valid (HP, Def) combinations, not just extremes
                    best_survival = -1000
                    best_spread = {"hp": 0, "def": 0, "spd": 0}
                    best_result = None

                    # Get nature modifiers for defense stats
                    def_nature_mod = get_nature_modifier(parsed_nature, "defense")
                    spd_nature_mod = get_nature_modifier(parsed_nature, "special_defense")

                    # Try ALL valid (HP, Def/SpD) combinations
                    for hp_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev > min(252, remaining_evs):
                            break

                        # Determine which defense stat to optimize
                        def_stat_evs = EV_BREAKPOINTS_LV50 if is_physical else [0]
                        spd_stat_evs = [0] if is_physical else EV_BREAKPOINTS_LV50

                        for def_ev in def_stat_evs:
                            if hp_ev + def_ev > remaining_evs:
                                break
                            for spd_ev in spd_stat_evs:
                                if hp_ev + def_ev + spd_ev > remaining_evs:
                                    break

                                # Normalize EVs to valid breakpoints
                                def_ev_norm = normalize_evs(min(252, def_ev))
                                spd_ev_norm = normalize_evs(min(252, spd_ev))

                                # Create defender build
                                defender = PokemonBuild(
                                    name=pokemon_name,
                                    base_stats=my_base,
                                    types=my_types,
                                    nature=parsed_nature,
                                    evs=EVSpread(
                                        hp=hp_ev,
                                        defense=def_ev_norm,
                                        special_defense=spd_ev_norm
                                    ),
                                    tera_type=defender_tera_type
                                )

                                # Calculate damage
                                modifiers = DamageModifiers(
                                    is_doubles=True,
                                    attacker_ability=survive_pokemon_ability,
                                    attacker_item=survive_pokemon_item,
                                    tera_type=survive_pokemon_tera_type,
                                    tera_active=survive_pokemon_tera_type is not None,
                                    defender_tera_type=defender_tera_type,
                                    defender_tera_active=defender_tera_type is not None,
                                    is_critical=move.always_crit,
                                    sword_of_ruin=sword_of_ruin,
                                    beads_of_ruin=beads_of_ruin
                                )
                                result = calculate_damage(attacker, defender, move, modifiers)

                                # Calculate effective bulk for tiebreaker
                                final_hp = calculate_hp(my_base.hp, 31, hp_ev, 50)
                                if is_physical:
                                    final_def = calculate_stat(my_base.defense, 31, def_ev_norm, 50, def_nature_mod)
                                else:
                                    final_def = calculate_stat(my_base.special_defense, 31, spd_ev_norm, 50, spd_nature_mod)
                                effective_bulk = final_hp * final_def

                                # Score: survival margin is priority, then minimum EVs, bulk as tiebreaker
                                survival_margin = 100 - result.max_percent
                                # Prefer: 1) highest survival, 2) minimum EVs, 3) highest bulk
                                total_defensive_evs = hp_ev + def_ev_norm + spd_ev_norm
                                score = survival_margin - (total_defensive_evs / 10000) + (effective_bulk / 100000000)

                                if score > best_survival:
                                    best_survival = score
                                    best_spread = {"hp": hp_ev, "def": def_ev_norm, "spd": spd_ev_norm}
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

                    # Normalize all EVs to valid breakpoints after distribution
                    hp_evs = normalize_evs(hp_evs)
                    def_evs = normalize_evs(def_evs)
                    spd_evs = normalize_evs(spd_evs)

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

    @mcp.tool()
    async def optimize_dual_survival_spread(
        pokemon_name: str,
        nature: str,
        survive_hit1_attacker: str,
        survive_hit1_move: str,
        survive_hit2_attacker: str,
        survive_hit2_move: str,
        outspeed_pokemon: Optional[str] = None,
        outspeed_pokemon_nature: str = "timid",
        outspeed_pokemon_evs: int = 252,
        speed_evs: Optional[int] = None,
        survive_hit1_nature: Optional[str] = None,
        survive_hit1_evs: Optional[int] = None,
        survive_hit1_item: Optional[str] = None,
        survive_hit1_ability: Optional[str] = None,
        survive_hit1_tera_type: Optional[str] = None,
        survive_hit2_nature: Optional[str] = None,
        survive_hit2_evs: Optional[int] = None,
        survive_hit2_item: Optional[str] = None,
        survive_hit2_ability: Optional[str] = None,
        survive_hit2_tera_type: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        target_survival: float = 93.75
    ) -> dict:
        """
        Find optimal EV spread to survive TWO DIFFERENT attacks while meeting a speed benchmark.

        IMPORTANT - WHEN TO USE THIS TOOL:
        - Use ONLY when the user wants to survive TWO DIFFERENT attacks from TWO DIFFERENT attackers
        - Examples: "survive Wicked Blow AND Sludge Bomb", "live both Moonblast and Sacred Sword"

        DO NOT USE THIS TOOL when:
        - User only mentions ONE attacker or ONE move (use design_spread_with_benchmarks instead)
        - User wants to survive the same attack twice (that's a 2HKO check, not dual survival)
        - User is asking about max Attack/SpA builds (use design_spread_with_benchmarks with prioritize="offense")

        Use this when asked questions like:
        - "I want my Ogerpon-Wellspring to survive Tera Dark Wicked Blow AND Sludge Bomb"
        - "Can Rillaboom live both Moonblast from Flutter Mane AND Heat Wave from Tornadus?"

        This tool searches ALL valid (HP, Def, SpD) combinations to find the optimal spread,
        or reports if the benchmarks are mathematically impossible.

        Args:
            pokemon_name: Your Pokemon (e.g., "ogerpon-wellspring")
            nature: Your Pokemon's nature (e.g., "jolly")
            survive_hit1_attacker: First attacker to survive (e.g., "urshifu") - MUST be different from hit2
            survive_hit1_move: First move to survive (e.g., "wicked-blow")
            survive_hit2_attacker: Second attacker to survive (e.g., "landorus-incarnate") - MUST be different from hit1
            survive_hit2_move: Second move to survive (e.g., "sludge-bomb")
            outspeed_pokemon: Pokemon to outspeed (optional)
            outspeed_pokemon_nature: Target's nature (default "timid")
            outspeed_pokemon_evs: Target's speed EVs (default 252)
            speed_evs: Override speed EVs directly instead of calculating from outspeed target
            survive_hit1_nature: First attacker's nature (auto-fetched from Smogon if not specified)
            survive_hit1_evs: First attacker's offensive EVs
            survive_hit1_item: First attacker's item
            survive_hit1_ability: First attacker's ability
            survive_hit1_tera_type: First attacker's Tera type if Terastallized
            survive_hit2_nature: Second attacker's nature
            survive_hit2_evs: Second attacker's offensive EVs
            survive_hit2_item: Second attacker's item
            survive_hit2_ability: Second attacker's ability
            survive_hit2_tera_type: Second attacker's Tera type if Terastallized
            defender_tera_type: Your Pokemon's Tera type if Terastallizing
            target_survival: Minimum survival % to consider "surviving" (default 93.75 = 15/16 rolls)

        Returns:
            Optimal spread with survival breakdown for each attack, or "IMPOSSIBLE" if no valid spread exists
        """
        try:
            # Fetch defender data
            my_base = await pokeapi.get_base_stats(pokemon_name)
            my_types = await pokeapi.get_pokemon_types(pokemon_name)

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return {"error": f"Invalid nature: {nature}"}

            # Fetch attacker 1 data
            atk1_base = await pokeapi.get_base_stats(survive_hit1_attacker)
            atk1_types = await pokeapi.get_pokemon_types(survive_hit1_attacker)
            move1 = await pokeapi.get_move(survive_hit1_move, user_name=survive_hit1_attacker)
            is_physical1 = move1.category == MoveCategory.PHYSICAL

            # Fetch attacker 2 data
            atk2_base = await pokeapi.get_base_stats(survive_hit2_attacker)
            atk2_types = await pokeapi.get_pokemon_types(survive_hit2_attacker)
            move2 = await pokeapi.get_move(survive_hit2_move, user_name=survive_hit2_attacker)
            is_physical2 = move2.category == MoveCategory.PHYSICAL

            # Auto-fetch Smogon spreads for attackers
            smogon1 = await _get_common_spread(survive_hit1_attacker)
            smogon2 = await _get_common_spread(survive_hit2_attacker)

            # Fill in attacker 1 defaults
            if smogon1:
                if survive_hit1_nature is None:
                    survive_hit1_nature = smogon1.get("nature", "adamant")
                if survive_hit1_evs is None:
                    evs = smogon1.get("evs", {})
                    survive_hit1_evs = evs.get("attack" if is_physical1 else "special_attack", 252)
                if survive_hit1_item is None:
                    survive_hit1_item = smogon1.get("item")
                if survive_hit1_ability is None:
                    survive_hit1_ability = smogon1.get("ability")
            else:
                survive_hit1_nature = survive_hit1_nature or ("adamant" if is_physical1 else "modest")
                survive_hit1_evs = survive_hit1_evs if survive_hit1_evs is not None else 252

            # Fill in attacker 2 defaults
            if smogon2:
                if survive_hit2_nature is None:
                    survive_hit2_nature = smogon2.get("nature", "adamant")
                if survive_hit2_evs is None:
                    evs = smogon2.get("evs", {})
                    survive_hit2_evs = evs.get("attack" if is_physical2 else "special_attack", 252)
                if survive_hit2_item is None:
                    survive_hit2_item = smogon2.get("item")
                if survive_hit2_ability is None:
                    survive_hit2_ability = smogon2.get("ability")
            else:
                survive_hit2_nature = survive_hit2_nature or ("adamant" if is_physical2 else "modest")
                survive_hit2_evs = survive_hit2_evs if survive_hit2_evs is not None else 252

            # Apply meta synergies fallback
            atk1_key = survive_hit1_attacker.lower().replace(" ", "-")
            if atk1_key in META_SYNERGIES:
                default_item, default_ability = META_SYNERGIES[atk1_key]
                if survive_hit1_item is None:
                    survive_hit1_item = default_item
                if survive_hit1_ability is None:
                    survive_hit1_ability = default_ability

            atk2_key = survive_hit2_attacker.lower().replace(" ", "-")
            if atk2_key in META_SYNERGIES:
                default_item, default_ability = META_SYNERGIES[atk2_key]
                if survive_hit2_item is None:
                    survive_hit2_item = default_item
                if survive_hit2_ability is None:
                    survive_hit2_ability = default_ability

            # Auto-detect Unseen Fist for Urshifu
            if atk1_key in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                if not survive_hit1_ability:
                    survive_hit1_ability = "unseen-fist"
            if atk2_key in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                if not survive_hit2_ability:
                    survive_hit2_ability = "unseen-fist"

            # Auto-detect Ruinous abilities for attacker 1
            # First: Direct detection from Pokemon name (most reliable)
            sword_of_ruin1 = atk1_key == "chien-pao"
            beads_of_ruin1 = atk1_key == "chi-yu"
            if sword_of_ruin1 and not survive_hit1_ability:
                survive_hit1_ability = "sword-of-ruin"
            if beads_of_ruin1 and not survive_hit1_ability:
                survive_hit1_ability = "beads-of-ruin"

            # Second: Check from ability string if set
            if not sword_of_ruin1 and not beads_of_ruin1 and survive_hit1_ability:
                ability_lower = survive_hit1_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_lower == "sword-of-ruin":
                    sword_of_ruin1 = True
                elif ability_lower == "beads-of-ruin":
                    beads_of_ruin1 = True

            # Third: Fallback to PokeAPI
            if not sword_of_ruin1 and not beads_of_ruin1 and not survive_hit1_ability:
                atk1_abilities = await pokeapi.get_pokemon_abilities(survive_hit1_attacker)
                if atk1_abilities:
                    ability_lower = atk1_abilities[0].lower().replace(" ", "-")
                    if ability_lower == "sword-of-ruin":
                        sword_of_ruin1 = True
                        survive_hit1_ability = "sword-of-ruin"
                    elif ability_lower == "beads-of-ruin":
                        beads_of_ruin1 = True
                        survive_hit1_ability = "beads-of-ruin"

            # Auto-detect Ruinous abilities for attacker 2
            # First: Direct detection from Pokemon name (most reliable)
            sword_of_ruin2 = atk2_key == "chien-pao"
            beads_of_ruin2 = atk2_key == "chi-yu"
            if sword_of_ruin2 and not survive_hit2_ability:
                survive_hit2_ability = "sword-of-ruin"
            if beads_of_ruin2 and not survive_hit2_ability:
                survive_hit2_ability = "beads-of-ruin"

            # Second: Check from ability string if set
            if not sword_of_ruin2 and not beads_of_ruin2 and survive_hit2_ability:
                ability_lower = survive_hit2_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_lower == "sword-of-ruin":
                    sword_of_ruin2 = True
                elif ability_lower == "beads-of-ruin":
                    beads_of_ruin2 = True

            # Third: Fallback to PokeAPI
            if not sword_of_ruin2 and not beads_of_ruin2 and not survive_hit2_ability:
                atk2_abilities = await pokeapi.get_pokemon_abilities(survive_hit2_attacker)
                if atk2_abilities:
                    ability_lower = atk2_abilities[0].lower().replace(" ", "-")
                    if ability_lower == "sword-of-ruin":
                        sword_of_ruin2 = True
                        survive_hit2_ability = "sword-of-ruin"
                    elif ability_lower == "beads-of-ruin":
                        beads_of_ruin2 = True
                        survive_hit2_ability = "beads-of-ruin"

            # Calculate speed EVs needed
            speed_evs_needed = 0
            target_speed = 0
            my_speed_stat = 0

            if speed_evs is not None:
                speed_evs_needed = speed_evs
            elif outspeed_pokemon:
                try:
                    target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                    target_nature = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature, "speed")
                    target_speed = calculate_stat(
                        target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )

                    my_speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(my_base.speed, 31, ev, 50, my_speed_mod)
                        if my_speed > target_speed:
                            speed_evs_needed = ev
                            my_speed_stat = my_speed
                            break
                    else:
                        speed_evs_needed = 252
                        my_speed_stat = calculate_stat(my_base.speed, 31, 252, 50, my_speed_mod)
                except Exception:
                    pass

            # Calculate remaining EVs for bulk
            remaining_evs = 508 - speed_evs_needed

            # Parse attacker natures
            atk1_nature = Nature(survive_hit1_nature.lower())
            atk2_nature = Nature(survive_hit2_nature.lower())

            # Create attacker builds
            attacker1 = PokemonBuild(
                name=survive_hit1_attacker,
                base_stats=atk1_base,
                types=atk1_types,
                nature=atk1_nature,
                evs=EVSpread(
                    attack=survive_hit1_evs if is_physical1 else 0,
                    special_attack=0 if is_physical1 else survive_hit1_evs
                ),
                item=survive_hit1_item,
                ability=survive_hit1_ability,
                tera_type=survive_hit1_tera_type
            )

            attacker2 = PokemonBuild(
                name=survive_hit2_attacker,
                base_stats=atk2_base,
                types=atk2_types,
                nature=atk2_nature,
                evs=EVSpread(
                    attack=survive_hit2_evs if is_physical2 else 0,
                    special_attack=0 if is_physical2 else survive_hit2_evs
                ),
                item=survive_hit2_item,
                ability=survive_hit2_ability,
                tera_type=survive_hit2_tera_type
            )

            # Search for MINIMUM EVs spread
            # Use coarse grid (0, 52, 100, 148, 196, 252) for speed, then refine
            best_spread = None
            best_results = None

            def_nature_mod = get_nature_modifier(parsed_nature, "defense")
            spd_nature_mod = get_nature_modifier(parsed_nature, "special_defense")

            # Coarse EV steps: 0, 52, 100, 148, 196, 252 = 6 values per stat = 216 combos max
            COARSE_EVS = [0, 52, 100, 148, 196, 252]

            def test_spread(hp_ev: int, def_ev: int, spd_ev: int) -> tuple:
                """Test a specific spread. Returns (survives_both, margin, result1, result2, pcts)."""
                defender = PokemonBuild(
                    name=pokemon_name, base_stats=my_base, types=my_types,
                    nature=parsed_nature,
                    evs=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                    tera_type=defender_tera_type
                )
                modifiers1 = DamageModifiers(
                    is_doubles=True, attacker_item=survive_hit1_item,
                    attacker_ability=survive_hit1_ability, tera_type=survive_hit1_tera_type,
                    tera_active=survive_hit1_tera_type is not None,
                    defender_tera_type=defender_tera_type,
                    defender_tera_active=defender_tera_type is not None,
                    is_critical=move1.always_crit,
                    sword_of_ruin=sword_of_ruin1,
                    beads_of_ruin=beads_of_ruin1
                )
                result1 = calculate_damage(attacker1, defender, move1, modifiers1)
                modifiers2 = DamageModifiers(
                    is_doubles=True, attacker_item=survive_hit2_item,
                    attacker_ability=survive_hit2_ability, tera_type=survive_hit2_tera_type,
                    tera_active=survive_hit2_tera_type is not None,
                    defender_tera_type=defender_tera_type,
                    defender_tera_active=defender_tera_type is not None,
                    is_critical=move2.always_crit,
                    sword_of_ruin=sword_of_ruin2,
                    beads_of_ruin=beads_of_ruin2
                )
                result2 = calculate_damage(attacker2, defender, move2, modifiers2)
                survive_rolls1 = sum(1 for r in result1.rolls if r < result1.defender_hp)
                survive_rolls2 = sum(1 for r in result2.rolls if r < result2.defender_hp)
                survival_pct1 = (survive_rolls1 / 16) * 100
                survival_pct2 = (survive_rolls2 / 16) * 100
                survives1 = survival_pct1 >= target_survival
                survives2 = survival_pct2 >= target_survival
                margin = min(100 - result1.max_percent, 100 - result2.max_percent)
                return (survives1 and survives2, margin, result1, result2, survival_pct1, survival_pct2, survives1, survives2)

            # Determine attack categories for HP-first optimization
            # is_physical1 and is_physical2 tell us whether to optimize Def or SpD
            both_physical = is_physical1 and is_physical2
            both_special = (not is_physical1) and (not is_physical2)
            is_mixed = not both_physical and not both_special

            def find_min_stat_to_survive(hp_ev: int, stat_ev_idx: int, attack_idx: int) -> int:
                """Find minimum Def or SpD EVs to survive a specific attack at given HP."""
                # stat_ev_idx: 0=defense, 1=special_defense
                max_ev = min(252, remaining_evs - hp_ev)

                for test_ev in EV_BREAKPOINTS_LV50:
                    if test_ev > max_ev:
                        break

                    def_ev = test_ev if stat_ev_idx == 0 else 0
                    spd_ev = test_ev if stat_ev_idx == 1 else 0

                    survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, def_ev, spd_ev)
                    target_survives = s1 if attack_idx == 1 else s2

                    if target_survives:
                        return test_ev

                return -1  # Can't survive even at max EVs

            # HP-first search: For each HP value, find minimum Def+SpD needed
            best_total = float('inf')
            best_hp, best_def, best_spd = 0, 0, 0
            best_results_data = None

            for hp_ev in EV_BREAKPOINTS_LV50:
                if hp_ev > min(252, remaining_evs):
                    break

                if is_mixed:
                    # Mixed attacks: need both Def and SpD
                    # Find minimum Def for physical attack, minimum SpD for special attack
                    phys_attack_idx = 1 if is_physical1 else 2
                    spec_attack_idx = 2 if is_physical1 else 1

                    min_def = find_min_stat_to_survive(hp_ev, 0, phys_attack_idx)
                    min_spd = find_min_stat_to_survive(hp_ev, 1, spec_attack_idx)

                    if min_def < 0 or min_spd < 0:
                        continue  # Can't survive at this HP

                    if hp_ev + min_def + min_spd > remaining_evs:
                        continue  # Not enough EVs

                    # Verify the combined spread actually works
                    survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, min_def, min_spd)
                    if survives:
                        total = hp_ev + min_def + min_spd
                        if total < best_total:
                            best_total = total
                            best_hp, best_def, best_spd = hp_ev, min_def, min_spd
                            best_results_data = (r1, r2, pct1, pct2, s1, s2)

                elif both_physical:
                    # Both physical: only need HP + Def
                    for def_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + def_ev > remaining_evs:
                            break
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, def_ev, 0)
                        if survives:
                            total = hp_ev + def_ev
                            if total < best_total:
                                best_total = total
                                best_hp, best_def, best_spd = hp_ev, def_ev, 0
                                best_results_data = (r1, r2, pct1, pct2, s1, s2)
                            break  # Found minimum Def for this HP, move to next HP

                else:  # both_special
                    # Both special: only need HP + SpD
                    for spd_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + spd_ev > remaining_evs:
                            break
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, 0, spd_ev)
                        if survives:
                            total = hp_ev + spd_ev
                            if total < best_total:
                                best_total = total
                                best_hp, best_def, best_spd = hp_ev, 0, spd_ev
                                best_results_data = (r1, r2, pct1, pct2, s1, s2)
                            break  # Found minimum SpD for this HP, move to next HP

            if best_results_data:
                r1, r2, pct1, pct2, s1, s2 = best_results_data
                best_spread = {"hp": best_hp, "def": best_def, "spd": best_spd}
                best_results = {
                    "result1": r1, "result2": r2,
                    "survival_pct1": pct1, "survival_pct2": pct2,
                    "survives1": s1, "survives2": s2
                }

            # If no valid spread, find best effort at max EVs
            if best_spread is None:
                best_margin = -float('inf')
                for hp_ev in COARSE_EVS:
                    if hp_ev > min(252, remaining_evs):
                        break
                    for def_ev in COARSE_EVS:
                        if hp_ev + def_ev > remaining_evs:
                            break
                        spd_ev = min(252, remaining_evs - hp_ev - def_ev)
                        spd_ev = normalize_evs(spd_ev)
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, def_ev, spd_ev)
                        if margin > best_margin:
                            best_margin = margin
                            best_spread = {"hp": hp_ev, "def": def_ev, "spd": spd_ev}
                            best_results = {
                                "result1": r1, "result2": r2,
                                "survival_pct1": pct1, "survival_pct2": pct2,
                                "survives1": s1, "survives2": s2
                            }

            if best_spread is None:
                return {
                    "verdict": "IMPOSSIBLE",
                    "error": "No valid EV spread found - try reducing speed requirement or changing nature",
                    "speed_evs_needed": speed_evs_needed,
                    "remaining_for_bulk": remaining_evs
                }

            # Calculate final stats
            final_hp = calculate_hp(my_base.hp, 31, best_spread["hp"], 50)
            final_def = calculate_stat(my_base.defense, 31, best_spread["def"], 50, def_nature_mod)
            final_spd = calculate_stat(my_base.special_defense, 31, best_spread["spd"], 50, spd_nature_mod)
            final_spe = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, get_nature_modifier(parsed_nature, "speed"))

            r1 = best_results["result1"]
            r2 = best_results["result2"]

            both_survive = best_results["survives1"] and best_results["survives2"]

            if both_survive:
                verdict = f"POSSIBLE - Survives both at {target_survival}%+ threshold"
            else:
                verdict = f"BEST EFFORT - Cannot hit {target_survival}% on both"

            # Build attacker spread strings
            atk1_stat = "Atk" if is_physical1 else "SpA"
            atk1_mod = get_nature_modifier(atk1_nature, "attack" if is_physical1 else "special_attack")
            atk1_nature_ind = "+" if atk1_mod > 1.0 else ("-" if atk1_mod < 1.0 else "")
            atk1_spread_str = f"{survive_hit1_evs}{atk1_nature_ind} {atk1_stat}"
            if survive_hit1_item:
                atk1_spread_str += f" {survive_hit1_item.replace('-', ' ').title()}"
            atk1_spread_str += f" {survive_hit1_attacker}"

            atk2_stat = "Atk" if is_physical2 else "SpA"
            atk2_mod = get_nature_modifier(atk2_nature, "attack" if is_physical2 else "special_attack")
            atk2_nature_ind = "+" if atk2_mod > 1.0 else ("-" if atk2_mod < 1.0 else "")
            atk2_spread_str = f"{survive_hit2_evs}{atk2_nature_ind} {atk2_stat}"
            if survive_hit2_item:
                atk2_spread_str += f" {survive_hit2_item.replace('-', ' ').title()}"
            atk2_spread_str += f" {survive_hit2_attacker}"

            return {
                "pokemon": pokemon_name,
                "nature": nature,
                "verdict": verdict,
                "spread": {
                    "hp_evs": best_spread["hp"],
                    "def_evs": best_spread["def"],
                    "spd_evs": best_spread["spd"],
                    "spe_evs": speed_evs_needed,
                    "total": best_spread["hp"] + best_spread["def"] + best_spread["spd"] + speed_evs_needed,
                    "offensive_evs_available": 508 - speed_evs_needed - best_spread["hp"] - best_spread["def"] - best_spread["spd"]
                },
                "final_stats": {
                    "hp": final_hp,
                    "defense": final_def,
                    "special_defense": final_spd,
                    "speed": final_spe
                },
                "speed_benchmark": {
                    "outspeeds": outspeed_pokemon,
                    "target_speed": target_speed,
                    "my_speed": final_spe,
                    "outspeeds_target": final_spe > target_speed if outspeed_pokemon else None
                },
                "survival_results": [
                    {
                        "attacker": survive_hit1_attacker,
                        "move": survive_hit1_move,
                        "attacker_spread": atk1_spread_str,
                        "tera_type": survive_hit1_tera_type,
                        "damage_range": r1.damage_range,
                        "damage_percent": f"{r1.min_percent:.1f}-{r1.max_percent:.1f}%",
                        "survival_chance": f"{best_results['survival_pct1']:.1f}%",
                        "survives_target": best_results["survives1"]
                    },
                    {
                        "attacker": survive_hit2_attacker,
                        "move": survive_hit2_move,
                        "attacker_spread": atk2_spread_str,
                        "tera_type": survive_hit2_tera_type,
                        "damage_range": r2.damage_range,
                        "damage_percent": f"{r2.min_percent:.1f}-{r2.max_percent:.1f}%",
                        "survival_chance": f"{best_results['survival_pct2']:.1f}%",
                        "survives_target": best_results["survives2"]
                    }
                ],
                "summary": (
                    f"{pokemon_name.title()} @ {nature.title()}: "
                    f"{best_spread['hp']} HP / {best_spread['def']} Def / {best_spread['spd']} SpD / {speed_evs_needed} Spe"
                ),
                "analysis": (
                    f"With {nature.title()} {best_spread['hp']} HP / {best_spread['def']} Def / {best_spread['spd']} SpD / {speed_evs_needed} Spe, "
                    f"{pokemon_name.title()} takes {r1.min_percent:.1f}-{r1.max_percent:.1f}% from {survive_hit1_move} "
                    f"({best_results['survival_pct1']:.1f}% survival) and "
                    f"{r2.min_percent:.1f}-{r2.max_percent:.1f}% from {survive_hit2_move} "
                    f"({best_results['survival_pct2']:.1f}% survival)"
                )
            }

        except Exception as e:
            return {"error": str(e)}