"""MCP tools for Smogon usage data."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.api.smogon import SmogonStatsClient

# MCP-UI support (enabled in vgc-mcp-lite)
from ..ui.resources import create_usage_stats_resource, add_ui_metadata
HAS_UI = True


def register_usage_tools(mcp: FastMCP, smogon: SmogonStatsClient):
    """Register Smogon usage data tools with the MCP server."""

    @mcp.tool()
    async def get_usage_stats(
        pokemon_name: str,
        format_name: Optional[str] = None,
        rating: int = 1760
    ) -> dict:
        """
        Get Smogon usage statistics for a Pokemon in VGC.

        Args:
            pokemon_name: Name of the Pokemon (e.g., "flutter-mane", "incineroar")
            format_name: VGC format (auto-detects latest if not specified)
            rating: Rating cutoff (0, 1500, 1630, or 1760). Higher = more competitive data.

        Returns:
            Usage percentage, common items, abilities, moves, spreads, and teammates
        """
        try:
            usage = await smogon.get_pokemon_usage(pokemon_name, format_name, rating)

            if not usage:
                return {
                    "error": f"No usage data found for {pokemon_name}",
                    "suggestions": [
                        "Check spelling (use hyphens: 'flutter-mane' not 'Flutter Mane')",
                        "Try a different format or rating",
                        "This Pokemon may not have enough usage data"
                    ]
                }

            # Add interactive UI (only in vgc-mcp-lite)
            if HAS_UI:
                # Extract regulation from format string (e.g., "gen9vgc2025regf" -> "Reg F")
                meta = usage.get("_meta", {})
                format_str = meta.get("format", "")
                reg_suffix = format_str[-4:] if len(format_str) >= 4 else ""
                if reg_suffix.startswith("reg") and len(reg_suffix) == 4:
                    reg_name = f"VGC Reg {reg_suffix[-1].upper()}"
                else:
                    reg_name = "VGC"

                ui_resource = create_usage_stats_resource(
                    pokemon_name=usage.get("pokemon", pokemon_name),
                    usage_percent=usage.get("usage_percent", 0),
                    items=usage.get("items", []),
                    abilities=usage.get("abilities", []),
                    moves=usage.get("moves", []),
                    spreads=usage.get("spreads", []),
                    tera_types=usage.get("tera_types"),
                    teammates=usage.get("teammates"),
                    rating=rating,
                    format_name=reg_name,
                    month_display=meta.get("month_display", ""),
                )
                return add_ui_metadata(
                    usage, ui_resource,
                    display_type="inline",
                    name="Usage Stats"
                )
            return usage

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_common_sets(
        pokemon_name: str,
        format_name: Optional[str] = None
    ) -> dict:
        """
        Get the most common competitive sets for a Pokemon.

        Args:
            pokemon_name: Name of the Pokemon
            format_name: VGC format (auto-detects latest if not specified)

        Returns:
            Top items, abilities, moves, EV spreads, and Tera types with usage rates
        """
        try:
            sets = await smogon.get_common_sets(pokemon_name, format_name)

            if not sets:
                return {"error": f"No set data found for {pokemon_name}"}

            return sets

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def suggest_teammates(
        pokemon_name: str,
        format_name: Optional[str] = None,
        limit: int = 10
    ) -> dict:
        """
        Get suggested teammates based on usage data.

        Args:
            pokemon_name: Pokemon to find teammates for
            format_name: VGC format (auto-detects latest if not specified)
            limit: Number of suggestions to return (default 10)

        Returns:
            List of common teammates with usage correlation percentages
        """
        try:
            teammates = await smogon.suggest_teammates(pokemon_name, format_name, limit)

            if not teammates:
                return {"error": f"No teammate data found for {pokemon_name}"}

            return teammates

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_current_format_info() -> dict:
        """
        Get information about the currently detected VGC format.

        Returns:
            Current format name, month, regulation, and available formats.
            Includes a notice if newer data became available mid-session.
        """
        try:
            # Trigger a fetch to populate current format info
            await smogon.get_usage_stats()

            result = {
                "current_format": smogon.current_format,
                "current_month": smogon.current_month,
                "regulation": smogon.regulation_config.current_regulation_name,
                "available_formats": smogon.VGC_FORMATS[:5],
                "rating_cutoffs": smogon.RATING_CUTOFFS
            }

            # Include data freshness notice if available
            notice = smogon.check_data_freshness()
            if notice:
                result["notice"] = notice

            return result

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def get_top_pokemon(
        format_name: Optional[str] = None,
        rating: int = 1760,
        limit: int = 20
    ) -> dict:
        """
        Get the top used Pokemon in the current VGC format.

        Args:
            format_name: VGC format (auto-detects latest if not specified)
            rating: Rating cutoff (0, 1500, 1630, or 1760). Default 1760 for high-level play.
            limit: Number of Pokemon to return

        Returns:
            List of top Pokemon with usage percentages
        """
        try:
            stats = await smogon.get_usage_stats(format_name, rating)

            if "data" not in stats:
                return {"error": "Could not fetch usage stats"}

            # Sort by usage
            pokemon_list = []
            for name, data in stats["data"].items():
                usage = data.get("usage", 0) * 100
                if usage > 0:
                    pokemon_list.append({
                        "name": name,
                        "usage_percent": round(usage, 2)
                    })

            pokemon_list.sort(key=lambda x: x["usage_percent"], reverse=True)

            return {
                "format": stats.get("_meta", {}).get("format"),
                "month": stats.get("_meta", {}).get("month"),
                "rating": rating,
                "top_pokemon": pokemon_list[:limit]
            }

        except Exception as e:
            return {"error": str(e)}

    @mcp.tool()
    async def compare_pokemon_month_over_month(
        pokemon_name: str,
        format_name: Optional[str] = None,
        rating: int = 1760
    ) -> dict:
        """
        Compare a Pokemon's usage between current and previous month.

        Identifies meta shifts like:
        - Usage percentage changes
        - Speed tier shifts (e.g., "Ogerpon was slower last month but faster this month")
        - Item preference changes
        - Move popularity changes

        Args:
            pokemon_name: Name of the Pokemon to analyze
            format_name: VGC format (auto-detects latest if not specified)
            rating: Rating cutoff (0, 1500, 1630, or 1760). Default 1760 for high-level play.

        Returns:
            Comparison data showing current vs previous month with identified changes
        """
        try:
            comparison = await smogon.compare_pokemon_usage(pokemon_name, format_name, rating)

            if not comparison:
                return {
                    "error": f"Could not find comparison data for {pokemon_name}",
                    "suggestion": "Pokemon may not have been used enough in both months"
                }

            return comparison

        except Exception as e:
            return {"error": str(e)}
