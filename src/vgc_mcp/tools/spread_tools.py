"""MCP tools for EV spread optimization."""

from typing import Annotated, Any, Optional, Union, cast

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.tools import spread_benchmark_handlers, spread_handlers, spread_survival_handlers
from vgc_mcp_core.tools.response_contract import CalcResult
from vgc_mcp_core.tools.spread_common import META_SYNERGIES as META_SYNERGIES


def _calc(result: dict[str, Any]) -> CalcResult:
    """FastMCP validates the dict against CalcResult (publishing an outputSchema);
    returning the dict itself keeps direct `.fn` callers working."""
    return cast(CalcResult, result)


def register_spread_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register EV spread optimization tools with the MCP server."""

    @mcp.tool(
        title="Check Spread Efficiency",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_spread_efficiency(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        nature: Annotated[str, Field(description="Pokemon's nature (e.g. 'timid', 'adamant')", min_length=1)],
        hp_evs: Annotated[int, Field(ge=0, le=252, description="HP EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        atk_evs: Annotated[int, Field(ge=0, le=252, description="Attack EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        def_evs: Annotated[int, Field(ge=0, le=252, description="Defense EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spa_evs: Annotated[int, Field(ge=0, le=252, description="Special Attack EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Special Defense EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spe_evs: Annotated[int, Field(ge=0, le=252, description="Speed EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spread: Annotated[Optional[str], Field(description="Whole allocation as an 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions); overrides the per-stat values")] = None,
    ) -> dict:
        """Check an EV spread for efficiency (wasted EVs, optimal distribution).

        Returns issues (over-cap totals, non-multiple-of-4 waste), suggestions,
        final stats, and a Showdown paste for the analyzed spread. In a
        Champions (Reg MA) session the inputs are validated on the Stat Point
        grain (0-32 per stat, 66 total) instead of 508/4.
        """
        return await spread_handlers.check_spread_efficiency(
            pokeapi,
            pokemon_name=pokemon_name,
            nature=nature,
            hp_evs=hp_evs,
            atk_evs=atk_evs,
            def_evs=def_evs,
            spa_evs=spa_evs,
            spd_evs=spd_evs,
            spe_evs=spe_evs,
            spread=spread,
        )

    @mcp.tool(
        title="Suggest Nature Optimization",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_nature_optimization(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        current_nature: Annotated[str, Field(description="Current nature (e.g. 'serious', 'timid')", min_length=1)],
        hp_evs: Annotated[int, Field(ge=0, le=252, description="Current HP EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        atk_evs: Annotated[int, Field(ge=0, le=252, description="Current Attack EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        def_evs: Annotated[int, Field(ge=0, le=252, description="Current Defense EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spa_evs: Annotated[int, Field(ge=0, le=252, description="Current Special Attack EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spd_evs: Annotated[int, Field(ge=0, le=252, description="Current Special Defense EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        spe_evs: Annotated[int, Field(ge=0, le=252, description="Current Speed EVs (0-252); Stat Points 0-32 in Champions sessions")] = 0,
        moves: Annotated[Optional[list[str]], Field(description="Optional list of moves used to determine physical/special preference")] = None,
        spread: Annotated[Optional[str], Field(description="Whole allocation as an 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions); overrides the per-stat values")] = None,
    ) -> dict:
        """Suggest a nature change that achieves the same stats with fewer EVs.

        Like Showdown's "Use a different nature to save X EVs" feature. Returns
        current vs optimized spreads (with Showdown pastes) and the EV savings.
        In a Champions (Reg MA) session the search runs on the Stat Point grain.
        """
        return await spread_handlers.suggest_nature_optimization(
            pokeapi,
            pokemon_name=pokemon_name,
            current_nature=current_nature,
            hp_evs=hp_evs,
            atk_evs=atk_evs,
            def_evs=def_evs,
            spa_evs=spa_evs,
            spd_evs=spd_evs,
            spe_evs=spe_evs,
            moves=moves,
            spread=spread,
        )

    @mcp.tool(
        title="Optimize Bulk EVs",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def optimize_bulk(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        nature: Annotated[str, Field(description="Pokemon's nature", min_length=1)],
        total_bulk_evs: Annotated[int, Field(ge=0, description="Total EVs to allocate to bulk; in Champions sessions the default (252) maps to the full 66 Stat Point budget")] = 252,
        defense_bias: Annotated[float, Field(description="0.5 = balanced, 1.0 = physical, 0.0 = special")] = 0.5,
        item: Annotated[Optional[str], Field(description="Held item for HP number optimization (e.g. 'leftovers', 'life-orb')")] = None,
        include_analysis: Annotated[bool, Field(description="Also return final stats, weighted bulk scores, efficiency vs all-HP / all-Def investment and an explanation")] = False,
    ) -> dict:
        """Optimize HP/Def/SpD EVs for maximum effective bulk.

        Searches distributions to maximize HP*Def / HP*SpD weighted by
        defense_bias and returns the optimal spread with a Showdown paste.
        Set include_analysis for the diminishing-returns breakdown.
        """
        return await spread_handlers.optimize_bulk(
            pokeapi,
            pokemon_name=pokemon_name,
            nature=nature,
            total_bulk_evs=total_bulk_evs,
            defense_bias=defense_bias,
            item=item,
            include_analysis=include_analysis,
        )

    @mcp.tool(
        title="Suggest EV Spread",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_spread(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        role: Annotated[str, Field(description="'offensive' (max offensive stat + speed), 'bulky' (HP + defenses), 'bulky_offense' (some bulk + offense), or 'support' (bulk focused)")] = "offensive",
        speed_target: Annotated[Optional[int], Field(description="Optional specific final Speed stat to hit (offensive role only)")] = None,
        item: Annotated[Optional[str], Field(description="Held item for HP number optimization (e.g. 'leftovers', 'life-orb')")] = None,
    ) -> dict:
        """Suggest an EV spread based on role, with a Showdown paste.

        Offensive role uses intelligent nature auto-selection. In a Champions
        (Reg MA) session the suggestion is returned on the Stat Point scale
        (0-32 per stat, 66 total) as an 'SPs:' paste.
        """
        return await spread_handlers.suggest_spread(
            pokeapi,
            pokemon_name=pokemon_name,
            role=role,
            speed_target=speed_target,
            item=item,
        )

    @mcp.tool(
        title="Analyze Bulk Diminishing Returns",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def analyze_bulk_diminishing_returns(
        pokemon_name: Annotated[str, Field(description="Pokemon name", min_length=1)],
        nature: Annotated[str, Field(description="Pokemon's nature", min_length=1)]
    ) -> dict:
        """Analyze diminishing returns for HP, Def, and SpD investment.

        Shows how the value of each additional EV decreases as you invest more
        in a stat, with marginal-gain data at each threshold and recommendations
        for optimal breakpoints.
        """
        return await spread_handlers.analyze_bulk_diminishing_returns(
            pokeapi,
            pokemon_name=pokemon_name,
            nature=nature,
        )

    @mcp.tool(
        title="Design Spread With Benchmarks",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def design_spread_with_benchmarks(
        pokemon_name: Annotated[str, Field(description="Your Pokemon", min_length=1)],
        nature: Annotated[Optional[str], Field(description="Your Pokemon's nature (optional - auto-selects the optimal nature if not provided)")] = None,
        outspeed_pokemon: Annotated[Optional[str], Field(description="Pokemon to outspeed")] = None,
        outspeed_pokemon_nature: Annotated[str, Field(description="Speed target's nature")] = "jolly",
        outspeed_pokemon_evs: Annotated[int, Field(ge=0, le=252, description="Target Speed EVs in mainline; native SP (0-32) in Champions. Legacy EV values above 32 are converted to SP.")] = 252,
        outspeed_at_speed_stage: Annotated[int, Field(ge=-6, le=6, description="Target's speed stage (-1 = after Icy Wind, -2 = after 2x Icy Wind, etc.)")] = 0,
        outspeed_target_has_booster: Annotated[bool, Field(description="True if the target has a Protosynthesis/Quark Drive speed boost active (1.5x)")] = False,
        outspeed_target_has_tailwind: Annotated[bool, Field(description="True if the target has Tailwind active (2x speed)")] = False,
        my_pokemon_has_booster: Annotated[bool, Field(description="True if YOUR Pokemon has a Protosynthesis/Quark Drive speed boost (1.5x)")] = False,
        my_pokemon_has_tailwind: Annotated[bool, Field(description="True if YOUR Pokemon has Tailwind active (2x speed)")] = False,
        survive_pokemon: Annotated[Optional[str], Field(description="Attacker to survive")] = None,
        survive_move: Annotated[Optional[str], Field(description="Move to survive")] = None,
        survive_pokemon_nature: Annotated[str, Field(description="Attacker's nature")] = "adamant",
        survive_pokemon_evs: Annotated[Union[Annotated[int, Field(ge=0, le=252)], str], Field(description="Attacker's offensive EVs (0-252), or its full 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions) whose Atk/SpA is used")] = 252,
        survive_pokemon_ability: Annotated[Optional[str], Field(description="Attacker's ability if relevant")] = None,
        survive_pokemon_item: Annotated[Optional[str], Field(description="Attacker's item (e.g. 'choice-band')")] = None,
        survive_pokemon_tera_type: Annotated[Optional[str], Field(description="Attacker's Tera type if Terastallized - ASK THE USER FIRST!")] = None,
        defender_tera_type: Annotated[Optional[str], Field(description="Your Pokemon's Tera type if Terastallizing - ASK THE USER FIRST!")] = None,
        prioritize: Annotated[str, Field(description="'bulk' (max bulk after speed) or 'offense' (specified offensive EVs)")] = "bulk",
        offensive_evs: Annotated[int, Field(ge=0, le=252, description="Attack/SpA EVs when prioritize='offense'")] = 0,
        item: Annotated[Optional[str], Field(description="Your Pokemon's held item")] = None,
        ability: Annotated[Optional[str], Field(description="Your Pokemon's ability")] = None,
    ) -> CalcResult:
        """Spread that outspeeds a target and survives ONE attack (or maxes offense).

        Use for "Entei that survives Surging Strikes and outspeeds Chien-Pao" or
        "max Attack Entei that outspeeds Chien-Pao after Icy Wind". Two
        different attacks: optimize_dual_survival_spread. Returns the spread,
        final stats, the survival calc and a Showdown paste.

        Ask first whether either side Terastallizes (and to what); Tera changes
        STAB and defensive typing, so do not assume none.
        """
        return _calc(await spread_benchmark_handlers.design_spread_with_benchmarks(
            pokeapi,
            smogon,
            pokemon_name=pokemon_name,
            nature=nature,
            outspeed_pokemon=outspeed_pokemon,
            outspeed_pokemon_nature=outspeed_pokemon_nature,
            outspeed_pokemon_evs=outspeed_pokemon_evs,
            outspeed_at_speed_stage=outspeed_at_speed_stage,
            outspeed_target_has_booster=outspeed_target_has_booster,
            outspeed_target_has_tailwind=outspeed_target_has_tailwind,
            my_pokemon_has_booster=my_pokemon_has_booster,
            my_pokemon_has_tailwind=my_pokemon_has_tailwind,
            survive_pokemon=survive_pokemon,
            survive_move=survive_move,
            survive_pokemon_nature=survive_pokemon_nature,
            survive_pokemon_evs=survive_pokemon_evs,
            survive_pokemon_ability=survive_pokemon_ability,
            survive_pokemon_item=survive_pokemon_item,
            survive_pokemon_tera_type=survive_pokemon_tera_type,
            defender_tera_type=defender_tera_type,
            prioritize=prioritize,
            offensive_evs=offensive_evs,
            item=item,
            ability=ability,
        ))

    @mcp.tool(
        title="Optimize Dual Survival Spread",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def optimize_dual_survival_spread(
        pokemon_name: Annotated[str, Field(description="Your Pokemon (e.g. 'ogerpon-wellspring')", min_length=1)],
        survive_hit1_attacker: Annotated[str, Field(description="First attacker to survive (e.g. 'urshifu') - MUST be different from hit2", min_length=1)],
        survive_hit1_move: Annotated[str, Field(description="First move to survive (e.g. 'wicked-blow')", min_length=1)],
        survive_hit2_attacker: Annotated[str, Field(description="Second attacker to survive (e.g. 'landorus-incarnate') - MUST be different from hit1", min_length=1)],
        survive_hit2_move: Annotated[str, Field(description="Second move to survive (e.g. 'sludge-bomb')", min_length=1)],
        nature: Annotated[Optional[str], Field(description="Your Pokemon's nature (optional - auto-selects the best nature if not provided)")] = None,
        outspeed_pokemon: Annotated[Optional[str], Field(description="Pokemon to outspeed (optional)")] = None,
        outspeed_pokemon_nature: Annotated[str, Field(description="Speed target's nature")] = "timid",
        outspeed_pokemon_evs: Annotated[int, Field(ge=0, le=252, description="Target Speed EVs in mainline; native SP (0-32) in Champions. Legacy EV values above 32 are converted to SP.")] = 252,
        outspeed_at_speed_stage: Annotated[int, Field(ge=-6, le=6, description="Target's speed stage (-1 = after Icy Wind, -2 = after 2x Icy Wind)")] = 0,
        outspeed_target_has_booster: Annotated[bool, Field(description="True if the target has a Protosynthesis/Quark Drive speed boost (1.5x)")] = False,
        outspeed_target_has_tailwind: Annotated[bool, Field(description="True if the target has Tailwind active (2x speed)")] = False,
        my_pokemon_has_booster: Annotated[bool, Field(description="True if YOUR Pokemon has a Protosynthesis/Quark Drive speed boost (1.5x)")] = False,
        my_pokemon_has_tailwind: Annotated[bool, Field(description="True if YOUR Pokemon has Tailwind active (2x speed)")] = False,
        speed_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Override Speed EVs directly instead of calculating from the outspeed target")] = None,
        survive_hit1_nature: Annotated[Optional[str], Field(description="First attacker's nature (auto-fetched from Smogon if not specified)")] = None,
        survive_hit1_evs: Annotated[Optional[Union[Annotated[int, Field(ge=0, le=252)], str]], Field(description="First attacker's offensive EVs (auto-fetched if not specified), or its full 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions) whose Atk/SpA is used")] = None,
        survive_hit1_item: Annotated[Optional[str], Field(description="First attacker's item")] = None,
        survive_hit1_ability: Annotated[Optional[str], Field(description="First attacker's ability")] = None,
        survive_hit1_tera_type: Annotated[Optional[str], Field(description="First attacker's Tera type if Terastallized")] = None,
        survive_hit2_nature: Annotated[Optional[str], Field(description="Second attacker's nature (auto-fetched from Smogon if not specified)")] = None,
        survive_hit2_evs: Annotated[Optional[Union[Annotated[int, Field(ge=0, le=252)], str]], Field(description="Second attacker's offensive EVs (auto-fetched if not specified), or its full 'HP/Atk/Def/SpA/SpD/Spe' slash string (e.g. '4/0/0/252/0/252'; Stat Points in Champions) whose Atk/SpA is used")] = None,
        survive_hit2_item: Annotated[Optional[str], Field(description="Second attacker's item")] = None,
        survive_hit2_ability: Annotated[Optional[str], Field(description="Second attacker's ability")] = None,
        survive_hit2_tera_type: Annotated[Optional[str], Field(description="Second attacker's Tera type if Terastallized")] = None,
        defender_tera_type: Annotated[Optional[str], Field(description="Your Pokemon's Tera type if Terastallizing")] = None,
        target_survival: Annotated[float, Field(ge=0, le=100, description="Minimum survival % to consider 'surviving' (93.75 = 15/16 rolls)")] = 100.0,
        item: Annotated[Optional[str], Field(description="Your Pokemon's held item")] = None,
        ability: Annotated[Optional[str], Field(description="Your Pokemon's ability")] = None,
    ) -> CalcResult:
        """Cheapest spread that survives TWO different attackers and hits a speed target.

        Use only for two different attacks ("survive Wicked Blow AND Sludge
        Bomb"). One attack: design_spread_with_benchmarks. Three or more:
        optimize_multi_survival_spread. Speed is set first, then HP/Def/SpD;
        with no nature given it picks the one that leaves the most spare
        investment. Returns the spread, a per-attack survival breakdown and a
        Showdown paste, or "IMPOSSIBLE".
        """
        return _calc(await spread_survival_handlers.optimize_dual_survival_spread(
            pokeapi,
            smogon,
            pokemon_name=pokemon_name,
            survive_hit1_attacker=survive_hit1_attacker,
            survive_hit1_move=survive_hit1_move,
            survive_hit2_attacker=survive_hit2_attacker,
            survive_hit2_move=survive_hit2_move,
            nature=nature,
            outspeed_pokemon=outspeed_pokemon,
            outspeed_pokemon_nature=outspeed_pokemon_nature,
            outspeed_pokemon_evs=outspeed_pokemon_evs,
            outspeed_at_speed_stage=outspeed_at_speed_stage,
            outspeed_target_has_booster=outspeed_target_has_booster,
            outspeed_target_has_tailwind=outspeed_target_has_tailwind,
            my_pokemon_has_booster=my_pokemon_has_booster,
            my_pokemon_has_tailwind=my_pokemon_has_tailwind,
            speed_evs=speed_evs,
            survive_hit1_nature=survive_hit1_nature,
            survive_hit1_evs=survive_hit1_evs,
            survive_hit1_item=survive_hit1_item,
            survive_hit1_ability=survive_hit1_ability,
            survive_hit1_tera_type=survive_hit1_tera_type,
            survive_hit2_nature=survive_hit2_nature,
            survive_hit2_evs=survive_hit2_evs,
            survive_hit2_item=survive_hit2_item,
            survive_hit2_ability=survive_hit2_ability,
            survive_hit2_tera_type=survive_hit2_tera_type,
            defender_tera_type=defender_tera_type,
            target_survival=target_survival,
            item=item,
            ability=ability,
        ))

    @mcp.tool(
        title="Optimize Multi-Threat Survival Spread",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def optimize_multi_survival_spread(
        pokemon_name: Annotated[str, Field(description="Your Pokemon (e.g. 'ogerpon-hearthflame')", min_length=1)],
        threats: Annotated[list[dict], Field(description="List of 3-6 threat dicts, each with required 'attacker' and 'move' plus optional 'nature', 'evs' (offensive EVs, or a full 'HP/Atk/Def/SpA/SpD/Spe' slash string, e.g. '4/252/0/0/0/252', SP-scale in Champions), 'item', 'ability' (auto-fetched from Smogon if omitted) and 'tera_type' (None = no Tera)")],
        nature: Annotated[Optional[str], Field(description="Your Pokemon's nature (auto-selected if None)")] = None,
        outspeed_pokemon: Annotated[Optional[str], Field(description="Pokemon to outspeed (optional)")] = None,
        outspeed_pokemon_nature: Annotated[str, Field(description="Speed target's nature")] = "timid",
        outspeed_pokemon_evs: Annotated[int, Field(ge=0, le=252, description="Target Speed EVs in mainline; native SP (0-32) in Champions. Legacy EV values above 32 are converted to SP.")] = 252,
        outspeed_at_speed_stage: Annotated[int, Field(ge=-6, le=6, description="Target's speed stage (e.g. -1 after Icy Wind)")] = 0,
        outspeed_target_has_booster: Annotated[bool, Field(description="True if the target has Protosynthesis/Quark Drive active (1.5x speed)")] = False,
        outspeed_target_has_tailwind: Annotated[bool, Field(description="True if the target has Tailwind (2x speed)")] = False,
        my_pokemon_has_booster: Annotated[bool, Field(description="True if YOUR Pokemon has Protosynthesis/Quark Drive active (1.5x speed)")] = False,
        my_pokemon_has_tailwind: Annotated[bool, Field(description="True if YOUR Pokemon has Tailwind (2x speed)")] = False,
        speed_evs: Annotated[Optional[int], Field(ge=0, le=252, description="Override Speed EVs directly")] = None,
        defender_tera_type: Annotated[Optional[str], Field(description="Your Tera type if Terastallizing")] = None,
        target_survival: Annotated[float, Field(ge=0, le=100, description="Minimum survival % (default 93.75 = 15/16 rolls)")] = 93.75,
        item: Annotated[Optional[str], Field(description="Your Pokemon's held item")] = None,
        ability: Annotated[Optional[str], Field(description="Your Pokemon's ability")] = None,
    ) -> CalcResult:
        """Cheapest spread that survives 3-6 different attacks and hits a speed target.

        Use for "survive Urshifu, Flutter Mane AND Chi-Yu". Two attacks:
        optimize_dual_survival_spread (faster). Returns the spread, per-threat
        survival and a Showdown paste; when impossible, the best partial
        solution plus a Tera suggestion. Takes 5-30 seconds.
        """
        return _calc(await spread_survival_handlers.optimize_multi_survival_spread(
            pokeapi,
            smogon,
            pokemon_name=pokemon_name,
            threats=threats,
            nature=nature,
            outspeed_pokemon=outspeed_pokemon,
            outspeed_pokemon_nature=outspeed_pokemon_nature,
            outspeed_pokemon_evs=outspeed_pokemon_evs,
            outspeed_at_speed_stage=outspeed_at_speed_stage,
            outspeed_target_has_booster=outspeed_target_has_booster,
            outspeed_target_has_tailwind=outspeed_target_has_tailwind,
            my_pokemon_has_booster=my_pokemon_has_booster,
            my_pokemon_has_tailwind=my_pokemon_has_tailwind,
            speed_evs=speed_evs,
            defender_tera_type=defender_tera_type,
            target_survival=target_survival,
            item=item,
            ability=ability,
        ))

    @mcp.tool(
        title="Analyze HP Number",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def analyze_hp_number(
        pokemon_name: Annotated[str, Field(description="Pokemon name (e.g. 'incineroar')", min_length=1)],
        item: Annotated[str, Field(description="Held item (e.g. 'leftovers', 'life-orb', 'sitrus-berry')", min_length=1)],
        current_hp_evs: Annotated[int, Field(ge=0, le=252, description="Current HP EVs (0-252) to compare against")] = 0,
    ) -> dict:
        """Analyze HP EV options for optimal item-based recovery or recoil.

        Shows which HP EV values produce the best HP numbers for a given item:
        Leftovers/Black Sludge and Grassy Terrain want HP divisible by 16
        (maximizes 1/16 recovery), Life Orb wants HP = 10n-1 (minimizes 1/10
        recoil), Sitrus Berry wants HP divisible by 4 (maximizes 25% heal).
        Returns optimal HP EV options and a recommendation.
        """
        return await spread_handlers.analyze_hp_number(
            pokeapi,
            pokemon_name=pokemon_name,
            item=item,
            current_hp_evs=current_hp_evs,
        )
