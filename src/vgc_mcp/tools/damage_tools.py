"""MCP tools for damage calculations."""

import logging
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.conversion import ev_to_sp, evs_to_sps_spread
from vgc_mcp_core.calc.damage import (
    calculate_bulk_threshold,
    calculate_damage,
    calculate_ko_threshold,
    format_percent,
)
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.pokemon import (
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
    get_nature_modifier,
)
from vgc_mcp_core.rules.format_detect import detect_champions_format
from vgc_mcp_core.tools.smogon_helpers import (
    get_common_spread as _shared_get_common_spread,
)
from vgc_mcp_core.tools.smogon_helpers import (
    get_common_spreads as _shared_get_common_spreads,
)
from vgc_mcp_core.utils.errors import (
    ErrorCodes,
    api_error,
    error_response,
    invalid_nature_error,
    pokemon_not_found_error,
)
from vgc_mcp_core.utils.fuzzy import suggest_nature, suggest_pokemon_name
from vgc_mcp_core.utils.normalize import (
    normalize_smogon_name as _normalize_smogon_name,  # noqa: F401  (re-exported for back-compat)
)

# Module-level Smogon client reference (set during registration)
_smogon_client: Optional[SmogonStatsClient] = None


logger = logging.getLogger(__name__)


async def _get_common_spreads(pokemon_name: str, limit: int = 3) -> list[dict]:
    """Module-local wrapper — passes the registered Smogon client through."""
    return await _shared_get_common_spreads(_smogon_client, pokemon_name, limit)


