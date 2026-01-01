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
