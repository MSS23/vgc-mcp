"""MCP tools for damage calculations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..api.pokeapi import PokeAPIClient
from ..api.smogon import SmogonStatsClient
from ..calc.damage import calculate_damage, calculate_ko_threshold, calculate_bulk_threshold
from ..calc.modifiers import DamageModifiers
from ..models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread
from ..utils.errors import error_response, ErrorCodes, pokemon_not_found_error, invalid_nature_error, api_error
from ..utils.fuzzy import suggest_pokemon_name, suggest_nature
from ..ui.resources import create_damage_calc_resource, add_ui_metadata


# Module-level Smogon client reference (set during registration)
_smogon_client: Optional[SmogonStatsClient] = None


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Fetch the most common spread for a Pokemon from Smogon usage stats.

    Returns:
        dict with 'nature' and 'evs' keys, or None if not found
    """
    if _smogon_client is None:
        return None
    try:
        usage = await _smogon_client.get_pokemon_usage(pokemon_name)
        if usage and usage.get("spreads"):
            top_spread = usage["spreads"][0]
            return {
                "nature": top_spread.get("nature", "Serious"),
                "evs": top_spread.get("evs", {}),
                "usage": top_spread.get("usage", 0),
                "item": list(usage.get("items", {}).keys())[0] if usage.get("items") else None,
                "ability": list(usage.get("abilities", {}).keys())[0] if usage.get("abilities") else None,
            }
    except Exception:
        pass
    return None


