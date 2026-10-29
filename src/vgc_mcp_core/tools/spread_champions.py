"""Champions (Stat Point) branches of the spread tools.

These mirror the EV tools but emit SP-scale spreads (0-32/stat, <=66 total)
via StatPointSpread + format_system='champions', so any returned
showdown_paste is an 'SPs:' paste. They are only reached when the active
session is the Champions format (see detect_champions_format).
"""

from typing import Any, Optional

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.champions_optimization import (
    SP_PER_STAT_MAX,
    SP_TOTAL_MAX,
    complete_sp_allocation,
    design_speed_benchmark_sps,
    find_optimal_hp_sps,
    find_speed_sps_to_outspeed,
    validate_sp_allocation,
)
from vgc_mcp_core.calc.conversion import ev_to_sp
from vgc_mcp_core.calc.damage import calculate_damage, format_percent
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats_champions import (
    calculate_hp_sp,
    calculate_stat_sp,
)
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.move import GEN9_SPECIAL_MOVES, MoveCategory
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    Nature,
    StatPointSpread,
    get_nature_modifier,
)
from vgc_mcp_core.tools import spread_common
from vgc_mcp_core.tools import spread_contract as sc
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.spread_common import (
    META_SYNERGIES,
    _build_champions_pokemon,
    offensive_investment,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response
from vgc_mcp_core.utils.normalize import normalize_move


async def _suggest_spread_champions(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    base_stats: BaseStats,
    role: str,
    speed_target: Optional[int],
    item: Optional[str],
) -> dict[str, Any]:
    """SP-scale version of suggest_spread (cap 32/stat, 66 total)."""
    is_physical = base_stats.attack >= base_stats.special_attack
    off_stat = "attack" if is_physical else "special_attack"
    offensive_label = "Attack" if is_physical else "Sp. Atk"

    # SP role templates (full-budget allocations, <=66 total, <=32/stat).
    if role == "offensive":
        nature_name = "Jolly" if is_physical else "Timid"
        sp_kwargs = {off_stat: SP_PER_STAT_MAX, "speed": SP_PER_STAT_MAX, "hp": 2}
        description = f"Max {offensive_label} and Speed for maximum damage output"
    elif role == "bulky":
        nature_name = "Calm" if base_stats.special_defense > base_stats.defense else "Bold"
        sp_kwargs = {"hp": SP_PER_STAT_MAX, "defense": 17, "special_defense": 17}
        description = "Maximum HP with balanced defenses"
    elif role == "bulky_offense":
        nature_name = "Adamant" if is_physical else "Modest"
        sp_kwargs = {"hp": SP_PER_STAT_MAX, off_stat: SP_PER_STAT_MAX, "special_defense": 2}
        description = f"Some bulk while maintaining {offensive_label}"
    elif role == "support":
        nature_name = "Bold"
        sp_kwargs = {"hp": SP_PER_STAT_MAX, "defense": SP_PER_STAT_MAX, "special_defense": 2}
        description = "Maximum bulk for supporting the team"
    else:
        return error_response(
            ErrorCodes.INTERNAL_ERROR,
            f'Unknown role: {role}. Use: offensive, bulky, bulky_offense, support',
        )

    nature_enum = Nature(nature_name.lower())

    # Speed target override (offensive role) — route through the SP solver.
    if speed_target and role == "offensive":
        needed = find_speed_sps_to_outspeed(
            base_stats.speed, speed_target - 1, nature_enum
        )
        if needed is not None and needed < SP_PER_STAT_MAX:
            leftover = SP_PER_STAT_MAX - needed
            sp_kwargs["speed"] = needed
            sp_kwargs["hp"] = min(SP_PER_STAT_MAX, sp_kwargs.get("hp", 0) + leftover)
            description += f" (Speed creep to {speed_target})"

    # HP-number optimization for the held item, on the SP grain.
    hp_optimization = None
    if item and sp_kwargs.get("hp", 0) > 0:
        from vgc_mcp_core.calc.hp_optimization import _get_item_category
        if _get_item_category(item) is not None:
            ranked = find_optimal_hp_sps(base_stats.hp, item)
            # Pick the best-scoring option that does not exceed the planned HP SP.
            cap = sp_kwargs["hp"]
            viable = [o for o in ranked if o["sp"] <= cap]
            if viable:
                best_hp = max(viable, key=lambda o: (o["score"], o["sp"]))
                if best_hp["sp"] != sp_kwargs["hp"]:
                    hp_optimization = best_hp
                    sp_kwargs["hp"] = best_hp["sp"]

    # Preserve the Speed target and any optimized HP number while spending
    # all 66 points. Defenses absorb both HP overflow and item savings.
    sp_kwargs = complete_sp_allocation(
        sp_kwargs, priorities=("defense", "special_defense", off_stat),
    )

    sps = StatPointSpread(**sp_kwargs)
    types = await pokeapi.get_pokemon_types(pokemon_name)
    suggested_pokemon = _build_champions_pokemon(
        pokemon_name, base_stats, types, nature_enum, sps, item=item
    )
    showdown_paste = pokemon_build_to_showdown(suggested_pokemon)

    spread = {
        "description": description,
        "nature": nature_name,
        "sps": {
            "hp": sps.hp,
            "attack": sps.attack,
            "defense": sps.defense,
            "special_attack": sps.special_attack,
            "special_defense": sps.special_defense,
            "speed": sps.speed,
        },
        "total_sps": sps.total,
    }

    result = {
        "pokemon": pokemon_name,
        "role": role,
        "format_system": "champions",
        "suggestion": spread,
        "base_stats": {
            "hp": base_stats.hp,
            "attack": base_stats.attack,
            "defense": base_stats.defense,
            "special_attack": base_stats.special_attack,
            "special_defense": base_stats.special_defense,
            "speed": base_stats.speed,
        },
        "showdown_paste": showdown_paste,
    }
    if hp_optimization:
        result["hp_optimization"] = hp_optimization
    return result


async def _optimize_bulk_champions(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    base_stats: BaseStats,
    parsed_nature: Nature,
    total_bulk_sps: int,
    defense_bias: float,
    item: Optional[str],
) -> dict[str, Any]:
    """SP-scale version of optimize_bulk (cap 32/stat, 66 total)."""
    total_bulk_sps = max(0, min(SP_TOTAL_MAX, total_bulk_sps))
    def_mod = get_nature_modifier(parsed_nature, "defense")
    spd_mod = get_nature_modifier(parsed_nature, "special_defense")

    best_spread = None
    best_bulk = -1.0
    for hp_sp in range(0, min(SP_PER_STAT_MAX, total_bulk_sps) + 1):
        remaining = total_bulk_sps - hp_sp
        for def_sp in range(0, min(SP_PER_STAT_MAX, remaining) + 1):
            spd_sp = remaining - def_sp
            if spd_sp < 0 or spd_sp > SP_PER_STAT_MAX:
                continue
            hp = calculate_hp_sp(base_stats.hp, 31, hp_sp, 50)
            def_stat = calculate_stat_sp(base_stats.defense, 31, def_sp, 50, def_mod)
            spd_stat = calculate_stat_sp(base_stats.special_defense, 31, spd_sp, 50, spd_mod)
            phys_bulk = hp * def_stat
            spec_bulk = hp * spd_stat
            total_bulk = phys_bulk * defense_bias + spec_bulk * (1 - defense_bias)
            if total_bulk > best_bulk:
                best_bulk = total_bulk
                best_spread = {
                    "hp_sps": hp_sp,
                    "def_sps": def_sp,
                    "spd_sps": spd_sp,
                    "final_hp": hp,
                    "final_def": def_stat,
                    "final_spd": spd_stat,
                    "physical_bulk": phys_bulk,
                    "special_bulk": spec_bulk,
                }

    hp_optimization = None
    if item and best_spread:
        from vgc_mcp_core.calc.hp_optimization import _get_item_category
        if _get_item_category(item) is not None:
            ranked = find_optimal_hp_sps(base_stats.hp, item)
            cap = best_spread["hp_sps"]
            minimum_hp = max(0, total_bulk_sps - 2 * SP_PER_STAT_MAX)
            viable = [o for o in ranked if minimum_hp <= o["sp"] <= cap]
            if viable:
                best_hp = max(viable, key=lambda o: (o["score"], o["sp"]))
                if best_hp["sp"] != best_spread["hp_sps"]:
                    best_spread["hp_sps"] = best_hp["sp"]
                    best_spread["final_hp"] = best_hp["hp_stat"]
                    best_spread["physical_bulk"] = best_hp["hp_stat"] * best_spread["final_def"]
                    best_spread["special_bulk"] = best_hp["hp_stat"] * best_spread["final_spd"]
                    hp_optimization = best_hp

    showdown_paste = None
    if best_spread:
        types = await pokeapi.get_pokemon_types(pokemon_name)
        sps = StatPointSpread(**complete_sp_allocation(
            {"hp": best_spread["hp_sps"], "defense": best_spread["def_sps"],
             "special_defense": best_spread["spd_sps"]},
            priorities=("defense", "special_defense") if defense_bias >= 0.5 else ("special_defense", "defense"),
            budget=total_bulk_sps,
        ))
        final_def = calculate_stat_sp(base_stats.defense, 31, sps.defense, 50, def_mod)
        final_spd = calculate_stat_sp(base_stats.special_defense, 31, sps.special_defense, 50, spd_mod)
        best_spread.update({
            "def_sps": sps.defense, "spd_sps": sps.special_defense,
            "final_def": final_def, "final_spd": final_spd,
            "physical_bulk": best_spread["final_hp"] * final_def,
            "special_bulk": best_spread["final_hp"] * final_spd,
        })
        optimized_pokemon = _build_champions_pokemon(
            pokemon_name, base_stats, types, parsed_nature, sps, item=item
        )
        showdown_paste = pokemon_build_to_showdown(optimized_pokemon)
        analysis_str = (
            f"Optimal bulk: {best_spread['hp_sps']} HP / {best_spread['def_sps']} Def / "
            f"{best_spread['spd_sps']} SpD SP for {pokemon_name}"
        )
    else:
        analysis_str = f"No optimal spread found for {pokemon_name}"

    result = {
        "pokemon": pokemon_name,
        "nature": parsed_nature.value,
        "format_system": "champions",
        "total_bulk_sps": total_bulk_sps,
        "defense_bias": defense_bias,
        "optimal_spread": best_spread,
        "showdown_paste": showdown_paste,
        "analysis": analysis_str,
    }
    if hp_optimization:
        result["hp_optimization"] = hp_optimization
    return result


def _min_sps_for_stat(base: int, target: int, nature_mod: float) -> int:
    """Minimum SP (0-32) to reach target non-HP stat under given nature."""
    for sp in range(0, SP_PER_STAT_MAX + 1):
        if calculate_stat_sp(base, 31, sp, 50, nature_mod) >= target:
            return sp
    return SP_PER_STAT_MAX


def _min_sps_for_hp(base: int, target: int) -> int:
    """Minimum SP (0-32) to reach target HP."""
    for sp in range(0, SP_PER_STAT_MAX + 1):
        if calculate_hp_sp(base, 31, sp, 50) >= target:
            return sp
    return SP_PER_STAT_MAX


async def _suggest_nature_optimization_champions(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    base_stats: BaseStats,
    current_nature: str,
    current_nature_enum: Nature,
    hp_sps: int,
    atk_sps: int,
    def_sps: int,
    spa_sps: int,
    spd_sps: int,
    spe_sps: int,
    moves: Optional[list[str]],
) -> dict[str, Any]:
    """SP-scale version of suggest_nature_optimization (cap 32/stat, 66 total)."""
    current_stats = {
        "hp": calculate_hp_sp(base_stats.hp, 31, hp_sps, 50),
        "attack": calculate_stat_sp(base_stats.attack, 31, atk_sps, 50, get_nature_modifier(current_nature_enum, "attack")),
        "defense": calculate_stat_sp(base_stats.defense, 31, def_sps, 50, get_nature_modifier(current_nature_enum, "defense")),
        "special_attack": calculate_stat_sp(base_stats.special_attack, 31, spa_sps, 50, get_nature_modifier(current_nature_enum, "special_attack")),
        "special_defense": calculate_stat_sp(base_stats.special_defense, 31, spd_sps, 50, get_nature_modifier(current_nature_enum, "special_defense")),
        "speed": calculate_stat_sp(base_stats.speed, 31, spe_sps, 50, get_nature_modifier(current_nature_enum, "speed")),
    }
    current_total = hp_sps + atk_sps + def_sps + spa_sps + spd_sps + spe_sps

    is_physical = False
    is_special = False
    if moves:
        for move_name in moves:
            try:
                move = await pokeapi.get_move(move_name)
                if move.category == MoveCategory.PHYSICAL:
                    is_physical = True
                elif move.category == MoveCategory.SPECIAL:
                    is_special = True
            except Exception:
                continue

    best_nature = None
    best_sps = None
    best_total = current_total
    best_stats = None

    for nature in Nature:
        if nature == current_nature_enum:
            continue
        if is_physical and get_nature_modifier(nature, "attack") < 1.0:
            continue
        if is_special and get_nature_modifier(nature, "special_attack") < 1.0:
            continue

        new = {
            "hp": _min_sps_for_hp(base_stats.hp, current_stats["hp"]),
            "attack": _min_sps_for_stat(base_stats.attack, current_stats["attack"], get_nature_modifier(nature, "attack")),
            "defense": _min_sps_for_stat(base_stats.defense, current_stats["defense"], get_nature_modifier(nature, "defense")),
            "special_attack": _min_sps_for_stat(base_stats.special_attack, current_stats["special_attack"], get_nature_modifier(nature, "special_attack")),
            "special_defense": _min_sps_for_stat(base_stats.special_defense, current_stats["special_defense"], get_nature_modifier(nature, "special_defense")),
            "speed": _min_sps_for_stat(base_stats.speed, current_stats["speed"], get_nature_modifier(nature, "speed")),
        }
        new_total = sum(new.values())

        new_stats = {
            "hp": calculate_hp_sp(base_stats.hp, 31, new["hp"], 50),
            "attack": calculate_stat_sp(base_stats.attack, 31, new["attack"], 50, get_nature_modifier(nature, "attack")),
            "defense": calculate_stat_sp(base_stats.defense, 31, new["defense"], 50, get_nature_modifier(nature, "defense")),
            "special_attack": calculate_stat_sp(base_stats.special_attack, 31, new["special_attack"], 50, get_nature_modifier(nature, "special_attack")),
            "special_defense": calculate_stat_sp(base_stats.special_defense, 31, new["special_defense"], 50, get_nature_modifier(nature, "special_defense")),
            "speed": calculate_stat_sp(base_stats.speed, 31, new["speed"], 50, get_nature_modifier(nature, "speed")),
        }

        stats_match = True
        if new_stats["hp"] < current_stats["hp"]:
            stats_match = False
        if is_physical and new_stats["attack"] < current_stats["attack"]:
            stats_match = False
        if is_special and new_stats["special_attack"] < current_stats["special_attack"]:
            stats_match = False
        if new_stats["speed"] < current_stats["speed"]:
            stats_match = False
        if new_stats["defense"] < current_stats["defense"]:
            stats_match = False
        if new_stats["special_defense"] < current_stats["special_defense"]:
            stats_match = False

        if stats_match and new_total < best_total:
            best_nature = nature
            best_sps = new
            best_total = new_total
            best_stats = new_stats

    types = await pokeapi.get_pokemon_types(pokemon_name)
    current_pokemon = _build_champions_pokemon(
        pokemon_name, base_stats, types, current_nature_enum,
        StatPointSpread(hp=hp_sps, attack=atk_sps, defense=def_sps,
                        special_attack=spa_sps, special_defense=spd_sps, speed=spe_sps),
    )
    current_showdown = pokemon_build_to_showdown(current_pokemon)

    if best_nature is None:
        return {
            "pokemon": pokemon_name,
            "current_nature": current_nature,
            "format_system": "champions",
            "optimization_found": False,
            "current_showdown_paste": current_showdown,
            "message": "Your nature is already optimal! No Stat Point savings possible.",
        }

    sp_savings = current_total - best_total
    optimized_pokemon = _build_champions_pokemon(
        pokemon_name, base_stats, types, best_nature,
        StatPointSpread(**best_sps),
    )
    optimized_showdown = pokemon_build_to_showdown(optimized_pokemon)

    return {
        "pokemon": pokemon_name,
        "current_nature": current_nature,
        "format_system": "champions",
        "current_sps": {
            "hp": hp_sps, "attack": atk_sps, "defense": def_sps,
            "special_attack": spa_sps, "special_defense": spd_sps, "speed": spe_sps,
        },
        "current_total_sps": current_total,
        "current_stats": current_stats,
        "current_showdown_paste": current_showdown,
        "suggested_nature": best_nature.value,
        "suggested_sps": best_sps,
        "suggested_total_sps": best_total,
        "remaining_sps": SP_TOTAL_MAX - best_total,
        "is_complete": best_total == SP_TOTAL_MAX,
        "suggested_stats": best_stats,
        "optimized_showdown_paste": optimized_showdown,
        "sp_savings": sp_savings,
        "optimization_found": True,
    }


async def _prepare_single_threat_build(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    attacker_name: str,
    move_name: str,
    nature_str: Optional[str],
    evs: Optional[int | str | dict[str, int]],
    item: Optional[str],
    ability: Optional[str],
    tera_type: Optional[str],
) -> dict[str, Any]:
    """Fetch and build a Champions attacker using native SP investment.

    Returns dict with attacker PokemonBuild, Move, modifiers, is_physical.
    Auto-fetches Smogon spread + meta synergies, same as the EV path.
    """
    atk_base = await pokeapi.get_base_stats(attacker_name)
    atk_types = await pokeapi.get_pokemon_types(attacker_name)
    move = await pokeapi.get_move(move_name, user_name=attacker_name)
    is_physical = move.category == MoveCategory.PHYSICAL

    off_stat = "attack" if is_physical else "special_attack"
    needs_source = None in (nature_str, evs, item, ability)
    evs = offensive_investment(evs, is_physical)
    allocation: dict[str, int] = {}
    sourced = await spread_common._get_common_spread(smogon, attacker_name)
    if sourced:
        if nature_str is None:
            nature_str = sourced.get("nature")
        if sourced.get("sps") is not None:
            allocation = StatPointSpread.from_sps_dict(sourced["sps"]).model_dump()
        elif sourced.get("evs"):
            allocation = {stat: ev_to_sp(value) for stat, value in sourced["evs"].items()}
        if item is None:
            item = sourced.get("item")
        if ability is None:
            ability = sourced.get("ability")

    key = attacker_name.lower().replace(" ", "-")
    if key in META_SYNERGIES:
        d_item, d_ability = META_SYNERGIES[key]
        item = item or d_item
        ability = ability or d_ability

    nature_str = nature_str or ("adamant" if is_physical else "modest")
    if evs is not None:
        if not 0 <= evs <= 252:
            raise ValueError("Offensive investment must be 0-32 SP or legacy EVs up to 252")
        allocation[off_stat] = ev_to_sp(evs) if evs > 32 else evs
    elif not allocation:
        allocation[off_stat] = SP_PER_STAT_MAX
    investment = allocation.get(off_stat, 0)
    # Explicit offense takes precedence; trim other assumed investments
    # if a sourced spread would otherwise exceed the Champions budget.
    overflow = max(0, sum(allocation.values()) - SP_TOTAL_MAX)
    for stat in ("hp", "defense", "special_defense", "speed", "attack", "special_attack"):
        if stat != off_stat:
            take = min(allocation.get(stat, 0), overflow)
            allocation[stat] = allocation.get(stat, 0) - take
            overflow -= take

    sword_of_ruin = beads_of_ruin = tablets_of_ruin = vessel_of_ruin = False
    if ability:
        al = ability.lower().replace(" ", "-").replace("_", "-")
        sword_of_ruin = al == "sword-of-ruin"
        beads_of_ruin = al == "beads-of-ruin"
        tablets_of_ruin = al == "tablets-of-ruin"
        vessel_of_ruin = al == "vessel-of-ruin"

    attacker = build_pokemon(
        name=attacker_name,
        base_stats=atk_base,
        types=atk_types,
        nature=Nature(nature_str.lower()),
        champions=True,
        spread=StatPointSpread(**allocation),
        item=item,
        ability=ability,
        tera_type=tera_type,
    )
    modifiers = DamageModifiers.from_scenario(
        attacker_item=item,
        attacker_ability=ability,
        tera_type=tera_type,
        is_critical=move.always_crit,
        sword_of_ruin=sword_of_ruin,
        beads_of_ruin=beads_of_ruin,
        tablets_of_ruin=tablets_of_ruin,
        vessel_of_ruin=vessel_of_ruin,
    )
    return {
        "attacker": attacker,
        "move": move,
        "modifiers": modifiers,
        "is_physical": is_physical,
        "nature": nature_str,
        "sps": investment,
        "item": item,
        "ability": ability,
        "tera_type": tera_type,
        "meta": sourced.get("meta") if sourced and needs_source else None,
    }


def _find_champions_survival_allocation(
    defender_name: str,
    my_base: BaseStats,
    my_types: list[str],
    parsed_nature: Nature,
    threats: list[dict[str, Any]],
    defender_item: Optional[str],
    defender_ability: Optional[str],
    defender_tera_type: Optional[str],
    sp_budget: int,
    offensive_sps: int = 0,
    offensive_stat: Optional[str] = None,
    target_survival: float = 93.75,
    speed_sps: int = 0,
) -> Optional[dict[str, Any]]:
    """Search the legal SP grid with exact final-build damage checks."""
    def targets_defense(threat: dict[str, Any]) -> bool:
        return bool(threat["is_physical"] or GEN9_SPECIAL_MOVES.get(
            normalize_move(threat["move"].name), {}).get("targets_physical_defense"))
    need_def = any(targets_defense(t) for t in threats)
    need_spd = any(not targets_defense(t) for t in threats)
    best = None
    for hp_sp in range(min(SP_PER_STAT_MAX, sp_budget) + 1):
        for def_sp in (range(SP_PER_STAT_MAX + 1) if need_def else [0]):
            for spd_sp in (range(SP_PER_STAT_MAX + 1) if need_spd else [0]):
                total = hp_sp + def_sp + spd_sp + offensive_sps
                if total > sp_budget or (best is not None and total >= best["total_sp"]):
                    break
                allocation = {"hp": hp_sp, "defense": def_sp, "special_defense": spd_sp, "speed": speed_sps}
                if offensive_sps and offensive_stat:
                    allocation[offensive_stat] = offensive_sps
                candidate = build_pokemon(
                    name=defender_name,
                    base_stats=my_base,
                    types=my_types,
                    nature=parsed_nature,
                    champions=True,
                    spread=StatPointSpread(**allocation),
                    ability=defender_ability,
                    item=defender_item,
                    tera_type=defender_tera_type,
                )
                worst = 0.0
                for threat in threats:
                    result = calculate_damage(threat["attacker"], candidate, threat["move"], threat["modifiers"])
                    if result.survival_percent < target_survival:
                        break
                    worst = max(worst, result.max_percent)
                else:
                    best = {"hp_sp": hp_sp, "def_sp": def_sp, "spd_sp": spd_sp,
                            "total_sp": total, "max_percent": worst, "verified": True}
                    break
    return best


async def _design_spread_with_benchmarks_champions(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    **kw,
) -> dict[str, Any]:
    """SP-scale version of design_spread_with_benchmarks (cap 32/stat, 66)."""
    pokemon_name = kw["pokemon_name"]
    my_base = kw["my_base"]
    my_types = kw["my_types"]
    nature = kw.get("nature")
    outspeed_pokemon = kw.get("outspeed_pokemon")
    outspeed_pokemon_nature = kw.get("outspeed_pokemon_nature", "jolly")
    outspeed_pokemon_evs = kw.get("outspeed_pokemon_evs", 252)
    survive_pokemon = kw.get("survive_pokemon")
    survive_move = kw.get("survive_move")
    prioritize = kw.get("prioritize", "bulk")
    item = kw.get("item")
    ability = kw.get("ability")
    defender_tera_type = kw.get("defender_tera_type")
    if bool(survive_pokemon) != bool(survive_move):
        return error_response(ErrorCodes.INVALID_PARAMETER, "Provide both survive_pokemon and survive_move")
    if defender_tera_type or kw.get("survive_pokemon_tera_type"):
        return error_response(ErrorCodes.INVALID_PARAMETER, "Terastallization is not available in Champions")
    if prioritize not in ("bulk", "offense"):
        return error_response(ErrorCodes.INVALID_PARAMETER, "prioritize must be 'bulk' or 'offense'")

    is_physical = my_base.attack >= my_base.special_attack
    off_stat = "attack" if is_physical else "special_attack"
    if nature is None:
        if prioritize == "offense":
            nature = "adamant" if is_physical else "modest"
        else:
            nature = "careful" if is_physical else "calm"
    try:
        parsed_nature = Nature(nature.lower())
    except ValueError:
        return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {nature}")

    results: dict[str, Any] = {
        "pokemon": pokemon_name,
        "nature": nature,
        "format_system": "champions",
        "benchmarks": {},
    }

    # 1. Speed benchmark on the SP grain.
    speed_sps = 0
    if outspeed_pokemon:
        try:
            target_base = await pokeapi.get_base_stats(outspeed_pokemon)
            target_nature = Nature(outspeed_pokemon_nature.lower())
            # Native 0-32 inputs are SP; retain legacy EV-scale defaults.
            target_sps = ev_to_sp(outspeed_pokemon_evs) if outspeed_pokemon_evs > 32 else outspeed_pokemon_evs
            benchmark = design_speed_benchmark_sps(
                my_base.speed, target_base.speed, target_sps, parsed_nature, target_nature,
                target_stage=kw.get("outspeed_at_speed_stage", 0),
                target_booster=kw.get("outspeed_target_has_booster", False),
                target_tailwind=kw.get("outspeed_target_has_tailwind", False),
                booster=kw.get("my_pokemon_has_booster", False),
                tailwind=kw.get("my_pokemon_has_tailwind", False),
            )
            speed_sps = benchmark["sps_needed"]
            results["benchmarks"]["speed"] = {
                "target": outspeed_pokemon,
                **benchmark,
            }
        except Exception as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, f"Cannot calculate speed benchmark: {e}")

    # 2. Offensive SP allocation.
    off_sps = 0
    if prioritize == "offense":
        requested = kw.get("offensive_evs", 0)
        off_sps = (ev_to_sp(requested) if requested > 32 else requested) if requested else SP_PER_STAT_MAX

    # 3. Survival.
    remaining = SP_TOTAL_MAX - speed_sps - off_sps
    hp_sp = def_sp = spd_sp = 0
    spec = None
    resolved_ability = ability
    if survive_pokemon and survive_move:
        try:
            spec = await _prepare_single_threat_build(pokeapi, smogon,
                survive_pokemon, survive_move,
                kw.get("survive_pokemon_nature"), kw.get("survive_pokemon_evs"),
                kw.get("survive_pokemon_item"), kw.get("survive_pokemon_ability"),
                kw.get("survive_pokemon_tera_type"),
            )
            from vgc_mcp_core.tools.ability_helpers import resolve_ability
            resolved_ability, _ = await resolve_ability(
                pokemon_name, pokeapi=pokeapi, smogon_client=smogon,
                user_override=ability,
            )
            alloc = _find_champions_survival_allocation(
                defender_name=pokemon_name,
                my_base=my_base,
                my_types=my_types,
                parsed_nature=parsed_nature,
                threats=[spec],
                defender_item=item,
                defender_ability=resolved_ability,
                defender_tera_type=defender_tera_type,
                sp_budget=SP_TOTAL_MAX - speed_sps,
                offensive_sps=off_sps,
                offensive_stat=off_stat,
                target_survival=93.75,
                speed_sps=speed_sps,
            )
            if alloc is None:
                results["benchmarks"]["survival"] = {
                    "attacker": survive_pokemon,
                    "move": survive_move,
                    "survives": False,
                    "note": "No SP allocation within 66 survives this hit.",
                }
            else:
                hp_sp = alloc["hp_sp"]
                def_sp = alloc["def_sp"]
                spd_sp = alloc["spd_sp"]
                results["benchmarks"]["survival"] = {
                    "attacker": survive_pokemon,
                    "move": survive_move,
                    "attacker_nature": spec["nature"],
                    "attacker_sps": spec["sps"],
                    "attacker_item": spec["item"],
                    "attacker_ability": spec["ability"],
                    "max_percent": alloc["max_percent"],
                    "survives": alloc["max_percent"] < 100,
                    "hp_remaining": f"{100 - alloc['max_percent']:.1f}%",
                }
        except Exception as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, f"Cannot calculate survival benchmark: {e}")
    else:
        # No survival target — dump remaining into HP/defenses.
        hp_sp = min(SP_PER_STAT_MAX, remaining)
        leftover = remaining - hp_sp
        def_sp = min(SP_PER_STAT_MAX, leftover // 2)
        spd_sp = min(SP_PER_STAT_MAX, leftover - def_sp)

    sp_kwargs = {"hp": hp_sp, "defense": def_sp, "special_defense": spd_sp, "speed": speed_sps}
    if off_sps:
        sp_kwargs[off_stat] = off_sps
    sp_kwargs = complete_sp_allocation(sp_kwargs)

    sps = StatPointSpread(**sp_kwargs)
    optimized_pokemon = _build_champions_pokemon(
        pokemon_name, my_base, my_types, parsed_nature, sps,
        item=item, tera_type=defender_tera_type, ability=resolved_ability,
    )
    if spec is not None:
        final_damage = calculate_damage(spec["attacker"], optimized_pokemon, spec["move"], spec["modifiers"])
        results["benchmarks"]["survival"].update({
            "survives": final_damage.survival_percent >= 93.75,
            "survival_pct": final_damage.survival_percent,
            "max_percent": final_damage.max_percent,
            "hp_remaining": f"{100 - final_damage.max_percent:.1f}%",
            "attacker_showdown_paste": pokemon_build_to_showdown(spec["attacker"]),
            "verified": final_damage.survival_percent >= 93.75,
        })
    final_stats = {
        "hp": calculate_hp_sp(my_base.hp, 31, sps.hp, 50),
        "attack": calculate_stat_sp(my_base.attack, 31, sps.attack, 50, get_nature_modifier(parsed_nature, "attack")),
        "defense": calculate_stat_sp(my_base.defense, 31, sps.defense, 50, get_nature_modifier(parsed_nature, "defense")),
        "special_attack": calculate_stat_sp(my_base.special_attack, 31, sps.special_attack, 50, get_nature_modifier(parsed_nature, "special_attack")),
        "special_defense": calculate_stat_sp(my_base.special_defense, 31, sps.special_defense, 50, get_nature_modifier(parsed_nature, "special_defense")),
        "speed": calculate_stat_sp(my_base.speed, 31, sps.speed, 50, get_nature_modifier(parsed_nature, "speed")),
    }
    results["spread"] = {
        "hp_sps": sps.hp,
        "atk_sps": sps.attack,
        "def_sps": sps.defense,
        "spa_sps": sps.special_attack,
        "spd_sps": sps.special_defense,
        "spe_sps": sps.speed,
        "total": sps.total,
    }
    results["final_stats"] = final_stats
    results["verified"] = all(
        benchmark.get("outspeeds", benchmark.get("verified", False))
        for benchmark in results["benchmarks"].values()
    )
    results["verdict"] = "SUCCESS" if results["verified"] else "BENCHMARK_NOT_MET"
    results["showdown_paste"] = pokemon_build_to_showdown(optimized_pokemon)
    return sc.contract(results, optimized_pokemon, sc.benchmark_parts(results["benchmarks"]),
                       {"attacker": spec["attacker"]} if spec else {}, [spec["meta"] if spec else None])


async def _optimize_multi_survival_champions(
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient],
    pokemon_name: str,
    my_base: BaseStats,
    my_types: list[str],
    nature: Optional[str],
    threats: list[dict[str, Any]],
    outspeed_pokemon: Optional[str],
    outspeed_pokemon_nature: str,
    outspeed_pokemon_evs: int,
    defender_tera_type: Optional[str],
    target_survival: float,
    item: Optional[str],
    ability: Optional[str],
    target_stage: int = 0,
    target_booster: bool = False,
    target_tailwind: bool = False,
    booster: bool = False,
    tailwind: bool = False,
    speed_override: Optional[int] = None,
    fill_remaining: bool = True,
) -> dict[str, Any]:
    """SP-scale multi/dual survival optimizer (cap 32/stat, 66 total).

    fill_remaining=False returns the minimum survival allocation instead of
    spending the leftover budget on HP/Def/SpD.
    """
    if defender_tera_type or any(threat.get("tera_type") for threat in threats):
        return error_response(ErrorCodes.INVALID_PARAMETER, "Terastallization is not available in Champions")
    is_physical = my_base.attack >= my_base.special_attack
    if nature is None:
        nature = "careful" if is_physical else "calm"
    try:
        parsed_nature = Nature(nature.lower())
    except ValueError:
        return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {nature}")

    # Speed benchmark.
    fixed_sps = (ev_to_sp(speed_override) if speed_override > 32 else speed_override) if speed_override is not None else None
    speed_sps = fixed_sps if fixed_sps is not None else 0
    speed_info = None
    if outspeed_pokemon:
        try:
            target_base = await pokeapi.get_base_stats(outspeed_pokemon)
            target_sps = ev_to_sp(outspeed_pokemon_evs) if outspeed_pokemon_evs > 32 else outspeed_pokemon_evs
            benchmark = design_speed_benchmark_sps(
                my_base.speed, target_base.speed, target_sps, parsed_nature,
                Nature(outspeed_pokemon_nature.lower()),
                target_stage=target_stage, target_booster=target_booster,
                target_tailwind=target_tailwind, booster=booster, tailwind=tailwind,
                fixed_sps=fixed_sps,
            )
            speed_sps = benchmark["sps_needed"]
            speed_info = {
                "target": outspeed_pokemon,
                **benchmark,
            }
        except Exception as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, f"Cannot calculate speed benchmark: {e}")

    # Prepare threats with the same Champions stat system as the defender.
    prepared = []
    for t in threats:
        spec = await _prepare_single_threat_build(pokeapi, smogon,
            t["attacker"], t["move"], t.get("nature"), t.get("evs"),
            t.get("item"), t.get("ability"), t.get("tera_type"),
        )
        prepared.append(spec)

    from vgc_mcp_core.tools.ability_helpers import resolve_ability
    resolved_ability, _ = await resolve_ability(
        pokemon_name, pokeapi=pokeapi, smogon_client=smogon, user_override=ability,
    )

    alloc = _find_champions_survival_allocation(
        defender_name=pokemon_name,
        my_base=my_base,
        my_types=my_types,
        parsed_nature=parsed_nature,
        threats=prepared,
        defender_item=item,
        defender_ability=resolved_ability,
        defender_tera_type=defender_tera_type,
        sp_budget=SP_TOTAL_MAX - speed_sps,
        target_survival=target_survival,
        speed_sps=speed_sps,
    )

    threat_builds = [spec["attacker"] for spec in prepared]
    if alloc is None:
        impossible = {
            "pokemon": pokemon_name,
            "format_system": "champions",
            "verdict": "IMPOSSIBLE",
            "message": (
                "No Stat Point allocation within the 66-point budget survives "
                "all threats at the requested survival rate."
            ),
            "speed_benchmark": speed_info,
        }
        return sc.apply_contract(
            impossible,
            headline=f"No {sc.species(pokemon_name)} spread within 66 SP survives all {len(prepared)} hits",
            spreads_used={k: sc.spread_label(b) for k, b in sc.attackers(threat_builds).items()},
            data_source=sc.data_source_from_meta(sc.first_meta(spec["meta"] for spec in prepared)),
        )

    minimum = {
        "hp": alloc["hp_sp"], "defense": alloc["def_sp"],
        "special_defense": alloc["spd_sp"], "speed": speed_sps,
    }
    sps = StatPointSpread(**(complete_sp_allocation(minimum) if fill_remaining else minimum))
    optimized_pokemon = _build_champions_pokemon(
        pokemon_name, my_base, my_types, parsed_nature, sps,
        item=item, tera_type=defender_tera_type, ability=resolved_ability,
    )

    # Per-threat breakdown.
    breakdown = []
    for spec in prepared:
        defender = optimized_pokemon
        result = calculate_damage(spec["attacker"], defender, spec["move"], spec["modifiers"])
        breakdown.append({
            "attacker": spec["attacker"].name,
            "move": spec["move"].name,
            "damage_percent": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
            "survival_pct": result.survival_percent,
            "survives": result.survival_percent >= target_survival,
            "attacker_showdown_paste": pokemon_build_to_showdown(spec["attacker"]),
        })

    final_stats = {
        "hp": calculate_hp_sp(my_base.hp, 31, sps.hp, 50),
        "defense": calculate_stat_sp(my_base.defense, 31, sps.defense, 50, get_nature_modifier(parsed_nature, "defense")),
        "special_defense": calculate_stat_sp(my_base.special_defense, 31, sps.special_defense, 50, get_nature_modifier(parsed_nature, "special_defense")),
        "speed": calculate_stat_sp(my_base.speed, 31, sps.speed, 50, get_nature_modifier(parsed_nature, "speed")),
    }

    payload = {
        "pokemon": pokemon_name,
        "nature": nature,
        "format_system": "champions",
        "verdict": "SUCCESS" if all(row["survives"] for row in breakdown) and (speed_info is None or speed_info.get("outspeeds", False)) else "BENCHMARK_NOT_MET",
        "verified": all(row["survives"] for row in breakdown) and (speed_info is None or speed_info.get("outspeeds", False)),
        "spread": {
            "hp_sps": sps.hp,
            "def_sps": sps.defense,
            "spd_sps": sps.special_defense,
            "spe_sps": sps.speed,
            "total": sps.total,
        },
        "final_stats": final_stats,
        "speed_benchmark": speed_info,
        "threat_breakdown": breakdown,
        "showdown_paste": pokemon_build_to_showdown(optimized_pokemon),
    }
    survived = sum(row["survives"] for row in breakdown)
    parts = [f"survives {survived}/{len(breakdown)} hits"]
    if speed_info is not None:
        parts.append(sc.speed_part(outspeed_pokemon or "", bool(speed_info.get("outspeeds"))))
    return sc.contract(payload, optimized_pokemon, parts, sc.attackers(threat_builds),
                       [spec["meta"] for spec in prepared])


