"""MCP-UI resource registration for VGC Team Builder.

This module registers UI resources that can be returned from tools
to render interactive components in compatible MCP clients.
"""

from typing import Any
from mcp.server.fastmcp import FastMCP

try:
    from mcp_ui_server import create_ui_resource
    MCP_UI_AVAILABLE = True
except ImportError:
    MCP_UI_AVAILABLE = False

    def create_ui_resource(config: dict) -> dict:
        """Fallback when mcp-ui-server is not installed."""
        return config

from .components import (
    create_damage_calc_ui,
    create_team_roster_ui,
    create_speed_tier_ui,
    create_coverage_ui,
    create_matchup_summary_ui,
    create_threat_analysis_ui,
    create_usage_stats_ui,
    create_speed_outspeed_ui,
    create_stats_card_ui,
    create_threat_matrix_ui,
    create_turn_order_ui,
    create_bring_selector_ui,
    create_ability_synergy_ui,
    create_team_report_ui,
    create_summary_table_ui,
    create_speed_outspeed_graph_ui,
    create_multi_hit_survival_ui,
)


def register_ui_resources(mcp: FastMCP) -> None:
    """Register UI resource handlers with the MCP server.

    This sets up resource URIs that tools can reference to
    render interactive UI components.

    Args:
        mcp: The FastMCP server instance
    """
    if not MCP_UI_AVAILABLE:
        return

    # Note: FastMCP resources are registered via decorators or direct calls.
    # The actual UI content is generated dynamically by tools and returned
    # with metadata pointing to these resource patterns.
    pass


