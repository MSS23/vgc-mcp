"""Core VGC tools - minimal set for rate-limited environments."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import calculate_damage, calculate_bulk_threshold
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp, calculate_speed
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats, get_nature_modifier
from vgc_mcp_core.models.move import MoveCategory
from vgc_mcp_core.utils.synergies import get_synergy_ability

# EV breakpoints at level 50
EV_BREAKPOINTS_LV50 = [0, 4, 12, 20, 28, 36, 44, 52, 60, 68, 76, 84, 92, 100, 108, 116, 124, 132, 140, 148, 156, 164, 172, 180, 188, 196, 204, 212, 220, 228, 236, 244, 252]

# Meta synergies for common Pokemon
META_SYNERGIES = {
    "chien-pao": ("focus-sash", "sword-of-ruin"),
    "chi-yu": ("choice-specs", "beads-of-ruin"),
    "flutter-mane": ("choice-specs", "protosynthesis"),
    "urshifu": ("choice-band", "unseen-fist"),
    "urshifu-single-strike": ("choice-band", "unseen-fist"),
    "urshifu-rapid-strike": ("choice-band", "unseen-fist"),
    "rillaboom": ("assault-vest", "grassy-surge"),
    "tornadus": ("covert-cloak", "prankster"),
    "landorus": ("life-orb", "sheer-force"),
    "landorus-incarnate": ("life-orb", "sheer-force"),
    "incineroar": ("safety-goggles", "intimidate"),
}

_smogon_client: Optional[SmogonStatsClient] = None


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Get most common Smogon spread for a Pokemon."""
    if _smogon_client is None:
        return None
    try:
        stats = await _smogon_client.get_pokemon_stats(pokemon_name)
        if stats and stats.spreads:
            top = stats.spreads[0]
            return {
                "nature": top.nature,
                "evs": top.evs,
                "usage": top.usage_percent,
                "item": stats.items[0].name if stats.items else None,
                "ability": stats.abilities[0].name if stats.abilities else None,
            }
    except Exception:
        pass
    return None