def register_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register damage calculation tools with the MCP server."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool()
    async def calculate_damage_output(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        attacker_nature: Optional[str] = None,
        attacker_atk_evs: Optional[int] = None,
        attacker_spa_evs: Optional[int] = None,
        defender_nature: Optional[str] = None,
        defender_hp_evs: Optional[int] = None,
        defender_def_evs: Optional[int] = None,
        defender_spd_evs: Optional[int] = None,
        use_smogon_spreads: bool = True,
        is_spread: bool = False,
        weather: Optional[str] = None,
        terrain: Optional[str] = None,
        attacker_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        defender_ability: Optional[str] = None,
        attacker_tera_type: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        reflect: bool = False,
        light_screen: bool = False,
        helping_hand: bool = False,
        commander_active: bool = False,
        defender_commander_active: bool = False,
        beads_of_ruin: bool = False,
        sword_of_ruin: bool = False,
        tablets_of_ruin: bool = False,
        vessel_of_ruin: bool = False,
        attacker_booster_energy: bool = False,
        defender_booster_energy: bool = False
    ) -> dict:
        """
        Calculate damage from one Pokemon to another.

        By default, uses the most common Smogon VGC spread for both Pokemon when
        nature/EVs are not specified. This gives realistic damage calculations
        based on how Pokemon are typically built in competitive play.

        Args:
            attacker_name: Attacking Pokemon's name
            defender_name: Defending Pokemon's name
            move_name: Name of the move being used
            attacker_nature: Attacker's nature. If None and use_smogon_spreads=True, uses most common.
            attacker_atk_evs: Attacker's Attack EVs. If None and use_smogon_spreads=True, uses most common.
            attacker_spa_evs: Attacker's Sp. Atk EVs. If None and use_smogon_spreads=True, uses most common.
            defender_nature: Defender's nature. If None and use_smogon_spreads=True, uses most common.
            defender_hp_evs: Defender's HP EVs. If None and use_smogon_spreads=True, uses most common.
            defender_def_evs: Defender's Defense EVs. If None and use_smogon_spreads=True, uses most common.
            defender_spd_evs: Defender's Sp. Def EVs. If None and use_smogon_spreads=True, uses most common.
            use_smogon_spreads: If True (default), auto-fetch most common spreads from Smogon usage data
            is_spread: True if move is hitting multiple targets (0.75x damage)
            weather: "sun", "rain", "sand", or "snow" (affects Fire/Water moves)
            terrain: "electric", "grassy", "psychic", or "misty" (affects damage)
            attacker_item: Item like "life-orb", "choice-band", "choice-specs". Auto-fetched if use_smogon_spreads=True.
            attacker_ability: Attacker's ability. Auto-detected if not specified.
            defender_ability: Defender's ability. Auto-detected if not specified.
            attacker_tera_type: Attacker's Tera type if Terastallized
            defender_tera_type: Defender's Tera type if Terastallized
            reflect: True if Reflect is active (halves physical damage)
            light_screen: True if Light Screen is active (halves special damage)
            helping_hand: True if Helping Hand was used (1.5x damage)
            commander_active: True if attacking Dondozo has Commander active (Tatsugiri inside). Doubles offensive stat.
            defender_commander_active: True if defending Dondozo has Commander active. Doubles defensive stat.
            beads_of_ruin: True if Chi-Yu's Beads of Ruin is active (lowers foe SpD to 0.75x)
            sword_of_ruin: True if Chien-Pao's Sword of Ruin is active (lowers foe Def to 0.75x)
            tablets_of_ruin: True if Wo-Chien's Tablets of Ruin is active (lowers foe Atk to 0.75x)
            vessel_of_ruin: True if Ting-Lu's Vessel of Ruin is active (lowers foe SpA to 0.75x)
            attacker_booster_energy: True if attacker used Booster Energy (activates Protosynthesis/Quark Drive)
            defender_booster_energy: True if defender used Booster Energy

        Returns:
            Damage range, percentages, and KO probability
        """
        try:
            # Fetch Pokemon data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name)

            # Track what spreads we used for the response
            attacker_spread_source = "custom"
            defender_spread_source = "custom"
            attacker_spread_info = None
            defender_spread_info = None

            # Auto-fetch Smogon spreads if enabled and values not provided
            if use_smogon_spreads:
                # Check if attacker needs spread data
                attacker_needs_spread = (
                    attacker_nature is None or
                    attacker_atk_evs is None or
                    attacker_spa_evs is None
                )
                if attacker_needs_spread:
                    atk_spread = await _get_common_spread(attacker_name)
                    if atk_spread:
                        attacker_spread_source = "smogon"
                        attacker_spread_info = atk_spread
                        if attacker_nature is None:
                            attacker_nature = atk_spread["nature"]
                        evs = atk_spread.get("evs", {})
                        if attacker_atk_evs is None:
                            attacker_atk_evs = evs.get("attack", 0)
                        if attacker_spa_evs is None:
                            attacker_spa_evs = evs.get("special_attack", 0)
                        # Also use common item/ability if not specified
                        if attacker_item is None and atk_spread.get("item"):
                            attacker_item = atk_spread["item"].lower().replace(" ", "-")
                        if attacker_ability is None and atk_spread.get("ability"):
                            attacker_ability = atk_spread["ability"].lower().replace(" ", "-")

                # Check if defender needs spread data
                defender_needs_spread = (
                    defender_nature is None or
                    defender_hp_evs is None or
                    defender_def_evs is None or
                    defender_spd_evs is None
                )
                if defender_needs_spread:
                    def_spread = await _get_common_spread(defender_name)
                    if def_spread:
                        defender_spread_source = "smogon"
                        defender_spread_info = def_spread
                        if defender_nature is None:
                            defender_nature = def_spread["nature"]
                        evs = def_spread.get("evs", {})
                        if defender_hp_evs is None:
                            defender_hp_evs = evs.get("hp", 0)
                        if defender_def_evs is None:
                            defender_def_evs = evs.get("defense", 0)
                        if defender_spd_evs is None:
                            defender_spd_evs = evs.get("special_defense", 0)
                        if defender_ability is None and def_spread.get("ability"):
                            defender_ability = def_spread["ability"].lower().replace(" ", "-")

            # Set defaults for any remaining None values
            attacker_nature = attacker_nature or "serious"
            attacker_atk_evs = attacker_atk_evs if attacker_atk_evs is not None else 0
            attacker_spa_evs = attacker_spa_evs if attacker_spa_evs is not None else 0
            defender_nature = defender_nature or "serious"
            defender_hp_evs = defender_hp_evs if defender_hp_evs is not None else 0
            defender_def_evs = defender_def_evs if defender_def_evs is not None else 0
            defender_spd_evs = defender_spd_evs if defender_spd_evs is not None else 0

            # Auto-fetch abilities if not specified
            if attacker_ability is None:
                atk_abilities = await pokeapi.get_pokemon_abilities(attacker_name)
                if atk_abilities:
                    # Use first (primary) ability as default
                    attacker_ability = atk_abilities[0].lower().replace(" ", "-")

            if defender_ability is None:
                def_abilities = await pokeapi.get_pokemon_abilities(defender_name)
                if def_abilities:
                    defender_ability = def_abilities[0].lower().replace(" ", "-")

            # Helper function to determine which stat Protosynthesis/Quark Drive boosts
            def get_paradox_boost_stat(base_stats, nature_enum, evs_dict) -> Optional[str]:
                """Determine which stat gets boosted by Protosynthesis/Quark Drive.
                Boosts the highest stat (excluding HP). Speed gets 1.5x, others get 1.3x."""
                from ..calc.stats import calculate_stat, calculate_speed
                from ..models.pokemon import get_nature_modifier

                stats = {
                    "attack": calculate_stat(
                        base_stats.attack, 31, evs_dict.get("attack", 0), 50,
                        get_nature_modifier(nature_enum, "attack")
                    ),
                    "defense": calculate_stat(
                        base_stats.defense, 31, evs_dict.get("defense", 0), 50,
                        get_nature_modifier(nature_enum, "defense")
                    ),
                    "special_attack": calculate_stat(
                        base_stats.special_attack, 31, evs_dict.get("special_attack", 0), 50,
                        get_nature_modifier(nature_enum, "special_attack")
                    ),
                    "special_defense": calculate_stat(
                        base_stats.special_defense, 31, evs_dict.get("special_defense", 0), 50,
                        get_nature_modifier(nature_enum, "special_defense")
                    ),
                    "speed": calculate_speed(
                        base_stats.speed, 31, evs_dict.get("speed", 0), 50,
                        get_nature_modifier(nature_enum, "speed")
                    ),
                }
                return max(stats, key=stats.get)

            # Parse natures
            try:
                atk_nature = Nature(attacker_nature.lower())
            except ValueError:
                suggestions = suggest_nature(attacker_nature)
                return invalid_nature_error(attacker_nature, suggestions if suggestions else [n.value for n in Nature])

            try:
                def_nature = Nature(defender_nature.lower())
            except ValueError:
                suggestions = suggest_nature(defender_nature)
                return invalid_nature_error(defender_nature, suggestions if suggestions else [n.value for n in Nature])

            # Create Pokemon builds
            attacker = PokemonBuild(
                name=attacker_name,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature,
                evs=EVSpread(
                    attack=attacker_atk_evs,
                    special_attack=attacker_spa_evs
                ),
                item=attacker_item,
                tera_type=attacker_tera_type
            )

            defender = PokemonBuild(
                name=defender_name,
                base_stats=def_base,
                types=def_types,
                nature=def_nature,
                evs=EVSpread(
                    hp=defender_hp_evs,
                    defense=defender_def_evs,
                    special_defense=defender_spd_evs
                ),
                tera_type=defender_tera_type
            )

            # Determine Protosynthesis/Quark Drive boost stats
            attacker_proto_boost = None
            attacker_quark_boost = None
            defender_proto_boost = None
            defender_quark_boost = None

            # Check if attacker has Protosynthesis and conditions are met
            if attacker_ability == "protosynthesis":
                if weather == "sun" or attacker_booster_energy:
                    attacker_proto_boost = get_paradox_boost_stat(
                        atk_base, atk_nature,
                        {"attack": attacker_atk_evs, "special_attack": attacker_spa_evs}
                    )

            # Check if attacker has Quark Drive and conditions are met
            if attacker_ability == "quark-drive":
                if terrain == "electric" or attacker_booster_energy:
                    attacker_quark_boost = get_paradox_boost_stat(
                        atk_base, atk_nature,
                        {"attack": attacker_atk_evs, "special_attack": attacker_spa_evs}
                    )

            # Check if defender has Protosynthesis and conditions are met
            if defender_ability == "protosynthesis":
                if weather == "sun" or defender_booster_energy:
                    defender_proto_boost = get_paradox_boost_stat(
                        def_base, def_nature,
                        {"hp": defender_hp_evs, "defense": defender_def_evs, "special_defense": defender_spd_evs}
                    )

            # Check if defender has Quark Drive and conditions are met
            if defender_ability == "quark-drive":
                if terrain == "electric" or defender_booster_energy:
                    defender_quark_boost = get_paradox_boost_stat(
                        def_base, def_nature,
                        {"hp": defender_hp_evs, "defense": defender_def_evs, "special_defense": defender_spd_evs}
                    )

            # Set up modifiers
            modifiers = DamageModifiers(
                is_doubles=True,
                multiple_targets=is_spread,
                weather=weather,
                terrain=terrain,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability,
                defender_ability=defender_ability,
                tera_type=attacker_tera_type,
                tera_active=attacker_tera_type is not None,
                defender_tera_type=defender_tera_type,
                defender_tera_active=defender_tera_type is not None,
                reflect_up=reflect,
                light_screen_up=light_screen,
                helping_hand=helping_hand,
                commander_active=commander_active,
                defender_commander_active=defender_commander_active,
                beads_of_ruin=beads_of_ruin,
                sword_of_ruin=sword_of_ruin,
                tablets_of_ruin=tablets_of_ruin,
                vessel_of_ruin=vessel_of_ruin,
                protosynthesis_boost=attacker_proto_boost,
                quark_drive_boost=attacker_quark_boost,
                defender_protosynthesis_boost=defender_proto_boost,
                defender_quark_drive_boost=defender_quark_boost
            )

            # Calculate damage
            result = calculate_damage(attacker, defender, move, modifiers)

            response = {
                "attacker": attacker_name,
                "attacker_ability": attacker_ability,
                "attacker_item": attacker_item,
                "defender": defender_name,
                "move": move_name,
                "move_type": move.type,
                "move_category": move.category.value,
                "base_power": move.power,
                "damage": {
                    "min": result.min_damage,
                    "max": result.max_damage,
                    "range": result.damage_range
                },
                "defender_hp": result.defender_hp,
                "ko_chance": result.ko_chance,
                "is_guaranteed_ohko": result.is_guaranteed_ohko,
                "is_possible_ohko": result.is_possible_ohko,
                "all_rolls": result.rolls,
                "modifiers": result.details.get("modifiers_applied", []),
                "type_effectiveness": result.details.get("type_effectiveness", 1.0)
            }

            # Add spread info to response so user knows what was used
            if attacker_spread_source == "smogon" and attacker_spread_info:
                response["attacker_spread"] = {
                    "source": "smogon_usage",
                    "nature": attacker_nature,
                    "evs": attacker_spread_info.get("evs", {}),
                    "usage_percent": attacker_spread_info.get("usage", 0)
                }
            if defender_spread_source == "smogon" and defender_spread_info:
                response["defender_spread"] = {
                    "source": "smogon_usage",
                    "nature": defender_nature,
                    "evs": defender_spread_info.get("evs", {}),
                    "usage_percent": defender_spread_info.get("usage", 0)
                }

            # Add ability effect notes
            ability_notes = []

            if commander_active:
                response["commander_active"] = True
                ability_notes.append("Attacker's Commander: doubles offensive stat (Atk or SpA)")

            if defender_commander_active:
                response["defender_commander_active"] = True
                ability_notes.append("Defender's Commander: doubles defensive stat (Def or SpD)")

            if beads_of_ruin:
                ability_notes.append("Beads of Ruin (Chi-Yu): Defender's SpD reduced to 0.75x")

            if sword_of_ruin:
                ability_notes.append("Sword of Ruin (Chien-Pao): Defender's Def reduced to 0.75x")

            if tablets_of_ruin:
                ability_notes.append("Tablets of Ruin (Wo-Chien): Attacker's Atk reduced to 0.75x")

            if vessel_of_ruin:
                ability_notes.append("Vessel of Ruin (Ting-Lu): Attacker's SpA reduced to 0.75x")

            if attacker_proto_boost:
                ability_notes.append(f"Protosynthesis: Attacker's {attacker_proto_boost.replace('_', ' ').title()} boosted (1.3x, 1.5x for Speed)")

            if attacker_quark_boost:
                ability_notes.append(f"Quark Drive: Attacker's {attacker_quark_boost.replace('_', ' ').title()} boosted (1.3x, 1.5x for Speed)")

            if defender_proto_boost:
                ability_notes.append(f"Protosynthesis: Defender's {defender_proto_boost.replace('_', ' ').title()} boosted (1.3x, 1.5x for Speed)")

            if defender_quark_boost:
                ability_notes.append(f"Quark Drive: Defender's {defender_quark_boost.replace('_', ' ').title()} boosted (1.3x, 1.5x for Speed)")

            if ability_notes:
                response["ability_effects"] = ability_notes

            # Add MCP-UI resource for interactive damage display
            try:
                ui_resource = create_damage_calc_resource(
                    attacker=attacker_name,
                    defender=defender_name,
                    move=move_name,
                    damage_min=result.damage_range[0],
                    damage_max=result.damage_range[1],
                    ko_chance=result.ko_chance,
                    type_effectiveness=result.details.get("type_effectiveness", 1.0),
                    attacker_item=attacker_item,
                    defender_item=None,
                    move_type=move.type,
                    notes=ability_notes if ability_notes else None,
                )
                response = add_ui_metadata(response, ui_resource)
            except Exception:
                # UI is optional - continue without it if there's an issue
                pass

            return response

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                # Try to identify which Pokemon wasn't found
                suggestions = suggest_pokemon_name(attacker_name) or suggest_pokemon_name(defender_name)
                return pokemon_not_found_error(
                    f"{attacker_name} or {defender_name}",
                    suggestions if suggestions else None
                )
            return api_error("PokeAPI", str(e), is_retryable=True)

    @mcp.tool()
    async def find_ko_evs(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        attacker_nature: str = "modest",
        defender_nature: str = "calm",
        defender_hp_evs: int = 252,
        defender_def_evs: int = 0,
        target_ko_chance: float = 100.0
    ) -> dict:
        """
        Find minimum offensive EVs needed to achieve a certain KO probability.

        Args:
            attacker_name: Attacking Pokemon
            defender_name: Defending Pokemon
            move_name: Move being used
            attacker_nature: Attacker's nature (use +Atk or +SpA for best results)
            defender_nature: Defender's nature
            defender_hp_evs: Defender's HP EVs (typically 252 for max bulk)
            defender_def_evs: Defender's Def/SpD EVs
            target_ko_chance: Target KO probability (100 = guaranteed OHKO)

        Returns:
            Required EVs and resulting damage calculation
        """
        try:
            # Fetch data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name)

            # Parse natures
            atk_nature = Nature(attacker_nature.lower())
            def_nature = Nature(defender_nature.lower())

            # Create builds
            attacker = PokemonBuild(
                name=attacker_name,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature,
                evs=EVSpread()
            )

            defender = PokemonBuild(
                name=defender_name,
                base_stats=def_base,
                types=def_types,
                nature=def_nature,
                evs=EVSpread(
                    hp=defender_hp_evs,
                    defense=defender_def_evs if move.category.value == "physical" else 0,
                    special_defense=defender_def_evs if move.category.value == "special" else 0
                )
            )

            result = calculate_ko_threshold(
                attacker, defender, move,
                target_ko_chance=target_ko_chance
            )

            if result is None:
                return {
                    "attacker": attacker_name,
                    "defender": defender_name,
                    "move": move_name,
                    "achievable": False,
                    "message": f"Cannot achieve {target_ko_chance}% OHKO with 252 EVs. Consider items, Tera, or different move."
                }

            return {
                "attacker": attacker_name,
                "defender": defender_name,
                "move": move_name,
                "achievable": True,
                "evs_needed": result["evs_needed"],
                "stat": result["stat_name"],
                "ko_chance": f"{result['ko_chance']:.1f}%",
                "damage_range": result["damage_range"]
            }

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = suggest_pokemon_name(attacker_name) or suggest_pokemon_name(defender_name)
                return pokemon_not_found_error(
                    f"{attacker_name} or {defender_name}",
                    suggestions if suggestions else None
                )
            return api_error("PokeAPI", str(e), is_retryable=True)

    @mcp.tool()
    async def find_bulk_evs(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        attacker_nature: str = "modest",
        attacker_evs: int = 252,
        defender_nature: str = "calm",
        target_survival_chance: float = 100.0
    ) -> dict:
        """
        Find minimum HP/Def EVs needed to survive an attack.

        Args:
            attacker_name: Attacking Pokemon
            defender_name: Defending Pokemon (your Pokemon)
            move_name: Move to survive
            attacker_nature: Attacker's nature
            attacker_evs: Attacker's offensive EVs
            defender_nature: Your nature
            target_survival_chance: Target survival % (100 = always survive)

        Returns:
            Required HP/Def EVs and resulting calculation
        """
        try:
            # Fetch data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name)

            # Parse natures
            atk_nature = Nature(attacker_nature.lower())
            def_nature = Nature(defender_nature.lower())

            # Create builds
            is_physical = move.category.value == "physical"

            attacker = PokemonBuild(
                name=attacker_name,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature,
                evs=EVSpread(
                    attack=attacker_evs if is_physical else 0,
                    special_attack=0 if is_physical else attacker_evs
                )
            )

            defender = PokemonBuild(
                name=defender_name,
                base_stats=def_base,
                types=def_types,
                nature=def_nature,
                evs=EVSpread()
            )

            result = calculate_bulk_threshold(
                attacker, defender, move,
                target_survival_chance=target_survival_chance
            )

            if result is None:
                return {
                    "attacker": attacker_name,
                    "defender": defender_name,
                    "move": move_name,
                    "achievable": False,
                    "message": f"Cannot survive this attack with max investment. Consider items, Tera typing, or screens."
                }

            return {
                "attacker": attacker_name,
                "defender": defender_name,
                "move": move_name,
                "achievable": True,
                "hp_evs_needed": result["hp_evs"],
                "def_evs_needed": result["def_evs"],
                "def_stat": result["def_stat_name"],
                "survival_chance": f"{result['survival_chance']:.1f}%",
                "damage_range": result["damage_range"]
            }

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = suggest_pokemon_name(attacker_name) or suggest_pokemon_name(defender_name)
                return pokemon_not_found_error(
                    f"{attacker_name} or {defender_name}",
                    suggestions if suggestions else None
                )
            return api_error("PokeAPI", str(e), is_retryable=True)
