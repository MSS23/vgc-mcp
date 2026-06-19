"""Breakpoint finder — cheapest spread change to clear a benchmark.

Top players spend hours asking "what's the minimum I need to invest to
guarantee this KO / outspeed this Pokémon / live this attack?" The
existing find_ko_evs / find_survival_evs tools answer one direction at
a time; this one searches the full (nature × EVs) space and returns
the *Pareto-optimal* options:

  - cheapest neutral-nature option
  - cheapest +nature option (faster) and what it costs elsewhere
  - "best bang for buck" option

The benchmark types supported:
  - "ko" — guarantee KO on a target
  - "outspeed" — outspeed a target's stat
  - "survive" — survive a target's attack at a chosen survival %
"""

from __future__ import annotations

import asyncio
from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_speed, calculate_stat
from vgc_mcp_core.calc.stats_champions import (
    SP_BREAKPOINTS_LV50,
    calculate_speed_sp,
)
from vgc_mcp_core.calc.champions_optimization import (
    SP_PER_STAT_MAX,
    SP_TOTAL_MAX,
    find_speed_sps_to_outspeed,
)
from vgc_mcp_core.models.pokemon import (
    BaseStats, EVSpread, IVSpread, Nature, PokemonBuild, StatPointSpread,
    get_nature_modifier,
)
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.utils.errors import error_response, ErrorCodes
from vgc_mcp_core.tools import get_common_spread
from vgc_mcp_core.tools.ability_helpers import (
    resolve_ability,
    compute_intimidate_attack_stage,
)


