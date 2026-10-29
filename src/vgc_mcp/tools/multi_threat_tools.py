"""MCP tools for multi-threat bulk calculations."""

from typing import Annotated, Dict, List, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.tools import spread_survival_handlers


def register_multi_threat_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon_client=None):
    """Register multi-threat bulk calculation tools with the MCP server."""

    @mcp.tool(
        title="Find Multi-Threat Bulk EVs",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def find_multi_threat_bulk_evs(
        pokemon_name: Annotated[str, Field(description="Name of the Pokemon to optimize", min_length=1)],
        threats: Annotated[List[Dict], Field(
            description="List of threat dicts, each with 'name' (attacker Pokemon), 'move' (move name), and optional 'spread' (dict with nature, evs, item, ability; most common Smogon spread used if omitted)",
        )],
        nature: Annotated[str, Field(description="Nature for the defender")] = "bold",
        item: Annotated[Optional[str], Field(description="Item for the defender")] = None,
        ability: Annotated[Optional[str], Field(description="Ability for the defender (auto-detected if None)")] = None,
        target_survival_chance: Annotated[float, Field(ge=0, le=100, description="Target survival % (100 = guaranteed survive)")] = 100.0,
    ) -> dict:
        """Deprecated alias of `optimize_multi_survival_spread`; will be removed in the next release.
        Call optimize_multi_survival_spread with threats=[{'attacker', 'move', ...}], nature and target_survival instead.

        Finds the minimum HP/Def/SpD investment that survives every threat at a
        fixed nature with no Speed investment, and keeps the legacy
        recommended_spread / survival_results / markdown_summary keys.
        """
        return await spread_survival_handlers.find_multi_threat_bulk_evs(
            pokeapi,
            smogon_client,
            pokemon_name=pokemon_name,
            threats=threats,
            nature=nature,
            item=item,
            ability=ability,
            target_survival_chance=target_survival_chance,
        )
