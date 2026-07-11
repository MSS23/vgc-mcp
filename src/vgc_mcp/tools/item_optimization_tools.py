"""MCP tools for Life Orb optimization and item comparison.

Tools for comparing items (Life Orb vs Choice items) and analyzing
EV-item trade-offs for competitive VGC optimization.
"""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.item_optimization import (
    analyze_life_orb_sustainability,
    calculate_ev_tradeoff,
    compare_items_damage,
)
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.pokemon import (
    BaseStats,
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.tools.smogon_helpers import (
    get_common_spread as _shared_get_common_spread,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

# Import META_SYNERGIES from spread_tools
from .spread_tools import META_SYNERGIES


def _detect_champions(pokemon_name: Optional[str] = None) -> bool:
    """Return True when the active session is the Champions (Reg MA) SP system.

    Optionally runs Pokemon-name inference first so a Mega/Reg MA mention
    auto-selects Champions. The mainline path is taken when this is False.
    """
    from vgc_mcp_core.rules.format_detect import detect_champions_format
    return detect_champions_format(pokemon_name)


def _sps_from_smogon_spread(spread: Optional[dict]) -> Optional[StatPointSpread]:
    """Build a StatPointSpread from a champions-tagged Smogon spread dict.

    Returns None when the spread isn't tagged format_system=='champions' or
    carries no `sps` data — callers then fall back to other SP sources.
    """
    if not spread or spread.get("format_system") != "champions":
        return None
    sps = spread.get("sps")
    if not sps:
        return None
    return StatPointSpread.from_sps_dict(sps)


def _sps_from_evs_dict(evs: Optional[dict]) -> StatPointSpread:
    """Convert a passed EV-style dict to a Champions StatPointSpread.

    EV values are mapped onto the SP grain (1 SP == 8 EVs) and trimmed to the
    66-point budget via the canonical converter. Used when a Champions session
    subject only has EV-named input (no explicit SP spread).
    """
    evs = evs or {}
    from vgc_mcp_core.calc.conversion import evs_to_sps_spread
    from vgc_mcp_core.models.pokemon import EVSpread
    # Convert EV-scale values to the SP grain (1 SP == 8 EVs) and trim to the
    # 66-point budget — NOT a naive min(ev, 32) clamp, which would massively
    # over-state any intermediate investment (e.g. 100 EVs -> 13 SP, not 32).
    return evs_to_sps_spread(
        EVSpread(
            hp=int(evs.get("hp", 0)),
            attack=int(evs.get("attack", 0)),
            defense=int(evs.get("defense", 0)),
            special_attack=int(evs.get("special_attack", 0)),
            special_defense=int(evs.get("special_defense", 0)),
            speed=int(evs.get("speed", 0)),
        )
    )


# SP-grain mirror of the mainline EV trade-off table. Choice items' 1.5x stat
# multiplier means the subject reaches the same offensive number with fewer
# Stat Points, freeing SP for bulk. ~88 EVs saved by choice items maps to
# 88 / 8 = 11 SP (1 SP == "8 EVs of effectiveness").
_CHOICE_OFFENSIVE_SP = 21   # 32 - 11 saved
_CHOICE_SPARE_DEF_SP = 11   # freed SP routed to Defense
_CHOICE_SP_SAVED = 11


def _champions_ev_tradeoff(
    pokemon_name: str,
    base_stats: BaseStats,
    types: list[str],
    nature: Nature,
    items_to_test: list[str],
    offensive_stat: str,
):
    """SP-grain item/Stat-Point trade-off for a Champions subject.

    Mirrors `calc.item_optimization.calculate_ev_tradeoff` but allocates Stat
    Points (cap 32/stat, 66 total) and returns 'SPs:' pastes. Returns
    `(analysis_list, best_entry)` sorted by total useful stats (desc).
    """
    from vgc_mcp_core.calc.champions_optimization import validate_sp_allocation
    from vgc_mcp_core.calc.stats_champions import calculate_all_stats_champions

    results = []
    for item in items_to_test:
        if item in ("choice-band", "choice-specs"):
            sps = {
                "hp": 0,
                "attack": _CHOICE_OFFENSIVE_SP if offensive_stat == "attack" else 0,
                "defense": _CHOICE_SPARE_DEF_SP,
                "special_attack": _CHOICE_OFFENSIVE_SP if offensive_stat == "special_attack" else 0,
                "special_defense": 0,
                "speed": 32,
            }
            sps_saved = _CHOICE_SP_SAVED
        else:  # life-orb and any other item: full offensive investment
            sps = {
                "hp": 0,
                "attack": 32 if offensive_stat == "attack" else 0,
                "defense": 0,
                "special_attack": 32 if offensive_stat == "special_attack" else 0,
                "special_defense": 0,
                "speed": 32,
            }
            sps_saved = 0

        # Enforce the 32/stat, 66-total budget defensively.
        validate_sp_allocation(sps)

        test_pokemon = PokemonBuild(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=nature,
            format_system="champions",
            sps=StatPointSpread(**sps),
            item=item,
        )

        final_stats = calculate_all_stats_champions(test_pokemon)
        total_useful = (
            final_stats.get(offensive_stat, 0)
            + final_stats.get("speed", 0)
            + final_stats.get("hp", 0) // 2
        )
        showdown_paste = pokemon_build_to_showdown(test_pokemon)

        results.append({
            "item": item,
            "sps": sps,
            "sps_saved": sps_saved,
            "total_useful_stats": total_useful,
            "final_stats": final_stats,
            "rank": 0,
            "showdown_paste": showdown_paste,
        })

    results.sort(key=lambda x: x["total_useful_stats"], reverse=True)
    for i, r in enumerate(results):
        r["rank"] = i + 1

    best_entry = results[0] if results else None
    return results, best_entry


# Module-level Smogon client reference
_smogon_client: Optional[SmogonStatsClient] = None



async def _get_common_spread(pokemon_name: str) -> Optional[dict]:
    """Module-local wrapper — passes the registered Smogon client through."""
    return await _shared_get_common_spread(_smogon_client, pokemon_name)


def register_item_optimization_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register Life Orb optimization and item comparison tools."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool(
        title="Compare Item Damage Output",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def compare_item_damage_output(
        pokemon_name: Annotated[str, Field(description="Attacker Pokemon (e.g. 'landorus-therian')", min_length=1)],
        move_name: Annotated[str, Field(description="Move to use (e.g. 'earth-power')", min_length=1)],
        target_name: Annotated[str, Field(description="Defender Pokemon (e.g. 'rillaboom')", min_length=1)],
        items_to_compare: Annotated[Optional[list[str]], Field(
            description="Items to compare (default: ['life-orb', 'choice-band', 'choice-specs', 'expert-belt'])",
        )] = None,
        num_turns: Annotated[int, Field(ge=1, description="Number of turns for recoil accumulation analysis")] = 3,
        attacker_nature: Annotated[Optional[str], Field(
            description="Attacker's nature (auto-fetched from Smogon if not specified)",
        )] = None,
        attacker_evs: Annotated[Optional[dict], Field(
            description="Attacker's EVs dict keyed hp/attack/defense/special_attack/special_defense/speed (auto-fetched from Smogon if not specified)",
        )] = None,
        target_nature: Annotated[Optional[str], Field(
            description="Defender's nature (auto-fetched from Smogon if not specified)",
        )] = None,
        target_evs: Annotated[Optional[dict], Field(
            description="Defender's EVs dict (auto-fetched from Smogon if not specified)",
        )] = None,
        use_smogon_spreads: Annotated[bool, Field(
            description="Auto-fetch common spreads from Smogon for unspecified natures/EVs",
        )] = True,
    ) -> dict:
        """Compare damage output across multiple items (Life Orb vs Choice items vs Expert Belt).

        Shows damage, recoil, and sustainability per item plus a best-item
        recommendation and Showdown paste. In a Champions (Reg MA) session the
        attacker is built on the Stat Point scale automatically.
        """
        try:
            if items_to_compare is None:
                items_to_compare = ["life-orb", "choice-band", "choice-specs", "expert-belt"]

            # Fetch Pokemon data
            attacker_base = await pokeapi.get_base_stats(pokemon_name)
            attacker_types = await pokeapi.get_pokemon_types(pokemon_name)
            defender_base = await pokeapi.get_base_stats(target_name)
            defender_types = await pokeapi.get_pokemon_types(target_name)
            move = await pokeapi.get_move(move_name, user_name=pokemon_name)

            # Auto-fetch Smogon spreads if requested
            attacker_spread = None
            defender_spread = None
            if use_smogon_spreads:
                attacker_spread = await _get_common_spread(pokemon_name)
                defender_spread = await _get_common_spread(target_name)

            # Build attacker
            if attacker_spread and attacker_nature is None:
                attacker_nature = attacker_spread.get("nature", "serious")
            if attacker_spread and attacker_evs is None:
                attacker_evs = attacker_spread.get("evs", {})

            attacker_nature_enum = Nature(attacker_nature.lower() if attacker_nature else "serious")
            attacker_evs_dict = attacker_evs or {}

            # Check for Sheer Force synergy
            attacker_key = pokemon_name.lower().replace(" ", "-")
            has_sheer_force = False
            attacker_ability = None

            # Get ability from Smogon spread if available
            if attacker_spread:
                attacker_ability = attacker_spread.get("ability")

            # Check META_SYNERGIES as fallback
            if attacker_key in META_SYNERGIES:
                _, meta_ability = META_SYNERGIES[attacker_key]
                if not attacker_ability:
                    attacker_ability = meta_ability

            # Normalize ability name for comparison
            if attacker_ability:
                ability_normalized = attacker_ability.lower().replace(" ", "-").replace("_", "-")
                if ability_normalized == "sheer-force":
                    has_sheer_force = True

            # The ATTACKER is the user's subject. In a Champions session build
            # it on the SP scale (StatPointSpread + format_system='champions')
            # so its stats and damage use the correct formula; mainline keeps
            # the EVSpread path byte-for-byte. The defender (opposing target)
            # below stays mainline unless its own fetched spread is champions.
            is_champions = _detect_champions(pokemon_name)
            if is_champions:
                attacker_sps = _sps_from_smogon_spread(attacker_spread)
                if attacker_sps is None:
                    attacker_sps = _sps_from_evs_dict(attacker_evs_dict)
                attacker = PokemonBuild(
                    name=pokemon_name,
                    base_stats=attacker_base,
                    types=attacker_types,
                    nature=attacker_nature_enum,
                    format_system="champions",
                    sps=attacker_sps,
                    ability=attacker_ability
                )
            else:
                attacker = PokemonBuild(
                    name=pokemon_name,
                    base_stats=attacker_base,
                    types=attacker_types,
                    nature=attacker_nature_enum,
                    evs=EVSpread(
                        hp=attacker_evs_dict.get("hp", 0),
                        attack=attacker_evs_dict.get("attack", 0),
                        defense=attacker_evs_dict.get("defense", 0),
                        special_attack=attacker_evs_dict.get("special_attack", 0),
                        special_defense=attacker_evs_dict.get("special_defense", 0),
                        speed=attacker_evs_dict.get("speed", 0)
                    ),
                    ability=attacker_ability
                )

            # Build defender
            if defender_spread and target_nature is None:
                target_nature = defender_spread.get("nature", "serious")
            if defender_spread and target_evs is None:
                target_evs = defender_spread.get("evs", {})

            defender_nature_enum = Nature(target_nature.lower() if target_nature else "serious")
            defender_evs_dict = target_evs or {}

            # Resolve defender ability so defensive interactions (Multiscale,
            # Filter, Thick Fat, etc.) propagate into compare_items_damage.
            defender_ability = (
                defender_spread.get("ability") if defender_spread else None
            )
            from vgc_mcp_core.tools.ability_helpers import resolve_ability
            if defender_ability is None:
                defender_ability, _ = await resolve_ability(
                    target_name, pokeapi=pokeapi, smogon_client=_smogon_client,
                )

            # Opposing target stays MAINLINE unless its own fetched Smogon
            # spread is explicitly champions-tagged (then honour the SP scale).
            defender_sps = _sps_from_smogon_spread(defender_spread)
            if defender_sps is not None:
                defender = PokemonBuild(
                    name=target_name,
                    base_stats=defender_base,
                    types=defender_types,
                    nature=defender_nature_enum,
                    ability=defender_ability,
                    format_system="champions",
                    sps=defender_sps
                )
            else:
                defender = PokemonBuild(
                    name=target_name,
                    base_stats=defender_base,
                    types=defender_types,
                    nature=defender_nature_enum,
                    ability=defender_ability,
                    evs=EVSpread(
                        hp=defender_evs_dict.get("hp", 0),
                        attack=defender_evs_dict.get("attack", 0),
                        defense=defender_evs_dict.get("defense", 0),
                        special_attack=defender_evs_dict.get("special_attack", 0),
                        special_defense=defender_evs_dict.get("special_defense", 0),
                        speed=defender_evs_dict.get("speed", 0)
                    )
                )

            # Create modifiers
            modifiers = DamageModifiers(is_doubles=True)

            # Compare items
            comparison_results = compare_items_damage(
                attacker, defender, move, items_to_compare, modifiers, has_sheer_force
            )

            # Format results
            item_comparison = []
            for result in comparison_results:
                item_comparison.append({
                    "item": result.item,
                    "damage": result.damage_range,
                    "damage_percent": result.damage_percent,
                    "recoil_per_attack": result.recoil_per_attack,
                    "recoil_percent": result.recoil_percent,
                    "turns_sustainable": result.turns_sustainable,
                    "recommendation": result.recommendation,
                    "notes": result.notes
                })

            # Generate key takeaways
            key_takeaways = []
            best_item = max(comparison_results, key=lambda x: (
                999 if x.turns_sustainable == 999 else x.turns_sustainable,
                float(x.damage_percent.split("-")[1].replace("%", ""))
            ))

            key_takeaways.append(f"{best_item.item.title()} provides best damage-to-sustainability ratio")
            if has_sheer_force and "life-orb" in items_to_compare:
                key_takeaways.append("Sheer Force negates Life Orb recoil - Life Orb is optimal")
            elif "life-orb" in items_to_compare:
                life_orb_result = next((r for r in comparison_results if r.item == "life-orb"), None)
                if life_orb_result:
                    key_takeaways.append(f"Life Orb recoil: {life_orb_result.recoil_percent}% per attack ({life_orb_result.turns_sustainable} attacks sustainable)")

            # Generate Showdown paste for attacker
            attacker_dict = attacker.model_dump()
            attacker_dict["item"] = best_item.item
            attacker_with_best_item = PokemonBuild(**attacker_dict)
            showdown_paste = pokemon_build_to_showdown(attacker_with_best_item)

            return {
                "attacker": pokemon_name,
                "move": move_name,
                "target": target_name,
                "item_comparison": item_comparison,
                "key_takeaways": key_takeaways,
                "showdown_paste": showdown_paste,
                "sheer_force_detected": has_sheer_force
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Optimize Life Orb Sustainability",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def optimize_life_orb_sustainability(
        pokemon_name: Annotated[str, Field(description="Pokemon to analyze (e.g. 'flutter-mane')", min_length=1)],
        hp_investment: Annotated[str, Field(
            description="'full' (compare 0 vs 252 HP EVs), 'minimal' (0 only), or a specific EV value; interpreted on the Stat Point grain (0-32) in Champions sessions",
        )] = "full",
        recovery_sources: Annotated[Optional[list[str]], Field(
            description="Recovery sources like ['grassy-terrain', 'leftovers'] (default: none)",
        )] = None,
        moves_per_game: Annotated[int, Field(ge=1, description="Expected number of attacks before fainting")] = 4,
        nature: Annotated[Optional[str], Field(
            description="Pokemon's nature (auto-fetched from Smogon if not specified)",
        )] = None,
        use_smogon_spread: Annotated[bool, Field(
            description="Auto-fetch the common spread from Smogon when nature is unspecified",
        )] = True,
    ) -> dict:
        """Analyze Life Orb sustainability with different HP investments.

        Compares 0 vs max HP investment for Life Orb users, showing attacks
        before fainting and net HP after multiple attacks. In a Champions
        (Reg MA) session the comparison runs on the Stat Point grain (0 vs 32).
        """
        try:
            if recovery_sources is None:
                recovery_sources = []

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Auto-fetch Smogon spread if requested
            smogon_spread = None
            if use_smogon_spread:
                smogon_spread = await _get_common_spread(pokemon_name)

            # The SUBJECT is the user's Pokemon. In a Champions session reason
            # on the SP grain (0 vs 32 / specific SP, capped at 32) instead of
            # 0 vs 252 EVs; mainline keeps the EV grain byte-for-byte.
            is_champions = _detect_champions(pokemon_name)

            # Determine HP investment values to test (SP units for champions,
            # EV units for mainline).
            cap = 32 if is_champions else 252
            if hp_investment == "full":
                hp_units_to_test = [0, cap]
            elif hp_investment == "minimal":
                hp_units_to_test = [0]
            else:
                try:
                    hp_units_to_test = [min(int(hp_investment), cap)]
                except ValueError:
                    hp_units_to_test = [0, cap]

            # Get nature and other EVs from Smogon if available
            if smogon_spread and nature is None:
                nature = smogon_spread.get("nature", "serious")
            nature_enum = Nature(nature.lower() if nature else "serious")

            # Analyze each HP investment
            sustainability_results = []
            for hp_units in hp_units_to_test:
                if is_champions:
                    # Build the subject on the SP scale so any returned stats /
                    # paste are SP-based. The shared calc takes an EV int and
                    # divides it by 4 (EV/4) in the HP formula; 1 SP ==
                    # "8 EVs of effectiveness" (EV slot SP*2), so pass SP*8 to
                    # reproduce the champions HP number exactly.
                    pokemon = PokemonBuild(
                        name=pokemon_name,
                        base_stats=base_stats,
                        types=types,
                        nature=nature_enum,
                        format_system="champions",
                        sps=StatPointSpread(hp=hp_units),
                    )
                    hp_ev_equiv = hp_units * 8
                else:
                    pokemon = PokemonBuild(
                        name=pokemon_name,
                        base_stats=base_stats,
                        types=types,
                        nature=nature_enum,
                        evs=EVSpread(hp=hp_units)
                    )
                    hp_ev_equiv = hp_units

                analysis = analyze_life_orb_sustainability(
                    pokemon, hp_ev_equiv, recovery_sources, moves_per_game
                )

                result_entry = {
                    "hp_evs": hp_units,
                    "max_hp": analysis.max_hp,
                    "attacks_before_faint": analysis.attacks_before_faint,
                    "net_hp_after_attacks": analysis.net_hp_after_attacks,
                    "recommendation": analysis.recommendation
                }
                if is_champions:
                    # Surface the SP grain explicitly for champions callers.
                    result_entry["hp_sps"] = hp_units
                sustainability_results.append(result_entry)

            # Use SP terminology for champions, EV for mainline.
            unit_label = "HP SPs" if is_champions else "HP EVs"
            max_unit = 32 if is_champions else 252

            # Generate recommendation
            if len(sustainability_results) == 2:
                zero_evs = sustainability_results[0]
                max_evs = sustainability_results[1]

                if zero_evs["attacks_before_faint"] == max_evs["attacks_before_faint"]:
                    recommendation = f"Invest 0 {unit_label} - same sustainability as {max_unit} {unit_label}"
                else:
                    recommendation = f"{max_unit} {unit_label} provides {max_evs['attacks_before_faint'] - zero_evs['attacks_before_faint']} more sustainable attacks"
            else:
                result = sustainability_results[0]
                recommendation = result["recommendation"]

            # Generate sustainability table
            table_lines = [f"| {unit_label} | Max HP | Attacks Before Faint |"]
            table_lines.append("|--------|--------|---------------------|")
            for result in sustainability_results:
                table_lines.append(
                    f"| {result['hp_evs']} | {result['max_hp']} | {result['attacks_before_faint']} |"
                )
            sustainability_table = "\n".join(table_lines)

            return {
                "pokemon": pokemon_name,
                "format_system": "champions" if is_champions else "mainline",
                "life_orb_analysis": {
                    "attacks_before_faint_0_evs": sustainability_results[0]["attacks_before_faint"],
                    "attacks_before_faint_252_evs": sustainability_results[-1]["attacks_before_faint"] if len(sustainability_results) > 1 else sustainability_results[0]["attacks_before_faint"],
                    "net_hp_after_4_attacks": sustainability_results[0]["net_hp_after_attacks"]
                },
                "recommendation": recommendation,
                "sustainability_table": sustainability_table,
                "recovery_sources": recovery_sources
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Analyze Item vs EV Trade-Off",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def analyze_item_ev_tradeoff(
        pokemon_name: Annotated[str, Field(description="Pokemon to optimize (e.g. 'flutter-mane')", min_length=1)],
        offensive_stat: Annotated[str, Field(
            description="'attack', 'special-attack', or 'auto' (picks the higher base offensive stat)",
        )] = "auto",
        target_benchmark: Annotated[Optional[dict], Field(
            description="Benchmark requirements dict (e.g. {'speed_target': 200})",
        )] = None,
        items_to_test: Annotated[Optional[list[str]], Field(
            description="Items to compare (default: ['life-orb', 'choice-band', 'choice-specs'])",
        )] = None,
        use_smogon_spread: Annotated[bool, Field(
            description="Auto-fetch the common spread from Smogon for the nature",
        )] = True,
    ) -> dict:
        """Find the optimal item + EV distribution to maximize useful stats.

        Compares items to see which saves the most EVs while meeting benchmarks
        (e.g. Life Orb needs full investment; Choice items reach the same number
        with fewer EVs). Runs on the Stat Point grain in Champions sessions.
        """
        try:
            if items_to_test is None:
                items_to_test = ["life-orb", "choice-band", "choice-specs"]
            if target_benchmark is None:
                target_benchmark = {}

            # Fetch Pokemon data
            base_stats = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)

            # Auto-fetch Smogon spread if requested
            smogon_spread = None
            if use_smogon_spread:
                smogon_spread = await _get_common_spread(pokemon_name)

            # Build base Pokemon
            nature = "serious"
            if smogon_spread:
                nature = smogon_spread.get("nature", "serious")

            # Determine offensive stat
            if offensive_stat == "auto":
                if base_stats.attack > base_stats.special_attack:
                    offensive_stat = "attack"
                else:
                    offensive_stat = "special_attack"

            # The SUBJECT is the user's Pokemon. In a Champions session the
            # EV-grain trade-off reasoning runs on the SP grain instead (32 per
            # stat / 66 total, 'SPs:' pastes); mainline keeps the shared
            # EV-grain calc byte-for-byte.
            is_champions = _detect_champions(pokemon_name)

            if is_champions:
                tradeoff_analysis, best_entry = _champions_ev_tradeoff(
                    pokemon_name, base_stats, types,
                    Nature(nature.lower()), items_to_test, offensive_stat,
                )
                if not tradeoff_analysis:
                    return error_response(ErrorCodes.INTERNAL_ERROR, 'No valid tradeoff results generated', pokemon=pokemon_name)

                return {
                    "pokemon": pokemon_name,
                    "format_system": "champions",
                    "offensive_stat": offensive_stat,
                    "tradeoff_analysis": tradeoff_analysis,
                    "recommendation": {
                        "best_item": best_entry["item"],
                        "sps_saved": best_entry["sps_saved"],
                        "showdown_paste": best_entry["showdown_paste"],
                        "final_stats": best_entry["final_stats"],
                    },
                }

            pokemon = PokemonBuild(
                name=pokemon_name,
                base_stats=base_stats,
                types=types,
                nature=Nature(nature.lower())
            )

            # Calculate trade-offs
            tradeoff_results = calculate_ev_tradeoff(
                pokemon, target_benchmark, items_to_test, offensive_stat
            )

            # Format results
            tradeoff_analysis = []
            for result in tradeoff_results:
                tradeoff_analysis.append({
                    "item": result.item,
                    "evs": result.evs,
                    "evs_saved": result.evs_saved,
                    "total_useful_stats": result.total_useful_stats,
                    "rank": result.rank,
                    "showdown_paste": result.showdown_paste,
                    "final_stats": result.final_stats
                })

            # Get best item
            if not tradeoff_results:
                return error_response(ErrorCodes.INTERNAL_ERROR, 'No valid tradeoff results generated', pokemon=pokemon_name)

            best_result = tradeoff_results[0]

            return {
                "pokemon": pokemon_name,
                "format_system": "mainline",
                "offensive_stat": offensive_stat,
                "tradeoff_analysis": tradeoff_analysis,
                "recommendation": {
                    "best_item": best_result.item,
                    "evs_saved": best_result.evs_saved,
                    "showdown_paste": best_result.showdown_paste,
                    "final_stats": best_result.final_stats
                }
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