def register_core_tools(
    mcp: FastMCP,
    pokeapi: PokeAPIClient,
    smogon: SmogonStatsClient
):
    """Register the 5 core VGC tools."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def calculate_damage(
        attacker: str,
        defender: str,
        move: str,
        attacker_nature: Optional[str] = None,
        attacker_evs: Optional[int] = None,
        defender_nature: Optional[str] = None,
        defender_hp_evs: Optional[int] = None,
        defender_def_evs: Optional[int] = None,
        attacker_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        attacker_tera: Optional[str] = None,
        defender_tera: Optional[str] = None,
        is_spread: bool = False,
        weather: Optional[str] = None,
        sword_of_ruin: bool = False,
        beads_of_ruin: bool = False
    ) -> dict:
        """Calculate damage between two Pokemon. Auto-fetches Smogon spreads if not specified."""
        try:
            from vgc_mcp_core.calc.damage import calculate_damage as calc_dmg

            atk_base = await pokeapi.get_base_stats(attacker)
            def_base = await pokeapi.get_base_stats(defender)
            atk_types = await pokeapi.get_pokemon_types(attacker)
            def_types = await pokeapi.get_pokemon_types(defender)
            move_data = await pokeapi.get_move(move, user_name=attacker)
            is_physical = move_data.category == MoveCategory.PHYSICAL

            # Auto-fetch Smogon spreads
            if attacker_nature is None or attacker_evs is None:
                spread = await _get_common_spread(attacker)
                if spread:
                    attacker_nature = attacker_nature or spread["nature"]
                    evs = spread.get("evs", {})
                    attacker_evs = attacker_evs if attacker_evs is not None else evs.get("attack" if is_physical else "special_attack", 0)
                    attacker_item = attacker_item or spread.get("item")
                    attacker_ability = attacker_ability or spread.get("ability")

            if defender_nature is None or defender_hp_evs is None:
                spread = await _get_common_spread(defender)
                if spread:
                    defender_nature = defender_nature or spread["nature"]
                    evs = spread.get("evs", {})
                    defender_hp_evs = defender_hp_evs if defender_hp_evs is not None else evs.get("hp", 0)
                    defender_def_evs = defender_def_evs if defender_def_evs is not None else evs.get("defense" if is_physical else "special_defense", 0)

            # Defaults
            attacker_nature = attacker_nature or "serious"
            attacker_evs = attacker_evs if attacker_evs is not None else 0
            defender_nature = defender_nature or "serious"
            defender_hp_evs = defender_hp_evs if defender_hp_evs is not None else 0
            defender_def_evs = defender_def_evs if defender_def_evs is not None else 0

            # Auto-detect ruinous abilities
            if attacker_ability is None:
                abilities = await pokeapi.get_pokemon_abilities(attacker)
                if abilities:
                    attacker_ability = abilities[0].lower().replace(" ", "-")

            if attacker_ability:
                ab = attacker_ability.lower().replace(" ", "-")
                if ab == "sword-of-ruin":
                    sword_of_ruin = True
                elif ab == "beads-of-ruin":
                    beads_of_ruin = True

            atk_nature_enum = Nature(attacker_nature.lower())
            def_nature_enum = Nature(defender_nature.lower())

            attacker_build = PokemonBuild(
                name=attacker,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature_enum,
                evs=EVSpread(
                    attack=attacker_evs if is_physical else 0,
                    special_attack=0 if is_physical else attacker_evs
                ),
                item=attacker_item,
                tera_type=attacker_tera
            )

            defender_build = PokemonBuild(
                name=defender,
                base_stats=def_base,
                types=def_types,
                nature=def_nature_enum,
                evs=EVSpread(
                    hp=defender_hp_evs,
                    defense=defender_def_evs if is_physical else 0,
                    special_defense=0 if is_physical else defender_def_evs
                ),
                tera_type=defender_tera
            )

            modifiers = DamageModifiers(
                is_doubles=True,
                multiple_targets=is_spread,
                weather=weather,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability,
                tera_type=attacker_tera,
                tera_active=attacker_tera is not None,
                defender_tera_type=defender_tera,
                defender_tera_active=defender_tera is not None,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin
            )

            result = calc_dmg(attacker_build, defender_build, move_data, modifiers)

            return {
                "attacker": attacker,
                "defender": defender,
                "move": move,
                "damage_range": f"{result.min_damage}-{result.max_damage}",
                "damage_percent": f"{result.min_percent:.1f}-{result.max_percent:.1f}%",
                "ko_chance": result.ko_chance,
                "defender_hp": result.defender_hp,
                "analysis": f"{attacker}'s {move} vs {defender}: {result.min_percent:.1f}-{result.max_percent:.1f}%. {result.ko_chance}"
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_pokemon_data(pokemon: str) -> dict:
        """Get Smogon usage data for a Pokemon including common spreads, items, abilities, and teammates."""
        try:
            stats = await smogon.get_pokemon_stats(pokemon)
            if not stats:
                return {"error": f"No data found for {pokemon}"}

            return {
                "pokemon": pokemon,
                "usage_percent": stats.usage_percent,
                "top_spreads": [
                    {"nature": s.nature, "evs": s.evs, "usage": f"{s.usage_percent:.1f}%"}
                    for s in (stats.spreads or [])[:3]
                ],
                "top_items": [
                    {"item": i.name, "usage": f"{i.usage_percent:.1f}%"}
                    for i in (stats.items or [])[:5]
                ],
                "top_abilities": [
                    {"ability": a.name, "usage": f"{a.usage_percent:.1f}%"}
                    for a in (stats.abilities or [])[:3]
                ],
                "top_moves": [
                    {"move": m.name, "usage": f"{m.usage_percent:.1f}%"}
                    for m in (stats.moves or [])[:6]
                ],
                "top_teammates": [
                    {"pokemon": t.name, "usage": f"{t.usage_percent:.1f}%"}
                    for t in (stats.teammates or [])[:5]
                ]
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def compare_speed(
        pokemon1: str,
        pokemon2: str,
        pokemon1_nature: str = "jolly",
        pokemon1_evs: int = 252,
        pokemon2_nature: str = "timid",
        pokemon2_evs: int = 252
    ) -> dict:
        """Compare speed stats between two Pokemon."""
        try:
            base1 = await pokeapi.get_base_stats(pokemon1)
            base2 = await pokeapi.get_base_stats(pokemon2)

            nature1 = Nature(pokemon1_nature.lower())
            nature2 = Nature(pokemon2_nature.lower())

            mod1 = get_nature_modifier(nature1, "speed")
            mod2 = get_nature_modifier(nature2, "speed")

            speed1 = calculate_speed(base1.speed, 31, pokemon1_evs, 50, mod1)
            speed2 = calculate_speed(base2.speed, 31, pokemon2_evs, 50, mod2)

            if speed1 > speed2:
                result = f"{pokemon1} outspeeds {pokemon2}"
            elif speed2 > speed1:
                result = f"{pokemon2} outspeeds {pokemon1}"
            else:
                result = "Speed tie"

            return {
                "pokemon1": {"name": pokemon1, "speed": speed1, "nature": pokemon1_nature, "evs": pokemon1_evs},
                "pokemon2": {"name": pokemon2, "speed": speed2, "nature": pokemon2_nature, "evs": pokemon2_evs},
                "result": result,
                "difference": abs(speed1 - speed2)
            }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def find_survival_evs(
        pokemon: str,
        attacker: str,
        move: str,
        pokemon_nature: str = "bold",
        attacker_nature: Optional[str] = None,
        attacker_evs: Optional[int] = None,
        attacker_item: Optional[str] = None,
        target_survival: float = 93.75
    ) -> dict:
        """Find minimum HP/Def or HP/SpD EVs to survive an attack."""
        try:
            my_base = await pokeapi.get_base_stats(pokemon)
            my_types = await pokeapi.get_pokemon_types(pokemon)
            atk_base = await pokeapi.get_base_stats(attacker)
            atk_types = await pokeapi.get_pokemon_types(attacker)
            move_data = await pokeapi.get_move(move, user_name=attacker)
            is_physical = move_data.category == MoveCategory.PHYSICAL

            # Auto-fetch attacker spread
            if attacker_nature is None or attacker_evs is None:
                spread = await _get_common_spread(attacker)
                if spread:
                    attacker_nature = attacker_nature or spread["nature"]
                    evs = spread.get("evs", {})
                    attacker_evs = attacker_evs if attacker_evs is not None else evs.get("attack" if is_physical else "special_attack", 252)
                    attacker_item = attacker_item or spread.get("item")

            attacker_nature = attacker_nature or ("adamant" if is_physical else "modest")
            attacker_evs = attacker_evs if attacker_evs is not None else 252

            # Auto-detect ruinous abilities
            sword_of_ruin = False
            beads_of_ruin = False
            atk_abilities = await pokeapi.get_pokemon_abilities(attacker)
            if atk_abilities:
                ab = atk_abilities[0].lower().replace(" ", "-")
                if ab == "sword-of-ruin":
                    sword_of_ruin = True
                elif ab == "beads-of-ruin":
                    beads_of_ruin = True

            atk_nature_enum = Nature(attacker_nature.lower())
            my_nature_enum = Nature(pokemon_nature.lower())

            attacker_build = PokemonBuild(
                name=attacker,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature_enum,
                evs=EVSpread(
                    attack=attacker_evs if is_physical else 0,
                    special_attack=0 if is_physical else attacker_evs
                ),
                item=attacker_item
            )

            def_stat = "defense" if is_physical else "special_defense"
            def_nature_mod = get_nature_modifier(my_nature_enum, def_stat)

            # Search for minimum EVs
            best_spread = None
            for hp_ev in EV_BREAKPOINTS_LV50:
                for def_ev in EV_BREAKPOINTS_LV50:
                    if hp_ev + def_ev > 508:
                        continue

                    defender = PokemonBuild(
                        name=pokemon,
                        base_stats=my_base,
                        types=my_types,
                        nature=my_nature_enum,
                        evs=EVSpread(
                            hp=hp_ev,
                            defense=def_ev if is_physical else 0,
                            special_defense=0 if is_physical else def_ev
                        )
                    )

                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attacker_item=attacker_item,
                        sword_of_ruin=sword_of_ruin,
                        beads_of_ruin=beads_of_ruin
                    )

                    from vgc_mcp_core.calc.damage import calculate_damage as calc_dmg
                    result = calc_dmg(attacker_build, defender, move_data, modifiers)

                    survive_rolls = sum(1 for r in result.rolls if r < result.defender_hp)
                    survival_pct = (survive_rolls / 16) * 100

                    if survival_pct >= target_survival:
                        total_evs = hp_ev + def_ev
                        if best_spread is None or total_evs < best_spread["total_evs"]:
                            best_spread = {
                                "hp_evs": hp_ev,
                                "def_evs": def_ev,
                                "total_evs": total_evs,
                                "survival_chance": survival_pct,
                                "damage_range": f"{result.min_percent:.1f}-{result.max_percent:.1f}%"
                            }

            if best_spread:
                stat_name = "Def" if is_physical else "SpD"
                return {
                    "pokemon": pokemon,
                    "attacker": attacker,
                    "move": move,
                    "spread": f"{best_spread['hp_evs']} HP / {best_spread['def_evs']} {stat_name}",
                    "survival_chance": f"{best_spread['survival_chance']:.1f}%",
                    "damage_taken": best_spread["damage_range"],
                    "evs_used": best_spread["total_evs"],
                    "evs_remaining": 508 - best_spread["total_evs"]
                }
            else:
                return {
                    "pokemon": pokemon,
                    "attacker": attacker,
                    "move": move,
                    "result": "IMPOSSIBLE - Cannot survive this attack with any EV investment"
                }
        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def design_spread(
        pokemon: str,
        nature: str,
        survive_pokemon: Optional[str] = None,
        survive_move: Optional[str] = None,
        outspeed_pokemon: Optional[str] = None,
        outspeed_nature: str = "timid",
        outspeed_evs: int = 252
    ) -> dict:
        """Design an EV spread to survive an attack and/or outspeed a target."""
        try:
            my_base = await pokeapi.get_base_stats(pokemon)
            my_types = await pokeapi.get_pokemon_types(pokemon)
            my_nature = Nature(nature.lower())

            speed_evs_needed = 0
            survival_info = None

            # Calculate speed EVs needed
            if outspeed_pokemon:
                target_base = await pokeapi.get_base_stats(outspeed_pokemon)
                target_nature = Nature(outspeed_nature.lower())
                target_speed_mod = get_nature_modifier(target_nature, "speed")
                target_speed = calculate_speed(target_base.speed, 31, outspeed_evs, 50, target_speed_mod)

                my_speed_mod = get_nature_modifier(my_nature, "speed")
                for ev in EV_BREAKPOINTS_LV50:
                    my_speed = calculate_speed(my_base.speed, 31, ev, 50, my_speed_mod)
                    if my_speed > target_speed:
                        speed_evs_needed = ev
                        break
                else:
                    speed_evs_needed = 252

            remaining = 508 - speed_evs_needed

            # Calculate survival EVs
            if survive_pokemon and survive_move:
                atk_base = await pokeapi.get_base_stats(survive_pokemon)
                atk_types = await pokeapi.get_pokemon_types(survive_pokemon)
                move_data = await pokeapi.get_move(survive_move, user_name=survive_pokemon)
                is_physical = move_data.category == MoveCategory.PHYSICAL

                spread = await _get_common_spread(survive_pokemon)
                atk_nature = "adamant" if is_physical else "modest"
                atk_evs = 252
                atk_item = None
                atk_ability = None

                if spread:
                    atk_nature = spread["nature"]
                    evs = spread.get("evs", {})
                    atk_evs = evs.get("attack" if is_physical else "special_attack", 252)
                    atk_item = spread.get("item")
                    atk_ability = spread.get("ability")

                # Auto-detect ruinous
                sword_of_ruin = False
                beads_of_ruin = False
                if atk_ability:
                    ab = atk_ability.lower().replace(" ", "-")
                    if ab == "sword-of-ruin":
                        sword_of_ruin = True
                    elif ab == "beads-of-ruin":
                        beads_of_ruin = True

                atk_nature_enum = Nature(atk_nature.lower())
                attacker_build = PokemonBuild(
                    name=survive_pokemon,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature_enum,
                    evs=EVSpread(
                        attack=atk_evs if is_physical else 0,
                        special_attack=0 if is_physical else atk_evs
                    ),
                    item=atk_item
                )

                # Find minimum bulk EVs
                best = None
                for hp_ev in EV_BREAKPOINTS_LV50:
                    for def_ev in EV_BREAKPOINTS_LV50:
                        if hp_ev + def_ev > remaining:
                            continue

                        defender = PokemonBuild(
                            name=pokemon,
                            base_stats=my_base,
                            types=my_types,
                            nature=my_nature,
                            evs=EVSpread(
                                hp=hp_ev,
                                defense=def_ev if is_physical else 0,
                                special_defense=0 if is_physical else def_ev
                            )
                        )

                        modifiers = DamageModifiers(
                            is_doubles=True,
                            attacker_item=atk_item,
                            sword_of_ruin=sword_of_ruin,
                            beads_of_ruin=beads_of_ruin
                        )

                        from vgc_mcp_core.calc.damage import calculate_damage as calc_dmg
                        result = calc_dmg(attacker_build, defender, move_data, modifiers)

                        survive_rolls = sum(1 for r in result.rolls if r < result.defender_hp)
                        survival_pct = (survive_rolls / 16) * 100

                        if survival_pct >= 93.75:
                            total = hp_ev + def_ev
                            if best is None or total < best["total"]:
                                best = {
                                    "hp": hp_ev,
                                    "def": def_ev,
                                    "total": total,
                                    "survival": survival_pct,
                                    "damage": f"{result.min_percent:.1f}-{result.max_percent:.1f}%"
                                }

                if best:
                    survival_info = {
                        "attacker": survive_pokemon,
                        "move": survive_move,
                        "hp_evs": best["hp"],
                        "def_evs": best["def"],
                        "survival_chance": f"{best['survival']:.1f}%",
                        "damage_taken": best["damage"]
                    }

            # Build final spread
            hp_evs = survival_info["hp_evs"] if survival_info else 0
            def_evs = survival_info["def_evs"] if survival_info else 0
            leftover = 508 - speed_evs_needed - hp_evs - def_evs

            return {
                "pokemon": pokemon,
                "nature": nature,
                "spread": {
                    "hp": hp_evs,
                    "speed": speed_evs_needed,
                    "bulk": def_evs,
                    "remaining": leftover
                },
                "speed_benchmark": f"Outspeeds {outspeed_pokemon}" if outspeed_pokemon else None,
                "survival_benchmark": survival_info,
                "summary": f"{hp_evs} HP / {def_evs} Def or SpD / {speed_evs_needed} Spe ({leftover} EVs remaining)"
            }
        except Exception as e:
            return {"error": str(e)}
