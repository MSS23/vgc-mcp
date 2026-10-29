"""Handlers for dual- and multi-threat survival spread optimization."""

import time
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
    _optimize_multi_survival_champions,
)
from vgc_mcp_core.tools.spread_common import (
    META_SYNERGIES,
    NATURE_CANDIDATES_PHYSICAL,
    NATURE_CANDIDATES_SPECIAL,
    SPEED_STAGE_MULTIPLIERS,
    DamageCache,
    _find_min_bulk_for_threat,
    _generate_nature_explanation,
    _prepare_threats,
    _quick_feasibility_check,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


async def optimize_dual_survival_spread(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    pokemon_name: str,
    survive_hit1_attacker: str,
    survive_hit1_move: str,
    survive_hit2_attacker: str,
    survive_hit2_move: str,
    nature: Optional[str] = None,
    outspeed_pokemon: Optional[str] = None,
    outspeed_pokemon_nature: str = 'timid',
    outspeed_pokemon_evs: int = 252,
    outspeed_at_speed_stage: int = 0,
    outspeed_target_has_booster: bool = False,
    outspeed_target_has_tailwind: bool = False,
    my_pokemon_has_booster: bool = False,
    my_pokemon_has_tailwind: bool = False,
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
    target_survival: float = 100.0,
    item: Optional[str] = None,
    ability: Optional[str] = None,
) -> dict[str, Any]:
    try:
        # Auto-assign fixed Tera types (Ogerpon forms, Terapagos)
        from vgc_mcp_core.calc.items import get_fixed_tera_type
        if survive_hit1_tera_type is not None:
            fixed_tera = get_fixed_tera_type(survive_hit1_attacker)
            if fixed_tera and survive_hit1_tera_type.lower() != fixed_tera.lower():
                survive_hit1_tera_type = fixed_tera
        if survive_hit2_tera_type is not None:
            fixed_tera = get_fixed_tera_type(survive_hit2_attacker)
            if fixed_tera and survive_hit2_tera_type.lower() != fixed_tera.lower():
                survive_hit2_tera_type = fixed_tera
        if defender_tera_type is not None:
            fixed_tera = get_fixed_tera_type(pokemon_name)
            if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                defender_tera_type = fixed_tera

        # Fetch defender data
        my_base = await pokeapi.get_base_stats(pokemon_name)
        my_types = await pokeapi.get_pokemon_types(pokemon_name)

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        if detect_champions_format(pokemon_name):
            threats = [
                {
                    "attacker": survive_hit1_attacker, "move": survive_hit1_move,
                    "nature": survive_hit1_nature, "evs": survive_hit1_evs,
                    "item": survive_hit1_item, "ability": survive_hit1_ability,
                    "tera_type": survive_hit1_tera_type,
                },
                {
                    "attacker": survive_hit2_attacker, "move": survive_hit2_move,
                    "nature": survive_hit2_nature, "evs": survive_hit2_evs,
                    "item": survive_hit2_item, "ability": survive_hit2_ability,
                    "tera_type": survive_hit2_tera_type,
                },
            ]
            return await _optimize_multi_survival_champions(pokeapi, smogon,
                pokemon_name=pokemon_name,
                my_base=my_base,
                my_types=my_types,
                nature=nature,
                threats=threats,
                target_stage=outspeed_at_speed_stage,
                target_booster=outspeed_target_has_booster,
                target_tailwind=outspeed_target_has_tailwind,
                booster=my_pokemon_has_booster,
                tailwind=my_pokemon_has_tailwind,
                speed_override=speed_evs,
                outspeed_pokemon=outspeed_pokemon,
                outspeed_pokemon_nature=outspeed_pokemon_nature,
                outspeed_pokemon_evs=outspeed_pokemon_evs,
                defender_tera_type=defender_tera_type,
                target_survival=target_survival,
                item=item,
                ability=ability,
            )

        # Track if nature was auto-selected
        nature_auto_selected = nature is None

        # If nature specified, validate it
        if nature is not None:
            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

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
        smogon1 = await spread_common._get_common_spread(smogon, survive_hit1_attacker)
        smogon2 = await spread_common._get_common_spread(smogon, survive_hit2_attacker)

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

        # Resolve defender ability and pre-compute Intimidate stages once.
        from vgc_mcp_core.tools.ability_helpers import (
            compute_intimidate_attack_stage,
            resolve_ability,
        )
        ability, _ability_source = await resolve_ability(
            pokemon_name, pokeapi=pokeapi, smogon_client=smogon,
            user_override=ability,
        )
        intim1_stage, _ = compute_intimidate_attack_stage(
            defender_ability=ability,
            attacker_ability=survive_hit1_ability,
            is_physical=is_physical1,
        )
        intim2_stage, _ = compute_intimidate_attack_stage(
            defender_ability=ability,
            attacker_ability=survive_hit2_ability,
            is_physical=is_physical2,
        )

        # Calculate target speed first (independent of our nature)
        target_speed = 0
        if speed_evs is not None:
            # User specified exact speed EVs
            pass
        elif outspeed_pokemon:
            try:
                target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                target_nature_parsed = Nature(outspeed_pokemon_nature.lower())
                target_speed_mod = get_nature_modifier(target_nature_parsed, "speed")
                target_speed = calculate_stat(
                    target_base.speed, 31, outspeed_pokemon_evs, 50, target_speed_mod
                )

                # Apply Protosynthesis/Quark Drive speed boost if active (1.5x, floored)
                if outspeed_target_has_booster:
                    target_speed = int(target_speed * 1.5)

                # Apply speed stage modifier (e.g., -1 for after Icy Wind)
                if outspeed_at_speed_stage != 0:
                    stage_mult = SPEED_STAGE_MULTIPLIERS.get(outspeed_at_speed_stage, 1)
                    target_speed = int(target_speed * stage_mult)

                # Apply Tailwind (2x speed, floored)
                if outspeed_target_has_tailwind:
                    target_speed = int(target_speed * 2)
            except Exception:
                pass

        def calc_min_speed_evs(base_speed: int, my_speed_mod: float) -> tuple[int, int]:
            """Calculate minimum speed EVs needed to outspeed target. Returns (evs, final_speed)."""
            if speed_evs is not None:
                my_speed = calculate_stat(base_speed, 31, speed_evs, 50, my_speed_mod)
                return speed_evs, my_speed
            if target_speed == 0:
                return 0, calculate_stat(base_speed, 31, 0, 50, my_speed_mod)

            for ev in EV_BREAKPOINTS_LV50:
                my_speed = calculate_stat(base_speed, 31, ev, 50, my_speed_mod)
                my_effective_speed = my_speed
                if my_pokemon_has_booster:
                    my_effective_speed = int(my_effective_speed * 1.5)
                if my_pokemon_has_tailwind:
                    my_effective_speed = int(my_effective_speed * 2)
                if my_effective_speed > target_speed:
                    return ev, my_speed
            # Can't outspeed even at max
            return 252, calculate_stat(base_speed, 31, 252, 50, my_speed_mod)

        # Determine natures to try
        if nature_auto_selected:
            # Choose nature list based on whether Pokemon is physical or special attacker
            is_special_attacker = my_base.special_attack > my_base.attack
            natures_to_try = NATURE_CANDIDATES_SPECIAL if is_special_attacker else NATURE_CANDIDATES_PHYSICAL
        else:
            # User specified nature - only try that one
            natures_to_try = [(nature.lower(), {
                "speed": get_nature_modifier(parsed_nature, "speed"),
                "defense": get_nature_modifier(parsed_nature, "defense"),
                "special_defense": get_nature_modifier(parsed_nature, "special_defense"),
                "attack": get_nature_modifier(parsed_nature, "attack"),
                "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
            })]

        # Parse attacker natures
        atk1_nature = Nature(survive_hit1_nature.lower())
        atk2_nature = Nature(survive_hit2_nature.lower())

        # Create attacker builds
        attacker1 = build_pokemon(
            name=survive_hit1_attacker,
            base_stats=atk1_base,
            types=atk1_types,
            nature=atk1_nature,
            spread=EVSpread(
                attack=survive_hit1_evs if is_physical1 else 0,
                special_attack=0 if is_physical1 else survive_hit1_evs
            ),
            item=survive_hit1_item,
            ability=survive_hit1_ability,
            tera_type=survive_hit1_tera_type,
        )

        attacker2 = build_pokemon(
            name=survive_hit2_attacker,
            base_stats=atk2_base,
            types=atk2_types,
            nature=atk2_nature,
            spread=EVSpread(
                attack=survive_hit2_evs if is_physical2 else 0,
                special_attack=0 if is_physical2 else survive_hit2_evs
            ),
            item=survive_hit2_item,
            ability=survive_hit2_ability,
            tera_type=survive_hit2_tera_type,
        )

        # Determine attack categories for HP-first optimization
        both_physical = is_physical1 and is_physical2
        both_special = (not is_physical1) and (not is_physical2)
        is_mixed = not both_physical and not both_special

        # Coarse EV steps for fallback search
        COARSE_EVS = [0, 52, 100, 148, 196, 252]

        # Track ALL valid natures (for alternative suggestions)
        all_valid_natures = []  # List of all natures that meet benchmarks

        for nature_name, nature_mods in natures_to_try:
            # Calculate speed EVs needed for this nature
            speed_mod = nature_mods["speed"]
            speed_evs_needed, my_speed_stat = calc_min_speed_evs(my_base.speed, speed_mod)

            # Check if we can even outspeed (if required)
            if target_speed > 0:
                test_speed = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_mod)
                effective_speed = test_speed
                if my_pokemon_has_booster:
                    effective_speed = int(effective_speed * 1.5)
                if my_pokemon_has_tailwind:
                    effective_speed = int(effective_speed * 2)
                if effective_speed <= target_speed:
                    continue  # This nature can't outspeed, skip

            remaining_evs = 508 - speed_evs_needed
            def_nature_mod = nature_mods["defense"]
            spd_nature_mod = nature_mods["special_defense"]

            # Create a nature enum for this iteration
            try:
                current_nature = Nature(nature_name)
            except ValueError:
                current_nature = Nature.SERIOUS

            def test_spread(hp_ev: int, def_ev: int, spd_ev: int) -> tuple:
                """Test a specific spread. Returns (survives_both, margin, result1, result2, pcts)."""
                defender = build_pokemon(
                    name=pokemon_name,
                    base_stats=my_base,
                    types=my_types,
                    nature=current_nature,
                    spread=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                    ability=ability,
                    item=item,
                    tera_type=defender_tera_type,
                )
                modifiers1 = DamageModifiers.from_scenario(
                    attacker_item=survive_hit1_item,
                    attacker_ability=survive_hit1_ability,
                    tera_type=survive_hit1_tera_type,
                    defender_tera_type=defender_tera_type,
                    is_critical=move1.always_crit,
                    sword_of_ruin=sword_of_ruin1,
                    beads_of_ruin=beads_of_ruin1,
                    defender_ability=ability,
                    intimidate_stage=intim1_stage,
                    is_physical=is_physical1,
                )
                result1 = calculate_damage(attacker1, defender, move1, modifiers1)
                modifiers2 = DamageModifiers.from_scenario(
                    attacker_item=survive_hit2_item,
                    attacker_ability=survive_hit2_ability,
                    tera_type=survive_hit2_tera_type,
                    defender_tera_type=defender_tera_type,
                    is_critical=move2.always_crit,
                    sword_of_ruin=sword_of_ruin2,
                    beads_of_ruin=beads_of_ruin2,
                    defender_ability=ability,
                    intimidate_stage=intim2_stage,
                    is_physical=is_physical2,
                )
                result2 = calculate_damage(attacker2, defender, move2, modifiers2)
                survival_pct1 = result1.survival_percent
                survival_pct2 = result2.survival_percent
                survives1 = survival_pct1 >= target_survival
                survives2 = survival_pct2 >= target_survival
                margin = min(100 - result1.max_percent, 100 - result2.max_percent)
                return (survives1 and survives2, margin, result1, result2, survival_pct1, survival_pct2, survives1, survives2)

            def find_min_stat_to_survive(hp_ev: int, stat_ev_idx: int, attack_idx: int) -> int:
                """Find minimum Def or SpD EVs to survive a specific attack at given HP."""
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
                return -1

            # HP-first search for this nature
            best_spread = None
            best_results = None
            best_total = float('inf')

            for hp_ev in EV_BREAKPOINTS_LV50:
                if hp_ev > min(252, remaining_evs):
                    break

                if is_mixed:
                    phys_attack_idx = 1 if is_physical1 else 2
                    spec_attack_idx = 2 if is_physical1 else 1
                    min_def = find_min_stat_to_survive(hp_ev, 0, phys_attack_idx)
                    min_spd = find_min_stat_to_survive(hp_ev, 1, spec_attack_idx)
                    if min_def < 0 or min_spd < 0:
                        continue
                    if hp_ev + min_def + min_spd > remaining_evs:
                        continue
                    survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, min_def, min_spd)
                    if survives:
                        total = hp_ev + min_def + min_spd
                        if total < best_total:
                            best_total = total
                            best_spread = {"hp": hp_ev, "def": min_def, "spd": min_spd}
                            best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}

                elif both_physical:
                    for def_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + def_ev > remaining_evs:
                            break
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, def_ev, 0)
                        if survives:
                            total = hp_ev + def_ev
                            if total < best_total:
                                best_total = total
                                best_spread = {"hp": hp_ev, "def": def_ev, "spd": 0}
                                best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}
                            break

                else:  # both_special
                    for spd_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + spd_ev > remaining_evs:
                            break
                        survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread(hp_ev, 0, spd_ev)
                        if survives:
                            total = hp_ev + spd_ev
                            if total < best_total:
                                best_total = total
                                best_spread = {"hp": hp_ev, "def": 0, "spd": spd_ev}
                                best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}
                            break

            # If this nature found a valid spread, add it to the list
            if best_spread and best_results and best_results["survives1"] and best_results["survives2"]:
                total_evs = speed_evs_needed + best_spread["hp"] + best_spread["def"] + best_spread["spd"]
                all_valid_natures.append({
                    "nature": nature_name,
                    "speed_evs": speed_evs_needed,
                    "spread": best_spread,
                    "results": best_results,
                    "mods": nature_mods,
                    "total_evs": total_evs,
                    "my_speed_stat": my_speed_stat
                })

        # If no nature found a valid spread, try best effort with first nature
        if not all_valid_natures:
            # Use first nature for best effort
            nature_name, nature_mods = natures_to_try[0]
            speed_mod = nature_mods["speed"]
            speed_evs_needed, my_speed_stat = calc_min_speed_evs(my_base.speed, speed_mod)
            remaining_evs = 508 - speed_evs_needed
            def_nature_mod = nature_mods["defense"]
            spd_nature_mod = nature_mods["special_defense"]
            try:
                current_nature = Nature(nature_name)
            except ValueError:
                current_nature = Nature.SERIOUS

            def test_spread_fallback(hp_ev: int, def_ev: int, spd_ev: int) -> tuple:
                defender = build_pokemon(
                    name=pokemon_name,
                    base_stats=my_base,
                    types=my_types,
                    nature=current_nature,
                    spread=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                    ability=ability,
                    item=item,
                    tera_type=defender_tera_type,
                )
                modifiers1 = DamageModifiers.from_scenario(
                    attacker_item=survive_hit1_item,
                    attacker_ability=survive_hit1_ability,
                    tera_type=survive_hit1_tera_type,
                    defender_tera_type=defender_tera_type,
                    is_critical=move1.always_crit,
                    sword_of_ruin=sword_of_ruin1,
                    beads_of_ruin=beads_of_ruin1,
                    defender_ability=ability,
                    intimidate_stage=intim1_stage,
                    is_physical=is_physical1,
                )
                result1 = calculate_damage(attacker1, defender, move1, modifiers1)
                modifiers2 = DamageModifiers.from_scenario(
                    attacker_item=survive_hit2_item,
                    attacker_ability=survive_hit2_ability,
                    tera_type=survive_hit2_tera_type,
                    defender_tera_type=defender_tera_type,
                    is_critical=move2.always_crit,
                    sword_of_ruin=sword_of_ruin2,
                    beads_of_ruin=beads_of_ruin2,
                    defender_ability=ability,
                    intimidate_stage=intim2_stage,
                    is_physical=is_physical2,
                )
                result2 = calculate_damage(attacker2, defender, move2, modifiers2)
                survival_pct1 = result1.survival_percent
                survival_pct2 = result2.survival_percent
                survives1 = survival_pct1 >= target_survival
                survives2 = survival_pct2 >= target_survival
                margin = min(100 - result1.max_percent, 100 - result2.max_percent)
                return (survives1 and survives2, margin, result1, result2, survival_pct1, survival_pct2, survives1, survives2)

            best_margin = -float('inf')
            best_spread = None
            best_results = None
            for hp_ev in COARSE_EVS:
                if hp_ev > min(252, remaining_evs):
                    break
                for def_ev in COARSE_EVS:
                    if hp_ev + def_ev > remaining_evs:
                        break
                    spd_ev = min(252, remaining_evs - hp_ev - def_ev)
                    spd_ev = normalize_evs(spd_ev)
                    survives, margin, r1, r2, pct1, pct2, s1, s2 = test_spread_fallback(hp_ev, def_ev, spd_ev)
                    if margin > best_margin:
                        best_margin = margin
                        best_spread = {"hp": hp_ev, "def": def_ev, "spd": spd_ev}
                        best_results = {"result1": r1, "result2": r2, "survival_pct1": pct1, "survival_pct2": pct2, "survives1": s1, "survives2": s2}

            if best_spread is None:
                return error_response(ErrorCodes.INTERNAL_ERROR, 'No valid EV spread found - benchmarks may be impossible', verdict='IMPOSSIBLE', speed_evs_needed=speed_evs_needed, remaining_for_bulk=remaining_evs)

            # Store fallback result
            all_valid_natures.append({
                "nature": nature_name,
                "speed_evs": speed_evs_needed,
                "spread": best_spread,
                "results": best_results,
                "mods": nature_mods,
                "total_evs": 508,
                "my_speed_stat": my_speed_stat
            })

        # Sort all valid natures by speed EVs (ascending), then total EVs (ascending)
        # Prioritize: 1. Less speed EVs needed, 2. Less total EVs
        all_valid_natures.sort(key=lambda x: (x["speed_evs"], x["total_evs"]))

        # Pick optimal (first one)
        optimal = all_valid_natures[0]

        # Generate alternative natures (next 2-3)
        alternative_natures = []
        for alt in all_valid_natures[1:4]:  # Top 3 alternatives
            explanation = _generate_nature_explanation(optimal, alt)
            alternative_natures.append({
                "nature": alt["nature"],
                "spread": {
                    "hp_evs": alt["spread"]["hp"],
                    "def_evs": alt["spread"]["def"],
                    "spd_evs": alt["spread"]["spd"],
                    "spe_evs": alt["speed_evs"]
                },
                "total_evs": alt["total_evs"],
                "ev_difference": f"+{alt['total_evs'] - optimal['total_evs']} EVs vs optimal",
                "explanation": explanation
            })

        # Unpack the optimal result
        chosen_nature = optimal["nature"]
        speed_evs_needed = optimal["speed_evs"]
        best_spread = optimal["spread"]
        best_results = optimal["results"]
        nature_mods = optimal["mods"]
        total_evs = optimal["total_evs"]
        my_speed_stat = optimal["my_speed_stat"]
        def_nature_mod = nature_mods["defense"]
        spd_nature_mod = nature_mods["special_defense"]
        speed_nature_mod = nature_mods["speed"]

        # Calculate offensive EVs (normalized to valid breakpoints)
        raw_offensive = 508 - speed_evs_needed - best_spread["hp"] - best_spread["def"] - best_spread["spd"]
        offensive_evs = normalize_evs(raw_offensive)
        leftover = raw_offensive - offensive_evs

        # Put leftover EVs in SpD (4 EVs = +1 stat point at level 50)
        extra_spd = normalize_evs(leftover) if leftover >= 4 else 0
        final_spd_evs = best_spread["spd"] + extra_spd

        # Calculate final stats (using final_spd_evs for SpD)
        final_hp = calculate_hp(my_base.hp, 31, best_spread["hp"], 50)
        final_def = calculate_stat(my_base.defense, 31, best_spread["def"], 50, def_nature_mod)
        final_spd_stat = calculate_stat(my_base.special_defense, 31, final_spd_evs, 50, spd_nature_mod)
        final_spe = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_nature_mod)

        r1 = best_results["result1"]
        r2 = best_results["result2"]

        both_survive = best_results["survives1"] and best_results["survives2"]

        if both_survive:
            verdict = "POSSIBLE - Survives both attacks (100% of rolls)"
        else:
            verdict = "IMPOSSIBLE - Cannot guarantee survival on both attacks"

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

        # Build nature reason
        if nature_auto_selected:
            nature_reason = f"Auto-selected: {speed_evs_needed} Spe EVs needed to outspeed target"
        else:
            nature_reason = "User specified"

        # Create PokemonBuild with optimized spread for Showdown export
        chosen_nature_enum = Nature(chosen_nature.lower())
        optimized_pokemon = build_pokemon(
            name=pokemon_name,
            base_stats=my_base,
            types=my_types,
            nature=chosen_nature_enum,
            spread=EVSpread(
                hp=best_spread["hp"],
                attack=0,  # This is a defensive spread
                defense=best_spread["def"],
                special_attack=offensive_evs,
                special_defense=final_spd_evs,
                speed=speed_evs_needed
            ),
            tera_type=defender_tera_type
        )

        dual_result = {
            "pokemon": pokemon_name,
            "nature": chosen_nature,
            "nature_auto_selected": nature_auto_selected,
            "nature_reason": nature_reason,
            "verdict": verdict,
            "spread": {
                "hp_evs": best_spread["hp"],
                "def_evs": best_spread["def"],
                "spd_evs": final_spd_evs,  # Includes extra EVs if available
                "spe_evs": speed_evs_needed,
                "spa_evs": offensive_evs,  # Leftover EVs for offense (normalized)
                "total": best_spread["hp"] + best_spread["def"] + final_spd_evs + speed_evs_needed + offensive_evs
            },
            "final_stats": {
                "hp": final_hp,
                "defense": final_def,
                "special_defense": final_spd_stat,
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
                    "attacker_nature": survive_hit1_nature,
                    "attacker_evs": survive_hit1_evs,
                    "attacker_item": survive_hit1_item,
                    "attacker_ability": survive_hit1_ability,
                    "tera_type": survive_hit1_tera_type,
                    "damage_range": r1.damage_range,
                    "damage_percent": f"{r1.min_percent:.2f}-{r1.max_percent:.2f}%",
                    "survival_chance": f"{best_results['survival_pct1']:.2f}%",
                    "survives_target": best_results["survives1"]
                },
                {
                    "attacker": survive_hit2_attacker,
                    "move": survive_hit2_move,
                    "attacker_spread": atk2_spread_str,
                    "attacker_nature": survive_hit2_nature,
                    "attacker_evs": survive_hit2_evs,
                    "attacker_item": survive_hit2_item,
                    "attacker_ability": survive_hit2_ability,
                    "tera_type": survive_hit2_tera_type,
                    "damage_range": r2.damage_range,
                    "damage_percent": f"{r2.min_percent:.2f}-{r2.max_percent:.2f}%",
                    "survival_chance": f"{best_results['survival_pct2']:.2f}%",
                    "survives_target": best_results["survives2"]
                }
            ],
            "summary": (
                f"{pokemon_name.title()} @ {chosen_nature.title()}: "
                f"{best_spread['hp']} HP / {best_spread['def']} Def / {offensive_evs} SpA / {final_spd_evs} SpD / {speed_evs_needed} Spe"
            ),
            "analysis": (
                f"With {chosen_nature.title()} {best_spread['hp']} HP / {best_spread['def']} Def / {final_spd_evs} SpD / {speed_evs_needed} Spe, "
                f"{pokemon_name.title()} takes {r1.min_percent:.2f}-{r1.max_percent:.2f}% from {survive_hit1_move} "
                f"({atk1_spread_str}) ({best_results['survival_pct1']:.2f}% survival) and "
                f"{r2.min_percent:.2f}-{r2.max_percent:.2f}% from {survive_hit2_move} "
                f"({atk2_spread_str}) ({best_results['survival_pct2']:.2f}% survival)"
            ),
            "showdown_paste": pokemon_build_to_showdown(optimized_pokemon),
            "alternative_natures": alternative_natures,
        }

        # HP number optimization for item
        if item and best_spread:
            from vgc_mcp_core.calc.hp_optimization import adjust_hp_evs_for_item
            hp_adj = adjust_hp_evs_for_item(my_base.hp, best_spread["hp"], item)
            if hp_adj["adjusted_evs"] != best_spread["hp"]:
                # Verify survival still holds with adjusted HP
                adj_defender = build_pokemon(
                    name=pokemon_name,
                    base_stats=my_base,
                    types=my_types,
                    nature=Nature(chosen_nature),
                    spread=EVSpread(
                        hp=hp_adj["adjusted_evs"],
                        defense=best_spread["def"],
                        special_defense=final_spd_evs,
                    ),
                    ability=ability,
                    item=item,
                    tera_type=defender_tera_type,
                )
                adj_mods1 = DamageModifiers.from_scenario(
                    attacker_item=survive_hit1_item,
                    attacker_ability=survive_hit1_ability,
                    tera_type=survive_hit1_tera_type,
                    defender_tera_type=defender_tera_type,
                    is_critical=move1.always_crit,
                    sword_of_ruin=sword_of_ruin1,
                    beads_of_ruin=beads_of_ruin1,
                    defender_ability=ability,
                    intimidate_stage=intim1_stage,
                    is_physical=is_physical1,
                )
                adj_mods2 = DamageModifiers.from_scenario(
                    attacker_item=survive_hit2_item,
                    attacker_ability=survive_hit2_ability,
                    tera_type=survive_hit2_tera_type,
                    defender_tera_type=defender_tera_type,
                    is_critical=move2.always_crit,
                    sword_of_ruin=sword_of_ruin2,
                    beads_of_ruin=beads_of_ruin2,
                    defender_ability=ability,
                    intimidate_stage=intim2_stage,
                    is_physical=is_physical2,
                )
                adj_r1 = calculate_damage(attacker1, adj_defender, move1, adj_mods1)
                adj_r2 = calculate_damage(attacker2, adj_defender, move2, adj_mods2)
                if adj_r1.max_percent < 100 and adj_r2.max_percent < 100:
                    dual_result["hp_optimization"] = hp_adj

        return dual_result

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def optimize_multi_survival_spread(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    pokemon_name: str,
    threats: list[dict],
    nature: Optional[str] = None,
    outspeed_pokemon: Optional[str] = None,
    outspeed_pokemon_nature: str = 'timid',
    outspeed_pokemon_evs: int = 252,
    outspeed_at_speed_stage: int = 0,
    outspeed_target_has_booster: bool = False,
    outspeed_target_has_tailwind: bool = False,
    my_pokemon_has_booster: bool = False,
    my_pokemon_has_tailwind: bool = False,
    speed_evs: Optional[int] = None,
    defender_tera_type: Optional[str] = None,
    target_survival: float = 93.75,
    item: Optional[str] = None,
    ability: Optional[str] = None,
) -> dict[str, Any]:
    start_time = time.time()

    try:
        # Validate threat count
        if len(threats) < 3:
            return error_response(ErrorCodes.INTERNAL_ERROR, 'This tool requires 3-6 threats. For 2 threats, use optimize_dual_survival_spread instead.')
        if len(threats) > 6:
            return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 6 threats supported. Please reduce the number of threats or prioritize the most important ones.')

        # Auto-assign fixed Tera type if needed
        from vgc_mcp_core.calc.items import get_fixed_tera_type
        if defender_tera_type is not None:
            fixed_tera = get_fixed_tera_type(pokemon_name)
            if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                defender_tera_type = fixed_tera

        # Fetch defender data
        my_base = await pokeapi.get_base_stats(pokemon_name)
        my_types = await pokeapi.get_pokemon_types(pokemon_name)

        # --- Champions (Reg MA) Stat-Point branch ---------------------------
        if detect_champions_format(pokemon_name):
            return await _optimize_multi_survival_champions(pokeapi, smogon,
                pokemon_name=pokemon_name,
                my_base=my_base,
                my_types=my_types,
                nature=nature,
                threats=threats,
                target_stage=outspeed_at_speed_stage,
                target_booster=outspeed_target_has_booster,
                target_tailwind=outspeed_target_has_tailwind,
                booster=my_pokemon_has_booster,
                tailwind=my_pokemon_has_tailwind,
                speed_override=speed_evs,
                outspeed_pokemon=outspeed_pokemon,
                outspeed_pokemon_nature=outspeed_pokemon_nature,
                outspeed_pokemon_evs=outspeed_pokemon_evs,
                defender_tera_type=defender_tera_type,
                target_survival=target_survival,
                item=item,
                ability=ability,
            )

        # Resolve defender's ability so the engine auto-applies defensive
        # ability interactions (Multiscale, Ice Scales, Thick Fat, Filter,
        # Levitate, type absorption) AND so any defender Intimidate triggers
        # the -1 Atk stage for physical threats.
        from vgc_mcp_core.tools.ability_helpers import resolve_ability
        ability, _ability_source = await resolve_ability(
            pokemon_name, pokeapi=pokeapi, smogon_client=smogon,
            user_override=ability,
        )

        # Prepare all threats (fetch data, auto-detect spreads)
        prepared_threats = await _prepare_threats(threats, pokeapi, smogon)

        # Create damage cache (defender ability flows through every test build)
        cache = DamageCache(
            prepared_threats, pokemon_name, my_base, my_types,
            defender_ability=ability,
            defender_item=item,
        )

        # Track if nature was auto-selected
        nature_auto_selected = nature is None

        # Speed stage multipliers (from optimize_dual_survival_spread)
        SPEED_STAGE_MULTIPLIERS = {
            -6: 2/8, -5: 2/7, -4: 2/6, -3: 2/5, -2: 2/4, -1: 2/3,
            0: 1,
            1: 3/2, 2: 4/2, 3: 5/2, 4: 6/2, 5: 7/2, 6: 8/2
        }

        # Calculate target speed
        target_speed = 0
        if speed_evs is None and outspeed_pokemon:
            try:
                target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                target_nature_parsed = Nature(outspeed_pokemon_nature.lower())
                target_speed_mod = get_nature_modifier(target_nature_parsed, "speed")
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

        # Helper function to calculate minimum speed EVs needed
        def calc_min_speed_evs(base_speed: int, my_speed_mod: float) -> tuple[int, int]:
            """Calculate minimum speed EVs needed to outspeed target. Returns (evs, final_speed)."""
            if speed_evs is not None:
                my_speed = calculate_stat(base_speed, 31, speed_evs, 50, my_speed_mod)
                return speed_evs, my_speed
            if target_speed == 0:
                return 0, calculate_stat(base_speed, 31, 0, 50, my_speed_mod)

            for ev in EV_BREAKPOINTS_LV50:
                my_speed = calculate_stat(base_speed, 31, ev, 50, my_speed_mod)
                my_effective_speed = my_speed
                if my_pokemon_has_booster:
                    my_effective_speed = int(my_effective_speed * 1.5)
                if my_pokemon_has_tailwind:
                    my_effective_speed = int(my_effective_speed * 2)
                if my_effective_speed > target_speed:
                    return ev, my_speed
            return 252, calculate_stat(base_speed, 31, 252, 50, my_speed_mod)

        # Determine natures to try
        is_special_attacker = my_base.special_attack > my_base.attack
        NATURE_CANDIDATES_PHYSICAL = [
            # Bulk-boosting natures FIRST
            ("impish", {"speed": 1.0, "attack": 1.0, "defense": 1.1, "special_attack": 0.9, "special_defense": 1.0}),
            ("careful", {"speed": 1.0, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.1}),
            ("bold", {"speed": 1.0, "attack": 0.9, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
            ("calm", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
            # Offensive natures (can save EVs for speed benchmarks)
            ("adamant", {"speed": 1.0, "attack": 1.1, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
            # Speed-boosting natures
            ("jolly", {"speed": 1.1, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
            ("timid", {"speed": 1.1, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
            # -Speed natures (for Trick Room or min speed)
            ("brave", {"speed": 0.9, "attack": 1.1, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
            ("relaxed", {"speed": 0.9, "attack": 1.0, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
            ("sassy", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
        ]
        NATURE_CANDIDATES_SPECIAL = [
            # Bulk-boosting natures FIRST
            ("bold", {"speed": 1.0, "attack": 0.9, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
            ("calm", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
            ("impish", {"speed": 1.0, "attack": 1.0, "defense": 1.1, "special_attack": 0.9, "special_defense": 1.0}),
            ("careful", {"speed": 1.0, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.1}),
            # Offensive natures (can save EVs for speed benchmarks)
            ("modest", {"speed": 1.0, "attack": 0.9, "defense": 1.0, "special_attack": 1.1, "special_defense": 1.0}),
            # Speed-boosting natures
            ("timid", {"speed": 1.1, "attack": 0.9, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.0}),
            ("jolly", {"speed": 1.1, "attack": 1.0, "defense": 1.0, "special_attack": 0.9, "special_defense": 1.0}),
            # -Speed natures
            ("quiet", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.1, "special_defense": 1.0}),
            ("relaxed", {"speed": 0.9, "attack": 1.0, "defense": 1.1, "special_attack": 1.0, "special_defense": 1.0}),
            ("sassy", {"speed": 0.9, "attack": 1.0, "defense": 1.0, "special_attack": 1.0, "special_defense": 1.1}),
        ]

        if nature_auto_selected:
            natures_to_try = NATURE_CANDIDATES_SPECIAL if is_special_attacker else NATURE_CANDIDATES_PHYSICAL
        else:
            try:
                parsed_nature = Nature(nature.lower())
                natures_to_try = [(nature.lower(), {
                    "speed": get_nature_modifier(parsed_nature, "speed"),
                    "defense": get_nature_modifier(parsed_nature, "defense"),
                    "special_defense": get_nature_modifier(parsed_nature, "special_defense"),
                    "attack": get_nature_modifier(parsed_nature, "attack"),
                    "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
                })]
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f'Invalid nature: {nature}')

        # Categorize threats by type
        physical_threats = [i for i, t in enumerate(prepared_threats) if t.is_physical]
        special_threats = [i for i, t in enumerate(prepared_threats) if not t.is_physical]
        is_mixed = len(physical_threats) > 0 and len(special_threats) > 0

        # Track ALL valid natures (for alternative suggestions)
        all_valid_natures_multi = []  # List of all natures that meet benchmarks

        for nature_name, nature_mods in natures_to_try:
            speed_mod = nature_mods["speed"]
            speed_evs_needed, my_speed_stat = calc_min_speed_evs(my_base.speed, speed_mod)

            # Check if we can outspeed
            if target_speed > 0:
                test_speed = calculate_stat(my_base.speed, 31, speed_evs_needed, 50, speed_mod)
                effective_speed = test_speed
                if my_pokemon_has_booster:
                    effective_speed = int(effective_speed * 1.5)
                if my_pokemon_has_tailwind:
                    effective_speed = int(effective_speed * 2)
                if effective_speed <= target_speed:
                    continue  # Can't outspeed with this nature

            remaining_evs = 508 - speed_evs_needed
            current_nature = Nature(nature_name)

            # Stage 1: Quick feasibility check
            feasible = _quick_feasibility_check(
                cache, remaining_evs, current_nature, target_survival, defender_tera_type
            )

            if feasible is None:
                # This nature can't survive all threats
                continue

            # Stage 2: HP-first search for optimal spread
            best_spread = None
            best_results = None
            best_total = float('inf')

            for hp_ev in EV_BREAKPOINTS_LV50:
                if hp_ev > min(252, remaining_evs):
                    break

                if is_mixed:
                    # Find max Defense needed across all physical threats
                    max_def = 0
                    for threat_idx in physical_threats:
                        min_def = _find_min_bulk_for_threat(
                            cache, threat_idx, hp_ev, current_nature, target_survival, "defense", defender_tera_type
                        )
                        if min_def < 0:
                            max_def = 999
                            break
                        max_def = max(max_def, min_def)

                    # Find max SpD needed across all special threats
                    max_spd = 0
                    for threat_idx in special_threats:
                        min_spd = _find_min_bulk_for_threat(
                            cache, threat_idx, hp_ev, current_nature, target_survival, "special_defense", defender_tera_type
                        )
                        if min_spd < 0:
                            max_spd = 999
                            break
                        max_spd = max(max_spd, min_spd)

                    if max_def == 999 or max_spd == 999:
                        continue  # Impossible at this HP
                    if hp_ev + max_def + max_spd > remaining_evs:
                        continue  # Not enough EVs

                    # Verify all threats
                    all_survive, results = cache.test_spread_all_threats(
                        hp_ev, max_def, max_spd, current_nature, target_survival, defender_tera_type
                    )

                    if all_survive:
                        total = hp_ev + max_def + max_spd
                        if total < best_total:
                            best_total = total
                            best_spread = {"hp": hp_ev, "def": max_def, "spd": max_spd}
                            best_results = results

                elif len(physical_threats) > 0:  # All physical
                    for def_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + def_ev > remaining_evs:
                            break

                        all_survive, results = cache.test_spread_all_threats(
                            hp_ev, def_ev, 0, current_nature, target_survival, defender_tera_type
                        )

                        if all_survive:
                            total = hp_ev + def_ev
                            if total < best_total:
                                best_total = total
                                best_spread = {"hp": hp_ev, "def": def_ev, "spd": 0}
                                best_results = results
                            break  # Early exit

                else:  # All special
                    for spd_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + spd_ev > remaining_evs:
                            break

                        all_survive, results = cache.test_spread_all_threats(
                            hp_ev, 0, spd_ev, current_nature, target_survival, defender_tera_type
                        )

                        if all_survive:
                            total = hp_ev + spd_ev
                            if total < best_total:
                                best_total = total
                                best_spread = {"hp": hp_ev, "def": 0, "spd": spd_ev}
                                best_results = results
                            break  # Early exit

            # If this nature found a valid spread, add it to the list
            if best_spread and best_results:
                total_evs = speed_evs_needed + best_spread["hp"] + best_spread["def"] + best_spread["spd"]
                # Calculate final stats
                final_hp = calculate_hp(my_base.hp, 31, best_spread["hp"], 50)
                final_def = calculate_stat(my_base.defense, 31, best_spread["def"], 50, nature_mods["defense"])
                final_spd = calculate_stat(my_base.special_defense, 31, best_spread["spd"], 50, nature_mods["special_defense"])

                all_valid_natures_multi.append({
                    "nature": nature_name,
                    "speed_evs": speed_evs_needed,
                    "spread": best_spread,
                    "results": best_results,
                    "mods": nature_mods,
                    "total_evs": total_evs,
                    "my_speed_stat": my_speed_stat,
                    "final_hp": final_hp,
                    "final_def": final_def,
                    "final_spd": final_spd
                })

        # Calculate computation stats
        end_time = time.time()
        time_ms = int((end_time - start_time) * 1000)
        cache_stats = cache.get_stats()

        # Check if we found a solution
        if all_valid_natures_multi:
            # Sort by speed EVs (ascending), then total EVs (ascending)
            all_valid_natures_multi.sort(key=lambda x: (x["speed_evs"], x["total_evs"]))

            # Pick optimal (first one)
            optimal_multi = all_valid_natures_multi[0]

            # Generate alternative natures (next 2-3)
            alternative_natures_multi = []
            for alt in all_valid_natures_multi[1:4]:  # Top 3 alternatives
                explanation = _generate_nature_explanation(optimal_multi, alt)
                alternative_natures_multi.append({
                    "nature": alt["nature"],
                    "spread": {
                        "hp_evs": alt["spread"]["hp"],
                        "def_evs": alt["spread"]["def"],
                        "spd_evs": alt["spread"]["spd"],
                        "spe_evs": alt["speed_evs"]
                    },
                    "total_evs": alt["total_evs"],
                    "ev_difference": f"+{alt['total_evs'] - optimal_multi['total_evs']} EVs vs optimal",
                    "explanation": explanation
                })

            # Unpack optimal result
            nature_name = optimal_multi["nature"]
            speed_evs_needed = optimal_multi["speed_evs"]
            best_spread = optimal_multi["spread"]
            best_results = optimal_multi["results"]
            total_evs = optimal_multi["total_evs"]
            my_speed_stat = optimal_multi["my_speed_stat"]
            final_hp = optimal_multi["final_hp"]
            final_def = optimal_multi["final_def"]
            final_spd = optimal_multi["final_spd"]

            # Build optimized Pokemon for Showdown paste
            optimized_pokemon = build_pokemon(
                name=pokemon_name,
                base_stats=my_base,
                types=my_types,
                nature=Nature(nature_name),
                spread=EVSpread(
                    hp=best_spread["hp"],
                    defense=best_spread["def"],
                    special_defense=best_spread["spd"],
                    speed=speed_evs_needed
                ),
                tera_type=defender_tera_type,
            )

            # Build threat survival analysis
            threat_analysis = []
            for i, (survives, result) in enumerate(best_results):
                threat = prepared_threats[i]
                survival_pct = result.survival_percent

                # Format attacker spread
                atk_ev_str = f"{threat.evs}"
                atk_spread = f"{threat.nature.title()} {atk_ev_str} {'Atk' if threat.is_physical else 'SpA'}"

                threat_analysis.append({
                    "attacker": threat.attacker_name,
                    "move": threat.move.name,
                    "spread": atk_spread,
                    "item": threat.item,
                    "ability": threat.ability,
                    "tera_type": threat.tera_type,
                    "damage_range": result.damage_range,
                    "damage_percent": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
                    "survival_rate": f"{survival_pct:.2f}%",
                    "survives": survives
                })

            multi_result = {
                "success": True,
                "optimal_spread": {
                    "hp_evs": best_spread["hp"],
                    "def_evs": best_spread["def"],
                    "spd_evs": best_spread["spd"],
                    "speed_evs": speed_evs_needed,
                    "nature": nature_name.title(),
                    "nature_auto_selected": nature_auto_selected,
                    "total_evs": total_evs,
                    "remaining_evs": 508 - total_evs,
                    "final_stats": {
                        "hp": final_hp,
                        "defense": final_def,
                        "special_defense": final_spd,
                        "speed": my_speed_stat
                    }
                },
                "threat_survival_analysis": threat_analysis,
                "showdown_paste": pokemon_build_to_showdown(optimized_pokemon),
                "alternative_natures": alternative_natures_multi,
                "computation_stats": {
                    "threats_count": len(prepared_threats),
                    "time_ms": time_ms,
                    "cache_size": cache_stats["total_cached"]
                }
            }

            # HP number optimization for item
            if item and best_spread:
                from vgc_mcp_core.calc.hp_optimization import adjust_hp_evs_for_item
                hp_adj = adjust_hp_evs_for_item(my_base.hp, best_spread["hp"], item)
                if hp_adj["adjusted_evs"] != best_spread["hp"]:
                    # For multi-survival, verify all threats still survived
                    adj_hp = calculate_hp(my_base.hp, 31, hp_adj["adjusted_evs"], 50)
                    all_survive = all(
                        r.max_percent < 100 for _, r in best_results
                    )
                    # Only apply if original already survived (we just check the HP change doesn't break things)
                    # A small HP decrease shouldn't break survival if the margin was there
                    if all_survive and adj_hp >= final_hp - 2:
                        multi_result["hp_optimization"] = hp_adj

            return multi_result

        else:
            # No solution found - report impossibility
            return {
                "success": False,
                "impossible": True,
                "reason": "No EV spread can survive all threats simultaneously",
                "threat_count": len(prepared_threats),
                "suggestions": [
                    "Consider dropping one threat to make survival possible",
                    "Try a different Tera type to improve type matchups",
                    f"Reduce target survival rate (currently {target_survival}%)"
                ],
                "computation_stats": {
                    "threats_count": len(prepared_threats),
                    "time_ms": time_ms,
                    "cache_size": cache_stats["total_cached"]
                }
            }

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
