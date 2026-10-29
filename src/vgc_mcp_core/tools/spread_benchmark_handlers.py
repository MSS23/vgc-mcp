"""Handler for design_spread_with_benchmarks (speed + survival benchmark spreads)."""

from typing import Any, Optional

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import calculate_damage, format_percent
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50, normalize_evs
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.move import MoveCategory
from vgc_mcp_core.models.pokemon import (
    EVSpread,
    Nature,
    get_nature_modifier,
)
from vgc_mcp_core.rules.format_detect import detect_champions_format
from vgc_mcp_core.tools import spread_common
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.spread_champions import (
    _design_spread_with_benchmarks_champions,
)
from vgc_mcp_core.tools.spread_common import (
    META_SYNERGIES,
    SPEED_STAGE_MULTIPLIERS,
    offensive_investment,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


async def design_spread_with_benchmarks(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    pokemon_name: str,
    nature: Optional[str] = None,
    outspeed_pokemon: Optional[str] = None,
    outspeed_pokemon_nature: str = 'jolly',
    outspeed_pokemon_evs: int = 252,
    outspeed_at_speed_stage: int = 0,
    outspeed_target_has_booster: bool = False,
    outspeed_target_has_tailwind: bool = False,
    my_pokemon_has_booster: bool = False,
    my_pokemon_has_tailwind: bool = False,
    survive_pokemon: Optional[str] = None,
    survive_move: Optional[str] = None,
    survive_pokemon_nature: str = 'adamant',
    survive_pokemon_evs: int | str = 252,
    survive_pokemon_ability: Optional[str] = None,
    survive_pokemon_item: Optional[str] = None,
    survive_pokemon_tera_type: Optional[str] = None,
    defender_tera_type: Optional[str] = None,
    prioritize: str = 'bulk',
    offensive_evs: int = 0,
    item: Optional[str] = None,
    ability: Optional[str] = None,
) -> dict[str, Any]:
    try:
        # Auto-assign fixed Tera types (Ogerpon forms, Terapagos)
        from vgc_mcp_core.calc.items import get_fixed_tera_type
        if survive_pokemon_tera_type is not None:
            fixed_tera = get_fixed_tera_type(survive_pokemon)
            if fixed_tera and survive_pokemon_tera_type.lower() != fixed_tera.lower():
                survive_pokemon_tera_type = fixed_tera
        if defender_tera_type is not None:
            fixed_tera = get_fixed_tera_type(pokemon_name)
            if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                defender_tera_type = fixed_tera

        # Fetch our Pokemon's data
        my_base = await pokeapi.get_base_stats(pokemon_name)
        my_types = await pokeapi.get_pokemon_types(pokemon_name)

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        if detect_champions_format(pokemon_name):
            return await _design_spread_with_benchmarks_champions(pokeapi, smogon,
                pokemon_name=pokemon_name,
                my_base=my_base,
                my_types=my_types,
                nature=nature,
                outspeed_pokemon=outspeed_pokemon,
                outspeed_pokemon_nature=outspeed_pokemon_nature,
                outspeed_pokemon_evs=outspeed_pokemon_evs,
                outspeed_at_speed_stage=outspeed_at_speed_stage,
                outspeed_target_has_booster=outspeed_target_has_booster,
                outspeed_target_has_tailwind=outspeed_target_has_tailwind,
                my_pokemon_has_booster=my_pokemon_has_booster,
                my_pokemon_has_tailwind=my_pokemon_has_tailwind,
                survive_pokemon=survive_pokemon,
                survive_move=survive_move,
                survive_pokemon_nature=survive_pokemon_nature,
                survive_pokemon_evs=survive_pokemon_evs,
                survive_pokemon_ability=survive_pokemon_ability,
                survive_pokemon_item=survive_pokemon_item,
                survive_pokemon_tera_type=survive_pokemon_tera_type,
                defender_tera_type=defender_tera_type,
                prioritize=prioritize,
                offensive_evs=offensive_evs,
                item=item,
                ability=ability,
            )

        # Auto-select nature if not provided
        nature_reasoning = None
        if nature is None:
            from vgc_mcp_core.calc.nature_optimization import find_optimal_nature_for_benchmarks

            # Determine attack type and role
            is_physical = offensive_evs > 0 and my_base.attack > my_base.special_attack
            is_special = offensive_evs > 0 and my_base.special_attack > my_base.attack
            role = "offensive" if prioritize == "offense" else "bulk"

            # Calculate speed target first (needed for benchmarks)
            target_speed = 0
            if outspeed_pokemon:
                try:
                    target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                    target_nature = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature, "speed")
                    target_speed = calculate_stat(
                        target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )
                    if outspeed_target_has_booster:
                        target_speed = int(target_speed * 1.5)
                    if outspeed_at_speed_stage != 0:
                        stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                        target_speed = int(target_speed * stage_mult)
                    if outspeed_target_has_tailwind:
                        target_speed = int(target_speed * 2)
                except Exception:
                    pass

            # Build benchmarks dict
            benchmarks = {
                "speed_target": target_speed if outspeed_pokemon else None,
                "prioritize": prioritize,
                "offensive_evs": offensive_evs if prioritize == "offense" else None,
            }

            # Find optimal nature
            nature_result = find_optimal_nature_for_benchmarks(
                base_stats=my_base,
                benchmarks=benchmarks,
                is_physical=is_physical,
                is_special=is_special,
                role=role
            )

            if nature_result:
                nature = nature_result.best_nature.value
                nature_reasoning = nature_result.reasoning
            else:
                # Fallback to neutral if optimization fails
                nature = "serious"
                nature_reasoning = "Could not optimize nature, using neutral nature"

        parsed_nature = Nature(nature.lower())

        results = {
            "pokemon": pokemon_name,
            "nature": nature,
            "benchmarks": {}
        }

        if nature_reasoning:
            results["nature_selection_reasoning"] = nature_reasoning

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

                # Apply Protosynthesis/Quark Drive speed boost if active (1.5x, floored)
                original_target_speed = target_speed
                if outspeed_target_has_booster:
                    target_speed = int(target_speed * 1.5)

                # Apply speed stage modifier (e.g., -1 for after Icy Wind)
                # Pokemon floors the result: floor(speed * multiplier)
                pre_stage_speed = target_speed
                if outspeed_at_speed_stage != 0:
                    stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                    target_speed = int(target_speed * stage_mult)

                # Apply Tailwind (2x speed, floored)
                pre_tailwind_speed = target_speed
                if outspeed_target_has_tailwind:
                    target_speed = int(target_speed * 2)

                # Find minimum EVs to outspeed (level 50 breakpoints)
                # Apply MY Pokemon's booster/tailwind modifiers when comparing
                my_speed_mod = get_nature_modifier(parsed_nature, "speed")
                for ev in EV_BREAKPOINTS_LV50:
                    my_speed = calculate_stat(my_base.speed, 31, ev, 50, my_speed_mod)
                    my_effective_speed = my_speed
                    # Apply MY Booster Energy (Protosynthesis/Quark Drive) - 1.5x, floored
                    if my_pokemon_has_booster:
                        my_effective_speed = int(my_effective_speed * 1.5)
                    # Apply MY Tailwind - 2x, floored
                    if my_pokemon_has_tailwind:
                        my_effective_speed = int(my_effective_speed * 2)
                    if my_effective_speed > target_speed:
                        speed_evs_needed = ev
                        break
                else:
                    speed_evs_needed = 252  # Max out if can't outspeed

                # Calculate final speeds for display
                my_base_speed = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, my_speed_mod)
                my_final_speed = my_base_speed
                if my_pokemon_has_booster:
                    my_final_speed = int(my_final_speed * 1.5)
                if my_pokemon_has_tailwind:
                    my_final_speed = int(my_final_speed * 2)

                speed_benchmark = {
                    "target": outspeed_pokemon,
                    "target_speed": target_speed,
                    "evs_needed": speed_evs_needed,
                    "my_speed": my_base_speed,
                    "my_effective_speed": my_final_speed,
                    "outspeeds": my_final_speed > target_speed
                }
                # Add booster, speed stage, and tailwind info if applicable
                if outspeed_target_has_booster:
                    speed_benchmark["target_base_speed"] = original_target_speed
                    speed_benchmark["target_boosted_speed"] = pre_stage_speed
                    speed_benchmark["booster_note"] = f"Protosynthesis/Quark Drive: {original_target_speed} -> {pre_stage_speed}"
                if outspeed_at_speed_stage != 0:
                    if not outspeed_target_has_booster:
                        speed_benchmark["target_base_speed"] = original_target_speed
                    speed_benchmark["target_speed_stage"] = outspeed_at_speed_stage
                    stage_name = "after Icy Wind" if outspeed_at_speed_stage == -1 else f"at {outspeed_at_speed_stage:+d} stage"
                    speed_benchmark["speed_stage_note"] = f"Target at {pre_tailwind_speed} Speed ({stage_name})"
                if outspeed_target_has_tailwind:
                    speed_benchmark["target_tailwind_speed"] = target_speed
                    speed_benchmark["tailwind_note"] = f"Target with Tailwind: {pre_tailwind_speed} -> {target_speed}"
                # Add MY Pokemon's modifiers info
                if my_pokemon_has_booster:
                    speed_benchmark["my_booster_note"] = f"My Protosynthesis/Quark Drive: {my_base_speed} -> {int(my_base_speed * 1.5)}"
                if my_pokemon_has_tailwind:
                    pre_tw = int(my_base_speed * 1.5) if my_pokemon_has_booster else my_base_speed
                    speed_benchmark["my_tailwind_note"] = f"My Tailwind: {pre_tw} -> {my_final_speed}"
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
                smogon_spread = await spread_common._get_common_spread(smogon, survive_pokemon)
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

                # Auto-detect Unseen Fist for Urshifu forms
                normalized_attacker = survive_pokemon.lower().replace(" ", "-")
                if normalized_attacker in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                    if not survive_pokemon_ability:
                        survive_pokemon_ability = "unseen-fist"

                # Auto-detect Ruinous abilities from attacker
                from vgc_mcp_core.calc.abilities import normalize_ability_name

                sword_of_ruin = False
                beads_of_ruin = False
                tablets_of_ruin = False
                vessel_of_ruin = False

                survive_pokemon_evs = offensive_investment(survive_pokemon_evs, is_physical)
                if survive_pokemon_ability:
                    ability_lower = normalize_ability_name(survive_pokemon_ability)
                    if ability_lower == "sword-of-ruin":
                        sword_of_ruin = True
                    elif ability_lower == "beads-of-ruin":
                        beads_of_ruin = True
                    elif ability_lower == "tablets-of-ruin":
                        tablets_of_ruin = True
                    elif ability_lower == "vessel-of-ruin":
                        vessel_of_ruin = True
                else:
                    # Auto-detect from Pokemon
                    atk_abilities = await pokeapi.get_pokemon_abilities(survive_pokemon)
                    if atk_abilities:
                        ability_lower = normalize_ability_name(atk_abilities[0])
                        if ability_lower == "sword-of-ruin":
                            sword_of_ruin = True
                            survive_pokemon_ability = "sword-of-ruin"
                        elif ability_lower == "beads-of-ruin":
                            beads_of_ruin = True
                            survive_pokemon_ability = "beads-of-ruin"
                        elif ability_lower == "tablets-of-ruin":
                            tablets_of_ruin = True
                            survive_pokemon_ability = "tablets-of-ruin"
                        elif ability_lower == "vessel-of-ruin":
                            vessel_of_ruin = True
                            survive_pokemon_ability = "vessel-of-ruin"

                # Create attacker build
                attacker = build_pokemon(
                    name=survive_pokemon,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    spread=EVSpread(
                        attack=survive_pokemon_evs if is_physical else 0,
                        special_attack=0 if is_physical else survive_pokemon_evs
                    ),
                    ability=survive_pokemon_ability,
                    item=survive_pokemon_item,
                    tera_type=survive_pokemon_tera_type,
                )

                # Resolve defender ability (mega > Smogon > pokeapi) so all
                # defensive ability interactions auto-apply, and pre-compute
                # the Intimidate stage event for this physical/special move.
                from vgc_mcp_core.tools.ability_helpers import (
                    compute_intimidate_attack_stage,
                    resolve_ability,
                )
                ability, _ability_source = await resolve_ability(
                    pokemon_name, pokeapi=pokeapi, smogon_client=smogon,
                    user_override=ability,
                )
                intim_stage, _ = compute_intimidate_attack_stage(
                    defender_ability=ability,
                    attacker_ability=survive_pokemon_ability,
                    is_physical=is_physical,
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
                            defender = build_pokemon(
                                name=pokemon_name,
                                base_stats=my_base,
                                types=my_types,
                                nature=parsed_nature,
                                spread=EVSpread(
                                    hp=hp_ev,
                                    defense=def_ev_norm,
                                    special_defense=spd_ev_norm
                                ),
                                ability=ability,
                                item=item,
                                tera_type=defender_tera_type,
                            )

                            # Calculate damage
                            modifiers = DamageModifiers.from_scenario(
                                attacker_ability=survive_pokemon_ability,
                                attacker_item=survive_pokemon_item,
                                defender_ability=ability,
                                tera_type=survive_pokemon_tera_type,
                                defender_tera_type=defender_tera_type,
                                is_critical=move.always_crit,
                                sword_of_ruin=sword_of_ruin,
                                beads_of_ruin=beads_of_ruin,
                                tablets_of_ruin=tablets_of_ruin,
                                vessel_of_ruin=vessel_of_ruin,
                                intimidate_stage=intim_stage,
                                is_physical=is_physical,
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
                analysis_str = f"{attacker_spread_str}'s {survive_move} vs {defender_spread_str}: {format_percent(best_result.min_percent)}-{format_percent(best_result.max_percent)}%"

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
                    "damage_percent": f"{format_percent(best_result.min_percent)}-{format_percent(best_result.max_percent)}%",
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

        # 3b. HP number optimization for item
        if item:
            from vgc_mcp_core.calc.hp_optimization import adjust_hp_evs_for_item
            hp_adj = adjust_hp_evs_for_item(my_base.hp, hp_evs, item)
            if hp_adj["adjusted_evs"] != hp_evs:
                # Verify the adjustment doesn't break survival
                apply_adj = True
                if survive_pokemon and survive_move and best_result is not None:
                    adj_defender = build_pokemon(
                        name=pokemon_name,
                        base_stats=my_base,
                        types=my_types,
                        nature=parsed_nature,
                        spread=EVSpread(
                            hp=hp_adj["adjusted_evs"],
                            defense=def_evs,
                            special_defense=spd_evs,
                        ),
                        ability=ability,
                        item=item,
                        tera_type=defender_tera_type,
                    )
                    adj_result = calculate_damage(attacker, adj_defender, move, modifiers)
                    if adj_result.max_percent >= 100:
                        apply_adj = False  # Would break survival
                if apply_adj:
                    hp_evs = hp_adj["adjusted_evs"]
                    results["hp_optimization"] = hp_adj

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

        # Create PokemonBuild with optimized spread for Showdown export
        optimized_pokemon = build_pokemon(
            name=pokemon_name,
            base_stats=my_base,
            types=my_types,
            nature=parsed_nature,
            spread=EVSpread(
                hp=hp_evs,
                attack=atk_evs if is_physical else 0,
                defense=def_evs,
                special_attack=0 if is_physical else atk_evs,
                special_defense=spd_evs,
                speed=speed_evs_needed
            ),
            tera_type=defender_tera_type,
        )
        results["showdown_paste"] = pokemon_build_to_showdown(optimized_pokemon)

        return results

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