def create_damage_calc_resource(
    attacker: str,
    defender: str,
    move: str,
    damage_min: float,
    damage_max: float,
    ko_chance: str,
    type_effectiveness: float = 1.0,
    attacker_item: str | None = None,
    defender_item: str | None = None,
    move_type: str | None = None,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Create a damage calculator UI resource.

    Returns a dict with the UI resource that can be included in tool results.
    Compatible clients will render this as an interactive damage display.
    """
    html = create_damage_calc_ui(
        attacker=attacker,
        defender=defender,
        move=move,
        damage_min=damage_min,
        damage_max=damage_max,
        ko_chance=ko_chance,
        type_effectiveness=type_effectiveness,
        attacker_item=attacker_item,
        defender_item=defender_item,
        move_type=move_type,
        notes=notes,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/damage-calc/{attacker.lower()}-vs-{defender.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_interactive_damage_calc_resource(
    attacker: str,
    defender: str,
    move: str,
    damage_min: float,
    damage_max: float,
    ko_chance: str,
    type_effectiveness: float = 1.0,
    attacker_item: str | None = None,
    defender_item: str | None = None,
    move_type: str | None = None,
    notes: list[str] | None = None,
    attacker_evs: dict[str, int] | None = None,
    defender_evs: dict[str, int] | None = None,
    attacker_nature: str = "Serious",
    defender_nature: str = "Serious",
    attacker_base_stats: dict[str, int] | None = None,
    defender_base_stats: dict[str, int] | None = None,
    move_category: str = "special",
    move_power: int = 0,
) -> dict[str, Any]:
    """Create an interactive damage calculator UI resource.

    Returns a dict with the UI resource that includes editable EV spreads
    and dynamically recalculates damage when users adjust values.
    """
    html = create_damage_calc_ui(
        attacker=attacker,
        defender=defender,
        move=move,
        damage_min=damage_min,
        damage_max=damage_max,
        ko_chance=ko_chance,
        type_effectiveness=type_effectiveness,
        attacker_item=attacker_item,
        defender_item=defender_item,
        move_type=move_type,
        notes=notes,
        interactive=True,
        attacker_evs=attacker_evs,
        defender_evs=defender_evs,
        attacker_nature=attacker_nature,
        defender_nature=defender_nature,
        attacker_base_stats=attacker_base_stats,
        defender_base_stats=defender_base_stats,
        move_category=move_category,
        move_power=move_power,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/damage-calc-interactive/{attacker.lower()}-vs-{defender.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_team_roster_resource(
    team: list[dict[str, Any]],
    team_name: str | None = None,
) -> dict[str, Any]:
    """Create a team roster UI resource.

    Returns a dict with the UI resource showing the current team.
    """
    html = create_team_roster_ui(team=team, team_name=team_name)

    return create_ui_resource({
        "uri": "ui://vgc/team/roster",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_speed_tier_resource(
    pokemon_name: str,
    pokemon_speed: int,
    speed_tiers: list[dict[str, Any]],
    modifiers: dict[str, bool] | None = None,
) -> dict[str, Any]:
    """Create a speed tier analyzer UI resource.

    Returns a dict with the UI resource showing speed tier comparisons.
    """
    html = create_speed_tier_ui(
        pokemon_name=pokemon_name,
        pokemon_speed=pokemon_speed,
        speed_tiers=speed_tiers,
        modifiers=modifiers,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/speed/tiers/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_coverage_resource(
    pokemon_name: str,
    moves: list[dict[str, Any]],
    coverage: dict[str, float],
) -> dict[str, Any]:
    """Create a type coverage analyzer UI resource.

    Returns a dict with the UI resource showing type coverage grid.
    """
    html = create_coverage_ui(
        pokemon_name=pokemon_name,
        moves=moves,
        coverage=coverage,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/coverage/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_matchup_summary_resource(
    pokemon_name: str,
    matchups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a matchup summary UI resource.

    Returns a dict with the UI resource showing matchup analysis.
    """
    html = create_matchup_summary_ui(
        pokemon_name=pokemon_name,
        matchups=matchups,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/matchups/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_threat_analysis_resource(
    threat_name: str,
    threat_speed: int,
    ohko_by: list[str],
    twohko_by: list[str],
    checks: list[str],
    counters: list[str],
    threatened: list[str],
    survives: list[str],
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Create a threat analysis UI resource.

    Returns a dict with the UI resource showing threat matchup analysis.
    """
    html = create_threat_analysis_ui(
        threat_name=threat_name,
        threat_speed=threat_speed,
        ohko_by=ohko_by,
        twohko_by=twohko_by,
        checks=checks,
        counters=counters,
        threatened=threatened,
        survives=survives,
        notes=notes,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/threat/{threat_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_usage_stats_resource(
    pokemon_name: str,
    usage_percent: float,
    items: list[dict[str, Any]],
    abilities: list[dict[str, Any]],
    moves: list[dict[str, Any]],
    spreads: list[dict[str, Any]],
    tera_types: list[dict[str, Any]] | None = None,
    teammates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a usage statistics UI resource.

    Returns a dict with the UI resource showing competitive usage data.
    """
    html = create_usage_stats_ui(
        pokemon_name=pokemon_name,
        usage_percent=usage_percent,
        items=items,
        abilities=abilities,
        moves=moves,
        spreads=spreads,
        tera_types=tera_types,
        teammates=teammates,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/usage/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_speed_outspeed_resource(
    pokemon_name: str,
    base_speed: int,
    current_speed: int,
    nature: str,
    speed_evs: int,
    speed_distribution: list[dict[str, Any]],
    outspeed_percentage: float,
    mode: str = "meta",
    target_pokemon: str | None = None,
    format_info: dict[str, Any] | None = None,
    pokemon_base_speeds: dict[str, int] | None = None,
) -> dict[str, Any]:
    """Create a speed outspeed percentage UI resource.

    Returns a dict with the UI resource showing what % of the meta
    (or a specific target) your Pokemon outspeeds, with an interactive
    slider to adjust Speed EVs.

    Args:
        pokemon_name: Your Pokemon's name
        base_speed: Base speed stat
        current_speed: Current calculated speed stat
        nature: Current nature
        speed_evs: Current Speed EVs
        speed_distribution: Pre-computed distribution from build_speed_distribution_data()
        outspeed_percentage: Initial outspeed percentage
        mode: "meta" for meta-wide, "single" for single target
        target_pokemon: Target Pokemon name (for single mode)
        format_info: Format metadata (name, month)
        pokemon_base_speeds: Dict mapping Pokemon names to their base speed stats
    """
    html = create_speed_outspeed_ui(
        pokemon_name=pokemon_name,
        base_speed=base_speed,
        current_speed=current_speed,
        nature=nature,
        speed_evs=speed_evs,
        speed_distribution=speed_distribution,
        outspeed_percentage=outspeed_percentage,
        mode=mode,
        target_pokemon=target_pokemon,
        format_info=format_info,
        pokemon_base_speeds=pokemon_base_speeds,
    )

    uri_suffix = f"{pokemon_name.lower()}"
    if mode == "single" and target_pokemon:
        uri_suffix = f"{pokemon_name.lower()}-vs-{target_pokemon.lower()}"

    return create_ui_resource({
        "uri": f"ui://vgc/speed/outspeed/{uri_suffix}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_stats_card_resource(
    pokemon_name: str,
    base_stats: dict[str, int],
    evs: dict[str, int] | None = None,
    ivs: dict[str, int] | None = None,
    nature: str = "Serious",
    level: int = 50,
    types: list[str] | None = None,
    ability: str | None = None,
    item: str | None = None,
) -> dict[str, Any]:
    """Create a stats card UI resource.

    Returns a dict with the UI resource showing Pokemon stats with bars.

    Args:
        pokemon_name: Pokemon name
        base_stats: Base stats dict {hp, atk, def, spa, spd, spe}
        evs: EV spread (optional)
        ivs: IV spread (optional)
        nature: Nature name
        level: Pokemon level (default 50 for VGC)
        types: Pokemon types
        ability: Pokemon ability
        item: Held item
    """
    html = create_stats_card_ui(
        pokemon_name=pokemon_name,
        base_stats=base_stats,
        evs=evs,
        ivs=ivs,
        nature=nature,
        level=level,
        types=types,
        ability=ability,
        item=item,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/stats/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_threat_matrix_resource(
    pokemon_name: str,
    pokemon_speed: int,
    threats: list[dict[str, Any]],
    pokemon_sprite: str | None = None,
) -> dict[str, Any]:
    """Create a threat matchup matrix UI resource.

    Returns a dict with the UI resource showing damage matchups vs threats.

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat
        threats: List of threat dicts with damage data
        pokemon_sprite: Optional sprite URL
    """
    html = create_threat_matrix_ui(
        pokemon_name=pokemon_name,
        pokemon_speed=pokemon_speed,
        threats=threats,
        pokemon_sprite=pokemon_sprite,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/threat-matrix/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_turn_order_resource(
    pokemon_list: list[dict[str, Any]],
    trick_room: bool = False,
    tailwind_pokemon: list[str] | None = None,
    paralysis_pokemon: list[str] | None = None,
) -> dict[str, Any]:
    """Create a turn order timeline UI resource.

    Returns a dict with the UI resource showing turn order with priority.

    Args:
        pokemon_list: List of Pokemon dicts {name, speed, priority, move, team}
        trick_room: Whether Trick Room is active
        tailwind_pokemon: List of Pokemon names benefiting from Tailwind
        paralysis_pokemon: List of Pokemon names affected by paralysis
    """
    html = create_turn_order_ui(
        pokemon_list=pokemon_list,
        trick_room=trick_room,
        tailwind_pokemon=tailwind_pokemon,
        paralysis_pokemon=paralysis_pokemon,
    )

    return create_ui_resource({
        "uri": "ui://vgc/turn-order",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_bring_selector_resource(
    your_team: list[dict[str, Any]],
    opponent_team: list[dict[str, Any]],
    recommendations: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a bring/leave selector UI resource.

    Returns a dict with the UI resource for team preview selection.

    Args:
        your_team: List of your team Pokemon dicts {name, types, item, ability}
        opponent_team: List of opponent Pokemon dicts
        recommendations: AI recommendations {bring: [], leave: [], reasoning}
    """
    html = create_bring_selector_ui(
        your_team=your_team,
        opponent_team=opponent_team,
        recommendations=recommendations,
    )

    return create_ui_resource({
        "uri": "ui://vgc/bring-selector",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_ability_synergy_resource(
    team: list[dict[str, Any]],
    synergies: dict[str, Any],
) -> dict[str, Any]:
    """Create an ability synergy network UI resource.

    Returns a dict with the UI resource showing ability interactions.

    Args:
        team: List of team Pokemon dicts {name, ability, types}
        synergies: Synergy data dict with weather, terrain, intimidate, combos, conflicts
    """
    html = create_ability_synergy_ui(
        team=team,
        synergies=synergies,
    )

    return create_ui_resource({
        "uri": "ui://vgc/ability-synergy",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_team_report_resource(
    team_name: str,
    grade: str,
    tournament_ready: bool,
    strengths: list[str],
    weaknesses: list[str],
    suggestions: list[dict[str, Any]],
    legality_issues: list[dict[str, Any]],
    type_coverage: dict[str, Any],
    speed_control: dict[str, Any],
    team: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a team report card UI resource.

    Returns a dict with the UI resource showing comprehensive team analysis.

    Args:
        team_name: Team name or identifier
        grade: Letter grade (A+, A, B+, B, etc.)
        tournament_ready: Whether team is legal for tournament
        strengths: List of strength descriptions
        weaknesses: List of weakness descriptions
        suggestions: List of suggestion dicts {action, reason, priority}
        legality_issues: List of issue dicts {issue, severity, fix}
        type_coverage: Dict with super_effective, weak_to, resists
        speed_control: Dict with has_trick_room, has_tailwind, fastest, slowest
        team: List of team Pokemon for display
    """
    html = create_team_report_ui(
        team_name=team_name,
        grade=grade,
        tournament_ready=tournament_ready,
        strengths=strengths,
        weaknesses=weaknesses,
        suggestions=suggestions,
        legality_issues=legality_issues,
        type_coverage=type_coverage,
        speed_control=speed_control,
        team=team,
    )

    return create_ui_resource({
        "uri": "ui://vgc/team-report",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def add_ui_metadata(
    result: dict[str, Any],
    ui_resource: dict[str, Any],
) -> dict[str, Any]:
    """Add UI metadata to a tool result for compatible clients.

    This adds the _meta field that MCP-UI clients look for to
    render interactive components.

    Args:
        result: The existing tool result dict
        ui_resource: The UI resource created by create_*_resource functions

    Returns:
        The result dict with _meta UI information added
    """
    if not MCP_UI_AVAILABLE:
        return result

    result["_meta"] = {
        "ui/resourceUri": ui_resource.get("uri", ""),
        "ui/resource": ui_resource,
    }
    return result


def create_summary_table_resource(
    title: str,
    rows: list[dict[str, str]],
    highlight_rows: list[str] | None = None,
    analysis: str | None = None,
) -> dict[str, Any]:
    """Create a summary table UI resource.

    Args:
        title: Table title (e.g., "Damage Calculation")
        rows: List of dicts with 'metric' and 'value' keys
        highlight_rows: List of metric names to highlight
        analysis: Optional prose summary to show above table

    Returns:
        UI resource dict
    """
    html = create_summary_table_ui(
        title=title,
        rows=rows,
        highlight_rows=highlight_rows,
        analysis=analysis,
    )

    # Create URI-safe title
    uri_title = title.lower().replace(" ", "-").replace("/", "-")

    return create_ui_resource({
        "uri": f"ui://vgc/summary-table/{uri_title}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_speed_outspeed_graph_resource(
    pokemon_name: str,
    pokemon_speed: int,
    target_pokemon: str,
    target_spreads: list[dict[str, Any]],
    outspeed_percent: float,
) -> dict[str, Any]:
    """Create a speed outspeed graph UI resource.

    Shows what percentage of a target Pokemon's common spreads you outspeed.

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat
        target_pokemon: The target Pokemon to compare against
        target_spreads: List of dicts with 'speed' and 'usage' (percentage) keys
        outspeed_percent: Percentage of spreads outsped (0-100)

    Returns:
        UI resource dict
    """
    html = create_speed_outspeed_graph_ui(
        pokemon_name=pokemon_name,
        pokemon_speed=pokemon_speed,
        target_pokemon=target_pokemon,
        target_spreads=target_spreads,
        outspeed_percent=outspeed_percent,
    )

    # Create URI-safe names
    uri_pokemon = pokemon_name.lower().replace(" ", "-")
    uri_target = target_pokemon.lower().replace(" ", "-")

    return create_ui_resource({
        "uri": f"ui://vgc/speed-outspeed/{uri_pokemon}-vs-{uri_target}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_multi_hit_survival_resource(
    defender_name: str,
    attacker_name: str,
    move_name: str,
    num_hits: int,
    per_hit_min: float,
    per_hit_max: float,
    total_min: float,
    total_max: float,
    hp_remaining_min: float,
    hp_remaining_max: float,
    survival_chance: float,
    survives: bool,
) -> dict[str, Any]:
    """Create a multi-hit survival visualization UI resource.

    Args:
        defender_name: Defending Pokemon
        attacker_name: Attacking Pokemon
        move_name: Move name
        num_hits: Number of hits
        per_hit_min: Min damage per hit (%)
        per_hit_max: Max damage per hit (%)
        total_min: Total min damage (%)
        total_max: Total max damage (%)
        hp_remaining_min: Min HP remaining (%)
        hp_remaining_max: Max HP remaining (%)
        survival_chance: Chance to survive (0-100)
        survives: Whether guaranteed to survive

    Returns:
        UI resource dict
    """
    html = create_multi_hit_survival_ui(
        defender_name=defender_name,
        attacker_name=attacker_name,
        move_name=move_name,
        num_hits=num_hits,
        per_hit_min=per_hit_min,
        per_hit_max=per_hit_max,
        total_min=total_min,
        total_max=total_max,
        hp_remaining_min=hp_remaining_min,
        hp_remaining_max=hp_remaining_max,
        survival_chance=survival_chance,
        survives=survives,
    )

    # Create URI-safe names
    uri_attacker = attacker_name.lower().replace(" ", "-")
    uri_defender = defender_name.lower().replace(" ", "-")
    uri_move = move_name.lower().replace(" ", "-")

    return create_ui_resource({
        "uri": f"ui://vgc/multi-hit/{uri_attacker}-{uri_move}-x{num_hits}-vs-{uri_defender}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })
