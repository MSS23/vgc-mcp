"""MCP tools for damage calculations."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import calculate_damage, calculate_ko_threshold, calculate_bulk_threshold
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, IVSpread, get_nature_modifier
from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp
from vgc_mcp_core.utils.errors import error_response, ErrorCodes, pokemon_not_found_error, invalid_nature_error, api_error
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name, suggest_nature
from vgc_mcp_core.utils.synergies import get_synergy_ability

# Note: MCP-UI is only available in vgc-mcp-lite, not the full server
HAS_UI = False


# Module-level Smogon client reference (set during registration)
_smogon_client: Optional[SmogonStatsClient] = None


def _normalize_smogon_name(name: str) -> str:
    """Normalize Smogon names to hyphenated format.

    Smogon uses concatenated names: 'lifeorb', 'sheerforce'
    Damage calc expects hyphenated: 'life-orb', 'sheer-force'
    """
    # Common mappings from Smogon format to hyphenated
    smogon_to_hyphenated = {
        # Items
        "lifeorb": "life-orb",
        "choiceband": "choice-band",
        "choicespecs": "choice-specs",
        "choicescarf": "choice-scarf",
        "assaultvest": "assault-vest",
        "focussash": "focus-sash",
        "clearamulet": "clear-amulet",
        "safetygoggles": "safety-goggles",
        "expertbelt": "expert-belt",
        "rockyhelmet": "rocky-helmet",
        "sitrusberry": "sitrus-berry",
        "lumberry": "lum-berry",
        "boosterenergy": "booster-energy",
        "hearthflamemask": "hearthflame-mask",
        "wellspringmask": "wellspring-mask",
        "cornerstonemask": "cornerstone-mask",
        "eviolite": "eviolite",
        "leftovers": "leftovers",
        "covertcloak": "covert-cloak",
        "mirrorherb": "mirror-herb",
        "loadeddice": "loaded-dice",
        "punchingglove": "punching-glove",
        "throatspray": "throat-spray",
        "weaknesspolicy": "weakness-policy",
        # Resistance berries
        "occaberry": "occa-berry",
        "passhoberry": "passho-berry",
        "wacanberry": "wacan-berry",
        "rindoberry": "rindo-berry",
        "yacheberry": "yache-berry",
        "chopleberry": "chople-berry",
        "kebiaberry": "kebia-berry",
        "shucaberry": "shuca-berry",
        "cobaberry": "coba-berry",
        "payapaberry": "payapa-berry",
        "tangaberry": "tanga-berry",
        "chartiberry": "charti-berry",
        "kasibberry": "kasib-berry",
        "habanberry": "haban-berry",
        "colburberry": "colbur-berry",
        "babiriberry": "babiri-berry",
        "roseliberry": "roseli-berry",
        # Abilities - offensive
        "sheerforce": "sheer-force",
        "sandforce": "sand-force",
        "hugepower": "huge-power",
        "purepower": "pure-power",
        "toughclaws": "tough-claws",
        "ironfist": "iron-fist",
        "gorillatactics": "gorilla-tactics",
        "technician": "technician",
        "adaptability": "adaptability",
        # Abilities - defensive
        "multiscale": "multiscale",
        "shadowshield": "shadow-shield",
        "icescales": "ice-scales",
        "solidrock": "solid-rock",
        "filter": "filter",
        "prismarmor": "prism-armor",
        "fluffy": "fluffy",
        "thickfat": "thick-fat",
        "furcoat": "fur-coat",
        "waterbubble": "water-bubble",
        "heatproof": "heatproof",
        # Abilities - Ruin
        "swordofruin": "sword-of-ruin",
        "beadsofruin": "beads-of-ruin",
        "tabletsofruin": "tablets-of-ruin",
        "vesselofruin": "vessel-of-ruin",
        # Abilities - Paradox
        "quarkdrive": "quark-drive",
        "protosynthesis": "protosynthesis",
        # Abilities - other common
        "friendguard": "friend-guard",
        "intimidate": "intimidate",
        "moldbreaker": "mold-breaker",
        "teravolt": "teravolt",
        "turboblaze": "turboblaze",
        "clearbody": "clear-body",
        "innerfocus": "inner-focus",
        "regenerator": "regenerator",
        "magicguard": "magic-guard",
        "magicbounce": "magic-bounce",
        "prankster": "prankster",
        "pixilate": "pixilate",
        "refrigerate": "refrigerate",
        "galvanize": "galvanize",
        "aerilate": "aerilate",
    }

    name_lower = name.lower().replace(" ", "-")
    return smogon_to_hyphenated.get(name_lower, name_lower)


async def _get_common_spreads(pokemon_name: str, limit: int = 3) -> list[dict]:
    """Fetch the top common spreads for a Pokemon from Smogon usage stats.

    Args:
        pokemon_name: Name of the Pokemon
        limit: Number of top spreads to return (default 3)

    Returns:
        List of dicts with 'nature', 'evs', 'item', 'ability', 'usage' keys.
        Returns empty list if not found.
    """
    if _smogon_client is None:
        return []
    try:
        usage = await _smogon_client.get_pokemon_usage(pokemon_name)
        if usage and usage.get("spreads"):
            spreads = usage["spreads"][:limit]
            # Get items and abilities with their usage percentages
            items = usage.get("items", {})
            abilities = usage.get("abilities", {})
            top_item = list(items.keys())[0] if items else None
            top_item_usage = list(items.values())[0] if items else 0

            # Get ability based on item synergy (e.g., Life Orb -> Sheer Force)
            top_ability, top_ability_usage = get_synergy_ability(top_item, abilities)

            result = []
            for i, spread in enumerate(spreads):
                result.append({
                    "rank": i + 1,
                    "nature": spread.get("nature", "Serious"),
                    "evs": spread.get("evs", {}),
                    "usage": spread.get("usage", 0),
                    "item": top_item,
                    "item_usage": top_item_usage,
                    "ability": top_ability,
                    "ability_usage": top_ability_usage,
                })
            return result
    except Exception:
        pass
    return []


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Fetch the most common spread for a Pokemon from Smogon usage stats.

    Returns:
        dict with 'nature' and 'evs' keys, or None if not found
    """
    spreads = await _get_common_spreads(pokemon_name, limit=1)
    return spreads[0] if spreads else None


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
        num_defender_spreads: int = 3,
        is_spread: bool = False,
        weather: Optional[str] = None,
        terrain: Optional[str] = None,
        attacker_item: Optional[str] = None,
        defender_item: Optional[str] = None,
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
        defender_booster_energy: bool = False,
        attacker_attack_stage: int = 0,
        attacker_special_attack_stage: int = 0,
        defender_defense_stage: int = 0,
        defender_special_defense_stage: int = 0,
        aurora_veil: bool = False,
        friend_guard: bool = False
    ) -> dict:
        """
        Calculate damage from one Pokemon to another.

        By default, uses the most common Smogon VGC spreads for both Pokemon when
        nature/EVs are not specified. Calculates against the top 3 defender spreads
        to show damage variance across common builds.

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
            use_smogon_spreads: If True (default), auto-fetch common spreads from Smogon usage data
            num_defender_spreads: Number of top defender spreads to calculate against (default 3). Set to 1 for single spread.
            is_spread: True if move is hitting multiple targets (0.75x damage)
            weather: "sun", "rain", "sand", or "snow" (affects Fire/Water moves)
            terrain: "electric", "grassy", "psychic", or "misty" (affects damage)
            attacker_item: Item like "life-orb", "choice-band". Auto-fetched if use_smogon_spreads=True.
            defender_item: Defender's item like "assault-vest", "sitrus-berry". Auto-fetched if use_smogon_spreads=True.
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
            attacker_attack_stage: Attacker's Attack stage (-6 to +6). Use -1 for Intimidate.
            attacker_special_attack_stage: Attacker's Sp. Atk stage (-6 to +6).
            defender_defense_stage: Defender's Defense stage (-6 to +6).
            defender_special_defense_stage: Defender's Sp. Def stage (-6 to +6).
            aurora_veil: True if Aurora Veil is active (halves both physical and special damage)
            friend_guard: True if ally has Friend Guard ability (reduces damage to 0.75x)

        Returns:
            Damage calculations against top defender spreads with KO probabilities and items
        """
        try:
            # Auto-assign signature items for Pokemon that require them
            if attacker_item is None:
                from vgc_mcp_core.calc.items import get_signature_item
                sig_item = get_signature_item(attacker_name)
                if sig_item:
                    attacker_item = sig_item

            # Auto-assign fixed Tera types (Ogerpon forms, Terapagos)
            from vgc_mcp_core.calc.items import get_fixed_tera_type
            if attacker_tera_type is not None:
                fixed_tera = get_fixed_tera_type(attacker_name)
                if fixed_tera and attacker_tera_type.lower() != fixed_tera.lower():
                    attacker_tera_type = fixed_tera
            if defender_tera_type is not None:
                fixed_tera = get_fixed_tera_type(defender_name)
                if fixed_tera and defender_tera_type.lower() != fixed_tera.lower():
                    defender_tera_type = fixed_tera

            # Fetch Pokemon data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            # Pass attacker_name for form-dependent move types (e.g., Ivy Cudgel)
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            # Auto-detect Ogerpon mask from Ivy Cudgel type
            # If user passes "ogerpon" with Fire-type Ivy Cudgel, assign Hearthflame Mask
            normalized_attacker = attacker_name.lower().replace(" ", "-")
            if normalized_attacker.startswith("ogerpon") and move.name.lower().replace(" ", "-") == "ivy-cudgel":
                mask_from_type = {
                    "Fire": "hearthflame-mask",
                    "Water": "wellspring-mask",
                    "Rock": "cornerstone-mask",
                    "Grass": "teal-mask",
                }
                inferred_mask = mask_from_type.get(move.type)
                if inferred_mask and attacker_item is None:
                    attacker_item = inferred_mask

            # Track what spreads we used for the response
            attacker_spread_source = "custom"
            defender_spread_source = "custom"
            attacker_spread_info = None
            defender_spread_info = None
            defender_spreads_list = []  # For multi-spread calculations

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
                            attacker_item = _normalize_smogon_name(atk_spread["item"])
                        if attacker_ability is None and atk_spread.get("ability"):
                            attacker_ability = _normalize_smogon_name(atk_spread["ability"])

                # Check if defender needs spread data - fetch multiple spreads for comparison
                defender_needs_spread = (
                    defender_nature is None or
                    defender_hp_evs is None or
                    defender_def_evs is None or
                    defender_spd_evs is None
                )
                if defender_needs_spread:
                    defender_spreads_list = await _get_common_spreads(defender_name, limit=num_defender_spreads)
                    if defender_spreads_list:
                        defender_spread_source = "smogon"
                        # Use first spread as the primary for backwards compatibility
                        def_spread = defender_spreads_list[0]
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
                            defender_ability = _normalize_smogon_name(def_spread["ability"])
                        # Also get defender item from Smogon if not specified
                        if defender_item is None and def_spread.get("item"):
                            defender_item = _normalize_smogon_name(def_spread["item"])

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

            # Auto-detect Ruinous abilities from attacker
            # These abilities affect all OTHER Pokemon on the field
            if attacker_ability:
                ability_lower = attacker_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_lower == "sword-of-ruin" and not sword_of_ruin:
                    sword_of_ruin = True
                elif ability_lower == "beads-of-ruin" and not beads_of_ruin:
                    beads_of_ruin = True
                # Note: Tablets/Vessel from attacker affect attacker's own stats,
                # but in a damage calc the attacker is calculating damage TO defender,
                # so we don't auto-apply these (they'd reduce attacker's own offense)

            # Auto-detect Ruinous abilities from defender that affect attacker
            if defender_ability:
                ability_lower = defender_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_lower == "tablets-of-ruin" and not tablets_of_ruin:
                    tablets_of_ruin = True
                elif ability_lower == "vessel-of-ruin" and not vessel_of_ruin:
                    vessel_of_ruin = True
                # Note: Sword/Beads from defender affect defender's own stats,
                # so we don't auto-apply these (they'd reduce defender's own defense)

            # Helper function to determine which stat Protosynthesis/Quark Drive boosts
            def get_paradox_boost_stat(base_stats, nature_enum, evs_dict) -> Optional[str]:
                """Determine which stat gets boosted by Protosynthesis/Quark Drive.
                Boosts the highest stat (excluding HP). Speed gets 1.5x, others get 1.3x."""
                from vgc_mcp_core.calc.stats import calculate_stat, calculate_speed
                from vgc_mcp_core.models.pokemon import get_nature_modifier

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
                defender_item=defender_item,
                attacker_ability=attacker_ability,
                defender_ability=defender_ability,
                tera_type=attacker_tera_type,
                tera_active=attacker_tera_type is not None,
                defender_tera_type=defender_tera_type,
                defender_tera_active=defender_tera_type is not None,
                reflect_up=reflect,
                light_screen_up=light_screen,
                aurora_veil_up=aurora_veil,
                helping_hand=helping_hand,
                friend_guard=friend_guard,
                commander_active=commander_active,
                defender_commander_active=defender_commander_active,
                beads_of_ruin=beads_of_ruin,
                sword_of_ruin=sword_of_ruin,
                tablets_of_ruin=tablets_of_ruin,
                vessel_of_ruin=vessel_of_ruin,
                protosynthesis_boost=attacker_proto_boost,
                quark_drive_boost=attacker_quark_boost,
                defender_protosynthesis_boost=defender_proto_boost,
                defender_quark_drive_boost=defender_quark_boost,
                attack_stage=attacker_attack_stage,
                special_attack_stage=attacker_special_attack_stage,
                defense_stage=defender_defense_stage,
                special_defense_stage=defender_special_defense_stage
            )

            # Calculate damage against multiple defender spreads if available
            results_by_spread = []

            if len(defender_spreads_list) > 1:
                # Multi-spread mode: calculate against each defender spread
                for spread_data in defender_spreads_list:
                    spread_nature = spread_data["nature"]
                    spread_evs = spread_data.get("evs", {})
                    spread_item = _normalize_smogon_name(spread_data["item"]) if spread_data.get("item") else defender_item
                    spread_ability = _normalize_smogon_name(spread_data["ability"]) if spread_data.get("ability") else defender_ability

                    # Parse the spread's nature
                    try:
                        spread_nature_enum = Nature(spread_nature.lower())
                    except ValueError:
                        spread_nature_enum = def_nature

                    # Create defender build for this spread
                    spread_defender = PokemonBuild(
                        name=defender_name,
                        base_stats=def_base,
                        types=def_types,
                        nature=spread_nature_enum,
                        evs=EVSpread(
                            hp=spread_evs.get("hp", 0),
                            defense=spread_evs.get("defense", 0),
                            special_defense=spread_evs.get("special_defense", 0)
                        ),
                        item=spread_item,
                        tera_type=defender_tera_type
                    )

                    # Update modifiers with this spread's item and ability
                    spread_modifiers = DamageModifiers(
                        is_doubles=True,
                        multiple_targets=is_spread,
                        weather=weather,
                        terrain=terrain,
                        attacker_item=attacker_item,
                        defender_item=spread_item,
                        attacker_ability=attacker_ability,
                        defender_ability=spread_ability,
                        tera_type=attacker_tera_type,
                        tera_active=attacker_tera_type is not None,
                        defender_tera_type=defender_tera_type,
                        defender_tera_active=defender_tera_type is not None,
                        reflect_up=reflect,
                        light_screen_up=light_screen,
                        aurora_veil_up=aurora_veil,
                        helping_hand=helping_hand,
                        friend_guard=friend_guard,
                        commander_active=commander_active,
                        defender_commander_active=defender_commander_active,
                        beads_of_ruin=beads_of_ruin,
                        sword_of_ruin=sword_of_ruin,
                        tablets_of_ruin=tablets_of_ruin,
                        vessel_of_ruin=vessel_of_ruin,
                        protosynthesis_boost=attacker_proto_boost,
                        quark_drive_boost=attacker_quark_boost,
                        defender_protosynthesis_boost=defender_proto_boost,
                        defender_quark_drive_boost=defender_quark_boost,
                        attack_stage=attacker_attack_stage,
                        special_attack_stage=attacker_special_attack_stage,
                        defense_stage=defender_defense_stage,
                        special_defense_stage=defender_special_defense_stage
                    )

                    # Calculate damage for this spread
                    spread_result = calculate_damage(attacker, spread_defender, move, spread_modifiers)

                    # Format EV string
                    ev_str = f"{spread_evs.get('hp', 0)}/{spread_evs.get('attack', 0)}/{spread_evs.get('defense', 0)}/{spread_evs.get('special_attack', 0)}/{spread_evs.get('special_defense', 0)}/{spread_evs.get('speed', 0)}"

                    results_by_spread.append({
                        "spread_rank": spread_data["rank"],
                        "nature": spread_nature,
                        "evs": spread_evs,
                        "ev_string": f"{spread_nature} {ev_str}",
                        "usage_percent": spread_data.get("usage", 0),
                        "item": spread_item,
                        "item_usage_percent": spread_data.get("item_usage", 0),
                        "ability": spread_ability,
                        "damage_range": spread_result.damage_range,
                        "damage_min": spread_result.min_damage,
                        "damage_max": spread_result.max_damage,
                        "defender_hp": spread_result.defender_hp,
                        "ko_chance": spread_result.ko_chance,
                        "is_guaranteed_ohko": spread_result.is_guaranteed_ohko,
                        "is_possible_ohko": spread_result.is_possible_ohko,
                    })

            # Calculate primary result (first spread or custom)
            result = calculate_damage(attacker, defender, move, modifiers)

            # Build response
            response = {
                "attacker": attacker_name,
                "attacker_ability": attacker_ability,
                "attacker_item": attacker_item,
                "attacker_tera": attacker_tera_type,
                "attacker_tera_active": attacker_tera_type is not None,
                "defender": defender_name,
                "defender_ability": defender_ability,
                "defender_item": defender_item,
                "defender_tera": defender_tera_type,
                "defender_tera_active": defender_tera_type is not None,
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

            # Add multi-spread results if available
            if results_by_spread:
                response["results_by_spread"] = results_by_spread
                # Add summary
                ohko_count = sum(1 for r in results_by_spread if r["is_guaranteed_ohko"])
                possible_ohko_count = sum(1 for r in results_by_spread if r["is_possible_ohko"])
                total_spreads = len(results_by_spread)
                response["spread_summary"] = {
                    "total_spreads": total_spreads,
                    "guaranteed_ohko_count": ohko_count,
                    "possible_ohko_count": possible_ohko_count,
                    "verdict": f"Guaranteed OHKO on {ohko_count}/{total_spreads} spreads" if ohko_count > 0 else f"Possible OHKO on {possible_ohko_count}/{total_spreads} spreads" if possible_ohko_count > 0 else f"0/{total_spreads} OHKO"
                }

            # Always show attacker spread info
            if attacker_spread_source == "smogon" and attacker_spread_info:
                response["attacker_spread"] = {
                    "source": "smogon_usage",
                    "nature": attacker_nature,
                    "evs": attacker_spread_info.get("evs", {}),
                    "item": attacker_item,
                    "ability": attacker_ability,
                    "tera_type": attacker_tera_type,
                    "tera_active": attacker_tera_type is not None,
                    "usage_percent": attacker_spread_info.get("usage", 0)
                }

            # Always show defender spread info (even for custom spreads)
            response["defender_spread"] = {
                "source": defender_spread_source,
                "nature": defender_nature,
                "evs": {
                    "hp": defender_hp_evs,
                    "defense": defender_def_evs,
                    "special_defense": defender_spd_evs
                },
                "item": defender_item,
                "ability": defender_ability,
                "tera_type": defender_tera_type,
                "tera_active": defender_tera_type is not None,
                "usage_percent": defender_spread_info.get("usage", 0) if defender_spread_info else None
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

            # Build condensed summary with all key info at a glance
            def _format_evs(evs_dict: dict) -> str:
                """Format EVs as HP/Atk/Def/SpA/SpD/Spe string."""
                return f"{evs_dict.get('hp', 0)}/{evs_dict.get('attack', 0)}/{evs_dict.get('defense', 0)}/{evs_dict.get('special_attack', 0)}/{evs_dict.get('special_defense', 0)}/{evs_dict.get('speed', 0)}"

            atk_evs_dict = attacker_spread_info.get("evs", {}) if attacker_spread_info else {"attack": attacker_atk_evs, "special_attack": attacker_spa_evs}
            def_evs_dict = {"hp": defender_hp_evs, "defense": defender_def_evs, "special_defense": defender_spd_evs}

            atk_tera_str = f" [Tera {attacker_tera_type.title()}]" if attacker_tera_type else ""
            def_tera_str = f" [Tera {defender_tera_type.title()}]" if defender_tera_type else ""

            response["condensed_summary"] = {
                "attacker_line": f"{attacker_name} ({attacker_nature.title()} {_format_evs(atk_evs_dict)}) @ {attacker_item or 'No item'} [{attacker_ability}]{atk_tera_str}",
                "defender_line": f"{defender_name} ({defender_nature.title()} {_format_evs(def_evs_dict)}) @ {defender_item or 'No item'} [{defender_ability}]{def_tera_str}",
                "move_line": f"{move_name} ({move.power} BP, {move.type.title()}, {move.category.value.title()})",
            }

            # Build summary table for clear display
            hp_remaining_min = max(0, result.defender_hp - result.max_damage)
            hp_remaining_max = max(0, result.defender_hp - result.min_damage)
            hp_remain_min_pct = round(hp_remaining_min / result.defender_hp * 100, 1)
            hp_remain_max_pct = round(hp_remaining_max / result.defender_hp * 100, 1)

            min_pct = round(result.min_damage / result.defender_hp * 100, 1)
            max_pct = round(result.max_damage / result.defender_hp * 100, 1)

            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Attacker         | {attacker_name} ({move_name})              |",
                f"| Defender         | {defender_name}                            |",
                f"| Damage Range     | {result.min_damage}-{result.max_damage} ({min_pct}-{max_pct}%) |",
                f"| HP Remaining     | {hp_remaining_min}-{hp_remaining_max} ({hp_remain_min_pct}-{hp_remain_max_pct}%) |",
                f"| KO Verdict       | {result.ko_chance}                         |",
            ]
            if attacker_item:
                table_lines.append(f"| Attacker Item    | {attacker_item}                            |")
            if defender_item:
                table_lines.append(f"| Defender Item    | {defender_item}                            |")

            response["summary_table"] = "\n".join(table_lines)

            # Build descriptive spread strings for analysis (Showdown format)
            is_physical = move.category.value == "physical"
            relevant_atk_evs = attacker_atk_evs if is_physical else attacker_spa_evs
            stat_name = "Atk" if is_physical else "SpA"

            # Get nature modifiers for attacker
            atk_nature_mod = get_nature_modifier(atk_nature, "attack")
            spa_nature_mod = get_nature_modifier(atk_nature, "special_attack")

            # Build attacker spread string (e.g., "252+ Atk Mystic Water")
            nature_boost = "+" if (is_physical and atk_nature_mod > 1.0) or (not is_physical and spa_nature_mod > 1.0) else ""
            nature_penalty = "-" if (is_physical and atk_nature_mod < 1.0) or (not is_physical and spa_nature_mod < 1.0) else ""
            nature_indicator = nature_boost or nature_penalty
            item_str = f" {attacker_item.replace('-', ' ').title()}" if attacker_item else ""
            attacker_spread_str = f"{relevant_atk_evs}{nature_indicator} {stat_name}{item_str} {attacker_name}"

            # Build defender spread string (e.g., "Impish 132 HP / 196 Def")
            relevant_def_evs = defender_def_evs if is_physical else defender_spd_evs
            def_stat_name = "Def" if is_physical else "SpD"
            defender_spread_str = f"{defender_nature.title()} {defender_hp_evs} HP / {relevant_def_evs} {def_stat_name} {defender_name}"

            response["analysis"] = f"{attacker_spread_str}'s {move_name} vs {defender_spread_str}: {min_pct}-{max_pct}% ({hp_remain_min_pct}-{hp_remain_max_pct}% remaining). {result.ko_chance}."

            # Add MCP-UI resource for interactive damage display with editable spreads
            # (only available in vgc-mcp-lite)
            if HAS_UI:
                try:
                    # Build EV dicts for the interactive UI
                    attacker_evs_dict = {
                        "hp": attacker_evs.hp,
                        "attack": attacker_evs.attack,
                        "defense": attacker_evs.defense,
                        "special_attack": attacker_evs.special_attack,
                        "special_defense": attacker_evs.special_defense,
                        "speed": attacker_evs.speed,
                    }
                    defender_evs_dict = {
                        "hp": defender_evs.hp,
                        "attack": defender_evs.attack,
                        "defense": defender_evs.defense,
                        "special_attack": defender_evs.special_attack,
                        "special_defense": defender_evs.special_defense,
                        "speed": defender_evs.speed,
                    }

                    # Build base stats dicts
                    attacker_base_stats_dict = {
                        "hp": atk_base.hp,
                        "attack": atk_base.attack,
                        "defense": atk_base.defense,
                        "special_attack": atk_base.special_attack,
                        "special_defense": atk_base.special_defense,
                        "speed": atk_base.speed,
                    }
                    defender_base_stats_dict = {
                        "hp": def_base.hp,
                        "attack": def_base.attack,
                        "defense": def_base.defense,
                        "special_attack": def_base.special_attack,
                        "special_defense": def_base.special_defense,
                        "speed": def_base.speed,
                    }

                    ui_resource = create_interactive_damage_calc_resource(
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
                        attacker_evs=attacker_evs_dict,
                        defender_evs=defender_evs_dict,
                        attacker_nature=str(atk_nature.value).title(),
                        defender_nature=str(def_nature.value).title(),
                        attacker_base_stats=attacker_base_stats_dict,
                        defender_base_stats=defender_base_stats_dict,
                        move_category=move.category,
                        move_power=move.power,
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
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            # Auto-detect Ruinous abilities from attacker
            sword_of_ruin = False
            beads_of_ruin = False
            atk_abilities = await pokeapi.get_pokemon_abilities(attacker_name)
            if atk_abilities:
                attacker_ability = atk_abilities[0].lower().replace(" ", "-")
                if attacker_ability == "sword-of-ruin":
                    sword_of_ruin = True
                elif attacker_ability == "beads-of-ruin":
                    beads_of_ruin = True

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

            # Create modifiers with Ruinous abilities
            modifiers = DamageModifiers(
                is_doubles=True,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin
            )

            result = calculate_ko_threshold(
                attacker, defender, move,
                modifiers=modifiers,
                target_ko_chance=target_ko_chance
            )

            if result is None:
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Attacker         | {attacker_name}                            |",
                    f"| Defender         | {defender_name}                            |",
                    f"| Move             | {move_name}                                |",
                    f"| Target KO        | {target_ko_chance}%                        |",
                    f"| Result           | Not achievable with 252 EVs                |",
                ]
                return {
                    "attacker": attacker_name,
                    "defender": defender_name,
                    "move": move_name,
                    "achievable": False,
                    "message": f"Cannot achieve {target_ko_chance}% OHKO with 252 EVs. Consider items, Tera, or different move.",
                    "summary_table": "\n".join(table_lines)
                }

            # Build defender spread string
            is_physical = move.category.value == "physical"
            relevant_def_evs = defender_def_evs if is_physical else defender_def_evs
            def_stat_name = "Def" if is_physical else "SpD"
            defender_spread_str = f"{defender_nature.title()} {defender_hp_evs} HP / {relevant_def_evs} {def_stat_name} {defender_name}"

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Attacker         | {attacker_name}                            |",
                f"| Defender         | {defender_spread_str}                      |",
                f"| Move             | {move_name}                                |",
                f"| Required EVs     | {result['evs_needed']} {result['stat_name']} |",
                f"| Damage Range     | {result['damage_range']}                   |",
                f"| KO Chance        | {result['ko_chance']:.2f}%                 |",
            ]

            return {
                "attacker": attacker_name,
                "defender": defender_name,
                "defender_spread": defender_spread_str,
                "move": move_name,
                "achievable": True,
                "evs_needed": result["evs_needed"],
                "stat": result["stat_name"],
                "ko_chance": f"{result['ko_chance']:.2f}%",
                "damage_range": result["damage_range"],
                "summary_table": "\n".join(table_lines),
                "analysis": f"Need {result['evs_needed']} {result['stat_name']} EVs to {result['ko_chance']:.0f}% OHKO {defender_spread_str} with {move_name}"
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
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            # Auto-detect Ruinous abilities from attacker
            sword_of_ruin = False
            beads_of_ruin = False
            atk_abilities = await pokeapi.get_pokemon_abilities(attacker_name)
            if atk_abilities:
                attacker_ability = atk_abilities[0].lower().replace(" ", "-")
                if attacker_ability == "sword-of-ruin":
                    sword_of_ruin = True
                elif attacker_ability == "beads-of-ruin":
                    beads_of_ruin = True

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

            # Create modifiers with Ruinous abilities
            modifiers = DamageModifiers(
                is_doubles=True,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin
            )

            result = calculate_bulk_threshold(
                attacker, defender, move,
                modifiers=modifiers,
                target_survival_chance=target_survival_chance
            )

            if result is None:
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Threat           | {attacker_name}'s {move_name}              |",
                    f"| Defender         | {defender_name}                            |",
                    f"| Target Survival  | {target_survival_chance}%                  |",
                    f"| Result           | Not achievable with max investment         |",
                ]
                return {
                    "attacker": attacker_name,
                    "defender": defender_name,
                    "move": move_name,
                    "achievable": False,
                    "message": f"Cannot survive this attack with max investment. Consider items, Tera typing, or screens.",
                    "summary_table": "\n".join(table_lines)
                }

            # Build attacker spread string
            stat_name = "Atk" if is_physical else "SpA"
            atk_nature_mod = get_nature_modifier(atk_nature, "attack" if is_physical else "special_attack")
            nature_boost = "+" if atk_nature_mod > 1.0 else ""
            nature_penalty = "-" if atk_nature_mod < 1.0 else ""
            nature_indicator = nature_boost or nature_penalty
            attacker_spread_str = f"{attacker_evs}{nature_indicator} {stat_name} {attacker_name}"

            # Build summary table
            total_evs = result["hp_evs"] + result["def_evs"]
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Threat           | {attacker_spread_str}'s {move_name}        |",
                f"| Defender         | {defender_name}                            |",
                f"| HP EVs           | {result['hp_evs']}                         |",
                f"| {result['def_stat_name']} EVs      | {result['def_evs']}                         |",
                f"| Total EVs        | {total_evs}                                |",
                f"| Damage Range     | {result['damage_range']}                   |",
                f"| Survival Rate    | {result['survival_chance']:.2f}%           |",
            ]

            return {
                "attacker": attacker_name,
                "attacker_spread": attacker_spread_str,
                "defender": defender_name,
                "move": move_name,
                "achievable": True,
                "hp_evs_needed": result["hp_evs"],
                "def_evs_needed": result["def_evs"],
                "def_stat": result["def_stat_name"],
                "survival_chance": f"{result['survival_chance']:.2f}%",
                "damage_range": result["damage_range"],
                "summary_table": "\n".join(table_lines),
                "analysis": f"Need {result['hp_evs']} HP / {result['def_evs']} {result['def_stat_name']} EVs to survive {move_name} from {attacker_spread_str} — takes {result['damage_range']}"
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
    async def survive_multiple_hits(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        num_hits: int = 2,
        attacker_nature: Optional[str] = None,
        attacker_atk_evs: Optional[int] = None,
        attacker_spa_evs: Optional[int] = None,
        defender_nature: Optional[str] = None,
        defender_hp_evs: Optional[int] = None,
        defender_def_evs: Optional[int] = None,
        defender_spd_evs: Optional[int] = None,
        use_smogon_spreads: bool = True,
        attacker_attack_stage: int = 0,
        defender_defense_stage: int = 0,
        weather: Optional[str] = None,
        terrain: Optional[str] = None,
        attacker_item: Optional[str] = None,
        reflect: bool = False,
        light_screen: bool = False,
        aurora_veil: bool = False,
        friend_guard: bool = False
    ) -> dict:
        """
        Calculate if a Pokemon can survive multiple hits of an attack.

        Useful for scenarios like "Can Ogerpon survive 2 Close Combats from Urshifu?"
        Note: Close Combat drops the ATTACKER's defenses, not the defender's,
        so each hit does the same damage to the defender.

        Args:
            attacker_name: Attacking Pokemon's name
            defender_name: Defending Pokemon's name (your Pokemon)
            move_name: Move being used repeatedly
            num_hits: Number of hits to survive (default 2)
            attacker_nature: Attacker's nature
            attacker_atk_evs: Attacker's Attack EVs
            attacker_spa_evs: Attacker's Sp. Atk EVs
            defender_nature: Defender's nature
            defender_hp_evs: Defender's HP EVs
            defender_def_evs: Defender's Defense EVs
            defender_spd_evs: Defender's Sp. Def EVs
            use_smogon_spreads: Auto-fetch spreads from Smogon
            attacker_attack_stage: Attack/Sp.Atk stage (-6 to +6). Use -1 for Intimidate.
            defender_defense_stage: Defense/Sp.Def stage (-6 to +6). Use -1 for Screech, etc.
            weather: "sun", "rain", "sand", or "snow"
            terrain: "electric", "grassy", "psychic", or "misty"
            attacker_item: Attacker's item
            reflect: True if Reflect is active
            light_screen: True if Light Screen is active
            aurora_veil: True if Aurora Veil is active
            friend_guard: True if ally has Friend Guard ability

        Returns:
            Analysis of whether the defender survives N hits
        """
        try:
            # Fetch Pokemon data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            # Auto-fetch Smogon spreads if enabled
            if use_smogon_spreads:
                if attacker_nature is None or attacker_atk_evs is None or attacker_spa_evs is None:
                    atk_spread = await _get_common_spread(attacker_name)
                    if atk_spread:
                        if attacker_nature is None:
                            attacker_nature = atk_spread["nature"]
                        evs = atk_spread.get("evs", {})
                        if attacker_atk_evs is None:
                            attacker_atk_evs = evs.get("attack", 0)
                        if attacker_spa_evs is None:
                            attacker_spa_evs = evs.get("special_attack", 0)
                        if attacker_item is None and atk_spread.get("item"):
                            attacker_item = _normalize_smogon_name(atk_spread["item"])

                if defender_nature is None or defender_hp_evs is None or defender_def_evs is None or defender_spd_evs is None:
                    def_spread = await _get_common_spread(defender_name)
                    if def_spread:
                        if defender_nature is None:
                            defender_nature = def_spread["nature"]
                        evs = def_spread.get("evs", {})
                        if defender_hp_evs is None:
                            defender_hp_evs = evs.get("hp", 0)
                        if defender_def_evs is None:
                            defender_def_evs = evs.get("defense", 0)
                        if defender_spd_evs is None:
                            defender_spd_evs = evs.get("special_defense", 0)

            # Set defaults
            attacker_nature = attacker_nature or "adamant"
            attacker_atk_evs = attacker_atk_evs if attacker_atk_evs is not None else 252
            attacker_spa_evs = attacker_spa_evs if attacker_spa_evs is not None else 0
            defender_nature = defender_nature or "serious"
            defender_hp_evs = defender_hp_evs if defender_hp_evs is not None else 0
            defender_def_evs = defender_def_evs if defender_def_evs is not None else 0
            defender_spd_evs = defender_spd_evs if defender_spd_evs is not None else 0

            # Auto-fill signature items for Pokemon that require them
            if attacker_item is None:
                from vgc_mcp_core.calc.items import get_signature_item
                sig_item = get_signature_item(attacker_name)
                if sig_item:
                    attacker_item = sig_item

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

            # Create builds
            attacker = PokemonBuild(
                name=attacker_name,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature,
                evs=EVSpread(attack=attacker_atk_evs, special_attack=attacker_spa_evs),
                item=attacker_item
            )

            defender = PokemonBuild(
                name=defender_name,
                base_stats=def_base,
                types=def_types,
                nature=def_nature,
                evs=EVSpread(hp=defender_hp_evs, defense=defender_def_evs, special_defense=defender_spd_evs)
            )

            # Set up modifiers with attack stage
            is_physical = move.category.value == "physical"
            modifiers = DamageModifiers(
                is_doubles=True,
                weather=weather,
                terrain=terrain,
                attacker_item=attacker_item,
                reflect_up=reflect,
                light_screen_up=light_screen,
                aurora_veil_up=aurora_veil,
                friend_guard=friend_guard,
                attack_stage=attacker_attack_stage if is_physical else 0,
                special_attack_stage=attacker_attack_stage if not is_physical else 0,
                defense_stage=defender_defense_stage if is_physical else 0,
                special_defense_stage=defender_defense_stage if not is_physical else 0
            )

            # Calculate single hit damage
            result = calculate_damage(attacker, defender, move, modifiers)

            # Calculate multi-hit survival
            min_per_hit = result.min_damage
            max_per_hit = result.max_damage
            defender_hp = result.defender_hp

            total_min = min_per_hit * num_hits
            total_max = max_per_hit * num_hits

            min_percent_per_hit = (min_per_hit / defender_hp) * 100
            max_percent_per_hit = (max_per_hit / defender_hp) * 100
            total_min_percent = (total_min / defender_hp) * 100
            total_max_percent = (total_max / defender_hp) * 100

            survives_guaranteed = total_max < defender_hp
            survives_possible = total_min < defender_hp

            # Calculate exact survival probability
            survival_scenarios = 0
            total_scenarios = 16 ** num_hits

            if num_hits <= 3:
                from itertools import product
                for roll_combo in product(result.rolls, repeat=num_hits):
                    if sum(roll_combo) < defender_hp:
                        survival_scenarios += 1
                survival_chance = (survival_scenarios / total_scenarios) * 100
            else:
                avg_damage = sum(result.rolls) / len(result.rolls)
                total_avg = avg_damage * num_hits
                survival_chance = 100.0 if total_avg < defender_hp else 0.0

            # Calculate HP remaining
            hp_remaining_min = max(0, defender_hp - total_max)
            hp_remaining_max = max(0, defender_hp - total_min)
            hp_remain_min_pct = round(hp_remaining_min / defender_hp * 100, 1)
            hp_remain_max_pct = round(hp_remaining_max / defender_hp * 100, 1)

            verdict_str = "SURVIVES" if survives_guaranteed else ("MIGHT SURVIVE" if survives_possible else "FAINTS")

            # Build summary table
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Attacker         | {attacker_name}                            |",
                f"| Defender         | {defender_name}                            |",
                f"| Move             | {move_name} x{num_hits}                    |",
                f"| Per Hit          | {min_per_hit}-{max_per_hit} ({min_percent_per_hit:.1f}-{max_percent_per_hit:.1f}%) |",
                f"| Total Damage     | {total_min}-{total_max} ({total_min_percent:.1f}-{total_max_percent:.1f}%) |",
                f"| HP Remaining     | {hp_remaining_min}-{hp_remaining_max} ({hp_remain_min_pct}-{hp_remain_max_pct}%) |",
                f"| Survival Chance  | {survival_chance:.2f}%                     |",
                f"| Verdict          | {verdict_str}                              |",
            ]

            # Build analysis prose with spread details (Showdown format)
            survival_word = "survives" if survives_guaranteed else ("may survive" if survives_possible else "does not survive")
            is_physical = move.category.value == "physical"
            relevant_atk_evs = attacker_atk_evs if is_physical else attacker_spa_evs
            stat_name = "Atk" if is_physical else "SpA"

            # Get nature modifiers for attacker
            atk_nature_mod = get_nature_modifier(atk_nature, "attack")
            spa_nature_mod = get_nature_modifier(atk_nature, "special_attack")

            # Build attacker spread string (e.g., "252+ Atk Mystic Water")
            nature_boost = "+" if (is_physical and atk_nature_mod > 1.0) or (not is_physical and spa_nature_mod > 1.0) else ""
            nature_penalty = "-" if (is_physical and atk_nature_mod < 1.0) or (not is_physical and spa_nature_mod < 1.0) else ""
            nature_indicator = nature_boost or nature_penalty
            item_str = f" {attacker_item.replace('-', ' ').title()}" if attacker_item else ""
            attacker_spread_str = f"{relevant_atk_evs}{nature_indicator} {stat_name}{item_str} {attacker_name}"

            # Build defender spread string (e.g., "Impish 132 HP / 196 Def")
            relevant_def_evs = defender_def_evs if is_physical else defender_spd_evs
            def_stat_name = "Def" if is_physical else "SpD"
            defender_spread_str = f"{defender_nature.title()} {defender_hp_evs} HP / {relevant_def_evs} {def_stat_name} {defender_name}"

            analysis_str = f"{defender_spread_str} {survival_word} {num_hits}x {attacker_spread_str}'s {move_name} — takes {total_min_percent:.0f}-{total_max_percent:.0f}% total, left at {hp_remain_min_pct}-{hp_remain_max_pct}% HP"

            response = {
                "attacker": attacker_name,
                "defender": defender_name,
                "move": move_name,
                "num_hits": num_hits,
                "defender_hp": defender_hp,
                "per_hit": {
                    "min_damage": min_per_hit,
                    "max_damage": max_per_hit,
                    "min_percent": f"{min_percent_per_hit:.1f}%",
                    "max_percent": f"{max_percent_per_hit:.1f}%"
                },
                "total_damage": {
                    "min": total_min,
                    "max": total_max,
                    "min_percent": f"{total_min_percent:.1f}%",
                    "max_percent": f"{total_max_percent:.1f}%"
                },
                "hp_remaining": {
                    "min": hp_remaining_min,
                    "max": hp_remaining_max,
                    "min_percent": f"{hp_remain_min_pct}%",
                    "max_percent": f"{hp_remain_max_pct}%"
                },
                "survives_guaranteed": survives_guaranteed,
                "survives_possible": survives_possible,
                "survival_chance": f"{survival_chance:.2f}%",
                "verdict": verdict_str,
                "attacker_spread": {
                    "nature": attacker_nature,
                    "attack_evs": attacker_atk_evs,
                    "spa_evs": attacker_spa_evs,
                    "attack_stage": attacker_attack_stage
                },
                "defender_spread": {
                    "nature": defender_nature,
                    "hp_evs": defender_hp_evs,
                    "def_evs": defender_def_evs,
                    "spd_evs": defender_spd_evs
                },
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

            if attacker_attack_stage == -1:
                response["notes"] = ["Attacker at -1 Attack (Intimidate)"]
            elif attacker_attack_stage < 0:
                response["notes"] = [f"Attacker at {attacker_attack_stage} Attack"]

            return response

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
    async def find_bulk_to_survive_hits(
        attacker_name: str,
        defender_name: str,
        move_name: str,
        num_hits: int = 2,
        attacker_nature: str = "adamant",
        attacker_evs: int = 252,
        defender_nature: str = "impish",
        attacker_attack_stage: int = 0,
        defender_defense_stage: int = 0,
        reflect: bool = False,
        light_screen: bool = False,
        aurora_veil: bool = False,
        friend_guard: bool = False
    ) -> dict:
        """
        Find minimum HP/Def EVs to survive multiple hits of an attack.

        Args:
            attacker_name: Attacking Pokemon
            defender_name: Defending Pokemon (your Pokemon)
            move_name: Move to survive
            num_hits: Number of hits to survive (default 2)
            attacker_nature: Attacker's nature
            attacker_evs: Attacker's offensive EVs
            defender_nature: Your nature (+Def: Impish/Bold, +SpD: Calm/Careful)
            attacker_attack_stage: Attack stage (-6 to +6). Use -1 for Intimidate.
            defender_defense_stage: Defense stage (-6 to +6). Use -1 for Screech, etc.
            reflect: True if Reflect is active
            light_screen: True if Light Screen is active
            aurora_veil: True if Aurora Veil is active
            friend_guard: True if ally has Friend Guard ability

        Returns:
            Required HP/Def EVs to survive, or indication if impossible
        """
        try:
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            atk_nature = Nature(attacker_nature.lower())
            def_nature_parsed = Nature(defender_nature.lower())
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

            best_spread = None
            min_total_evs = 999

            for hp_ev in range(0, 256, 4):
                for def_ev in range(0, 256, 4):
                    if hp_ev + def_ev > 508:
                        continue

                    test_evs = EVSpread(hp=hp_ev)
                    if is_physical:
                        test_evs.defense = def_ev
                    else:
                        test_evs.special_defense = def_ev

                    defender = PokemonBuild(
                        name=defender_name,
                        base_stats=def_base,
                        types=def_types,
                        nature=def_nature_parsed,
                        evs=test_evs
                    )

                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attack_stage=attacker_attack_stage if is_physical else 0,
                        special_attack_stage=attacker_attack_stage if not is_physical else 0,
                        defense_stage=defender_defense_stage if is_physical else 0,
                        special_defense_stage=defender_defense_stage if not is_physical else 0,
                        reflect_up=reflect,
                        light_screen_up=light_screen,
                        aurora_veil_up=aurora_veil,
                        friend_guard=friend_guard
                    )

                    result = calculate_damage(attacker, defender, move, modifiers)
                    total_max = result.max_damage * num_hits

                    if total_max < result.defender_hp:
                        total_evs = hp_ev + def_ev
                        if total_evs < min_total_evs:
                            min_total_evs = total_evs
                            best_spread = {
                                "hp_evs": hp_ev,
                                "def_evs": def_ev,
                                "total_evs": total_evs,
                                "defender_hp": result.defender_hp,
                                "per_hit_max": result.max_damage,
                                "total_max": total_max,
                                "remaining_hp": result.defender_hp - total_max
                            }
                            break

            if best_spread is None:
                max_defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature_parsed,
                    evs=EVSpread(hp=252, defense=252 if is_physical else 0, special_defense=0 if is_physical else 252)
                )
                modifiers = DamageModifiers(
                    is_doubles=True,
                    attack_stage=attacker_attack_stage if is_physical else 0,
                    special_attack_stage=attacker_attack_stage if not is_physical else 0,
                    defense_stage=defender_defense_stage if is_physical else 0,
                    special_defense_stage=defender_defense_stage if not is_physical else 0,
                    reflect_up=reflect,
                    light_screen_up=light_screen,
                    aurora_veil_up=aurora_veil,
                    friend_guard=friend_guard
                )
                result = calculate_damage(attacker, max_defender, move, modifiers)
                total_max = result.max_damage * num_hits

                # Build summary table for failure case
                def_stat_name = "Def" if is_physical else "SpD"
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Threat           | {attacker_name}'s {move_name} x{num_hits}  |",
                    f"| Defender         | {defender_name}                            |",
                    f"| Max Investment   | 252 HP / 252 {def_stat_name} {defender_nature} |",
                    f"| Per Hit (max)    | {result.max_damage} ({result.max_damage/result.defender_hp*100:.1f}%) |",
                    f"| Total (max)      | {total_max} ({total_max/result.defender_hp*100:.1f}%) |",
                    f"| Result           | Cannot survive                             |",
                ]

                return {
                    "attacker": attacker_name,
                    "defender": defender_name,
                    "move": move_name,
                    "num_hits": num_hits,
                    "achievable": False,
                    "message": f"Cannot survive {num_hits} hits even with 252 HP / 252 {'Def' if is_physical else 'SpD'} {defender_nature}",
                    "max_bulk_stats": {
                        "hp": result.defender_hp,
                        "per_hit": f"{result.max_damage} ({result.max_damage/result.defender_hp*100:.1f}%)",
                        "total": f"{total_max} ({total_max/result.defender_hp*100:.1f}%)"
                    },
                    "suggestion": "Try Intimidate (-1 Attack)" if attacker_attack_stage >= 0 else "Try Reflect/Light Screen or resistance berry",
                    "summary_table": "\n".join(table_lines)
                }

            # Build attacker spread string
            stat_name = "Atk" if is_physical else "SpA"
            atk_nature_mod = get_nature_modifier(atk_nature, "attack" if is_physical else "special_attack")
            nature_boost = "+" if atk_nature_mod > 1.0 else ""
            nature_penalty = "-" if atk_nature_mod < 1.0 else ""
            nature_indicator = nature_boost or nature_penalty
            attacker_spread_str = f"{attacker_evs}{nature_indicator} {stat_name} {attacker_name}"

            # Build summary table for success case
            hp_remain_pct = round(best_spread["remaining_hp"] / best_spread["defender_hp"] * 100, 1)
            def_stat_name = "Def" if is_physical else "SpD"
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Threat           | {attacker_spread_str}'s {move_name} x{num_hits} |",
                f"| Defender         | {defender_name}                            |",
                f"| HP EVs           | {best_spread['hp_evs']}                    |",
                f"| {def_stat_name} EVs          | {best_spread['def_evs']}                    |",
                f"| Total EVs        | {best_spread['total_evs']}                 |",
                f"| EVs Remaining    | {508 - best_spread['total_evs']}           |",
                f"| Per Hit (max)    | {best_spread['per_hit_max']}               |",
                f"| Total (max)      | {best_spread['total_max']}                 |",
                f"| HP Remaining     | {best_spread['remaining_hp']} ({hp_remain_pct}%) |",
            ]

            return {
                "attacker": attacker_name,
                "attacker_spread": attacker_spread_str,
                "defender": defender_name,
                "move": move_name,
                "num_hits": num_hits,
                "achievable": True,
                "minimum_spread": {
                    "hp_evs": best_spread["hp_evs"],
                    "def_evs": best_spread["def_evs"],
                    "nature": defender_nature,
                    "total_evs": best_spread["total_evs"],
                    "evs_remaining": 508 - best_spread["total_evs"]
                },
                "calculation": {
                    "defender_hp": best_spread["defender_hp"],
                    "per_hit_max": best_spread["per_hit_max"],
                    "total_max": best_spread["total_max"],
                    "hp_remaining": best_spread["remaining_hp"]
                },
                "summary_table": "\n".join(table_lines),
                "analysis": f"Need {best_spread['hp_evs']} HP / {best_spread['def_evs']} {def_stat_name} EVs to survive {num_hits}x {move_name} from {attacker_spread_str}, left at {hp_remain_pct}% HP"
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
    async def survive_double_up(
        defender_name: str,
        attacker1_name: str,
        move1_name: str,
        attacker2_name: str,
        move2_name: str,
        defender_nature: Optional[str] = None,
        defender_hp_evs: Optional[int] = None,
        defender_def_evs: Optional[int] = None,
        defender_spd_evs: Optional[int] = None,
        defender_item: Optional[str] = None,
        defender_ability: Optional[str] = None,
        defender_tera_type: Optional[str] = None,
        attacker1_nature: Optional[str] = None,
        attacker1_atk_evs: Optional[int] = None,
        attacker1_spa_evs: Optional[int] = None,
        attacker1_item: Optional[str] = None,
        attacker1_ability: Optional[str] = None,
        attacker2_nature: Optional[str] = None,
        attacker2_atk_evs: Optional[int] = None,
        attacker2_spa_evs: Optional[int] = None,
        attacker2_item: Optional[str] = None,
        attacker2_ability: Optional[str] = None,
        use_smogon_spreads: bool = True,
        weather: Optional[str] = None,
        terrain: Optional[str] = None,
        reflect: bool = False,
        light_screen: bool = False,
        aurora_veil: bool = False,
        friend_guard: bool = False,
        sword_of_ruin: bool = False,
        beads_of_ruin: bool = False,
        tablets_of_ruin: bool = False,
        vessel_of_ruin: bool = False,
        attacker1_attack_stage: int = 0,
        attacker2_attack_stage: int = 0,
        defender_defense_stage: int = 0,
        defender_special_defense_stage: int = 0
    ) -> dict:
        """
        Check if a Pokemon survives combined damage from two attackers in one turn (double-up).

        Use this to answer questions like "Can Chien-Pao survive Grassy Glide + Aqua Jet?"

        Args:
            defender_name: Target Pokemon being attacked (e.g., "Chien-Pao")
            attacker1_name: First attacker (e.g., "Rillaboom")
            move1_name: First attack (e.g., "Grassy Glide")
            attacker2_name: Second attacker (e.g., "Urshifu-Rapid-Strike")
            move2_name: Second attack (e.g., "Aqua Jet")
            defender_nature: Defender's nature (auto-fetched from Smogon if not specified)
            defender_hp_evs: Defender's HP EVs
            defender_def_evs: Defender's Defense EVs
            defender_spd_evs: Defender's Sp. Def EVs
            defender_item: Defender's item (e.g., "focus-sash")
            defender_ability: Defender's ability
            defender_tera_type: Defender's Tera type if Terastallized
            attacker1_nature: First attacker's nature
            attacker1_atk_evs: First attacker's Attack EVs
            attacker1_spa_evs: First attacker's Sp. Atk EVs
            attacker1_item: First attacker's item
            attacker1_ability: First attacker's ability
            attacker2_nature: Second attacker's nature
            attacker2_atk_evs: Second attacker's Attack EVs
            attacker2_spa_evs: Second attacker's Sp. Atk EVs
            attacker2_item: Second attacker's item
            attacker2_ability: Second attacker's ability
            use_smogon_spreads: Auto-fetch spreads from Smogon (default True)
            weather: "sun", "rain", "sand", or "snow"
            terrain: "electric", "grassy", "psychic", or "misty"
            reflect: True if Reflect is active (halves physical damage)
            light_screen: True if Light Screen is active (halves special damage)
            aurora_veil: True if Aurora Veil is active (halves all damage in hail)
            friend_guard: True if ally has Friend Guard (0.75x damage)
            sword_of_ruin: True if Chien-Pao's Sword of Ruin is active (lowers Def to 0.75x)
            beads_of_ruin: True if Chi-Yu's Beads of Ruin is active (lowers SpD to 0.75x)
            tablets_of_ruin: True if Wo-Chien's Tablets of Ruin is active (lowers Atk to 0.75x)
            vessel_of_ruin: True if Ting-Lu's Vessel of Ruin is active (lowers SpA to 0.75x)
            attacker1_attack_stage: First attacker's stat stage from -6 to +6 (0 = neutral)
            attacker2_attack_stage: Second attacker's stat stage from -6 to +6 (0 = neutral)
            defender_defense_stage: Defender's Defense stat stage from -6 to +6
            defender_special_defense_stage: Defender's Sp. Def stat stage from -6 to +6

        Returns:
            Combined damage range, survival result, and breakdown per attacker
        """
        try:
            # Fetch Pokemon data for all three Pokemon
            def_base = await pokeapi.get_base_stats(defender_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            atk1_base = await pokeapi.get_base_stats(attacker1_name)
            atk1_types = await pokeapi.get_pokemon_types(attacker1_name)
            atk2_base = await pokeapi.get_base_stats(attacker2_name)
            atk2_types = await pokeapi.get_pokemon_types(attacker2_name)
            move1 = await pokeapi.get_move(move1_name, user_name=attacker1_name)
            move2 = await pokeapi.get_move(move2_name, user_name=attacker2_name)

            # Auto-fetch Smogon spreads if enabled
            if use_smogon_spreads:
                # Defender spread
                if defender_nature is None or defender_hp_evs is None or defender_def_evs is None or defender_spd_evs is None:
                    def_spread = await _get_common_spread(defender_name)
                    if def_spread:
                        if defender_nature is None:
                            defender_nature = def_spread["nature"]
                        evs = def_spread.get("evs", {})
                        if defender_hp_evs is None:
                            defender_hp_evs = evs.get("hp", 0)
                        if defender_def_evs is None:
                            defender_def_evs = evs.get("defense", 0)
                        if defender_spd_evs is None:
                            defender_spd_evs = evs.get("special_defense", 0)
                        if defender_item is None and def_spread.get("item"):
                            defender_item = _normalize_smogon_name(def_spread["item"])
                        if defender_ability is None and def_spread.get("ability"):
                            defender_ability = _normalize_smogon_name(def_spread["ability"])

                # Attacker 1 spread
                if attacker1_nature is None or attacker1_atk_evs is None or attacker1_spa_evs is None:
                    atk1_spread = await _get_common_spread(attacker1_name)
                    if atk1_spread:
                        if attacker1_nature is None:
                            attacker1_nature = atk1_spread["nature"]
                        evs = atk1_spread.get("evs", {})
                        if attacker1_atk_evs is None:
                            attacker1_atk_evs = evs.get("attack", 0)
                        if attacker1_spa_evs is None:
                            attacker1_spa_evs = evs.get("special_attack", 0)
                        if attacker1_item is None and atk1_spread.get("item"):
                            attacker1_item = _normalize_smogon_name(atk1_spread["item"])
                        if attacker1_ability is None and atk1_spread.get("ability"):
                            attacker1_ability = _normalize_smogon_name(atk1_spread["ability"])

                # Attacker 2 spread
                if attacker2_nature is None or attacker2_atk_evs is None or attacker2_spa_evs is None:
                    atk2_spread = await _get_common_spread(attacker2_name)
                    if atk2_spread:
                        if attacker2_nature is None:
                            attacker2_nature = atk2_spread["nature"]
                        evs = atk2_spread.get("evs", {})
                        if attacker2_atk_evs is None:
                            attacker2_atk_evs = evs.get("attack", 0)
                        if attacker2_spa_evs is None:
                            attacker2_spa_evs = evs.get("special_attack", 0)
                        if attacker2_item is None and atk2_spread.get("item"):
                            attacker2_item = _normalize_smogon_name(atk2_spread["item"])
                        if attacker2_ability is None and atk2_spread.get("ability"):
                            attacker2_ability = _normalize_smogon_name(atk2_spread["ability"])

            # Set defaults
            defender_nature = defender_nature or "serious"
            defender_hp_evs = defender_hp_evs if defender_hp_evs is not None else 0
            defender_def_evs = defender_def_evs if defender_def_evs is not None else 0
            defender_spd_evs = defender_spd_evs if defender_spd_evs is not None else 0
            attacker1_nature = attacker1_nature or "adamant"
            attacker1_atk_evs = attacker1_atk_evs if attacker1_atk_evs is not None else 252
            attacker1_spa_evs = attacker1_spa_evs if attacker1_spa_evs is not None else 0
            attacker2_nature = attacker2_nature or "adamant"
            attacker2_atk_evs = attacker2_atk_evs if attacker2_atk_evs is not None else 252
            attacker2_spa_evs = attacker2_spa_evs if attacker2_spa_evs is not None else 0

            # Auto-assign signature items
            from ...vgc_mcp_core.calc.items import get_signature_item
            if attacker1_item is None:
                sig_item = get_signature_item(attacker1_name)
                if sig_item:
                    attacker1_item = sig_item
            if attacker2_item is None:
                sig_item = get_signature_item(attacker2_name)
                if sig_item:
                    attacker2_item = sig_item

            # Parse natures
            try:
                def_nature = Nature(defender_nature.lower())
            except ValueError:
                suggestions = suggest_nature(defender_nature)
                return invalid_nature_error(defender_nature, suggestions if suggestions else [n.value for n in Nature])

            try:
                atk1_nature = Nature(attacker1_nature.lower())
            except ValueError:
                suggestions = suggest_nature(attacker1_nature)
                return invalid_nature_error(attacker1_nature, suggestions if suggestions else [n.value for n in Nature])

            try:
                atk2_nature = Nature(attacker2_nature.lower())
            except ValueError:
                suggestions = suggest_nature(attacker2_nature)
                return invalid_nature_error(attacker2_nature, suggestions if suggestions else [n.value for n in Nature])

            # Create Pokemon builds
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
                item=defender_item,
                tera_type=defender_tera_type
            )

            attacker1 = PokemonBuild(
                name=attacker1_name,
                base_stats=atk1_base,
                types=atk1_types,
                nature=atk1_nature,
                evs=EVSpread(
                    attack=attacker1_atk_evs,
                    special_attack=attacker1_spa_evs
                ),
                item=attacker1_item
            )

            attacker2 = PokemonBuild(
                name=attacker2_name,
                base_stats=atk2_base,
                types=atk2_types,
                nature=atk2_nature,
                evs=EVSpread(
                    attack=attacker2_atk_evs,
                    special_attack=attacker2_spa_evs
                ),
                item=attacker2_item
            )

            # Determine if each move is physical or special
            is_physical1 = move1.category.value == "physical"
            is_physical2 = move2.category.value == "physical"

            # Set up modifiers for both attacks
            modifiers1 = DamageModifiers(
                is_doubles=True,
                weather=weather,
                terrain=terrain,
                attacker_item=attacker1_item,
                defender_item=defender_item,
                attacker_ability=attacker1_ability,
                defender_ability=defender_ability,
                defender_tera_type=defender_tera_type,
                defender_tera_active=defender_tera_type is not None,
                reflect_up=reflect,
                light_screen_up=light_screen,
                aurora_veil_up=aurora_veil,
                friend_guard=friend_guard,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin,
                tablets_of_ruin=tablets_of_ruin,
                vessel_of_ruin=vessel_of_ruin,
                attack_stage=attacker1_attack_stage if is_physical1 else 0,
                special_attack_stage=attacker1_attack_stage if not is_physical1 else 0,
                defense_stage=defender_defense_stage if is_physical1 else 0,
                special_defense_stage=defender_special_defense_stage if not is_physical1 else 0
            )

            modifiers2 = DamageModifiers(
                is_doubles=True,
                weather=weather,
                terrain=terrain,
                attacker_item=attacker2_item,
                defender_item=defender_item,
                attacker_ability=attacker2_ability,
                defender_ability=defender_ability,
                defender_tera_type=defender_tera_type,
                defender_tera_active=defender_tera_type is not None,
                reflect_up=reflect,
                light_screen_up=light_screen,
                aurora_veil_up=aurora_veil,
                friend_guard=friend_guard,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin,
                tablets_of_ruin=tablets_of_ruin,
                vessel_of_ruin=vessel_of_ruin,
                attack_stage=attacker2_attack_stage if is_physical2 else 0,
                special_attack_stage=attacker2_attack_stage if not is_physical2 else 0,
                defense_stage=defender_defense_stage if is_physical2 else 0,
                special_defense_stage=defender_special_defense_stage if not is_physical2 else 0
            )

            # Calculate damage from each attack
            result1 = calculate_damage(attacker1, defender, move1, modifiers1)
            result2 = calculate_damage(attacker2, defender, move2, modifiers2)

            defender_hp = result1.defender_hp

            # Calculate combined damage
            combined_min = result1.min_damage + result2.min_damage
            combined_max = result1.max_damage + result2.max_damage

            combined_min_pct = round((combined_min / defender_hp) * 100, 1)
            combined_max_pct = round((combined_max / defender_hp) * 100, 1)

            # Calculate survival
            survives_min_roll = combined_max < defender_hp
            survives_max_roll = combined_min < defender_hp

            # Calculate exact survival probability by combining roll distributions
            survival_scenarios = 0
            total_scenarios = 16 * 16  # 256 combinations

            for roll1 in result1.rolls:
                for roll2 in result2.rolls:
                    if roll1 + roll2 < defender_hp:
                        survival_scenarios += 1

            survival_chance = round((survival_scenarios / total_scenarios) * 100, 1)

            # Determine verdict
            if survives_min_roll:
                verdict = "SURVIVES"
            elif survives_max_roll:
                verdict = "MIGHT SURVIVE"
            else:
                verdict = "FAINTS"

            # HP remaining calculations
            hp_remaining_min = max(0, defender_hp - combined_max)
            hp_remaining_max = max(0, defender_hp - combined_min)
            hp_remain_min_pct = round((hp_remaining_min / defender_hp) * 100, 1)
            hp_remain_max_pct = round((hp_remaining_max / defender_hp) * 100, 1)

            # Format individual attack results
            move1_min_pct = round((result1.min_damage / defender_hp) * 100, 1)
            move1_max_pct = round((result1.max_damage / defender_hp) * 100, 1)
            move2_min_pct = round((result2.min_damage / defender_hp) * 100, 1)
            move2_max_pct = round((result2.max_damage / defender_hp) * 100, 1)

            # Build summary table
            table_lines = [
                "| Attack           | Damage                                     |",
                "|------------------|---------------------------------------------|",
                f"| {attacker1_name}'s {move1_name} | {result1.min_damage}-{result1.max_damage} ({move1_min_pct}-{move1_max_pct}%) |",
                f"| {attacker2_name}'s {move2_name} | {result2.min_damage}-{result2.max_damage} ({move2_min_pct}-{move2_max_pct}%) |",
                f"| **Combined**     | {combined_min}-{combined_max} ({combined_min_pct}-{combined_max_pct}%) |",
                "|------------------|---------------------------------------------|",
                f"| {defender_name} HP | {defender_hp}                             |",
                f"| HP Remaining     | {hp_remaining_min}-{hp_remaining_max} ({hp_remain_min_pct}-{hp_remain_max_pct}%) |",
                f"| Survival Chance  | {survival_chance}%                         |",
                f"| **Verdict**      | {verdict}                                  |",
            ]

            # Build attacker spread strings
            # Attacker 1
            atk1_stat_name = "Atk" if is_physical1 else "SpA"
            atk1_evs = attacker1_atk_evs if is_physical1 else attacker1_spa_evs
            atk1_nature_mod = get_nature_modifier(atk1_nature, "attack" if is_physical1 else "special_attack")
            atk1_nature_indicator = "+" if atk1_nature_mod > 1.0 else ("-" if atk1_nature_mod < 1.0 else "")
            atk1_item_str = f" {attacker1_item}" if attacker1_item else ""
            atk1_spread_str = f"{atk1_evs}{atk1_nature_indicator} {atk1_stat_name}{atk1_item_str} {attacker1_name}"

            # Attacker 2
            atk2_stat_name = "Atk" if is_physical2 else "SpA"
            atk2_evs = attacker2_atk_evs if is_physical2 else attacker2_spa_evs
            atk2_nature_mod = get_nature_modifier(atk2_nature, "attack" if is_physical2 else "special_attack")
            atk2_nature_indicator = "+" if atk2_nature_mod > 1.0 else ("-" if atk2_nature_mod < 1.0 else "")
            atk2_item_str = f" {attacker2_item}" if attacker2_item else ""
            atk2_spread_str = f"{atk2_evs}{atk2_nature_indicator} {atk2_stat_name}{atk2_item_str} {attacker2_name}"

            # Build analysis prose
            survival_word = "survives" if survives_min_roll else ("may survive" if survives_max_roll else "does not survive")
            analysis = f"{defender_name} {survival_word} {move1_name} from {atk1_spread_str} + {move2_name} from {atk2_spread_str} — takes {combined_min_pct}-{combined_max_pct}% combined damage, left at {hp_remain_min_pct}-{hp_remain_max_pct}% HP ({survival_chance}% survival chance)"

            # Determine move priorities for turn order info
            priority_info = []
            if move1.priority > 0:
                priority_info.append(f"{move1_name}: +{move1.priority} priority")
            if move2.priority > 0:
                priority_info.append(f"{move2_name}: +{move2.priority} priority")

            response = {
                "defender": defender_name,
                "defender_hp": defender_hp,
                "attacks": [
                    {
                        "attacker": attacker1_name,
                        "move": move1_name,
                        "damage_min": result1.min_damage,
                        "damage_max": result1.max_damage,
                        "damage_range": f"{result1.min_damage}-{result1.max_damage}",
                        "percent": f"{move1_min_pct}-{move1_max_pct}%",
                        "priority": move1.priority,
                        "item": attacker1_item,
                        "ability": attacker1_ability
                    },
                    {
                        "attacker": attacker2_name,
                        "move": move2_name,
                        "damage_min": result2.min_damage,
                        "damage_max": result2.max_damage,
                        "damage_range": f"{result2.min_damage}-{result2.max_damage}",
                        "percent": f"{move2_min_pct}-{move2_max_pct}%",
                        "priority": move2.priority,
                        "item": attacker2_item,
                        "ability": attacker2_ability
                    }
                ],
                "combined_damage": {
                    "min": combined_min,
                    "max": combined_max,
                    "range": f"{combined_min}-{combined_max}",
                    "percent": f"{combined_min_pct}-{combined_max_pct}%"
                },
                "hp_remaining": {
                    "min": hp_remaining_min,
                    "max": hp_remaining_max,
                    "percent": f"{hp_remain_min_pct}-{hp_remain_max_pct}%"
                },
                "survives_min_roll": survives_min_roll,
                "survives_max_roll": survives_max_roll,
                "survival_chance": f"{survival_chance}%",
                "verdict": verdict,
                "defender_spread": {
                    "nature": defender_nature,
                    "hp_evs": defender_hp_evs,
                    "def_evs": defender_def_evs,
                    "spd_evs": defender_spd_evs,
                    "item": defender_item,
                    "ability": defender_ability,
                    "tera_type": defender_tera_type
                },
                "summary_table": "\n".join(table_lines),
                "analysis": analysis
            }

            if priority_info:
                response["priority_notes"] = priority_info

            # Add notes for active conditions
            notes = []
            if weather:
                notes.append(f"Weather: {weather.title()}")
            if terrain:
                notes.append(f"Terrain: {terrain.title()}")
            if reflect:
                notes.append("Reflect active")
            if light_screen:
                notes.append("Light Screen active")
            if friend_guard:
                notes.append("Friend Guard active (0.75x damage)")
            if sword_of_ruin:
                notes.append("Sword of Ruin active (0.75x Def)")
            if beads_of_ruin:
                notes.append("Beads of Ruin active (0.75x SpD)")
            if tablets_of_ruin:
                notes.append("Tablets of Ruin active (0.75x Atk)")
            if vessel_of_ruin:
                notes.append("Vessel of Ruin active (0.75x SpA)")
            if notes:
                response["active_conditions"] = notes

            return response

        except Exception as e:
            error_str = str(e).lower()
            if "not found" in error_str or "404" in error_str:
                suggestions = (
                    suggest_pokemon_name(defender_name) or
                    suggest_pokemon_name(attacker1_name) or
                    suggest_pokemon_name(attacker2_name)
                )
                return pokemon_not_found_error(
                    f"{defender_name}, {attacker1_name}, or {attacker2_name}",
                    suggestions if suggestions else None
                )
            return api_error("PokeAPI", str(e), is_retryable=True)