async def _check_spread_efficiency_champions(
    pokeapi: PokeAPIClient,
    pokemon_name: str,
    base_stats: BaseStats,
    parsed_nature: Nature,
    nature: str,
    hp_sps: int,
    atk_sps: int,
    def_sps: int,
    spa_sps: int,
    spd_sps: int,
    spe_sps: int,
) -> dict[str, Any]:
    """SP-scale version of check_spread_efficiency (cap 32/stat, 66 total)."""
    allocation = {
        "hp": hp_sps,
        "attack": atk_sps,
        "defense": def_sps,
        "special_attack": spa_sps,
        "special_defense": spd_sps,
        "speed": spe_sps,
    }
    validation = validate_sp_allocation(allocation)
    total = validation["total"]

    issues: list[str] = list(validation["per_stat_violations"])
    suggestions: list[str] = []
    if validation["over_budget"]:
        issues.append(
            f"Total SP ({total}) exceeds maximum of {SP_TOTAL_MAX}"
        )
    elif total < SP_TOTAL_MAX:
        suggestions.append(
            f"You have {SP_TOTAL_MAX - total} Stat Points remaining to allocate"
        )

    nature_mods = {
        "attack": get_nature_modifier(parsed_nature, "attack"),
        "special_attack": get_nature_modifier(parsed_nature, "special_attack"),
    }
    if nature_mods["attack"] < 1.0 and atk_sps > 0:
        suggestions.append(
            f"Investing in Attack with -{nature} nature. Consider a neutral or +Atk nature."
        )
    if nature_mods["special_attack"] < 1.0 and spa_sps > 0:
        suggestions.append(
            f"Investing in Sp.Atk with -{nature} nature. Consider a neutral or +SpA nature."
        )

    final_stats = {
        "hp": calculate_hp_sp(base_stats.hp, 31, hp_sps, 50),
        "attack": calculate_stat_sp(base_stats.attack, 31, atk_sps, 50, get_nature_modifier(parsed_nature, "attack")),
        "defense": calculate_stat_sp(base_stats.defense, 31, def_sps, 50, get_nature_modifier(parsed_nature, "defense")),
        "special_attack": calculate_stat_sp(base_stats.special_attack, 31, spa_sps, 50, get_nature_modifier(parsed_nature, "special_attack")),
        "special_defense": calculate_stat_sp(base_stats.special_defense, 31, spd_sps, 50, get_nature_modifier(parsed_nature, "special_defense")),
        "speed": calculate_stat_sp(base_stats.speed, 31, spe_sps, 50, get_nature_modifier(parsed_nature, "speed")),
    }

    # Only emit a paste when the allocation is within caps — StatPointSpread
    # rejects out-of-range values, so an invalid spread is reported via the
    # issues list rather than a paste.
    showdown_paste = None
    if validation["is_valid"]:
        types = await pokeapi.get_pokemon_types(pokemon_name)
        sps = StatPointSpread(**allocation)
        analyzed_pokemon = _build_champions_pokemon(
            pokemon_name, base_stats, types, parsed_nature, sps
        )
        showdown_paste = pokemon_build_to_showdown(analyzed_pokemon)

    return {
        "pokemon": pokemon_name,
        "nature": nature,
        "format_system": "champions",
        "total_sps": total,
        "remaining_sps": validation["remaining"],
        "is_complete": validation["is_complete"],
        "final_stats": final_stats,
        "issues": issues if issues else ["No issues found"],
        "suggestions": suggestions if suggestions else ["Spread looks efficient!"],
        "is_valid": validation["is_valid"],
        "showdown_paste": showdown_paste,
        "analysis": (
            f"{pokemon_name}'s spread uses {total}/{SP_TOTAL_MAX} SP — "
            f"{validation['remaining']} remaining"
        ),
    }
