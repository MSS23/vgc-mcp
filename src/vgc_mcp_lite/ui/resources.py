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
    create_usage_stats_ui,
    create_stats_card_ui,
    create_pokemon_build_card_ui,
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


def create_usage_stats_resource(
    pokemon_name: str,
    usage_percent: float,
    items: list[dict[str, Any]],
    abilities: list[dict[str, Any]],
    moves: list[dict[str, Any]],
    spreads: list[dict[str, Any]],
    tera_types: list[dict[str, Any]] | None = None,
    teammates: list[dict[str, Any]] | None = None,
    rating: int = 1760,
    format_name: str = "VGC Reg G",
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
        rating=rating,
        format_name=format_name,
    )

    return create_ui_resource({
        "uri": f"ui://vgc/usage/{pokemon_name.lower()}",
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


def create_summary_table_resource(
    title: str,
    rows: list[dict[str, str]],
    highlight_rows: list[str] | None = None,
    analysis: str | None = None,
) -> dict[str, Any]:
    """Create a summary table UI resource.

    Returns a dict with the UI resource showing a simple key-value table.

    Args:
        title: Table title
        rows: List of dicts with "metric" and "value" keys
        highlight_rows: List of metric names to highlight
        analysis: Optional analysis text to show below table
    """
    highlight_set = set(highlight_rows or [])

    # Build simple HTML table
    table_rows = []
    for row in rows:
        metric = row.get("metric", "")
        value = row.get("value", "")
        is_highlight = metric in highlight_set
        style = "background: #e8f5e9; font-weight: bold;" if is_highlight else ""
        table_rows.append(
            f'<tr style="{style}"><td style="padding: 8px; border: 1px solid #ddd;">{metric}</td>'
            f'<td style="padding: 8px; border: 1px solid #ddd;">{value}</td></tr>'
        )

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 400px;">
        <h3 style="margin: 0 0 12px 0; color: #333;">{title}</h3>
        <table style="border-collapse: collapse; width: 100%;">
            <thead>
                <tr style="background: #f5f5f5;">
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Metric</th>
                    <th style="padding: 8px; border: 1px solid #ddd; text-align: left;">Value</th>
                </tr>
            </thead>
            <tbody>
                {"".join(table_rows)}
            </tbody>
        </table>
        {f'<p style="margin-top: 12px; color: #666; font-size: 14px;">{analysis}</p>' if analysis else ""}
    </div>
    """

    return create_ui_resource({
        "uri": f"ui://vgc/summary/{title.lower().replace(' ', '-')}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_multi_hit_survival_resource(
    pokemon_name: str,
    attacker_name: str,
    move_name: str,
    hits_to_ko: int,
    damage_per_hit: tuple[float, float],
    total_damage: tuple[float, float],
    hp: int,
) -> dict[str, Any]:
    """Create a multi-hit survival analysis UI resource.

    Args:
        pokemon_name: Defending Pokemon name
        attacker_name: Attacking Pokemon name
        move_name: Multi-hit move name
        hits_to_ko: Number of hits needed to KO
        damage_per_hit: (min, max) damage percentage per hit
        total_damage: (min, max) total damage percentage
        hp: Defender's HP stat
    """
    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 400px; padding: 16px; border: 1px solid #ddd; border-radius: 8px;">
        <h3 style="margin: 0 0 12px 0; color: #333;">Multi-Hit Survival</h3>
        <p style="margin: 4px 0;"><strong>{attacker_name}</strong> using <strong>{move_name}</strong></p>
        <p style="margin: 4px 0;">vs <strong>{pokemon_name}</strong> ({hp} HP)</p>
        <hr style="border: none; border-top: 1px solid #eee; margin: 12px 0;">
        <p style="margin: 4px 0;">Damage per hit: {damage_per_hit[0]:.1f}% - {damage_per_hit[1]:.1f}%</p>
        <p style="margin: 4px 0;">Total damage: {total_damage[0]:.1f}% - {total_damage[1]:.1f}%</p>
        <p style="margin: 4px 0; font-weight: bold; color: {'#c62828' if hits_to_ko <= 3 else '#2e7d32'};">
            Hits to KO: {hits_to_ko}
        </p>
    </div>
    """

    return create_ui_resource({
        "uri": f"ui://vgc/survival/{pokemon_name.lower()}-vs-{attacker_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_speed_outspeed_graph_resource(
    pokemon_name: str,
    pokemon_speed: int,
    outspeed_data: list[dict[str, Any]],
) -> dict[str, Any]:
    """Create a speed outspeed graph UI resource.

    Args:
        pokemon_name: Pokemon name
        pokemon_speed: Current speed stat
        outspeed_data: List of Pokemon with speed comparisons
    """
    rows_html = ""
    for entry in outspeed_data[:10]:
        name = entry.get("name", "Unknown")
        speed = entry.get("speed", 0)
        outspeed = "faster" if pokemon_speed > speed else ("tied" if pokemon_speed == speed else "slower")
        color = "#2e7d32" if outspeed == "faster" else ("#f57c00" if outspeed == "tied" else "#c62828")
        rows_html += f'<tr><td style="padding: 6px; border-bottom: 1px solid #eee;">{name}</td><td style="padding: 6px; border-bottom: 1px solid #eee;">{speed}</td><td style="padding: 6px; border-bottom: 1px solid #eee; color: {color};">{outspeed}</td></tr>'

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 500px;">
        <h3 style="margin: 0 0 12px 0; color: #333;">{pokemon_name} Speed Analysis ({pokemon_speed} Spe)</h3>
        <table style="width: 100%; border-collapse: collapse;">
            <thead>
                <tr style="background: #f5f5f5;">
                    <th style="padding: 8px; text-align: left;">Pokemon</th>
                    <th style="padding: 8px; text-align: left;">Speed</th>
                    <th style="padding: 8px; text-align: left;">Result</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
    """

    return create_ui_resource({
        "uri": f"ui://vgc/speed/outspeed/{pokemon_name.lower()}",
        "content": {
            "type": "rawHtml",
            "htmlString": html,
        },
        "encoding": "text",
    })


def create_threat_analysis_resource(
    pokemon_name: str,
    threats: list[dict[str, Any]],
    counters: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a threat analysis UI resource.

    Args:
        pokemon_name: Pokemon being analyzed
        threats: List of threatening Pokemon with damage info
        counters: List of Pokemon this one threatens (optional)
    """
    threats_html = ""
    for threat in threats[:5]:
        name = threat.get("name", "Unknown")
        move = threat.get("move", "")
        damage = threat.get("damage", "?%")
        threats_html += f'<li style="margin: 4px 0;"><strong>{name}</strong> - {move}: {damage}</li>'

    counters_html = ""
    if counters:
        counters_html = "<h4 style='margin: 12px 0 8px 0;'>Threatens:</h4><ul style='margin: 0; padding-left: 20px;'>"
        for counter in counters[:5]:
            name = counter.get("name", "Unknown")
            move = counter.get("move", "")
            damage = counter.get("damage", "?%")
            counters_html += f'<li style="margin: 4px 0;"><strong>{name}</strong> - {move}: {damage}</li>'
        counters_html += "</ul>"

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 400px; padding: 16px; border: 1px solid #ddd; border-radius: 8px;">
        <h3 style="margin: 0 0 12px 0; color: #333;">{pokemon_name} Threat Analysis</h3>
        <h4 style="margin: 0 0 8px 0; color: #c62828;">Threatened by:</h4>
        <ul style="margin: 0; padding-left: 20px;">
            {threats_html if threats_html else '<li>No major threats identified</li>'}
        </ul>
        {counters_html}
    </div>
    """

    return create_ui_resource({
        "uri": f"ui://vgc/threats/{pokemon_name.lower()}",
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
    """Create a coverage heatmap UI resource.

    Args:
        pokemon_name: Pokemon or team name
        moves: List of moves with name and type
        coverage: Dict mapping type names to effectiveness values
    """
    # Type color palette
    type_colors = {
        "normal": "#A8A878", "fire": "#F08030", "water": "#6890F0",
        "electric": "#F8D030", "grass": "#78C850", "ice": "#98D8D8",
        "fighting": "#C03028", "poison": "#A040A0", "ground": "#E0C068",
        "flying": "#A890F0", "psychic": "#F85888", "bug": "#A8B820",
        "rock": "#B8A038", "ghost": "#705898", "dragon": "#7038F8",
        "dark": "#705848", "steel": "#B8B8D0", "fairy": "#EE99AC",
    }

    # Build coverage grid cells
    cells_html = ""
    for type_name, eff in sorted(coverage.items()):
        bg_color = type_colors.get(type_name.lower(), "#888")
        # Effectiveness overlay
        if eff >= 2.0:
            eff_color = "rgba(0, 200, 0, 0.3)"  # Green for SE
            eff_text = f"{eff}x"
        elif eff < 1.0 and eff > 0:
            eff_color = "rgba(200, 0, 0, 0.3)"  # Red for NVE
            eff_text = f"{eff}x"
        elif eff == 0:
            eff_color = "rgba(0, 0, 0, 0.5)"  # Dark for immune
            eff_text = "0x"
        else:
            eff_color = "transparent"
            eff_text = "1x"

        cells_html += f'''
        <div style="
            background: linear-gradient({eff_color}, {eff_color}), {bg_color};
            color: white;
            padding: 8px;
            border-radius: 4px;
            text-align: center;
            text-shadow: 1px 1px 2px black;
            font-size: 12px;
        ">
            <div style="font-weight: bold;">{type_name.title()}</div>
            <div>{eff_text}</div>
        </div>
        '''

    # Build moves list
    moves_html = ""
    for move in moves[:4]:
        move_name = move.get("name", "Unknown")
        move_type = move.get("type", "normal")
        moves_html += f'<span style="background: {type_colors.get(move_type.lower(), "#888")}; color: white; padding: 4px 8px; border-radius: 4px; margin: 2px; display: inline-block; text-shadow: 1px 1px 2px black;">{move_name}</span>'

    html = f"""
    <div style="font-family: system-ui, sans-serif; max-width: 500px;">
        <h3 style="margin: 0 0 12px 0; color: #333;">{pokemon_name} Coverage</h3>
        <div style="margin-bottom: 12px;">
            {moves_html if moves_html else '<em>No moves</em>'}
        </div>
        <div style="display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px;">
            {cells_html}
        </div>
        <p style="margin-top: 12px; font-size: 12px; color: #666;">
            Green = Super Effective | Red = Not Very Effective | Dark = Immune
        </p>
    </div>
    """

    return create_ui_resource({
        "uri": f"ui://vgc/coverage/{pokemon_name.lower().replace(' ', '-')}",
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
