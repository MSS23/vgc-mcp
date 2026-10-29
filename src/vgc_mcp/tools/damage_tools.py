"""MCP tools for damage calculations.

Thin wrappers: the logic lives in ``vgc_mcp_core.tools.damage_handlers``.
"""

from typing import Annotated, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.tools import damage_handlers
from vgc_mcp_core.tools.calc_result import CalcResultDict
from vgc_mcp_core.tools.damage_handlers import _get_common_spread as _get_common_spread
from vgc_mcp_core.tools.damage_handlers import _get_common_spreads as _get_common_spreads
from vgc_mcp_core.tools.damage_handlers import (
    format_transparent_output as format_transparent_output,
)
from vgc_mcp_core.utils.normalize import (
    normalize_smogon_name as _normalize_smogon_name,  # noqa: F401
)


def register_damage_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None) -> None:
    """Register damage calculation tools with the MCP server."""
    damage_handlers._smogon_client = smogon

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
    ) -> CalcResultDict:
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
        return await damage_handlers.calculate_damage_output(
            pokeapi,
            smogon,
            attacker_name=attacker_name,
            defender_name=defender_name,
            move_name=move_name,
            attacker_nature=attacker_nature,
            attacker_atk_evs=attacker_atk_evs,
            attacker_spa_evs=attacker_spa_evs,
            attacker_hp_evs=attacker_hp_evs,
            attacker_def_evs=attacker_def_evs,
            attacker_spd_evs=attacker_spd_evs,
            attacker_spe_evs=attacker_spe_evs,
            defender_nature=defender_nature,
            defender_hp_evs=defender_hp_evs,
            defender_def_evs=defender_def_evs,
            defender_spd_evs=defender_spd_evs,
            defender_atk_evs=defender_atk_evs,
            defender_spa_evs=defender_spa_evs,
            defender_spe_evs=defender_spe_evs,
            attacker_sps=attacker_sps,
            defender_sps=defender_sps,
            use_smogon_spreads=use_smogon_spreads,
            num_defender_spreads=num_defender_spreads,
            is_spread=is_spread,
            weather=weather,
            terrain=terrain,
            attacker_item=attacker_item,
            defender_item=defender_item,
            attacker_ability=attacker_ability,
            defender_ability=defender_ability,
            attacker_tera_type=attacker_tera_type,
            defender_tera_type=defender_tera_type,
            reflect=reflect,
            light_screen=light_screen,
            helping_hand=helping_hand,
            commander_active=commander_active,
            defender_commander_active=defender_commander_active,
            beads_of_ruin=beads_of_ruin,
            sword_of_ruin=sword_of_ruin,
            tablets_of_ruin=tablets_of_ruin,
            vessel_of_ruin=vessel_of_ruin,
            attacker_booster_energy=attacker_booster_energy,
            defender_booster_energy=defender_booster_energy,
            attacker_attack_stage=attacker_attack_stage,
            attacker_special_attack_stage=attacker_special_attack_stage,
            defender_defense_stage=defender_defense_stage,
            defender_special_defense_stage=defender_special_defense_stage,
            aurora_veil=aurora_veil,
            friend_guard=friend_guard,
            defender_starting_hp_percent=defender_starting_hp_percent,
            attacker_starting_hp_percent=attacker_starting_hp_percent,
        )

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
        return await damage_handlers.find_ko_evs(
            pokeapi,
            smogon,
            attacker_name=attacker_name,
            defender_name=defender_name,
            move_name=move_name,
            attacker_nature=attacker_nature,
            defender_nature=defender_nature,
            defender_hp_evs=defender_hp_evs,
            defender_def_evs=defender_def_evs,
            target_ko_chance=target_ko_chance,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            defender_ability=defender_ability,
            use_smogon_spreads=use_smogon_spreads,
        )

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
        attacker_evs: Annotated[Optional[Union[Annotated[int, Field(ge=0, le=252)], str]], Field(description="Attacker's offensive EVs as an int (auto-fetched from Smogon if not provided), or the full spread as an 'HP/Atk/Def/SpA/SpD/Spe' slash string, e.g. '4/252/0/0/0/252' (Stat Points, e.g. '0/32/0/0/2/32', in Champions sessions)")] = None,
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (auto-fetched from Smogon if not provided)")] = None,
        defender_nature: Annotated[str, Field(description="Your Pokemon's nature (default: Calm for SpD, use Impish for Def)")] = "calm",
        target_survival_chance: Annotated[float, Field(ge=0, le=100, description="Survival %: 93.75 (15/16 rolls, survive max damage only) is RECOMMENDED — minimal EVs; 87.5 = can die to 2 highest rolls; 100 = guaranteed survival (wastes EVs)")] = 93.75,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch attacker spread from Smogon (default True)")] = True,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability. Auto-detected if not specified (Mega forms resolve to their post-mega ability, e.g. Mega Manectric → Intimidate).")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability — overrides auto-detection")] = None,
        apply_defender_intimidate: Annotated[bool, Field(description="If True (default), automatically applies the defender's Intimidate (-1 attacker Atk for physical moves), accounting for attacker blockers (Clear Body, Inner Focus, etc.) and punishers (Defiant, Contrary). Set False to ignore Intimidate (e.g. simulating a turn after switch-in).")] = True
    ) -> CalcResultDict:
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
        return await damage_handlers.find_survival_evs(
            pokeapi,
            smogon,
            attacker_name=attacker_name,
            defender_name=defender_name,
            move_name=move_name,
            attacker_nature=attacker_nature,
            attacker_evs=attacker_evs,
            attacker_item=attacker_item,
            defender_nature=defender_nature,
            target_survival_chance=target_survival_chance,
            use_smogon_spreads=use_smogon_spreads,
            defender_ability=defender_ability,
            attacker_ability=attacker_ability,
            apply_defender_intimidate=apply_defender_intimidate,
        )

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
        return await damage_handlers.survive_multiple_hits(
            pokeapi,
            smogon,
            attacker_name=attacker_name,
            defender_name=defender_name,
            move_name=move_name,
            num_hits=num_hits,
            attacker_nature=attacker_nature,
            attacker_atk_evs=attacker_atk_evs,
            attacker_spa_evs=attacker_spa_evs,
            defender_nature=defender_nature,
            defender_hp_evs=defender_hp_evs,
            defender_def_evs=defender_def_evs,
            defender_spd_evs=defender_spd_evs,
            use_smogon_spreads=use_smogon_spreads,
            attacker_attack_stage=attacker_attack_stage,
            defender_defense_stage=defender_defense_stage,
            weather=weather,
            terrain=terrain,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            defender_ability=defender_ability,
            apply_defender_intimidate=apply_defender_intimidate,
            reflect=reflect,
            light_screen=light_screen,
            aurora_veil=aurora_veil,
            friend_guard=friend_guard,
        )

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
        attacker_evs: Annotated[Union[Annotated[int, Field(ge=0, le=252)], str], Field(description="Attacker's offensive EVs as an int, or the full EV spread as an 'HP/Atk/Def/SpA/SpD/Spe' slash string, e.g. '4/252/0/0/0/252'")] = 252,
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
        return await damage_handlers.find_bulk_to_survive_hits(
            pokeapi,
            smogon,
            attacker_name=attacker_name,
            defender_name=defender_name,
            move_name=move_name,
            num_hits=num_hits,
            attacker_nature=attacker_nature,
            attacker_evs=attacker_evs,
            defender_nature=defender_nature,
            attacker_attack_stage=attacker_attack_stage,
            defender_defense_stage=defender_defense_stage,
            reflect=reflect,
            light_screen=light_screen,
            aurora_veil=aurora_veil,
            friend_guard=friend_guard,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            defender_ability=defender_ability,
            apply_defender_intimidate=apply_defender_intimidate,
            use_smogon_spreads=use_smogon_spreads,
        )

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
        return await damage_handlers.survive_double_up(
            pokeapi,
            smogon,
            defender_name=defender_name,
            attacker1_name=attacker1_name,
            move1_name=move1_name,
            attacker2_name=attacker2_name,
            move2_name=move2_name,
            defender_nature=defender_nature,
            defender_hp_evs=defender_hp_evs,
            defender_def_evs=defender_def_evs,
            defender_spd_evs=defender_spd_evs,
            defender_item=defender_item,
            defender_ability=defender_ability,
            defender_tera_type=defender_tera_type,
            attacker1_nature=attacker1_nature,
            attacker1_atk_evs=attacker1_atk_evs,
            attacker1_spa_evs=attacker1_spa_evs,
            attacker1_item=attacker1_item,
            attacker1_ability=attacker1_ability,
            attacker2_nature=attacker2_nature,
            attacker2_atk_evs=attacker2_atk_evs,
            attacker2_spa_evs=attacker2_spa_evs,
            attacker2_item=attacker2_item,
            attacker2_ability=attacker2_ability,
            use_smogon_spreads=use_smogon_spreads,
            weather=weather,
            terrain=terrain,
            reflect=reflect,
            light_screen=light_screen,
            aurora_veil=aurora_veil,
            friend_guard=friend_guard,
            sword_of_ruin=sword_of_ruin,
            beads_of_ruin=beads_of_ruin,
            tablets_of_ruin=tablets_of_ruin,
            vessel_of_ruin=vessel_of_ruin,
            attacker1_attack_stage=attacker1_attack_stage,
            attacker2_attack_stage=attacker2_attack_stage,
            defender_defense_stage=defender_defense_stage,
            defender_special_defense_stage=defender_special_defense_stage,
        )
