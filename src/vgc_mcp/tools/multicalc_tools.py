"""Multi-damage calculator tools for VGC coverage analysis.

Tools for batch damage calculations:
- Offensive coverage (1 attacker vs multiple defenders)
- Defensive threats (1 defender vs multiple attackers)
- Team coverage matrix (team of 6 vs meta threats)
"""

import asyncio
import logging
import time
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.calc.damage import calculate_damage, format_percent
from vgc_mcp_core.calc.modifiers import DamageModifiers
from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown
from vgc_mcp_core.models.pokemon import (
    EVSpread,
    Nature,
    PokemonBuild,
    StatPointSpread,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

# Import helper functions from damage_tools (do NOT edit that module — reuse only)
from .damage_tools import _detect_champions, _get_common_spread, _sps_from_smogon_spread

logger = logging.getLogger(__name__)

# Module-level Smogon client reference
_smogon_client: Optional[SmogonStatsClient] = None


async def _build_pokemon_from_smogon(
    pokemon_name: str,
    pokeapi: PokeAPIClient,
    nature: Optional[str] = None,
    evs: Optional[dict] = None,
    item: Optional[str] = None,
    ability: Optional[str] = None,
    *,
    subject_is_champions: bool = False,
    sps: Optional[dict] = None,
) -> PokemonBuild:
    """Build a PokemonBuild from Smogon data or provided values.

    Ability resolution: user override > mega-form lookup > Smogon's most-used >
    pokeapi first-listed. Ensures every PokemonBuild carries the right ability
    so the damage engine auto-applies offensive (Sheer Force, Tough Claws,
    Adaptability, Aerilate, etc.) AND defensive (Multiscale, Ice Scales, Thick
    Fat, Filter, Levitate, type absorption, etc.) interactions.

    Champions (Reg MA) dispatch — two independent triggers:
      * The fetched/returned Smogon spread is itself tagged
        ``format_system == 'champions'`` (Wave-1 passthrough), in which case the
        build is SP-scale regardless of who it represents. This is how an
        OPPOSING reference mon legitimately becomes champions.
      * ``subject_is_champions=True`` — the caller knows this is the USER'S
        subject (attacker / team member) in a champions session, so it must use
        the SP system even when Smogon only has a mainline spread. The subject's
        SP allocation comes from the explicit ``sps`` arg (or the fetched
        spread's ``sps``); EVs are never applied to a champions subject.

    Opposing reference mons left at ``subject_is_champions=False`` stay MAINLINE
    unless their own fetched spread is champions-tagged — exactly the nuance
    required so a champions defender and a mainline attacker can be compared.
    """
    base_stats = await pokeapi.get_base_stats(pokemon_name)
    types = await pokeapi.get_pokemon_types(pokemon_name)

    smogon_spread: Optional[dict] = None
    # Auto-fetch from Smogon if not provided
    if nature is None or evs is None:
        smogon_spread = await _get_common_spread(pokemon_name)
        if smogon_spread:
            if nature is None:
                nature = smogon_spread.get("nature", "serious")
            if evs is None:
                evs = smogon_spread.get("evs", {})
            if item is None:
                item = smogon_spread.get("item")
            if ability is None:
                ability = smogon_spread.get("ability")

    # Centralised ability resolver (mega > Smogon > pokeapi).
    from vgc_mcp_core.tools.ability_helpers import resolve_ability
    if ability is None:
        ability, _ = await resolve_ability(
            pokemon_name, pokeapi=pokeapi, smogon_client=_smogon_client,
        )

    nature_enum = Nature(nature.lower() if nature else "serious")

    # A fetched spread that is itself champions-tagged forces SP scale even for
    # an opposing reference mon (matches the calc's per-build format_system read).
    fetched_sp_spread = (
        _sps_from_smogon_spread(smogon_spread) if smogon_spread else None
    )
    use_champions = subject_is_champions or fetched_sp_spread is not None

    if use_champions:
        # Subject SP input wins; else fall back to the fetched champions sps;
        # else an empty StatPointSpread (subject with no SP data yet).
        if sps is not None:
            sp_spread = StatPointSpread(
                hp=sps.get("hp", 0),
                attack=sps.get("attack", 0),
                defense=sps.get("defense", 0),
                special_attack=sps.get("special_attack", 0),
                special_defense=sps.get("special_defense", 0),
                speed=sps.get("speed", 0),
            )
        else:
            sp_spread = fetched_sp_spread or StatPointSpread()

        return PokemonBuild(
            name=pokemon_name,
            base_stats=base_stats,
            types=types,
            nature=nature_enum,
            format_system="champions",
            sps=sp_spread,
            item=item,
            ability=ability,
        )

    evs_dict = evs or {}

    return PokemonBuild(
        name=pokemon_name,
        base_stats=base_stats,
        types=types,
        nature=nature_enum,
        evs=EVSpread(
            hp=evs_dict.get("hp", 0),
            attack=evs_dict.get("attack", 0),
            defense=evs_dict.get("defense", 0),
            special_attack=evs_dict.get("special_attack", 0),
            special_defense=evs_dict.get("special_defense", 0),
            speed=evs_dict.get("speed", 0)
        ),
        item=item,
        ability=ability
    )


def register_multicalc_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register multi-damage calculator tools."""
    global _smogon_client
    _smogon_client = smogon

    @mcp.tool(
        title="Calculate Offensive Coverage",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_offensive_coverage(
        attacker_name: Annotated[str, Field(description="Your Pokemon (e.g. 'landorus-therian')", min_length=1)],
        attacker_move: Annotated[str, Field(description="Attack to test (e.g. 'earthquake')", min_length=1)],
        defender_names: Annotated[list[str], Field(description="List of 5-10 Pokemon to test against (max 10, e.g. ['incineroar', 'rillaboom', 'flutter-mane'])")],
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch spreads from Smogon")] = True,
        attacker_nature: Annotated[Optional[str], Field(description="Attacker's nature (auto-fetched if not specified)")] = None,
        attacker_evs: Annotated[Optional[dict], Field(description="Attacker's EVs dict (auto-fetched if not specified)")] = None,
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (auto-fetched if not specified)")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability (auto-fetched if not specified)")] = None,
        attacker_sps: Annotated[Optional[dict], Field(description="Attacker's Stat Points dict for Champions (Reg MA) sessions")] = None,
        weather: Annotated[Optional[str], Field(description="Weather: 'sun', 'rain', 'sand', or 'snow'")] = None,
        terrain: Annotated[Optional[str], Field(description="Terrain: 'electric', 'grassy', 'psychic', or 'misty'")] = None,
        attacker_tera_type: Annotated[Optional[str], Field(description="Attacker's Tera type if Terastallized")] = None,
    ) -> dict:
        """Calculate damage from one attacker vs multiple defenders (offensive coverage analysis).

        Useful for understanding how well your Pokemon's attack covers common meta
        threats. Returns damage ranges, KO verdicts per defender, a summary of
        OHKO/2HKO counts, Showdown pastes, and a markdown table.
        """
        try:
            if len(defender_names) > 10:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 10 defenders supported. Please reduce the list.')

            # Champions (Reg MA) detection — only the user's subject (the
            # attacker) becomes SP-scale. Opposing defenders stay mainline
            # unless their own fetched Smogon spread is champions-tagged.
            is_champions = _detect_champions(attacker_name)

            # Fetch attacker data
            await pokeapi.get_base_stats(attacker_name)
            await pokeapi.get_pokemon_types(attacker_name)
            move = await pokeapi.get_move(attacker_move, user_name=attacker_name)

            # Build attacker (subject — SP-scale in a champions session)
            attacker = await _build_pokemon_from_smogon(
                attacker_name, pokeapi, attacker_nature, attacker_evs, attacker_item, attacker_ability,
                subject_is_champions=is_champions, sps=attacker_sps,
            )

            # Build all defenders in parallel
            start_time = time.monotonic()
            defender_tasks = [
                _build_pokemon_from_smogon(name, pokeapi) for name in defender_names
            ]
            defender_results = await asyncio.gather(*defender_tasks, return_exceptions=True)
            logger.debug(
                "Built %d defenders in %.1fms",
                len(defender_names), (time.monotonic() - start_time) * 1000
            )

            # Calculate damage against each defender
            matchups = []
            guaranteed_ohkos = 0
            possible_ohkos = 0
            twohkos = 0

            for defender_name, defender_or_err in zip(defender_names, defender_results):
                try:
                    if isinstance(defender_or_err, Exception):
                        raise defender_or_err
                    defender = defender_or_err

                    # Create modifiers (defender Intimidate event stacks for physical moves)
                    from vgc_mcp_core.tools.ability_helpers import compute_intimidate_attack_stage
                    is_phys = move.category.value == "physical"
                    intim, _ = compute_intimidate_attack_stage(
                        defender_ability=defender.ability,
                        attacker_ability=attacker.ability,
                        is_physical=is_phys,
                    )
                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attacker_item=attacker.item,
                        attacker_ability=attacker.ability,
                        defender_ability=defender.ability,
                        tera_type=attacker_tera_type,
                        tera_active=attacker_tera_type is not None,
                        weather=weather,
                        terrain=terrain,
                        attack_stage=intim if is_phys else 0,
                    )

                    # Calculate damage
                    result = calculate_damage(attacker, defender, move, modifiers)

                    # Determine KO verdict
                    ko_verdict = ""
                    if result.max_percent >= 100:
                        if result.min_percent >= 100:
                            ko_verdict = "OHKO"
                            guaranteed_ohkos += 1
                        else:
                            # Calculate OHKO probability (simplified)
                            ohko_prob = ((result.max_percent - 100) / (result.max_percent - result.min_percent)) * 100
                            ko_verdict = f"OHKO {ohko_prob:.1f}%"
                            possible_ohkos += 1
                    elif result.max_percent >= 50:
                        ko_verdict = "2HKO"
                        twohkos += 1
                    else:
                        ko_verdict = "3HKO+"

                    # Generate defender Showdown paste
                    defender_paste = pokemon_build_to_showdown(defender)

                    matchups.append({
                        "defender_name": defender_name,
                        "damage_range": f"{result.min_damage}-{result.max_damage}",
                        "damage_percent": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
                        "ko_verdict": ko_verdict,
                        "defender_showdown_paste": defender_paste
                    })

                except Exception as e:
                    matchups.append({
                        "defender_name": defender_name,
                        "error": str(e)
                    })

            # Generate attacker Showdown paste
            attacker_paste = pokemon_build_to_showdown(attacker)

            # Generate markdown table
            table_lines = ["| Defender | Damage | Result |"]
            table_lines.append("|----------|--------|--------|")
            for matchup in matchups:
                if "error" not in matchup:
                    table_lines.append(
                        f"| {matchup['defender_name'].title()} | {matchup['damage_percent']} | {matchup['ko_verdict']} |"
                    )

            markdown_table = "\n".join(table_lines)

            atk_alloc = attacker.sps if attacker.is_champions() else attacker.evs
            return {
                "attacker": {
                    "name": attacker_name,
                    "spread": f"{attacker.nature.value.title()} {atk_alloc.attack}/{atk_alloc.special_attack}/{atk_alloc.speed}",
                    "showdown_paste": attacker_paste
                },
                "move": attacker_move,
                "matchups": matchups,
                "summary": {
                    "guaranteed_ohkos": guaranteed_ohkos,
                    "possible_ohkos": possible_ohkos,
                    "twohkos": twohkos,
                    "total_tested": len(defender_names)
                },
                "markdown_table": markdown_table
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Calculate Defensive Threats",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_defensive_threats(
        defender_name: Annotated[str, Field(description="Your Pokemon (e.g. 'ogerpon-hearthflame')", min_length=1)],
        attacker_configs: Annotated[list[dict], Field(description="List of attacker configs (max 10), each with 'name' and 'move' plus optional 'nature', 'evs', 'item', 'ability', 'tera_type' (e.g. {'name': 'urshifu', 'move': 'surging-strikes', 'item': 'choice-scarf'})")],
        defender_nature: Annotated[Optional[str], Field(description="Defender's nature (auto-fetched if not specified)")] = None,
        defender_evs: Annotated[Optional[dict], Field(description="Defender's EVs dict (auto-fetched if not specified)")] = None,
        defender_item: Annotated[Optional[str], Field(description="Defender's item (auto-fetched if not specified)")] = None,
        defender_ability: Annotated[Optional[str], Field(description="Defender's ability (auto-fetched if not specified)")] = None,
        defender_tera_type: Annotated[Optional[str], Field(description="Defender's Tera type if Terastallizing")] = None,
        defender_sps: Annotated[Optional[dict], Field(description="Defender's Stat Points dict for Champions (Reg MA) sessions")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch spreads from Smogon")] = True,
    ) -> dict:
        """Calculate damage from multiple attackers vs one defender (threat analysis).

        Shows which threats can OHKO or 2HKO your Pokemon, helping identify
        defensive gaps. Returns per-attacker damage, survival chances, and a
        summary of guaranteed OHKOs vs survivable hits.
        """
        try:
            if len(attacker_configs) > 10:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 10 attackers supported. Please reduce the list.')

            # Champions (Reg MA) detection — only the user's subject (the
            # defender) becomes SP-scale. Opposing attacker threats stay mainline
            # unless their own fetched Smogon spread is champions-tagged.
            is_champions = _detect_champions(defender_name)

            # Build defender (subject — SP-scale in a champions session)
            defender = await _build_pokemon_from_smogon(
                defender_name, pokeapi, defender_nature, defender_evs, defender_item, defender_ability,
                subject_is_champions=is_champions, sps=defender_sps,
            )
            defender.tera_type = defender_tera_type

            # Build all attackers and fetch moves in parallel
            valid_configs = [c for c in attacker_configs if c.get("name") and c.get("move")]

            async def _build_attacker_with_move(config):
                attacker = await _build_pokemon_from_smogon(
                    config["name"], pokeapi,
                    config.get("nature"), config.get("evs"),
                    config.get("item"), config.get("ability")
                )
                attacker.tera_type = config.get("tera_type")
                move = await pokeapi.get_move(config["move"], user_name=config["name"])
                return attacker, move

            start_time = time.monotonic()
            build_results = await asyncio.gather(
                *[_build_attacker_with_move(c) for c in valid_configs],
                return_exceptions=True
            )
            logger.debug(
                "Built %d attackers in %.1fms",
                len(valid_configs), (time.monotonic() - start_time) * 1000
            )

            # Calculate damage from each attacker
            threats = []
            guaranteed_ohkos = 0
            survivable = 0

            for config, build_result in zip(valid_configs, build_results):
                attacker_name = config["name"]
                move_name = config["move"]

                try:
                    if isinstance(build_result, Exception):
                        raise build_result
                    attacker, move = build_result

                    # Create modifiers (defender Intimidate stacks for physical moves)
                    from vgc_mcp_core.tools.ability_helpers import compute_intimidate_attack_stage
                    is_phys = move.category.value == "physical"
                    intim, _ = compute_intimidate_attack_stage(
                        defender_ability=defender.ability,
                        attacker_ability=attacker.ability,
                        is_physical=is_phys,
                    )
                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attacker_item=attacker.item,
                        attacker_ability=attacker.ability,
                        defender_ability=defender.ability,
                        tera_type=attacker.tera_type,
                        tera_active=attacker.tera_type is not None,
                        defender_tera_type=defender.tera_type,
                        defender_tera_active=defender.tera_type is not None,
                        attack_stage=intim if is_phys else 0,
                    )

                    # Calculate damage
                    result = calculate_damage(attacker, defender, move, modifiers)

                    # Determine survival
                    survival_chance = 100.0
                    ko_verdict = "Survives"
                    if result.max_percent >= 100:
                        if result.min_percent >= 100:
                            ko_verdict = "OHKO"
                            guaranteed_ohkos += 1
                            survival_chance = 0.0
                        else:
                            # Calculate survival probability
                            survival_chance = ((100 - result.max_percent) / (result.max_percent - result.min_percent)) * 100
                            ko_verdict = f"OHKO {100 - survival_chance:.1f}%"
                    else:
                        survivable += 1

                    threats.append({
                        "attacker_name": attacker_name,
                        "move": move_name,
                        "damage_range": f"{result.min_damage}-{result.max_damage}",
                        "damage_percent": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
                        "survival_chance": survival_chance,
                        "ko_verdict": ko_verdict
                    })

                except Exception as e:
                    threats.append({
                        "attacker_name": config.get("name", "unknown"),
                        "error": str(e)
                    })

            # Generate defender Showdown paste
            defender_paste = pokemon_build_to_showdown(defender)

            def_alloc = defender.sps if defender.is_champions() else defender.evs
            return {
                "defender": {
                    "name": defender_name,
                    "spread": f"{defender.nature.value.title()} {def_alloc.hp}/{def_alloc.defense}/{def_alloc.special_defense}",
                    "showdown_paste": defender_paste
                },
                "threats": threats,
                "summary": {
                    "guaranteed_ohkos": guaranteed_ohkos,
                    "survivable": survivable,
                    "total_tested": len(attacker_configs)
                }
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Calculate Team Coverage Matrix",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calculate_team_coverage_matrix(
        team_pokemon: Annotated[list[dict], Field(description="List of team member configs (max 6), each with 'name' and 'move' plus optional 'nature', 'evs', 'item', 'ability' (e.g. {'name': 'landorus', 'move': 'earthquake'}). In a Champions (Reg MA) session a member may carry an 'sps' dict (Stat Points) instead of 'evs'")],
        meta_threats: Annotated[Optional[list[str]], Field(description="List of meta threats to test against, capped at 15 (default: built-in top 15)")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="Auto-fetch spreads from Smogon")] = True,
    ) -> dict:
        """Calculate a team coverage matrix: team of up to 6 vs meta threats.

        Shows which team members can OHKO/2HKO which threats, identifying
        coverage gaps. Returns the matrix, best answers per threat, gap list,
        and a markdown table.
        """
        try:
            if len(team_pokemon) > 6:
                return error_response(ErrorCodes.INVALID_PARAMETER, 'Maximum 6 team members supported.')

            # Champions (Reg MA) detection — only the user's team members (the
            # subjects) become SP-scale. Meta threats stay mainline unless their
            # own fetched Smogon spread is champions-tagged. Infer from the full
            # set of team-member names so any Mega/Champions signal is caught.
            is_champions = _detect_champions(
                *[c.get("name") for c in team_pokemon if c.get("name")]
            )

            # Get meta threats if not provided
            if meta_threats is None:
                # Default top meta threats (simplified - would fetch from Smogon in production)
                meta_threats = [
                    "incineroar", "rillaboom", "flutter-mane", "urshifu-rapid-strike",
                    "landorus-therian", "chien-pao", "chi-yu", "ogerpon-hearthflame",
                    "tornadus", "iron-hands", "amoonguss", "farigiraf",
                    "ting-lu", "wo-chien", "iron-boulder"
                ]

            if len(meta_threats) > 15:
                meta_threats = meta_threats[:15]  # Limit to 15 threats

            # Build team members in parallel
            valid_members = [c for c in team_pokemon if c.get("name") and c.get("move")]

            async def _build_member(config):
                pokemon = await _build_pokemon_from_smogon(
                    config["name"], pokeapi,
                    config.get("nature"), config.get("evs"),
                    config.get("item"), config.get("ability"),
                    subject_is_champions=is_champions, sps=config.get("sps"),
                )
                move = await pokeapi.get_move(config["move"], user_name=config["name"])
                return {"name": config["name"], "pokemon": pokemon, "move": move, "move_name": config["move"]}

            start_time = time.monotonic()
            member_results = await asyncio.gather(
                *[_build_member(c) for c in valid_members],
                return_exceptions=True
            )

            team_members = []
            for config, result in zip(valid_members, member_results):
                if isinstance(result, Exception):
                    team_members.append({"name": config["name"], "error": str(result)})
                else:
                    team_members.append(result)

            # Build all threats in parallel
            threat_tasks = [_build_pokemon_from_smogon(t, pokeapi) for t in meta_threats]
            threat_results = await asyncio.gather(*threat_tasks, return_exceptions=True)
            logger.debug(
                "Built %d members + %d threats in %.1fms",
                len(valid_members), len(meta_threats),
                (time.monotonic() - start_time) * 1000
            )

            # Calculate coverage matrix
            coverage_matrix = []
            best_answers = {}
            coverage_gaps = []

            for threat_name, threat_or_err in zip(meta_threats, threat_results):
                try:
                    if isinstance(threat_or_err, Exception):
                        raise threat_or_err
                    threat = threat_or_err

                    threat_row = []
                    threat_ohkos = []

                    for member in team_members:
                        if "error" in member:
                            threat_row.append("Error")
                            continue

                        try:
                            from vgc_mcp_core.tools.ability_helpers import (
                                compute_intimidate_attack_stage,
                            )
                            is_phys = member["move"].category.value == "physical"
                            intim, _ = compute_intimidate_attack_stage(
                                defender_ability=threat.ability,
                                attacker_ability=member["pokemon"].ability,
                                is_physical=is_phys,
                            )
                            modifiers = DamageModifiers(
                                is_doubles=True,
                                attacker_item=member["pokemon"].item,
                                attacker_ability=member["pokemon"].ability,
                                defender_ability=threat.ability,
                                attack_stage=intim if is_phys else 0,
                            )

                            result = calculate_damage(member["pokemon"], threat, member["move"], modifiers)

                            # Determine verdict
                            if result.max_percent >= 100:
                                if result.min_percent >= 100:
                                    verdict = "OHKO"
                                    threat_ohkos.append(member["name"])
                                else:
                                    verdict = f"OHKO {((result.max_percent - 100) / (result.max_percent - result.min_percent) * 100):.0f}%"
                            elif result.max_percent >= 50:
                                verdict = "2HKO"
                            elif result.max_percent >= 33:
                                verdict = "3HKO"
                            else:
                                verdict = "Resists"

                            threat_row.append(verdict)

                        except Exception:
                            threat_row.append("Error")

                    coverage_matrix.append(threat_row)

                    # Track best answers
                    if threat_ohkos:
                        best_answers[threat_name] = threat_ohkos
                    else:
                        coverage_gaps.append(threat_name)

                except Exception:
                    coverage_matrix.append(["Error"] * len(team_members))

            # Generate markdown table
            table_lines = ["| Team Member | " + " | ".join([t.title() for t in meta_threats]) + " |"]
            table_lines.append("|-------------|" + "|".join(["---"] * (len(meta_threats) + 1)) + "|")

            for i, member in enumerate(team_members):
                member_name = member.get("name", "Unknown")
                row = [member_name] + [coverage_matrix[j][i] for j in range(len(meta_threats))]
                table_lines.append("| " + " | ".join(row) + " |")

            markdown_table = "\n".join(table_lines)

            return {
                "team": [m.get("name") for m in team_members],
                "threats_analyzed": meta_threats,
                "coverage_matrix": coverage_matrix,
                "best_answers": best_answers,
                "coverage_gaps": coverage_gaps,
                "markdown_table": markdown_table
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
