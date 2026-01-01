"""Item mechanics tools for VGC MCP server.

Tools for calculating item effects on stats and damage:
- Booster Energy for Paradox Pokemon
- Assault Vest Special Defense boost
- Choice item stat boosts
- Eviolite for NFE Pokemon
- Berry activation thresholds
- Focus Sash survival checks
- Life Orb damage and recoil
"""

from mcp.server.fastmcp import FastMCP

from ..calc.items import (
    calculate_booster_energy_boost,
    calculate_assault_vest_boost,
    calculate_eviolite_boost,
    calculate_choice_item_boost,
    calculate_life_orb_effect,
    check_berry_activation,
    check_focus_sash_survival,
    get_item_damage_modifier,
    PARADOX_POKEMON,
    NFE_POKEMON,
)
from ..api.pokeapi import PokeAPIClient
from ..utils.errors import error_response, success_response


def register_item_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register item calculation tools."""

    @mcp.tool()
    async def calculate_booster_energy(
        pokemon_name: str,
        nature: str = "hardy"
    ) -> dict:
        """
        Calculate Booster Energy stat boost for Paradox Pokemon.

        Booster Energy activates Protosynthesis (past) or Quark Drive (future)
        to boost the highest stat by 30% (or 50% for Speed).

        Args:
            pokemon_name: Paradox Pokemon name (e.g., "flutter-mane", "iron-hands")
            nature: Nature for stat modifiers (default: hardy/neutral)

        Returns:
            Which stat gets boosted and by how much, or error if not Paradox
        """
        try:
            # Fetch base stats
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response(
                    "pokemon_not_found",
                    f"Could not find Pokemon: {pokemon_name}",
                    suggestions=["Check spelling", "Use hyphenated names (e.g., flutter-mane)"]
                )

            # Get nature modifiers
            nature_data = await pokeapi.get_nature(nature)
            nature_mods = {}
            if nature_data:
                if nature_data.get("increased_stat"):
                    stat_name = nature_data["increased_stat"]["name"].replace("-", "_")
                    nature_mods[stat_name] = 1.1
                if nature_data.get("decreased_stat"):
                    stat_name = nature_data["decreased_stat"]["name"].replace("-", "_")
                    nature_mods[stat_name] = 0.9

            base_stats = {
                "attack": stats.get("attack", 0),
                "defense": stats.get("defense", 0),
                "special_attack": stats.get("special-attack", 0),
                "special_defense": stats.get("special-defense", 0),
                "speed": stats.get("speed", 0),
            }

            result = calculate_booster_energy_boost(pokemon_name, base_stats, nature_mods)

            return {
                "pokemon": pokemon_name,
                "item": "Booster Energy",
                "is_paradox": result.applies,
                "boosted_stat": list(result.stat_modifiers.keys())[0] if result.stat_modifiers else None,
                "boost_multiplier": list(result.stat_modifiers.values())[0] if result.stat_modifiers else None,
                "description": result.description,
                "notes": result.notes,
                "paradox_pokemon_list": sorted(PARADOX_POKEMON) if not result.applies else None
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_assault_vest(
        pokemon_name: str,
        spd_evs: int = 0,
        spd_ivs: int = 31,
        nature: str = "hardy"
    ) -> dict:
        """
        Calculate Assault Vest Special Defense boost.

        Assault Vest provides 1.5x Special Defense but prevents status moves.

        Args:
            pokemon_name: Pokemon name
            spd_evs: Special Defense EVs (0-252)
            spd_ivs: Special Defense IVs (0-31)
            nature: Nature (affects SpD if +/- SpD nature)

        Returns:
            SpD before and after Assault Vest, effective bulk increase
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            # Get nature modifier
            nature_data = await pokeapi.get_nature(nature)
            nature_mod = 1.0
            if nature_data:
                if nature_data.get("increased_stat", {}).get("name") == "special-defense":
                    nature_mod = 1.1
                elif nature_data.get("decreased_stat", {}).get("name") == "special-defense":
                    nature_mod = 0.9

            # Calculate SpD at level 50
            base_spd = stats.get("special-defense", 80)
            spd_stat = int(((2 * base_spd + spd_ivs + spd_evs // 4) * 50 // 100 + 5) * nature_mod)

            result = calculate_assault_vest_boost(spd_stat)

            boosted_spd = int(spd_stat * 1.5)

            return {
                "pokemon": pokemon_name,
                "item": "Assault Vest",
                "base_spd": base_spd,
                "spd_before": spd_stat,
                "spd_after": boosted_spd,
                "effective_bulk_increase": "50%",
                "description": result.description,
                "restrictions": result.notes,
                "commonly_blocked_moves": [
                    "Protect", "Substitute", "Taunt", "Thunder Wave",
                    "Will-O-Wisp", "Trick Room", "Tailwind"
                ]
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_choice_item(
        pokemon_name: str,
        item: str,
        evs: int = 252,
        ivs: int = 31,
        nature: str = "hardy"
    ) -> dict:
        """
        Calculate Choice item stat boost.

        Choice Band: 1.5x Attack (locked to one move)
        Choice Specs: 1.5x Special Attack (locked to one move)
        Choice Scarf: 1.5x Speed (locked to one move)

        Args:
            pokemon_name: Pokemon name
            item: "choice-band", "choice-specs", or "choice-scarf"
            evs: EVs in the relevant stat (0-252)
            ivs: IVs in the relevant stat (0-31)
            nature: Nature for stat calculation

        Returns:
            Stat before and after Choice item boost
        """
        try:
            item_lower = item.lower().replace(" ", "-")
            stat_map = {
                "choice-band": ("attack", "attack"),
                "choice-specs": ("special_attack", "special-attack"),
                "choice-scarf": ("speed", "speed"),
            }

            if item_lower not in stat_map:
                return error_response(
                    "invalid_item",
                    f"'{item}' is not a Choice item",
                    suggestions=["Use choice-band, choice-specs, or choice-scarf"]
                )

            stat_key, api_stat = stat_map[item_lower]

            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            # Get nature modifier
            nature_data = await pokeapi.get_nature(nature)
            nature_mod = 1.0
            if nature_data:
                if nature_data.get("increased_stat", {}).get("name") == api_stat:
                    nature_mod = 1.1
                elif nature_data.get("decreased_stat", {}).get("name") == api_stat:
                    nature_mod = 0.9

            base_stat = stats.get(api_stat, 80)

            # Calculate stat at level 50
            if stat_key == "speed":
                # Speed uses standard formula
                final_stat = int(((2 * base_stat + ivs + evs // 4) * 50 // 100 + 5) * nature_mod)
            else:
                # Attack/SpA use standard formula
                final_stat = int(((2 * base_stat + ivs + evs // 4) * 50 // 100 + 5) * nature_mod)

            result = calculate_choice_item_boost(item, final_stat)

            boosted_stat = int(final_stat * 1.5)

            return {
                "pokemon": pokemon_name,
                "item": item.replace("-", " ").title(),
                "stat_boosted": stat_key.replace("_", " ").title(),
                "base_stat": base_stat,
                "stat_before": final_stat,
                "stat_after": boosted_stat,
                "boost": "1.5x",
                "description": result.description,
                "drawback": "Locked into first move used until switching",
                "notes": result.notes
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_eviolite(
        pokemon_name: str,
        def_evs: int = 0,
        spd_evs: int = 0,
        def_ivs: int = 31,
        spd_ivs: int = 31,
        nature: str = "hardy"
    ) -> dict:
        """
        Calculate Eviolite defensive boosts for NFE Pokemon.

        Eviolite gives 1.5x Defense AND Special Defense to not-fully-evolved Pokemon.
        Common Eviolite users: Chansey, Porygon2, Dusclops

        Args:
            pokemon_name: NFE Pokemon name
            def_evs: Defense EVs (0-252)
            spd_evs: Special Defense EVs (0-252)
            def_ivs: Defense IVs (0-31)
            spd_ivs: Special Defense IVs (0-31)
            nature: Nature for stat modifiers

        Returns:
            Defensive stats before and after Eviolite, or error if fully evolved
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            # Get nature modifiers
            nature_data = await pokeapi.get_nature(nature)
            def_mod = 1.0
            spd_mod = 1.0
            if nature_data:
                if nature_data.get("increased_stat", {}).get("name") == "defense":
                    def_mod = 1.1
                elif nature_data.get("decreased_stat", {}).get("name") == "defense":
                    def_mod = 0.9
                if nature_data.get("increased_stat", {}).get("name") == "special-defense":
                    spd_mod = 1.1
                elif nature_data.get("decreased_stat", {}).get("name") == "special-defense":
                    spd_mod = 0.9

            base_def = stats.get("defense", 80)
            base_spd = stats.get("special-defense", 80)

            # Calculate stats at level 50
            final_def = int(((2 * base_def + def_ivs + def_evs // 4) * 50 // 100 + 5) * def_mod)
            final_spd = int(((2 * base_spd + spd_ivs + spd_evs // 4) * 50 // 100 + 5) * spd_mod)

            result = calculate_eviolite_boost(pokemon_name, final_def, final_spd)

            if not result.applies:
                return {
                    "pokemon": pokemon_name,
                    "item": "Eviolite",
                    "applies": False,
                    "reason": result.description,
                    "notes": result.notes,
                    "common_eviolite_users": ["Chansey", "Porygon2", "Dusclops", "Scyther", "Rhydon"]
                }

            boosted_def = int(final_def * 1.5)
            boosted_spd = int(final_spd * 1.5)

            return {
                "pokemon": pokemon_name,
                "item": "Eviolite",
                "applies": True,
                "defense_before": final_def,
                "defense_after": boosted_def,
                "spd_before": final_spd,
                "spd_after": boosted_spd,
                "boost": "1.5x to both Def and SpD",
                "description": result.description,
                "notes": result.notes
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def check_berry_activation_threshold(
        pokemon_name: str,
        berry: str,
        current_hp_percent: float = 100.0,
        hp_evs: int = 0,
        hp_ivs: int = 31
    ) -> dict:
        """
        Check when a berry would activate based on HP threshold.

        Sitrus Berry: Heals 25% HP when below 50%
        Pinch berries (Figy, Wiki, etc.): Heal 33% HP when below 25%
        Stat berries (Liechi, Petaya, etc.): +1 stat when below 25%

        Args:
            pokemon_name: Pokemon name (for HP calculation)
            berry: Berry name (sitrus, figy, liechi, etc.)
            current_hp_percent: Current HP as percentage (0-100)
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)

        Returns:
            Whether berry would activate and its effect
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            base_hp = stats.get("hp", 100)
            # HP calculation at level 50
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10
            current_hp = int(max_hp * current_hp_percent / 100)

            result = check_berry_activation(berry, current_hp, max_hp)

            if "error" in result:
                return error_response("unknown_berry", result["error"], suggestions=[
                    f"Supported berries: {', '.join(result.get('supported_berries', []))}"
                ])

            return {
                "pokemon": pokemon_name,
                "max_hp": max_hp,
                "current_hp": current_hp,
                **result,
                "hp_to_activate": int(max_hp * float(result["threshold"].replace("% HP", "")) / 100),
                "damage_needed_to_activate": current_hp - int(max_hp * float(result["threshold"].replace("% HP", "")) / 100)
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def check_focus_sash(
        pokemon_name: str,
        incoming_damage: int,
        hp_evs: int = 0,
        hp_ivs: int = 31,
        at_full_hp: bool = True
    ) -> dict:
        """
        Check if Focus Sash would save a Pokemon from an attack.

        Focus Sash prevents OHKO when at full HP, leaving 1 HP.
        Only works once, doesn't protect from multi-hit moves.

        Args:
            pokemon_name: Pokemon name
            incoming_damage: Damage amount from the attack
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)
            at_full_hp: Whether Pokemon is at full HP (sash requires this)

        Returns:
            Whether sash activates, HP remaining, and relevant notes
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10
            current_hp = max_hp if at_full_hp else max_hp - 1  # Simulate not full HP

            result = check_focus_sash_survival(incoming_damage, current_hp, max_hp)

            return {
                "pokemon": pokemon_name,
                "max_hp": max_hp,
                "current_hp": current_hp,
                **result,
                "overkill_damage": max(0, incoming_damage - max_hp) if result["sash_activates"] else 0,
                "tips": [
                    "Use Fake Out first to break Sash",
                    "Multi-hit moves bypass Focus Sash",
                    "Weather/status chip breaks Sash condition",
                    "Stealth Rock on switch-in can break Sash"
                ] if result["sash_activates"] else []
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def calculate_life_orb_damage(
        pokemon_name: str,
        base_damage: int,
        hp_evs: int = 0,
        hp_ivs: int = 31
    ) -> dict:
        """
        Calculate Life Orb damage boost and recoil.

        Life Orb: 1.3x damage dealt, costs 10% max HP per attack.

        Args:
            pokemon_name: Pokemon name (for HP/recoil calculation)
            base_damage: Damage the move would deal without Life Orb
            hp_evs: HP EVs (0-252)
            hp_ivs: HP IVs (0-31)

        Returns:
            Boosted damage, recoil amount, and how many attacks before fainting to recoil
        """
        try:
            stats = await pokeapi.get_pokemon_stats(pokemon_name)
            if not stats:
                return error_response("pokemon_not_found", f"Could not find Pokemon: {pokemon_name}")

            base_hp = stats.get("hp", 100)
            max_hp = (2 * base_hp + hp_ivs + hp_evs // 4) * 50 // 100 + 50 + 10

            result = calculate_life_orb_effect(base_damage, max_hp)

            attacks_before_faint = max_hp // result["recoil"]

            return {
                "pokemon": pokemon_name,
                "max_hp": max_hp,
                **result,
                "attacks_before_faint_to_recoil": attacks_before_faint,
                "note": "Sheer Force prevents recoil on moves with secondary effects",
                "magic_guard_note": "Magic Guard prevents Life Orb recoil entirely"
            }

        except Exception as e:
            return error_response("calculation_error", str(e))

    @mcp.tool()
    async def get_item_damage_boost(
        item: str,
        move_category: str = "physical",
        is_super_effective: bool = False,
        consecutive_uses: int = 1
    ) -> dict:
        """
        Get the damage multiplier for a held item.

        Args:
            item: Item name (life-orb, expert-belt, muscle-band, etc.)
            move_category: "physical" or "special" (for Muscle Band/Wise Glasses)
            is_super_effective: Whether move is super effective (for Expert Belt)
            consecutive_uses: For Metronome item, how many times move used in a row

        Returns:
            Damage multiplier and conditions
        """
        is_physical = move_category.lower() == "physical"

        multiplier = get_item_damage_modifier(
            item,
            is_physical=is_physical,
            is_super_effective=is_super_effective,
            consecutive_uses=consecutive_uses
        )

        item_info = {
            "life-orb": {
                "multiplier": 1.3,
                "condition": "Always",
                "drawback": "10% HP recoil per attack"
            },
            "expert-belt": {
                "multiplier": 1.2,
                "condition": "Only on super effective moves",
                "drawback": "None"
            },
            "muscle-band": {
                "multiplier": 1.1,
                "condition": "Physical moves only",
                "drawback": "None"
            },
            "wise-glasses": {
                "multiplier": 1.1,
                "condition": "Special moves only",
                "drawback": "None"
            },
            "metronome": {
                "multiplier": min(2.0, 1.0 + (consecutive_uses - 1) * 0.2),
                "condition": f"Using same move consecutively ({consecutive_uses}x)",
                "drawback": "Resets on different move or switch"
            },
            "choice-band": {
                "multiplier": 1.5,
                "condition": "Attack stat boost (physical moves)",
                "drawback": "Locked to one move"
            },
            "choice-specs": {
                "multiplier": 1.5,
                "condition": "Sp. Atk stat boost (special moves)",
                "drawback": "Locked to one move"
            },
        }

        normalized = item.lower().replace(" ", "-")
        info = item_info.get(normalized, {
            "multiplier": 1.0,
            "condition": "Unknown or no damage boost",
            "drawback": "N/A"
        })

        return {
            "item": item,
            "damage_multiplier": multiplier,
            "effective_multiplier": multiplier,
            "condition": info["condition"],
            "drawback": info["drawback"],
            "applies_to_current": multiplier > 1.0,
            "note": "Expert Belt only applies if super effective" if normalized == "expert-belt" and not is_super_effective else None
        }