def _session_is_champions(pokemon_name: Optional[str] = None) -> bool:
    """Return True when the active session is the Champions (Reg MA) SP system.

    Mirrors spread_tools._session_is_champions: optionally runs Pokemon-name
    inference first so a Mega/Reg MA mention auto-selects Champions without the
    user having to set it explicitly. The mainline path is taken when False.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(pokemon_name)


# Natures that boost / nerf each stat
_PLUS_NATURES = {
    "attack": "adamant", "defense": "impish", "speed": "jolly",
    "special_attack": "modest", "special_defense": "careful",
}
_MINUS_NATURES = {  # neutralizes the offset stat without touching the boosted one
    "attack": "calm",     # +SpD -Atk
    "special_attack": "adamant",  # +Atk -SpA (often used on physical attackers to free SpA)
}


def register_breakpoint_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient] = None,
):

    @mcp.tool()
    async def find_breakpoint(
        pokemon_name: str,
        benchmark_type: str,
        target_pokemon: str,
        target_move: Optional[str] = None,
        target_stat: Optional[str] = None,
        survival_chance: float = 93.75,
        target_spread_overrides: Optional[dict] = None,
    ) -> dict:
        """Find the cheapest spread change to hit a specific benchmark.

        Args:
            pokemon_name: Your Pokémon (e.g. "flutter-mane")
            benchmark_type: "ko" | "outspeed" | "survive"
            target_pokemon: The opponent
            target_move: For "ko" — your move. For "survive" — opponent's move.
                         Ignored for "outspeed".
            target_stat: For "outspeed" — defaults to "speed" but can be any stat
                         if you want to outpace something else (rare).
            survival_chance: For "survive" — 93.75 (default), 87.5, 75, 100, etc.
            target_spread_overrides: Override the opponent's auto-fetched spread
                                     ({"nature":"adamant", "evs":{...}, "item":"...",
                                      "ability":"..."}). The ability key wins over
                                     Smogon — pass it explicitly to test alt abilities
                                     like Multiscale vs Inner Focus on Dragonite.

        Ability awareness: BOTH sides have abilities resolved automatically
        (mega-form > Smogon > pokeapi). All offensive abilities (Sheer Force,
        Tough Claws, Adaptability, Intrepid Sword, Embody Aspect, Booster
        Energy + Paradox) and defensive ones (Multiscale, Ice Scales, Thick
        Fat, Filter, Levitate) auto-apply. Defender Intimidate auto-drops the
        attacker's Atk for physical moves, with Defiant/Contrary punishment
        and Clear Body / Inner Focus blocking handled correctly.

        Returns 3 Pareto-optimal options:
            1. CHEAPEST: minimum total EVs investment, neutral nature
            2. FASTEST: optimal + nature (boosts the relevant stat — good if you
               also need speed)
            3. BALANCED: rounds the EV usage to the nearest 4 EVs, leaves leftover
               EVs available for other benchmarks

        Each option includes: nature, EV breakdown, Showdown paste, and the
        resulting numeric stat / damage / survival.
        """
        if benchmark_type not in {"ko", "outspeed", "survive"}:
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                f"benchmark_type must be 'ko', 'outspeed', or 'survive' (got '{benchmark_type}')",
            )

        try:
            me_base = await pokeapi.get_base_stats(pokemon_name)
            me_types = await pokeapi.get_pokemon_types(pokemon_name)
            tgt_base = await pokeapi.get_base_stats(target_pokemon)
            tgt_types = await pokeapi.get_pokemon_types(target_pokemon)
        except Exception as e:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, str(e))

        # Resolve target spread (Smogon-fetched, then user overrides)
        tgt_spread = await get_common_spread(smogon, target_pokemon) or {}
        if target_spread_overrides:
            tgt_spread = {**tgt_spread, **target_spread_overrides}
            if "evs" in target_spread_overrides:
                tgt_spread["evs"] = {**(tgt_spread.get("evs") or {}),
                                     **target_spread_overrides["evs"]}

        # Resolve abilities (mega > Smogon > pokeapi) so offensive abilities
        # like Sheer Force, Tough Claws, Adaptability AND defensive ones like
        # Multiscale, Ice Scales, Thick Fat all flow through the calc.
        me_ability, _ = await resolve_ability(
            pokemon_name, pokeapi=pokeapi, smogon_client=smogon,
        )
        tgt_ability_override = tgt_spread.get("ability") if tgt_spread else None
        tgt_ability, _ = await resolve_ability(
            target_pokemon, pokeapi=pokeapi, smogon_client=smogon,
            user_override=tgt_ability_override,
        )
        if tgt_spread is not None and tgt_ability and not tgt_spread.get("ability"):
            tgt_spread["ability"] = tgt_ability

        # Only the USER's subject Pokemon becomes a Champions (SP) build; the
        # opposing target stays mainline (it's an opposing meta reference).
        is_champions = _session_is_champions(pokemon_name)

        if benchmark_type == "outspeed":
            return _find_speed_breakpoint(me_base, tgt_base, tgt_spread,
                                          pokemon_name, target_pokemon,
                                          target_stat or "speed",
                                          is_champions=is_champions)
        if benchmark_type == "ko":
            return await _find_ko_breakpoint(
                pokeapi, me_base, me_types, tgt_base, tgt_types, tgt_spread,
                pokemon_name, target_pokemon, target_move,
                me_ability=me_ability, is_champions=is_champions,
            )
        return await _find_survival_breakpoint(
            pokeapi, me_base, me_types, tgt_base, tgt_types, tgt_spread,
            pokemon_name, target_pokemon, target_move, survival_chance,
            me_ability=me_ability, is_champions=is_champions,
        )


def _find_speed_breakpoint(me_base, tgt_base, tgt_spread, me_name, tgt_name, stat,
                           is_champions=False):
    """Find min EVs (or SP, for Champions) to outspeed a target's stat."""
    tgt_evs = (tgt_spread.get("evs") or {}).get(stat, 0)
    tgt_nature_str = tgt_spread.get("nature", "serious").lower()
    try:
        tgt_nature = Nature(tgt_nature_str)
    except ValueError:
        tgt_nature = Nature.SERIOUS
    tgt_speed = calculate_speed(getattr(tgt_base, stat),
                                ev=tgt_evs, iv=31, nature=tgt_nature)
    target_min = tgt_speed + 1

    if is_champions:
        return _find_speed_breakpoint_champions(
            me_base, tgt_speed, target_min, me_name, tgt_name, stat,
        )

    options = []
    me_base_stat = getattr(me_base, stat)

    def _calc(ev: int, nat: Nature) -> int:
        return calculate_speed(me_base_stat, ev=ev, iv=31, nature=nat)

    # Option 1: cheapest neutral
    cheapest_evs = _min_evs_to_reach(me_base_stat, target_min, nature_mod=1.0)
    if cheapest_evs is not None:
        options.append({
            "label": "cheapest (neutral nature)",
            "nature": "serious",
            "evs": {stat: cheapest_evs},
            "result_stat": _calc(cheapest_evs, Nature.SERIOUS),
            "ev_cost": cheapest_evs,
        })

    # Option 2: +nature (Jolly for speed)
    plus_nat = _PLUS_NATURES.get(stat)
    if plus_nat:
        plus_evs = _min_evs_to_reach(me_base_stat, target_min, nature_mod=1.1)
        if plus_evs is not None:
            try:
                plus_nature_enum = Nature(plus_nat)
            except ValueError:
                plus_nature_enum = Nature.SERIOUS
            options.append({
                "label": f"+nature ({plus_nat})",
                "nature": plus_nat,
                "evs": {stat: plus_evs},
                "result_stat": _calc(plus_evs, plus_nature_enum),
                "ev_cost": plus_evs,
                "tradeoff": (
                    f"costs {plus_evs} {stat} EVs but {plus_nat} nature reduces "
                    "the *other* stat 10% — pick this if you can afford the loss."
                ),
            })

    if not options:
        return error_response(
            ErrorCodes.INVALID_PARAMETER,
            f"Cannot outspeed {tgt_name} — its {stat} ({tgt_speed}) is unreachable "
            f"by {me_name} even at max investment. Use Tailwind / Choice Scarf / "
            "Trick Room instead.",
            target_stat=tgt_speed,
        )

    return {
        "success": True,
        "benchmark": f"outspeed {tgt_name} (stat: {stat})",
        "target_stat_value": tgt_speed,
        "options": options,
        "agent_instruction": (
            "Render `options` as a table: Label | Nature | EVs | Resulting stat. "
            "Highlight the cheapest option. Mention the tradeoff for the +nature row."
        ),
    }


