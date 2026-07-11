"""MCP tools for move-based coverage analysis."""

import logging
from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.calc.coverage import (
    ALL_TYPES,
    COVERAGE_MOVES,
    analyze_move_coverage,
    check_coverage_vs_pokemon,
    check_quad_weaknesses,
    find_coverage_holes,
    get_coverage_summary,
    suggest_coverage_moves,
)
from vgc_mcp_core.utils.errors import ErrorCodes, error_response

logger = logging.getLogger(__name__)


def register_coverage_tools(mcp: FastMCP, team_manager, pokeapi):
    """Register coverage analysis tools with the MCP server."""

    @mcp.tool(
        title="Analyze Team Move Coverage",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def analyze_team_move_coverage() -> dict:
        """Analyze the current team's move-based offensive coverage.

        Unlike STAB-based analysis, this checks what types the team can hit
        super-effectively with their actual movesets. Returns types covered,
        coverage holes, best/worst covered types, and coverage percentage.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return error_response(
                ErrorCodes.TEAM_EMPTY,
                "No Pokemon on team. Add Pokemon with moves to analyze coverage.",
            )

        # Build team data for analysis
        team_data = []
        for slot in team.slots:
            pokemon = slot.pokemon
            team_data.append({
                "name": pokemon.name,
                "types": pokemon.types,
                "moves": pokemon.moves
            })

        result = analyze_move_coverage(team_data)

        # Format type coverage for output
        type_coverage_summary = {}
        for type_name, cov in result.type_coverage.items():
            if cov.is_covered:
                type_coverage_summary[type_name] = {
                    "covered": True,
                    "coverage_count": cov.coverage_count,
                    "stab_options": len(cov.stab_coverage),
                    "non_stab_options": len(cov.non_stab_coverage),
                    "covered_by": [
                        {
                            "pokemon": c.pokemon,
                            "move": c.move_name,
                            "is_stab": c.is_stab
                        }
                        for c in cov.covered_by[:3]  # Top 3
                    ]
                }

        summary = get_coverage_summary(team_data)

        output = {
            "team_pokemon": result.team_pokemon,
            "coverage_summary": summary,
            "type_coverage": type_coverage_summary,
            "coverage_holes": result.coverage_holes,
            "best_covered_types": result.best_coverage,
            "message": (
                f"Team covers {summary['covered_types']}/{summary['total_types']} types "
                f"({summary['coverage_percentage']}%)"
                + (f". Missing: {', '.join(result.coverage_holes)}"
                   if result.coverage_holes else "")
            )
        }

        return output

    @mcp.tool(
        title="Find Team Coverage Holes",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def find_team_coverage_holes() -> dict:
        """Find types that no current team member can hit super-effectively.

        Coverage holes represent types the team struggles against. Returns the
        hole list plus move suggestions to address them.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "holes": [],
                "message": "No Pokemon on team"
            }

        team_data = []
        for slot in team.slots:
            pokemon = slot.pokemon
            team_data.append({
                "name": pokemon.name,
                "types": pokemon.types,
                "moves": pokemon.moves
            })

        holes = find_coverage_holes(team_data)

        if not holes:
            return {
                "holes": [],
                "has_holes": False,
                "message": "Excellent! Team has super-effective coverage against all types"
            }

        # Suggest what to add
        suggestions = suggest_coverage_moves(holes, prioritize_spread=True)

        return {
            "holes": holes,
            "hole_count": len(holes),
            "has_holes": True,
            "suggestions": suggestions[:5],
            "message": (
                f"Team has no SE coverage against {len(holes)} type(s): "
                f"{', '.join(holes)}"
            )
        }

    @mcp.tool(
        title="Check Team Quad Weaknesses",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_team_quad_weaknesses() -> dict:
        """Find Pokemon on the current team with 4x type weaknesses.

        Quad weaknesses are dangerous because even resisted super-effective
        moves can deal massive damage. Returns each 4x weakness, grouped by type.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "quad_weaknesses": [],
                "message": "No Pokemon on team"
            }

        team_data = []
        for slot in team.slots:
            pokemon = slot.pokemon
            team_data.append({
                "name": pokemon.name,
                "types": pokemon.types,
                "moves": pokemon.moves
            })

        quad = check_quad_weaknesses(team_data)

        if not quad:
            return {
                "quad_weaknesses": [],
                "has_quad_weakness": False,
                "message": "No Pokemon on team have 4x type weaknesses"
            }

        # Group by type
        by_type = {}
        for qw in quad:
            weak_to = qw["weak_to"]
            if weak_to not in by_type:
                by_type[weak_to] = []
            by_type[weak_to].append(qw["pokemon"])

        return {
            "quad_weaknesses": quad,
            "grouped_by_type": by_type,
            "has_quad_weakness": True,
            "count": len(quad),
            "message": (
                f"Found {len(quad)} 4x weakness(es): "
                + ", ".join(f"{qw['pokemon']} (4x {qw['weak_to']})" for qw in quad)
            )
        }

    @mcp.tool(
        title="Check Coverage vs Target",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=True,
        ),
    )
    async def check_coverage_vs_target(
        target_pokemon: Annotated[str, Field(description="Name of the Pokemon to check coverage against (e.g. 'incineroar')", min_length=1)]
    ) -> dict:
        """Check if the current team has super-effective coverage against a specific Pokemon.

        Useful for checking matchups against common meta threats. Returns the
        coverage options (best move and all moves) that hit the target super-effectively.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "has_coverage": False,
                "message": "No Pokemon on team"
            }

        # Get target Pokemon types
        try:
            target_data = await pokeapi.get_pokemon(target_pokemon)
            target_types = target_data.get("types", [])
        except Exception as e:
            logger.warning("Failed to fetch Pokemon '%s': %s", target_pokemon, e)
            return error_response(
                ErrorCodes.POKEMON_NOT_FOUND,
                f"Could not find Pokemon: {target_pokemon}",
                suggestions=["Check the Pokemon name and spelling"],
            )

        if not target_types:
            return error_response(
                ErrorCodes.API_ERROR,
                f"Could not determine types for {target_pokemon} — Pokemon data incomplete",
            )

        team_data = []
        for slot in team.slots:
            pokemon = slot.pokemon
            team_data.append({
                "name": pokemon.name,
                "types": pokemon.types,
                "moves": pokemon.moves
            })

        result = check_coverage_vs_pokemon(team_data, target_types)

        return {
            "target_pokemon": target_pokemon,
            "target_types": result["target_types"],
            "has_coverage": result["has_coverage"],
            "coverage_count": result["coverage_count"],
            "best_option": result["best_option"],
            "all_options": result["options"],
            "message": (
                f"{result['coverage_count']} move(s) hit {target_pokemon} "
                f"({'/'.join(result['target_types'])}) super-effectively"
                if result["has_coverage"]
                else f"No super-effective coverage against {target_pokemon} "
                f"({'/'.join(result['target_types'])})"
            )
        }

    @mcp.tool(
        title="Suggest Team Coverage Moves",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def suggest_team_coverage_moves(
        category: Annotated[Optional[str], Field(description="Filter suggestions by move category: 'physical' or 'special'")] = None,
        prioritize_spread: Annotated[bool, Field(description="If True, prefer spread moves (better in doubles)")] = False
    ) -> dict:
        """Suggest moves to fill the current team's coverage gaps.

        Finds the team's coverage holes and returns candidate moves that would
        cover them, honoring the category/spread filters.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "suggestions": [],
                "message": "No Pokemon on team"
            }

        team_data = []
        existing_types = set()
        for slot in team.slots:
            pokemon = slot.pokemon
            team_data.append({
                "name": pokemon.name,
                "types": pokemon.types,
                "moves": pokemon.moves
            })
            # Track types already covered
            for ptype in pokemon.types:
                existing_types.add(ptype.capitalize())

        holes = find_coverage_holes(team_data)

        if not holes:
            return {
                "suggestions": [],
                "coverage_complete": True,
                "message": "Team already has full type coverage!"
            }

        suggestions = suggest_coverage_moves(
            coverage_holes=holes,
            existing_types=list(existing_types),
            category_preference=category.lower() if category else None,
            prioritize_spread=prioritize_spread
        )

        return {
            "coverage_holes": holes,
            "suggestions": suggestions,
            "filters_applied": {
                "category": category,
                "prioritize_spread": prioritize_spread
            },
            "message": (
                f"Found {len(suggestions)} move(s) to cover: {', '.join(holes)}"
            )
        }

    @mcp.tool(
        title="Get Coverage Move Options",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_coverage_move_options(
        move_type: Annotated[str, Field(description="The type of coverage move to look for (e.g. 'Ice', 'Ground')", min_length=1)]
    ) -> dict:
        """Get available coverage moves of a specific type.

        Returns physical/special/spread/priority move options of that type,
        with stats and what they hit super-effectively.
        """
        move_type = move_type.capitalize()

        if move_type not in ALL_TYPES:
            return error_response(
                ErrorCodes.INVALID_PARAMETER,
                f"Invalid type: {move_type}. Please specify a valid type.",
                valid_types=ALL_TYPES,
            )

        if move_type not in COVERAGE_MOVES:
            return {
                "moves": [],
                "message": f"No coverage move data for {move_type} type"
            }

        moves = COVERAGE_MOVES[move_type]

        # Calculate what each move hits SE
        super_effective_vs = []
        for target_type in ALL_TYPES:
            from vgc_mcp_core.calc.modifiers import get_type_effectiveness
            eff = get_type_effectiveness(move_type, [target_type])
            if eff >= 2.0:
                super_effective_vs.append(target_type)

        physical_moves = [m for m in moves if m.get("category") == "physical"]
        special_moves = [m for m in moves if m.get("category") == "special"]

        return {
            "type": move_type,
            "super_effective_vs": super_effective_vs,
            "physical_options": physical_moves,
            "special_options": special_moves,
            "spread_moves": [m for m in moves if m.get("spread", False)],
            "priority_moves": [m for m in moves if m.get("priority", 0) > 0],
            "total_moves": len(moves),
            "message": (
                f"{move_type} moves hit {', '.join(super_effective_vs)} super-effectively"
            )
        }
