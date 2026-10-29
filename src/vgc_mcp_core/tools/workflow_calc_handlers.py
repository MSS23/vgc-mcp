"""Handlers for workflow calc tools (quick damage, speed matchups, Smogon-set calcs, role design)."""

from typing import Any, Optional

from vgc_mcp_core.calc.damage import format_percent
from vgc_mcp_core.config import EV_BREAKPOINTS_LV50
from vgc_mcp_core.tools import spread_contract as sc
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.tools.spread_common import slash_values
from vgc_mcp_core.utils.errors import ErrorCodes, error_response, success_response
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name


async def quick_damage_check(
    pokeapi: Any,
    attacker: str,
    defender: str,
    move: str,
    attacker_item: Optional[str] = None,
    attacker_ability: Optional[str] = None,
    defender_hp_evs: int = 0,
    defender_def_evs: int = 0,
    is_doubles: bool = True,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.damage import calculate_damage
    from vgc_mcp_core.calc.modifiers import DamageModifiers
    from vgc_mcp_core.models.move import MoveCategory
    from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature

    try:
        # Get Pokemon data
        atk_data = await pokeapi.get_pokemon(attacker)
        def_data = await pokeapi.get_pokemon(defender)
        move_data = await pokeapi.get_move(move)

        if not atk_data:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Attacker '{attacker}' not found")
        if not def_data:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Defender '{defender}' not found")
        if not move_data:
            return error_response(ErrorCodes.MOVE_NOT_FOUND, f"Move '{move}' not found")

        is_physical = move_data.category == MoveCategory.PHYSICAL

        # Auto-detect ability if not provided
        if not attacker_ability:
            abilities = await pokeapi.get_pokemon_abilities(attacker)
            if abilities:
                attacker_ability = abilities[0].lower().replace(" ", "-")

        # Create attacker with competitive defaults
        atk_nature = Nature.ADAMANT if is_physical else Nature.MODEST
        atk_build = build_pokemon(
            name=attacker,
            base_stats=BaseStats(**atk_data["base_stats"]),
            types=atk_data.get("types", []),
            nature=atk_nature,
            spread=EVSpread(
                attack=252 if is_physical else 0,
                special_attack=0 if is_physical else 252
            ),
            ability=attacker_ability,
            item=attacker_item,
        )

        # Create defender
        def_build = build_pokemon(
            name=defender,
            base_stats=BaseStats(**def_data["base_stats"]),
            types=def_data.get("types", []),
            nature=Nature.SERIOUS,
            spread=EVSpread(
                hp=defender_hp_evs,
                defense=defender_def_evs if is_physical else 0,
                special_defense=0 if is_physical else defender_def_evs
            ),
        )

        # Calculate damage
        modifiers = DamageModifiers.from_scenario(
            is_doubles=is_doubles,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
        )
        result = calculate_damage(atk_build, def_build, move_data, modifiers)

        # Determine KO chance
        if result.min_percent >= 100:
            ko_chance = "Guaranteed OHKO"
        elif result.max_percent >= 100:
            ko_chance = "Possible OHKO (roll)"
        elif result.max_percent >= 50:
            ko_chance = "2HKO"
        elif result.max_percent >= 33:
            ko_chance = "3HKO"
        else:
            ko_chance = "4HKO+"

        # Suggest what could change outcome
        suggestions = []
        if result.max_percent < 100 and not attacker_item:
            suggestions.append("Life Orb would add ~30% damage")
            suggestions.append("Choice Band/Specs would add ~50% damage")
        if result.min_percent >= 100:
            suggestions.append("Focus Sash would let defender survive")

        return success_response(
            f"{attacker} vs {defender}",
            attacker=attacker,
            attacker_ability=attacker_ability,
            attacker_item=attacker_item,
            defender=defender,
            move=move,
            move_type=move_data.type,
            base_power=move_data.power,
            damage_range=result.damage_range,
            percent_range=f"{format_percent(result.min_percent)}% - {format_percent(result.max_percent)}%",
            survives=result.max_percent < 100,
            ko_chance=ko_chance,
            defender_hp=result.defender_hp,
            what_changes_outcome=suggestions if suggestions else ["No major items would change this outcome"]
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def analyze_speed_matchup(
    pokeapi: Any,
    my_pokemon: str,
    opponent_pokemon: str,
    my_nature: str = 'jolly',
    my_speed_evs: int = 252,
    opponent_nature: str = 'jolly',
    opponent_speed_evs: int = 252,
    include_scenarios: Optional[list[str]] = None,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.stats import calculate_stat
    from vgc_mcp_core.models.pokemon import Nature, get_nature_modifier

    try:
        my_data = await pokeapi.get_pokemon(my_pokemon)
        opp_data = await pokeapi.get_pokemon(opponent_pokemon)

        if not my_data:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Pokemon '{my_pokemon}' not found")
        if not opp_data:
            return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Pokemon '{opponent_pokemon}' not found")

        try:
            my_nat = Nature(my_nature.lower())
            opp_nat = Nature(opponent_nature.lower())
        except ValueError as e:
            return error_response(ErrorCodes.INVALID_NATURE, str(e))

        my_speed_mod = get_nature_modifier(my_nat, "speed")
        opp_speed_mod = get_nature_modifier(opp_nat, "speed")

        my_speed = calculate_stat(my_data["base_stats"]["speed"], 31, my_speed_evs, 50, my_speed_mod)
        opp_speed = calculate_stat(opp_data["base_stats"]["speed"], 31, opponent_speed_evs, 50, opp_speed_mod)

        results = {
            "my_pokemon": my_pokemon,
            "my_speed": my_speed,
            "opponent_pokemon": opponent_pokemon,
            "opponent_speed": opp_speed,
            "normal": {
                "faster": my_pokemon if my_speed > opp_speed else (opponent_pokemon if opp_speed > my_speed else "Speed tie"),
                "difference": abs(my_speed - opp_speed)
            }
        }

        scenarios = include_scenarios or ["tailwind", "trick_room", "paralysis"]
        scenario_results = {}

        # Helper to determine faster Pokemon with proper tie handling
        def get_faster(speed_a: int, speed_b: int, name_a: str, name_b: str) -> str:
            if speed_a > speed_b:
                return name_a
            elif speed_b > speed_a:
                return name_b
            else:
                return "Speed tie (50/50)"

        for scenario in scenarios:
            if scenario == "tailwind":
                my_tw = my_speed * 2
                opp_tw = opp_speed * 2
                scenario_results["my_tailwind"] = {
                    "my_speed": my_tw,
                    "opponent_speed": opp_speed,
                    "faster": get_faster(my_tw, opp_speed, my_pokemon, opponent_pokemon)
                }
                scenario_results["opponent_tailwind"] = {
                    "my_speed": my_speed,
                    "opponent_speed": opp_tw,
                    "faster": get_faster(my_speed, opp_tw, my_pokemon, opponent_pokemon)
                }
            elif scenario == "trick_room":
                # In Trick Room, slower moves first - but ties are still 50/50
                if my_speed == opp_speed:
                    faster_in_tr = "Speed tie (50/50)"
                elif my_speed > opp_speed:
                    faster_in_tr = opponent_pokemon
                else:
                    faster_in_tr = my_pokemon
                scenario_results["trick_room"] = {
                    "faster": faster_in_tr,
                    "note": "Slower Pokemon moves first in Trick Room"
                }
            elif scenario == "paralysis":
                my_para = int(my_speed * 0.5)
                opp_para = int(opp_speed * 0.5)
                scenario_results["my_paralysis"] = {
                    "my_speed": my_para,
                    "faster": get_faster(my_para, opp_speed, my_pokemon, opponent_pokemon)
                }
                scenario_results["opponent_paralysis"] = {
                    "opponent_speed": opp_para,
                    "faster": get_faster(my_speed, opp_para, my_pokemon, opponent_pokemon)
                }
            elif scenario == "icy_wind":
                from vgc_mcp_core.calc.speed_control import apply_stage_modifier
                opp_icy = apply_stage_modifier(opp_speed, -1)
                scenario_results["after_icy_wind"] = {
                    "opponent_speed": opp_icy,
                    "faster": get_faster(my_speed, opp_icy, my_pokemon, opponent_pokemon)
                }
            elif scenario == "choice_scarf":
                my_scarf = int(my_speed * 1.5)
                opp_scarf = int(opp_speed * 1.5)
                scenario_results["my_choice_scarf"] = {
                    "my_speed": my_scarf,
                    "faster": get_faster(my_scarf, opp_speed, my_pokemon, opponent_pokemon)
                }
                scenario_results["opponent_choice_scarf"] = {
                    "opponent_speed": opp_scarf,
                    "faster": get_faster(my_speed, opp_scarf, my_pokemon, opponent_pokemon)
                }

        results["scenarios"] = scenario_results

        # Calculate EVs needed to outspeed
        if my_speed <= opp_speed:
            for ev in EV_BREAKPOINTS_LV50:
                test_speed = calculate_stat(my_data["base_stats"]["speed"], 31, ev, 50, my_speed_mod)
                if test_speed > opp_speed:
                    results["evs_to_outspeed"] = ev
                    break
            else:
                results["evs_to_outspeed"] = "Cannot outspeed with current nature"

        return success_response(
            f"Speed comparison: {my_pokemon} vs {opponent_pokemon}",
            **results
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def design_pokemon_for_role(
    pokeapi: Any,
    pokemon_name: str,
    role: str = 'auto',
    speed_benchmark: Optional[str] = None,
    survive_hit: Optional[dict[str, Any]] = None,
    item: Optional[str] = None,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.stats import calculate_hp, calculate_stat
    from vgc_mcp_core.models.pokemon import Nature, get_nature_modifier

    try:
        pokemon_data = await pokeapi.get_pokemon(pokemon_name)
        if not pokemon_data:
            suggestions = suggest_pokemon_name(pokemon_name)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Pokemon '{pokemon_name}' not found",
                suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
            )

        base_stats = pokemon_data["base_stats"]
        types = pokemon_data.get("types", [])
        abilities = await pokeapi.get_pokemon_abilities(pokemon_name)

        # Auto-detect role
        if role == "auto":
            atk = base_stats["attack"]
            spa = base_stats["special_attack"]
            speed = base_stats["speed"]
            hp = base_stats["hp"]
            defense = (base_stats["defense"] + base_stats["special_defense"]) / 2

            if speed >= 100 and max(atk, spa) >= 100:
                role = "sweeper"
            elif speed < 50 and max(atk, spa) >= 90:
                role = "trick_room"
            elif hp >= 90 and defense >= 85:
                role = "wall"
            elif hp >= 80 and max(atk, spa) >= 90:
                role = "bulky_attacker"
            else:
                role = "support"

        is_physical = base_stats["attack"] > base_stats["special_attack"]

        # Define role templates
        role_templates = {
            "sweeper": {
                "nature": "jolly" if is_physical else "timid",
                "evs": {"spe": 252, "atk" if is_physical else "spa": 252, "hp": 4},
                "item": "life-orb" if not item else item,
                "reasoning": "Max Speed and offense for sweeping"
            },
            "bulky_attacker": {
                "nature": "adamant" if is_physical else "modest",
                "evs": {"hp": 252, "atk" if is_physical else "spa": 252, "spe": 4},
                "item": "assault-vest" if not is_physical else "choice-band",
                "reasoning": "Bulk with offensive pressure"
            },
            "wall": {
                "nature": "bold" if base_stats["defense"] >= base_stats["special_defense"] else "calm",
                "evs": {"hp": 252, "def": 252 if base_stats["defense"] >= base_stats["special_defense"] else 0,
                        "spd": 0 if base_stats["defense"] >= base_stats["special_defense"] else 252, "spe": 4},
                "item": "leftovers",
                "reasoning": "Maximum bulk for defensive presence"
            },
            "support": {
                "nature": "bold",
                "evs": {"hp": 252, "def": 128, "spd": 128},
                "item": "sitrus-berry",
                "reasoning": "Balanced bulk for team support"
            },
            "trick_room": {
                "nature": "brave" if is_physical else "quiet",
                "evs": {"hp": 252, "atk" if is_physical else "spa": 252, "spd": 4},
                "item": "life-orb",
                "reasoning": "Minimum Speed (0 IVs), max offense for Trick Room"
            }
        }

        template = role_templates.get(role, role_templates["sweeper"])

        # Override with speed benchmark if provided
        evs = template["evs"].copy()
        speed_evs_needed = evs.get("spe", 0)

        if speed_benchmark:
            bench_data = await pokeapi.get_pokemon(speed_benchmark)
            if bench_data:
                bench_speed = calculate_stat(bench_data["base_stats"]["speed"], 31, 252, 50, 1.1)
                try:
                    parsed_nature = Nature(template["nature"].lower())
                    speed_mod = get_nature_modifier(parsed_nature, "speed")
                    for ev in EV_BREAKPOINTS_LV50:
                        my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                        if my_speed > bench_speed:
                            speed_evs_needed = ev
                            break
                except ValueError:
                    pass

            evs["spe"] = speed_evs_needed

        # Calculate final stats
        try:
            parsed_nature = Nature(template["nature"].lower())
        except ValueError:
            parsed_nature = Nature.SERIOUS

        hp_evs = evs.get("hp", 0)
        atk_evs = evs.get("atk", 0)
        def_evs = evs.get("def", 0)
        spa_evs = evs.get("spa", 0)
        spd_evs = evs.get("spd", 0)
        spe_evs = evs.get("spe", 0)

        final_stats = {
            "hp": calculate_hp(base_stats["hp"], 31, hp_evs, 50),
            "attack": calculate_stat(base_stats["attack"], 31, atk_evs, 50, get_nature_modifier(parsed_nature, "attack")),
            "defense": calculate_stat(base_stats["defense"], 31, def_evs, 50, get_nature_modifier(parsed_nature, "defense")),
            "special_attack": calculate_stat(base_stats["special_attack"], 31, spa_evs, 50, get_nature_modifier(parsed_nature, "special_attack")),
            "special_defense": calculate_stat(base_stats["special_defense"], 31, spd_evs, 50, get_nature_modifier(parsed_nature, "special_defense")),
            "speed": calculate_stat(base_stats["speed"], 31, spe_evs, 50, get_nature_modifier(parsed_nature, "speed"))
        }

        # Suggest moves based on type
        suggested_moves = []
        stab_moves = {
            "fire": ["flamethrower", "heat-wave", "fire-blast"],
            "water": ["hydro-pump", "scald", "surf"],
            "grass": ["energy-ball", "leaf-storm", "giga-drain"],
            "electric": ["thunderbolt", "volt-switch", "thunder"],
            "psychic": ["psychic", "psyshock", "expanding-force"],
            "fairy": ["moonblast", "dazzling-gleam", "play-rough"],
            "dark": ["dark-pulse", "knock-off", "foul-play"],
            "ghost": ["shadow-ball", "shadow-sneak", "hex"],
            "dragon": ["draco-meteor", "dragon-pulse", "dragon-claw"],
            "fighting": ["close-combat", "aura-sphere", "drain-punch"],
            "ground": ["earthquake", "earth-power", "high-horsepower"],
            "rock": ["rock-slide", "stone-edge", "power-gem"],
            "ice": ["ice-beam", "blizzard", "freeze-dry"],
            "steel": ["iron-head", "flash-cannon", "steel-beam"],
            "poison": ["sludge-bomb", "gunk-shot", "poison-jab"],
            "flying": ["air-slash", "hurricane", "brave-bird"],
            "bug": ["bug-buzz", "u-turn", "x-scissor"],
            "normal": ["body-slam", "hyper-voice", "facade"]
        }

        for t in types:
            if t.lower() in stab_moves:
                moves = stab_moves[t.lower()]
                if is_physical:
                    suggested_moves.append(moves[-1] if len(moves) > 2 else moves[0])
                else:
                    suggested_moves.append(moves[0])

        suggested_moves.append("protect")  # Always suggest Protect for VGC

        return success_response(
            f"Designed {role} build for {pokemon_name}",
            pokemon=pokemon_name,
            role=role,
            types=types,
            ability=abilities[0] if abilities else "Unknown",
            nature=template["nature"],
            nature_reasoning=template["reasoning"],
            evs={
                "HP": hp_evs,
                "Atk": atk_evs,
                "Def": def_evs,
                "SpA": spa_evs,
                "SpD": spd_evs,
                "Spe": spe_evs
            },
            item=item or template["item"],
            suggested_moves=suggested_moves[:4],
            final_stats=final_stats,
            speed_benchmark_met=f"Outspeeds {speed_benchmark}" if speed_benchmark else None,
            showdown_format=(
                f"{pokemon_name.title()}\n"
                f"Ability: {abilities[0] if abilities else 'Unknown'}\n"
                f"EVs: {hp_evs} HP / {atk_evs} Atk / {def_evs} Def / {spa_evs} SpA / {spd_evs} SpD / {spe_evs} Spe\n"
                f"{template['nature'].title()} Nature\n"
                f"- {suggested_moves[0].replace('-', ' ').title() if suggested_moves else 'Move 1'}\n"
                f"- {suggested_moves[1].replace('-', ' ').title() if len(suggested_moves) > 1 else 'Move 2'}\n"
                f"- {suggested_moves[2].replace('-', ' ').title() if len(suggested_moves) > 2 else 'Move 3'}\n"
                f"- Protect"
            )
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def calc_damage_vs_smogon_sets(
    pokeapi: Any,
    smogon: Any,
    my_pokemon: str,
    my_nature: str,
    my_hp_evs: int = 0,
    my_atk_evs: int = 0,
    my_def_evs: int = 0,
    my_spa_evs: int = 0,
    my_spd_evs: int = 0,
    my_spe_evs: int = 0,
    my_spread: Optional[str] = None,
    my_item: Optional[str] = None,
    my_ability: Optional[str] = None,
    my_tera_type: Optional[str] = None,
    opponent_pokemon: str = '',
    move: str = '',
    direction: str = 'from',
    num_sets: int = 3,
    attacker_stage: int = 0,
    intimidate: Optional[bool] = None,
) -> dict[str, Any]:
    if my_spread:
        try:
            my_hp_evs, my_atk_evs, my_def_evs, my_spa_evs, my_spd_evs, my_spe_evs = slash_values(my_spread)
        except ValueError as e:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(e))
    from vgc_mcp_core.calc.damage import DamageResult, calculate_damage
    from vgc_mcp_core.calc.modifiers import DamageModifiers
    from vgc_mcp_core.calc.stats import calculate_all_stats
    from vgc_mcp_core.models.pokemon import (
        EVSpread,
        Nature,
        StatPointSpread,
    )
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    from vgc_mcp_core.tools.ability_helpers import compute_intimidate_attack_stage

    try:
        # Validate inputs
        if not opponent_pokemon:
            return error_response(ErrorCodes.VALIDATION_ERROR, "opponent_pokemon is required")
        if not move:
            return error_response(ErrorCodes.VALIDATION_ERROR, "move is required")
        if direction not in ["from", "to"]:
            return error_response(ErrorCodes.VALIDATION_ERROR, "direction must be 'from' or 'to'")

        # Get my Pokemon data
        try:
            await pokeapi.get_pokemon(my_pokemon)
            my_base_stats = await pokeapi.get_base_stats(my_pokemon)
        except Exception:
            suggestions = suggest_pokemon_name(my_pokemon)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Pokemon '{my_pokemon}' not found",
                suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
            )

        # Get opponent Pokemon data
        try:
            await pokeapi.get_pokemon(opponent_pokemon)
            opp_base_stats = await pokeapi.get_base_stats(opponent_pokemon)
        except Exception:
            suggestions = suggest_pokemon_name(opponent_pokemon)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Pokemon '{opponent_pokemon}' not found",
                suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
            )

        # Get move data
        move_data = await pokeapi.get_move(move)
        if not move_data:
            return error_response(ErrorCodes.MOVE_NOT_FOUND, f"Move '{move}' not found")

        # Parse my nature
        try:
            parsed_nature = Nature(my_nature.lower())
        except ValueError:
            return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {my_nature}")

        # Resolve my ability (Mega form > Smogon most-used > pokeapi) so
        # e.g. Incineroar reads as Intimidate, not pokeapi's first-listed Blaze.
        if not my_ability:
            from vgc_mcp_core.tools.ability_helpers import resolve_ability
            my_ability, _ = await resolve_ability(my_pokemon, pokeapi=pokeapi, smogon_client=smogon)
        if my_ability:
            my_ability = my_ability.lower().replace(" ", "-")

        # Build my Pokemon
        my_types = await pokeapi.get_pokemon_types(my_pokemon)
        # If Tera active, defensive typing changes
        defensive_types = [my_tera_type] if my_tera_type else my_types

        # Champions: the my_*_evs ints are Stat Points (0-32, 66 total).
        is_champions = detect_champions_format(my_pokemon, opponent_pokemon)
        my_alloc = {
            "hp": my_hp_evs, "attack": my_atk_evs, "defense": my_def_evs,
            "special_attack": my_spa_evs, "special_defense": my_spd_evs, "speed": my_spe_evs,
        }
        if is_champions:
            if max(my_alloc.values()) > 32 or sum(my_alloc.values()) > 66:
                return error_response(
                    ErrorCodes.INVALID_PARAMETER,
                    "Champions session: my_*_evs are Stat Points (0-32 per stat, 66 total)",
                )
            my_build = build_pokemon(
                name=my_pokemon,
                base_stats=my_base_stats,
                types=defensive_types,
                nature=parsed_nature,
                champions=True,
                spread=StatPointSpread(**my_alloc),
                item=my_item,
                ability=my_ability,
                tera_type=my_tera_type,
            )
        else:
            my_build = build_pokemon(
                name=my_pokemon,
                base_stats=my_base_stats,
                types=defensive_types,
                nature=parsed_nature,
                spread=EVSpread(**my_alloc),
                item=my_item,
                ability=my_ability,
                tera_type=my_tera_type,
            )

        # Final stats for display (format-aware: SP formula in Champions)
        my_final_stats = calculate_all_stats(my_build)

        # Get opponent's Smogon usage data
        opp_usage = await smogon.get_pokemon_usage(opponent_pokemon)
        if not opp_usage:
            return error_response(
                ErrorCodes.API_ERROR,
                f"No Smogon usage data for {opponent_pokemon}",
                suggestions=["This Pokemon may not have enough usage in the current format"]
            )

        opp_spreads = opp_usage.get("spreads", [])[:num_sets]
        opp_items = opp_usage.get("items", {})
        opp_abilities = opp_usage.get("abilities", {})
        opp_tera_types = opp_usage.get("tera_types", {})

        if not opp_spreads:
            return error_response(
                ErrorCodes.API_ERROR,
                f"No spread data available for {opponent_pokemon}"
            )

        # Get most common item and ability for opponent
        top_item = list(opp_items.keys())[0] if opp_items else None
        top_ability = list(opp_abilities.keys())[0] if opp_abilities else None
        top_tera = list(opp_tera_types.keys())[0] if opp_tera_types else None

        # Normalize item/ability names
        if top_item:
            top_item = top_item.lower().replace(" ", "-")
        if top_ability:
            top_ability = top_ability.lower().replace(" ", "-")

        opp_types = await pokeapi.get_pokemon_types(opponent_pokemon)

        damage_results = []
        opp_builds = []
        survives_count = 0
        ko_count = 0

        # Check for special ability interactions
        warnings = []

        # Check if opponent is Urshifu (has Unseen Fist)
        normalized_opp = opponent_pokemon.lower().replace(" ", "-")
        if normalized_opp in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
            warnings.append("⚠️ Urshifu has Unseen Fist - contact moves bypass Protect!")

        # Calculate my Life Orb recoil if I have one
        my_life_orb_recoil = 0
        if my_item and my_item.lower().replace(" ", "-") == "life-orb":
            my_life_orb_recoil = my_final_stats["hp"] // 10

        # Intimidate on the DEFENDING side drops the attacker's Atk by one
        # stage at switch-in (blocked by Clear Body etc., reversed by
        # Contrary/Defiant). Computed once; applied as a second calc per set.
        atk_ability, def_ability = (
            (top_ability, my_ability) if direction == "from" else (my_ability, top_ability)
        )
        defender_has_intimidate = (def_ability or "").lower().replace(" ", "-") == "intimidate"
        is_physical_move = move_data.category.value == "physical"
        intim_stage, intim_note = 0, None
        if intimidate is not False and (defender_has_intimidate or intimidate):
            intim_stage, intim_note = compute_intimidate_attack_stage(
                # intimidate=True models an Intimidate partner on the field
                defender_ability="intimidate" if intimidate else def_ability,
                attacker_ability=atk_ability,
                is_physical=is_physical_move,
            )
            if intimidate and not is_physical_move:
                intim_note = f"Intimidate requested, but {move} is special — Atk drop has no effect"
        intimidate_info = None
        if intim_note:
            intimidate_info = {
                "applied": intim_stage != 0,
                "stage": intim_stage,
                "note": intim_note,
                "intimidate_user": (
                    (opponent_pokemon if direction == "to" else my_pokemon)
                    if defender_has_intimidate else "requested (Intimidate partner on the field)"
                ),
                "source": "auto (defender has Intimidate)" if defender_has_intimidate else "requested",
            }

        def _short_outcome(res: DamageResult) -> str:
            if direction == "from":
                if res.max_percent < 100:
                    return f"Survives (HP: {my_final_stats['hp'] - res.max_damage}-{my_final_stats['hp'] - res.min_damage})"
                return "KO'd"
            if res.min_percent >= 100:
                return "Guaranteed OHKO"
            if res.max_percent >= 100:
                return "Possible OHKO (roll)"
            return f"{res.max_percent:.0f}% max"

        alloc_key = "sps" if is_champions else "evs"
        alloc_unit = "SP" if is_champions else "EV"
        stat_keys = ("hp", "attack", "defense", "special_attack", "special_defense", "speed")
        for i, spread in enumerate(opp_spreads):
            spread_evs = spread.get(alloc_key)
            if not spread_evs:
                continue  # wrong-format or unparsable spread

            spread_nature_str = spread.get("nature", "Serious")

            try:
                spread_nature = Nature(spread_nature_str.lower())
            except ValueError:
                spread_nature = Nature.SERIOUS

            # Build opponent with this spread (SP spread in Champions)
            opp_build = build_pokemon(
                name=opponent_pokemon,
                base_stats=opp_base_stats,
                types=opp_types,
                nature=spread_nature,
                item=top_item,
                ability=top_ability,
                champions=is_champions,
                spread=StatPointSpread(**spread_evs) if is_champions else EVSpread(**spread_evs),
            )

            # Set up modifiers based on direction
            if direction == "from":
                # Opponent attacks me
                attacker = opp_build
                defender = my_build
                modifiers = DamageModifiers.from_scenario(
                    attacker_item=top_item,
                    attacker_ability=top_ability,
                    defender_item=my_item,
                    defender_ability=my_ability,
                    defender_tera_type=my_tera_type,
                    attack_stage=attacker_stage,
                    special_attack_stage=attacker_stage,
                )
            else:
                # I attack opponent
                attacker = my_build
                defender = opp_build
                modifiers = DamageModifiers.from_scenario(
                    attacker_item=my_item,
                    attacker_ability=my_ability,
                    defender_item=top_item,
                    defender_ability=top_ability,
                    tera_type=my_tera_type,
                    attack_stage=attacker_stage,
                    special_attack_stage=attacker_stage,
                )

            result = calculate_damage(attacker, defender, move_data, modifiers)
            intim_result = None
            if intim_stage:
                from dataclasses import replace as _replace
                intim_result = calculate_damage(
                    attacker, defender, move_data,
                    _replace(modifiers, attack_stage=attacker_stage + intim_stage),
                )

            # Determine outcome
            alloc_desc = " / ".join(
                f"{spread_evs.get(k, 0)} {lbl}"
                for k, lbl in zip(stat_keys, ("HP", "Atk", "Def", "SpA", "SpD", "Spe"))
                if spread_evs.get(k, 0)
            ) or f"0 {alloc_unit}s"
            slash_str = "/".join(str(spread_evs.get(k, 0)) for k in stat_keys)
            result_entry = {
                "set_rank": i + 1,
                "usage": f"{spread.get('usage', 0)}%",
                "nature": spread_nature_str,
                alloc_key: alloc_desc,
                "allocation_unit": alloc_unit,
                "spread_line": (
                    f"{spread_nature_str} {slash_str}"
                    + (" SP" if is_champions else "")
                    + (f" @ {top_item}" if top_item else "")
                ),
                "damage_range": result.damage_range,
                "percent_range": f"{format_percent(result.min_percent)}% - {format_percent(result.max_percent)}%",
            }
            if intim_result is not None:
                result_entry["after_intimidate"] = {
                    "attack_stage": attacker_stage + intim_stage,
                    "damage_range": intim_result.damage_range,
                    "percent_range": f"{format_percent(intim_result.min_percent)}% - {format_percent(intim_result.max_percent)}%",
                    "outcome": _short_outcome(intim_result),
                }

            if direction == "from":
                # I'm being attacked
                survives = result.max_percent < 100
                hp_remaining_min = my_final_stats["hp"] - result.max_damage
                hp_remaining_max = my_final_stats["hp"] - result.min_damage

                # Calculate survival after my Life Orb recoil (if I attack back with Extreme Speed, etc.)
                if my_life_orb_recoil > 0 and survives:
                    hp_after_attack_then_lo = hp_remaining_min - my_life_orb_recoil
                    survives_after_lo = hp_after_attack_then_lo > 0

                    result_entry["hp_remaining"] = f"{hp_remaining_min}-{hp_remaining_max} HP"
                    result_entry["life_orb_recoil"] = f"-{my_life_orb_recoil} HP ({(my_life_orb_recoil / my_final_stats['hp'] * 100):.0f}%)"

                    if survives and survives_after_lo:
                        outcome = f"Survives (HP: {hp_remaining_min}-{hp_remaining_max}, after LO: {hp_after_attack_then_lo}+)"
                    elif survives and not survives_after_lo:
                        outcome = f"⚠️ Survives hit but DIES to Life Orb recoil! (HP: {hp_remaining_min} -> {hp_after_attack_then_lo})"
                        survives = False  # Don't count as survival
                    else:
                        outcome = "KO'd"
                else:
                    outcome = "Survives" if survives else "KO'd"
                    if survives:
                        result_entry["hp_remaining"] = f"{hp_remaining_min}-{hp_remaining_max} HP"

                if survives:
                    survives_count += 1
            else:
                # I'm attacking
                kos = result.min_percent >= 100
                possible_ko = result.max_percent >= 100
                if kos:
                    ko_count += 1
                    outcome = "Guaranteed OHKO"
                elif possible_ko:
                    ko_count += 0.5  # Partial credit for roll
                    outcome = "Possible OHKO (roll)"
                else:
                    outcome = f"{result.max_percent:.0f}% max"

                # Add Life Orb recoil note for offensive calcs
                if my_life_orb_recoil > 0:
                    result_entry["life_orb_recoil"] = f"-{my_life_orb_recoil} HP per attack"

            result_entry["outcome"] = outcome
            damage_results.append(result_entry)
            opp_builds.append(opp_build)

        # Build summary
        if direction == "from":
            summary = f"Survives {survives_count}/{len(damage_results)} common sets"
            if survives_count == len(damage_results):
                verdict = "Safe - survives all common sets"
            elif survives_count == 0:
                verdict = "Danger - KO'd by all common sets"
            else:
                verdict = f"Mixed - survives {survives_count}/{len(damage_results)}"
        else:
            summary = f"KOs {ko_count}/{len(damage_results)} common sets"
            if ko_count >= len(damage_results):
                verdict = "Offensive threat - OHKOs all common sets"
            elif ko_count == 0:
                verdict = "Not a KO threat - consider boosting item"
            else:
                verdict = f"Situational - KOs {ko_count}/{len(damage_results)}"

        # Build response
        response_data = {
            "your_pokemon": my_pokemon,
            "your_build": {
                "nature": my_nature,
                alloc_key: {
                    "HP": my_hp_evs,
                    "Atk": my_atk_evs,
                    "Def": my_def_evs,
                    "SpA": my_spa_evs,
                    "SpD": my_spd_evs,
                    "Spe": my_spe_evs
                },
                "allocation_unit": alloc_unit,
                "item": my_item,
                "ability": my_ability,
                "tera_type": my_tera_type,
                "final_stats": my_final_stats
            },
            "opponent_pokemon": opponent_pokemon,
            "opponent_common_item": top_item,
            "opponent_common_ability": top_ability,
            "opponent_common_tera": top_tera,
            "move": move,
            "move_type": move_data.type,
            "move_power": move_data.power,
            "direction": "Opponent attacks you" if direction == "from" else "You attack opponent",
            "attacker_stage": attacker_stage,
            "damage_vs_sets": damage_results,
            "summary": summary,
            "verdict": verdict,
            "meta_info": opp_usage.get("_meta", {})
        }

        if intimidate_info:
            response_data["intimidate"] = intimidate_info
            if intim_stage:
                if direction == "from":
                    n_ok = sum(1 for r in damage_results if r["after_intimidate"]["outcome"].startswith("Survives"))
                    intimidate_info["summary"] = f"After Intimidate: survives {n_ok}/{len(damage_results)} common sets"
                else:
                    n_ok = sum(1 for r in damage_results if r["after_intimidate"]["outcome"] == "Guaranteed OHKO")
                    intimidate_info["summary"] = f"After Intimidate: OHKOs {n_ok}/{len(damage_results)} common sets"

        # Add warnings if any
        if warnings:
            response_data["warnings"] = warnings

        # Add Life Orb info if relevant
        if my_life_orb_recoil > 0:
            response_data["your_life_orb_recoil"] = {
                "damage": my_life_orb_recoil,
                "percent": f"{(my_life_orb_recoil / my_final_stats['hp'] * 100):.0f}%",
                "note": "Life Orb costs 10% HP per attacking move"
            }

        response = success_response(
            f"{my_pokemon} vs {opponent_pokemon} ({direction} {move})",
            **response_data
        )
        opp, move_name = sc.species(opponent_pokemon), sc.words(move)
        verdict_text = (f"survives {survives_count}/{len(damage_results)} common {opp} sets' {move_name}"
                        if direction == "from" else
                        f"KOs {ko_count:g}/{len(damage_results)} common {opp} sets with {move_name}")
        return sc.apply_contract(
            response,
            headline=f"{sc.subject(my_build)} {verdict_text}",
            spreads_used={"pokemon": sc.spread_label(my_build),
                          **{f"opponent_set_{n}": sc.spread_label(b) for n, b in enumerate(opp_builds, 1)}},
            data_source=sc.data_source_from_meta(opp_usage.get("_meta")),
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def compare_pokemon_options(
    pokeapi: Any,
    smogon: Any,
    pokemon_a: str,
    pokemon_b: str,
    role: str = 'auto',
    check_vs_pokemon: Optional[str] = None,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.modifiers import get_type_effectiveness
    from vgc_mcp_core.calc.stats import calculate_stat

    try:
        # Fetch both Pokemon
        data_a = await pokeapi.get_pokemon(pokemon_a)
        data_b = await pokeapi.get_pokemon(pokemon_b)

        if not data_a:
            suggestions = suggest_pokemon_name(pokemon_a)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Pokemon '{pokemon_a}' not found",
                suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
            )
        if not data_b:
            suggestions = suggest_pokemon_name(pokemon_b)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Pokemon '{pokemon_b}' not found",
                suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
            )

        stats_a = data_a["base_stats"]
        stats_b = data_b["base_stats"]
        types_a = await pokeapi.get_pokemon_types(pokemon_a)
        types_b = await pokeapi.get_pokemon_types(pokemon_b)
        abilities_a = await pokeapi.get_pokemon_abilities(pokemon_a)
        abilities_b = await pokeapi.get_pokemon_abilities(pokemon_b)

        # Calculate max speed for both (Jolly/Timid 252 EVs)
        max_speed_a = calculate_stat(stats_a["speed"], 31, 252, 50, 1.1)
        max_speed_b = calculate_stat(stats_b["speed"], 31, 252, 50, 1.1)

        # Stat totals
        bst_a = sum(stats_a.values())
        bst_b = sum(stats_b.values())

        # Side by side comparison
        side_by_side = {
            "stat": ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed", "BST"],
            pokemon_a: [stats_a["hp"], stats_a["attack"], stats_a["defense"],
                       stats_a["special_attack"], stats_a["special_defense"], stats_a["speed"], bst_a],
            pokemon_b: [stats_b["hp"], stats_b["attack"], stats_b["defense"],
                       stats_b["special_attack"], stats_b["special_defense"], stats_b["speed"], bst_b],
            "winner": []
        }

        # Determine winner for each stat
        stat_keys = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
        for key in stat_keys:
            if stats_a[key] > stats_b[key]:
                side_by_side["winner"].append(pokemon_a)
            elif stats_b[key] > stats_a[key]:
                side_by_side["winner"].append(pokemon_b)
            else:
                side_by_side["winner"].append("Tie")
        side_by_side["winner"].append(pokemon_a if bst_a > bst_b else (pokemon_b if bst_b > bst_a else "Tie"))

        # Speed comparison
        speed_diff = abs(max_speed_a - max_speed_b)
        speed_comparison = {
            f"{pokemon_a}_max_speed": max_speed_a,
            f"{pokemon_b}_max_speed": max_speed_b,
            "faster": pokemon_a if max_speed_a > max_speed_b else (pokemon_b if max_speed_b > max_speed_a else "Tie"),
            "difference": speed_diff,
            "note": f"{pokemon_a if max_speed_a > max_speed_b else pokemon_b} outspeeds by {speed_diff} points at max investment"
        }

        # Type analysis
        all_types = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
                    "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
                    "Dragon", "Dark", "Steel", "Fairy"]

        weaknesses_a = [t for t in all_types if get_type_effectiveness(t, types_a) >= 2]
        weaknesses_b = [t for t in all_types if get_type_effectiveness(t, types_b) >= 2]
        resistances_a = [t for t in all_types if 0 < get_type_effectiveness(t, types_a) < 1]
        resistances_b = [t for t in all_types if 0 < get_type_effectiveness(t, types_b) < 1]
        immunities_a = [t for t in all_types if get_type_effectiveness(t, types_a) == 0]
        immunities_b = [t for t in all_types if get_type_effectiveness(t, types_b) == 0]

        shared_weaknesses = list(set(weaknesses_a) & set(weaknesses_b))
        unique_weaknesses_a = list(set(weaknesses_a) - set(weaknesses_b))
        unique_weaknesses_b = list(set(weaknesses_b) - set(weaknesses_a))

        typing_analysis = {
            pokemon_a: {
                "types": types_a,
                "weaknesses": weaknesses_a,
                "resistances": resistances_a,
                "immunities": immunities_a
            },
            pokemon_b: {
                "types": types_b,
                "weaknesses": weaknesses_b,
                "resistances": resistances_b,
                "immunities": immunities_b
            },
            "shared_weaknesses": shared_weaknesses,
            "unique_to_a": unique_weaknesses_a,
            "unique_to_b": unique_weaknesses_b
        }

        # Ability comparison
        ability_comparison = {
            pokemon_a: abilities_a,
            pokemon_b: abilities_b
        }

        # Try to get usage data
        usage_data = {}
        try:
            usage_a = await smogon.get_pokemon_usage(pokemon_a)
            if usage_a:
                usage_data[pokemon_a] = {
                    "usage_percent": usage_a.get("usage", "N/A"),
                    "common_items": list(usage_a.get("items", {}).keys())[:3],
                    "common_moves": list(usage_a.get("moves", {}).keys())[:4]
                }
        except Exception:
            pass

        try:
            usage_b = await smogon.get_pokemon_usage(pokemon_b)
            if usage_b:
                usage_data[pokemon_b] = {
                    "usage_percent": usage_b.get("usage", "N/A"),
                    "common_items": list(usage_b.get("items", {}).keys())[:3],
                    "common_moves": list(usage_b.get("moves", {}).keys())[:4]
                }
        except Exception:
            pass

        # Check vs specific threat if provided
        threat_matchup = None
        if check_vs_pokemon:
            try:
                threat_data = await pokeapi.get_pokemon(check_vs_pokemon)
                if threat_data:
                    threat_types = await pokeapi.get_pokemon_types(check_vs_pokemon)
                    eff_a = get_type_effectiveness(types_a[0], threat_types) if types_a else 1.0
                    eff_b = get_type_effectiveness(types_b[0], threat_types) if types_b else 1.0

                    threat_speed = calculate_stat(threat_data["base_stats"]["speed"], 31, 252, 50, 1.1)

                    threat_matchup = {
                        "threat": check_vs_pokemon,
                        "threat_max_speed": threat_speed,
                        f"{pokemon_a}_outspeeds": max_speed_a > threat_speed,
                        f"{pokemon_b}_outspeeds": max_speed_b > threat_speed,
                        f"{pokemon_a}_type_eff": eff_a,
                        f"{pokemon_b}_type_eff": eff_b
                    }
            except Exception:
                pass

        # Generate verdict
        advantages_a = []
        advantages_b = []

        if max_speed_a > max_speed_b:
            advantages_a.append(f"Faster ({max_speed_a} vs {max_speed_b})")
        elif max_speed_b > max_speed_a:
            advantages_b.append(f"Faster ({max_speed_b} vs {max_speed_a})")

        if stats_a["attack"] > stats_b["attack"]:
            advantages_a.append(f"Higher Attack ({stats_a['attack']} vs {stats_b['attack']})")
        elif stats_b["attack"] > stats_a["attack"]:
            advantages_b.append(f"Higher Attack ({stats_b['attack']} vs {stats_a['attack']})")

        if stats_a["special_attack"] > stats_b["special_attack"]:
            advantages_a.append(f"Higher Sp. Atk ({stats_a['special_attack']} vs {stats_b['special_attack']})")
        elif stats_b["special_attack"] > stats_a["special_attack"]:
            advantages_b.append(f"Higher Sp. Atk ({stats_b['special_attack']} vs {stats_a['special_attack']})")

        bulk_a = stats_a["hp"] * (stats_a["defense"] + stats_a["special_defense"])
        bulk_b = stats_b["hp"] * (stats_b["defense"] + stats_b["special_defense"])
        if bulk_a > bulk_b * 1.1:
            advantages_a.append("Bulkier overall")
        elif bulk_b > bulk_a * 1.1:
            advantages_b.append("Bulkier overall")

        if len(weaknesses_a) < len(weaknesses_b):
            advantages_a.append(f"Fewer weaknesses ({len(weaknesses_a)} vs {len(weaknesses_b)})")
        elif len(weaknesses_b) < len(weaknesses_a):
            advantages_b.append(f"Fewer weaknesses ({len(weaknesses_b)} vs {len(weaknesses_a)})")

        if len(advantages_a) > len(advantages_b):
            winner = pokemon_a
            verdict_text = f"{pokemon_a} has more advantages: {', '.join(advantages_a)}"
        elif len(advantages_b) > len(advantages_a):
            winner = pokemon_b
            verdict_text = f"{pokemon_b} has more advantages: {', '.join(advantages_b)}"
        else:
            winner = "Situational"
            verdict_text = f"Both have trade-offs. {pokemon_a}: {', '.join(advantages_a) or 'None'}. {pokemon_b}: {', '.join(advantages_b) or 'None'}"

        return success_response(
            f"Comparison: {pokemon_a} vs {pokemon_b}",
            pokemon_a=pokemon_a,
            pokemon_b=pokemon_b,
            side_by_side=side_by_side,
            speed_comparison=speed_comparison,
            typing_analysis=typing_analysis,
            ability_comparison=ability_comparison,
            usage_data=usage_data if usage_data else "No usage data available",
            threat_matchup=threat_matchup,
            verdict={
                "winner": winner,
                f"{pokemon_a}_advantages": advantages_a,
                f"{pokemon_b}_advantages": advantages_b,
                "summary": verdict_text
            }
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