async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Module-local wrapper — passes the registered Smogon client through."""
    return await _shared_get_common_spread(_smogon_client, pokemon_name)


def _detect_champions(*pokemon_names: str) -> bool:
    """Return True when the active format resolves to Champions (Reg MA).

    Read-only: an explicit session regulation wins, otherwise the format is
    INFERRED from the mentioned Pokemon without mutating session state (a plain
    damage calc must not silently rewrite a mainline user's session).
    """
    return detect_champions_format(*pokemon_names)


def _sps_from_smogon_spread(spread: dict) -> Optional[StatPointSpread]:
    """Build a StatPointSpread from a Champions Smogon spread dict.

    Wave-1's smogon helper carries `sps` (canonical-stat-name dict) +
    `format_system` alongside `evs`. Returns None when the spread isn't a
    champions spread or has no SP data.
    """
    if spread.get("format_system") != "champions":
        return None
    sps = spread.get("sps")
    if not sps:
        return None
    return StatPointSpread.from_sps_dict(sps)


def format_transparent_output(
    attacker: PokemonBuild,
    defender: PokemonBuild,
    move,
    damage_result,
    modifiers_applied: list[str],
    calculation_steps: Optional[list[dict]] = None
) -> str:
    """Generate transparent markdown output showing full calculation.

    Args:
        attacker: Attacking Pokemon build
        defender: Defending Pokemon build
        move: Move object
        damage_result: DamageResult from calculate_damage
        modifiers_applied: List of modifier strings
        calculation_steps: Optional list of calculation step dicts

    Returns:
        Formatted markdown string with full calculation breakdown
    """
    from vgc_mcp_core.calc.stats import calculate_all_stats

    # Calculate final stats for both Pokemon
    attacker_stats = calculate_all_stats(attacker)
    defender_stats = calculate_all_stats(defender)

    # Format nature string
    def format_nature(nature: Nature) -> str:
        if nature == Nature.SERIOUS:
            return "Serious"
        plus_stat = nature.value.split("_")[0].title()
        minus_stat = nature.value.split("_")[1].title() if "_" in nature.value else ""
        if minus_stat:
            return f"{plus_stat} (+{plus_stat}, -{minus_stat})"
        return plus_stat

    # Get stat abbreviations
    def get_stat_abbrev(stat_name: str) -> str:
        abbrevs = {
            "hp": "HP", "attack": "Atk", "defense": "Def",
            "special_attack": "SpA", "special_defense": "SpD", "speed": "Spe"
        }
        return abbrevs.get(stat_name, stat_name.title())

    lines = []
    lines.append("## Damage Calculation\n")

    # Attacker section
    lines.append(f"### Attacker: {attacker.name}")
    lines.append("| Stat | HP | Atk | Def | SpA | SpD | Spe |")
    lines.append("|------|-----|-----|-----|-----|-----|-----|")

    # Base stats
    base_line = "| Base |"
    for stat in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
        base_line += f" {attacker.base_stats.__dict__[stat]} |"
    lines.append(base_line)

    # EVs / SPs (Champions builds invest Stat Points, not EVs)
    atk_alloc = attacker.sps if attacker.is_champions() else attacker.evs
    ev_line = ("| SPs  |" if attacker.is_champions() else "| EVs  |")
    for stat in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
        ev_value = (atk_alloc.__dict__.get(stat, 0) if atk_alloc else 0)
        ev_line += f" {ev_value} |"
    lines.append(ev_line)

    # Final stats
    final_line = "| Final|"
    for stat in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
        final_line += f" {attacker_stats[stat]} |"
    lines.append(final_line)
    lines.append("")

    # Attacker details
    lines.append(f"**Nature:** {format_nature(attacker.nature)}")
    lines.append(f"**Item:** {attacker.item or 'None'}")
    lines.append(f"**Ability:** {attacker.ability or 'None'}")
    if attacker.tera_type:
        lines.append(f"**Tera:** {attacker.tera_type.title()} (Active)")
    else:
        lines.append("**Tera:** None")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Defender section
    lines.append(f"### Defender: {defender.name}")
    lines.append("| Stat | HP | Atk | Def | SpA | SpD | Spe |")
    lines.append("|------|-----|-----|-----|-----|-----|-----|")

    # Base stats
    base_line = "| Base |"
    for stat in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
        base_line += f" {defender.base_stats.__dict__[stat]} |"
    lines.append(base_line)

    # EVs / SPs (Champions builds invest Stat Points, not EVs)
    def_alloc = defender.sps if defender.is_champions() else defender.evs
    ev_line = ("| SPs  |" if defender.is_champions() else "| EVs  |")
    for stat in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
        ev_value = (def_alloc.__dict__.get(stat, 0) if def_alloc else 0)
        ev_line += f" {ev_value} |"
    lines.append(ev_line)

    # Final stats
    final_line = "| Final|"
    for stat in ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]:
        final_line += f" {defender_stats[stat]} |"
    lines.append(final_line)
    lines.append("")

    # Defender details
    lines.append(f"**Nature:** {format_nature(defender.nature)}")
    lines.append(f"**Item:** {defender.item or 'None'}")
    lines.append(f"**Ability:** {defender.ability or 'None'}")
    if defender.tera_type:
        lines.append(f"**Tera:** {defender.tera_type.title()} (Active)")
    else:
        lines.append("**Tera:** None")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Move section
    lines.append(f"### Move: {move.name}")
    lines.append("| Base Power | Type | Category | Accuracy |")
    lines.append("|------------|------|----------|----------|")
    accuracy_str = f"{move.accuracy}%" if move.accuracy else "—"
    lines.append(f"| {move.power} | {move.type.title()} | {move.category.value.title()} | {accuracy_str} |")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Calculation breakdown
    if calculation_steps:
        lines.append("### Calculation Breakdown")
        lines.append("| Step | Value | Notes |")
        lines.append("|------|-------|-------|")
        for step in calculation_steps:
            step_name = step.get("name", "")
            value = step.get("value", "")
            notes = step.get("notes", "")
            lines.append(f"| {step_name} | {value} | {notes} |")
        lines.append("")

    # Result section
    lines.append("### Result")
    lines.append("| Min | Max | % Range | HP After | Verdict |")
    lines.append("|-----|-----|---------|----------|---------|")

    hp_after_min = max(0, defender_stats["hp"] - damage_result.max_damage)
    hp_after_max = max(0, defender_stats["hp"] - damage_result.min_damage)

    verdict = damage_result.ko_chance
    if damage_result.is_guaranteed_ohko:
        verdict = "OHKO"
    elif damage_result.is_possible_ohko:
        verdict = f"{damage_result.ko_chance}"

    lines.append(f"| {damage_result.min_damage} | {damage_result.max_damage} | "
                f"{format_percent(damage_result.min_percent)}-{format_percent(damage_result.max_percent)}% | "
                f"{hp_after_min}-{hp_after_max} | {verdict} |")
    lines.append("")

    # Modifiers applied
    if modifiers_applied:
        lines.append("### Modifiers Applied")
        for mod in modifiers_applied:
            lines.append(f"- {mod}")

    return "\n".join(lines)


def register_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register damage calculation tools with the MCP server."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool(
        title="Calculate Damage Output",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_damage_output(
        attacker_name: Annotated[str, Field(description="Attacking Pokemon's name", min_length=1)],
        defender_name: Annotated[str, Field(description="Defending Pokemon's name", min_length=1)],
        move_name: Annotated[str, Field(description="Name of the move being used", min_length=1)],
        attacker_nature: Annotated[Optional[str], Field(description="Attacker's nature. If None and use_smogon_spreads=True, uses most common.")] = None,
        attacker_atk_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Attack EVs (0-252). If None and use_smogon_spreads=True, uses most common. Treated as Stat Points in Champions sessions.")] = None,
        attacker_spa_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Sp. Atk EVs (0-252). If None and use_smogon_spreads=True, uses most common. Treated as Stat Points in Champions sessions.")] = None,
        attacker_hp_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's HP EVs (0-252). Include for a complete custom spread.")] = None,
        attacker_def_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Defense EVs (0-252). Used when resolving Protosynthesis/Quark Drive's highest stat.")] = None,
        attacker_spd_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Sp. Def EVs (0-252). Used when resolving Protosynthesis/Quark Drive's highest stat.")] = None,
        attacker_spe_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Speed EVs (0-252). Used when resolving Protosynthesis/Quark Drive's highest stat.")] = None,
        defender_nature: Annotated[Optional[str], Field(description="Defender's nature. If None and use_smogon_spreads=True, uses most common.")] = None,
        defender_hp_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's HP EVs (0-252). If None and use_smogon_spreads=True, uses most common. Treated as Stat Points in Champions sessions.")] = None,
        defender_def_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Defense EVs (0-252). If None and use_smogon_spreads=True, uses most common. Treated as Stat Points in Champions sessions.")] = None,
        defender_spd_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Sp. Def EVs (0-252). If None and use_smogon_spreads=True, uses most common. Treated as Stat Points in Champions sessions.")] = None,
        defender_atk_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Attack EVs (0-252). Include for a complete custom spread.")] = None,
        defender_spa_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Sp. Atk EVs (0-252). Used when resolving Protosynthesis/Quark Drive's highest stat.")] = None,
        defender_spe_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Speed EVs (0-252). Used when resolving Protosynthesis/Quark Drive's highest stat.")] = None,
        attacker_sps: Annotated[Optional[str], Field(description="Champions (Reg MA) only. Attacker Stat Points as 'HP/Atk/Def/SpA/SpD/Spe' (0-32 per stat, 66 total). Ignored in mainline sessions. When the session is Champions and this is None, falls back to the attacker's EV params (treated as SP) or a Champions Smogon spread.")] = None,
        defender_sps: Annotated[Optional[str], Field(description="Champions (Reg MA) only. Defender Stat Points as 'HP/Atk/Def/SpA/SpD/Spe' (0-32 per stat, 66 total). Ignored in mainline sessions.")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="If True (default), auto-fetch common spreads from Smogon usage data")] = True,
        num_defender_spreads: Annotated[int, Field(ge=1, description="Number of top defender spreads to calculate against (default 3). Set to 1 for single spread.")] = 3,
        is_spread: Annotated[bool, Field(description="True if move is hitting multiple targets (0.75x damage)")] = False,
        weather: Annotated[Optional[str], Field(description="'sun', 'rain', 'sand', or 'snow' (affects Fire/Water moves)")] = None,
        terrain: Annotated[Optional[str], Field(description="'electric', 'grassy', 'psychic', or 'misty' (affects damage)")] = None,
        attacker_item: Annotated[Optional[str], Field(description="Item like 'life-orb', 'choice-band'. Auto-fetched if use_smogon_spreads=True.")] = None,
        defender_item: Annotated[Optional[str], Field(description="Defender's item like 'assault-vest', 'sitrus-berry'. Auto-fetched if use_smogon_spreads=True.")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability. Auto-detected if not specified.")] = None,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability. Auto-detected if not specified.")] = None,
        attacker_tera_type: Annotated[Optional[str], Field(description="Attacker's Tera type if Terastallized")] = None,
        defender_tera_type: Annotated[Optional[str], Field(description="Defender's Tera type if Terastallized")] = None,
        reflect: Annotated[bool, Field(description="True if Reflect is active (halves physical damage)")] = False,
        light_screen: Annotated[bool, Field(description="True if Light Screen is active (halves special damage)")] = False,
        helping_hand: Annotated[bool, Field(description="True if Helping Hand was used (1.5x damage)")] = False,
        commander_active: Annotated[bool, Field(description="True if attacking Dondozo has Commander active (Tatsugiri inside). Doubles offensive stat.")] = False,
        defender_commander_active: Annotated[bool, Field(description="True if defending Dondozo has Commander active. Doubles defensive stat.")] = False,
        beads_of_ruin: Annotated[bool, Field(description="True if Chi-Yu's Beads of Ruin is active (lowers foe SpD to 0.75x)")] = False,
        sword_of_ruin: Annotated[bool, Field(description="True if Chien-Pao's Sword of Ruin is active (lowers foe Def to 0.75x)")] = False,
        tablets_of_ruin: Annotated[bool, Field(description="True if Wo-Chien's Tablets of Ruin is active (lowers foe Atk to 0.75x)")] = False,
        vessel_of_ruin: Annotated[bool, Field(description="True if Ting-Lu's Vessel of Ruin is active (lowers foe SpA to 0.75x)")] = False,
        attacker_booster_energy: Annotated[Optional[bool], Field(description="Whether the attacker's Booster Energy activation is active. Omit to infer from a held Booster Energy; false explicitly disables the item trigger. Sun/electric terrain can still activate the ability.")] = None,
        defender_booster_energy: Annotated[Optional[bool], Field(description="Whether the defender's Booster Energy activation is active. Omit to infer from the held item; false explicitly disables the item trigger.")] = None,
        attacker_attack_stage: Annotated[int, Field(ge=-6, le=6, description="Attacker's Attack stage (-6 to +6). Use -1 for Intimidate.")] = 0,
        attacker_special_attack_stage: Annotated[int, Field(ge=-6, le=6, description="Attacker's Sp. Atk stage (-6 to +6)")] = 0,
        defender_defense_stage: Annotated[int, Field(ge=-6, le=6, description="Defender's Defense stage (-6 to +6)")] = 0,
        defender_special_defense_stage: Annotated[int, Field(ge=-6, le=6, description="Defender's Sp. Def stage (-6 to +6)")] = 0,
        aurora_veil: Annotated[bool, Field(description="True if Aurora Veil is active (halves both physical and special damage)")] = False,
        friend_guard: Annotated[bool, Field(description="True if ally has Friend Guard ability (reduces damage to 0.75x)")] = False,
        defender_starting_hp_percent: Annotated[float, Field(description="Defender's HP at the moment of the hit (0.1-100). Use this to model prior chip damage — e.g. 90.0 if defender has taken one Life Orb chip (10%), 75.0 if it lost a Sitrus to a previous hit. Affects KO computation only; damage rolls themselves are unchanged.")] = 100.0,
        attacker_starting_hp_percent: Annotated[float, Field(description="Attacker's HP %, used only for Multiscale / Shadow Shield activation checks (these abilities halve damage at full HP). Default 100.0 (full HP).")] = 100.0,
    ) -> dict:
        """⭐ PRIMARY DAMAGE TOOL — use this for ANY damage / KO / survival question.

        USE THIS WHEN the user asks ANY of:
            - "Does X OHKO/2HKO/KO Y?"
            - "Can X survive Y?"
            - "Does this spread live Y after Tera/chip/screens/whatever?"
            - "What's the damage of X's move vs Y?"
            - "How much HP does Y have left after X's attack?"

        FULLY HANDLES: Tera (both sides), every item (Life Orb, Choice items,
        Assault Vest, Booster Energy, Sitrus Berry, Hearthflame Mask, etc.),
        every ability (Sheer Force, Intimidate, Multiscale, Ruin abilities,
        Adaptability, etc.), weather, terrain, screens (Reflect, Light Screen,
        Aurora Veil), Helping Hand, Friend Guard, stat stages, multi-hit moves,
        always-crit moves, spread-move 0.75x, and prior chip damage.

        DO NOT USE the simpler tools (`check_survival_benchmark`,
        `survive_multiple_hits`, `find_bulk_to_survive_hits`) unless the user
        is specifically asking about *finding spreads*, not computing damage.

        EXAMPLE — "Does Tera Normal Entei live Sheer Force LO Earth Power
        after 1 chip of LO damage?":
            calculate_damage_output(
                attacker_name="landorus", defender_name="entei",
                move_name="earth-power", attacker_item="life-orb",
                attacker_ability="sheer-force", defender_tera_type="normal",
                defender_starting_hp_percent=90.0,  # 1 chip = 10% lost
            )

        By default, uses the most common Smogon VGC spreads for both Pokemon when
        nature/EVs are not specified. Calculates against the top 3 defender spreads
        to show damage variance across common builds.

        Returns damage calculations against top defender spreads with KO
        probabilities and items. IMPORTANT: the response includes
        'attacker_spread' showing the exact spread used — always show this to
        the user so they know what nature/EVs/item were assumed ("252 Atk"
        notation means neutral nature; "252+ Atk" means boosting nature). When
        `defender_starting_hp_percent` < 100, the response also includes
        `survival_after_chip` describing whether the defender survives given
        the prior damage.
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

            # Champions (Reg MA) detection. When the session resolves to the
            # Stat-Point format we build PokemonBuilds with format_system=
            # 'champions' + a StatPointSpread (32/stat, 66 total) instead of EVs.
            is_champions = _detect_champions(attacker_name, defender_name)

            # Parse explicit SP inputs ("HP/Atk/Def/SpA/SpD/Spe"). These win over
            # any EV params / Smogon fetch when the session is Champions.
            def _parse_sp_string(s: Optional[str]) -> Optional[StatPointSpread]:
                if not s:
                    return None
                parts = [p.strip() for p in s.replace(",", "/").split("/")]
                if len(parts) != 6:
                    raise ValueError(
                        "Stat Points must be 'HP/Atk/Def/SpA/SpD/Spe' (six values)"
                    )
                vals = [int(p) for p in parts]
                return StatPointSpread(
                    hp=vals[0], attack=vals[1], defense=vals[2],
                    special_attack=vals[3], special_defense=vals[4], speed=vals[5],
                )

            attacker_sp_spread: Optional[StatPointSpread] = None
            defender_sp_spread: Optional[StatPointSpread] = None
            if is_champions:
                try:
                    attacker_sp_spread = _parse_sp_string(attacker_sps)
                    defender_sp_spread = _parse_sp_string(defender_sps)
                except ValueError as ve:
                    return error_response(ErrorCodes.INVALID_INPUT, str(ve))

            # Track what spreads we used for the response
            attacker_spread_source = "custom"
            defender_spread_source = "custom"
            attacker_spread_info = None
            defender_spread_info = None
            defender_spreads_list = []  # For multi-spread calculations

            # Auto-fetch Smogon spreads if enabled and values not provided
            if use_smogon_spreads:
                # Check if user manually specified ANY attacker EVs
                user_specified_attacker_evs = (
                    attacker_hp_evs is not None or
                    attacker_atk_evs is not None or
                    attacker_def_evs is not None or
                    attacker_spa_evs is not None or
                    attacker_spd_evs is not None or
                    attacker_spe_evs is not None
                )

                # Only fetch from Smogon if user didn't specify any EVs
                attacker_needs_spread = (
                    not user_specified_attacker_evs and
                    (attacker_nature is None or attacker_atk_evs is None or attacker_spa_evs is None)
                )
                if attacker_needs_spread:
                    atk_spread = await _get_common_spread(attacker_name)
                    if atk_spread:
                        attacker_spread_source = "smogon"
                        attacker_spread_info = atk_spread
                        # Add regulation info
                        if _smogon_client and _smogon_client.current_regulation_from_data:
                            attacker_spread_info["regulation"] = f"Reg {_smogon_client.current_regulation_from_data}"
                        if attacker_nature is None:
                            attacker_nature = atk_spread["nature"]
                        evs = atk_spread.get("evs", {})
                        if attacker_atk_evs is None:
                            attacker_atk_evs = evs.get("attack", 0)
                        if attacker_spa_evs is None:
                            attacker_spa_evs = evs.get("special_attack", 0)
                        if attacker_hp_evs is None:
                            attacker_hp_evs = evs.get("hp", 0)
                        if attacker_def_evs is None:
                            attacker_def_evs = evs.get("defense", 0)
                        if attacker_spd_evs is None:
                            attacker_spd_evs = evs.get("special_defense", 0)
                        if attacker_spe_evs is None:
                            attacker_spe_evs = evs.get("speed", 0)
                        # Champions: pull the Stat-Point allocation (smogon helper
                        # carries 'sps' + format_system) rather than the empty
                        # 'evs' dict.
                        if is_champions and attacker_sp_spread is None:
                            attacker_sp_spread = _sps_from_smogon_spread(atk_spread)
                        # Also use common item/ability if not specified
                        if attacker_item is None and atk_spread.get("item"):
                            attacker_item = _normalize_smogon_name(atk_spread["item"])
                        if attacker_ability is None and atk_spread.get("ability"):
                            attacker_ability = _normalize_smogon_name(atk_spread["ability"])

                # Check if user manually specified ANY defender EVs
                user_specified_defender_evs = (
                    defender_hp_evs is not None or
                    defender_atk_evs is not None or
                    defender_def_evs is not None or
                    defender_spa_evs is not None or
                    defender_spd_evs is not None or
                    defender_spe_evs is not None
                )

                # Only fetch from Smogon if user didn't specify any EVs
                defender_needs_spread = (
                    not user_specified_defender_evs and
                    (defender_nature is None or defender_hp_evs is None or
                     defender_def_evs is None or defender_spd_evs is None)
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
                        if defender_atk_evs is None:
                            defender_atk_evs = evs.get("attack", 0)
                        if defender_spa_evs is None:
                            defender_spa_evs = evs.get("special_attack", 0)
                        if defender_spe_evs is None:
                            defender_spe_evs = evs.get("speed", 0)
                        if is_champions and defender_sp_spread is None:
                            defender_sp_spread = _sps_from_smogon_spread(def_spread)
                        if defender_ability is None and def_spread.get("ability"):
                            defender_ability = _normalize_smogon_name(def_spread["ability"])
                        # Also get defender item from Smogon if not specified
                        if defender_item is None and def_spread.get("item"):
                            defender_item = _normalize_smogon_name(def_spread["item"])

            # Set defaults for any remaining None values
            attacker_nature = attacker_nature or "serious"
            attacker_hp_evs = attacker_hp_evs if attacker_hp_evs is not None else 0
            attacker_atk_evs = attacker_atk_evs if attacker_atk_evs is not None else 0
            attacker_def_evs = attacker_def_evs if attacker_def_evs is not None else 0
            attacker_spa_evs = attacker_spa_evs if attacker_spa_evs is not None else 0
            attacker_spd_evs = attacker_spd_evs if attacker_spd_evs is not None else 0
            attacker_spe_evs = attacker_spe_evs if attacker_spe_evs is not None else 0
            defender_nature = defender_nature or "serious"
            defender_hp_evs = defender_hp_evs if defender_hp_evs is not None else 0
            defender_atk_evs = defender_atk_evs if defender_atk_evs is not None else 0
            defender_def_evs = defender_def_evs if defender_def_evs is not None else 0
            defender_spa_evs = defender_spa_evs if defender_spa_evs is not None else 0
            defender_spd_evs = defender_spd_evs if defender_spd_evs is not None else 0
            defender_spe_evs = defender_spe_evs if defender_spe_evs is not None else 0

            # Champions fallback: if no SP spread was supplied or fetched, treat
            # the (possibly user-supplied) offensive/defensive EV integers as
            # Stat Points so callers who pass attacker_atk_evs etc. in a
            # Champions session still get an SP-scale build (capped at 32).
            if is_champions:
                if attacker_sp_spread is None:
                    attacker_sp_spread = StatPointSpread(
                        hp=ev_to_sp(attacker_hp_evs, round_mode="floor"),
                        attack=ev_to_sp(attacker_atk_evs, round_mode="floor"),
                        defense=ev_to_sp(attacker_def_evs, round_mode="floor"),
                        special_attack=ev_to_sp(attacker_spa_evs, round_mode="floor"),
                        special_defense=ev_to_sp(attacker_spd_evs, round_mode="floor"),
                        speed=ev_to_sp(attacker_spe_evs, round_mode="floor"),
                    )
                if defender_sp_spread is None:
                    defender_sp_spread = StatPointSpread(
                        hp=ev_to_sp(defender_hp_evs, round_mode="ceil"),
                        attack=ev_to_sp(defender_atk_evs, round_mode="floor"),
                        defense=ev_to_sp(defender_def_evs, round_mode="ceil"),
                        special_attack=ev_to_sp(defender_spa_evs, round_mode="floor"),
                        special_defense=ev_to_sp(defender_spd_evs, round_mode="ceil"),
                        speed=ev_to_sp(defender_spe_evs, round_mode="floor"),
                    )

            # Auto-fetch abilities if not specified — use Smogon-aware resolver
            # (Mega-form > Smogon's most-used > pokeapi first-listed) so VGC
            # builds get the right ability (e.g. Dragonite → Multiscale, not
            # pokeapi's first-listed Inner Focus).
            from vgc_mcp_core.tools.ability_helpers import resolve_ability
            if attacker_ability is None:
                attacker_ability, _ = await resolve_ability(
                    attacker_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                    use_smogon=use_smogon_spreads,
                )
            if defender_ability is None:
                defender_ability, _ = await resolve_ability(
                    defender_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                    use_smogon=use_smogon_spreads,
                )
            # Normalize both inferred and explicitly supplied values so the
            # tool-level ability routing and explanatory notes stay in sync
            # with the core calculator's normalized matching.
            if attacker_ability:
                attacker_ability = attacker_ability.lower().replace(" ", "-")
            if defender_ability:
                defender_ability = defender_ability.lower().replace(" ", "-")

            # Auto-detect Ruinous abilities from attacker/defender
            # Create temporary modifiers to use the helper function
            from vgc_mcp_core.calc.abilities import apply_ruin_abilities
            from vgc_mcp_core.calc.modifiers import DamageModifiers

            temp_modifiers = DamageModifiers(
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin,
                tablets_of_ruin=tablets_of_ruin,
                vessel_of_ruin=vessel_of_ruin
            )
            apply_ruin_abilities(
                attacker_ability=attacker_ability,
                defender_ability=defender_ability,
                modifiers=temp_modifiers
            )
            # Extract the updated values
            sword_of_ruin = temp_modifiers.sword_of_ruin
            beads_of_ruin = temp_modifiers.beads_of_ruin
            tablets_of_ruin = temp_modifiers.tablets_of_ruin
            vessel_of_ruin = temp_modifiers.vessel_of_ruin

            # Tri-state Booster Energy semantics: an omitted flag auto-detects
            # from the held item, while an explicit False must remain False.
            # This lets callers model an unactivated/already-spent item without
            # losing the held-item information in the returned build.
            if attacker_booster_energy is None:
                attacker_booster_energy = bool(
                    attacker_item
                    and attacker_item.lower().replace(" ", "-") == "booster-energy"
                )
            if defender_booster_energy is None:
                defender_booster_energy = bool(
                    defender_item
                    and defender_item.lower().replace(" ", "-") == "booster-energy"
                )

            # Helper function to determine which stat Protosynthesis/Quark Drive boosts
            def get_paradox_boost_stat(base_stats, nature_enum, evs_dict) -> Optional[str]:
                """Determine which stat gets boosted by Protosynthesis/Quark Drive.
                Boosts the highest stat (excluding HP). Speed gets 1.5x, others get 1.3x."""
                from vgc_mcp_core.calc.stats import calculate_speed, calculate_stat
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
                # Find highest stat - Speed takes priority when tied
                max_value = max(stats.values())
                tied_stats = [stat for stat, val in stats.items() if val == max_value]
                if "speed" in tied_stats:
                    return "speed"
                return tied_stats[0]

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

            # Create Pokemon builds. For Champions we attach a StatPointSpread +
            # format_system='champions'; mainline keeps the EVSpread path
            # byte-for-byte unchanged.
            if is_champions:
                attacker = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    format_system="champions",
                    sps=attacker_sp_spread or StatPointSpread(),
                    item=attacker_item,
                    ability=attacker_ability,
                    tera_type=attacker_tera_type
                )
                defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    format_system="champions",
                    sps=defender_sp_spread or StatPointSpread(),
                    ability=defender_ability,
                    tera_type=defender_tera_type
                )
            else:
                attacker = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    evs=EVSpread(
                        hp=attacker_hp_evs,
                        attack=attacker_atk_evs,
                        defense=attacker_def_evs,
                        special_attack=attacker_spa_evs,
                        special_defense=attacker_spd_evs,
                        speed=attacker_spe_evs,
                    ),
                    item=attacker_item,
                    ability=attacker_ability,
                    tera_type=attacker_tera_type
                )

                defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    evs=EVSpread(
                        hp=defender_hp_evs,
                        attack=defender_atk_evs,
                        defense=defender_def_evs,
                        special_attack=defender_spa_evs,
                        special_defense=defender_spd_evs,
                        speed=defender_spe_evs,
                    ),
                    ability=defender_ability,
                    tera_type=defender_tera_type
                )

            # Determine Protosynthesis/Quark Drive boost stats
            attacker_proto_boost = None
            attacker_quark_boost = None
            defender_proto_boost = None
            defender_quark_boost = None

            # Mainline: pre-compute the Paradox boost stat from EVs. Champions
            # builds let calculate_damage auto-detect the boost from the
            # format-aware stats (the EV ints are SP-scale here, so the mainline
            # formula would mis-pick) — leave the *_boost vars None.
            if not is_champions:
                # Check if attacker has Protosynthesis and conditions are met
                if attacker_ability == "protosynthesis":
                    if weather == "sun" or attacker_booster_energy:
                        attacker_proto_boost = get_paradox_boost_stat(
                            atk_base, atk_nature,
                            {
                                "attack": attacker_atk_evs,
                                "defense": attacker_def_evs,
                                "special_attack": attacker_spa_evs,
                                "special_defense": attacker_spd_evs,
                                "speed": attacker_spe_evs,
                            }
                        )

                # Check if attacker has Quark Drive and conditions are met
                if attacker_ability == "quark-drive":
                    if terrain == "electric" or attacker_booster_energy:
                        attacker_quark_boost = get_paradox_boost_stat(
                            atk_base, atk_nature,
                            {
                                "attack": attacker_atk_evs,
                                "defense": attacker_def_evs,
                                "special_attack": attacker_spa_evs,
                                "special_defense": attacker_spd_evs,
                                "speed": attacker_spe_evs,
                            }
                        )

                # Check if defender has Protosynthesis and conditions are met
                if defender_ability == "protosynthesis":
                    if weather == "sun" or defender_booster_energy:
                        defender_proto_boost = get_paradox_boost_stat(
                            def_base, def_nature,
                            {
                                "attack": defender_atk_evs,
                                "defense": defender_def_evs,
                                "special_attack": defender_spa_evs,
                                "special_defense": defender_spd_evs,
                                "speed": defender_spe_evs,
                            }
                        )

                # Check if defender has Quark Drive and conditions are met
                if defender_ability == "quark-drive":
                    if terrain == "electric" or defender_booster_energy:
                        defender_quark_boost = get_paradox_boost_stat(
                            def_base, def_nature,
                            {
                                "attack": defender_atk_evs,
                                "defense": defender_def_evs,
                                "special_attack": defender_spa_evs,
                                "special_defense": defender_spd_evs,
                                "speed": defender_spe_evs,
                            }
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
                attacker_booster_energy=attacker_booster_energy,
                defender_booster_energy=defender_booster_energy,
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

                    # Create defender build for this spread (SP-aware in Champions)
                    if is_champions:
                        spread_defender = PokemonBuild(
                            name=defender_name,
                            base_stats=def_base,
                            types=def_types,
                            nature=spread_nature_enum,
                            format_system="champions",
                            # Prefer the threat's champions-tagged SP spread; otherwise
                            # convert its real mainline Smogon EVs to the SP grain so its
                            # bulk is preserved (NOT zeroed out).
                            sps=_sps_from_smogon_spread(spread_data) or evs_to_sps_spread(
                                EVSpread(
                                    hp=spread_evs.get("hp", 0),
                                    defense=spread_evs.get("defense", 0),
                                    special_defense=spread_evs.get("special_defense", 0),
                                )
                            ),
                            item=spread_item,
                            ability=spread_ability,
                            tera_type=defender_tera_type
                        )
                    else:
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
                            ability=spread_ability,
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
                        attacker_booster_energy=attacker_booster_energy,
                        defender_booster_energy=defender_booster_energy,
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

            # Build calculation steps for transparent output
            calculation_steps = []
            details = result.details
            if details.get("base_power"):
                calculation_steps.append({
                    "name": "Base Power",
                    "value": str(details["base_power"]),
                    "notes": f"{move.name} base power"
                })
            if details.get("attacker_stat"):
                calculation_steps.append({
                    "name": "Attacker Stat",
                    "value": str(details["attacker_stat"]),
                    "notes": f"{'Atk' if move.category.value == 'physical' else 'SpA'} stat"
                })
            if details.get("defender_stat"):
                calculation_steps.append({
                    "name": "Defender Stat",
                    "value": str(details["defender_stat"]),
                    "notes": f"{'Def' if move.category.value == 'physical' else 'SpD'} stat"
                })

            # Build attacker EV string for top-level visibility. In a Champions
            # session the attacker carries a StatPointSpread (not EVs), so read
            # the real SP allocation instead of the empty EV spread.
            stat_abbrevs = [("hp", "HP"), ("attack", "Atk"), ("defense", "Def"),
                            ("special_attack", "SpA"), ("special_defense", "SpD"),
                            ("speed", "Spe")]
            if is_champions:
                atk_sps_dict = attacker.sps.model_dump() if attacker.sps else {}
                sp_parts = [f"{atk_sps_dict.get(stat, 0)} {abbrev}"
                            for stat, abbrev in stat_abbrevs
                            if atk_sps_dict.get(stat, 0) > 0]
                attacker_ev_string = ("SPs: " + " / ".join(sp_parts)) if sp_parts else "0 SPs"
            else:
                atk_evs_for_string = attacker_spread_info.get("evs", {}) if attacker_spread_info else {
                    "hp": attacker_hp_evs, "attack": attacker_atk_evs,
                    "defense": attacker_def_evs, "special_attack": attacker_spa_evs,
                    "special_defense": attacker_spd_evs, "speed": attacker_spe_evs
                }
                ev_parts = []
                for stat, abbrev in stat_abbrevs:
                    ev_val = atk_evs_for_string.get(stat, 0)
                    if ev_val > 0:
                        ev_parts.append(f"{ev_val} {abbrev}")
                attacker_ev_string = " / ".join(ev_parts) if ev_parts else "0 EVs"

            # Champions has no Terastallization — still compute, but flag it.
            champions_tera_warning = None
            if is_champions and (attacker_tera_type or defender_tera_type):
                champions_tera_warning = (
                    "Pokemon Champions (Reg MA/MB) has no Terastallization — "
                    "this calc applied Tera anyway because it was requested, "
                    "but it cannot happen in a real Champions battle."
                )

            # Build response
            response = {
                "attacker": attacker_name,
                # Top-level attacker info for LLM visibility
                "attacker_nature": attacker_nature.title(),
                "attacker_ev_spread": attacker_ev_string,
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
                "type_effectiveness": result.details.get("type_effectiveness", 1.0),
                "transparent_output": format_transparent_output(
                    attacker,
                    defender,
                    move,
                    result,
                    result.details.get("modifiers_applied", []),
                    calculation_steps
                )
            }

            if champions_tera_warning:
                response["champions_tera_warning"] = champions_tera_warning

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
                    "usage_percent": attacker_spread_info.get("usage", 0),
                    "regulation": attacker_spread_info.get("regulation")
                }
                # Add regulation to top-level response for visibility
                if attacker_spread_info.get("regulation"):
                    response["data_from"] = attacker_spread_info.get("regulation")

            # Always show defender spread info (even for custom spreads)
            response["defender_spread"] = {
                "source": defender_spread_source,
                "nature": defender_nature,
                "evs": {
                    "hp": defender_hp_evs,
                    "attack": defender_atk_evs,
                    "defense": defender_def_evs,
                    "special_attack": defender_spa_evs,
                    "special_defense": defender_spd_evs,
                    "speed": defender_spe_evs,
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

            def_evs_dict = {
                "hp": defender_hp_evs,
                "attack": defender_atk_evs,
                "defense": defender_def_evs,
                "special_attack": defender_spa_evs,
                "special_defense": defender_spd_evs,
                "speed": defender_spe_evs,
            }

            atk_tera_str = f" [Tera {attacker_tera_type.title()}]" if attacker_tera_type else ""
            def_tera_str = f" [Tera {defender_tera_type.title()}]" if defender_tera_type else ""

            # In Champions, show the SP allocation (e.g. "0/0/0/32/0/32 SP")
            # for both lines; mainline keeps the EV HP/Atk/Def/SpA/SpD/Spe form.
            if is_champions:
                atk_sp = attacker.sps.model_dump() if attacker.sps else {}
                def_sp = defender.sps.model_dump() if defender.sps else {}
                attacker_alloc_str = f"{_format_evs(atk_sp)} SP"
                defender_alloc_str = f"{_format_evs(def_sp)} SP"
            else:
                atk_evs_dict = attacker_spread_info.get("evs", {}) if attacker_spread_info else {
                    "hp": attacker_hp_evs,
                    "attack": attacker_atk_evs,
                    "defense": attacker_def_evs,
                    "special_attack": attacker_spa_evs,
                    "special_defense": attacker_spd_evs,
                    "speed": attacker_spe_evs,
                }
                attacker_alloc_str = _format_evs(atk_evs_dict)
                defender_alloc_str = _format_evs(def_evs_dict)

            response["condensed_summary"] = {
                "attacker_line": f"{attacker_name} ({attacker_nature.title()} {attacker_alloc_str}) @ {attacker_item or 'No item'} [{attacker_ability}]{atk_tera_str}",
                "defender_line": f"{defender_name} ({defender_nature.title()} {defender_alloc_str}) @ {defender_item or 'No item'} [{defender_ability}]{def_tera_str}",
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

            # Build descriptive spread strings for analysis (Showdown format).
            # In Champions, read the real SP allocation (and label it "SP") so the
            # analysis text doesn't claim "0 SpA" for a Pokemon with SP invested.
            is_physical = move.category.value == "physical"
            stat_name = "Atk" if is_physical else "SpA"
            if is_champions:
                atk_sp = attacker.sps.model_dump() if attacker.sps else {}
                def_sp = defender.sps.model_dump() if defender.sps else {}
                relevant_atk_evs = atk_sp.get("attack", 0) if is_physical else atk_sp.get("special_attack", 0)
                stat_unit = " SP"
                def_hp_disp = def_sp.get("hp", 0)
                relevant_def_evs = def_sp.get("defense", 0) if is_physical else def_sp.get("special_defense", 0)
            else:
                relevant_atk_evs = attacker_atk_evs if is_physical else attacker_spa_evs
                stat_unit = ""
                def_hp_disp = defender_hp_evs
                relevant_def_evs = defender_def_evs if is_physical else defender_spd_evs

            # Get nature modifiers for attacker
            atk_nature_mod = get_nature_modifier(atk_nature, "attack")
            spa_nature_mod = get_nature_modifier(atk_nature, "special_attack")

            # Build attacker spread string (e.g., "252+ Atk Mystic Water")
            nature_boost = "+" if (is_physical and atk_nature_mod > 1.0) or (not is_physical and spa_nature_mod > 1.0) else ""
            nature_penalty = "-" if (is_physical and atk_nature_mod < 1.0) or (not is_physical and spa_nature_mod < 1.0) else ""
            nature_indicator = nature_boost or nature_penalty
            item_str = f" {attacker_item.replace('-', ' ').title()}" if attacker_item else ""
            attacker_spread_str = f"{relevant_atk_evs}{stat_unit}{nature_indicator} {stat_name}{item_str} {attacker_name}"

            # Build defender spread string (e.g., "Impish 132 HP / 196 Def")
            def_stat_name = "Def" if is_physical else "SpD"
            defender_spread_str = f"{defender_nature.title()} {def_hp_disp} HP{stat_unit} / {relevant_def_evs} {def_stat_name}{stat_unit} {defender_name}"

            response["analysis"] = f"{attacker_spread_str}'s {move_name} vs {defender_spread_str}: {min_pct}-{max_pct}% ({hp_remain_min_pct}-{hp_remain_max_pct}% remaining). {result.ko_chance}."

            # Chip-aware survival check: if defender_starting_hp_percent < 100,
            # compute survival against the reduced HP pool. Damage rolls don't
            # change — we just count how many rolls KO the chip-reduced HP.
            if 0 < defender_starting_hp_percent < 100:
                effective_hp = max(1, int(round(result.defender_hp * defender_starting_hp_percent / 100)))
                rolls = result.rolls or [result.min_damage] * 8 + [result.max_damage] * 8
                kos = sum(1 for r in rolls if r >= effective_hp)
                survives_n = len(rolls) - kos
                survival_pct = round(survives_n / len(rolls) * 100, 2) if rolls else 0.0

                if kos == 0:
                    chip_verdict = (f"Survives every roll ({survival_pct}%) — defender at "
                                    f"{defender_starting_hp_percent}% HP has {effective_hp} HP "
                                    f"vs max {result.max_damage} damage.")
                elif kos == len(rolls):
                    chip_verdict = (f"Guaranteed KO at {defender_starting_hp_percent}% starting HP — "
                                    f"every roll ({result.min_damage}+) clears the {effective_hp} HP pool.")
                else:
                    chip_verdict = (f"{survival_pct}% survival at {defender_starting_hp_percent}% "
                                    f"starting HP ({survives_n}/{len(rolls)} rolls). "
                                    f"Effective HP: {effective_hp}, damage range: "
                                    f"{result.min_damage}-{result.max_damage}.")

                response["survival_after_chip"] = {
                    "starting_hp_percent": defender_starting_hp_percent,
                    "effective_hp": effective_hp,
                    "survives_rolls": survives_n,
                    "ko_rolls": kos,
                    "total_rolls": len(rolls),
                    "survival_percent": survival_pct,
                    "verdict": chip_verdict,
                }

            # Add Showdown paste format for both Pokemon
            attacker.ability = attacker_ability
            defender.ability = defender_ability
            defender.item = defender_item
            response["attacker_showdown_paste"] = pokemon_build_to_showdown(attacker)
            response["defender_showdown_paste"] = pokemon_build_to_showdown(defender)

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

    @mcp.tool(
        title="Find KO EVs",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_ko_evs(
        attacker_name: Annotated[str, Field(description="Attacking Pokemon", min_length=1)],
        defender_name: Annotated[str, Field(description="Defending Pokemon", min_length=1)],
        move_name: Annotated[str, Field(description="Move being used", min_length=1)],
        attacker_nature: Annotated[str, Field(description="Attacker's nature (use +Atk or +SpA for best results)")] = "modest",
        defender_nature: Annotated[str, Field(description="Defender's nature")] = "calm",
        defender_hp_evs: Annotated[int, Field(ge=0, le=252, description="Defender's HP EVs (typically 252 for max bulk); Stat Points 0-32 in Champions sessions")] = 252,
        defender_def_evs: Annotated[int, Field(ge=0, le=252, description="Defender's Def/SpD EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        target_ko_chance: Annotated[float, Field(ge=0, le=100, description="Target KO probability percent (100 = guaranteed OHKO)")] = 100.0,
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (auto-filled with signature item if None)")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability — overrides auto-detection. Engine auto-applies offensive abilities (Sheer Force, Tough Claws, Adaptability, Iron Fist, etc.) and static stages (Intrepid Sword, Embody Aspect on Tera, Booster Energy / sun / electric-terrain Paradox boosts).")] = None,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability — overrides auto-detection. Auto-applies defensive abilities (Multiscale, Ice Scales, Thick Fat, Filter, etc.).")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch ability defaults from Smogon (default True)")] = True,
    ) -> dict:
        """Find minimum offensive EVs needed to achieve a certain KO probability.

        In Champions (Reg MA) sessions the attacker sweeps Stat Points instead
        and the response carries 'sps_needed'. Returns the required offensive
        investment, the resulting damage calculation, resolved attacker/defender
        abilities, and a Showdown paste with the required allocation.
        """
        try:
            # Fetch data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            # Resolve abilities (mega-form > Smogon > pokeapi). Stamping
            # attacker.ability lets the engine apply offensive ability
            # multipliers (Sheer Force, Tough Claws, Adaptability, Aerilate,
            # Iron Fist, Reckless, Sniper, Stakeout, Steely Spirit, Punk Rock,
            # Mega Launcher, Strong Jaw, Tinted Lens, Sand Force, Solar Power,
            # Hustle, Huge Power, Pure Power, Defeatist, etc.). Stamping
            # defender.ability lets the engine apply defensive resistances
            # (Multiscale, Ice Scales, Thick Fat, Fluffy, Filter/Solid Rock,
            # Levitate, Heatproof, type absorption, Wonder Guard, etc.).
            from vgc_mcp_core.tools.ability_helpers import resolve_ability
            attacker_ability, attacker_ability_source = await resolve_ability(
                attacker_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=attacker_ability, use_smogon=use_smogon_spreads,
            )
            defender_ability, defender_ability_source = await resolve_ability(
                defender_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=defender_ability, use_smogon=use_smogon_spreads,
            )
            atk_norm = (attacker_ability or "").lower().replace(" ", "-")
            sword_of_ruin = atk_norm == "sword-of-ruin"
            beads_of_ruin = atk_norm == "beads-of-ruin"

            # Parse natures
            atk_nature = Nature(attacker_nature.lower())
            def_nature = Nature(defender_nature.lower())

            # Champions (Reg MA) detection — when active the attacker sweeps Stat
            # Points (0-32) and calculate_ko_threshold returns 'sps_needed'.
            # Detect from the SUBJECT (the attacker being optimized), not the
            # opposing defender, so a Mega/Reg-MA opponent can't flip the format.
            is_champions = _detect_champions(attacker_name)

            # Auto-fill signature items
            if attacker_item is None:
                from vgc_mcp_core.calc.items import get_signature_item
                sig_item = get_signature_item(attacker_name)
                if sig_item:
                    attacker_item = sig_item

            # Create builds — abilities stamped so the engine auto-applies them.
            # The attacker's offensive allocation is what the threshold solver
            # sweeps, so it starts empty (EVSpread / StatPointSpread).
            if is_champions:
                attacker = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    format_system="champions",
                    sps=StatPointSpread(),
                    item=attacker_item,
                    ability=attacker_ability,
                )
                defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    format_system="champions",
                    sps=StatPointSpread(
                        hp=ev_to_sp(defender_hp_evs, round_mode="ceil"),
                        defense=ev_to_sp(defender_def_evs, round_mode="ceil") if move.category.value == "physical" else 0,
                        special_defense=ev_to_sp(defender_def_evs, round_mode="ceil") if move.category.value == "special" else 0,
                    ),
                    ability=defender_ability,
                )
            else:
                attacker = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    evs=EVSpread(),
                    item=attacker_item,
                    ability=attacker_ability,
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
                    ),
                    ability=defender_ability,
                )

            # Create modifiers with Ruinous abilities + ability/item bridge
            modifiers = DamageModifiers(
                is_doubles=True,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability,
            )

            result = calculate_ko_threshold(
                attacker, defender, move,
                modifiers=modifiers,
                target_ko_chance=target_ko_chance
            )

            # Unit label: Champions invests Stat Points (cap 32), mainline EVs.
            units_label = "Stat Points" if is_champions else "EVs"
            cap_text = "32 SP" if is_champions else "252 EVs"

            if result is None:
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Attacker         | {attacker_name}                            |",
                    f"| Defender         | {defender_name}                            |",
                    f"| Move             | {move_name}                                |",
                    f"| Target KO        | {target_ko_chance}%                        |",
                    f"| Result           | Not achievable with {cap_text}             |",
                ]
                return {
                    "attacker": attacker_name,
                    "defender": defender_name,
                    "move": move_name,
                    "achievable": False,
                    "message": f"Cannot achieve {target_ko_chance}% OHKO with {cap_text}. Consider items, Tera, or different move.",
                    "summary_table": "\n".join(table_lines)
                }

            # Wave-1 calc returns 'sps_needed' for champions, 'evs_needed' otherwise.
            units_needed = result.get("sps_needed", result.get("evs_needed"))
            # calculate_ko_threshold's stat_name is the full canonical name.
            is_atk_stat = result["stat_name"] == "attack"
            short_stat = "Atk" if is_atk_stat else "SpA"

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
                f"| Required {units_label:<9}| {units_needed} {short_stat} |",
                f"| Damage Range     | {result['damage_range']}                   |",
                f"| KO Chance        | {result['ko_chance']:.2f}%                 |",
            ]

            # Generate Showdown paste for attacker with the required allocation.
            if is_champions:
                ko_sps = StatPointSpread(
                    attack=units_needed if is_atk_stat else 0,
                    special_attack=0 if is_atk_stat else units_needed,
                )
                attacker_pokemon = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    format_system="champions",
                    sps=ko_sps,
                    ability=attacker_ability,
                    item=attacker_item,
                )
            else:
                attacker_pokemon = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    evs=EVSpread(
                        attack=units_needed if is_atk_stat else 0,
                        special_attack=0 if is_atk_stat else units_needed,
                    ),
                    ability=attacker_ability,
                    item=attacker_item,
                )
            attacker_showdown = pokemon_build_to_showdown(attacker_pokemon)

            response = {
                "attacker": attacker_name,
                "attacker_ability": attacker_ability.replace("-", " ").title() if attacker_ability else None,
                "attacker_ability_source": attacker_ability_source,
                "defender": defender_name,
                "defender_ability": defender_ability.replace("-", " ").title() if defender_ability else None,
                "defender_ability_source": defender_ability_source,
                "defender_spread": defender_spread_str,
                "move": move_name,
                "achievable": True,
                "stat": result["stat_name"],
                "units": units_label,
                "ko_chance": f"{result['ko_chance']:.2f}%",
                "damage_range": result["damage_range"],
                "attacker_showdown_paste": attacker_showdown,
                "summary_table": "\n".join(table_lines),
                "analysis": f"Need {units_needed} {short_stat} {units_label} to {result['ko_chance']:.0f}% OHKO {defender_spread_str} with {move_name}"
            }
            # Preserve the original unit-specific key (mainline) and add the SP key.
            if is_champions:
                response["sps_needed"] = units_needed
            else:
                response["evs_needed"] = units_needed
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

    @mcp.tool(
        title="Find Survival EVs",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_survival_evs(
        attacker_name: Annotated[str, Field(description="The Pokemon attacking you (e.g. 'Urshifu-Rapid-Strike')", min_length=1)],
        defender_name: Annotated[str, Field(description="YOUR Pokemon that needs to survive", min_length=1)],
        move_name: Annotated[str, Field(description="The attack to survive (e.g. 'Surging Strikes')", min_length=1)],
        attacker_nature: Annotated[Optional[str], Field(description="Attacker's nature (auto-fetched from Smogon if not provided)")] = None,
        attacker_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's offensive EVs (auto-fetched from Smogon if not provided)")] = None,
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (auto-fetched from Smogon if not provided)")] = None,
        defender_nature: Annotated[str, Field(description="Your Pokemon's nature (default: Calm for SpD, use Impish for Def)")] = "calm",
        target_survival_chance: Annotated[float, Field(ge=0, le=100, description="Survival %: 93.75 (15/16 rolls, survive max damage only) is RECOMMENDED — minimal EVs; 87.5 = can die to 2 highest rolls; 100 = guaranteed survival (wastes EVs)")] = 93.75,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch attacker spread from Smogon (default True)")] = True,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability. Auto-detected if not specified (Mega forms resolve to their post-mega ability, e.g. Mega Manectric → Intimidate).")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability — overrides auto-detection")] = None,
        apply_defender_intimidate: Annotated[bool, Field(description="If True (default), automatically applies the defender's Intimidate (-1 attacker Atk for physical moves), accounting for attacker blockers (Clear Body, Inner Focus, etc.) and punishers (Defiant, Contrary). Set False to ignore Intimidate (e.g. simulating a turn after switch-in).")] = True
    ) -> dict:
        """Find minimum HP/Defense EVs needed to SURVIVE a specific attack.

        Default behavior (93.75% survival) survives the MAXIMUM damage roll but
        not necessarily the absolute minimum roll — optimal for competitive
        play, leaving more EVs for offense, speed, or other stats.

        USE THIS TOOL when user asks:
        - "What EVs to survive X?"
        - "Can my Pokemon survive Y?"
        - "How much bulk/HP do I need?"
        - "What spread survives Z?"

        This tool auto-fetches the attacker's Smogon spread (nature, EVs, item)
        unless you specify them manually. Always show the attacker_spread_info
        in your response so the user knows what spread was used.

        Returns the required HP/Def EVs, the damage calculation, and full
        attacker spread info.
        """
        try:
            # Fetch data
            atk_base = await pokeapi.get_base_stats(attacker_name)
            def_base = await pokeapi.get_base_stats(defender_name)
            atk_types = await pokeapi.get_pokemon_types(attacker_name)
            def_types = await pokeapi.get_pokemon_types(defender_name)
            move = await pokeapi.get_move(move_name, user_name=attacker_name)

            is_physical = move.category.value == "physical"

            # Champions (Reg MA) detection — defender invests Stat Points, and
            # calculate_bulk_threshold returns 'hp_sps'/'def_sps'. Detect from the
            # SUBJECT (the defender being optimized), not the attacking threat.
            is_champions = _detect_champions(defender_name)
            attacker_sp_spread: Optional[StatPointSpread] = None

            # Track attacker spread info for output
            attacker_spread_info = {
                "pokemon": attacker_name,
                "source": "custom"
            }
            attacker_full_evs = {}
            # User-supplied attacker_ability wins over Smogon auto-fetch.
            attacker_ability_name = attacker_ability

            # Auto-fetch Smogon spread if enabled and not fully specified
            if use_smogon_spreads and (attacker_nature is None or attacker_evs is None or attacker_item is None):
                atk_spread = await _get_common_spread(attacker_name)
                if atk_spread:
                    attacker_spread_info["source"] = "smogon"
                    attacker_spread_info["usage_percent"] = atk_spread.get("usage", 0)
                    # Add regulation info from Smogon data
                    if _smogon_client and _smogon_client.current_regulation_from_data:
                        attacker_spread_info["regulation"] = f"Reg {_smogon_client.current_regulation_from_data}"

                    if attacker_nature is None:
                        attacker_nature = atk_spread["nature"]

                    evs = atk_spread.get("evs", {})
                    attacker_full_evs = evs
                    if attacker_evs is None:
                        # Use the relevant offensive stat EVs
                        attacker_evs = evs.get("attack", 0) if is_physical else evs.get("special_attack", 0)

                    # Champions: capture the attacker's Stat-Point allocation so
                    # the threat's damage is computed on the real SP investment.
                    if is_champions:
                        attacker_sp_spread = _sps_from_smogon_spread(atk_spread)

                    if attacker_item is None and atk_spread.get("item"):
                        attacker_item = _normalize_smogon_name(atk_spread["item"])
                        attacker_spread_info["item_usage_percent"] = atk_spread.get("item_usage", 0)

                    if atk_spread.get("ability") and attacker_ability_name is None:
                        # Don't overwrite an explicit user override with Smogon
                        attacker_ability_name = atk_spread["ability"]
                        attacker_spread_info["ability_usage_percent"] = atk_spread.get("ability_usage", 0)

            # Set defaults if still None (use neutral nature to match "252 Atk" notation)
            attacker_nature = attacker_nature or "serious"
            attacker_evs = attacker_evs if attacker_evs is not None else 252

            # Auto-detect Ruinous abilities from attacker
            sword_of_ruin = False
            beads_of_ruin = False
            atk_abilities = await pokeapi.get_pokemon_abilities(attacker_name)
            if atk_abilities:
                # Use Smogon ability if available, otherwise first ability
                ability_to_check = attacker_ability_name or atk_abilities[0]
                ability_normalized = ability_to_check.lower().replace(" ", "-")
                if attacker_ability_name is None:
                    attacker_ability_name = ability_to_check
                if ability_normalized == "sword-of-ruin":
                    sword_of_ruin = True
                elif ability_normalized == "beads-of-ruin":
                    beads_of_ruin = True

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

            def_nature = Nature(defender_nature.lower())

            # Build full EV spread for attacker display
            if not attacker_full_evs:
                attacker_full_evs = {
                    "hp": 0,
                    "attack": attacker_evs if is_physical else 0,
                    "defense": 0,
                    "special_attack": 0 if is_physical else attacker_evs,
                    "special_defense": 0,
                    "speed": 0
                }

            # Auto-detect Protosynthesis/Quark Drive from attacker ability + Booster Energy
            protosynthesis_boost = None
            quark_drive_boost = None
            if attacker_ability_name:
                ability_normalized = attacker_ability_name.lower().replace(" ", "-")
                if ability_normalized == "protosynthesis":
                    if attacker_item and attacker_item.lower().replace(" ", "-") == "booster-energy":
                        # Calculate which stat gets boosted (highest non-HP stat, Speed priority when tied)
                        from vgc_mcp_core.calc.stats import calculate_speed, calculate_stat
                        stats = {
                            "attack": calculate_stat(atk_base.attack, 31, attacker_full_evs.get("attack", 0), 50, get_nature_modifier(atk_nature, "attack")),
                            "defense": calculate_stat(atk_base.defense, 31, attacker_full_evs.get("defense", 0), 50, get_nature_modifier(atk_nature, "defense")),
                            "special_attack": calculate_stat(atk_base.special_attack, 31, attacker_full_evs.get("special_attack", 0), 50, get_nature_modifier(atk_nature, "special_attack")),
                            "special_defense": calculate_stat(atk_base.special_defense, 31, attacker_full_evs.get("special_defense", 0), 50, get_nature_modifier(atk_nature, "special_defense")),
                            "speed": calculate_speed(atk_base.speed, 31, attacker_full_evs.get("speed", 0), 50, get_nature_modifier(atk_nature, "speed")),
                        }
                        # Speed takes priority when tied
                        max_value = max(stats.values())
                        tied_stats = [stat for stat, val in stats.items() if val == max_value]
                        protosynthesis_boost = "speed" if "speed" in tied_stats else tied_stats[0]
                elif ability_normalized == "quark-drive":
                    if attacker_item and attacker_item.lower().replace(" ", "-") == "booster-energy":
                        from vgc_mcp_core.calc.stats import calculate_speed, calculate_stat
                        stats = {
                            "attack": calculate_stat(atk_base.attack, 31, attacker_full_evs.get("attack", 0), 50, get_nature_modifier(atk_nature, "attack")),
                            "defense": calculate_stat(atk_base.defense, 31, attacker_full_evs.get("defense", 0), 50, get_nature_modifier(atk_nature, "defense")),
                            "special_attack": calculate_stat(atk_base.special_attack, 31, attacker_full_evs.get("special_attack", 0), 50, get_nature_modifier(atk_nature, "special_attack")),
                            "special_defense": calculate_stat(atk_base.special_defense, 31, attacker_full_evs.get("special_defense", 0), 50, get_nature_modifier(atk_nature, "special_defense")),
                            "speed": calculate_speed(atk_base.speed, 31, attacker_full_evs.get("speed", 0), 50, get_nature_modifier(atk_nature, "speed")),
                        }
                        # Speed takes priority when tied
                        max_value = max(stats.values())
                        tied_stats = [stat for stat, val in stats.items() if val == max_value]
                        quark_drive_boost = "speed" if "speed" in tied_stats else tied_stats[0]

            # Auto-detect defender's ability so all defensive ability interactions
            # (Multiscale, Ice Scales, Thick Fat, Fluffy, Filter/Solid Rock, Heatproof,
            #  Levitate, Furry Coat, Prism Armor, Wonder Guard, type absorption like
            #  Flash Fire/Water Absorb/Volt Absorb/Sap Sipper/Storm Drain/Lightning
            #  Rod/Motor Drive/Dry Skin, etc.) flow through calculate_damage.
            from vgc_mcp_core.tools.ability_helpers import resolve_ability
            defender_ability, defender_ability_source = await resolve_ability(
                defender_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=defender_ability, use_smogon=use_smogon_spreads,
            )

            # Create builds — stamp abilities so the damage engine auto-applies
            # every offensive AND defensive ability interaction generically.
            # Champions builds use Stat Points; the defender starts empty so the
            # SP solver can sweep its allocation.
            if is_champions:
                if attacker_sp_spread is None:
                    # No Champions Smogon spread — fall back to treating the
                    # resolved offensive EV count as Stat Points (capped 32).
                    attacker_sp_spread = StatPointSpread(
                        attack=ev_to_sp(attacker_evs, round_mode="floor") if is_physical else 0,
                        special_attack=0 if is_physical else ev_to_sp(attacker_evs, round_mode="floor"),
                    )
                attacker = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    format_system="champions",
                    sps=attacker_sp_spread,
                    item=attacker_item,
                    ability=attacker_ability_name,
                )
                defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    format_system="champions",
                    sps=StatPointSpread(),
                    ability=defender_ability,
                )
            else:
                attacker = PokemonBuild(
                    name=attacker_name,
                    base_stats=atk_base,
                    types=atk_types,
                    nature=atk_nature,
                    evs=EVSpread(
                        hp=attacker_full_evs.get("hp", 0),
                        attack=attacker_full_evs.get("attack", attacker_evs if is_physical else 0),
                        defense=attacker_full_evs.get("defense", 0),
                        special_attack=attacker_full_evs.get("special_attack", 0 if is_physical else attacker_evs),
                        special_defense=attacker_full_evs.get("special_defense", 0),
                        speed=attacker_full_evs.get("speed", 0)
                    ),
                    item=attacker_item,
                    ability=attacker_ability_name,
                )

                defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    evs=EVSpread(),
                    ability=defender_ability,
                )

            from vgc_mcp_core.tools.ability_helpers import compute_intimidate_attack_stage
            attack_stage, intimidate_note = compute_intimidate_attack_stage(
                defender_ability=defender_ability,
                attacker_ability=attacker_ability_name,
                is_physical=is_physical,
                apply=apply_defender_intimidate,
            )

            # Create modifiers with Ruinous abilities, item, Paradox boosts, and Intimidate
            modifiers = DamageModifiers(
                is_doubles=True,
                sword_of_ruin=sword_of_ruin,
                beads_of_ruin=beads_of_ruin,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability_name,
                protosynthesis_boost=protosynthesis_boost,
                quark_drive_boost=quark_drive_boost,
                attack_stage=attack_stage,
            )

            result = calculate_bulk_threshold(
                attacker, defender, move,
                modifiers=modifiers,
                target_survival_chance=target_survival_chance
            )

            # Build attacker spread display strings
            ev_parts = []
            for stat, abbrev in [("hp", "HP"), ("attack", "Atk"), ("defense", "Def"),
                                  ("special_attack", "SpA"), ("special_defense", "SpD"), ("speed", "Spe")]:
                ev_val = attacker_full_evs.get(stat, 0)
                if ev_val > 0:
                    ev_parts.append(f"{ev_val} {abbrev}")
            ev_string = " / ".join(ev_parts) if ev_parts else "0 EVs"

            attacker_spread_info["nature"] = attacker_nature.title()
            attacker_spread_info["evs"] = attacker_full_evs
            attacker_spread_info["ev_string"] = ev_string
            attacker_spread_info["item"] = attacker_item.replace("-", " ").title() if attacker_item else None
            attacker_spread_info["ability"] = attacker_ability_name.replace("-", " ").title() if attacker_ability_name else None

            # Build short attacker spread string for display
            attacker_spread_str = f"{attacker_nature.title()} {ev_string}"
            if attacker_item:
                attacker_spread_str += f" @ {attacker_item.replace('-', ' ').title()}"

            if result is None:
                table_lines = [
                    "| Metric           | Value                                      |",
                    "|------------------|---------------------------------------------|",
                    f"| Attacker         | {attacker_name}                            |",
                    f"| Attacker Nature  | {attacker_nature.title()}                  |",
                    f"| Attacker Spread  | {ev_string}                                |",
                    f"| Attacker Item    | {attacker_item.replace('-', ' ').title() if attacker_item else 'None'} |",
                    f"| Move             | {move_name}                                |",
                    f"| Defender         | {defender_name}                            |",
                    f"| Defender Ability | {defender_ability.replace('-', ' ').title() if defender_ability else 'Unknown'} |",
                    f"| Target Survival  | {target_survival_chance}%                  |",
                    "| Result           | Not achievable with max investment         |",
                ]
                if intimidate_note:
                    table_lines.append(f"| Intimidate       | {intimidate_note}                          |")
                return {
                    "attacker": attacker_name,
                    # Top-level attacker info for LLM visibility
                    "attacker_item": attacker_item.replace("-", " ").title() if attacker_item else "None",
                    "attacker_nature": attacker_nature.title(),
                    "attacker_ev_spread": ev_string,
                    "attacker_ability": attacker_ability_name.replace("-", " ").title() if attacker_ability_name else None,
                    "attacker_spread": attacker_spread_info,
                    "defender": defender_name,
                    "defender_ability": defender_ability.replace("-", " ").title() if defender_ability else None,
                    "intimidate_applied": intimidate_note is not None and attack_stage != 0,
                    "intimidate_note": intimidate_note,
                    "move": move_name,
                    "achievable": False,
                    "message": "Cannot survive this attack with max investment. Consider items, Tera typing, or screens.",
                    "summary_table": "\n".join(table_lines)
                }

            # Normalize the solver result into format-agnostic locals. Wave-1's
            # calculate_bulk_threshold returns 'hp_sps'/'def_sps' for champions
            # defenders, 'hp_evs'/'def_evs' for mainline. Mainline output is kept
            # byte-for-byte: it still labels with the raw calc def_stat_name + "EVs".
            if is_champions:
                hp_units = result["hp_sps"]
                def_units = result["def_sps"]
                units_label = "Stat Points"
                units_short = "SP"
                # Champions uses the canonical short label for clarity.
                def_stat_table_label = "Def" if result["def_stat_name"] == "defense" else "SpD"
            else:
                hp_units = result["hp_evs"]
                def_units = result["def_evs"]
                units_label = "EVs"
                units_short = "EVs"
                def_stat_table_label = result["def_stat_name"]

            # Build summary table with full attacker info
            total_units = hp_units + def_units
            table_lines = [
                "| Metric           | Value                                      |",
                "|------------------|---------------------------------------------|",
                f"| Attacker         | {attacker_name}                            |",
                f"| Attacker Nature  | {attacker_nature.title()}                  |",
                f"| Attacker Spread  | {ev_string}                                |",
                f"| Attacker Item    | {attacker_item.replace('-', ' ').title() if attacker_item else 'None'} |",
                f"| Attacker Ability | {attacker_ability_name.replace('-', ' ').title() if attacker_ability_name else 'Unknown'} |",
                f"| Move             | {move_name}                                |",
                f"| Your Pokemon     | {defender_name}                            |",
                f"| HP {units_short} Needed    | {hp_units}                         |",
                f"| {def_stat_table_label} {units_short} Needed   | {def_units}                         |",
                f"| Total {units_short}        | {total_units}                                |",
                f"| Damage Range     | {result['damage_range']}                   |",
                f"| Survival Rate    | {result['survival_chance']:.2f}%           |",
            ]

            # Add source info if from Smogon
            if attacker_spread_info["source"] == "smogon":
                usage = attacker_spread_info.get("usage_percent", 0)
                reg = attacker_spread_info.get("regulation", "")
                reg_str = f" [{reg}]" if reg else ""
                table_lines.append(f"| Spread Source    | Smogon ({usage:.1f}% usage){reg_str}        |")

            # Surface defender ability + Intimidate handling
            if defender_ability:
                table_lines.append(
                    f"| Defender Ability | {defender_ability.replace('-', ' ').title()}                  |"
                )
            if intimidate_note:
                table_lines.append(f"| Intimidate       | {intimidate_note}                          |")

            # Build analysis string with explicit attacker and defender info.
            item_str = f" with {attacker_item.replace('-', ' ').title()}" if attacker_item else ""

            # Recommended defender export. Champions builds emit a StatPointSpread
            # ('SPs:' paste); mainline keeps the EVSpread path byte-for-byte.
            is_def_physical = result["def_stat_name"] == "defense"
            if is_champions:
                defender_ev_str = f"{hp_units} HP / {def_units} {def_stat_table_label} SP"
                recommended_defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    format_system="champions",
                    sps=StatPointSpread(
                        hp=hp_units,
                        defense=def_units if is_def_physical else 0,
                        special_defense=0 if is_def_physical else def_units,
                    ),
                    ability=defender.ability,
                    item=defender.item,
                    tera_type=defender.tera_type
                )
            else:
                defender_ev_str = f"{result['hp_evs']} HP / {result['def_evs']} {result['def_stat_name']}"
                defender_evs_dict = {
                    "hp": result["hp_evs"],
                    "defense": result["def_evs"] if result["def_stat_name"] == "Def" else 0,
                    "special_defense": result["def_evs"] if result["def_stat_name"] == "SpD" else 0,
                }
                recommended_defender = PokemonBuild(
                    name=defender_name,
                    base_stats=def_base,
                    types=def_types,
                    nature=def_nature,
                    evs=EVSpread(**defender_evs_dict),
                    ability=defender.ability,
                    item=defender.item,
                    tera_type=defender.tera_type
                )
            defender_showdown_paste = pokemon_build_to_showdown(recommended_defender)

            response = {
                "attacker": attacker_name,
                # Top-level attacker info for LLM visibility
                "attacker_item": attacker_item.replace("-", " ").title() if attacker_item else "None",
                "attacker_nature": attacker_nature.title(),
                "attacker_ev_spread": ev_string,
                "attacker_ability": attacker_ability_name.replace("-", " ").title() if attacker_ability_name else None,
                "attacker_spread": attacker_spread_info,
                "defender": defender_name,
                # Top-level defender info for LLM visibility
                "defender_nature": defender_nature.title(),
                "defender_ability": defender_ability.replace("-", " ").title() if defender_ability else None,
                "defender_ability_source": defender_ability_source,
                "defender_recommended_spread": defender_ev_str,
                "defender_showdown_paste": defender_showdown_paste,
                "intimidate_applied": intimidate_note is not None and attack_stage != 0,
                "intimidate_note": intimidate_note,
                "move": move_name,
                "achievable": True,
                "def_stat": result["def_stat_name"],
                "units": units_label,
                "survival_chance": f"{result['survival_chance']:.2f}%",
                "damage_range": result["damage_range"],
                "summary_table": "\n".join(table_lines),
                "analysis": (
                    f"{defender_name} needs {defender_ev_str} EVs ({defender_nature.title()}) to survive {move_name} from "
                    f"{attacker_nature.title()} {ev_string}{item_str} {attacker_name} — takes {result['damage_range']} "
                    f"({result['survival_chance']:.1f}% survival = {int(result['survival_chance'] * 16 / 100)}/16 rolls). "
                    f"{'This is the MINIMUM EVs to survive max damage roll.' if result['survival_chance'] < 95 else 'Guaranteed survival against all damage rolls.'}"
                ) if not is_champions else (
                    f"{defender_name} needs {defender_ev_str} ({defender_nature.title()}) to survive {move_name} from "
                    f"{attacker_nature.title()} {ev_string}{item_str} {attacker_name} — takes {result['damage_range']} "
                    f"({result['survival_chance']:.1f}% survival = {int(result['survival_chance'] * 16 / 100)}/16 rolls). "
                    f"{'This is the MINIMUM Stat Points to survive max damage roll.' if result['survival_chance'] < 95 else 'Guaranteed survival against all damage rolls.'}"
                )
            }
            # Preserve original mainline unit-specific keys; add SP keys for champions.
            if is_champions:
                response["hp_sps_needed"] = hp_units
                response["def_sps_needed"] = def_units
            else:
                response["hp_evs_needed"] = hp_units
                response["def_evs_needed"] = def_units

            # Add regulation to top-level response for visibility
            if attacker_spread_info.get("regulation"):
                response["data_from"] = attacker_spread_info["regulation"]

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

    @mcp.tool(
        title="Survive Multiple Hits",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def survive_multiple_hits(
        attacker_name: Annotated[str, Field(description="Attacking Pokemon's name", min_length=1)],
        defender_name: Annotated[str, Field(description="Defending Pokemon's name (your Pokemon)", min_length=1)],
        move_name: Annotated[str, Field(description="Move being used repeatedly", min_length=1)],
        num_hits: Annotated[int, Field(ge=1, description="Number of hits to survive (default 2)")] = 2,
        attacker_nature: Annotated[Optional[str], Field(description="Attacker's nature (auto-fetched from Smogon if None)")] = None,
        attacker_atk_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Attack EVs (auto-fetched from Smogon if None)")] = None,
        attacker_spa_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Attacker's Sp. Atk EVs (auto-fetched from Smogon if None)")] = None,
        defender_nature: Annotated[Optional[str], Field(description="Defender's nature (auto-fetched from Smogon if None)")] = None,
        defender_hp_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's HP EVs (auto-fetched from Smogon if None)")] = None,
        defender_def_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Defense EVs (auto-fetched from Smogon if None)")] = None,
        defender_spd_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Sp. Def EVs (auto-fetched from Smogon if None)")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch spreads from Smogon")] = True,
        attacker_attack_stage: Annotated[int, Field(ge=-6, le=6, description="Attack/Sp.Atk stage (-6 to +6). Stacks additively with auto-applied defender Intimidate (-1) when apply_defender_intimidate=True.")] = 0,
        defender_defense_stage: Annotated[int, Field(ge=-6, le=6, description="Defense/Sp.Def stage (-6 to +6). Use -1 for Screech, etc.")] = 0,
        weather: Annotated[Optional[str], Field(description="'sun', 'rain', 'sand', or 'snow'")] = None,
        terrain: Annotated[Optional[str], Field(description="'electric', 'grassy', 'psychic', or 'misty'")] = None,
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (auto-fetched if None)")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability — overrides auto-detection. Engine auto-applies offensive abilities (Sheer Force, Tough Claws, Adaptability, Aerilate, Iron Fist, etc.) and static stages (Intrepid Sword +1 Atk, Embody Aspect on Tera, Booster Energy / sun / electric-terrain Paradox boosts).")] = None,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability — overrides auto-detection (mega-form > Smogon > pokeapi). Auto-applies defensive abilities (Multiscale, Ice Scales, Thick Fat, Filter, Levitate, type absorption, etc.).")] = None,
        apply_defender_intimidate: Annotated[bool, Field(description="If True (default), defender Intimidate auto-drops the attacker's Atk by -1 for physical moves (with Defiant/Contrary punishment and Clear Body / Inner Focus blocking handled correctly).")] = True,
        reflect: Annotated[bool, Field(description="True if Reflect is active")] = False,
        light_screen: Annotated[bool, Field(description="True if Light Screen is active")] = False,
        aurora_veil: Annotated[bool, Field(description="True if Aurora Veil is active")] = False,
        friend_guard: Annotated[bool, Field(description="True if ally has Friend Guard ability")] = False
    ) -> dict:
        """Calculate if a Pokemon can survive multiple hits of an attack.

        Useful for scenarios like "Can Ogerpon survive 2 Close Combats from Urshifu?"
        Note: Close Combat drops the ATTACKER's defenses, not the defender's,
        so each hit does the same damage to the defender.

        Returns an analysis of whether the defender survives N hits, including
        resolved attacker/defender abilities and any Intimidate note.
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

            # Set defaults (use neutral nature to match "252 Atk" notation)
            attacker_nature = attacker_nature or "serious"
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

            is_physical = move.category.value == "physical"

            # Resolve abilities so all offensive/defensive ability interactions
            # (Sheer Force, Tough Claws, Adaptability, Multiscale, Ice Scales,
            # Thick Fat, Filter, Levitate, Flash Fire, etc.) flow through the
            # damage engine. Intimidate is computed as a stage event below.
            from vgc_mcp_core.tools.ability_helpers import (
                compute_intimidate_attack_stage,
                resolve_ability,
            )
            attacker_ability, attacker_ability_source = await resolve_ability(
                attacker_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=attacker_ability, use_smogon=use_smogon_spreads,
            )
            defender_ability, defender_ability_source = await resolve_ability(
                defender_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=defender_ability, use_smogon=use_smogon_spreads,
            )
            intimidate_stage, intimidate_note = compute_intimidate_attack_stage(
                defender_ability=defender_ability,
                attacker_ability=attacker_ability,
                is_physical=is_physical,
                apply=apply_defender_intimidate,
            )

            # Create builds — stamp abilities so the engine auto-applies them.
            attacker = PokemonBuild(
                name=attacker_name,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature,
                evs=EVSpread(attack=attacker_atk_evs, special_attack=attacker_spa_evs),
                item=attacker_item,
                ability=attacker_ability,
            )

            defender = PokemonBuild(
                name=defender_name,
                base_stats=def_base,
                types=def_types,
                nature=def_nature,
                evs=EVSpread(hp=defender_hp_evs, defense=defender_def_evs, special_defense=defender_spd_evs),
                ability=defender_ability,
            )

            # Set up modifiers with attack stage (caller-supplied stage stacks
            # with defender Intimidate's auto-detected -1).
            effective_attack_stage = attacker_attack_stage + (intimidate_stage if is_physical else 0)
            effective_spa_stage = attacker_attack_stage if not is_physical else 0
            modifiers = DamageModifiers(
                is_doubles=True,
                weather=weather,
                terrain=terrain,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability,
                reflect_up=reflect,
                light_screen_up=light_screen,
                aurora_veil_up=aurora_veil,
                friend_guard=friend_guard,
                attack_stage=effective_attack_stage if is_physical else 0,
                special_attack_stage=effective_spa_stage,
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
                f"| Per Hit          | {min_per_hit}-{max_per_hit} ({format_percent(min_percent_per_hit)}-{format_percent(max_percent_per_hit)}%) |",
                f"| Total Damage     | {total_min}-{total_max} ({format_percent(total_min_percent)}-{format_percent(total_max_percent)}%) |",
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
                    "min_percent": f"{format_percent(min_percent_per_hit)}%",
                    "max_percent": f"{format_percent(max_percent_per_hit)}%"
                },
                "total_damage": {
                    "min": total_min,
                    "max": total_max,
                    "min_percent": f"{format_percent(total_min_percent)}%",
                    "max_percent": f"{format_percent(total_max_percent)}%"
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
                "attacker_ability": attacker_ability.replace("-", " ").title() if attacker_ability else None,
                "attacker_ability_source": attacker_ability_source,
                "defender_spread": {
                    "nature": defender_nature,
                    "hp_evs": defender_hp_evs,
                    "def_evs": defender_def_evs,
                    "spd_evs": defender_spd_evs
                },
                "defender_ability": defender_ability.replace("-", " ").title() if defender_ability else None,
                "defender_ability_source": defender_ability_source,
                "intimidate_applied": intimidate_note is not None and intimidate_stage != 0,
                "intimidate_note": intimidate_note,
                "summary_table": "\n".join(table_lines),
                "analysis": analysis_str
            }

            notes = []
            if attacker_attack_stage == -1:
                notes.append("Caller-supplied attacker_attack_stage=-1")
            elif attacker_attack_stage < 0:
                notes.append(f"Caller-supplied attacker_attack_stage={attacker_attack_stage}")
            if intimidate_note:
                notes.append(intimidate_note)
            if notes:
                response["notes"] = notes

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

    @mcp.tool(
        title="Find Bulk to Survive Hits",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_bulk_to_survive_hits(
        attacker_name: Annotated[str, Field(description="Attacking Pokemon", min_length=1)],
        defender_name: Annotated[str, Field(description="Defending Pokemon (your Pokemon)", min_length=1)],
        move_name: Annotated[str, Field(description="Move to survive", min_length=1)],
        num_hits: Annotated[int, Field(ge=1, description="Number of hits to survive (default 2)")] = 2,
        attacker_nature: Annotated[str, Field(description="Attacker's nature")] = "adamant",
        attacker_evs: Annotated[int, Field(ge=0, le=252, description="Attacker's offensive EVs")] = 252,
        defender_nature: Annotated[str, Field(description="Your nature (+Def: Impish/Bold, +SpD: Calm/Careful)")] = "impish",
        attacker_attack_stage: Annotated[int, Field(ge=-6, le=6, description="Attack stage (-6 to +6). Use -1 for manual Intimidate override; defender Intimidate is auto-applied unless apply_defender_intimidate=False.")] = 0,
        defender_defense_stage: Annotated[int, Field(ge=-6, le=6, description="Defense stage (-6 to +6). Use -1 for Screech, etc.")] = 0,
        reflect: Annotated[bool, Field(description="True if Reflect is active")] = False,
        light_screen: Annotated[bool, Field(description="True if Light Screen is active")] = False,
        aurora_veil: Annotated[bool, Field(description="True if Aurora Veil is active")] = False,
        friend_guard: Annotated[bool, Field(description="True if ally has Friend Guard ability")] = False,
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (auto-fetched signature item if None)")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability — overrides auto-detection. The damage engine auto-applies offensive abilities (Sheer Force, Tough Claws, Adaptability, Aerilate, Iron Fist, Reckless, Sniper, Stakeout, Steely Spirit, Punk Rock, Mega Launcher, Strong Jaw, Tinted Lens, Sand Force, Solar Power, Hustle, Huge Power, Pure Power, Defeatist, etc.) and static stat-stage events (Intrepid Sword +1 Atk, Embody Aspect on Tera, Booster Energy / sun / electric-terrain Paradox boosts).")] = None,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability — overrides auto-detection (mega-form > Smogon > pokeapi). Auto-applies defensive abilities (Multiscale, Ice Scales, Thick Fat, Fluffy, Filter, Levitate, type absorption, etc.).")] = None,
        apply_defender_intimidate: Annotated[bool, Field(description="If True (default), defender Intimidate auto-drops the attacker's Atk by -1 for physical moves (with Defiant/Contrary punishment and Clear Body / Inner Focus blocking handled correctly).")] = True,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch attacker spread from Smogon (default True)")] = True,
    ) -> dict:
        """Find minimum HP/Def EVs to survive multiple hits of an attack.

        Returns the required HP/Def EVs to survive, or an indication that it is
        impossible, including resolved attacker/defender abilities and any
        Intimidate note.
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

            # Resolve abilities so offensive (Sheer Force, Tough Claws,
            # Adaptability, Aerilate, etc.) AND defensive (Multiscale, Ice
            # Scales, Thick Fat, Fluffy, Filter, Levitate, type absorption)
            # interactions all flow through calculate_damage.
            from vgc_mcp_core.tools.ability_helpers import (
                compute_intimidate_attack_stage,
                resolve_ability,
            )
            attacker_ability, attacker_ability_source = await resolve_ability(
                attacker_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=attacker_ability, use_smogon=use_smogon_spreads,
            )
            defender_ability, defender_ability_source = await resolve_ability(
                defender_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                user_override=defender_ability, use_smogon=use_smogon_spreads,
            )
            intimidate_stage, intimidate_note = compute_intimidate_attack_stage(
                defender_ability=defender_ability,
                attacker_ability=attacker_ability,
                is_physical=is_physical,
                apply=apply_defender_intimidate,
            )

            # Auto-fill signature items if needed.
            if attacker_item is None:
                from vgc_mcp_core.calc.items import get_signature_item
                sig_item = get_signature_item(attacker_name)
                if sig_item:
                    attacker_item = sig_item

            attacker = PokemonBuild(
                name=attacker_name,
                base_stats=atk_base,
                types=atk_types,
                nature=atk_nature,
                evs=EVSpread(
                    attack=attacker_evs if is_physical else 0,
                    special_attack=0 if is_physical else attacker_evs
                ),
                item=attacker_item,
                ability=attacker_ability,
            )

            effective_attack_stage = attacker_attack_stage + (intimidate_stage if is_physical else 0)

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
                        evs=test_evs,
                        ability=defender_ability,
                    )

                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attack_stage=effective_attack_stage if is_physical else 0,
                        special_attack_stage=attacker_attack_stage if not is_physical else 0,
                        defense_stage=defender_defense_stage if is_physical else 0,
                        special_defense_stage=defender_defense_stage if not is_physical else 0,
                        reflect_up=reflect,
                        light_screen_up=light_screen,
                        aurora_veil_up=aurora_veil,
                        friend_guard=friend_guard,
                        attacker_item=attacker_item,
                        attacker_ability=attacker_ability,
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
                    evs=EVSpread(hp=252, defense=252 if is_physical else 0, special_defense=0 if is_physical else 252),
                    ability=defender_ability,
                )
                modifiers = DamageModifiers(
                    is_doubles=True,
                    attack_stage=effective_attack_stage if is_physical else 0,
                    special_attack_stage=attacker_attack_stage if not is_physical else 0,
                    defense_stage=defender_defense_stage if is_physical else 0,
                    special_defense_stage=defender_defense_stage if not is_physical else 0,
                    reflect_up=reflect,
                    light_screen_up=light_screen,
                    aurora_veil_up=aurora_veil,
                    friend_guard=friend_guard,
                    attacker_item=attacker_item,
                    attacker_ability=attacker_ability,
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
                    "| Result           | Cannot survive                             |",
                ]

                return {
                    "attacker": attacker_name,
                    "attacker_ability": attacker_ability.replace("-", " ").title() if attacker_ability else None,
                    "attacker_ability_source": attacker_ability_source,
                    "defender": defender_name,
                    "defender_ability": defender_ability.replace("-", " ").title() if defender_ability else None,
                    "defender_ability_source": defender_ability_source,
                    "intimidate_applied": intimidate_note is not None and intimidate_stage != 0,
                    "intimidate_note": intimidate_note,
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
                "attacker_ability": attacker_ability.replace("-", " ").title() if attacker_ability else None,
                "attacker_ability_source": attacker_ability_source,
                "defender_ability": defender_ability.replace("-", " ").title() if defender_ability else None,
                "defender_ability_source": defender_ability_source,
                "intimidate_applied": intimidate_note is not None and intimidate_stage != 0,
                "intimidate_note": intimidate_note,
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

    @mcp.tool(
        title="Survive Double-Up",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def survive_double_up(
        defender_name: Annotated[str, Field(description="Target Pokemon being attacked (e.g. 'Chien-Pao')", min_length=1)],
        attacker1_name: Annotated[str, Field(description="First attacker (e.g. 'Rillaboom')", min_length=1)],
        move1_name: Annotated[str, Field(description="First attack (e.g. 'Grassy Glide')", min_length=1)],
        attacker2_name: Annotated[str, Field(description="Second attacker (e.g. 'Urshifu-Rapid-Strike')", min_length=1)],
        move2_name: Annotated[str, Field(description="Second attack (e.g. 'Aqua Jet')", min_length=1)],
        defender_nature: Annotated[Optional[str], Field(description="Defender's nature (auto-fetched from Smogon if not specified)")] = None,
        defender_hp_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's HP EVs (auto-fetched from Smogon if None)")] = None,
        defender_def_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Defense EVs (auto-fetched from Smogon if None)")] = None,
        defender_spd_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Defender's Sp. Def EVs (auto-fetched from Smogon if None)")] = None,
        defender_item: Annotated[Optional[str], Field(description="Defender's item (e.g. 'focus-sash')")] = None,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability")] = None,
        defender_tera_type: Annotated[Optional[str], Field(description="Defender's Tera type if Terastallized")] = None,
        attacker1_nature: Annotated[Optional[str], Field(description="First attacker's nature (auto-fetched from Smogon if None)")] = None,
        attacker1_atk_evs: Annotated[Optional[int], Field(ge=0, le=252, description="First attacker's Attack EVs (auto-fetched from Smogon if None)")] = None,
        attacker1_spa_evs: Annotated[Optional[int], Field(ge=0, le=252, description="First attacker's Sp. Atk EVs (auto-fetched from Smogon if None)")] = None,
        attacker1_item: Annotated[Optional[str], Field(description="First attacker's item")] = None,
        attacker1_ability: Annotated[Optional[str], Field(description="First attacker's ability")] = None,
        attacker2_nature: Annotated[Optional[str], Field(description="Second attacker's nature (auto-fetched from Smogon if None)")] = None,
        attacker2_atk_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Second attacker's Attack EVs (auto-fetched from Smogon if None)")] = None,
        attacker2_spa_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Second attacker's Sp. Atk EVs (auto-fetched from Smogon if None)")] = None,
        attacker2_item: Annotated[Optional[str], Field(description="Second attacker's item")] = None,
        attacker2_ability: Annotated[Optional[str], Field(description="Second attacker's ability")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch spreads from Smogon (default True)")] = True,
        weather: Annotated[Optional[str], Field(description="'sun', 'rain', 'sand', or 'snow'")] = None,
        terrain: Annotated[Optional[str], Field(description="'electric', 'grassy', 'psychic', or 'misty'")] = None,
        reflect: Annotated[bool, Field(description="True if Reflect is active (halves physical damage)")] = False,
        light_screen: Annotated[bool, Field(description="True if Light Screen is active (halves special damage)")] = False,
        aurora_veil: Annotated[bool, Field(description="True if Aurora Veil is active (halves all damage in hail)")] = False,
        friend_guard: Annotated[bool, Field(description="True if ally has Friend Guard (0.75x damage)")] = False,
        sword_of_ruin: Annotated[bool, Field(description="True if Chien-Pao's Sword of Ruin is active (lowers Def to 0.75x)")] = False,
        beads_of_ruin: Annotated[bool, Field(description="True if Chi-Yu's Beads of Ruin is active (lowers SpD to 0.75x)")] = False,
        tablets_of_ruin: Annotated[bool, Field(description="True if Wo-Chien's Tablets of Ruin is active (lowers Atk to 0.75x)")] = False,
        vessel_of_ruin: Annotated[bool, Field(description="True if Ting-Lu's Vessel of Ruin is active (lowers SpA to 0.75x)")] = False,
        attacker1_attack_stage: Annotated[int, Field(ge=-6, le=6, description="First attacker's stat stage from -6 to +6 (0 = neutral)")] = 0,
        attacker2_attack_stage: Annotated[int, Field(ge=-6, le=6, description="Second attacker's stat stage from -6 to +6 (0 = neutral)")] = 0,
        defender_defense_stage: Annotated[int, Field(ge=-6, le=6, description="Defender's Defense stat stage from -6 to +6")] = 0,
        defender_special_defense_stage: Annotated[int, Field(ge=-6, le=6, description="Defender's Sp. Def stat stage from -6 to +6")] = 0
    ) -> dict:
        """Check if a Pokemon survives combined damage from two attackers in one turn (double-up).

        Use this to answer questions like "Can Chien-Pao survive Grassy Glide + Aqua Jet?"

        Returns the combined damage range, survival result, and a per-attacker
        breakdown.
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
            from vgc_mcp_core.calc.items import get_signature_item
            if attacker1_item is None:
                sig_item = get_signature_item(attacker1_name)
                if sig_item:
                    attacker1_item = sig_item
            if attacker2_item is None:
                sig_item = get_signature_item(attacker2_name)
                if sig_item:
                    attacker2_item = sig_item

            # Backfill any abilities Smogon didn't supply (mega > Smogon > pokeapi).
            from vgc_mcp_core.tools.ability_helpers import (
                compute_intimidate_attack_stage,
                resolve_ability,
            )
            if attacker1_ability is None:
                attacker1_ability, _ = await resolve_ability(
                    attacker1_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                    use_smogon=use_smogon_spreads,
                )
            if attacker2_ability is None:
                attacker2_ability, _ = await resolve_ability(
                    attacker2_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                    use_smogon=use_smogon_spreads,
                )
            if defender_ability is None:
                defender_ability, _ = await resolve_ability(
                    defender_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                    use_smogon=use_smogon_spreads,
                )

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

            # Create Pokemon builds — abilities stamped so engine auto-applies
            # offensive/defensive ability interactions even without modifier override.
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
                ability=defender_ability,
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
                item=attacker1_item,
                ability=attacker1_ability,
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
                item=attacker2_item,
                ability=attacker2_ability,
            )

            # Determine if each move is physical or special
            is_physical1 = move1.category.value == "physical"
            is_physical2 = move2.category.value == "physical"

            # Defender Intimidate event: lowers each opposing attacker's Atk by -1
            # for physical moves, accounting for blockers/punishers on each attacker.
            intim1_stage, _ = compute_intimidate_attack_stage(
                defender_ability=defender_ability,
                attacker_ability=attacker1_ability,
                is_physical=is_physical1,
            )
            intim2_stage, _ = compute_intimidate_attack_stage(
                defender_ability=defender_ability,
                attacker_ability=attacker2_ability,
                is_physical=is_physical2,
            )
            effective_atk1_stage = attacker1_attack_stage + (intim1_stage if is_physical1 else 0)
            effective_atk2_stage = attacker2_attack_stage + (intim2_stage if is_physical2 else 0)

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
                attack_stage=effective_atk1_stage if is_physical1 else 0,
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
                attack_stage=effective_atk2_stage if is_physical2 else 0,
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
