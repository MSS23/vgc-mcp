"""MCP tools for speed tier visualization."""

from typing import Annotated, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.tools import speed_handlers


def register_speed_viz_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient]):
    """Register speed tier visualization tools."""

    @mcp.tool(
        title="Visualize Team Speed Tiers",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def visualize_team_speed_tiers(
        team_pokemon: Annotated[List[Dict], Field(description="List of Pokemon dicts, each with 'name' and optional 'nature', 'evs', 'item'")],
        include_weather: Annotated[bool, Field(description="Include weather speed modifiers")] = True,
        include_tailwind: Annotated[bool, Field(description="Include Tailwind (2x) speed tiers")] = True,
        format: Annotated[str, Field(description="VGC format (e.g. 'reg_h')")] = "reg_h"
    ) -> dict:
        """Deprecated alias of `visualize_speed_tiers`; will be removed in the next release.
        Call `visualize_speed_tiers(pokemon_speeds=team_pokemon, include_tailwind=...)` instead; its entries accept 'nature' + 'evs'.

        `include_weather` and `format` were never applied and are ignored. The
        result is the canonical chart plus this tool's legacy keys
        (team_speeds, meta_speeds, all_speeds, markdown_summary).
        """
        result = await speed_handlers.visualize_speed_tiers(
            pokeapi,
            pokemon_speeds=team_pokemon,
            include_tailwind=include_tailwind,
        )
        everyone = result["all_pokemon"]
        return {
            **result,
            "team_speeds": result["your_pokemon"],
            "meta_speeds": [p for p in everyone if not p["is_yours"]],
            "all_speeds": everyone,
            "markdown_summary": result["visualization"],
        }