def _sp_paste_for(me_name, me_base, nature_str, sp_dict):
    """Build a Champions PokemonBuild + 'SPs:' paste from a stat->SP dict."""
    try:
        nat = Nature((nature_str or "serious").lower())
    except ValueError:
        nat = Nature.SERIOUS
    build = PokemonBuild(
        name=me_name, base_stats=me_base, nature=nat,
        format_system="champions",
        sps=StatPointSpread(**sp_dict),
    )
    return pokemon_build_to_showdown(build)


def _find_speed_breakpoint_champions(me_base, tgt_speed, target_min,
                                     me_name, tgt_name, stat):
    """SP-scale speed breakpoint (0-32 per stat, <=66 total)."""
    me_base_stat = getattr(me_base, stat)
    options = []

    # Option 1: cheapest neutral nature
    neutral_sp = find_speed_sps_to_outspeed(me_base_stat, tgt_speed, Nature.SERIOUS)
    if neutral_sp is not None:
        sp_dict = {stat: neutral_sp}
        options.append({
            "label": "cheapest (neutral nature)",
            "nature": "serious",
            "sps": sp_dict,
            "result_stat": calculate_speed_sp(me_base_stat, 31, neutral_sp,
                                              nature=Nature.SERIOUS),
            "sp_cost": neutral_sp,
            "showdown_paste": _sp_paste_for(me_name, me_base, "serious", sp_dict),
        })

    # Option 2: +nature (boosts the relevant stat — Jolly for speed)
    plus_nat = _PLUS_NATURES.get(stat)
    if plus_nat:
        try:
            plus_nature_enum = Nature(plus_nat)
        except ValueError:
            plus_nature_enum = Nature.SERIOUS
        plus_sp = find_speed_sps_to_outspeed(me_base_stat, tgt_speed, plus_nature_enum)
        if plus_sp is not None:
            sp_dict = {stat: plus_sp}
            options.append({
                "label": f"+nature ({plus_nat})",
                "nature": plus_nat,
                "sps": sp_dict,
                "result_stat": calculate_speed_sp(me_base_stat, 31, plus_sp,
                                                 nature=plus_nature_enum),
                "sp_cost": plus_sp,
                "showdown_paste": _sp_paste_for(me_name, me_base, plus_nat, sp_dict),
                "tradeoff": (
                    f"costs {plus_sp} {stat} SP but {plus_nat} nature reduces "
                    "the *other* stat 10% — pick this if you can afford the loss."
                ),
            })

    if not options:
        return error_response(
            ErrorCodes.INVALID_PARAMETER,
            f"Cannot outspeed {tgt_name} — its {stat} ({tgt_speed}) is unreachable "
            f"by {me_name} even at 32 SP. Use Tailwind / Trick Room instead.",
            target_stat=tgt_speed,
        )

    return {
        "success": True,
        "format_system": "champions",
        "benchmark": f"outspeed {tgt_name} (stat: {stat})",
        "target_stat_value": tgt_speed,
        "options": options,
        "agent_instruction": (
            "Champions (Reg MA) SP units. Render `options` as a table: "
            "Label | Nature | SP | Resulting stat. Highlight the cheapest option. "
            "Show the showdown_paste (an 'SPs:' paste) for it in a code block. "
            "Mention the tradeoff for the +nature row."
        ),
    }


