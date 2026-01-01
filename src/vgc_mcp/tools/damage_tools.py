"""MCP tools for damage calculations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..api.pokeapi import PokeAPIClient
from ..calc.damage import calculate_damage, calculate_ko_threshold, calculate_bulk_threshold
from ..calc.modifiers import DamageModifiers
from ..models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread
from ..utils.errors import error_response, ErrorCodes, pokemon_not_found_error, invalid_nature_error, api_error
from ..utils.fuzzy import suggest_pokemon_name, suggest_nature


def register_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register damage calculation tools with the MCP server."""

    @mcp.tool()
    async def calculate_damage_output(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        attacker_nature: str = "serious",
        attacker_atk_evs: int = 0,
        attacker_spa_evs: int = 0,
        defender_nature: str = "serious",
        defender_hp_evs: int = 0,
        defender_def_evs: int = 0,
        defender_spd_evs: int = 0,
        is_spread: bool = False,
        weather: Optional[str] = None,
        attacker_item: Optional[str] = None,
        attacker_ability: Optional[str] = None,
        attacker_tera_type: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        reflect: bool = False,
        light_screen: bool = False,
        helping_hand: bool = False,
        commander_active: bool = False,
        defender_commander_active: bool = False
    ) -> dict:
        """
        Calculate damage from one Pokemon to another.

        Args:
            attacker_name: Attacking Pokemon's name
            defender_name: Defending Pokemon's name
            move_name: Name of the move being used
            attacker_nature: Attacker's nature (default: serious)
            attacker_atk_evs: Attacker's Attack EVs (for physical moves)
            attacker_spa_evs: Attacker's Sp. Atk EVs (for special moves)
            defender_nature: Defender's nature
            defender_hp_evs: Defender's HP EVs
            defender_def_evs: Defender's Defense EVs
            defender_spd_evs: Defender's Sp. Def EVs
            is_spread: True if move is hitting multiple targets (0.75x damage)
            weather: "sun", "rain", "sand", or "snow" (affects Fire/Water moves)
            attacker_item: Item like "life-orb", "choice-band", "choice-specs"
            attacker_ability: Attacker's ability (e.g., "sheer-force", "adaptability"). Auto-detected if not specified.
            attacker_tera_type: Attacker's Tera type if Terastallized
            defender_tera_type: Defender's Tera type if Terastallized
            reflect: True if Reflect is active (halves physical damage)
            light_screen: True if Light Screen is active (halves special damage)
            helping_hand: True if Helping Hand was used (1.5x damage)
            commander_active: True if attacking Dondozo has Commander active (Tatsugiri inside). Doubles offensive stat.
            defender_commander_active: True if defending Dondozo has Commander active. Doubles defensive stat.

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

            # Auto-fetch ability if not specified
            if attacker_ability is None:
                atk_abilities = await pokeapi.get_pokemon_abilities(attacker_name)
                if atk_abilities:
                    # Use first (primary) ability as default
                    attacker_ability = atk_abilities[0].lower().replace(" ", "-")

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

            # Set up modifiers
            modifiers = DamageModifiers(
                is_doubles=True,
                multiple_targets=is_spread,
                weather=weather,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability,
                tera_type=attacker_tera_type,
                tera_active=attacker_tera_type is not None,
                defender_tera_type=defender_tera_type,
                defender_tera_active=defender_tera_type is not None,
                reflect_up=reflect,
                light_screen_up=light_screen,
                helping_hand=helping_hand,
                commander_active=commander_active,
                defender_commander_active=defender_commander_active
            )

            # Calculate damage
            result = calculate_damage(attacker, defender, move, modifiers)

            response = {
                "attacker": attacker_name,
                "attacker_ability": attacker_ability,
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

            if commander_active:
                response["commander_active"] = True
                response["note"] = "Attacker's Commander: doubles offensive stat (Atk or SpA)"

            if defender_commander_active:
                response["defender_commander_active"] = True
                response["defender_note"] = "Defender's Commander: doubles defensive stat (Def or SpD)"

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
