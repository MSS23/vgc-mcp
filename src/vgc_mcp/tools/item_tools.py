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

from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.calc.items import (
    PARADOX_POKEMON,
    calculate_assault_vest_boost,
    calculate_booster_energy_boost,
    calculate_choice_item_boost,
    calculate_eviolite_boost,
    calculate_life_orb_effect,
    check_berry_activation,
    check_focus_sash_survival,
    get_item_damage_modifier,
)
from vgc_mcp_core.utils.errors import error_response


def register_item_tools(mcp: FastMCP, pokeapi: PokeAPIClient):
    """Register item calculation tools."""

    @mcp.tool(
        title="Calculate Booster Energy Boost",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_booster_energy(
        pokemon_name: Annotated[str, Field(
            description="Paradox Pokemon name (e.g. 'flutter-mane', 'iron-hands')",
            min_length=1,
        )],
        nature: Annotated[str, Field(description="Nature for stat modifiers (default: hardy/neutral)")] = "hardy",
    ) -> dict:
        """Calculate the Booster Energy stat boost for a Paradox Pokemon.

        Booster Energy activates Protosynthesis (past) or Quark Drive (future)
        to boost the highest stat by 30% (or 50% for Speed). Returns which stat
        gets boosted and by how much, or an error if the Pokemon is not Paradox.
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

    @mcp.tool(
        title="Calculate Assault Vest Boost",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_assault_vest(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Special Defense EVs (0-252)")] = 0,
        spd_ivs: Annotated[int, Field(ge=0, le=31, description="Special Defense IVs (0-31)")] = 31,
        nature: Annotated[str, Field(description="Nature (affects SpD if +/- SpD nature)")] = "hardy",
    ) -> dict:
        """Calculate the Assault Vest Special Defense boost.

        Assault Vest provides 1.5x Special Defense but prevents status moves.
        Returns SpD before/after the boost and the effective bulk increase.
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

    @mcp.tool(
        title="Calculate Choice Item Boost",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_choice_item(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        item: Annotated[str, Field(
            description="'choice-band' (1.5x Attack), 'choice-specs' (1.5x SpA), or 'choice-scarf' (1.5x Speed)",
            min_length=1,
        )],
        evs: Annotated[int, Field(ge=0, le=252, description="EVs in the boosted stat (0-252)")] = 252,
        ivs: Annotated[int, Field(ge=0, le=31, description="IVs in the boosted stat (0-31)")] = 31,
        nature: Annotated[str, Field(description="Nature for the stat calculation")] = "hardy",
    ) -> dict:
        """Calculate a Choice item's 1.5x stat boost.

        Returns the relevant stat before and after the boost, plus the
        move-lock drawback.
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

    @mcp.tool(
        title="Calculate Eviolite Boost",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_eviolite(
        pokemon_name: Annotated[str, Field(
            description="Not-fully-evolved Pokemon name (e.g. 'porygon2', 'dusclops', 'chansey')",
            min_length=1,
        )],
        def_evs: Annotated[int, Field(ge=0, le=252, description="Defense EVs (0-252)")] = 0,
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Special Defense EVs (0-252)")] = 0,
        def_ivs: Annotated[int, Field(ge=0, le=31, description="Defense IVs (0-31)")] = 31,
        spd_ivs: Annotated[int, Field(ge=0, le=31, description="Special Defense IVs (0-31)")] = 31,
        nature: Annotated[str, Field(description="Nature for stat modifiers")] = "hardy",
    ) -> dict:
        """Calculate Eviolite defensive boosts for a not-fully-evolved Pokemon.

        Eviolite gives 1.5x Defense AND Special Defense to NFE Pokemon. Returns
        both stats before/after, or explains why it does not apply when the
        Pokemon is fully evolved.
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

    @mcp.tool(
        title="Check Berry Activation Threshold",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_berry_activation_threshold(
        pokemon_name: Annotated[str, Field(description="Pokemon name (for max HP calculation)", min_length=1)],
        berry: Annotated[str, Field(
            description="Berry name (e.g. 'sitrus', 'figy', 'liechi')",
            min_length=1,
        )],
        current_hp_percent: Annotated[float, Field(ge=0, le=100, description="Current HP as a percentage (0-100)")] = 100.0,
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252)")] = 0,
        hp_ivs: Annotated[int, Field(ge=0, le=31, description="HP IVs (0-31)")] = 31,
    ) -> dict:
        """Check when a berry would activate based on its HP threshold.

        Sitrus heals 25% HP below 50%; pinch berries (Figy, Wiki, ...) heal 33%
        below 25%; stat berries (Liechi, Petaya, ...) grant +1 below 25%.
        Returns whether the berry activates now and how much damage is needed
        to reach the threshold.
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

    @mcp.tool(
        title="Check Focus Sash Survival",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_focus_sash(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        incoming_damage: Annotated[int, Field(ge=0, description="Damage amount from the attack")],
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252)")] = 0,
        hp_ivs: Annotated[int, Field(ge=0, le=31, description="HP IVs (0-31)")] = 31,
        at_full_hp: Annotated[bool, Field(
            description="Whether the Pokemon is at full HP (Focus Sash only activates at full HP)",
        )] = True,
    ) -> dict:
        """Check if Focus Sash would save a Pokemon from an attack.

        Focus Sash prevents an OHKO at full HP, leaving 1 HP; it only works once
        and doesn't protect against multi-hit moves. Returns whether the sash
        activates, HP remaining, and sash-breaking tips.
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

    @mcp.tool(
        title="Calculate Life Orb Damage and Recoil",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_life_orb_damage(
        pokemon_name: Annotated[str, Field(description="Pokemon name (for HP/recoil calculation)", min_length=1)],
        base_damage: Annotated[int, Field(ge=0, description="Damage the move would deal without Life Orb")],
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252)")] = 0,
        hp_ivs: Annotated[int, Field(ge=0, le=31, description="HP IVs (0-31)")] = 31,
    ) -> dict:
        """Calculate the Life Orb damage boost and recoil cost.

        Life Orb deals 1.3x damage at the cost of 10% max HP per attack.
        Returns the boosted damage, recoil per attack, and attacks before
        fainting to recoil.
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

    @mcp.tool(
        title="Get Item Damage Multiplier",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_item_damage_boost(
        item: Annotated[str, Field(
            description="Item name (e.g. 'life-orb', 'expert-belt', 'muscle-band', 'metronome')",
            min_length=1,
        )],
        move_category: Annotated[str, Field(
            description="'physical' or 'special' (relevant for Muscle Band/Wise Glasses)",
        )] = "physical",
        is_super_effective: Annotated[bool, Field(
            description="Whether the move is super effective (relevant for Expert Belt)",
        )] = False,
        consecutive_uses: Annotated[int, Field(
            ge=1,
            description="For the Metronome item: how many times the move has been used in a row",
        )] = 1,
    ) -> dict:
        """Get the damage multiplier a held item applies to a move.

        Returns the multiplier, its activation condition, and any drawback
        (static item data; no network lookup).
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