def _min_evs_to_reach(base: int, target: int, nature_mod: float, level: int = 50) -> Optional[int]:
    """Binary search for the minimum EVs needed to reach `target`."""
    for ev in range(0, 256, 4):
        stat = int((((2 * base + 31 + ev // 4) * level) // 100 + 5) * nature_mod)
        if stat >= target:
            return ev
    return None


async def _find_ko_breakpoint(pokeapi, me_base, me_types, tgt_base, tgt_types, tgt_spread,
                              me_name, tgt_name, move_name, me_ability=None,
                              is_champions=False):
    """Find min Atk/SpA EVs (or SP, for Champions) to guarantee KO with `move_name`."""
    if not move_name:
        return error_response(ErrorCodes.INVALID_PARAMETER,
                              "target_move required for benchmark_type='ko'")
    move = await pokeapi.get_move(move_name, user_name=me_name)
    is_physical = move.category.value == "physical"
    offensive_stat = "attack" if is_physical else "special_attack"
    plus_nature = _PLUS_NATURES[offensive_stat]

    tgt_build = _build_from_spread(tgt_base, tgt_types, tgt_name, tgt_spread)

    # Defender Intimidate event: if target has Intimidate and we're using a
    # physical move, drop our Atk by -1 (accounting for blockers/punishers).
    intim_stage, _ = compute_intimidate_attack_stage(
        defender_ability=tgt_build.ability,
        attacker_ability=me_ability,
        is_physical=is_physical,
    )

    options = []
    for label, nature, mod in [
        ("cheapest (neutral)", "serious", 1.0),
        (f"+nature ({plus_nature})", plus_nature, 1.1),
    ]:
        cost = _min_invest_for_ko(
            me_base, me_types, me_name, offensive_stat,
            mod, move, tgt_build,
            me_ability=me_ability, intim_stage=intim_stage if is_physical else 0,
            is_champions=is_champions,
        )
        if cost is None:
            options.append({"label": label, "nature": nature, "achievable": False})
            continue
        if is_champions:
            sp_dict = {offensive_stat: cost}
            me_build = _build_champions_subject(
                me_base, me_types, me_name, nature, sp_dict, ability=me_ability,
            )
            options.append({
                "label": label,
                "nature": nature,
                "sps": sp_dict,
                "sp_cost": cost,
                "achievable": True,
                "showdown_paste": pokemon_build_to_showdown(me_build),
            })
        else:
            # Build resulting Pokémon for paste
            ev_dict = {offensive_stat: cost}
            me_build = _build_from_spread(me_base, me_types, me_name,
                                          {"nature": nature, "evs": ev_dict, "ability": me_ability})
            options.append({
                "label": label,
                "nature": nature,
                "evs": ev_dict,
                "ev_cost": cost,
                "achievable": True,
                "showdown_paste": pokemon_build_to_showdown(me_build),
            })

    unit = "SP" if is_champions else "EVs"
    result_dict = {
        "success": True,
        "benchmark": f"guarantee KO on {tgt_name} with {move_name}",
        "attacker_ability": (me_ability.replace("-", " ").title() if me_ability else None),
        "defender_ability": (tgt_build.ability.replace("-", " ").title() if tgt_build.ability else None),
        "intimidate_applied": intim_stage != 0,
        "options": options,
        "agent_instruction": (
            f"Render `options` as a Label | Nature | {unit} | Cost table. "
            "Show the showdown_paste for the cheapest achievable option as a code block. "
            "If neither option is achievable, say so plainly and suggest item "
            "or Tera as alternatives. Mention the resolved attacker/defender abilities "
            "if they materially shift the calc (Multiscale, Sheer Force, Intimidate, etc.)."
        ),
    }
    if is_champions:
        result_dict["format_system"] = "champions"
    return result_dict


def _build_champions_subject(me_base, me_types, me_name, nature, sp_dict,
                             ability=None, item=None):
    """Construct a Champions (SP) PokemonBuild for the user's subject Pokemon."""
    try:
        nat = Nature((nature or "serious").lower()) if isinstance(nature, str) else nature
    except ValueError:
        nat = Nature.SERIOUS
    return PokemonBuild(
        name=me_name, base_stats=me_base, types=me_types,
        nature=nat, format_system="champions",
        sps=StatPointSpread(**sp_dict), ivs=IVSpread(),
        ability=ability, item=item,
    )


def _min_invest_for_ko(me_base, me_types, me_name, off_stat, nat_mod, move, tgt_build,
                       me_ability=None, intim_stage: int = 0,
                       is_champions=False) -> Optional[int]:
    nature = Nature.SERIOUS
    if nat_mod > 1.0:
        if off_stat == "attack":
            nature = Nature.ADAMANT
        else:
            nature = Nature.MODEST

    is_physical = off_stat == "attack"

    if is_champions:
        for sp in SP_BREAKPOINTS_LV50:
            me_build = _build_champions_subject(
                me_base, me_types, me_name, nature, {off_stat: sp},
                ability=me_ability,
            )
            result = calculate_damage(
                me_build, tgt_build, move,
                DamageModifiers(
                    is_doubles=True,
                    attacker_ability=me_ability,
                    attack_stage=intim_stage if is_physical else 0,
                ),
            )
            if result.is_guaranteed_ohko:
                return sp
        return None

    for ev in range(0, 256, 4):
        evs = EVSpread(**{off_stat: ev})
        me_build = PokemonBuild(
            name=me_name, base_stats=me_base, types=me_types,
            nature=nature, evs=evs, ivs=IVSpread(),
            ability=me_ability,
        )
        result = calculate_damage(
            me_build, tgt_build, move,
            DamageModifiers(
                is_doubles=True,
                attacker_ability=me_ability,
                attack_stage=intim_stage if is_physical else 0,
            ),
        )
        if result.is_guaranteed_ohko:
            return ev
    return None


async def _find_survival_breakpoint(pokeapi, me_base, me_types, tgt_base, tgt_types, tgt_spread,
                                    me_name, tgt_name, move_name, survival_chance,
                                    me_ability=None, is_champions=False):
    """Find min HP/Def or HP/SpD EVs (or SP, for Champions) to survive at survival_chance."""
    if not move_name:
        return error_response(ErrorCodes.INVALID_PARAMETER,
                              "target_move required for benchmark_type='survive'")
    move = await pokeapi.get_move(move_name, user_name=tgt_name)
    is_physical = move.category.value == "physical"
    def_stat = "defense" if is_physical else "special_defense"
    plus_nature = _PLUS_NATURES[def_stat]

    tgt_build = _build_from_spread(tgt_base, tgt_types, tgt_name, tgt_spread)

    # Our (defender) Intimidate vs the target's (attacker) ability — drop their
    # Atk for physical moves only.
    intim_stage, _ = compute_intimidate_attack_stage(
        defender_ability=me_ability,
        attacker_ability=tgt_build.ability,
        is_physical=is_physical,
    )

    # We sweep (HP, Def/SpD) jointly to minimize total investment.
    options: list[dict] = []
    for label, nature, nat_mod in [
        ("cheapest (neutral)", "serious", 1.0),
        (f"+nature ({plus_nature})", plus_nature, 1.1),
    ]:
        best = _min_total_invest_for_survival(
            me_base, me_types, me_name, def_stat,
            nat_mod, move, tgt_build, survival_chance,
            me_ability=me_ability,
            intim_stage=intim_stage if is_physical else 0,
            is_champions=is_champions,
        )
        if best is None:
            options.append({"label": label, "nature": nature, "achievable": False})
            continue
        hp_inv, def_inv = best
        if is_champions:
            sp_dict = {"hp": hp_inv, def_stat: def_inv}
            me_build = _build_champions_subject(
                me_base, me_types, me_name, nature, sp_dict, ability=me_ability,
            )
            options.append({
                "label": label,
                "nature": nature,
                "sps": sp_dict,
                "sp_cost": hp_inv + def_inv,
                "achievable": True,
                "showdown_paste": pokemon_build_to_showdown(me_build),
            })
        else:
            ev_dict = {"hp": hp_inv, def_stat: def_inv}
            me_build = _build_from_spread(me_base, me_types, me_name,
                                          {"nature": nature, "evs": ev_dict, "ability": me_ability})
            options.append({
                "label": label,
                "nature": nature,
                "evs": ev_dict,
                "ev_cost": hp_inv + def_inv,
                "achievable": True,
                "showdown_paste": pokemon_build_to_showdown(me_build),
            })

    result_dict = {
        "success": True,
        "benchmark": (f"survive {tgt_name}'s {move_name} at "
                      f"{survival_chance}%"),
        "attacker_ability": (tgt_build.ability.replace("-", " ").title() if tgt_build.ability else None),
        "defender_ability": (me_ability.replace("-", " ").title() if me_ability else None),
        "intimidate_applied": intim_stage != 0,
        "options": options,
        "agent_instruction": (
            "Render options as a table. Show the cheapest achievable spread's "
            "showdown_paste in a code block. If unachievable, say so and suggest "
            "Tera-typing into a resist or running a defensive item (Sitrus, AV). "
            "Mention resolved attacker/defender abilities if they materially shift "
            "the calc (Multiscale halves damage, Intimidate drops Atk, etc.)."
        ),
    }
    if is_champions:
        result_dict["format_system"] = "champions"
    return result_dict


def _build_from_spread(base, types, name, spread):
    evs = spread.get("evs") or {}
    return PokemonBuild(
        name=name, base_stats=base, types=types,
        nature=Nature((spread.get("nature") or "serious").lower()),
        evs=EVSpread(
            hp=evs.get("hp", 0),
            attack=evs.get("attack", 0),
            defense=evs.get("defense", 0),
            special_attack=evs.get("special_attack", 0),
            special_defense=evs.get("special_defense", 0),
            speed=evs.get("speed", 0),
        ),
        ivs=IVSpread(),
        item=spread.get("item"),
        ability=spread.get("ability"),
    )


def _min_total_invest_for_survival(me_base, me_types, me_name, def_stat,
                                   nat_mod, move, tgt_build, survival_chance,
                                   me_ability=None, intim_stage: int = 0,
                                   is_champions=False) -> Optional[tuple[int, int]]:
    nature = Nature.SERIOUS
    if nat_mod > 1.0:
        nature = Nature((_PLUS_NATURES[def_stat]).upper().lower())

    is_physical = def_stat == "defense"
    threshold_rolls = round(survival_chance / 100 * 16)

    if is_champions:
        # Sweep (hp_sp, def_sp) on the SP grain (1), honouring 32/stat & 66/total.
        best: Optional[tuple[int, int]] = None
        best_total = 9999
        for hp_sp in SP_BREAKPOINTS_LV50:
            if hp_sp >= best_total:
                break
            for def_sp in SP_BREAKPOINTS_LV50:
                total = hp_sp + def_sp
                if total >= best_total or total > SP_TOTAL_MAX:
                    break
                me_build = _build_champions_subject(
                    me_base, me_types, me_name, nature,
                    {"hp": hp_sp, def_stat: def_sp}, ability=me_ability,
                )
                result = calculate_damage(
                    tgt_build, me_build, move,
                    DamageModifiers(is_doubles=True,
                                    attacker_item=tgt_build.item,
                                    attacker_ability=tgt_build.ability,
                                    defender_ability=me_ability,
                                    attack_stage=intim_stage if is_physical else 0),
                )
                survived = sum(1 for r in result.rolls if r < result.defender_hp)
                if survived >= threshold_rolls:
                    best = (hp_sp, def_sp)
                    best_total = total
                    break
        return best

    best = None
    best_total = 9999
    # Sweep coarse grid first (steps of 4 EVs to respect the breakpoint quantum)
    for hp_ev in range(0, 256, 4):
        for def_ev in range(0, 256, 4):
            if hp_ev + def_ev >= best_total:
                continue
            evs = EVSpread(hp=hp_ev, **{def_stat: def_ev})
            me_build = PokemonBuild(
                name=me_name, base_stats=me_base, types=me_types,
                nature=nature, evs=evs, ivs=IVSpread(),
                ability=me_ability,
            )
            result = calculate_damage(
                tgt_build, me_build, move,
                DamageModifiers(is_doubles=True,
                                attacker_item=tgt_build.item,
                                attacker_ability=tgt_build.ability,
                                defender_ability=me_ability,
                                attack_stage=intim_stage if is_physical else 0),
            )
            # Count rolls that don't KO
            survived = sum(1 for r in result.rolls if r < result.defender_hp)
            if survived >= threshold_rolls:
                best = (hp_ev, def_ev)
                best_total = hp_ev + def_ev
                # Found a winner at this hp_ev — increasing def_ev only worsens cost
                break
    return best
