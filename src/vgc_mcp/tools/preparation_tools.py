"""Thin MCP registrations for verified preparation and sourced sets."""

from typing import Annotated, Any, Literal

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.api.pokeapi import PokeAPIClient
from vgc_mcp_core.api.smogon import SmogonStatsClient
from vgc_mcp_core.export.preparation_report import export_preparation_report
from vgc_mcp_core.models.pokemon import Nature
from vgc_mcp_core.models.preparation import BenchmarkSpec
from vgc_mcp_core.team.manager import TeamManager
from vgc_mcp_core.tools.preparation_handlers import (
    benchmark_handler,
    import_reference_handler,
    outcomes_handler,
    prepare_team_handler,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False, idempotentHint=True, openWorldHint=True)


def register_preparation_tools(mcp: FastMCP, pokeapi: PokeAPIClient, smogon: SmogonStatsClient, team_manager: TeamManager) -> None:
    """Expose cohesive workflows to Claude and other MCP clients."""

    @mcp.tool(title="Move Outcomes Including Accuracy and Hit Counts", annotations=READ_ONLY)
    async def calculate_move_outcomes(
        attacker_paste: str, defender_paste: str, move_name: str,
        regulation: str | None = None, conditions: dict[str, Any] | None = None,
        include_accuracy: bool = True, random_hits: bool = True,
    ) -> dict[str, Any]:
        """Calculate independent hit rolls, misses, berries and Parental Bond from exact Showdown pastes.

        Probability includes accuracy and random hit counts by default. Set both
        flags false for damage conditional on the chosen/default number of hits.
        conditions accepts DamageModifiers fields; regulation defaults to the session.
        """
        try:
            return await outcomes_handler(attacker_paste, defender_paste, move_name, pokeapi,
                                          regulation, conditions, include_accuracy, random_hits)
        except (ValueError, TypeError) as exc:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(exc))
        except Exception as exc:
            return error_response(ErrorCodes.API_ERROR, str(exc))

    @mcp.tool(title="Verify Exact Spread Benchmarks", annotations=READ_ONLY)
    async def verify_spread_benchmarks(
        pokemon_paste: str, benchmarks: Annotated[list[BenchmarkSpec], Field(min_length=1, max_length=6)],
        regulation: str | None = None,
    ) -> dict[str, Any]:
        """Recalculate survive, KO and outspeed constraints against exact or chaos opponents.

        Each benchmark supplies kind, exactly one opponent_paste/opponent_name,
        move for damage, optional probability percent and conditions. Includes
        all exact spreads, assumptions and provenance for independent checking.
        """
        try:
            return await benchmark_handler(pokemon_paste, benchmarks, pokeapi, smogon, regulation)
        except (ValueError, TypeError) as exc:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(exc))
        except Exception as exc:
            return error_response(ErrorCodes.API_ERROR, str(exc))

    @mcp.tool(title="Recommend Verified Spread Alternatives", annotations=READ_ONLY)
    async def recommend_verified_spreads(
        pokemon_paste: str, benchmarks: Annotated[list[BenchmarkSpec], Field(min_length=1, max_length=6)],
        regulation: str | None = None, natures: Annotated[list[Nature] | None, Field(max_length=25)] = None,
    ) -> dict[str, Any]:
        """Offer minimum-investment, offensive and bulky spreads that pass final exact verification.

        Retains item, ability, moves, IVs and level. Reports stat tradeoffs and
        bounded search scope; no result is not proof that every spread is impossible.
        """
        try:
            return await benchmark_handler(pokemon_paste, benchmarks, pokeapi, smogon, regulation,
                                           recommend=True, natures=natures)
        except (ValueError, TypeError) as exc:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(exc))
        except Exception as exc:
            return error_response(ErrorCodes.API_ERROR, str(exc))

    @mcp.tool(title="Import Complete Reference Sets", annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=True, openWorldHint=True))
    async def import_reference_team(
        paste: str, source_name: str, source_url: str | None = None, regulation: str | None = None,
    ) -> dict[str, Any]:
        """Store complete user-supplied sets with attribution in this MCP session.

        Requires an ability and four moves per Pokemon. These are separate from
        chaos marginal frequencies; source attribution is not independently verified.
        Does not replace the user's active team.
        """
        try:
            return await import_reference_handler(paste, source_name, source_url, regulation, pokeapi, team_manager)
        except (ValueError, TypeError) as exc:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(exc))
        except Exception as exc:
            return error_response(ErrorCodes.API_ERROR, str(exc))

    @mcp.tool(title="Prepare Team Against the Current Metagame", annotations=ToolAnnotations(
        readOnlyHint=False, destructiveHint=False, idempotentHint=False, openWorldHint=True))
    async def prepare_team(
        team_paste: str | None = None, regulation: str | None = None,
        opponent_names: Annotated[list[str] | None, Field(min_length=1, max_length=12)] = None,
        meta_limit: Annotated[int, Field(ge=1, le=12)] = 6,
        benchmarks_by_slot: dict[int, list[BenchmarkSpec]] | None = None,
        export_format: Literal["markdown", "json", "excel", "pdf"] | None = None,
    ) -> dict[str, Any]:
        """Prepare a Showdown team or current session team in one MCP call.

        Returns rules checks, speed tiers, offensive/defensive threat comparisons,
        dated chaos sources, a Markdown report and paste. Optional benchmarks_by_slot
        (one-based slots) adds three verified spread alternatives per requested slot.
        Optional export returns file data for the MCP client; does not change the team.
        """
        try:
            report = await prepare_team_handler(team_paste, regulation, opponent_names, meta_limit,
                                               benchmarks_by_slot, pokeapi, smogon, team_manager)
            if export_format:
                report["export"] = export_preparation_report(report, export_format)
            return report
        except (ValueError, TypeError) as exc:
            return error_response(ErrorCodes.INVALID_PARAMETER, str(exc))
        except Exception as exc:
            return error_response(ErrorCodes.API_ERROR, str(exc))
