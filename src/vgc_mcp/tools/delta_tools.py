"""Spread / item / Tera deltas — the iteration loop.

When a user changes ONE thing about a build (item, nature, Tera, EV
allocation), they want to know what flipped: which KOs they gained,
which they lost, which survival benchmarks broke.

This tool produces that diff against a list of threats.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import calculate_damage
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import (
    BaseStats, EVSpread, IVSpread, Nature, PokemonBuild,
)
from vgc_mcp_core.utils.errors import error_response, ErrorCodes
from vgc_mcp_core.utils.normalize import normalize_move
from vgc_mcp_core.tools import get_common_spread


def _verdict(min_pct: float, max_pct: float) -> str:
    if min_pct >= 100:
        return "OHKO"
    if max_pct >= 100:
        prob = (max_pct - 100) / max(0.001, max_pct - min_pct) * 100
        return f"{round(prob, 0):.0f}% OHKO"
    if min_pct + max_pct >= 100:
        return "2HKO"
    if min_pct + max_pct >= 67:
        return "3HKO"
    if max_pct < 30:
        return "Resists"
    return "4HKO+"


def _mods_for(spread: dict, item_field: str, ability_field: str) -> DamageModifiers:
    return DamageModifiers(
        is_doubles=True,
        attacker_item=spread.get(item_field),
        attacker_ability=spread.get(ability_field),
    )


async def _build_from_overrides(
    pokeapi: PokeAPIClient,
    name: str,
    *,
    nature: Optional[str] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    tera_type: Optional[str] = None,
    evs: Optional[dict] = None,
) -> PokemonBuild:
    base = await pokeapi.get_base_stats(name)
    types = await pokeapi.get_pokemon_types(name)
    ev_obj = EVSpread()
    if evs:
        ev_obj = EVSpread(
            hp=evs.get("hp", 0),
            attack=evs.get("attack", 0),
            defense=evs.get("defense", 0),
            special_attack=evs.get("special_attack", 0),
            special_defense=evs.get("special_defense", 0),
            speed=evs.get("speed", 0),
        )
    return PokemonBuild(
        name=name,
        base_stats=base,
        types=types,
        nature=Nature(nature.lower()) if nature else Nature.SERIOUS,
        evs=ev_obj,
        ivs=IVSpread(),
        item=item,
        ability=ability,
        tera_type=tera_type,
    )


def register_delta_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    smogon: Optional[SmogonStatsClient] = None,
):
    @mcp.tool()
    async def compare_build_changes(
        pokemon_name: str,
        before: dict,
        after: dict,
        threats: list[str],
        threat_moves: Optional[dict[str, str]] = None,
        as_attacker: bool = True,
    ) -> dict:
        """Show what changed between two builds against a fixed threat list.

        Use this whenever a user iterates ONE thing on a Pokémon (changed
        item, nature, Tera type, or moved EVs around) and wants to know
        what flipped. Avoids the user re-running 10 separate damage calcs.

        Args:
            pokemon_name: The Pokémon being iterated (e.g. "flutter-mane").
            before / after: dicts with any of:
                {"nature": "...", "item": "...", "ability": "...",
                 "tera_type": "...", "evs": {"hp":4,"special_attack":252,...}}
                Both dicts default to the "most common Smogon spread" for any
                unspecified field — only override what you're testing.
            threats: list of threat Pokémon names (the opponents).
            threat_moves: optional {"incineroar": "flare-blitz"} override of
                each threat's move; defaults to the threat's most common move.
            as_attacker: True = "what KOs do I gain/lose against threats?"
                         False = "which threats do I survive better/worse against?"

        Returns a delta table per threat: before result vs after result,
        with a one-word change label (gained-OHKO, lost-OHKO, no-change, etc.).
        """
        if not threats:
            return error_response(ErrorCodes.INVALID_PARAMETER, "Provide at least one threat")
        if len(threats) > 20:
            return error_response(ErrorCodes.INVALID_PARAMETER, "Maximum 20 threats per delta")

        try:
            me_before = await _build_from_overrides(
                pokeapi, pokemon_name,
                nature=before.get("nature"),
                item=before.get("item"),
                ability=before.get("ability"),
                tera_type=before.get("tera_type"),
                evs=before.get("evs"),
            )
            me_after = await _build_from_overrides(
                pokeapi, pokemon_name,
                nature=after.get("nature"),
                item=after.get("item"),
                ability=after.get("ability"),
                tera_type=after.get("tera_type"),
                evs=after.get("evs"),
            )
        except Exception as e:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, str(e))

        threat_moves = threat_moves or {}

        # Resolve each threat's spread + chosen move in parallel
        async def _resolve_threat(t_name: str) -> dict:
            try:
                spread = await get_common_spread(smogon, t_name) or {}
                t_build = await _build_from_overrides(
                    pokeapi, t_name,
                    nature=spread.get("nature"),
                    item=spread.get("item"),
                    ability=spread.get("ability"),
                    evs=spread.get("evs"),
                )
                # Chosen move: explicit > Smogon top move > first STAB
                mv = threat_moves.get(t_name)
                if mv is None:
                    usage_moves = []
                    if smogon:
                        try:
                            u = await smogon.get_pokemon_usage(t_name)
                            usage_moves = list((u or {}).get("moves", {}).keys())
                        except Exception:
                            pass
                    mv = usage_moves[0] if usage_moves else "tackle"
                # Smogon usage returns concatenated names ("surgingstrikes"); PokeAPI
                # wants hyphenated. Run through the canonical normalizer.
                mv = normalize_move(mv)
                move = await pokeapi.get_move(mv, user_name=t_name)
                return {"name": t_name, "build": t_build, "move": move,
                        "spread": spread, "ok": True}
            except Exception as e:
                return {"name": t_name, "ok": False, "error": str(e)}

        threat_data = await asyncio.gather(*[_resolve_threat(t) for t in threats])

        # Compute matchups
        rows = []
        gained, lost, unchanged = 0, 0, 0
        for td in threat_data:
            if not td["ok"]:
                rows.append({"threat": td["name"], "error": td["error"]})
                continue

            # In as_attacker mode, ME attacks the threat with ME's first STAB.
            # In as_defender mode, the THREAT attacks ME with its move.
            if as_attacker:
                # We need a representative attacking move from "me"
                me_move = await pokeapi.get_move(_first_stab_move(me_before),
                                                  user_name=pokemon_name)
                r_b = calculate_damage(me_before, td["build"], me_move,
                                       DamageModifiers(is_doubles=True,
                                                       attacker_item=me_before.item,
                                                       attacker_ability=me_before.ability))
                r_a = calculate_damage(me_after, td["build"], me_move,
                                       DamageModifiers(is_doubles=True,
                                                       attacker_item=me_after.item,
                                                       attacker_ability=me_after.ability))
            else:
                # Defender Intimidate event (per "before" / "after" defender state),
                # honouring attacker blockers/punishers.
                from vgc_mcp_core.tools.ability_helpers import compute_intimidate_attack_stage
                is_phys = td["move"].category.value == "physical"
                intim_b, _ = compute_intimidate_attack_stage(
                    defender_ability=me_before.ability,
                    attacker_ability=td["build"].ability,
                    is_physical=is_phys,
                )
                intim_a, _ = compute_intimidate_attack_stage(
                    defender_ability=me_after.ability,
                    attacker_ability=td["build"].ability,
                    is_physical=is_phys,
                )
                r_b = calculate_damage(td["build"], me_before, td["move"],
                                       DamageModifiers(is_doubles=True,
                                                       attacker_item=td["build"].item,
                                                       attacker_ability=td["build"].ability,
                                                       defender_ability=me_before.ability,
                                                       attack_stage=intim_b if is_phys else 0))
                r_a = calculate_damage(td["build"], me_after, td["move"],
                                       DamageModifiers(is_doubles=True,
                                                       attacker_item=td["build"].item,
                                                       attacker_ability=td["build"].ability,
                                                       defender_ability=me_after.ability,
                                                       attack_stage=intim_a if is_phys else 0))

            v_b = _verdict(r_b.min_percent, r_b.max_percent)
            v_a = _verdict(r_a.min_percent, r_a.max_percent)
            label = _delta_label(v_b, v_a, r_b.min_percent, r_a.min_percent, as_attacker)

            if "gained" in label:
                gained += 1
            elif "lost" in label:
                lost += 1
            else:
                unchanged += 1

            rows.append({
                "threat": td["name"],
                "before": {"min_pct": r_b.min_percent, "max_pct": r_b.max_percent,
                           "verdict": v_b},
                "after": {"min_pct": r_a.min_percent, "max_pct": r_a.max_percent,
                          "verdict": v_a},
                "change": label,
            })

        return {
            "success": True,
            "pokemon": pokemon_name,
            "before": before,
            "after": after,
            "as_attacker": as_attacker,
            "summary": {"gained": gained, "lost": lost, "unchanged": unchanged},
            "deltas": rows,
            "agent_instruction": (
                "Render `deltas` as a 4-column table: Threat | Before | After | Change. "
                "Color/highlight the Change column (✅ gained, ❌ lost, ⚖ no-change). "
                "End with a 2-bullet 'Verdict' summarising what the change traded."
            ),
        }


def _first_stab_move(build: PokemonBuild) -> str:
    """Pick a representative offensive STAB for `as_attacker` mode."""
    type_to_move = {
        "Fire": "flamethrower", "Water": "scald", "Electric": "thunderbolt",
        "Grass": "energy-ball", "Ice": "ice-beam", "Fighting": "close-combat",
        "Poison": "sludge-bomb", "Ground": "earth-power", "Flying": "air-slash",
        "Psychic": "psychic", "Bug": "bug-buzz", "Rock": "stone-edge",
        "Ghost": "shadow-ball", "Dragon": "draco-meteor", "Dark": "dark-pulse",
        "Steel": "iron-head", "Fairy": "moonblast", "Normal": "tri-attack",
    }
    for t in build.types or []:
        if t in type_to_move:
            return type_to_move[t]
    return "tackle"


def _delta_label(v_before: str, v_after: str,
                 min_b: float, min_a: float,
                 as_attacker: bool) -> str:
    """Single-word change label suitable for table rendering."""
    if v_before == v_after:
        if abs(min_a - min_b) < 1.0:
            return "no-change"
        return "shifted (≈same verdict)"
    rank = {"OHKO": 0, "2HKO": 1, "3HKO": 2, "4HKO+": 3, "Resists": 4}
    rb = rank.get(v_before, 1)
    ra = rank.get(v_after, 1)
    # Probabilistic OHKO categories — treat as between OHKO and 2HKO
    if "OHKO" in v_before and v_before != "OHKO":
        rb = 0.5
    if "OHKO" in v_after and v_after != "OHKO":
        ra = 0.5
    if as_attacker:
        return "gained-pressure" if ra < rb else "lost-pressure"
    return "gained-bulk" if ra > rb else "lost-bulk"
