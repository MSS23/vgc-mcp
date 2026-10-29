"""MCP tools for Smogon-integrated speed analysis.

This module provides speed probability analysis using real Smogon usage data.
Complements speed_analysis_tools.py with live data integration.
"""

from typing import Annotated, Optional, Union

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.tools import speed_handlers
from vgc_mcp_core.tools.response_contract import CalcResult

# Common VGC Pokemon with their base speeds and common speed investments
# Used as fallback when Smogon data is unavailable
META_SPEED_TIERS = {
    # Ultra fast (200+)
    "regieleki": {"base": 200, "common_speeds": [277, 252, 200]},

    # Very fast (135-150)
    "electrode-hisui": {"base": 150, "common_speeds": [222, 202]},
    "dragapult": {"base": 142, "common_speeds": [213, 194]},
    "iron-bundle": {"base": 136, "common_speeds": [205, 187, 136]},
    "flutter-mane": {"base": 135, "common_speeds": [205, 187, 157]},
    "miraidon": {"base": 135, "common_speeds": [205, 187]},
    "koraidon": {"base": 135, "common_speeds": [205, 187]},
    "meowscarada": {"base": 123, "common_speeds": [192, 175]},

    # Fast (100-120)
    "chien-pao": {"base": 135, "common_speeds": [205, 187]},
    "iron-moth": {"base": 110, "common_speeds": [178, 162]},
    "raging-bolt": {"base": 110, "common_speeds": [178, 162, 110]},
    "gouging-fire": {"base": 110, "common_speeds": [178, 162]},
    "walking-wake": {"base": 109, "common_speeds": [177, 161]},
    "entei": {"base": 100, "common_speeds": [167, 152, 157]},
    "urshifu": {"base": 97, "common_speeds": [163, 148]},
    "urshifu-rapid-strike": {"base": 97, "common_speeds": [163, 148]},
    "landorus": {"base": 101, "common_speeds": [168, 153]},
    "garchomp": {"base": 102, "common_speeds": [169, 154]},
    "arcanine": {"base": 95, "common_speeds": [161, 146, 95]},
    "arcanine-hisui": {"base": 90, "common_speeds": [156, 141, 90]},

    # Medium (70-95)
    "ogerpon": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-wellspring": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-hearthflame": {"base": 110, "common_speeds": [178, 162]},
    "ogerpon-cornerstone": {"base": 110, "common_speeds": [178, 162]},
    "kingambit": {"base": 50, "common_speeds": [70, 50]},
    "gholdengo": {"base": 84, "common_speeds": [150, 136]},
    "palafin": {"base": 100, "common_speeds": [167, 152]},
    "annihilape": {"base": 90, "common_speeds": [156, 142]},
    "dragonite": {"base": 80, "common_speeds": [145, 132, 80]},
    "gyarados": {"base": 81, "common_speeds": [146, 133]},
    "pelipper": {"base": 65, "common_speeds": [126, 85]},

    # Slow (50-70)
    "rillaboom": {"base": 85, "common_speeds": [150, 137, 85]},
    "incineroar": {"base": 60, "common_speeds": [123, 92, 60]},
    "amoonguss": {"base": 30, "common_speeds": [31, 30]},
    "porygon2": {"base": 60, "common_speeds": [92, 60]},
    "dondozo": {"base": 35, "common_speeds": [75, 35]},
    "torkoal": {"base": 20, "common_speeds": [40, 20]},

    # Very Slow / Trick Room (under 50)
    "iron-hands": {"base": 50, "common_speeds": [70, 50]},
    "ursaluna": {"base": 50, "common_speeds": [70, 50]},
    "ursaluna-bloodmoon": {"base": 52, "common_speeds": [73, 52]},
    "calyrex-ice": {"base": 50, "common_speeds": [70, 50, 36]},
    "calyrex-shadow": {"base": 150, "common_speeds": [222, 202]},
    "glimmora": {"base": 70, "common_speeds": [134, 122]},
    "hatterene": {"base": 29, "common_speeds": [49, 29]},
    "indeedee-f": {"base": 95, "common_speeds": [161, 146]},
    "farigiraf": {"base": 60, "common_speeds": [123, 60]},
    "kyogre": {"base": 90, "common_speeds": [156, 142]},
    "groudon": {"base": 90, "common_speeds": [156, 142]},
}


def register_speed_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: Optional[SmogonStatsClient] = None):
    """Register Smogon-integrated speed tools with the MCP server."""

    @mcp.tool(
        title="Analyze Outspeed Probability",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def analyze_outspeed_probability(
        pokemon_name: Annotated[str, Field(description="Your Pokemon's name", min_length=1)],
        target_pokemon: Annotated[str, Field(description="The target Pokemon to compare against", min_length=1)],
        nature: Annotated[str, Field(description="Your Pokemon's nature (ignored if speed_stat is provided)")] = "serious",
        speed_evs: Annotated[Union[Annotated[int, Field(ge=0, le=252)], str], Field(description="Speed EVs (0-252), or Stat Points (0-32) in Champions; also accepts the full 'HP/Atk/Def/SpA/SpD/Spe' slash string (its Spe value is used). Ignored if speed_stat is provided")] = 0,
        speed_stat: Annotated[Optional[int], Field(description="Your Pokemon's final Speed stat (overrides the nature/EVs calculation)")] = None
    ) -> CalcResult:
        """Analyze what percentage of a target Pokemon's common spreads you outspeed.

        Uses real Smogon usage data when available, falling back to hardcoded
        meta speed tiers and then calculated standard spreads.
        """
        result = await speed_handlers.analyze_outspeed_probability(
            pokeapi,
            smogon,
            pokemon_name=pokemon_name,
            target_pokemon=target_pokemon,
            nature=nature,
            speed_evs=speed_evs,
            speed_stat=speed_stat,
        )
        return await speed_handlers.outspeed_contract(result, smogon)
