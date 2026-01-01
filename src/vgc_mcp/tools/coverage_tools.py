"""MCP tools for move-based coverage analysis."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from ..calc.coverage import (
    analyze_move_coverage,
    find_coverage_holes,
    check_quad_weaknesses,
    check_coverage_vs_pokemon,
    suggest_coverage_moves,
    get_coverage_summary,
    ALL_TYPES,
    COVERAGE_MOVES,
)
from ..ui.resources import create_coverage_resource, add_ui_metadata


def register_coverage_tools(mcp: FastMCP, team_manager, pokeapi):
    """Register coverage analysis tools with the MCP server."""

    @mcp.tool()
    async def analyze_team_move_coverage() -> dict:
        """
        Analyze team's move-based offensive coverage.

        Unlike STAB-based analysis, this checks what types the team
        can hit super-effectively with their actual moveset.

        Returns:
            Complete coverage analysis including:
            - Types covered by moves
            - Coverage holes (types with no SE coverage)
            - Best and worst covered types
            - Coverage percentage
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "error": "No Pokemon on team",
                "message": "Add Pokemon with moves to analyze coverage"
            }

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

        # Add MCP-UI resource for interactive coverage display
        try:
            if team_data:
                # Build coverage dict for UI (type -> effectiveness)
                from ..calc.modifiers import get_type_effectiveness
                coverage_dict = {}
                for type_name in ALL_TYPES:
                    # Find best coverage against this type from team's moves
                    best_eff = 1.0
                    for pokemon in team_data:
                        for move_name in (pokemon.get("moves") or []):
                            # Look up move type from COVERAGE_MOVES or assume normal
                            move_type = "Normal"
                            for mtype, moves in COVERAGE_MOVES.items():
                                if any(m.get("name", "").lower() == move_name.lower() for m in moves):
                                    move_type = mtype
                                    break
                            eff = get_type_effectiveness(move_type, [type_name])
                            if eff > best_eff:
                                best_eff = eff
                    coverage_dict[type_name.lower()] = best_eff

                # Use first Pokemon for UI display
                first_pokemon = team_data[0]
                moves_for_ui = [{"name": m, "type": "normal", "power": "-"} for m in (first_pokemon.get("moves") or [])]

                ui_resource = create_coverage_resource(
                    pokemon_name="Team",
                    moves=moves_for_ui,
                    coverage=coverage_dict,
                )
                output = add_ui_metadata(output, ui_resource)
        except Exception:
            # UI is optional
            pass

        return output

    @mcp.tool()
    async def find_team_coverage_holes() -> dict:
        """
        Find types that no team member can hit super-effectively.

        Coverage holes represent types the team struggles against.
        Consider adding coverage moves or Pokemon to address these.

        Returns:
            List of types with no super-effective coverage
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

    @mcp.tool()
    async def check_team_quad_weaknesses() -> dict:
        """
        Find Pokemon on the team with 4x type weaknesses.

        Quad weaknesses are dangerous because even resisted
        super-effective moves can deal massive damage.

        Returns:
            List of Pokemon and their 4x weaknesses
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

    @mcp.tool()
    async def check_coverage_vs_target(
        target_pokemon: str
    ) -> dict:
        """
        Check if the team has super-effective coverage against a specific Pokemon.

        Useful for checking matchups against common meta threats.

        Args:
            target_pokemon: Name of the Pokemon to check coverage against

        Returns:
            Coverage options against the target
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
        except Exception:
            return {
                "error": f"Could not find Pokemon: {target_pokemon}",
                "message": "Please check the Pokemon name"
            }

        if not target_types:
            return {
                "error": f"Could not determine types for {target_pokemon}",
                "message": "Pokemon data incomplete"
            }

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

    @mcp.tool()
    async def suggest_team_coverage_moves(
        category: Optional[str] = None,
        prioritize_spread: bool = False
    ) -> dict:
        """
        Suggest moves to fill coverage gaps on the team.

        Args:
            category: Filter by "physical" or "special" (optional)
            prioritize_spread: If True, prefer spread moves for doubles

        Returns:
            Move suggestions to improve coverage
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

    @mcp.tool()
    async def get_coverage_move_options(
        move_type: str
    ) -> dict:
        """
        Get available coverage moves of a specific type.

        Args:
            move_type: The type of coverage move to look for (e.g., "Ice", "Ground")

        Returns:
            List of moves with their stats and notes
        """
        move_type = move_type.capitalize()

        if move_type not in ALL_TYPES:
            return {
                "error": f"Invalid type: {move_type}",
                "valid_types": ALL_TYPES,
                "message": "Please specify a valid type"
            }

        if move_type not in COVERAGE_MOVES:
            return {
                "moves": [],
                "message": f"No coverage move data for {move_type} type"
            }

        moves = COVERAGE_MOVES[move_type]

        # Calculate what each move hits SE
        super_effective_vs = []
        for target_type in ALL_TYPES:
            from ..calc.modifiers import get_type_effectiveness
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
