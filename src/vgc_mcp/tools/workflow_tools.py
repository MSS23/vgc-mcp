"""High-level workflow coordinator tools for improved user experience.

These tools combine multiple operations into single, intuitive commands
for common VGC teambuilding workflows.
"""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.tools import (
    workflow_calc_handlers,
    workflow_spread_handlers,
    workflow_team_handlers,
)


def register_workflow_tools(mcp: FastMCP, pokeapi, smogon, team_manager, analyzer):
    """Register high-level workflow tools with the MCP server."""

    @mcp.tool(
        title="Full Team Check",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def full_team_check(
        paste: Annotated[Optional[str], Field(description="Showdown team paste (Pokemon separated by blank lines). If omitted, analyzes the currently loaded team")] = None,
        detailed: Annotated[bool, Field(description="True for full analysis (grade, tournament readiness, legality, strengths/weaknesses, fix suggestions); False for a quick summary (major weaknesses, unresisted types, speed range)")] = True,
    ) -> dict:
        """Team analysis with configurable detail level.

        detailed=True returns overall_grade (A-F), tournament_ready, legality,
        top strengths/weaknesses, and the single most impactful fix.
        detailed=False returns a quick summary (team size, major weaknesses,
        unresisted types, speed range) - useful for fast iteration. Note:
        quick mode on a raw paste is limited; load the team first for the
        full quick analysis.
        """
        return await workflow_team_handlers.full_team_check(
            team_manager,
            analyzer,
            paste=paste,
            detailed=detailed,
        )

    @mcp.tool(
        title="Import and Analyze Team",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def import_and_analyze(
        paste: Annotated[str, Field(description="Showdown format team paste (Pokemon separated by blank lines)", min_length=1)],
        load_to_team: Annotated[bool, Field(description="If True, REPLACES the currently loaded team with this paste so further tools can use it")] = True,
    ) -> dict:
        """Import a Showdown team paste and immediately analyze it.

        Combines import + legality check + coverage analysis + speed structure
        into one call. Returns the imported builds, legality verdict, coverage
        holes, speed tiers, and top suggested improvements. With load_to_team
        (default) the current team is cleared and replaced.
        """
        return await workflow_team_handlers.import_and_analyze(
            pokeapi,
            team_manager,
            analyzer,
            paste=paste,
            load_to_team=load_to_team,
        )

    @mcp.tool(
        title="Fix Team Issues",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def fix_team_issues(
        paste: Annotated[Optional[str], Field(description="Showdown team paste to analyze. If omitted, uses the currently loaded team")] = None,
    ) -> dict:
        """Identify team legality/structure issues and suggest specific fixes.

        Checks banned Pokemon, restricted count, item clause, species clause,
        and team size. Returns each issue with severity, an actionable fix,
        and a priority order for addressing them.
        """
        return await workflow_team_handlers.fix_team_issues(team_manager, paste=paste)

    @mcp.tool(
        title="Add Pokemon with Smart Defaults",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=False,
            openWorldHint=True,
        ),
    )
    async def add_pokemon_smart(
        pokemon_name: Annotated[str, Field(description="Pokemon to add (use hyphens for forms, e.g. 'flutter-mane')", min_length=1)],
        role: Annotated[str, Field(description="Role hint: 'sweeper', 'wall', 'support', 'trick_room', 'bulky_offense', 'mixed', or 'auto' (detects the best role from base stats)")] = "auto",
    ) -> dict:
        """Add a Pokemon to the team with an intelligently suggested build.

        Picks nature, investment, and ability from the Pokemon's base stats
        and the detected role. Auto-detects the regulation/format from the
        Pokemon name (Champions builds get Stat Points instead of EVs) and
        surfaces `regulation_auto_detected` when inference applied. Returns
        the added build with reasoning and a Showdown paste.
        """
        return await workflow_team_handlers.add_pokemon_smart(
            pokeapi,
            team_manager,
            pokemon_name=pokemon_name,
            role=role,
        )

    @mcp.tool(
        title="Suggest EV Spread",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_ev_spread(
        pokemon_name: Annotated[str, Field(description="Your Pokemon (e.g. 'entei', 'flutter-mane')", min_length=1)],
        nature: Annotated[str, Field(description="Nature to use, or 'auto' to suggest one based on constraints and prioritize mode")] = "auto",
        outspeed_targets: Annotated[Optional[list[str]], Field(description="Pokemon names to outspeed, assuming +Speed nature 252 EVs on the target (e.g. ['arcanine-hisui', 'iron-bundle'])")] = None,
        survive_hits: Annotated[Optional[list[dict]], Field(description="Attacks to survive, each a dict with 'attacker' and 'move', plus optional 'item' (auto-fetched from Smogon usage if omitted) and 'ability'")] = None,
        ko_targets: Annotated[Optional[list[dict]], Field(description="KOs to achieve, each a dict with 'defender' and 'move', plus optional 'evs' (defender HP EVs, default 0)")] = None,
        prioritize: Annotated[str, Field(description="Where leftover EVs go: 'bulk' (maximize survival), 'offense' (maximize damage), or 'speed' (maximize speed tier)")] = "bulk",
    ) -> dict:
        """Design an optimal EV spread meeting multiple constraints in ONE call.

        The go-to tool for spread design - handles speed benchmarks, survival
        requirements, and KO targets together instead of 5+ separate calls.
        Returns the spread, suggested nature, final level-50 stats,
        benchmarks_met / benchmarks_failed, and a Showdown-ready summary.
        Auto-detects Champions (Reg MA) sessions and emits Stat Points there.

        Example: suggest_ev_spread(pokemon_name="rillaboom",
        outspeed_targets=["amoonguss"],
        survive_hits=[{"attacker": "flutter-mane", "move": "moonblast"}],
        ko_targets=[{"defender": "palafin", "move": "wood-hammer"}])
        """
        return await workflow_spread_handlers.suggest_ev_spread(
            pokeapi,
            smogon,
            pokemon_name=pokemon_name,
            nature=nature,
            outspeed_targets=outspeed_targets,
            survive_hits=survive_hits,
            ko_targets=ko_targets,
            prioritize=prioritize,
        )

    @mcp.tool(
        title="Quick Damage Check",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def quick_damage_check(
        attacker: Annotated[str, Field(description="Attacking Pokemon name", min_length=1)],
        defender: Annotated[str, Field(description="Defending Pokemon name", min_length=1)],
        move: Annotated[str, Field(description="Move name to use (e.g. 'surging-strikes')", min_length=1)],
        attacker_item: Annotated[Optional[str], Field(description="Attacker's item (e.g. 'life-orb', 'choice-band')")] = None,
        attacker_ability: Annotated[Optional[str], Field(description="Attacker's ability (auto-detected from PokeAPI if not specified)")] = None,
        defender_hp_evs: Annotated[int, Field(ge=0, le=252, description="Defender's HP EVs (0-252)")] = 0,
        defender_def_evs: Annotated[int, Field(ge=0, le=252, description="Defender's Def/SpD EVs (0-252); applied to the relevant defensive stat for the move's category")] = 0,
        is_doubles: Annotated[bool, Field(description="True applies the doubles spread-move 0.75x reduction")] = True,
    ) -> dict:
        """Quick damage calculation with smart defaults - ONE call for damage info.

        Uses competitive defaults (252 offensive EVs, optimal nature) so you
        don't need to specify everything. Returns the damage/percent range,
        whether the defender survives, a KO verdict, and which items or
        abilities would flip the outcome.
        """
        return await workflow_calc_handlers.quick_damage_check(
            pokeapi,
            attacker=attacker,
            defender=defender,
            move=move,
            attacker_item=attacker_item,
            attacker_ability=attacker_ability,
            defender_hp_evs=defender_hp_evs,
            defender_def_evs=defender_def_evs,
            is_doubles=is_doubles,
        )

    @mcp.tool(
        title="Analyze Speed Matchup",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def analyze_speed_matchup(
        my_pokemon: Annotated[str, Field(description="Your Pokemon name", min_length=1)],
        opponent_pokemon: Annotated[str, Field(description="Opponent's Pokemon name", min_length=1)],
        my_nature: Annotated[str, Field(description="Your Pokemon's nature")] = "jolly",
        my_speed_evs: Annotated[int, Field(ge=0, le=252, description="Your Speed EVs (0-252)")] = 252,
        opponent_nature: Annotated[str, Field(description="Opponent's nature")] = "jolly",
        opponent_speed_evs: Annotated[int, Field(ge=0, le=252, description="Opponent's Speed EVs (0-252)")] = 252,
        include_scenarios: Annotated[Optional[list[str]], Field(description="Extra scenarios to check: 'tailwind' (2x), 'trick_room' (slower first), 'paralysis' (0.5x), 'icy_wind' (-1 stage), 'choice_scarf' (1.5x)")] = None,
    ) -> dict:
        """Compare Speed between two Pokemon across various scenarios.

        Answers "who's faster?" in normal play plus any requested scenarios
        (Tailwind, Trick Room, paralysis, Icy Wind, Choice Scarf). Also
        reports the minimum EVs needed to outspeed if you're behind.
        """
        return await workflow_calc_handlers.analyze_speed_matchup(
            pokeapi,
            my_pokemon=my_pokemon,
            opponent_pokemon=opponent_pokemon,
            my_nature=my_nature,
            my_speed_evs=my_speed_evs,
            opponent_nature=opponent_nature,
            opponent_speed_evs=opponent_speed_evs,
            include_scenarios=include_scenarios,
        )

    @mcp.tool(
        title="Check Team vs Threat",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_team_vs_threat(
        threat_pokemon: Annotated[str, Field(description="The threatening Pokemon to check the loaded team against", min_length=1)],
        threat_nature: Annotated[str, Field(description="Threat's nature")] = "modest",
        threat_offensive_evs: Annotated[int, Field(ge=0, le=252, description="Threat's offensive EVs (0-252), applied to its stronger attacking stat")] = 252,
        threat_item: Annotated[Optional[str], Field(description="Threat's item (e.g. 'choice-specs')")] = None,
        threat_ability: Annotated[Optional[str], Field(description="Threat's ability (auto-detected if not specified)")] = None,
        check_moves: Annotated[Optional[list[str]], Field(description="Specific moves to check (top 2 used); defaults to common STAB moves for the threat's types")] = None,
    ) -> dict:
        """Check how your currently loaded team handles a specific threat.

        Calculates damage from the threat to each team member and vice versa,
        giving each member a verdict (Counters / Checks / Revenge kills /
        Loses to) plus overall safe_switches and answers lists. Requires a
        loaded team (import_showdown_team first).
        """
        return await workflow_team_handlers.check_team_vs_threat(
            pokeapi,
            team_manager,
            threat_pokemon=threat_pokemon,
            threat_nature=threat_nature,
            threat_offensive_evs=threat_offensive_evs,
            threat_item=threat_item,
            threat_ability=threat_ability,
            check_moves=check_moves,
        )

    @mcp.tool(
        title="Design Pokemon for Role",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def design_pokemon_for_role(
        pokemon_name: Annotated[str, Field(description="Pokemon to build", min_length=1)],
        role: Annotated[str, Field(description="Desired role: 'auto' (detect from stats), 'sweeper' (fast + offensive), 'bulky_attacker' (offense with HP), 'wall' (max bulk), 'support' (bulk with some speed), or 'trick_room' (min speed, max offense)")] = "auto",
        speed_benchmark: Annotated[Optional[str], Field(description="Pokemon to outspeed (e.g. 'iron-bundle'); Speed EVs are tuned to beat its max-investment speed")] = None,
        survive_hit: Annotated[Optional[dict], Field(description="Attack to survive as a dict with 'attacker' and 'move'")] = None,
        item: Annotated[Optional[str], Field(description="Item to use (auto-suggested from the role if not provided)")] = None,
    ) -> dict:
        """Design a complete Pokemon build for a specific role in ONE call.

        Determines nature, EV spread, item, and suggested moves from the
        Pokemon's stats and the desired role. Returns the full build with
        reasoning, level-50 final stats, and a Showdown-format block.
        """
        return await workflow_calc_handlers.design_pokemon_for_role(
            pokeapi,
            pokemon_name=pokemon_name,
            role=role,
            speed_benchmark=speed_benchmark,
            survive_hit=survive_hit,
            item=item,
        )

    @mcp.tool(
        title="Damage vs Smogon Sets",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def calc_damage_vs_smogon_sets(
        my_pokemon: Annotated[str, Field(description="Your Pokemon name", min_length=1)],
        my_nature: Annotated[str, Field(description="Your Pokemon's nature", min_length=1)],
        my_hp_evs: Annotated[int, Field(ge=0, le=252, description="Your HP EVs (0-252). In a Champions session these are Stat Points (0-32, 66 total).")] = 0,
        my_atk_evs: Annotated[int, Field(ge=0, le=252, description="Your Attack EVs (0-252); Stat Points in Champions")] = 0,
        my_def_evs: Annotated[int, Field(ge=0, le=252, description="Your Defense EVs (0-252); Stat Points in Champions")] = 0,
        my_spa_evs: Annotated[int, Field(ge=0, le=252, description="Your Sp. Atk EVs (0-252); Stat Points in Champions")] = 0,
        my_spd_evs: Annotated[int, Field(ge=0, le=252, description="Your Sp. Def EVs (0-252); Stat Points in Champions")] = 0,
        my_spe_evs: Annotated[int, Field(ge=0, le=252, description="Your Speed EVs (0-252); Stat Points in Champions")] = 0,
        my_spread: Annotated[Optional[str], Field(description="Whole allocation as an 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions); overrides the per-stat my_*_evs values")] = None,
        my_item: Annotated[Optional[str], Field(description="Your item")] = None,
        my_ability: Annotated[Optional[str], Field(description="Your ability (auto-detected if not specified)")] = None,
        my_tera_type: Annotated[Optional[str], Field(description="Your Tera type if active (replaces your defensive typing)")] = None,
        opponent_pokemon: Annotated[str, Field(description="Opponent Pokemon to check against (required)")] = "",
        move: Annotated[str, Field(description="Move being used (required)")] = "",
        direction: Annotated[str, Field(description="'from' = opponent attacks you with the move; 'to' = you attack the opponent")] = "from",
        num_sets: Annotated[int, Field(ge=1, description="Number of top Smogon spreads to check")] = 3,
        attacker_stage: Annotated[int, Field(ge=-6, le=6, description="Extra offensive stat stage on whichever side is attacking (e.g. +2 after Swords Dance). Do not pass -1 for Intimidate — use `intimidate`.")] = 0,
        intimidate: Annotated[Optional[bool], Field(description="Intimidate on the attacker. Omit (None) = automatic: applied only when the defending side's Pokemon actually has Intimidate (Incineroar, Landorus-T, Mega Manectric...). True = the user asked for the Intimidate calc (e.g. an Intimidate partner is on the field) — apply -1 Atk even if the defender itself lacks it. False = never apply it. Attacker-side blockers (Clear Body, Inner Focus...) are always respected.")] = None,
    ) -> dict:
        """Calculate damage using YOUR exact spread vs the top Smogon sets.

        Answers questions like "how much damage does my 252 HP / 116 Def Entei
        take from the top 3 Urshifu sets?" or "can my Flutter Mane OHKO the
        common Incineroar spreads?". Returns your build's stats, the top N
        Smogon sets with usage % and their exact spread, a damage calc per
        set, a survival/KO summary, and `meta_info` naming the chaos
        month/format/rating. Champions-aware: in a Champions session your
        `my_*_evs` are Stat Points and the opponent sets are SP spreads.
        If the defending side's Pokemon has Intimidate (or `intimidate=True`
        was requested) and the move is physical, each set also carries
        `after_intimidate` (the -1 Atk calc), unless the attacker's ability
        blocks or reverses it — see the top-level `intimidate` field. For a head-to-head ("my X vs Y"), call once with
        direction='to' for your move and once with direction='from' for
        their retaliation.
        """
        return await workflow_calc_handlers.calc_damage_vs_smogon_sets(
            pokeapi,
            smogon,
            my_pokemon=my_pokemon,
            my_nature=my_nature,
            my_hp_evs=my_hp_evs,
            my_atk_evs=my_atk_evs,
            my_def_evs=my_def_evs,
            my_spa_evs=my_spa_evs,
            my_spd_evs=my_spd_evs,
            my_spe_evs=my_spe_evs,
            my_spread=my_spread,
            my_item=my_item,
            my_ability=my_ability,
            my_tera_type=my_tera_type,
            opponent_pokemon=opponent_pokemon,
            move=move,
            direction=direction,
            num_sets=num_sets,
            attacker_stage=attacker_stage,
            intimidate=intimidate,
        )

    @mcp.tool(
        title="Optimize EV Spread",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def optimize_spread(
        pokemon_name: Annotated[str, Field(description="Your Pokemon", min_length=1)],
        current_nature: Annotated[Optional[str], Field(description="Current nature (optimal one is suggested if not provided)")] = None,
        current_hp_evs: Annotated[int, Field(ge=0, le=252, description="Current HP EVs, used as starting point (0-252)")] = 0,
        current_atk_evs: Annotated[int, Field(ge=0, le=252, description="Current Attack EVs, used as starting point (0-252)")] = 0,
        current_def_evs: Annotated[int, Field(ge=0, le=252, description="Current Defense EVs, used as starting point (0-252)")] = 0,
        current_spa_evs: Annotated[int, Field(ge=0, le=252, description="Current Sp. Atk EVs, used as starting point (0-252)")] = 0,
        current_spd_evs: Annotated[int, Field(ge=0, le=252, description="Current Sp. Def EVs, used as starting point (0-252)")] = 0,
        current_spe_evs: Annotated[int, Field(ge=0, le=252, description="Current Speed EVs, used as starting point (0-252)")] = 0,
        current_spread: Annotated[Optional[str], Field(description="Whole allocation as an 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions); overrides the per-stat current_*_evs values")] = None,
        target_speed: Annotated[Optional[int], Field(description="Exact Speed stat you want to hit")] = None,
        outspeed_pokemon: Annotated[Optional[str], Field(description="Pokemon you want to outspeed")] = None,
        outspeed_pokemon_nature: Annotated[str, Field(description="Outspeed target's nature")] = "jolly",
        outspeed_pokemon_evs: Annotated[int, Field(ge=0, le=252, description="Outspeed target's Speed EVs (0-252)")] = 252,
        survive_pokemon: Annotated[Optional[str], Field(description="Attacker to survive against")] = None,
        survive_move: Annotated[Optional[str], Field(description="Move to survive")] = None,
        survive_pokemon_nature: Annotated[str, Field(description="Attacker's nature (ignored if use_smogon_spreads=True)")] = "adamant",
        survive_pokemon_evs: Annotated[int, Field(ge=0, le=252, description="Attacker's offensive EVs (0-252; ignored if use_smogon_spreads=True)")] = 252,
        survive_pokemon_item: Annotated[Optional[str], Field(description="Attacker's item (e.g. 'choice-specs') - REQUIRED if use_smogon_spreads=True")] = None,
        survive_pokemon_ability: Annotated[Optional[str], Field(description="Attacker's ability")] = None,
        use_smogon_spreads: Annotated[bool, Field(description="If True, fetch the attacker's top Smogon spreads and calc against each")] = False,
        smogon_spread_count: Annotated[int, Field(ge=1, description="Number of top Smogon spreads to check")] = 3,
        max_damage_percent: Annotated[Optional[float], Field(ge=0, description="Max damage % to take from the survive attack (e.g. 80.0 = take at most 80%)")] = None,
        target_nko: Annotated[Optional[int], Field(ge=1, description="Target N-HKO vs the survive attack (2 = be 2HKO'd = survive 1 hit; 3 = survive 2 hits)")] = None,
        target_hp_stat: Annotated[Optional[int], Field(description="Exact HP stat you want")] = None,
        target_atk_stat: Annotated[Optional[int], Field(description="Exact Attack stat you want")] = None,
        target_def_stat: Annotated[Optional[int], Field(description="Exact Defense stat you want")] = None,
        target_spa_stat: Annotated[Optional[int], Field(description="Exact Sp. Atk stat you want")] = None,
        target_spd_stat: Annotated[Optional[int], Field(description="Exact Sp. Def stat you want")] = None,
    ) -> dict:
        """Optimize or fix an EV spread to meet specific stat/benchmark targets.

        Reverse-engineers the exact EVs and nature needed for any mix of: an
        exact Speed stat, a Pokemon to outspeed, an attack to survive (100%),
        a max damage % to take, a target N-HKO, or exact stat values. Returns
        the optimized spread and nature, changes from the current spread,
        level-50 final stats, benchmarks_hit, ev_savings, and (with
        use_smogon_spreads) per-spread Smogon damage calcs.

        Examples:
            optimize_spread(pokemon_name="entei", survive_pokemon="urshifu", survive_move="surging-strikes")
            optimize_spread(pokemon_name="entei", survive_pokemon="urshifu", survive_move="surging-strikes", max_damage_percent=80)
            optimize_spread(pokemon_name="entei", survive_pokemon="flutter-mane", survive_move="moonblast", target_nko=2)
            optimize_spread(pokemon_name="entei", survive_pokemon="flutter-mane", survive_move="power-gem", survive_pokemon_item="choice-specs", use_smogon_spreads=True)
        """
        return await workflow_spread_handlers.optimize_spread(
            pokeapi,
            smogon,
            pokemon_name=pokemon_name,
            current_nature=current_nature,
            current_hp_evs=current_hp_evs,
            current_atk_evs=current_atk_evs,
            current_def_evs=current_def_evs,
            current_spa_evs=current_spa_evs,
            current_spd_evs=current_spd_evs,
            current_spe_evs=current_spe_evs,
            current_spread=current_spread,
            target_speed=target_speed,
            outspeed_pokemon=outspeed_pokemon,
            outspeed_pokemon_nature=outspeed_pokemon_nature,
            outspeed_pokemon_evs=outspeed_pokemon_evs,
            survive_pokemon=survive_pokemon,
            survive_move=survive_move,
            survive_pokemon_nature=survive_pokemon_nature,
            survive_pokemon_evs=survive_pokemon_evs,
            survive_pokemon_item=survive_pokemon_item,
            survive_pokemon_ability=survive_pokemon_ability,
            use_smogon_spreads=use_smogon_spreads,
            smogon_spread_count=smogon_spread_count,
            max_damage_percent=max_damage_percent,
            target_nko=target_nko,
            target_hp_stat=target_hp_stat,
            target_atk_stat=target_atk_stat,
            target_def_stat=target_def_stat,
            target_spa_stat=target_spa_stat,
            target_spd_stat=target_spd_stat,
        )

    @mcp.tool(
        title="Compare Pokemon Options",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def compare_pokemon_options(
        pokemon_a: Annotated[str, Field(description="First Pokemon to compare", min_length=1)],
        pokemon_b: Annotated[str, Field(description="Second Pokemon to compare", min_length=1)],
        role: Annotated[str, Field(description="Context for the comparison: 'auto' (detect from stats), 'physical_attacker', 'special_attacker', 'support', 'wall', or 'speed_control'")] = "auto",
        check_vs_pokemon: Annotated[Optional[str], Field(description="Also check both candidates against this specific threat")] = None,
    ) -> dict:
        """Compare two Pokemon to help decide which fits your team better.

        Answers "should I use Entei or Arcanine-Hisui?" - compares base stats,
        max speed tiers, typing (shared/unique weaknesses and resistances),
        abilities, and Smogon usage, then returns a verdict with reasoning.
        """
        return await workflow_calc_handlers.compare_pokemon_options(
            pokeapi,
            smogon,
            pokemon_a=pokemon_a,
            pokemon_b=pokemon_b,
            role=role,
            check_vs_pokemon=check_vs_pokemon,
        )

    @mcp.tool(
        title="Find Counters for Threat",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_counter_for(
        threat: Annotated[str, Field(description="The Pokemon you need to counter", min_length=1)],
        check_team_first: Annotated[bool, Field(description="Check the currently loaded team for existing answers")] = True,
        suggest_pokemon: Annotated[bool, Field(description="Suggest popular meta Pokemon as counters")] = True,
        max_suggestions: Annotated[int, Field(ge=1, description="Maximum Pokemon to suggest")] = 5,
    ) -> dict:
        """Find counters for a threatening Pokemon.

        Answers "what beats Flutter Mane?" - checks your current team for
        answers, type advantages (resist + hit super effectively), speed
        matchups, and common meta counters, then recommends the best approach.
        """
        return await workflow_team_handlers.find_counter_for(
            pokeapi,
            team_manager,
            threat=threat,
            check_team_first=check_team_first,
            suggest_pokemon=suggest_pokemon,
            max_suggestions=max_suggestions,
        )

    @mcp.tool(
        title="Evaluate Pokemon Core",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def evaluate_core(
        pokemon_list: Annotated[list[str], Field(description="2-4 Pokemon names forming the core")],
        suggest_partners: Annotated[bool, Field(description="Suggest Pokemon that complement the core's gaps")] = True,
        max_partners: Annotated[int, Field(ge=1, description="Number of partner suggestions to return")] = 3,
    ) -> dict:
        """Evaluate a Pokemon core (2-4 Pokemon) for synergy.

        Answers "is Kyogre + Flutter Mane a good core?" - checks type synergy
        (shared weaknesses, covered gaps), speed tiers and speed control,
        offensive coverage, and role redundancy. Returns a 1-10 synergy score,
        issues found, and suggested partner Pokemon.
        """
        return await workflow_team_handlers.evaluate_core(
            pokeapi,
            pokemon_list=pokemon_list,
            suggest_partners=suggest_partners,
            max_partners=max_partners,
        )
