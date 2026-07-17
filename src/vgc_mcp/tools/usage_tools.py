"""MCP tools for Smogon usage data."""

from typing import Annotated, Literal, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_usage_tools(mcp: FastMCP, smogon: SmogonStatsClient):
    """Register Smogon usage data tools with the MCP server."""

    @mcp.tool(
        title="Get Pokemon Usage Stats",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_usage_stats(
        pokemon_name: Annotated[
            str,
            Field(
                description="Name of the Pokemon (e.g. 'flutter-mane', 'incineroar')", min_length=1
            ),
        ],
        format_name: Annotated[
            Optional[str], Field(description="VGC format (auto-detects latest if not specified)")
        ] = None,
        rating: Annotated[
            Optional[Literal[0, 1500, 1630, 1760]],
            Field(
                description="Smogon weighting cutoff; omit for the competitive default (1630), use 0 for unweighted data, 1500 for average ladder, or 1760 for elite play"
            ),
        ] = None,
        month: Annotated[
            Optional[str],
            Field(
                pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                description="Smogon stats month in YYYY-MM format; omit for the latest available month",
            ),
        ] = None,
    ) -> dict:
        """Get Smogon usage statistics for a Pokemon in VGC.

        Returns usage percentage, common items, abilities, moves, spreads,
        and teammates.
        """
        try:
            usage = await smogon.get_pokemon_usage(
                pokemon_name,
                format_name,
                rating,
                month,
            )

            if not usage:
                return error_response(
                    ErrorCodes.INTERNAL_ERROR,
                    f"No usage data found for {pokemon_name}",
                    suggestions=[
                        "Check spelling (use hyphens: 'flutter-mane' not 'Flutter Mane')",
                        "Try a different format or rating",
                        "This Pokemon may not have enough usage data",
                    ],
                )

            return usage

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Get Common Competitive Sets",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_common_sets(
        pokemon_name: Annotated[str, Field(description="Name of the Pokemon", min_length=1)],
        format_name: Annotated[
            Optional[str], Field(description="VGC format (auto-detects latest if not specified)")
        ] = None,
        rating: Annotated[
            Optional[Literal[0, 1500, 1630, 1760]],
            Field(description="Smogon weighting cutoff; omit for 1630 competitive data"),
        ] = None,
        month: Annotated[
            Optional[str],
            Field(
                pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                description="Smogon stats month in YYYY-MM format; omit for latest",
            ),
        ] = None,
    ) -> dict:
        """Get the most common competitive sets for a Pokemon.

        Returns top items, abilities, moves, EV spreads, and Tera types with
        usage rates.
        """
        try:
            sets = await smogon.get_common_sets(
                pokemon_name,
                format_name,
                rating,
                month=month,
            )

            if not sets:
                return error_response(
                    ErrorCodes.INTERNAL_ERROR, f"No set data found for {pokemon_name}"
                )

            return sets

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Suggest Teammates",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def suggest_teammates(
        pokemon_name: Annotated[
            str, Field(description="Pokemon to find teammates for", min_length=1)
        ],
        format_name: Annotated[
            Optional[str], Field(description="VGC format (auto-detects latest if not specified)")
        ] = None,
        rating: Annotated[
            Optional[Literal[0, 1500, 1630, 1760]],
            Field(description="Smogon weighting cutoff; omit for 1630 competitive data"),
        ] = None,
        limit: Annotated[int, Field(ge=1, description="Number of suggestions to return")] = 10,
        month: Annotated[
            Optional[str],
            Field(
                pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                description="Smogon stats month in YYYY-MM format; omit for latest",
            ),
        ] = None,
    ) -> dict:
        """Get suggested teammates based on Smogon usage data.

        Returns common teammates with usage correlation percentages.
        """
        try:
            teammates = await smogon.suggest_teammates(
                pokemon_name,
                format_name,
                rating,
                limit,
                month,
            )

            if not teammates:
                return error_response(
                    ErrorCodes.INTERNAL_ERROR, f"No teammate data found for {pokemon_name}"
                )

            return teammates

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Get Current Format Info",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_current_format_info() -> dict:
        """Get information about the currently detected VGC format.

        Returns the current format name, month, actual and configured
        regulation, available formats, and any mismatch warnings. The
        configured regulation and the data's regulation may differ if Smogon
        doesn't have the latest regulation's stats yet.
        """
        try:
            # Trigger a fetch to populate current format info
            stats = await smogon.get_usage_stats()

            actual_reg_letter = smogon.current_regulation_from_data
            configured_formats = smogon.ACTIVE_VGC_FORMATS
            data_format = stats.get("_meta", {}).get("format")

            result = {
                "current_format": smogon.current_format,
                "current_month": smogon.current_month,
                "current_rating": stats.get("_meta", {}).get("rating"),
                "source_url": stats.get("_meta", {}).get("source_url"),
                "data_regulation": f"Regulation {actual_reg_letter}"
                if actual_reg_letter
                else "Unknown",
                "configured_regulation": smogon.regulation_config.current_regulation_name,
                "available_formats": smogon.VGC_FORMATS[:5],
                "rating_cutoffs": smogon.RATING_CUTOFFS,
            }

            # Check for regulation mismatch
            if data_format not in configured_formats:
                result["notice"] = (
                    f"Configured formats {configured_formats} but using {data_format} "
                    "because the preferred Smogon dataset was unavailable."
                )
            else:
                # Include data freshness notice if available
                notice = smogon.check_data_freshness()
                if notice:
                    result["notice"] = notice

            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Get Top Used Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def get_top_pokemon(
        format_name: Annotated[
            Optional[str], Field(description="VGC format (auto-detects latest if not specified)")
        ] = None,
        rating: Annotated[
            Optional[Literal[0, 1500, 1630, 1760]],
            Field(description="Smogon weighting cutoff; omit for 1630 competitive data"),
        ] = None,
        limit: Annotated[int, Field(ge=1, description="Number of Pokemon to return")] = 20,
        month: Annotated[
            Optional[str],
            Field(
                pattern=r"^\d{4}-(0[1-9]|1[0-2])$",
                description="Smogon stats month in YYYY-MM format; omit for latest",
            ),
        ] = None,
    ) -> dict:
        """Get the top used Pokemon in the current VGC format.

        Returns a list of top Pokemon with usage percentages.
        """
        try:
            stats = await smogon.get_usage_stats(format_name, rating, month)

            if "data" not in stats:
                return error_response(ErrorCodes.API_ERROR, "Could not fetch usage stats")

            # Sort by usage
            pokemon_list = []
            for name, data in stats["data"].items():
                usage = data.get("usage", 0) * 100
                if usage > 0:
                    pokemon_list.append({"name": name, "usage_percent": round(usage, 2)})

            pokemon_list.sort(key=lambda x: x["usage_percent"], reverse=True)

            return {
                "format": stats.get("_meta", {}).get("format"),
                "month": stats.get("_meta", {}).get("month"),
                "rating": stats.get("_meta", {}).get("rating"),
                "source_url": stats.get("_meta", {}).get("source_url"),
                "top_pokemon": pokemon_list[:limit],
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool(
        title="Compare Usage Month over Month",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def compare_pokemon_month_over_month(
        pokemon_name: Annotated[
            str, Field(description="Name of the Pokemon to analyze", min_length=1)
        ],
        format_name: Annotated[
            Optional[str], Field(description="VGC format (auto-detects latest if not specified)")
        ] = None,
        rating: Annotated[
            Optional[Literal[0, 1500, 1630, 1760]],
            Field(description="Smogon weighting cutoff; omit for 1630 competitive data"),
        ] = None,
    ) -> dict:
        """Compare a Pokemon's usage between the current and previous month.

        Returns comparison data with identified meta shifts: usage percentage
        changes, speed tier shifts, item preference changes, and move
        popularity changes.
        """
        try:
            comparison = await smogon.compare_pokemon_usage(pokemon_name, format_name, rating)

            if not comparison:
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Could not find comparison data for {pokemon_name}",
                    suggestion="Pokemon may not have been used enough in both months",
                )

            return comparison

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
