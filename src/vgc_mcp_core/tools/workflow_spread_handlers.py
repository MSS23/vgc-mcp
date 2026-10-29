"""Handlers for the workflow spread tools (suggest_ev_spread, optimize_spread)."""

from typing import Any, Optional

from vgc_mcp_core.calc.damage import format_percent
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.spread_common import slash_values
from vgc_mcp_core.utils.errors import ErrorCodes, error_response, success_response
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name


async def suggest_ev_spread(
    pokeapi: Any,
    smogon: Any,
    pokemon_name: str,
    nature: str = 'auto',
    outspeed_targets: Optional[list[str]] = None,
    survive_hits: Optional[list[dict[str, Any]]] = None,
    ko_targets: Optional[list[dict[str, Any]]] = None,
    prioritize: str = 'bulk',
) -> dict[str, Any]:
    from vgc_mcp_core.calc.conversion import evs_to_sps_spread
    from vgc_mcp_core.calc.damage import calculate_damage
    from vgc_mcp_core.calc.modifiers import DamageModifiers
    from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat
    from vgc_mcp_core.config import normalize_evs
    from vgc_mcp_core.models.move import MoveCategory
    from vgc_mcp_core.models.pokemon import (
        EVSpread,
        Nature,
        get_nature_modifier,
    )
    from vgc_mcp_core.rules.regulation_router import auto_detect_regulation

    try:
        # Resolve base stats + types via the canonical helpers (raw PokeAPI
        # response uses a `stats` array, not a `base_stats` dict — calling
        # get_pokemon directly here used to raise KeyError).
        try:
            base_stats_model = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
        except Exception:
            suggestions = suggest_pokemon_name(pokemon_name)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Pokemon '{pokemon_name}' not found",
                suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
            )

        base_stats = {
            "hp": base_stats_model.hp,
            "attack": base_stats_model.attack,
            "defense": base_stats_model.defense,
            "special_attack": base_stats_model.special_attack,
            "special_defense": base_stats_model.special_defense,
            "speed": base_stats_model.speed,
        }

        # Detect Champions vs mainline. We use whichever signal fires:
        # explicit session regulation, then Pokemon-name inference. Survive
        # targets aren't included in inference so the user's defender drives
        # the format choice.
        cfg = get_regulation_config()
        inference_names = [pokemon_name] + (outspeed_targets or [])
        try:
            auto_detect_regulation(inference_names, cfg)
        except Exception:
            pass
        format_system = cfg.get_format_system() or "mainline"
        is_champions = format_system == "champions"

        # Determine nature
        is_physical = base_stats["attack"] > base_stats["special_attack"]
        if nature == "auto":
            if prioritize == "speed":
                nature = "jolly" if is_physical else "timid"
            elif prioritize == "offense":
                nature = "adamant" if is_physical else "modest"
            else:  # bulk
                nature = "careful" if is_physical else "calm"

        try:
            parsed_nature = Nature(nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {nature}")

        # Initialize tracking
        benchmarks_met = []
        benchmarks_failed = []
        speed_evs_needed = 0
        hp_evs = 0
        def_evs = 0
        spd_evs = 0
        atk_evs = 0

        # 1. Calculate speed requirements
        if outspeed_targets:
            max_speed_needed = 0
            for target in outspeed_targets:
                try:
                    target_base = await pokeapi.get_base_stats(target)
                    target_base_speed = target_base.speed
                    target_speed = calculate_stat(target_base_speed, 31, 252, 50, 1.1)  # Assume +Speed nature

                    speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                        if my_speed > target_speed:
                            if ev > max_speed_needed:
                                max_speed_needed = ev
                            benchmarks_met.append(f"Outspeeds {target} ({my_speed} vs {target_speed})")
                            break
                    else:
                        benchmarks_failed.append(f"Cannot outspeed {target} even with 252 Speed EVs")
                        max_speed_needed = 252
                except Exception:
                    benchmarks_failed.append(f"Could not check speed vs {target}")

            speed_evs_needed = max_speed_needed

        remaining_evs = 508 - speed_evs_needed

        # 2. Calculate survival requirements
        #
        # Two pieces of context the caller usually omits but that change the
        # math materially:
        #   - Defender's post-mega ability. Mega Manectric is Intimidate,
        #     not Lightning Rod. Without this, the calc misses the -1 Atk
        #     drop on physical attackers.
        #   - Attacker's most-used item from the active regulation's Smogon
        #     usage data. Excadrill in Reg MA usually runs Life Orb, which
        #     bumps damage by 1.3x — assuming "no item" silently understates
        #     the threat.
        from vgc_mcp_core.calc.mega_evolution import get_mega_ability, is_mega_form

        defender_ability = get_mega_ability(pokemon_name) if is_mega_form(pokemon_name) else None
        mega_intimidate_active = defender_ability and defender_ability.lower() == "intimidate"

        if survive_hits and remaining_evs > 0:
            for hit in survive_hits:
                attacker_name = hit.get("attacker", "")
                move_name = hit.get("move", "")
                attacker_item = hit.get("item")
                attacker_ability = hit.get("ability")

                try:
                    atk_base = await pokeapi.get_base_stats(attacker_name)
                    atk_types = await pokeapi.get_pokemon_types(attacker_name)
                    move = await pokeapi.get_move(move_name)

                    # Auto-fetch attacker item from Smogon's active-regulation
                    # usage stats if the caller didn't provide one. We pull
                    # the format-specific dataset (Reg MA chaos JSON for
                    # Champions, Reg F for mainline) so the answer reflects
                    # the meta the user is actually playing.
                    item_source = "user-supplied" if attacker_item else None
                    if not attacker_item:
                        try:
                            fmt_list = cfg.get_smogon_formats() if hasattr(cfg, "get_smogon_formats") else None
                            fmt_name = fmt_list[0] if fmt_list else None
                            rating = cfg.get_default_smogon_rating() or 1500
                            common = await smogon.get_common_sets(
                                attacker_name, format_name=fmt_name, rating=rating, limit=1,
                            )
                            if common and common.get("top_items"):
                                top = common["top_items"][0]
                                if top.get("name") and top["name"].lower() != "nothing":
                                    attacker_item = top["name"]
                                    item_source = f"Smogon {fmt_name or 'auto'} top item"
                        except Exception:
                            pass

                    if atk_base and move:
                        is_phys = move.category == MoveCategory.PHYSICAL
                        atk_nature = Nature.ADAMANT if is_phys else Nature.MODEST

                        # Apply Intimidate if defender is Mega → Intimidate
                        # AND the attacker is a physical mover. -1 Atk stage.
                        stage_attack = -1 if (mega_intimidate_active and is_phys) else 0

                        attacker = build_pokemon(
                            name=attacker_name,
                            base_stats=atk_base,
                            types=atk_types,
                            nature=atk_nature,
                            spread=EVSpread(
                                attack=252 if is_phys else 0,
                                special_attack=0 if is_phys else 252
                            ),
                            ability=attacker_ability,
                            item=attacker_item,
                        )

                        best_hp = 0
                        best_def = 0
                        survived = False

                        # Lean-survival search: find the MINIMUM total
                        # investment (hp + def/spd) such that max-roll damage
                        # < 100%, then within that minimum prefer the most
                        # HP-heavy split. HP is a flat buffer that helps
                        # against ALL hits (physical and special), so
                        # HP-first matches VGC convention and gives the
                        # spread side-benefits against threats outside the
                        # explicit benchmark — much more useful than pure
                        # Def, which only helps this one matchup.
                        #
                        # Outer loop sweeps total budget low → high (4 EVs at
                        # a time) so we stop at the cheapest survival.
                        # Inner loop sweeps hp HIGH → low at each budget, so
                        # the first split that survives is the maximum-HP
                        # one that still works. This produces spreads like
                        # "156 HP / 16 Def" rather than "0 HP / 172 Def".
                        cap = min(508, remaining_evs)
                        found_pair = None
                        for total_budget in EV_BREAKPOINTS_LV50:
                            if total_budget > cap:
                                break
                            # Try most-HP split first, then peel HP off in
                            # 4-EV steps and feed it to defense.
                            hp_candidates = [
                                h for h in EV_BREAKPOINTS_LV50
                                if h <= min(total_budget, 252)
                            ]
                            for hp_ev in reversed(hp_candidates):
                                def_alloc = total_budget - hp_ev
                                if def_alloc > 252:
                                    continue
                                def_ev = def_alloc if is_phys else 0
                                spd_ev = def_alloc if not is_phys else 0

                                defender = build_pokemon(
                                    name=pokemon_name,
                                    base_stats=base_stats_model,
                                    types=types,
                                    nature=parsed_nature,
                                    spread=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev),
                                    ability=defender_ability,
                                )

                                modifiers = DamageModifiers.from_scenario(
                                    attacker_ability=attacker_ability,
                                    attacker_item=attacker_item,
                                    attack_stage=stage_attack,
                                )
                                result = calculate_damage(attacker, defender, move, modifiers)

                                if result.max_percent < 100:
                                    found_pair = (hp_ev, def_alloc, result)
                                    break
                            if found_pair:
                                break

                        if found_pair:
                            hp_ev, def_alloc, result = found_pair
                            best_hp = hp_ev
                            best_def = def_alloc
                            survived = True
                            note = ""
                            if mega_intimidate_active and is_phys:
                                note += " [Intimidate -1 Atk]"
                            if attacker_item and item_source != "user-supplied":
                                note += f" [item={attacker_item}]"
                            benchmarks_met.append(
                                f"Survives {attacker_name} {move_name} "
                                f"({result.min_percent:.0f}-{result.max_percent:.0f}%){note}"
                            )

                        if survived:
                            hp_evs = max(hp_evs, best_hp)
                            if is_phys:
                                def_evs = max(def_evs, best_def)
                            else:
                                spd_evs = max(spd_evs, best_def)
                        else:
                            detail = []
                            if mega_intimidate_active and is_phys:
                                detail.append("Intimidate applied")
                            if attacker_item:
                                detail.append(f"item={attacker_item}")
                            suffix = f" ({', '.join(detail)})" if detail else ""
                            benchmarks_failed.append(
                                f"Cannot survive {attacker_name} {move_name}{suffix}"
                            )

                except Exception as e:
                    benchmarks_failed.append(f"Error checking survival vs {attacker_name}: {str(e)}")

        # 3. Calculate KO requirements
        if ko_targets and remaining_evs > 0:
            for target in ko_targets:
                defender_name = target.get("defender", "")
                move_name = target.get("move", "")
                defender_hp_evs = target.get("evs", 0)

                try:
                    def_base = await pokeapi.get_base_stats(defender_name)
                    def_types = await pokeapi.get_pokemon_types(defender_name)
                    move = await pokeapi.get_move(move_name)

                    if def_base and move:
                        is_phys = move.category == MoveCategory.PHYSICAL

                        # Create defender
                        defender = build_pokemon(
                            name=defender_name,
                            base_stats=def_base,
                            types=def_types,
                            nature=Nature.SERIOUS,
                            spread=EVSpread(hp=defender_hp_evs),
                        )

                        # Check if we can KO with remaining EVs
                        atk_ev_available = remaining_evs - hp_evs - def_evs - spd_evs
                        atk_ev = min(252, max(0, atk_ev_available))

                        attacker = build_pokemon(
                            name=pokemon_name,
                            base_stats=base_stats_model,
                            types=types,
                            nature=parsed_nature,
                            spread=EVSpread(
                                attack=atk_ev if is_phys else 0,
                                special_attack=0 if is_phys else atk_ev
                            ),
                        )

                        modifiers = DamageModifiers.from_scenario()
                        result = calculate_damage(attacker, defender, move, modifiers)

                        if result.min_percent >= 100:
                            atk_evs = atk_ev
                            benchmarks_met.append(f"OHKOs {defender_name} with {move_name}")
                        elif result.max_percent >= 100:
                            atk_evs = atk_ev
                            benchmarks_met.append(f"Can OHKO {defender_name} with {move_name} (roll)")
                        else:
                            benchmarks_failed.append(
                                f"Cannot OHKO {defender_name} with {move_name} ({result.max_percent:.0f}% max)"
                            )

                except Exception as e:
                    benchmarks_failed.append(f"Error checking KO on {defender_name}: {str(e)}")

        # 4. Distribute remaining EVs (ensure multiples of 4)
        #
        # If a survival benchmark was met we already invested the minimum
        # needed (lean-survival search above), so leftover here is genuine
        # surplus. Default policy:
        #   1. The Pokemon's primary OFFENSIVE stat (Atk or SpA, picked
        #      from base stats — Mega Manectric base SpA 135 > Atk 75 so
        #      it pumps SpA). Capped at 252.
        #   2. Speed, if not already maxed and Speed is competitive
        #      (≥80 base — slow Pokemon don't benefit from creep).
        #   3. Secondary defensive bulk (the OPPOSITE of the survival
        #      stat we already invested in).
        #   4. HP last — never auto-padded, since that undoes the lean
        #      survival fit.
        # In offense / speed modes the existing single-stat fill stands.
        used_evs = speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs
        leftover = 508 - used_evs

        if leftover > 0:
            survival_was_used = bool(survive_hits) and (def_evs > 0 or spd_evs > 0 or hp_evs > 0)

            if prioritize == "bulk":
                if survival_was_used:
                    # 1. Pump the species' primary offensive stat.
                    # `atk_evs` is mapped to atk OR spa in final_stats via
                    # `is_physical`, so this single counter works for both.
                    atk_room = max(0, 252 - atk_evs)
                    if atk_room > 0:
                        atk_share = normalize_evs(min(atk_room, leftover))
                        atk_evs = normalize_evs(min(252, atk_evs + atk_share))
                        leftover = 508 - (speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs)

                    # 2. Speed, if the species is Speed-relevant
                    # (base ≥80) and we still have surplus. Slow species
                    # like Incineroar (base 60) skip this and dump into
                    # secondary bulk instead.
                    if leftover > 0 and base_stats["speed"] >= 80:
                        spe_room = max(0, 252 - speed_evs_needed)
                        if spe_room > 0:
                            spe_share = normalize_evs(min(spe_room, leftover))
                            speed_evs_needed = normalize_evs(min(252, speed_evs_needed + spe_share))
                            leftover = 508 - (speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs)

                    # 3. Secondary defense — opposite of whichever side we
                    # invested in for survival.
                    if leftover > 0:
                        if def_evs > 0 and spd_evs == 0:
                            spd_share = normalize_evs(min(252 - spd_evs, leftover))
                            spd_evs = normalize_evs(min(252, spd_evs + spd_share))
                        elif spd_evs > 0 and def_evs == 0:
                            def_share = normalize_evs(min(252 - def_evs, leftover))
                            def_evs = normalize_evs(min(252, def_evs + def_share))
                        else:
                            # Both sides already touched — split.
                            def_share = normalize_evs(leftover // 2)
                            spd_share = normalize_evs(leftover - def_share)
                            def_evs = normalize_evs(min(252, def_evs + def_share))
                            spd_evs = normalize_evs(min(252, spd_evs + spd_share))
                        leftover = 508 - (speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs)

                    # 4. HP last (only if anything's still leftover).
                    if leftover > 0:
                        hp_evs = normalize_evs(min(252, hp_evs + leftover))
                else:
                    # No survival benchmark — fall back to the original
                    # bulk distribution (HP-first, defenses split).
                    hp_evs = normalize_evs(min(252, hp_evs + leftover))
                    leftover = 508 - (speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs)
                    if leftover > 0:
                        def_share = normalize_evs(leftover // 2)
                        spd_share = normalize_evs(leftover - def_share)
                        def_evs = normalize_evs(min(252, def_evs + def_share))
                        spd_evs = normalize_evs(min(252, spd_evs + spd_share))
            elif prioritize == "offense":
                atk_evs = normalize_evs(min(252, atk_evs + leftover))
            else:  # speed
                speed_evs_needed = normalize_evs(min(252, speed_evs_needed + leftover))

        # 5. Calculate final stats
        speed_mod = get_nature_modifier(parsed_nature, "speed")
        atk_mod = get_nature_modifier(parsed_nature, "attack")
        spa_mod = get_nature_modifier(parsed_nature, "special_attack")
        def_mod = get_nature_modifier(parsed_nature, "defense")
        spd_mod = get_nature_modifier(parsed_nature, "special_defense")

        final_stats = {
            "hp": calculate_hp(base_stats["hp"], 31, hp_evs, 50),
            "attack": calculate_stat(base_stats["attack"], 31, atk_evs if is_physical else 0, 50, atk_mod),
            "defense": calculate_stat(base_stats["defense"], 31, def_evs, 50, def_mod),
            "special_attack": calculate_stat(base_stats["special_attack"], 31, 0 if is_physical else atk_evs, 50, spa_mod),
            "special_defense": calculate_stat(base_stats["special_defense"], 31, spd_evs, 50, spd_mod),
            "speed": calculate_stat(base_stats["speed"], 31, speed_evs_needed, 50, speed_mod)
        }

        # 5b. Re-run damage on the FINAL spread for every survival benchmark.
        # The search loop reports the % at search-time (often 0 HP / max Def);
        # the leftover-redistribution step then bumps HP, lowering the actual
        # final %. We rewrite each "Survives ..." message with the real
        # final-spread numbers so users see what they actually copy-paste.
        if survive_hits:
            final_defender_evs = EVSpread(
                hp=hp_evs,
                defense=def_evs,
                special_defense=spd_evs,
                attack=atk_evs if is_physical else 0,
                special_attack=0 if is_physical else atk_evs,
                speed=speed_evs_needed,
            )
            rewritten_msgs: list[str] = []
            for hit in survive_hits:
                attacker_name = hit.get("attacker", "")
                move_name = hit.get("move", "")
                attacker_item = hit.get("item")
                attacker_ability = hit.get("ability")
                try:
                    atk_base2 = await pokeapi.get_base_stats(attacker_name)
                    atk_types2 = await pokeapi.get_pokemon_types(attacker_name)
                    move2 = await pokeapi.get_move(move_name)
                    if atk_base2 is None or move2 is None:
                        continue
                    is_phys2 = move2.category == MoveCategory.PHYSICAL
                    atk_nature2 = Nature.ADAMANT if is_phys2 else Nature.MODEST

                    # Re-fetch attacker item if not user-supplied (cheap; cached).
                    if not attacker_item:
                        try:
                            fmt_list = cfg.get_smogon_formats() if hasattr(cfg, "get_smogon_formats") else None
                            fmt_name = fmt_list[0] if fmt_list else None
                            rating = cfg.get_default_smogon_rating() or 1500
                            common = await smogon.get_common_sets(
                                attacker_name, format_name=fmt_name, rating=rating, limit=1,
                            )
                            if common and common.get("top_items"):
                                top = common["top_items"][0]
                                if top.get("name") and top["name"].lower() != "nothing":
                                    attacker_item = top["name"]
                        except Exception:
                            pass

                    stage_attack2 = -1 if (mega_intimidate_active and is_phys2) else 0
                    attacker2 = build_pokemon(
                        name=attacker_name,
                        base_stats=atk_base2,
                        types=atk_types2,
                        nature=atk_nature2,
                        spread=EVSpread(
                            attack=252 if is_phys2 else 0,
                            special_attack=0 if is_phys2 else 252,
                        ),
                        ability=attacker_ability,
                        item=attacker_item,
                    )
                    defender2 = build_pokemon(
                        name=pokemon_name,
                        base_stats=base_stats_model,
                        types=types,
                        nature=parsed_nature,
                        spread=final_defender_evs,
                        ability=defender_ability,
                    )
                    mods2 = DamageModifiers.from_scenario(
                        attacker_ability=attacker_ability,
                        attacker_item=attacker_item,
                        attack_stage=stage_attack2,
                    )
                    result2 = calculate_damage(attacker2, defender2, move2, mods2)
                    note = ""
                    if mega_intimidate_active and is_phys2:
                        note += " [Intimidate -1 Atk]"
                    if attacker_item:
                        note += f" [item={attacker_item}]"
                    if result2.max_percent < 100:
                        rewritten_msgs.append(
                            f"Survives {attacker_name} {move_name} "
                            f"({result2.min_damage}-{result2.max_damage} = "
                            f"{result2.min_percent:.1f}-{result2.max_percent:.1f}%){note}"
                        )
                    else:
                        verdict = "guaranteed OHKO" if result2.min_percent >= 100 else f"{result2.max_percent:.1f}% max — does NOT survive"
                        rewritten_msgs.append(
                            f"Cannot survive {attacker_name} {move_name} "
                            f"({result2.min_damage}-{result2.max_damage} = "
                            f"{result2.min_percent:.1f}-{result2.max_percent:.1f}%, {verdict}){note}"
                        )
                except Exception:
                    pass

            # Replace the search-time "Survives ..." entries with final-spread ones.
            if rewritten_msgs:
                benchmarks_met = [m for m in benchmarks_met if not m.startswith("Survives ")]
                benchmarks_failed = [m for m in benchmarks_failed if not m.startswith("Cannot survive ")]
                for msg in rewritten_msgs:
                    if msg.startswith("Survives "):
                        benchmarks_met.append(msg)
                    else:
                        benchmarks_failed.append(msg)

        spread = {
            "hp": hp_evs,
            "atk": atk_evs if is_physical else 0,
            "def": def_evs,
            "spa": 0 if is_physical else atk_evs,
            "spd": spd_evs,
            "spe": speed_evs_needed,
            "total": hp_evs + atk_evs + def_evs + spd_evs + speed_evs_needed
        }

        from vgc_mcp_core.formats.showdown import export_pokemon_to_showdown

        # Champions branch: convert the EV spread we built to SPs and emit the
        # showdown paste with `SPs:` instead of `EVs:`. The stat math is the
        # same (32 SP saturates to 252 EV); the `evs_to_sps_spread` helper
        # rounds up so we don't lose survival benchmarks.
        champions_block = None
        if is_champions:
            ev_obj = EVSpread(
                hp=hp_evs,
                attack=atk_evs if is_physical else 0,
                defense=def_evs,
                special_attack=0 if is_physical else atk_evs,
                special_defense=spd_evs,
                speed=speed_evs_needed,
            )
            sp_obj = evs_to_sps_spread(ev_obj, round_mode="ceil")
            sp_dict = {
                "hp": sp_obj.hp,
                "atk": sp_obj.attack,
                "def": sp_obj.defense,
                "spa": sp_obj.special_attack,
                "spd": sp_obj.special_defense,
                "spe": sp_obj.speed,
            }
            champions_paste = export_pokemon_to_showdown(
                species=pokemon_name,
                nature=nature.title(),
                sps=sp_dict,
            )
            champions_block = {
                "spread_sps": {
                    **sp_dict,
                    "total": sp_obj.total,
                },
                "showdown_paste": champions_paste,
                "format_system": "champions",
                "stat_units": "Stat Points (SPs)",
                "sp_budget_remaining": max(0, 66 - sp_obj.total),
            }
            summary = (
                f"{pokemon_name.title()} @ {nature.title()} (Champions): "
                f"{sp_obj.hp} HP / {sp_obj.attack if is_physical else 0} Atk / {sp_obj.defense} Def / "
                f"{0 if is_physical else sp_obj.special_attack} SpA / {sp_obj.special_defense} SpD / {sp_obj.speed} Spe SPs"
            )
        else:
            summary = (
                f"{pokemon_name.title()} @ {nature.title()}: "
                f"{hp_evs} HP / {atk_evs if is_physical else 0} Atk / {def_evs} Def / "
                f"{0 if is_physical else atk_evs} SpA / {spd_evs} SpD / {speed_evs_needed} Spe"
            )

        mainline_paste = export_pokemon_to_showdown(
            species=pokemon_name,
            nature=nature.title(),
            evs={
                "hp": hp_evs,
                "atk": atk_evs if is_physical else 0,
                "def": def_evs,
                "spa": 0 if is_physical else atk_evs,
                "spd": spd_evs,
                "spe": speed_evs_needed,
            },
        )

        # In a champions session the top-level `spread` and `showdown_paste`
        # must read in SP units (cap 32/stat, 66 total) so an LLM can't
        # surface EV-scale numbers (e.g. spa:252, total:252) as the answer.
        # We swap `spread` to the SP allocation and rename the mainline EV
        # paste to `ev_equivalent_showdown_paste` (clearly secondary) rather
        # than leaving `mainline_showdown_paste` to be mistaken for the
        # primary answer. Mainline sessions are unchanged.
        if champions_block:
            top_spread = {
                **champions_block["spread_sps"],
                "stat_units": "Stat Points (SPs)",
            }
        else:
            top_spread = spread

        response_kwargs = dict(
            pokemon=pokemon_name,
            nature=nature,
            spread=top_spread,
            final_stats=final_stats,
            benchmarks_met=benchmarks_met if benchmarks_met else ["No specific benchmarks requested"],
            benchmarks_failed=benchmarks_failed if benchmarks_failed else [],
            all_constraints_met=len(benchmarks_failed) == 0,
            summary=summary,
            format_system=format_system,
            showdown_paste=(champions_block["showdown_paste"] if champions_block else mainline_paste),
        )
        if champions_block:
            response_kwargs["champions"] = champions_block
            # Keep the EV-scale paste for reference but clearly tagged so it
            # can't be mistaken for the SP answer.
            response_kwargs["ev_equivalent_showdown_paste"] = mainline_paste
        else:
            response_kwargs["mainline_showdown_paste"] = mainline_paste
        return success_response(
            f"Designed spread for {pokemon_name}",
            **response_kwargs,
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def optimize_spread(
    pokeapi: Any,
    smogon: Any,
    pokemon_name: str,
    current_nature: Optional[str] = None,
    current_hp_evs: int = 0,
    current_atk_evs: int = 0,
    current_def_evs: int = 0,
    current_spa_evs: int = 0,
    current_spd_evs: int = 0,
    current_spe_evs: int = 0,
    current_spread: Optional[str] = None,
    target_speed: Optional[int] = None,
    outspeed_pokemon: Optional[str] = None,
    outspeed_pokemon_nature: str = 'jolly',
    outspeed_pokemon_evs: int = 252,
    survive_pokemon: Optional[str] = None,
    survive_move: Optional[str] = None,
    survive_pokemon_nature: str = 'adamant',
    survive_pokemon_evs: int = 252,
    survive_pokemon_item: Optional[str] = None,
    survive_pokemon_ability: Optional[str] = None,
    use_smogon_spreads: bool = False,
    smogon_spread_count: int = 3,
    max_damage_percent: Optional[float] = None,
    target_nko: Optional[int] = None,
    target_hp_stat: Optional[int] = None,
    target_atk_stat: Optional[int] = None,
    target_def_stat: Optional[int] = None,
    target_spa_stat: Optional[int] = None,
    target_spd_stat: Optional[int] = None,
) -> dict[str, Any]:
    if current_spread:
        try:
            current_hp_evs, current_atk_evs, current_def_evs, current_spa_evs, current_spd_evs, current_spe_evs = slash_values(current_spread)
        except ValueError as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(e))
    from vgc_mcp_core.calc.damage import calculate_damage
    from vgc_mcp_core.calc.modifiers import DamageModifiers
    from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat
    from vgc_mcp_core.models.move import MoveCategory
    from vgc_mcp_core.models.pokemon import (
        BaseStats,
        EVSpread,
        Nature,
        get_nature_modifier,
    )

    try:
        # Get Pokemon data
        pokemon_data = await pokeapi.get_pokemon(pokemon_name)

        base_stats = pokemon_data["base_stats"]
        types = pokemon_data.get("types", [])
        is_physical = base_stats["attack"] > base_stats["special_attack"]

        # Import EV normalization helper
        from vgc_mcp_core.config import EV_BREAKPOINTS_LV50, normalize_evs

        # Normalize input EVs to valid multiples of 4
        current_hp_evs = normalize_evs(current_hp_evs)
        current_atk_evs = normalize_evs(current_atk_evs)
        current_def_evs = normalize_evs(current_def_evs)
        current_spa_evs = normalize_evs(current_spa_evs)
        current_spd_evs = normalize_evs(current_spd_evs)
        current_spe_evs = normalize_evs(current_spe_evs)

        # Track current spread
        current_spread = {
            "hp": current_hp_evs,
            "atk": current_atk_evs,
            "def": current_def_evs,
            "spa": current_spa_evs,
            "spd": current_spd_evs,
            "spe": current_spe_evs,
            "total": current_hp_evs + current_atk_evs + current_def_evs + current_spa_evs + current_spd_evs + current_spe_evs
        }

        # Optimization results
        optimized = {
            "hp": 0,
            "atk": 0,
            "def": 0,
            "spa": 0,
            "spd": 0,
            "spe": 0
        }
        benchmarks_hit = []
        changes = []

        # Determine best nature
        suggested_nature = current_nature
        if not suggested_nature:
            # Auto-suggest based on targets
            if target_speed or outspeed_pokemon:
                suggested_nature = "jolly" if is_physical else "timid"
            elif survive_pokemon:
                suggested_nature = "careful" if is_physical else "calm"
            else:
                suggested_nature = "adamant" if is_physical else "modest"

        try:
            parsed_nature = Nature(suggested_nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {suggested_nature}")

        # 1. Handle speed targeting
        speed_evs_needed = 0

        if target_speed:
            # Reverse-engineer EVs for target speed
            speed_mod = get_nature_modifier(parsed_nature, "speed")
            for ev in EV_BREAKPOINTS_LV50:
                calc_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                if calc_speed >= target_speed:
                    speed_evs_needed = ev
                    actual_speed = calc_speed
                    benchmarks_hit.append(f"Hits {actual_speed} Speed (target: {target_speed})")
                    break
            else:
                # Can't reach target, try bulk-first natures (prefer bulk boost over speed boost)
                for nature_try in ["bold", "calm", "impish", "careful", "jolly", "timid"]:
                    try:
                        test_nature = Nature(nature_try)
                        test_mod = get_nature_modifier(test_nature, "speed")
                        for ev in EV_BREAKPOINTS_LV50:
                            calc_speed = calculate_stat(base_stats["speed"], 31, ev, 50, test_mod)
                            if calc_speed >= target_speed:
                                speed_evs_needed = ev
                                suggested_nature = nature_try
                                parsed_nature = test_nature
                                actual_speed = calc_speed
                                benchmarks_hit.append(f"Hits {actual_speed} Speed with {nature_try.title()} nature")
                                changes.append(f"Changed nature to {nature_try.title()} to reach speed target")
                                break
                        if speed_evs_needed > 0:
                            break
                    except ValueError:
                        pass

        elif outspeed_pokemon:
            # Calculate target's speed and find EVs to outspeed
            try:
                target_data = await pokeapi.get_pokemon(outspeed_pokemon)
                if target_data:
                    target_nature = Nature(outspeed_pokemon_nature.lower())
                    target_speed_mod = get_nature_modifier(target_nature, "speed")
                    target_speed_stat = calculate_stat(
                        target_data["base_stats"]["speed"], 31, outspeed_pokemon_evs, 50, target_speed_mod
                    )

                    speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                        if my_speed > target_speed_stat:
                            speed_evs_needed = ev
                            benchmarks_hit.append(f"Outspeeds {outspeed_pokemon} ({my_speed} vs {target_speed_stat})")
                            break
                    else:
                        # Try bulk-first natures (prefer bulk boost over speed boost)
                        for nature_try in ["bold", "calm", "impish", "careful", "jolly", "timid"]:
                            try:
                                test_nature = Nature(nature_try)
                                test_mod = get_nature_modifier(test_nature, "speed")
                                for ev in EV_BREAKPOINTS_LV50:
                                    my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, test_mod)
                                    if my_speed > target_speed_stat:
                                        speed_evs_needed = ev
                                        suggested_nature = nature_try
                                        parsed_nature = test_nature
                                        benchmarks_hit.append(f"Outspeeds {outspeed_pokemon} with {nature_try.title()} ({my_speed} vs {target_speed_stat})")
                                        changes.append(f"Changed nature to {nature_try.title()} to outspeed")
                                        break
                                if speed_evs_needed > 0:
                                    break
                            except ValueError:
                                pass
                        if speed_evs_needed == 0:
                            benchmarks_hit.append(f"Cannot outspeed {outspeed_pokemon} ({target_speed_stat}) - max 252 Speed EVs")
                            speed_evs_needed = 252
            except Exception as e:
                benchmarks_hit.append(f"Error checking {outspeed_pokemon}: {str(e)}")

        optimized["spe"] = speed_evs_needed

        # 2. Handle survival/damage targeting
        remaining_evs = 508 - speed_evs_needed
        smogon_calcs = []  # Results from each Smogon spread

        if survive_pokemon and survive_move:
            try:
                atk_data = await pokeapi.get_pokemon(survive_pokemon)
                move = await pokeapi.get_move(survive_move)

                if atk_data and move:
                    is_phys_move = move.category == MoveCategory.PHYSICAL
                    atk_types = await pokeapi.get_pokemon_types(survive_pokemon)

                    # Build list of attacker spreads to check against
                    attacker_spreads = []

                    if use_smogon_spreads:
                        # Fetch top spreads from Smogon
                        try:
                            smogon_data = await smogon.get_pokemon_usage(survive_pokemon)
                            if smogon_data and "spreads" in smogon_data:
                                # spreads is a list of pre-parsed dicts from get_pokemon_usage
                                spreads_list = smogon_data["spreads"][:smogon_spread_count]

                                for spread in spreads_list:
                                    try:
                                        nature_str = spread.get("nature", "modest")
                                        evs = spread.get("evs", {})
                                        usage_pct = spread.get("usage", 0)

                                        atk_nature = Nature(nature_str.lower())
                                        attacker_spreads.append({
                                            "nature": atk_nature,
                                            "evs": EVSpread(
                                                hp=evs.get("hp", 0),
                                                attack=evs.get("attack", 0),
                                                defense=evs.get("defense", 0),
                                                special_attack=evs.get("special_attack", 0),
                                                special_defense=evs.get("special_defense", 0),
                                                speed=evs.get("speed", 0)
                                            ),
                                            "usage": usage_pct,
                                            "description": spread.get("spread_string", f"{nature_str}") + f" ({usage_pct:.1f}%)"
                                        })
                                    except (ValueError, KeyError):
                                        continue

                            if not attacker_spreads:
                                benchmarks_hit.append(f"No Smogon spreads found for {survive_pokemon}, using default")
                        except Exception as e:
                            benchmarks_hit.append(f"Could not fetch Smogon data: {str(e)}, using default")

                    # If no Smogon spreads or not using them, use the provided/default spread
                    if not attacker_spreads:
                        atk_nature = Nature(survive_pokemon_nature.lower())
                        attacker_spreads.append({
                            "nature": atk_nature,
                            "evs": EVSpread(
                                attack=survive_pokemon_evs if is_phys_move else 0,
                                special_attack=0 if is_phys_move else survive_pokemon_evs
                            ),
                            "usage": 100.0,
                            "description": f"{survive_pokemon_nature.title()} {survive_pokemon_evs} {'Atk' if is_phys_move else 'SpA'}"
                        })

                    # Determine target threshold based on parameters
                    if max_damage_percent is not None:
                        target_max_damage = max_damage_percent
                    elif target_nko is not None:
                        target_max_damage = 100.0 / target_nko
                    else:
                        target_max_damage = 99.9

                    # Find minimum bulk to survive the WORST case (highest damage spread)
                    best_hp = 0
                    best_def = 0
                    target_met = False
                    worst_result = None

                    for hp_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev > min(252, remaining_evs):
                            break
                        for def_ev in EV_BREAKPOINTS_LV50:
                            if def_ev > min(252, remaining_evs - hp_ev):
                                break
                            if hp_ev + def_ev > remaining_evs:
                                break

                            defender = build_pokemon(
                                name=pokemon_name,
                                base_stats=BaseStats(**base_stats),
                                types=types,
                                nature=parsed_nature,
                                spread=EVSpread(
                                    hp=hp_ev,
                                    defense=def_ev if is_phys_move else 0,
                                    special_defense=0 if is_phys_move else def_ev
                                ),
                            )

                            # Check against ALL attacker spreads
                            all_survive = True
                            max_damage_seen = 0

                            for atk_spread in attacker_spreads:
                                attacker = build_pokemon(
                                    name=survive_pokemon,
                                    base_stats=BaseStats(**atk_data["base_stats"]),
                                    types=atk_types,
                                    nature=atk_spread["nature"],
                                    spread=atk_spread["evs"],
                                    ability=survive_pokemon_ability,
                                    item=survive_pokemon_item,
                                )

                                modifiers = DamageModifiers.from_scenario(
                                    attacker_ability=survive_pokemon_ability,
                                    attacker_item=survive_pokemon_item,
                                )
                                result = calculate_damage(attacker, defender, move, modifiers)

                                if result.max_percent > target_max_damage:
                                    all_survive = False
                                if result.max_percent > max_damage_seen:
                                    max_damage_seen = result.max_percent
                                    worst_result = result

                            if all_survive:
                                best_hp = hp_ev
                                best_def = def_ev
                                target_met = True
                                break
                        if target_met:
                            break

                    # Record damage calcs from each spread at the optimized EVs
                    if target_met or best_hp > 0 or best_def > 0:
                        final_defender = build_pokemon(
                            name=pokemon_name,
                            base_stats=BaseStats(**base_stats),
                            types=types,
                            nature=parsed_nature,
                            spread=EVSpread(
                                hp=best_hp if target_met else 252,
                                defense=(best_def if is_phys_move else 0) if target_met else (252 if is_phys_move else 0),
                                special_defense=(0 if is_phys_move else best_def) if target_met else (0 if is_phys_move else 252)
                            ),
                        )

                        for atk_spread in attacker_spreads:
                            attacker = build_pokemon(
                                name=survive_pokemon,
                                base_stats=BaseStats(**atk_data["base_stats"]),
                                types=atk_types,
                                nature=atk_spread["nature"],
                                spread=atk_spread["evs"],
                                ability=survive_pokemon_ability,
                                item=survive_pokemon_item,
                            )

                            modifiers = DamageModifiers.from_scenario(
                                attacker_ability=survive_pokemon_ability,
                                attacker_item=survive_pokemon_item,
                            )
                            result = calculate_damage(attacker, final_defender, move, modifiers)

                            smogon_calcs.append({
                                "spread": atk_spread["description"],
                                "usage": atk_spread["usage"],
                                "damage_range": f"{result.min_damage}-{result.max_damage}",
                                "percent_range": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
                                "survives": result.max_percent < 100,
                                "ko_chance": result.ko_chance
                            })

                    if target_met:
                        optimized["hp"] = best_hp
                        if is_phys_move:
                            optimized["def"] = best_def
                        else:
                            optimized["spd"] = best_def

                        item_note = f" with {survive_pokemon_item}" if survive_pokemon_item else ""
                        spread_note = f" (vs {len(attacker_spreads)} spreads)" if use_smogon_spreads and len(attacker_spreads) > 1 else ""
                        if max_damage_percent is not None:
                            benchmarks_hit.append(
                                f"Takes max {worst_result.max_percent:.0f}% from {survive_pokemon} {survive_move}{item_note}{spread_note}"
                            )
                        elif target_nko is not None:
                            benchmarks_hit.append(
                                f"Is {target_nko}HKO'd by {survive_pokemon} {survive_move}{item_note}{spread_note}"
                            )
                        else:
                            benchmarks_hit.append(
                                f"Survives {survive_pokemon} {survive_move}{item_note}{spread_note} ({worst_result.min_percent:.0f}-{worst_result.max_percent:.0f}%)"
                            )
                    else:
                        if max_damage_percent is not None:
                            benchmarks_hit.append(f"Cannot limit {survive_pokemon} {survive_move} to {max_damage_percent:.0f}% with available EVs")
                        elif target_nko is not None:
                            benchmarks_hit.append(f"Cannot be {target_nko}HKO'd by {survive_pokemon} {survive_move} with available EVs")
                        else:
                            benchmarks_hit.append(f"Cannot survive {survive_pokemon} {survive_move} with available EVs")

            except Exception as e:
                benchmarks_hit.append(f"Error checking survival: {str(e)}")

        # 3. Handle target stat values
        if target_hp_stat:
            for ev in EV_BREAKPOINTS_LV50:
                hp = calculate_hp(base_stats["hp"], 31, ev, 50)
                if hp >= target_hp_stat:
                    optimized["hp"] = max(optimized["hp"], ev)
                    benchmarks_hit.append(f"Hits {hp} HP (target: {target_hp_stat})")
                    break

        if target_atk_stat:
            atk_mod = get_nature_modifier(parsed_nature, "attack")
            for ev in EV_BREAKPOINTS_LV50:
                atk = calculate_stat(base_stats["attack"], 31, ev, 50, atk_mod)
                if atk >= target_atk_stat:
                    optimized["atk"] = max(optimized["atk"], ev)
                    benchmarks_hit.append(f"Hits {atk} Attack (target: {target_atk_stat})")
                    break

        if target_def_stat:
            def_mod = get_nature_modifier(parsed_nature, "defense")
            for ev in EV_BREAKPOINTS_LV50:
                defense = calculate_stat(base_stats["defense"], 31, ev, 50, def_mod)
                if defense >= target_def_stat:
                    optimized["def"] = max(optimized["def"], ev)
                    benchmarks_hit.append(f"Hits {defense} Defense (target: {target_def_stat})")
                    break

        if target_spa_stat:
            spa_mod = get_nature_modifier(parsed_nature, "special_attack")
            for ev in EV_BREAKPOINTS_LV50:
                spa = calculate_stat(base_stats["special_attack"], 31, ev, 50, spa_mod)
                if spa >= target_spa_stat:
                    optimized["spa"] = max(optimized["spa"], ev)
                    benchmarks_hit.append(f"Hits {spa} Sp. Atk (target: {target_spa_stat})")
                    break

        if target_spd_stat:
            spd_mod = get_nature_modifier(parsed_nature, "special_defense")
            for ev in EV_BREAKPOINTS_LV50:
                spd = calculate_stat(base_stats["special_defense"], 31, ev, 50, spd_mod)
                if spd >= target_spd_stat:
                    optimized["spd"] = max(optimized["spd"], ev)
                    benchmarks_hit.append(f"Hits {spd} Sp. Def (target: {target_spd_stat})")
                    break

        # 4. Calculate final stats
        speed_mod = get_nature_modifier(parsed_nature, "speed")
        atk_mod = get_nature_modifier(parsed_nature, "attack")
        spa_mod = get_nature_modifier(parsed_nature, "special_attack")
        def_mod = get_nature_modifier(parsed_nature, "defense")
        spd_mod = get_nature_modifier(parsed_nature, "special_defense")

        optimized["total"] = sum([optimized["hp"], optimized["atk"], optimized["def"],
                                   optimized["spa"], optimized["spd"], optimized["spe"]])

        final_stats = {
            "hp": calculate_hp(base_stats["hp"], 31, optimized["hp"], 50),
            "attack": calculate_stat(base_stats["attack"], 31, optimized["atk"], 50, atk_mod),
            "defense": calculate_stat(base_stats["defense"], 31, optimized["def"], 50, def_mod),
            "special_attack": calculate_stat(base_stats["special_attack"], 31, optimized["spa"], 50, spa_mod),
            "special_defense": calculate_stat(base_stats["special_defense"], 31, optimized["spd"], 50, spd_mod),
            "speed": calculate_stat(base_stats["speed"], 31, optimized["spe"], 50, speed_mod)
        }

        # 5. Compare with current spread
        ev_savings = current_spread["total"] - optimized["total"]
        if current_spread["total"] > 0:
            if ev_savings > 0:
                changes.append(f"Saved {ev_savings} EVs compared to current spread")
            elif ev_savings < 0:
                changes.append(f"Needs {-ev_savings} more EVs than current spread")

            # Detail specific changes
            for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
                diff = optimized[stat] - current_spread[stat]
                if diff != 0:
                    stat_name = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}[stat]
                    if diff > 0:
                        changes.append(f"+{diff} {stat_name} EVs")
                    else:
                        changes.append(f"{diff} {stat_name} EVs")

        # Format summary
        summary = (
            f"{pokemon_name.title()} @ {suggested_nature.title()}: "
            f"{optimized['hp']} HP / {optimized['atk']} Atk / {optimized['def']} Def / "
            f"{optimized['spa']} SpA / {optimized['spd']} SpD / {optimized['spe']} Spe"
        )

        result = success_response(
            f"Optimized spread for {pokemon_name}",
            pokemon=pokemon_name,
            optimized_nature=suggested_nature,
            optimized_spread=optimized,
            final_stats=final_stats,
            benchmarks_hit=benchmarks_hit if benchmarks_hit else ["No specific targets - using minimal EVs"],
            changes_from_current=changes if changes else ["No current spread provided"],
            ev_savings=ev_savings if current_spread["total"] > 0 else "N/A",
            remaining_evs=508 - optimized["total"],
            summary=summary,
            showdown_format=(
                f"{pokemon_name.title()}\n"
                f"EVs: {optimized['hp']} HP / {optimized['atk']} Atk / {optimized['def']} Def / "
                f"{optimized['spa']} SpA / {optimized['spd']} SpD / {optimized['spe']} Spe\n"
                f"{suggested_nature.title()} Nature"
            )
        )

        # Add Smogon calcs if we checked against multiple spreads
        if smogon_calcs:
            result["smogon_calcs"] = smogon_calcs

        return result

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
