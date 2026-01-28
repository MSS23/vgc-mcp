"""High-level workflow coordinator tools for improved user experience.

These tools combine multiple operations into single, intuitive commands
for common VGC teambuilding workflows.
"""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.formats.showdown import parse_showdown_team, ShowdownParseError
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.utils.errors import error_response, success_response, ErrorCodes
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name
from vgc_mcp_core.calc.damage import format_percent


def register_workflow_tools(mcp: FastMCP, pokeapi, smogon, team_manager, analyzer):
    """Register high-level workflow tools with the MCP server."""

    @mcp.tool()
    async def full_team_check(
        paste: Optional[str] = None,
        detailed: bool = True
    ) -> dict:
        """
        Team analysis with configurable detail level.

        When detailed=True (default): Full comprehensive analysis with grade,
        tournament readiness, legality check, strengths, weaknesses, and fix suggestions.

        When detailed=False: Quick summary with just major weaknesses,
        unresisted types, and speed range - useful for fast iteration.

        Args:
            paste: Optional Showdown paste. If not provided, uses current team.
            detailed: If True (default), returns full analysis with grades.
                     If False, returns quick summary only.

        Returns (detailed=True):
            - overall_grade: Letter grade (A to F)
            - tournament_ready: Whether team can be used in tournaments
            - legality: Pass/fail with specific issues
            - strengths: Top 3 things the team does well
            - weaknesses: Top 3 problems to address
            - one_fix: Single most impactful improvement to make

        Returns (detailed=False):
            - team_size: Number of Pokemon
            - pokemon: List of names
            - major_weaknesses: Types the team is weak to
            - unresisted_types: Types the team can't hit super effectively
            - speed_range: Slowest and fastest Pokemon
        """
        try:
            # If paste provided, parse it temporarily
            if paste:
                try:
                    parsed = parse_showdown_team(paste)
                    if not parsed:
                        return error_response(
                            ErrorCodes.PARSE_ERROR,
                            "Could not parse team from paste",
                            suggestions=["Check paste format - each Pokemon should be separated by a blank line"]
                        )
                    # Create temporary team for analysis
                    pokemon_names = [p.name for p in parsed]
                except ShowdownParseError as e:
                    return error_response(ErrorCodes.PARSE_ERROR, str(e))
            else:
                # Use current team
                if team_manager.size == 0:
                    return error_response(
                        ErrorCodes.TEAM_EMPTY,
                        "No team to check",
                        suggestions=[
                            "Add Pokemon with 'add_to_team' or 'add_pokemon_smart'",
                            "Import a team with 'import_showdown_team'",
                            "Provide a paste directly: full_team_check(paste='...')"
                        ]
                    )
                pokemon_names = [slot.pokemon.name for slot in team_manager.team.slots]

            # Quick summary mode - return early with minimal analysis
            if not detailed:
                if paste:
                    # For paste-only mode, we can only return names
                    return {
                        "team_size": len(pokemon_names),
                        "pokemon": pokemon_names,
                        "major_weaknesses": [],
                        "unresisted_types": [],
                        "speed_range": {},
                        "note": "Quick analysis on pastes is limited. Load team with import_showdown_team for full quick analysis."
                    }
                # Use the analyzer's quick summary
                return analyzer.get_quick_summary(team_manager.team)

            # Initialize scores
            scores = {
                "legality": 100,
                "coverage": 0,
                "speed_control": 0,
                "bulk": 0,
                "synergy": 0
            }
            issues = []
            strengths = []
            weaknesses = []

            # --- Legality Check ---
            config = get_regulation_config()
            reg = config.current_regulation
            restricted = config.get_restricted_pokemon(reg)
            banned = config.get_banned_pokemon(reg)
            rules = config.get_rules(reg)

            restricted_count = sum(1 for name in pokemon_names if name.lower() in restricted)
            banned_count = sum(1 for name in pokemon_names if name.lower() in banned)

            legality_issues = []
            if banned_count > 0:
                legality_issues.append(f"Contains {banned_count} banned Pokemon")
                scores["legality"] -= 50

            if restricted_count > rules.get("restricted_limit", 2):
                legality_issues.append(
                    f"Too many restricted Pokemon ({restricted_count}/{rules.get('restricted_limit', 2)})"
                )
                scores["legality"] -= 30

            if len(pokemon_names) > 6:
                legality_issues.append("More than 6 Pokemon")
                scores["legality"] -= 20

            # Check for duplicates (species clause)
            base_names = [name.split("-")[0].lower() for name in pokemon_names]
            if len(base_names) != len(set(base_names)):
                legality_issues.append("Duplicate species detected (species clause)")
                scores["legality"] -= 20

            is_legal = len(legality_issues) == 0

            if is_legal:
                strengths.append("Team is tournament legal")
            else:
                for issue in legality_issues:
                    weaknesses.append(issue)

            # --- Analysis (if we have current team loaded) ---
            if not paste and team_manager.size > 0:
                analysis = analyzer.get_summary(team_manager.team)

                # Check type coverage
                if "offensive_coverage" in analysis:
                    coverage = analysis["offensive_coverage"]
                    covered_types = sum(1 for v in coverage.values() if v > 0)
                    scores["coverage"] = min(100, covered_types * 6)  # 18 types max

                    if covered_types >= 15:
                        strengths.append(f"Excellent type coverage ({covered_types}/18 types)")
                    elif covered_types < 10:
                        weaknesses.append(f"Limited type coverage ({covered_types}/18 types)")

                # Check for shared weaknesses
                if "defensive_weaknesses" in analysis:
                    weak_types = [t for t, count in analysis["defensive_weaknesses"].items() if count >= 3]
                    if weak_types:
                        weaknesses.append(f"Shared weakness to: {', '.join(weak_types[:3])}")
                    else:
                        strengths.append("Good defensive type balance")

                # Speed tier check
                if "speed_tiers" in analysis:
                    speeds = analysis["speed_tiers"]
                    fast_count = sum(1 for s in speeds if s.get("speed", 0) >= 100)
                    slow_count = sum(1 for s in speeds if s.get("speed", 0) < 60)

                    if fast_count >= 2:
                        strengths.append(f"{fast_count} fast Pokemon for speed control")
                        scores["speed_control"] += 30
                    if slow_count >= 2:
                        strengths.append(f"{slow_count} Trick Room options")
                        scores["speed_control"] += 20

            # Calculate overall grade
            total_score = (
                scores["legality"] * 0.4 +
                scores["coverage"] * 0.2 +
                scores["speed_control"] * 0.2 +
                scores["synergy"] * 0.2
            )

            if total_score >= 90:
                grade = "A"
            elif total_score >= 80:
                grade = "B"
            elif total_score >= 70:
                grade = "C"
            elif total_score >= 60:
                grade = "D"
            else:
                grade = "F"

            # Determine single most impactful fix
            one_fix = None
            if not is_legal:
                one_fix = f"Fix legality: {legality_issues[0]}"
            elif weaknesses:
                one_fix = f"Address: {weaknesses[0]}"
            else:
                one_fix = "Team looks good! Consider testing against top meta threats."

            return {
                "overall_grade": grade,
                "tournament_ready": is_legal and len(pokemon_names) >= 4,
                "team_size": len(pokemon_names),
                "pokemon": pokemon_names,
                "legality": {
                    "valid": is_legal,
                    "regulation": reg,
                    "issues": legality_issues if legality_issues else ["None - team is legal"]
                },
                "strengths": strengths[:3] if strengths else ["Analysis requires loaded team"],
                "weaknesses": weaknesses[:3] if weaknesses else ["None identified"],
                "one_fix": one_fix,
                "scores": scores
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def import_and_analyze(paste: str, load_to_team: bool = True) -> dict:
        """
        Import a Showdown team paste and immediately analyze it.

        Combines import + legality check + coverage analysis + threat assessment
        into a single operation.

        Args:
            paste: Showdown format team paste (Pokemon separated by blank lines)
            load_to_team: If True, loads the team for further operations (default: True)

        Returns:
            - team: List of imported Pokemon with their builds
            - legality: Whether the team is tournament legal
            - coverage: Types the team can hit super-effectively
            - coverage_holes: Types the team struggles against
            - speed_structure: Speed tiers from fastest to slowest
            - suggested_improvements: Top 3 things to improve
        """
        try:
            # Parse the team
            try:
                parsed = parse_showdown_team(paste)
            except ShowdownParseError as e:
                return error_response(
                    ErrorCodes.PARSE_ERROR,
                    f"Failed to parse team: {e}",
                    suggestions=[
                        "Check that each Pokemon is separated by a blank line",
                        "Ensure the format matches Pokemon Showdown export format"
                    ]
                )

            if not parsed:
                return error_response(
                    ErrorCodes.PARSE_ERROR,
                    "No Pokemon found in paste",
                    suggestions=["Paste should contain at least 1 Pokemon in Showdown format"]
                )

            # Load to team if requested
            if load_to_team:
                team_manager.clear()
                for pokemon in parsed[:6]:  # Max 6
                    # Get Pokemon data from API
                    pokemon_data = await pokeapi.get_pokemon(pokemon.name)
                    if pokemon_data:
                        from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats

                        base_stats = BaseStats(
                            hp=pokemon_data["base_stats"]["hp"],
                            attack=pokemon_data["base_stats"]["attack"],
                            defense=pokemon_data["base_stats"]["defense"],
                            special_attack=pokemon_data["base_stats"]["special_attack"],
                            special_defense=pokemon_data["base_stats"]["special_defense"],
                            speed=pokemon_data["base_stats"]["speed"]
                        )

                        evs = EVSpread(
                            hp=pokemon.evs.get("hp", 0),
                            attack=pokemon.evs.get("atk", 0),
                            defense=pokemon.evs.get("def", 0),
                            special_attack=pokemon.evs.get("spa", 0),
                            special_defense=pokemon.evs.get("spd", 0),
                            speed=pokemon.evs.get("spe", 0)
                        )

                        try:
                            nature = Nature(pokemon.nature.lower()) if pokemon.nature else Nature.serious
                        except ValueError:
                            nature = Nature.serious

                        build = PokemonBuild(
                            name=pokemon_data["name"],
                            base_stats=base_stats,
                            types=pokemon_data.get("types", []),
                            nature=nature,
                            evs=evs,
                            ability=pokemon.ability,
                            item=pokemon.item,
                            moves=pokemon.moves[:4] if pokemon.moves else [],
                            tera_type=pokemon.tera_type,
                            level=50
                        )

                        team_manager.add(build)

            # Build team summary
            team_summary = []
            for pokemon in parsed[:6]:
                team_summary.append({
                    "name": pokemon.name,
                    "item": pokemon.item or "None",
                    "ability": pokemon.ability or "Unknown",
                    "nature": pokemon.nature or "Serious",
                    "tera_type": pokemon.tera_type,
                    "moves": pokemon.moves[:4] if pokemon.moves else []
                })

            # Legality check
            config = get_regulation_config()
            reg = config.current_regulation
            restricted = config.get_restricted_pokemon(reg)
            banned = config.get_banned_pokemon(reg)
            rules = config.get_rules(reg)

            pokemon_names = [p.name.lower() for p in parsed]
            restricted_count = sum(1 for name in pokemon_names if name in restricted)
            banned_list = [name for name in pokemon_names if name in banned]

            legality = {
                "valid": True,
                "regulation": reg,
                "issues": []
            }

            if banned_list:
                legality["valid"] = False
                legality["issues"].append(f"Banned Pokemon: {', '.join(banned_list)}")

            if restricted_count > rules.get("restricted_limit", 2):
                legality["valid"] = False
                legality["issues"].append(
                    f"Too many restricted ({restricted_count}/{rules.get('restricted_limit', 2)})"
                )

            # Items check
            items = [p.item for p in parsed if p.item]
            if len(items) != len(set(items)):
                legality["valid"] = False
                legality["issues"].append("Duplicate items (item clause violation)")

            # Coverage analysis (basic if team loaded)
            coverage_holes = []
            covered_types = []

            if load_to_team and team_manager.size > 0:
                analysis = analyzer.get_summary(team_manager.team)
                if "offensive_coverage" in analysis:
                    covered_types = [t for t, v in analysis["offensive_coverage"].items() if v > 0]
                    coverage_holes = [t for t, v in analysis["offensive_coverage"].items() if v == 0]

            # Speed structure
            speed_structure = []
            for pokemon in parsed[:6]:
                speed_ev = pokemon.evs.get("spe", 0)
                pokemon_data = await pokeapi.get_pokemon(pokemon.name)
                if pokemon_data:
                    base_speed = pokemon_data["base_stats"]["speed"]
                    # Approximate speed stat
                    nature_mod = 1.1 if pokemon.nature and pokemon.nature.lower() in ["jolly", "timid"] else 1.0
                    speed = int((((2 * base_speed + 31 + speed_ev // 4) * 50 // 100) + 5) * nature_mod)
                    speed_structure.append({
                        "pokemon": pokemon.name,
                        "speed": speed,
                        "speed_evs": speed_ev
                    })

            speed_structure.sort(key=lambda x: x["speed"], reverse=True)

            # Generate suggestions
            suggestions = []
            if not legality["valid"]:
                suggestions.append(f"Fix legality issues: {legality['issues'][0]}")
            if coverage_holes:
                suggestions.append(f"Add coverage for: {', '.join(coverage_holes[:3])}")
            if len(parsed) < 6:
                suggestions.append(f"Add {6 - len(parsed)} more Pokemon to complete the team")

            if not suggestions:
                suggestions.append("Team looks solid! Consider testing matchups against top meta threats.")

            return success_response(
                f"Imported {len(parsed)} Pokemon",
                team=team_summary,
                team_size=len(parsed),
                loaded_to_team=load_to_team,
                legality=legality,
                coverage={
                    "types_covered": len(covered_types),
                    "coverage_holes": coverage_holes[:5] if coverage_holes else ["Full coverage!"]
                },
                speed_structure=speed_structure,
                suggested_improvements=suggestions[:3]
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def fix_team_issues(paste: Optional[str] = None) -> dict:
        """
        Identify team issues and suggest specific fixes.

        Goes beyond just reporting problems - provides actionable solutions
        for each issue found.

        Args:
            paste: Optional Showdown paste. If not provided, uses current team.

        Returns:
            - issues: List of problems found with severity
            - fixes: Specific solution for each issue
            - priority_order: Which issues to fix first
        """
        try:
            # Get team data
            if paste:
                try:
                    parsed = parse_showdown_team(paste)
                    if not parsed:
                        return error_response(ErrorCodes.PARSE_ERROR, "No Pokemon found in paste")
                    pokemon_list = [{"name": p.name, "item": p.item} for p in parsed]
                except ShowdownParseError as e:
                    return error_response(ErrorCodes.PARSE_ERROR, str(e))
            else:
                if team_manager.size == 0:
                    return error_response(
                        ErrorCodes.TEAM_EMPTY,
                        "No team to analyze",
                        suggestions=["Load a team first with 'import_showdown_team'"]
                    )
                pokemon_list = [
                    {"name": slot.pokemon.name, "item": slot.pokemon.item}
                    for slot in team_manager.team.slots
                ]

            issues = []
            fixes = []

            # Check legality
            config = get_regulation_config()
            reg = config.current_regulation
            restricted = config.get_restricted_pokemon(reg)
            banned = config.get_banned_pokemon(reg)
            rules = config.get_rules(reg)

            pokemon_names = [p["name"].lower() for p in pokemon_list]

            # Banned Pokemon
            banned_found = [name for name in pokemon_names if name in banned]
            if banned_found:
                issues.append({
                    "type": "banned_pokemon",
                    "severity": "critical",
                    "description": f"Banned Pokemon: {', '.join(banned_found)}"
                })
                fixes.append({
                    "for_issue": "banned_pokemon",
                    "action": "Remove these Pokemon - they cannot be used in VGC",
                    "alternatives": "Consider similar Pokemon: Mythicals are banned, use regular legendaries instead"
                })

            # Restricted count
            restricted_found = [name for name in pokemon_names if name in restricted]
            restricted_limit = rules.get("restricted_limit", 2)
            if len(restricted_found) > restricted_limit:
                issues.append({
                    "type": "restricted_over_limit",
                    "severity": "critical",
                    "description": f"Too many restricted: {len(restricted_found)}/{restricted_limit}",
                    "restricted_pokemon": restricted_found
                })
                fixes.append({
                    "for_issue": "restricted_over_limit",
                    "action": f"Remove {len(restricted_found) - restricted_limit} restricted Pokemon",
                    "suggestion": f"Keep your 2 best restricted, consider which has better synergy with the team"
                })

            # Item clause
            items = [p["item"] for p in pokemon_list if p.get("item")]
            duplicate_items = [item for item in set(items) if items.count(item) > 1]
            if duplicate_items:
                issues.append({
                    "type": "duplicate_items",
                    "severity": "critical",
                    "description": f"Duplicate items: {', '.join(duplicate_items)}"
                })

                # Suggest alternatives
                common_items = [
                    "Choice Scarf", "Choice Band", "Choice Specs", "Life Orb",
                    "Focus Sash", "Assault Vest", "Leftovers", "Sitrus Berry",
                    "Safety Goggles", "Covert Cloak", "Clear Amulet"
                ]
                unused_items = [i for i in common_items if i.lower() not in [x.lower() for x in items]]

                fixes.append({
                    "for_issue": "duplicate_items",
                    "action": f"Replace duplicate {duplicate_items[0]} on one Pokemon",
                    "alternatives": f"Consider: {', '.join(unused_items[:4])}"
                })

            # Species clause
            base_names = [name.split("-")[0] for name in pokemon_names]
            duplicate_species = [name for name in set(base_names) if base_names.count(name) > 1]
            if duplicate_species:
                issues.append({
                    "type": "species_clause",
                    "severity": "critical",
                    "description": f"Duplicate species: {', '.join(duplicate_species)}"
                })
                fixes.append({
                    "for_issue": "species_clause",
                    "action": "Remove one copy of each duplicate species",
                    "suggestion": "You can only have one Pokemon from each evolutionary line"
                })

            # Team size
            if len(pokemon_list) < 6:
                issues.append({
                    "type": "incomplete_team",
                    "severity": "warning",
                    "description": f"Only {len(pokemon_list)}/6 Pokemon"
                })
                fixes.append({
                    "for_issue": "incomplete_team",
                    "action": f"Add {6 - len(pokemon_list)} more Pokemon",
                    "suggestion": "Use 'add_pokemon_smart' or 'suggest_team_completion' for suggestions"
                })

            # Priority order
            priority_order = []
            for issue in issues:
                if issue["severity"] == "critical":
                    priority_order.insert(0, issue["type"])
                else:
                    priority_order.append(issue["type"])

            if not issues:
                return success_response(
                    "No issues found! Team is ready for tournament play.",
                    team_size=len(pokemon_list),
                    regulation=reg,
                    status="legal"
                )

            return {
                "team_size": len(pokemon_list),
                "regulation": reg,
                "issue_count": len(issues),
                "issues": issues,
                "fixes": fixes,
                "priority_order": priority_order,
                "summary": f"Found {len([i for i in issues if i['severity'] == 'critical'])} critical and {len([i for i in issues if i['severity'] == 'warning'])} warning issues"
            }

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def add_pokemon_smart(
        pokemon_name: str,
        role: str = "auto"
    ) -> dict:
        """
        Add a Pokemon to the team with intelligent defaults.

        Automatically suggests nature, EVs, and moves based on:
        - The Pokemon's base stats and common competitive builds
        - What the current team needs (coverage, speed, bulk)
        - Popular Smogon usage data

        Args:
            pokemon_name: Name of the Pokemon to add
            role: Role hint - "sweeper", "wall", "support", "mixed", or "auto" (default)
                  "auto" will detect the best role based on base stats

        Returns:
            - Added Pokemon with suggested build
            - Reasoning for the suggested spread
            - Alternative options
        """
        try:
            # Get Pokemon data
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)

            if not pokemon_data:
                # Try fuzzy matching
                suggestions = suggest_pokemon_name(pokemon_name)
                if suggestions:
                    return error_response(
                        ErrorCodes.POKEMON_NOT_FOUND,
                        f"Pokemon '{pokemon_name}' not found",
                        suggestions=[f"Did you mean: {', '.join(suggestions)}?"]
                    )
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{pokemon_name}' not found",
                    suggestions=["Check spelling (use hyphens for forms: 'flutter-mane')"]
                )

            base_stats = pokemon_data["base_stats"]

            # Auto-detect role based on stats
            if role == "auto":
                atk = base_stats["attack"]
                spa = base_stats["special_attack"]
                speed = base_stats["speed"]
                hp = base_stats["hp"]
                defense = base_stats["defense"]
                spd = base_stats["special_defense"]

                bulk = (hp + defense + spd) / 3
                offense = max(atk, spa)

                if speed >= 100 and offense >= 100:
                    role = "sweeper"
                elif bulk >= 90 and offense < 80:
                    role = "wall"
                elif speed < 60 and offense >= 90:
                    role = "trick_room"
                elif hp >= 100 or (defense >= 90 and spd >= 90):
                    role = "bulky_offense"
                else:
                    role = "mixed"

            # Determine nature and EVs based on role
            is_physical = base_stats["attack"] > base_stats["special_attack"]

            role_builds = {
                "sweeper": {
                    "nature": "Jolly" if is_physical else "Timid",
                    "evs": {"atk" if is_physical else "spa": 252, "spe": 252, "hp": 4},
                    "description": "Max Speed and offensive stat for sweeping"
                },
                "wall": {
                    "nature": "Bold" if base_stats["defense"] > base_stats["special_defense"] else "Calm",
                    "evs": {"hp": 252, "def" if base_stats["defense"] > base_stats["special_defense"] else "spd": 252, "spe": 4},
                    "description": "Max HP and best defensive stat"
                },
                "bulky_offense": {
                    "nature": "Adamant" if is_physical else "Modest",
                    "evs": {"hp": 252, "atk" if is_physical else "spa": 252, "spe": 4},
                    "description": "Bulk with offensive pressure"
                },
                "trick_room": {
                    "nature": "Brave" if is_physical else "Quiet",
                    "evs": {"hp": 252, "atk" if is_physical else "spa": 252, "spd": 4},
                    "description": "Min Speed (0 IVs) with max offense for Trick Room"
                },
                "support": {
                    "nature": "Bold",
                    "evs": {"hp": 252, "def": 128, "spd": 128},
                    "description": "Balanced bulk for team support"
                },
                "mixed": {
                    "nature": "Naive" if base_stats["speed"] >= 80 else "Brave",
                    "evs": {"atk": 128, "spa": 128, "spe": 252},
                    "description": "Mixed attacking with Speed"
                }
            }

            build = role_builds.get(role, role_builds["mixed"])

            # Create the Pokemon build
            from vgc_mcp_core.models.pokemon import PokemonBuild, Nature, EVSpread, BaseStats

            ev_map = build["evs"]
            evs = EVSpread(
                hp=ev_map.get("hp", 0),
                attack=ev_map.get("atk", 0),
                defense=ev_map.get("def", 0),
                special_attack=ev_map.get("spa", 0),
                special_defense=ev_map.get("spd", 0),
                speed=ev_map.get("spe", 0)
            )

            try:
                nature = Nature(build["nature"].lower())
            except ValueError:
                nature = Nature.serious

            pokemon_build = PokemonBuild(
                name=pokemon_data["name"],
                base_stats=BaseStats(
                    hp=base_stats["hp"],
                    attack=base_stats["attack"],
                    defense=base_stats["defense"],
                    special_attack=base_stats["special_attack"],
                    special_defense=base_stats["special_defense"],
                    speed=base_stats["speed"]
                ),
                types=pokemon_data.get("types", []),
                nature=nature,
                evs=evs,
                ability=pokemon_data["abilities"][0] if pokemon_data.get("abilities") else None,
                level=50
            )

            # Check team status
            if team_manager.is_full:
                return error_response(
                    ErrorCodes.TEAM_FULL,
                    "Team is full (6 Pokemon)",
                    suggestions=[
                        "Use 'remove_from_team' to remove a Pokemon first",
                        "Use 'swap_pokemon' to replace a specific slot"
                    ],
                    suggested_build={
                        "pokemon": pokemon_data["name"],
                        "role": role,
                        "nature": build["nature"],
                        "evs": ev_map,
                        "reasoning": build["description"]
                    }
                )

            # Add to team
            success, message, data = team_manager.add(pokemon_build)

            if not success:
                return error_response(
                    ErrorCodes.SPECIES_CLAUSE if "species" in message.lower() else ErrorCodes.INTERNAL_ERROR,
                    message,
                    suggestions=["This Pokemon or its variant may already be on the team"]
                )

            return success_response(
                f"Added {pokemon_data['name']} to team",
                pokemon=pokemon_data["name"],
                slot=data.get("slot", team_manager.size),
                role=role,
                build={
                    "nature": build["nature"],
                    "evs": ev_map,
                    "ability": pokemon_build.ability,
                    "reasoning": build["description"]
                },
                team_size=team_manager.size,
                tip=f"Use 'update_pokemon' to customize the build, or 'get_usage_stats' to see common competitive sets"
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def suggest_ev_spread(
        pokemon_name: str,
        nature: str = "auto",
        outspeed_targets: list[str] = None,
        survive_hits: list[dict] = None,
        ko_targets: list[dict] = None,
        prioritize: str = "bulk"
    ) -> dict:
        """
        Design an optimal EV spread meeting multiple constraints in ONE call.

        This is the go-to tool for spread design. Instead of calling 5+ tools
        for speed, bulk, and damage calcs separately, this handles everything.

        Args:
            pokemon_name: Your Pokemon (e.g., "entei", "flutter-mane")
            nature: Nature to use, or "auto" to suggest based on constraints
            outspeed_targets: List of Pokemon names to outspeed (e.g., ["arcanine-hisui", "iron-bundle"])
            survive_hits: List of attacks to survive, each with:
                - attacker: Pokemon name
                - move: Move name
                - item: Optional attacker item (e.g., "choice-band")
                - ability: Optional attacker ability
            ko_targets: List of KOs to achieve, each with:
                - defender: Pokemon name
                - move: Move name
                - evs: Optional defender HP EVs (default 0)
            prioritize: "bulk" (maximize survival), "offense" (maximize damage), "speed" (maximize speed tier)

        Returns:
            - spread: Complete EV distribution
            - nature: Suggested nature
            - final_stats: Calculated stats at level 50
            - benchmarks_met: Which constraints are satisfied
            - benchmarks_failed: Which couldn't be met (with explanation)
            - summary: Ready-to-use spread string

        Example:
            suggest_ev_spread(
                pokemon_name="rillaboom",
                outspeed_targets=["amoonguss"],
                survive_hits=[{"attacker": "flutter-mane", "move": "moonblast"}],
                ko_targets=[{"defender": "palafin", "move": "wood-hammer"}]
            )
        """
        from vgc_mcp_core.models.pokemon import Nature, PokemonBuild, EVSpread, BaseStats, get_nature_modifier
        from vgc_mcp_core.models.move import MoveCategory
        from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp
        from vgc_mcp_core.calc.damage import calculate_damage
        from vgc_mcp_core.calc.modifiers import DamageModifiers

        try:
            # Get Pokemon data
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            if not pokemon_data:
                suggestions = suggest_pokemon_name(pokemon_name)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{pokemon_name}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            base_stats = pokemon_data["base_stats"]
            types = pokemon_data.get("types", [])

            # Determine nature
            is_physical = base_stats["attack"] > base_stats["special_attack"]
            if nature == "auto":
                if prioritize == "speed":
                    nature = "jolly" if is_physical else "timid"
                elif prioritize == "offense":
                    nature = "adamant" if is_physical else "modest"
                else:  # bulk
                    nature = "careful" if is_physical else "calm"

            try:
                parsed_nature = Nature(nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {nature}")

            # Initialize tracking
            benchmarks_met = []
            benchmarks_failed = []
            speed_evs_needed = 0
            hp_evs = 0
            def_evs = 0
            spd_evs = 0
            atk_evs = 0

            # 1. Calculate speed requirements
            if outspeed_targets:
                max_speed_needed = 0
                for target in outspeed_targets:
                    try:
                        target_data = await pokeapi.get_pokemon(target)
                        if target_data:
                            # Assume max speed investment
                            target_base_speed = target_data["base_stats"]["speed"]
                            target_speed = calculate_stat(target_base_speed, 31, 252, 50, 1.1)  # Assume +Speed nature

                            # Find EVs needed to outspeed
                            speed_mod = get_nature_modifier(parsed_nature, "speed")
                            for ev in EV_BREAKPOINTS_LV50:
                                my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                                if my_speed > target_speed:
                                    if ev > max_speed_needed:
                                        max_speed_needed = ev
                                    benchmarks_met.append(f"Outspeeds {target} ({my_speed} vs {target_speed})")
                                    break
                            else:
                                benchmarks_failed.append(f"Cannot outspeed {target} even with 252 Speed EVs")
                                max_speed_needed = 252
                    except Exception:
                        benchmarks_failed.append(f"Could not check speed vs {target}")

                speed_evs_needed = max_speed_needed

            remaining_evs = 508 - speed_evs_needed

            # 2. Calculate survival requirements
            if survive_hits and remaining_evs > 0:
                for hit in survive_hits:
                    attacker_name = hit.get("attacker", "")
                    move_name = hit.get("move", "")
                    attacker_item = hit.get("item")
                    attacker_ability = hit.get("ability")

                    try:
                        atk_data = await pokeapi.get_pokemon(attacker_name)
                        move = await pokeapi.get_move(move_name)

                        if atk_data and move:
                            is_phys = move.category == MoveCategory.PHYSICAL
                            atk_nature = Nature.adamant if is_phys else Nature.modest

                            # Create attacker
                            attacker = PokemonBuild(
                                name=attacker_name,
                                base_stats=BaseStats(**atk_data["base_stats"]),
                                types=atk_data.get("types", []),
                                nature=atk_nature,
                                evs=EVSpread(
                                    attack=252 if is_phys else 0,
                                    special_attack=0 if is_phys else 252
                                ),
                                ability=attacker_ability,
                                item=attacker_item
                            )

                            # Find bulk EVs needed
                            best_hp = 0
                            best_def = 0
                            survived = False

                            for hp_ev in EV_BREAKPOINTS_LV50:
                                if hp_ev > min(252, remaining_evs):
                                    break
                                def_ev = normalize_evs(min(252, remaining_evs - hp_ev)) if is_phys else 0
                                spd_ev = normalize_evs(min(252, remaining_evs - hp_ev)) if not is_phys else 0

                                defender = PokemonBuild(
                                    name=pokemon_name,
                                    base_stats=BaseStats(**base_stats),
                                    types=types,
                                    nature=parsed_nature,
                                    evs=EVSpread(hp=hp_ev, defense=def_ev, special_defense=spd_ev)
                                )

                                modifiers = DamageModifiers(
                                    is_doubles=True,
                                    attacker_ability=attacker_ability,
                                    attacker_item=attacker_item
                                )
                                result = calculate_damage(attacker, defender, move, modifiers)

                                if result.max_percent < 100:
                                    best_hp = hp_ev
                                    best_def = def_ev if is_phys else spd_ev
                                    survived = True
                                    benchmarks_met.append(
                                        f"Survives {attacker_name} {move_name} ({result.min_percent:.0f}-{result.max_percent:.0f}%)"
                                    )
                                    break

                            if survived:
                                hp_evs = max(hp_evs, best_hp)
                                if is_phys:
                                    def_evs = max(def_evs, best_def)
                                else:
                                    spd_evs = max(spd_evs, best_def)
                            else:
                                benchmarks_failed.append(f"Cannot survive {attacker_name} {move_name}")

                    except Exception as e:
                        benchmarks_failed.append(f"Error checking survival vs {attacker_name}: {str(e)}")

            # 3. Calculate KO requirements
            if ko_targets and remaining_evs > 0:
                for target in ko_targets:
                    defender_name = target.get("defender", "")
                    move_name = target.get("move", "")
                    defender_hp_evs = target.get("evs", 0)

                    try:
                        def_data = await pokeapi.get_pokemon(defender_name)
                        move = await pokeapi.get_move(move_name)

                        if def_data and move:
                            is_phys = move.category == MoveCategory.PHYSICAL

                            # Create defender
                            defender = PokemonBuild(
                                name=defender_name,
                                base_stats=BaseStats(**def_data["base_stats"]),
                                types=def_data.get("types", []),
                                nature=Nature.serious,
                                evs=EVSpread(hp=defender_hp_evs)
                            )

                            # Check if we can KO with remaining EVs
                            atk_ev_available = remaining_evs - hp_evs - def_evs - spd_evs
                            atk_ev = min(252, max(0, atk_ev_available))

                            attacker = PokemonBuild(
                                name=pokemon_name,
                                base_stats=BaseStats(**base_stats),
                                types=types,
                                nature=parsed_nature,
                                evs=EVSpread(
                                    attack=atk_ev if is_phys else 0,
                                    special_attack=0 if is_phys else atk_ev
                                )
                            )

                            modifiers = DamageModifiers(is_doubles=True)
                            result = calculate_damage(attacker, defender, move, modifiers)

                            if result.min_percent >= 100:
                                atk_evs = atk_ev
                                benchmarks_met.append(f"OHKOs {defender_name} with {move_name}")
                            elif result.max_percent >= 100:
                                atk_evs = atk_ev
                                benchmarks_met.append(f"Can OHKO {defender_name} with {move_name} (roll)")
                            else:
                                benchmarks_failed.append(
                                    f"Cannot OHKO {defender_name} with {move_name} ({result.max_percent:.0f}% max)"
                                )

                    except Exception as e:
                        benchmarks_failed.append(f"Error checking KO on {defender_name}: {str(e)}")

            # 4. Distribute remaining EVs (ensure multiples of 4)
            from vgc_mcp_core.config import normalize_evs, EV_BREAKPOINTS_LV50

            used_evs = speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs
            leftover = 508 - used_evs

            if leftover > 0:
                if prioritize == "bulk":
                    hp_evs = normalize_evs(min(252, hp_evs + leftover))
                    leftover = 508 - (speed_evs_needed + hp_evs + def_evs + spd_evs + atk_evs)
                    if leftover > 0:
                        # Split remaining between defenses, keeping multiples of 4
                        def_share = normalize_evs(leftover // 2)
                        spd_share = normalize_evs(leftover - def_share)
                        def_evs = normalize_evs(min(252, def_evs + def_share))
                        spd_evs = normalize_evs(min(252, spd_evs + spd_share))
                elif prioritize == "offense":
                    atk_evs = normalize_evs(min(252, atk_evs + leftover))
                else:  # speed
                    speed_evs_needed = normalize_evs(min(252, speed_evs_needed + leftover))

            # 5. Calculate final stats
            speed_mod = get_nature_modifier(parsed_nature, "speed")
            atk_mod = get_nature_modifier(parsed_nature, "attack")
            spa_mod = get_nature_modifier(parsed_nature, "special_attack")
            def_mod = get_nature_modifier(parsed_nature, "defense")
            spd_mod = get_nature_modifier(parsed_nature, "special_defense")

            final_stats = {
                "hp": calculate_hp(base_stats["hp"], 31, hp_evs, 50),
                "attack": calculate_stat(base_stats["attack"], 31, atk_evs if is_physical else 0, 50, atk_mod),
                "defense": calculate_stat(base_stats["defense"], 31, def_evs, 50, def_mod),
                "special_attack": calculate_stat(base_stats["special_attack"], 31, 0 if is_physical else atk_evs, 50, spa_mod),
                "special_defense": calculate_stat(base_stats["special_defense"], 31, spd_evs, 50, spd_mod),
                "speed": calculate_stat(base_stats["speed"], 31, speed_evs_needed, 50, speed_mod)
            }

            spread = {
                "hp": hp_evs,
                "atk": atk_evs if is_physical else 0,
                "def": def_evs,
                "spa": 0 if is_physical else atk_evs,
                "spd": spd_evs,
                "spe": speed_evs_needed,
                "total": hp_evs + atk_evs + def_evs + spd_evs + speed_evs_needed
            }

            summary = (
                f"{pokemon_name.title()} @ {nature.title()}: "
                f"{hp_evs} HP / {atk_evs if is_physical else 0} Atk / {def_evs} Def / "
                f"{0 if is_physical else atk_evs} SpA / {spd_evs} SpD / {speed_evs_needed} Spe"
            )

            return success_response(
                f"Designed spread for {pokemon_name}",
                pokemon=pokemon_name,
                nature=nature,
                spread=spread,
                final_stats=final_stats,
                benchmarks_met=benchmarks_met if benchmarks_met else ["No specific benchmarks requested"],
                benchmarks_failed=benchmarks_failed if benchmarks_failed else [],
                all_constraints_met=len(benchmarks_failed) == 0,
                summary=summary
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def quick_damage_check(
        attacker: str,
        defender: str,
        move: str,
        attacker_item: str = None,
        attacker_ability: str = None,
        defender_hp_evs: int = 0,
        defender_def_evs: int = 0,
        is_doubles: bool = True
    ) -> dict:
        """
        Quick damage calculation with smart defaults - ONE call for damage info.

        Uses competitive defaults (252 offensive EVs, optimal nature) so you
        don't need to specify everything manually.

        Args:
            attacker: Attacking Pokemon name
            defender: Defending Pokemon name
            move: Move name to use
            attacker_item: Optional item (e.g., "life-orb", "choice-band")
            attacker_ability: Optional ability (auto-detected if not specified)
            defender_hp_evs: Defender's HP EVs (default 0)
            defender_def_evs: Defender's Def/SpD EVs (default 0)
            is_doubles: True for doubles spread move reduction (default True)

        Returns:
            - damage_range: Min-max damage
            - percent_range: Min-max as percentage
            - survives: Whether defender survives
            - ko_chance: "Guaranteed OHKO", "Possible OHKO", "2HKO", "3HKO+", "Never KO"
            - what_changes_outcome: Items/abilities that would flip the result
        """
        from vgc_mcp_core.models.pokemon import Nature, PokemonBuild, EVSpread, BaseStats
        from vgc_mcp_core.models.move import MoveCategory
        from vgc_mcp_core.calc.damage import calculate_damage
        from vgc_mcp_core.calc.modifiers import DamageModifiers

        try:
            # Get Pokemon data
            atk_data = await pokeapi.get_pokemon(attacker)
            def_data = await pokeapi.get_pokemon(defender)
            move_data = await pokeapi.get_move(move)

            if not atk_data:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Attacker '{attacker}' not found")
            if not def_data:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Defender '{defender}' not found")
            if not move_data:
                return error_response(ErrorCodes.MOVE_NOT_FOUND, f"Move '{move}' not found")

            is_physical = move_data.category == MoveCategory.PHYSICAL

            # Auto-detect ability if not provided
            if not attacker_ability:
                abilities = await pokeapi.get_pokemon_abilities(attacker)
                if abilities:
                    attacker_ability = abilities[0].lower().replace(" ", "-")

            # Create attacker with competitive defaults
            atk_nature = Nature.adamant if is_physical else Nature.modest
            atk_build = PokemonBuild(
                name=attacker,
                base_stats=BaseStats(**atk_data["base_stats"]),
                types=atk_data.get("types", []),
                nature=atk_nature,
                evs=EVSpread(
                    attack=252 if is_physical else 0,
                    special_attack=0 if is_physical else 252
                ),
                ability=attacker_ability,
                item=attacker_item
            )

            # Create defender
            def_build = PokemonBuild(
                name=defender,
                base_stats=BaseStats(**def_data["base_stats"]),
                types=def_data.get("types", []),
                nature=Nature.serious,
                evs=EVSpread(
                    hp=defender_hp_evs,
                    defense=defender_def_evs if is_physical else 0,
                    special_defense=0 if is_physical else defender_def_evs
                )
            )

            # Calculate damage
            modifiers = DamageModifiers(
                is_doubles=is_doubles,
                attacker_item=attacker_item,
                attacker_ability=attacker_ability
            )
            result = calculate_damage(atk_build, def_build, move_data, modifiers)

            # Determine KO chance
            if result.min_percent >= 100:
                ko_chance = "Guaranteed OHKO"
            elif result.max_percent >= 100:
                ko_chance = "Possible OHKO (roll)"
            elif result.max_percent >= 50:
                ko_chance = "2HKO"
            elif result.max_percent >= 33:
                ko_chance = "3HKO"
            else:
                ko_chance = "4HKO+"

            # Suggest what could change outcome
            suggestions = []
            if result.max_percent < 100 and not attacker_item:
                suggestions.append("Life Orb would add ~30% damage")
                suggestions.append("Choice Band/Specs would add ~50% damage")
            if result.min_percent >= 100:
                suggestions.append("Focus Sash would let defender survive")

            return success_response(
                f"{attacker} vs {defender}",
                attacker=attacker,
                attacker_ability=attacker_ability,
                attacker_item=attacker_item,
                defender=defender,
                move=move,
                move_type=move_data.type,
                base_power=move_data.power,
                damage_range=result.damage_range,
                percent_range=f"{format_percent(result.min_percent)}% - {format_percent(result.max_percent)}%",
                survives=result.max_percent < 100,
                ko_chance=ko_chance,
                defender_hp=result.defender_hp,
                what_changes_outcome=suggestions if suggestions else ["No major items would change this outcome"]
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def analyze_speed_matchup(
        my_pokemon: str,
        opponent_pokemon: str,
        my_nature: str = "jolly",
        my_speed_evs: int = 252,
        opponent_nature: str = "jolly",
        opponent_speed_evs: int = 252,
        include_scenarios: list[str] = None
    ) -> dict:
        """
        Compare speed between two Pokemon across various scenarios.

        Answers: "Who's faster?" in normal play, Tailwind, Trick Room, etc.

        Args:
            my_pokemon: Your Pokemon name
            opponent_pokemon: Opponent's Pokemon name
            my_nature: Your Pokemon's nature (default: jolly)
            my_speed_evs: Your speed EVs (default: 252)
            opponent_nature: Opponent's nature (default: jolly)
            opponent_speed_evs: Opponent's speed EVs (default: 252)
            include_scenarios: List of scenarios to check:
                - "tailwind" (2x speed)
                - "trick_room" (slower goes first)
                - "paralysis" (0.5x speed)
                - "icy_wind" (-1 speed stage = 0.67x)
                - "choice_scarf" (1.5x speed)

        Returns:
            - base_comparison: Who's faster normally
            - scenarios: Result for each requested scenario
            - evs_to_outspeed: Minimum EVs needed to outspeed (if behind)
        """
        from vgc_mcp_core.models.pokemon import Nature, get_nature_modifier
        from vgc_mcp_core.calc.stats import calculate_stat

        try:
            my_data = await pokeapi.get_pokemon(my_pokemon)
            opp_data = await pokeapi.get_pokemon(opponent_pokemon)

            if not my_data:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Pokemon '{my_pokemon}' not found")
            if not opp_data:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Pokemon '{opponent_pokemon}' not found")

            try:
                my_nat = Nature(my_nature.lower())
                opp_nat = Nature(opponent_nature.lower())
            except ValueError as e:
                return error_response(ErrorCodes.INVALID_NATURE, str(e))

            my_speed_mod = get_nature_modifier(my_nat, "speed")
            opp_speed_mod = get_nature_modifier(opp_nat, "speed")

            my_speed = calculate_stat(my_data["base_stats"]["speed"], 31, my_speed_evs, 50, my_speed_mod)
            opp_speed = calculate_stat(opp_data["base_stats"]["speed"], 31, opponent_speed_evs, 50, opp_speed_mod)

            results = {
                "my_pokemon": my_pokemon,
                "my_speed": my_speed,
                "opponent_pokemon": opponent_pokemon,
                "opponent_speed": opp_speed,
                "normal": {
                    "faster": my_pokemon if my_speed > opp_speed else (opponent_pokemon if opp_speed > my_speed else "Speed tie"),
                    "difference": abs(my_speed - opp_speed)
                }
            }

            scenarios = include_scenarios or ["tailwind", "trick_room", "paralysis"]
            scenario_results = {}

            # Helper to determine faster Pokemon with proper tie handling
            def get_faster(speed_a: int, speed_b: int, name_a: str, name_b: str) -> str:
                if speed_a > speed_b:
                    return name_a
                elif speed_b > speed_a:
                    return name_b
                else:
                    return "Speed tie (50/50)"

            for scenario in scenarios:
                if scenario == "tailwind":
                    my_tw = my_speed * 2
                    opp_tw = opp_speed * 2
                    scenario_results["my_tailwind"] = {
                        "my_speed": my_tw,
                        "opponent_speed": opp_speed,
                        "faster": get_faster(my_tw, opp_speed, my_pokemon, opponent_pokemon)
                    }
                    scenario_results["opponent_tailwind"] = {
                        "my_speed": my_speed,
                        "opponent_speed": opp_tw,
                        "faster": get_faster(my_speed, opp_tw, my_pokemon, opponent_pokemon)
                    }
                elif scenario == "trick_room":
                    # In Trick Room, slower moves first - but ties are still 50/50
                    if my_speed == opp_speed:
                        faster_in_tr = "Speed tie (50/50)"
                    elif my_speed > opp_speed:
                        faster_in_tr = opponent_pokemon
                    else:
                        faster_in_tr = my_pokemon
                    scenario_results["trick_room"] = {
                        "faster": faster_in_tr,
                        "note": "Slower Pokemon moves first in Trick Room"
                    }
                elif scenario == "paralysis":
                    my_para = int(my_speed * 0.5)
                    opp_para = int(opp_speed * 0.5)
                    scenario_results["my_paralysis"] = {
                        "my_speed": my_para,
                        "faster": get_faster(my_para, opp_speed, my_pokemon, opponent_pokemon)
                    }
                    scenario_results["opponent_paralysis"] = {
                        "opponent_speed": opp_para,
                        "faster": get_faster(my_speed, opp_para, my_pokemon, opponent_pokemon)
                    }
                elif scenario == "icy_wind":
                    from vgc_mcp_core.calc.speed_control import apply_stage_modifier
                    opp_icy = apply_stage_modifier(opp_speed, -1)
                    scenario_results["after_icy_wind"] = {
                        "opponent_speed": opp_icy,
                        "faster": get_faster(my_speed, opp_icy, my_pokemon, opponent_pokemon)
                    }
                elif scenario == "choice_scarf":
                    my_scarf = int(my_speed * 1.5)
                    opp_scarf = int(opp_speed * 1.5)
                    scenario_results["my_choice_scarf"] = {
                        "my_speed": my_scarf,
                        "faster": get_faster(my_scarf, opp_speed, my_pokemon, opponent_pokemon)
                    }
                    scenario_results["opponent_choice_scarf"] = {
                        "opponent_speed": opp_scarf,
                        "faster": get_faster(my_speed, opp_scarf, my_pokemon, opponent_pokemon)
                    }

            results["scenarios"] = scenario_results

            # Calculate EVs needed to outspeed
            if my_speed <= opp_speed:
                for ev in EV_BREAKPOINTS_LV50:
                    test_speed = calculate_stat(my_data["base_stats"]["speed"], 31, ev, 50, my_speed_mod)
                    if test_speed > opp_speed:
                        results["evs_to_outspeed"] = ev
                        break
                else:
                    results["evs_to_outspeed"] = "Cannot outspeed with current nature"

            return success_response(
                f"Speed comparison: {my_pokemon} vs {opponent_pokemon}",
                **results
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def check_team_vs_threat(
        threat_pokemon: str,
        threat_nature: str = "modest",
        threat_offensive_evs: int = 252,
        threat_item: str = None,
        threat_ability: str = None,
        check_moves: list[str] = None
    ) -> dict:
        """
        Check how your current team handles a specific threat.

        Calculates damage from the threat to each team member and vice versa.

        Args:
            threat_pokemon: The threatening Pokemon to check against
            threat_nature: Threat's nature (default: modest)
            threat_offensive_evs: Threat's offensive EVs (default: 252)
            threat_item: Threat's item (e.g., "choice-specs")
            threat_ability: Threat's ability (auto-detected if not specified)
            check_moves: Specific moves to check (auto-detects common moves if not specified)

        Returns:
            - threat_info: The threat's stats
            - team_matchups: For each team member:
                - survives: Can they survive the threat's attack?
                - can_ko: Can they KO the threat?
                - verdict: "Checks", "Counters", "Loses to", "Mutual KO"
            - safe_switches: Team members that can switch in safely
            - answers: Team members that can KO the threat
        """
        from vgc_mcp_core.models.pokemon import Nature, PokemonBuild, EVSpread, BaseStats
        from vgc_mcp_core.calc.damage import calculate_damage
        from vgc_mcp_core.calc.modifiers import DamageModifiers

        try:
            if team_manager.size == 0:
                return error_response(
                    ErrorCodes.TEAM_EMPTY,
                    "No team loaded",
                    suggestions=["Load a team with 'import_showdown_team' first"]
                )

            threat_data = await pokeapi.get_pokemon(threat_pokemon)
            if not threat_data:
                return error_response(ErrorCodes.POKEMON_NOT_FOUND, f"Threat '{threat_pokemon}' not found")

            # Auto-detect ability
            if not threat_ability:
                abilities = await pokeapi.get_pokemon_abilities(threat_pokemon)
                if abilities:
                    threat_ability = abilities[0].lower().replace(" ", "-")

            try:
                threat_nat = Nature(threat_nature.lower())
            except ValueError:
                threat_nat = Nature.modest

            is_physical = threat_data["base_stats"]["attack"] > threat_data["base_stats"]["special_attack"]

            threat_build = PokemonBuild(
                name=threat_pokemon,
                base_stats=BaseStats(**threat_data["base_stats"]),
                types=threat_data.get("types", []),
                nature=threat_nat,
                evs=EVSpread(
                    attack=threat_offensive_evs if is_physical else 0,
                    special_attack=0 if is_physical else threat_offensive_evs
                ),
                ability=threat_ability,
                item=threat_item
            )

            # Get common moves if not specified
            if not check_moves:
                # Use first STAB move as default
                check_moves = []
                threat_types = threat_data.get("types", [])
                common_moves = {
                    "fire": "flamethrower",
                    "water": "hydro-pump",
                    "grass": "energy-ball",
                    "electric": "thunderbolt",
                    "psychic": "psychic",
                    "fairy": "moonblast",
                    "dark": "dark-pulse",
                    "ghost": "shadow-ball",
                    "dragon": "draco-meteor",
                    "fighting": "close-combat",
                    "ground": "earthquake",
                    "rock": "rock-slide",
                    "ice": "ice-beam",
                    "steel": "iron-head",
                    "poison": "sludge-bomb",
                    "flying": "air-slash",
                    "bug": "bug-buzz",
                    "normal": "body-slam"
                }
                for t in threat_types:
                    if t.lower() in common_moves:
                        check_moves.append(common_moves[t.lower()])

            if not check_moves:
                check_moves = ["tackle"]  # Fallback

            team_matchups = []
            safe_switches = []
            answers = []

            for slot in team_manager.team.slots:
                pokemon = slot.pokemon
                matchup = {
                    "pokemon": pokemon.name,
                    "survives_hits": [],
                    "can_ko_with": []
                }

                # Check if team member survives threat's attacks
                survives_all = True
                for move_name in check_moves[:2]:  # Check top 2 moves
                    try:
                        move = await pokeapi.get_move(move_name)
                        if move:
                            modifiers = DamageModifiers(
                                is_doubles=True,
                                attacker_ability=threat_ability,
                                attacker_item=threat_item
                            )
                            result = calculate_damage(threat_build, pokemon, move, modifiers)

                            survives = result.max_percent < 100
                            matchup["survives_hits"].append({
                                "move": move_name,
                                "damage": f"{result.min_percent:.0f}-{result.max_percent:.0f}%",
                                "survives": survives
                            })
                            if not survives:
                                survives_all = False
                    except Exception:
                        pass

                # Check if team member can KO the threat
                can_ko = False
                if pokemon.moves:
                    for move_name in pokemon.moves[:2]:
                        try:
                            move = await pokeapi.get_move(move_name.lower().replace(" ", "-"))
                            if move:
                                modifiers = DamageModifiers(is_doubles=True)
                                result = calculate_damage(pokemon, threat_build, move, modifiers)

                                if result.max_percent >= 100:
                                    matchup["can_ko_with"].append({
                                        "move": move_name,
                                        "damage": f"{result.min_percent:.0f}-{result.max_percent:.0f}%"
                                    })
                                    can_ko = True
                        except Exception:
                            pass

                # Determine verdict
                if survives_all and can_ko:
                    matchup["verdict"] = "Counters"
                    safe_switches.append(pokemon.name)
                    answers.append(pokemon.name)
                elif survives_all:
                    matchup["verdict"] = "Checks (survives but can't KO)"
                    safe_switches.append(pokemon.name)
                elif can_ko:
                    matchup["verdict"] = "Revenge kills (can KO but doesn't survive)"
                    answers.append(pokemon.name)
                else:
                    matchup["verdict"] = "Loses to"

                team_matchups.append(matchup)

            return success_response(
                f"Team vs {threat_pokemon}",
                threat=threat_pokemon,
                threat_ability=threat_ability,
                threat_item=threat_item,
                moves_checked=check_moves[:2],
                team_matchups=team_matchups,
                safe_switches=safe_switches if safe_switches else ["No safe switch-ins"],
                answers=answers if answers else ["No answers - consider adding a counter"],
                summary=f"{len(safe_switches)} safe switches, {len(answers)} answers"
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def design_pokemon_for_role(
        pokemon_name: str,
        role: str = "auto",
        speed_benchmark: str = None,
        survive_hit: dict = None,
        item: str = None
    ) -> dict:
        """
        Design a complete Pokemon build for a specific role in ONE call.

        Automatically determines nature, EVs, suggested moves, and item
        based on the Pokemon's stats and the desired role.

        Args:
            pokemon_name: Pokemon to build
            role: Desired role:
                - "auto": Detect from stats
                - "sweeper": Fast + offensive
                - "bulky_attacker": Offensive with HP investment
                - "wall": Maximum bulk
                - "support": Bulk with some speed
                - "trick_room": Minimum speed, max offense
            speed_benchmark: Optional Pokemon to outspeed (e.g., "iron-bundle")
            survive_hit: Optional attack to survive:
                - attacker: Pokemon name
                - move: Move name
            item: Suggested item (auto-suggested if not provided)

        Returns:
            - build: Complete recommended build
            - nature: Optimal nature with reasoning
            - evs: Full EV spread
            - item: Suggested item
            - moves: Suggested moves (from common competitive usage)
            - final_stats: Stats at level 50
        """
        from vgc_mcp_core.models.pokemon import Nature, EVSpread, get_nature_modifier
        from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp

        try:
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            if not pokemon_data:
                suggestions = suggest_pokemon_name(pokemon_name)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{pokemon_name}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            base_stats = pokemon_data["base_stats"]
            types = pokemon_data.get("types", [])
            abilities = await pokeapi.get_pokemon_abilities(pokemon_name)

            # Auto-detect role
            if role == "auto":
                atk = base_stats["attack"]
                spa = base_stats["special_attack"]
                speed = base_stats["speed"]
                hp = base_stats["hp"]
                defense = (base_stats["defense"] + base_stats["special_defense"]) / 2

                if speed >= 100 and max(atk, spa) >= 100:
                    role = "sweeper"
                elif speed < 50 and max(atk, spa) >= 90:
                    role = "trick_room"
                elif hp >= 90 and defense >= 85:
                    role = "wall"
                elif hp >= 80 and max(atk, spa) >= 90:
                    role = "bulky_attacker"
                else:
                    role = "support"

            is_physical = base_stats["attack"] > base_stats["special_attack"]

            # Define role templates
            role_templates = {
                "sweeper": {
                    "nature": "jolly" if is_physical else "timid",
                    "evs": {"spe": 252, "atk" if is_physical else "spa": 252, "hp": 4},
                    "item": "life-orb" if not item else item,
                    "reasoning": "Max Speed and offense for sweeping"
                },
                "bulky_attacker": {
                    "nature": "adamant" if is_physical else "modest",
                    "evs": {"hp": 252, "atk" if is_physical else "spa": 252, "spe": 4},
                    "item": "assault-vest" if not is_physical else "choice-band",
                    "reasoning": "Bulk with offensive pressure"
                },
                "wall": {
                    "nature": "bold" if base_stats["defense"] >= base_stats["special_defense"] else "calm",
                    "evs": {"hp": 252, "def": 252 if base_stats["defense"] >= base_stats["special_defense"] else 0,
                            "spd": 0 if base_stats["defense"] >= base_stats["special_defense"] else 252, "spe": 4},
                    "item": "leftovers",
                    "reasoning": "Maximum bulk for defensive presence"
                },
                "support": {
                    "nature": "bold",
                    "evs": {"hp": 252, "def": 128, "spd": 128},
                    "item": "sitrus-berry",
                    "reasoning": "Balanced bulk for team support"
                },
                "trick_room": {
                    "nature": "brave" if is_physical else "quiet",
                    "evs": {"hp": 252, "atk" if is_physical else "spa": 252, "spd": 4},
                    "item": "life-orb",
                    "reasoning": "Minimum Speed (0 IVs), max offense for Trick Room"
                }
            }

            template = role_templates.get(role, role_templates["sweeper"])

            # Override with speed benchmark if provided
            evs = template["evs"].copy()
            speed_evs_needed = evs.get("spe", 0)

            if speed_benchmark:
                bench_data = await pokeapi.get_pokemon(speed_benchmark)
                if bench_data:
                    bench_speed = calculate_stat(bench_data["base_stats"]["speed"], 31, 252, 50, 1.1)
                    try:
                        parsed_nature = Nature(template["nature"].lower())
                        speed_mod = get_nature_modifier(parsed_nature, "speed")
                        for ev in EV_BREAKPOINTS_LV50:
                            my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                            if my_speed > bench_speed:
                                speed_evs_needed = ev
                                break
                    except ValueError:
                        pass

                evs["spe"] = speed_evs_needed

            # Calculate final stats
            try:
                parsed_nature = Nature(template["nature"].lower())
            except ValueError:
                parsed_nature = Nature.serious

            hp_evs = evs.get("hp", 0)
            atk_evs = evs.get("atk", 0)
            def_evs = evs.get("def", 0)
            spa_evs = evs.get("spa", 0)
            spd_evs = evs.get("spd", 0)
            spe_evs = evs.get("spe", 0)

            final_stats = {
                "hp": calculate_hp(base_stats["hp"], 31, hp_evs, 50),
                "attack": calculate_stat(base_stats["attack"], 31, atk_evs, 50, get_nature_modifier(parsed_nature, "attack")),
                "defense": calculate_stat(base_stats["defense"], 31, def_evs, 50, get_nature_modifier(parsed_nature, "defense")),
                "special_attack": calculate_stat(base_stats["special_attack"], 31, spa_evs, 50, get_nature_modifier(parsed_nature, "special_attack")),
                "special_defense": calculate_stat(base_stats["special_defense"], 31, spd_evs, 50, get_nature_modifier(parsed_nature, "special_defense")),
                "speed": calculate_stat(base_stats["speed"], 31, spe_evs, 50, get_nature_modifier(parsed_nature, "speed"))
            }

            # Suggest moves based on type
            suggested_moves = []
            stab_moves = {
                "fire": ["flamethrower", "heat-wave", "fire-blast"],
                "water": ["hydro-pump", "scald", "surf"],
                "grass": ["energy-ball", "leaf-storm", "giga-drain"],
                "electric": ["thunderbolt", "volt-switch", "thunder"],
                "psychic": ["psychic", "psyshock", "expanding-force"],
                "fairy": ["moonblast", "dazzling-gleam", "play-rough"],
                "dark": ["dark-pulse", "knock-off", "foul-play"],
                "ghost": ["shadow-ball", "shadow-sneak", "hex"],
                "dragon": ["draco-meteor", "dragon-pulse", "dragon-claw"],
                "fighting": ["close-combat", "aura-sphere", "drain-punch"],
                "ground": ["earthquake", "earth-power", "high-horsepower"],
                "rock": ["rock-slide", "stone-edge", "power-gem"],
                "ice": ["ice-beam", "blizzard", "freeze-dry"],
                "steel": ["iron-head", "flash-cannon", "steel-beam"],
                "poison": ["sludge-bomb", "gunk-shot", "poison-jab"],
                "flying": ["air-slash", "hurricane", "brave-bird"],
                "bug": ["bug-buzz", "u-turn", "x-scissor"],
                "normal": ["body-slam", "hyper-voice", "facade"]
            }

            for t in types:
                if t.lower() in stab_moves:
                    moves = stab_moves[t.lower()]
                    if is_physical:
                        suggested_moves.append(moves[-1] if len(moves) > 2 else moves[0])
                    else:
                        suggested_moves.append(moves[0])

            suggested_moves.append("protect")  # Always suggest Protect for VGC

            return success_response(
                f"Designed {role} build for {pokemon_name}",
                pokemon=pokemon_name,
                role=role,
                types=types,
                ability=abilities[0] if abilities else "Unknown",
                nature=template["nature"],
                nature_reasoning=template["reasoning"],
                evs={
                    "HP": hp_evs,
                    "Atk": atk_evs,
                    "Def": def_evs,
                    "SpA": spa_evs,
                    "SpD": spd_evs,
                    "Spe": spe_evs
                },
                item=item or template["item"],
                suggested_moves=suggested_moves[:4],
                final_stats=final_stats,
                speed_benchmark_met=f"Outspeeds {speed_benchmark}" if speed_benchmark else None,
                showdown_format=(
                    f"{pokemon_name.title()}\n"
                    f"Ability: {abilities[0] if abilities else 'Unknown'}\n"
                    f"EVs: {hp_evs} HP / {atk_evs} Atk / {def_evs} Def / {spa_evs} SpA / {spd_evs} SpD / {spe_evs} Spe\n"
                    f"{template['nature'].title()} Nature\n"
                    f"- {suggested_moves[0].replace('-', ' ').title() if suggested_moves else 'Move 1'}\n"
                    f"- {suggested_moves[1].replace('-', ' ').title() if len(suggested_moves) > 1 else 'Move 2'}\n"
                    f"- {suggested_moves[2].replace('-', ' ').title() if len(suggested_moves) > 2 else 'Move 3'}\n"
                    f"- Protect"
                )
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def calc_damage_vs_smogon_sets(
        my_pokemon: str,
        my_nature: str,
        my_hp_evs: int = 0,
        my_atk_evs: int = 0,
        my_def_evs: int = 0,
        my_spa_evs: int = 0,
        my_spd_evs: int = 0,
        my_spe_evs: int = 0,
        my_item: str = None,
        my_ability: str = None,
        my_tera_type: str = None,
        opponent_pokemon: str = "",
        move: str = "",
        direction: str = "from",
        num_sets: int = 3
    ) -> dict:
        """
        Calculate damage using YOUR exact spread vs the top Smogon sets.

        This answers questions like:
        - "How much damage does my Entei (252 HP/116 Def) take from the top 3 Urshifu sets?"
        - "Can my Flutter Mane OHKO the common Incineroar spreads?"

        Args:
            my_pokemon: Your Pokemon name
            my_nature: Your Pokemon's nature
            my_hp_evs: Your HP EVs
            my_atk_evs: Your Attack EVs
            my_def_evs: Your Defense EVs
            my_spa_evs: Your Sp. Atk EVs
            my_spd_evs: Your Sp. Def EVs
            my_spe_evs: Your Speed EVs
            my_item: Your item (optional)
            my_ability: Your ability (auto-detected if not specified)
            my_tera_type: Your Tera type if active (changes your defensive typing)
            opponent_pokemon: The opponent Pokemon to check against
            move: The move being used
            direction: "from" (opponent attacks you) or "to" (you attack opponent)
            num_sets: Number of top Smogon sets to check (default 3)

        Returns:
            - your_build: Your Pokemon's stats
            - opponent_sets: Top N Smogon sets with usage %
            - damage_results: Damage calc for each set
            - summary: Quick overview of survival/KO across sets
        """
        from vgc_mcp_core.models.pokemon import Nature, PokemonBuild, EVSpread, BaseStats, get_nature_modifier
        from vgc_mcp_core.models.move import MoveCategory
        from vgc_mcp_core.calc.damage import calculate_damage
        from vgc_mcp_core.calc.modifiers import DamageModifiers
        from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp

        try:
            # Validate inputs
            if not opponent_pokemon:
                return error_response(ErrorCodes.VALIDATION_ERROR, "opponent_pokemon is required")
            if not move:
                return error_response(ErrorCodes.VALIDATION_ERROR, "move is required")
            if direction not in ["from", "to"]:
                return error_response(ErrorCodes.VALIDATION_ERROR, "direction must be 'from' or 'to'")

            # Get my Pokemon data
            try:
                my_data = await pokeapi.get_pokemon(my_pokemon)
                my_base_stats = await pokeapi.get_base_stats(my_pokemon)
            except Exception:
                suggestions = suggest_pokemon_name(my_pokemon)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{my_pokemon}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            # Get opponent Pokemon data
            try:
                opp_data = await pokeapi.get_pokemon(opponent_pokemon)
                opp_base_stats = await pokeapi.get_base_stats(opponent_pokemon)
            except Exception:
                suggestions = suggest_pokemon_name(opponent_pokemon)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{opponent_pokemon}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            # Get move data
            move_data = await pokeapi.get_move(move)
            if not move_data:
                return error_response(ErrorCodes.MOVE_NOT_FOUND, f"Move '{move}' not found")

            # Parse my nature
            try:
                parsed_nature = Nature(my_nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {my_nature}")

            # Auto-detect my ability if not provided
            if not my_ability:
                abilities = await pokeapi.get_pokemon_abilities(my_pokemon)
                if abilities:
                    my_ability = abilities[0].lower().replace(" ", "-")

            # Build my Pokemon
            my_types = await pokeapi.get_pokemon_types(my_pokemon)
            # If Tera active, defensive typing changes
            defensive_types = [my_tera_type] if my_tera_type else my_types

            my_build = PokemonBuild(
                name=my_pokemon,
                base_stats=my_base_stats,
                types=defensive_types,
                nature=parsed_nature,
                evs=EVSpread(
                    hp=my_hp_evs,
                    attack=my_atk_evs,
                    defense=my_def_evs,
                    special_attack=my_spa_evs,
                    special_defense=my_spd_evs,
                    speed=my_spe_evs
                ),
                item=my_item,
                ability=my_ability,
                tera_type=my_tera_type
            )

            # Calculate my final stats for display
            my_final_stats = {
                "hp": calculate_hp(my_base_stats.hp, 31, my_hp_evs, 50),
                "attack": calculate_stat(my_base_stats.attack, 31, my_atk_evs, 50, get_nature_modifier(parsed_nature, "attack")),
                "defense": calculate_stat(my_base_stats.defense, 31, my_def_evs, 50, get_nature_modifier(parsed_nature, "defense")),
                "special_attack": calculate_stat(my_base_stats.special_attack, 31, my_spa_evs, 50, get_nature_modifier(parsed_nature, "special_attack")),
                "special_defense": calculate_stat(my_base_stats.special_defense, 31, my_spd_evs, 50, get_nature_modifier(parsed_nature, "special_defense")),
                "speed": calculate_stat(my_base_stats.speed, 31, my_spe_evs, 50, get_nature_modifier(parsed_nature, "speed"))
            }

            # Get opponent's Smogon usage data
            opp_usage = await smogon.get_pokemon_usage(opponent_pokemon)
            if not opp_usage:
                return error_response(
                    ErrorCodes.API_ERROR,
                    f"No Smogon usage data for {opponent_pokemon}",
                    suggestions=["This Pokemon may not have enough usage in the current format"]
                )

            opp_spreads = opp_usage.get("spreads", [])[:num_sets]
            opp_items = opp_usage.get("items", {})
            opp_abilities = opp_usage.get("abilities", {})
            opp_tera_types = opp_usage.get("tera_types", {})

            if not opp_spreads:
                return error_response(
                    ErrorCodes.API_ERROR,
                    f"No spread data available for {opponent_pokemon}"
                )

            # Get most common item and ability for opponent
            top_item = list(opp_items.keys())[0] if opp_items else None
            top_ability = list(opp_abilities.keys())[0] if opp_abilities else None
            top_tera = list(opp_tera_types.keys())[0] if opp_tera_types else None

            # Normalize item/ability names
            if top_item:
                top_item = top_item.lower().replace(" ", "-")
            if top_ability:
                top_ability = top_ability.lower().replace(" ", "-")

            opp_types = await pokeapi.get_pokemon_types(opponent_pokemon)
            is_physical = move_data.category == MoveCategory.PHYSICAL

            damage_results = []
            survives_count = 0
            ko_count = 0

            # Check for special ability interactions
            warnings = []

            # Check if opponent is Urshifu (has Unseen Fist)
            normalized_opp = opponent_pokemon.lower().replace(" ", "-")
            if normalized_opp in ("urshifu", "urshifu-single-strike", "urshifu-rapid-strike"):
                warnings.append("⚠️ Urshifu has Unseen Fist - contact moves bypass Protect!")

            # Calculate my Life Orb recoil if I have one
            my_life_orb_recoil = 0
            if my_item and my_item.lower().replace(" ", "-") == "life-orb":
                my_life_orb_recoil = my_final_stats["hp"] // 10

            for i, spread in enumerate(opp_spreads):
                if "evs" not in spread:
                    continue

                spread_evs = spread["evs"]
                spread_nature_str = spread.get("nature", "Serious")

                try:
                    spread_nature = Nature(spread_nature_str.lower())
                except ValueError:
                    spread_nature = Nature.serious

                # Build opponent with this spread
                opp_build = PokemonBuild(
                    name=opponent_pokemon,
                    base_stats=opp_base_stats,
                    types=opp_types,
                    nature=spread_nature,
                    evs=EVSpread(
                        hp=spread_evs.get("hp", 0),
                        attack=spread_evs.get("attack", 0),
                        defense=spread_evs.get("defense", 0),
                        special_attack=spread_evs.get("special_attack", 0),
                        special_defense=spread_evs.get("special_defense", 0),
                        speed=spread_evs.get("speed", 0)
                    ),
                    item=top_item,
                    ability=top_ability
                )

                # Set up modifiers based on direction
                if direction == "from":
                    # Opponent attacks me
                    attacker = opp_build
                    defender = my_build
                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attacker_item=top_item,
                        attacker_ability=top_ability,
                        defender_tera_type=my_tera_type,
                        defender_tera_active=my_tera_type is not None
                    )
                else:
                    # I attack opponent
                    attacker = my_build
                    defender = opp_build
                    modifiers = DamageModifiers(
                        is_doubles=True,
                        attacker_item=my_item,
                        attacker_ability=my_ability,
                        tera_type=my_tera_type,
                        tera_active=my_tera_type is not None
                    )

                result = calculate_damage(attacker, defender, move_data, modifiers)

                # Determine outcome
                result_entry = {
                    "set_rank": i + 1,
                    "usage": f"{spread.get('usage', 0)}%",
                    "nature": spread_nature_str,
                    "evs": f"{spread_evs.get('hp', 0)} HP / {spread_evs.get('attack', 0)} Atk / {spread_evs.get('defense', 0)} Def / {spread_evs.get('special_attack', 0)} SpA / {spread_evs.get('special_defense', 0)} SpD / {spread_evs.get('speed', 0)} Spe",
                    "damage_range": result.damage_range,
                    "percent_range": f"{format_percent(result.min_percent)}% - {format_percent(result.max_percent)}%",
                }

                if direction == "from":
                    # I'm being attacked
                    survives = result.max_percent < 100
                    hp_remaining_min = my_final_stats["hp"] - result.max_damage
                    hp_remaining_max = my_final_stats["hp"] - result.min_damage

                    # Calculate survival after my Life Orb recoil (if I attack back with Extreme Speed, etc.)
                    if my_life_orb_recoil > 0 and survives:
                        hp_after_attack_then_lo = hp_remaining_min - my_life_orb_recoil
                        survives_after_lo = hp_after_attack_then_lo > 0

                        result_entry["hp_remaining"] = f"{hp_remaining_min}-{hp_remaining_max} HP"
                        result_entry["life_orb_recoil"] = f"-{my_life_orb_recoil} HP ({(my_life_orb_recoil / my_final_stats['hp'] * 100):.0f}%)"

                        if survives and survives_after_lo:
                            outcome = f"Survives (HP: {hp_remaining_min}-{hp_remaining_max}, after LO: {hp_after_attack_then_lo}+)"
                        elif survives and not survives_after_lo:
                            outcome = f"⚠️ Survives hit but DIES to Life Orb recoil! (HP: {hp_remaining_min} -> {hp_after_attack_then_lo})"
                            survives = False  # Don't count as survival
                        else:
                            outcome = "KO'd"
                    else:
                        outcome = "Survives" if survives else "KO'd"
                        if survives:
                            result_entry["hp_remaining"] = f"{hp_remaining_min}-{hp_remaining_max} HP"

                    if survives:
                        survives_count += 1
                else:
                    # I'm attacking
                    kos = result.min_percent >= 100
                    possible_ko = result.max_percent >= 100
                    if kos:
                        ko_count += 1
                        outcome = "Guaranteed OHKO"
                    elif possible_ko:
                        ko_count += 0.5  # Partial credit for roll
                        outcome = "Possible OHKO (roll)"
                    else:
                        outcome = f"{result.max_percent:.0f}% max"

                    # Add Life Orb recoil note for offensive calcs
                    if my_life_orb_recoil > 0:
                        result_entry["life_orb_recoil"] = f"-{my_life_orb_recoil} HP per attack"

                result_entry["outcome"] = outcome
                damage_results.append(result_entry)

            # Build summary
            if direction == "from":
                summary = f"Survives {survives_count}/{len(damage_results)} common sets"
                if survives_count == len(damage_results):
                    verdict = "Safe - survives all common sets"
                elif survives_count == 0:
                    verdict = "Danger - KO'd by all common sets"
                else:
                    verdict = f"Mixed - survives {survives_count}/{len(damage_results)}"
            else:
                summary = f"KOs {ko_count}/{len(damage_results)} common sets"
                if ko_count >= len(damage_results):
                    verdict = "Offensive threat - OHKOs all common sets"
                elif ko_count == 0:
                    verdict = "Not a KO threat - consider boosting item"
                else:
                    verdict = f"Situational - KOs {ko_count}/{len(damage_results)}"

            # Build response
            response_data = {
                "your_pokemon": my_pokemon,
                "your_build": {
                    "nature": my_nature,
                    "evs": {
                        "HP": my_hp_evs,
                        "Atk": my_atk_evs,
                        "Def": my_def_evs,
                        "SpA": my_spa_evs,
                        "SpD": my_spd_evs,
                        "Spe": my_spe_evs
                    },
                    "item": my_item,
                    "ability": my_ability,
                    "tera_type": my_tera_type,
                    "final_stats": my_final_stats
                },
                "opponent_pokemon": opponent_pokemon,
                "opponent_common_item": top_item,
                "opponent_common_ability": top_ability,
                "opponent_common_tera": top_tera,
                "move": move,
                "move_type": move_data.type,
                "move_power": move_data.power,
                "direction": "Opponent attacks you" if direction == "from" else "You attack opponent",
                "damage_vs_sets": damage_results,
                "summary": summary,
                "verdict": verdict,
                "meta_info": opp_usage.get("_meta", {})
            }

            # Add warnings if any
            if warnings:
                response_data["warnings"] = warnings

            # Add Life Orb info if relevant
            if my_life_orb_recoil > 0:
                response_data["your_life_orb_recoil"] = {
                    "damage": my_life_orb_recoil,
                    "percent": f"{(my_life_orb_recoil / my_final_stats['hp'] * 100):.0f}%",
                    "note": "Life Orb costs 10% HP per attacking move"
                }

            return success_response(
                f"{my_pokemon} vs {opponent_pokemon} ({direction} {move})",
                **response_data
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def optimize_spread(
        pokemon_name: str,
        current_nature: str = None,
        current_hp_evs: int = 0,
        current_atk_evs: int = 0,
        current_def_evs: int = 0,
        current_spa_evs: int = 0,
        current_spd_evs: int = 0,
        current_spe_evs: int = 0,
        target_speed: int = None,
        outspeed_pokemon: str = None,
        outspeed_pokemon_nature: str = "jolly",
        outspeed_pokemon_evs: int = 252,
        survive_pokemon: str = None,
        survive_move: str = None,
        survive_pokemon_nature: str = "adamant",
        survive_pokemon_evs: int = 252,
        survive_pokemon_item: str = None,
        survive_pokemon_ability: str = None,
        use_smogon_spreads: bool = False,
        smogon_spread_count: int = 3,
        max_damage_percent: float = None,
        target_nko: int = None,
        target_hp_stat: int = None,
        target_atk_stat: int = None,
        target_def_stat: int = None,
        target_spa_stat: int = None,
        target_spd_stat: int = None
    ) -> dict:
        """
        Optimize or fix an EV spread to meet specific stat targets.

        Give me your current spread (optional) and tell me what you need:
        - A specific speed stat to hit
        - A Pokemon to outspeed
        - An attack to survive (100% survival)
        - A max damage % to take (e.g., "take max 80% from this attack")
        - A target N-HKO (e.g., "be 2HKO'd by this attack" = survive 1 hit)
        - Any target stat value

        I'll reverse-engineer the exact EVs and nature needed.

        Args:
            pokemon_name: Your Pokemon
            current_nature: Current nature (optional, will suggest optimal if not provided)
            current_*_evs: Current EV spread (optional, used as starting point)
            target_speed: Exact speed stat you want to hit
            outspeed_pokemon: Pokemon you want to outspeed
            outspeed_pokemon_nature: Target's nature (default: jolly)
            outspeed_pokemon_evs: Target's speed EVs (default: 252)
            survive_pokemon: Attacker to check against
            survive_move: Move to check against
            survive_pokemon_nature: Attacker's nature (default: adamant, ignored if use_smogon_spreads=True)
            survive_pokemon_evs: Attacker's offensive EVs (default: 252, ignored if use_smogon_spreads=True)
            survive_pokemon_item: Attacker's item (e.g., "choice-specs") - REQUIRED if use_smogon_spreads=True
            survive_pokemon_ability: Attacker's ability
            use_smogon_spreads: If True, fetch top spreads from Smogon and calc against each
            smogon_spread_count: Number of top Smogon spreads to check (default: 3)
            max_damage_percent: Max damage % to take (e.g., 80.0 = take max 80%)
            target_nko: Target N-HKO (2 = be 2HKO'd = survive 1 hit, 3 = survive 2 hits)
            target_hp_stat: Exact HP stat you want
            target_atk_stat: Exact Attack stat you want
            target_def_stat: Exact Defense stat you want
            target_spa_stat: Exact Sp. Atk stat you want
            target_spd_stat: Exact Sp. Def stat you want

        Returns:
            - optimized_spread: New EV distribution
            - optimized_nature: Recommended nature
            - changes_from_current: What changed and why
            - final_stats: Resulting stats at level 50
            - benchmarks_hit: Targets achieved
            - ev_savings: EVs saved compared to current spread
            - smogon_calcs: (if use_smogon_spreads) Damage from each top spread

        Examples:
            # Survive a hit (100% survival)
            optimize_spread(pokemon_name="entei", survive_pokemon="urshifu", survive_move="surging-strikes")

            # Take max 80% from an attack
            optimize_spread(pokemon_name="entei", survive_pokemon="urshifu", survive_move="surging-strikes", max_damage_percent=80)

            # Be 2HKO'd (survive 1 hit guaranteed)
            optimize_spread(pokemon_name="entei", survive_pokemon="flutter-mane", survive_move="moonblast", target_nko=2)

            # Survive Choice Specs Flutter Mane using top 3 Smogon spreads
            optimize_spread(
                pokemon_name="entei",
                survive_pokemon="flutter-mane",
                survive_move="power-gem",
                survive_pokemon_item="choice-specs",
                use_smogon_spreads=True
            )
        """
        from vgc_mcp_core.models.pokemon import Nature, PokemonBuild, EVSpread, BaseStats, get_nature_modifier
        from vgc_mcp_core.models.move import MoveCategory
        from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp
        from vgc_mcp_core.calc.damage import calculate_damage
        from vgc_mcp_core.calc.modifiers import DamageModifiers

        try:
            # Get Pokemon data
            pokemon_data = await pokeapi.get_pokemon(pokemon_name)
            if not pokemon_data:
                suggestions = suggest_pokemon_name(pokemon_name)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{pokemon_name}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            base_stats = pokemon_data["base_stats"]
            types = pokemon_data.get("types", [])
            is_physical = base_stats["attack"] > base_stats["special_attack"]

            # Import EV normalization helper
            from vgc_mcp_core.config import normalize_evs, EV_BREAKPOINTS_LV50

            # Normalize input EVs to valid multiples of 4
            current_hp_evs = normalize_evs(current_hp_evs)
            current_atk_evs = normalize_evs(current_atk_evs)
            current_def_evs = normalize_evs(current_def_evs)
            current_spa_evs = normalize_evs(current_spa_evs)
            current_spd_evs = normalize_evs(current_spd_evs)
            current_spe_evs = normalize_evs(current_spe_evs)

            # Track current spread
            current_spread = {
                "hp": current_hp_evs,
                "atk": current_atk_evs,
                "def": current_def_evs,
                "spa": current_spa_evs,
                "spd": current_spd_evs,
                "spe": current_spe_evs,
                "total": current_hp_evs + current_atk_evs + current_def_evs + current_spa_evs + current_spd_evs + current_spe_evs
            }

            # Optimization results
            optimized = {
                "hp": 0,
                "atk": 0,
                "def": 0,
                "spa": 0,
                "spd": 0,
                "spe": 0
            }
            benchmarks_hit = []
            changes = []

            # Determine best nature
            suggested_nature = current_nature
            if not suggested_nature:
                # Auto-suggest based on targets
                if target_speed or outspeed_pokemon:
                    suggested_nature = "jolly" if is_physical else "timid"
                elif survive_pokemon:
                    suggested_nature = "careful" if is_physical else "calm"
                else:
                    suggested_nature = "adamant" if is_physical else "modest"

            try:
                parsed_nature = Nature(suggested_nature.lower())
            except ValueError:
                return error_response(ErrorCodes.INVALID_NATURE, f"Invalid nature: {suggested_nature}")

            # 1. Handle speed targeting
            speed_evs_needed = 0

            if target_speed:
                # Reverse-engineer EVs for target speed
                speed_mod = get_nature_modifier(parsed_nature, "speed")
                for ev in EV_BREAKPOINTS_LV50:
                    calc_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                    if calc_speed >= target_speed:
                        speed_evs_needed = ev
                        actual_speed = calc_speed
                        benchmarks_hit.append(f"Hits {actual_speed} Speed (target: {target_speed})")
                        break
                else:
                    # Can't reach target, try bulk-first natures (prefer bulk boost over speed boost)
                    for nature_try in ["bold", "calm", "impish", "careful", "jolly", "timid"]:
                        try:
                            test_nature = Nature(nature_try)
                            test_mod = get_nature_modifier(test_nature, "speed")
                            for ev in EV_BREAKPOINTS_LV50:
                                calc_speed = calculate_stat(base_stats["speed"], 31, ev, 50, test_mod)
                                if calc_speed >= target_speed:
                                    speed_evs_needed = ev
                                    suggested_nature = nature_try
                                    parsed_nature = test_nature
                                    actual_speed = calc_speed
                                    benchmarks_hit.append(f"Hits {actual_speed} Speed with {nature_try.title()} nature")
                                    changes.append(f"Changed nature to {nature_try.title()} to reach speed target")
                                    break
                            if speed_evs_needed > 0:
                                break
                        except ValueError:
                            pass

            elif outspeed_pokemon:
                # Calculate target's speed and find EVs to outspeed
                try:
                    target_data = await pokeapi.get_pokemon(outspeed_pokemon)
                    if target_data:
                        target_nature = Nature(outspeed_pokemon_nature.lower())
                        target_speed_mod = get_nature_modifier(target_nature, "speed")
                        target_speed_stat = calculate_stat(
                            target_data["base_stats"]["speed"], 31, outspeed_pokemon_evs, 50, target_speed_mod
                        )

                        speed_mod = get_nature_modifier(parsed_nature, "speed")
                        for ev in EV_BREAKPOINTS_LV50:
                            my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, speed_mod)
                            if my_speed > target_speed_stat:
                                speed_evs_needed = ev
                                benchmarks_hit.append(f"Outspeeds {outspeed_pokemon} ({my_speed} vs {target_speed_stat})")
                                break
                        else:
                            # Try bulk-first natures (prefer bulk boost over speed boost)
                            for nature_try in ["bold", "calm", "impish", "careful", "jolly", "timid"]:
                                try:
                                    test_nature = Nature(nature_try)
                                    test_mod = get_nature_modifier(test_nature, "speed")
                                    for ev in EV_BREAKPOINTS_LV50:
                                        my_speed = calculate_stat(base_stats["speed"], 31, ev, 50, test_mod)
                                        if my_speed > target_speed_stat:
                                            speed_evs_needed = ev
                                            suggested_nature = nature_try
                                            parsed_nature = test_nature
                                            benchmarks_hit.append(f"Outspeeds {outspeed_pokemon} with {nature_try.title()} ({my_speed} vs {target_speed_stat})")
                                            changes.append(f"Changed nature to {nature_try.title()} to outspeed")
                                            break
                                    if speed_evs_needed > 0:
                                        break
                                except ValueError:
                                    pass
                            if speed_evs_needed == 0:
                                benchmarks_hit.append(f"Cannot outspeed {outspeed_pokemon} ({target_speed_stat}) - max 252 Speed EVs")
                                speed_evs_needed = 252
                except Exception as e:
                    benchmarks_hit.append(f"Error checking {outspeed_pokemon}: {str(e)}")

            optimized["spe"] = speed_evs_needed

            # 2. Handle survival/damage targeting
            remaining_evs = 508 - speed_evs_needed
            smogon_calcs = []  # Results from each Smogon spread

            if survive_pokemon and survive_move:
                try:
                    atk_data = await pokeapi.get_pokemon(survive_pokemon)
                    move = await pokeapi.get_move(survive_move)

                    if atk_data and move:
                        is_phys_move = move.category == MoveCategory.PHYSICAL
                        atk_types = await pokeapi.get_pokemon_types(survive_pokemon)

                        # Build list of attacker spreads to check against
                        attacker_spreads = []

                        if use_smogon_spreads:
                            # Fetch top spreads from Smogon
                            try:
                                smogon_data = await smogon.get_pokemon_usage(survive_pokemon)
                                if smogon_data and "spreads" in smogon_data:
                                    # spreads is a list of pre-parsed dicts from get_pokemon_usage
                                    spreads_list = smogon_data["spreads"][:smogon_spread_count]

                                    for spread in spreads_list:
                                        try:
                                            nature_str = spread.get("nature", "modest")
                                            evs = spread.get("evs", {})
                                            usage_pct = spread.get("usage", 0)

                                            atk_nature = Nature(nature_str.lower())
                                            attacker_spreads.append({
                                                "nature": atk_nature,
                                                "evs": EVSpread(
                                                    hp=evs.get("hp", 0),
                                                    attack=evs.get("attack", 0),
                                                    defense=evs.get("defense", 0),
                                                    special_attack=evs.get("special_attack", 0),
                                                    special_defense=evs.get("special_defense", 0),
                                                    speed=evs.get("speed", 0)
                                                ),
                                                "usage": usage_pct,
                                                "description": spread.get("spread_string", f"{nature_str}") + f" ({usage_pct:.1f}%)"
                                            })
                                        except (ValueError, KeyError):
                                            continue

                                if not attacker_spreads:
                                    benchmarks_hit.append(f"No Smogon spreads found for {survive_pokemon}, using default")
                            except Exception as e:
                                benchmarks_hit.append(f"Could not fetch Smogon data: {str(e)}, using default")

                        # If no Smogon spreads or not using them, use the provided/default spread
                        if not attacker_spreads:
                            atk_nature = Nature(survive_pokemon_nature.lower())
                            attacker_spreads.append({
                                "nature": atk_nature,
                                "evs": EVSpread(
                                    attack=survive_pokemon_evs if is_phys_move else 0,
                                    special_attack=0 if is_phys_move else survive_pokemon_evs
                                ),
                                "usage": 100.0,
                                "description": f"{survive_pokemon_nature.title()} {survive_pokemon_evs} {'Atk' if is_phys_move else 'SpA'}"
                            })

                        # Determine target threshold based on parameters
                        if max_damage_percent is not None:
                            target_max_damage = max_damage_percent
                            target_description = f"take max {max_damage_percent:.0f}%"
                        elif target_nko is not None:
                            target_max_damage = 100.0 / target_nko
                            target_description = f"be {target_nko}HKO'd (max {target_max_damage:.1f}% per hit)"
                        else:
                            target_max_damage = 99.9
                            target_description = "survive"

                        # Find minimum bulk to survive the WORST case (highest damage spread)
                        best_hp = 0
                        best_def = 0
                        target_met = False
                        worst_result = None
                        worst_spread_desc = ""

                        for hp_ev in EV_BREAKPOINTS_LV50:
                            if hp_ev > min(252, remaining_evs):
                                break
                            for def_ev in EV_BREAKPOINTS_LV50:
                                if def_ev > min(252, remaining_evs - hp_ev):
                                    break
                                if hp_ev + def_ev > remaining_evs:
                                    break

                                defender = PokemonBuild(
                                    name=pokemon_name,
                                    base_stats=BaseStats(**base_stats),
                                    types=types,
                                    nature=parsed_nature,
                                    evs=EVSpread(
                                        hp=hp_ev,
                                        defense=def_ev if is_phys_move else 0,
                                        special_defense=0 if is_phys_move else def_ev
                                    )
                                )

                                # Check against ALL attacker spreads
                                all_survive = True
                                max_damage_seen = 0
                                worst_spread_for_this_ev = ""

                                for atk_spread in attacker_spreads:
                                    attacker = PokemonBuild(
                                        name=survive_pokemon,
                                        base_stats=BaseStats(**atk_data["base_stats"]),
                                        types=atk_types,
                                        nature=atk_spread["nature"],
                                        evs=atk_spread["evs"],
                                        ability=survive_pokemon_ability,
                                        item=survive_pokemon_item
                                    )

                                    modifiers = DamageModifiers(
                                        is_doubles=True,
                                        attacker_ability=survive_pokemon_ability,
                                        attacker_item=survive_pokemon_item
                                    )
                                    result = calculate_damage(attacker, defender, move, modifiers)

                                    if result.max_percent > target_max_damage:
                                        all_survive = False
                                    if result.max_percent > max_damage_seen:
                                        max_damage_seen = result.max_percent
                                        worst_spread_for_this_ev = atk_spread["description"]
                                        worst_result = result

                                if all_survive:
                                    best_hp = hp_ev
                                    best_def = def_ev
                                    target_met = True
                                    worst_spread_desc = worst_spread_for_this_ev
                                    break
                            if target_met:
                                break

                        # Record damage calcs from each spread at the optimized EVs
                        if target_met or best_hp > 0 or best_def > 0:
                            final_defender = PokemonBuild(
                                name=pokemon_name,
                                base_stats=BaseStats(**base_stats),
                                types=types,
                                nature=parsed_nature,
                                evs=EVSpread(
                                    hp=best_hp if target_met else 252,
                                    defense=(best_def if is_phys_move else 0) if target_met else (252 if is_phys_move else 0),
                                    special_defense=(0 if is_phys_move else best_def) if target_met else (0 if is_phys_move else 252)
                                )
                            )

                            for atk_spread in attacker_spreads:
                                attacker = PokemonBuild(
                                    name=survive_pokemon,
                                    base_stats=BaseStats(**atk_data["base_stats"]),
                                    types=atk_types,
                                    nature=atk_spread["nature"],
                                    evs=atk_spread["evs"],
                                    ability=survive_pokemon_ability,
                                    item=survive_pokemon_item
                                )

                                modifiers = DamageModifiers(
                                    is_doubles=True,
                                    attacker_ability=survive_pokemon_ability,
                                    attacker_item=survive_pokemon_item
                                )
                                result = calculate_damage(attacker, final_defender, move, modifiers)

                                smogon_calcs.append({
                                    "spread": atk_spread["description"],
                                    "usage": atk_spread["usage"],
                                    "damage_range": f"{result.min_damage}-{result.max_damage}",
                                    "percent_range": f"{format_percent(result.min_percent)}-{format_percent(result.max_percent)}%",
                                    "survives": result.max_percent < 100,
                                    "ko_chance": result.ko_chance
                                })

                        if target_met:
                            optimized["hp"] = best_hp
                            if is_phys_move:
                                optimized["def"] = best_def
                            else:
                                optimized["spd"] = best_def

                            item_note = f" with {survive_pokemon_item}" if survive_pokemon_item else ""
                            spread_note = f" (vs {len(attacker_spreads)} spreads)" if use_smogon_spreads and len(attacker_spreads) > 1 else ""
                            if max_damage_percent is not None:
                                benchmarks_hit.append(
                                    f"Takes max {worst_result.max_percent:.0f}% from {survive_pokemon} {survive_move}{item_note}{spread_note}"
                                )
                            elif target_nko is not None:
                                benchmarks_hit.append(
                                    f"Is {target_nko}HKO'd by {survive_pokemon} {survive_move}{item_note}{spread_note}"
                                )
                            else:
                                benchmarks_hit.append(
                                    f"Survives {survive_pokemon} {survive_move}{item_note}{spread_note} ({worst_result.min_percent:.0f}-{worst_result.max_percent:.0f}%)"
                                )
                        else:
                            if max_damage_percent is not None:
                                benchmarks_hit.append(f"Cannot limit {survive_pokemon} {survive_move} to {max_damage_percent:.0f}% with available EVs")
                            elif target_nko is not None:
                                benchmarks_hit.append(f"Cannot be {target_nko}HKO'd by {survive_pokemon} {survive_move} with available EVs")
                            else:
                                benchmarks_hit.append(f"Cannot survive {survive_pokemon} {survive_move} with available EVs")

                except Exception as e:
                    benchmarks_hit.append(f"Error checking survival: {str(e)}")

            # 3. Handle target stat values
            if target_hp_stat:
                for ev in EV_BREAKPOINTS_LV50:
                    hp = calculate_hp(base_stats["hp"], 31, ev, 50)
                    if hp >= target_hp_stat:
                        optimized["hp"] = max(optimized["hp"], ev)
                        benchmarks_hit.append(f"Hits {hp} HP (target: {target_hp_stat})")
                        break

            if target_atk_stat:
                atk_mod = get_nature_modifier(parsed_nature, "attack")
                for ev in EV_BREAKPOINTS_LV50:
                    atk = calculate_stat(base_stats["attack"], 31, ev, 50, atk_mod)
                    if atk >= target_atk_stat:
                        optimized["atk"] = max(optimized["atk"], ev)
                        benchmarks_hit.append(f"Hits {atk} Attack (target: {target_atk_stat})")
                        break

            if target_def_stat:
                def_mod = get_nature_modifier(parsed_nature, "defense")
                for ev in EV_BREAKPOINTS_LV50:
                    defense = calculate_stat(base_stats["defense"], 31, ev, 50, def_mod)
                    if defense >= target_def_stat:
                        optimized["def"] = max(optimized["def"], ev)
                        benchmarks_hit.append(f"Hits {defense} Defense (target: {target_def_stat})")
                        break

            if target_spa_stat:
                spa_mod = get_nature_modifier(parsed_nature, "special_attack")
                for ev in EV_BREAKPOINTS_LV50:
                    spa = calculate_stat(base_stats["special_attack"], 31, ev, 50, spa_mod)
                    if spa >= target_spa_stat:
                        optimized["spa"] = max(optimized["spa"], ev)
                        benchmarks_hit.append(f"Hits {spa} Sp. Atk (target: {target_spa_stat})")
                        break

            if target_spd_stat:
                spd_mod = get_nature_modifier(parsed_nature, "special_defense")
                for ev in EV_BREAKPOINTS_LV50:
                    spd = calculate_stat(base_stats["special_defense"], 31, ev, 50, spd_mod)
                    if spd >= target_spd_stat:
                        optimized["spd"] = max(optimized["spd"], ev)
                        benchmarks_hit.append(f"Hits {spd} Sp. Def (target: {target_spd_stat})")
                        break

            # 4. Calculate final stats
            speed_mod = get_nature_modifier(parsed_nature, "speed")
            atk_mod = get_nature_modifier(parsed_nature, "attack")
            spa_mod = get_nature_modifier(parsed_nature, "special_attack")
            def_mod = get_nature_modifier(parsed_nature, "defense")
            spd_mod = get_nature_modifier(parsed_nature, "special_defense")

            optimized["total"] = sum([optimized["hp"], optimized["atk"], optimized["def"],
                                       optimized["spa"], optimized["spd"], optimized["spe"]])

            final_stats = {
                "hp": calculate_hp(base_stats["hp"], 31, optimized["hp"], 50),
                "attack": calculate_stat(base_stats["attack"], 31, optimized["atk"], 50, atk_mod),
                "defense": calculate_stat(base_stats["defense"], 31, optimized["def"], 50, def_mod),
                "special_attack": calculate_stat(base_stats["special_attack"], 31, optimized["spa"], 50, spa_mod),
                "special_defense": calculate_stat(base_stats["special_defense"], 31, optimized["spd"], 50, spd_mod),
                "speed": calculate_stat(base_stats["speed"], 31, optimized["spe"], 50, speed_mod)
            }

            # 5. Compare with current spread
            ev_savings = current_spread["total"] - optimized["total"]
            if current_spread["total"] > 0:
                if ev_savings > 0:
                    changes.append(f"Saved {ev_savings} EVs compared to current spread")
                elif ev_savings < 0:
                    changes.append(f"Needs {-ev_savings} more EVs than current spread")

                # Detail specific changes
                for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
                    diff = optimized[stat] - current_spread[stat]
                    if diff != 0:
                        stat_name = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}[stat]
                        if diff > 0:
                            changes.append(f"+{diff} {stat_name} EVs")
                        else:
                            changes.append(f"{diff} {stat_name} EVs")

            # Format summary
            summary = (
                f"{pokemon_name.title()} @ {suggested_nature.title()}: "
                f"{optimized['hp']} HP / {optimized['atk']} Atk / {optimized['def']} Def / "
                f"{optimized['spa']} SpA / {optimized['spd']} SpD / {optimized['spe']} Spe"
            )

            result = success_response(
                f"Optimized spread for {pokemon_name}",
                pokemon=pokemon_name,
                optimized_nature=suggested_nature,
                optimized_spread=optimized,
                final_stats=final_stats,
                benchmarks_hit=benchmarks_hit if benchmarks_hit else ["No specific targets - using minimal EVs"],
                changes_from_current=changes if changes else ["No current spread provided"],
                ev_savings=ev_savings if current_spread["total"] > 0 else "N/A",
                remaining_evs=508 - optimized["total"],
                summary=summary,
                showdown_format=(
                    f"{pokemon_name.title()}\n"
                    f"EVs: {optimized['hp']} HP / {optimized['atk']} Atk / {optimized['def']} Def / "
                    f"{optimized['spa']} SpA / {optimized['spd']} SpD / {optimized['spe']} Spe\n"
                    f"{suggested_nature.title()} Nature"
                )
            )

            # Add Smogon calcs if we checked against multiple spreads
            if smogon_calcs:
                result["smogon_calcs"] = smogon_calcs

            return result

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def compare_pokemon_options(
        pokemon_a: str,
        pokemon_b: str,
        role: str = "auto",
        check_vs_pokemon: str = None
    ) -> dict:
        """
        Compare two Pokemon to help decide which fits your team better.

        Answers: "Should I use Entei or Arcanine-Hisui?"

        Compares:
        - Base stats and stat spreads
        - Speed tiers (who outspeeds what)
        - Typing and weaknesses
        - Abilities
        - Common moves and sets (from Smogon)

        Args:
            pokemon_a: First Pokemon to compare
            pokemon_b: Second Pokemon to compare
            role: Context for comparison:
                - "auto": Detect from stats
                - "physical_attacker", "special_attacker"
                - "support", "wall", "speed_control"
            check_vs_pokemon: Optional - check both against a specific threat

        Returns:
            - side_by_side: Stats comparison
            - speed_comparison: Who's faster, by how much
            - typing_analysis: Shared weaknesses, unique resistances
            - ability_comparison: Key ability differences
            - usage_data: Smogon usage if available
            - verdict: Recommendation with reasoning
        """
        from vgc_mcp_core.calc.stats import calculate_stat, calculate_hp
        from vgc_mcp_core.calc.modifiers import get_type_effectiveness

        try:
            # Fetch both Pokemon
            data_a = await pokeapi.get_pokemon(pokemon_a)
            data_b = await pokeapi.get_pokemon(pokemon_b)

            if not data_a:
                suggestions = suggest_pokemon_name(pokemon_a)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{pokemon_a}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )
            if not data_b:
                suggestions = suggest_pokemon_name(pokemon_b)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{pokemon_b}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            stats_a = data_a["base_stats"]
            stats_b = data_b["base_stats"]
            types_a = await pokeapi.get_pokemon_types(pokemon_a)
            types_b = await pokeapi.get_pokemon_types(pokemon_b)
            abilities_a = await pokeapi.get_pokemon_abilities(pokemon_a)
            abilities_b = await pokeapi.get_pokemon_abilities(pokemon_b)

            # Calculate max speed for both (Jolly/Timid 252 EVs)
            max_speed_a = calculate_stat(stats_a["speed"], 31, 252, 50, 1.1)
            max_speed_b = calculate_stat(stats_b["speed"], 31, 252, 50, 1.1)

            # Stat totals
            bst_a = sum(stats_a.values())
            bst_b = sum(stats_b.values())

            # Side by side comparison
            side_by_side = {
                "stat": ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed", "BST"],
                pokemon_a: [stats_a["hp"], stats_a["attack"], stats_a["defense"],
                           stats_a["special_attack"], stats_a["special_defense"], stats_a["speed"], bst_a],
                pokemon_b: [stats_b["hp"], stats_b["attack"], stats_b["defense"],
                           stats_b["special_attack"], stats_b["special_defense"], stats_b["speed"], bst_b],
                "winner": []
            }

            # Determine winner for each stat
            stat_keys = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
            for key in stat_keys:
                if stats_a[key] > stats_b[key]:
                    side_by_side["winner"].append(pokemon_a)
                elif stats_b[key] > stats_a[key]:
                    side_by_side["winner"].append(pokemon_b)
                else:
                    side_by_side["winner"].append("Tie")
            side_by_side["winner"].append(pokemon_a if bst_a > bst_b else (pokemon_b if bst_b > bst_a else "Tie"))

            # Speed comparison
            speed_diff = abs(max_speed_a - max_speed_b)
            speed_comparison = {
                f"{pokemon_a}_max_speed": max_speed_a,
                f"{pokemon_b}_max_speed": max_speed_b,
                "faster": pokemon_a if max_speed_a > max_speed_b else (pokemon_b if max_speed_b > max_speed_a else "Tie"),
                "difference": speed_diff,
                "note": f"{pokemon_a if max_speed_a > max_speed_b else pokemon_b} outspeeds by {speed_diff} points at max investment"
            }

            # Type analysis
            all_types = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
                        "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
                        "Dragon", "Dark", "Steel", "Fairy"]

            weaknesses_a = [t for t in all_types if get_type_effectiveness(t, types_a) >= 2]
            weaknesses_b = [t for t in all_types if get_type_effectiveness(t, types_b) >= 2]
            resistances_a = [t for t in all_types if 0 < get_type_effectiveness(t, types_a) < 1]
            resistances_b = [t for t in all_types if 0 < get_type_effectiveness(t, types_b) < 1]
            immunities_a = [t for t in all_types if get_type_effectiveness(t, types_a) == 0]
            immunities_b = [t for t in all_types if get_type_effectiveness(t, types_b) == 0]

            shared_weaknesses = list(set(weaknesses_a) & set(weaknesses_b))
            unique_weaknesses_a = list(set(weaknesses_a) - set(weaknesses_b))
            unique_weaknesses_b = list(set(weaknesses_b) - set(weaknesses_a))

            typing_analysis = {
                pokemon_a: {
                    "types": types_a,
                    "weaknesses": weaknesses_a,
                    "resistances": resistances_a,
                    "immunities": immunities_a
                },
                pokemon_b: {
                    "types": types_b,
                    "weaknesses": weaknesses_b,
                    "resistances": resistances_b,
                    "immunities": immunities_b
                },
                "shared_weaknesses": shared_weaknesses,
                "unique_to_a": unique_weaknesses_a,
                "unique_to_b": unique_weaknesses_b
            }

            # Ability comparison
            ability_comparison = {
                pokemon_a: abilities_a,
                pokemon_b: abilities_b
            }

            # Try to get usage data
            usage_data = {}
            try:
                usage_a = await smogon.get_pokemon_usage(pokemon_a)
                if usage_a:
                    usage_data[pokemon_a] = {
                        "usage_percent": usage_a.get("usage", "N/A"),
                        "common_items": list(usage_a.get("items", {}).keys())[:3],
                        "common_moves": list(usage_a.get("moves", {}).keys())[:4]
                    }
            except Exception:
                pass

            try:
                usage_b = await smogon.get_pokemon_usage(pokemon_b)
                if usage_b:
                    usage_data[pokemon_b] = {
                        "usage_percent": usage_b.get("usage", "N/A"),
                        "common_items": list(usage_b.get("items", {}).keys())[:3],
                        "common_moves": list(usage_b.get("moves", {}).keys())[:4]
                    }
            except Exception:
                pass

            # Check vs specific threat if provided
            threat_matchup = None
            if check_vs_pokemon:
                try:
                    threat_data = await pokeapi.get_pokemon(check_vs_pokemon)
                    if threat_data:
                        threat_types = await pokeapi.get_pokemon_types(check_vs_pokemon)
                        eff_a = get_type_effectiveness(types_a[0], threat_types) if types_a else 1.0
                        eff_b = get_type_effectiveness(types_b[0], threat_types) if types_b else 1.0

                        threat_speed = calculate_stat(threat_data["base_stats"]["speed"], 31, 252, 50, 1.1)

                        threat_matchup = {
                            "threat": check_vs_pokemon,
                            "threat_max_speed": threat_speed,
                            f"{pokemon_a}_outspeeds": max_speed_a > threat_speed,
                            f"{pokemon_b}_outspeeds": max_speed_b > threat_speed,
                            f"{pokemon_a}_type_eff": eff_a,
                            f"{pokemon_b}_type_eff": eff_b
                        }
                except Exception:
                    pass

            # Generate verdict
            advantages_a = []
            advantages_b = []

            if max_speed_a > max_speed_b:
                advantages_a.append(f"Faster ({max_speed_a} vs {max_speed_b})")
            elif max_speed_b > max_speed_a:
                advantages_b.append(f"Faster ({max_speed_b} vs {max_speed_a})")

            if stats_a["attack"] > stats_b["attack"]:
                advantages_a.append(f"Higher Attack ({stats_a['attack']} vs {stats_b['attack']})")
            elif stats_b["attack"] > stats_a["attack"]:
                advantages_b.append(f"Higher Attack ({stats_b['attack']} vs {stats_a['attack']})")

            if stats_a["special_attack"] > stats_b["special_attack"]:
                advantages_a.append(f"Higher Sp. Atk ({stats_a['special_attack']} vs {stats_b['special_attack']})")
            elif stats_b["special_attack"] > stats_a["special_attack"]:
                advantages_b.append(f"Higher Sp. Atk ({stats_b['special_attack']} vs {stats_a['special_attack']})")

            bulk_a = stats_a["hp"] * (stats_a["defense"] + stats_a["special_defense"])
            bulk_b = stats_b["hp"] * (stats_b["defense"] + stats_b["special_defense"])
            if bulk_a > bulk_b * 1.1:
                advantages_a.append("Bulkier overall")
            elif bulk_b > bulk_a * 1.1:
                advantages_b.append("Bulkier overall")

            if len(weaknesses_a) < len(weaknesses_b):
                advantages_a.append(f"Fewer weaknesses ({len(weaknesses_a)} vs {len(weaknesses_b)})")
            elif len(weaknesses_b) < len(weaknesses_a):
                advantages_b.append(f"Fewer weaknesses ({len(weaknesses_b)} vs {len(weaknesses_a)})")

            if len(advantages_a) > len(advantages_b):
                winner = pokemon_a
                verdict_text = f"{pokemon_a} has more advantages: {', '.join(advantages_a)}"
            elif len(advantages_b) > len(advantages_a):
                winner = pokemon_b
                verdict_text = f"{pokemon_b} has more advantages: {', '.join(advantages_b)}"
            else:
                winner = "Situational"
                verdict_text = f"Both have trade-offs. {pokemon_a}: {', '.join(advantages_a) or 'None'}. {pokemon_b}: {', '.join(advantages_b) or 'None'}"

            return success_response(
                f"Comparison: {pokemon_a} vs {pokemon_b}",
                pokemon_a=pokemon_a,
                pokemon_b=pokemon_b,
                side_by_side=side_by_side,
                speed_comparison=speed_comparison,
                typing_analysis=typing_analysis,
                ability_comparison=ability_comparison,
                usage_data=usage_data if usage_data else "No usage data available",
                threat_matchup=threat_matchup,
                verdict={
                    "winner": winner,
                    f"{pokemon_a}_advantages": advantages_a,
                    f"{pokemon_b}_advantages": advantages_b,
                    "summary": verdict_text
                }
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def find_counter_for(
        threat: str,
        check_team_first: bool = True,
        suggest_pokemon: bool = True,
        max_suggestions: int = 5
    ) -> dict:
        """
        Find counters for a threatening Pokemon.

        Answers: "What beats Flutter Mane?" or "How do I handle Urshifu?"

        Checks:
        1. Your current team for existing answers
        2. Type advantages
        3. Speed matchups
        4. Common counters from meta usage

        Args:
            threat: The Pokemon you need to counter
            check_team_first: Check current team for answers (default: True)
            suggest_pokemon: Suggest meta Pokemon as counters (default: True)
            max_suggestions: Max Pokemon to suggest (default: 5)

        Returns:
            - threat_info: The threat's key stats/typing
            - team_answers: Which team members can handle it
            - type_counters: Types that resist and hit back
            - meta_counters: Popular Pokemon that counter this threat
            - recommendation: Best approach
        """
        from vgc_mcp_core.calc.stats import calculate_stat
        from vgc_mcp_core.calc.modifiers import get_type_effectiveness

        try:
            # Get threat data
            threat_data = await pokeapi.get_pokemon(threat)
            if not threat_data:
                suggestions = suggest_pokemon_name(threat)
                return error_response(
                    ErrorCodes.POKEMON_NOT_FOUND,
                    f"Pokemon '{threat}' not found",
                    suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                )

            threat_stats = threat_data["base_stats"]
            threat_types = await pokeapi.get_pokemon_types(threat)
            threat_abilities = await pokeapi.get_pokemon_abilities(threat)
            threat_max_speed = calculate_stat(threat_stats["speed"], 31, 252, 50, 1.1)

            # Determine if threat is physical or special
            is_physical = threat_stats["attack"] > threat_stats["special_attack"]
            offensive_stat = threat_stats["attack"] if is_physical else threat_stats["special_attack"]

            threat_info = {
                "name": threat,
                "types": threat_types,
                "abilities": threat_abilities,
                "max_speed": threat_max_speed,
                "offensive_stat": f"{'Attack' if is_physical else 'Sp. Atk'}: {offensive_stat}",
                "is_physical_attacker": is_physical
            }

            # Find type advantages
            all_types = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
                        "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
                        "Dragon", "Dark", "Steel", "Fairy"]

            # Types that resist the threat's STAB
            resists_threat = []
            for t in all_types:
                # Check resistance to both threat types
                total_eff = 1.0
                for threat_type in threat_types:
                    total_eff *= get_type_effectiveness(threat_type, [t])
                if total_eff < 1:
                    resists_threat.append((t, total_eff))

            # Types that hit threat super effectively
            hits_threat_se = []
            for t in all_types:
                eff = get_type_effectiveness(t, threat_types)
                if eff >= 2:
                    hits_threat_se.append((t, eff))

            # Best counter types (resist AND hit SE)
            resist_types = set([t for t, _ in resists_threat])
            se_types = set([t for t, _ in hits_threat_se])
            ideal_counter_types = list(resist_types & se_types)

            type_counters = {
                "resists_threat_stab": [f"{t} ({eff}x)" for t, eff in resists_threat],
                "hits_threat_super_effective": [f"{t} ({eff}x)" for t, eff in hits_threat_se],
                "ideal_counter_types": ideal_counter_types if ideal_counter_types else "No single type both resists and hits SE"
            }

            # Check current team
            team_answers = []
            if check_team_first and team_manager.size > 0:
                for slot in team_manager.team.slots:
                    pokemon = slot.pokemon
                    pokemon_types = pokemon.types

                    # Check if resists threat
                    resists = True
                    for threat_type in threat_types:
                        if get_type_effectiveness(threat_type, pokemon_types) >= 1:
                            resists = False
                            break

                    # Check if outspeeds
                    pokemon_speed = calculate_stat(pokemon.base_stats.speed, 31, 252, 50, 1.1)
                    outspeeds = pokemon_speed > threat_max_speed

                    # Check if hits SE
                    hits_se = False
                    for poke_type in pokemon_types:
                        if get_type_effectiveness(poke_type, threat_types) >= 2:
                            hits_se = True
                            break

                    if resists or hits_se or outspeeds:
                        answer = {
                            "pokemon": pokemon.name,
                            "resists_threat": resists,
                            "outspeeds_threat": outspeeds,
                            "hits_super_effective": hits_se,
                            "verdict": []
                        }
                        if resists and hits_se:
                            answer["verdict"].append("Hard counter (resists + hits SE)")
                        elif resists:
                            answer["verdict"].append("Defensive check (resists)")
                        elif hits_se and outspeeds:
                            answer["verdict"].append("Offensive check (outspeeds + hits SE)")
                        elif hits_se:
                            answer["verdict"].append("Revenge killer (hits SE but slower)")

                        if answer["verdict"]:
                            team_answers.append(answer)

            # Suggest meta counters
            meta_counters = []
            if suggest_pokemon:
                # Common counters by type
                counter_suggestions = {
                    "Fairy": ["Flutter Mane", "Primarina", "Hatterene", "Sylveon"],
                    "Ghost": ["Gholdengo", "Flutter Mane", "Dragapult", "Annihilape"],
                    "Dark": ["Kingambit", "Hydreigon", "Tyranitar", "Incineroar"],
                    "Steel": ["Gholdengo", "Kingambit", "Heatran", "Corviknight"],
                    "Dragon": ["Dragonite", "Dragapult", "Roaring Moon", "Kommo-o"],
                    "Ground": ["Landorus", "Garchomp", "Great Tusk", "Ting-Lu"],
                    "Water": ["Kyogre", "Palafin", "Urshifu-Rapid-Strike", "Dondozo"],
                    "Fire": ["Chi-Yu", "Entei", "Arcanine-Hisui", "Volcarona"],
                    "Fighting": ["Urshifu", "Iron Hands", "Annihilape", "Great Tusk"],
                    "Psychic": ["Indeedee-F", "Hatterene", "Meowscarada"],
                    "Electric": ["Raging Bolt", "Miraidon", "Iron Hands"],
                    "Ice": ["Chien-Pao", "Baxcalibur", "Iron Bundle"]
                }

                # Suggest Pokemon that are good against threat's weaknesses
                for se_type, _ in hits_threat_se[:3]:
                    if se_type in counter_suggestions:
                        for suggestion in counter_suggestions[se_type][:2]:
                            if suggestion.lower() != threat.lower():
                                meta_counters.append({
                                    "pokemon": suggestion,
                                    "reason": f"Strong {se_type}-type attacker"
                                })

                # Deduplicate
                seen = set()
                unique_counters = []
                for counter in meta_counters:
                    if counter["pokemon"] not in seen:
                        seen.add(counter["pokemon"])
                        unique_counters.append(counter)
                meta_counters = unique_counters[:max_suggestions]

            # Generate recommendation
            if team_answers:
                has_hard_counter = any("Hard counter" in str(a.get("verdict", [])) for a in team_answers)
                if has_hard_counter:
                    recommendation = f"Your team has a hard counter. Lead with or pivot to your answer."
                else:
                    recommendation = f"Your team has checks but no hard counter. Consider adding a {ideal_counter_types[0] if ideal_counter_types else 'resistant'}-type."
            elif meta_counters:
                top_counter = meta_counters[0]["pokemon"]
                recommendation = f"Your team lacks answers. Consider adding {top_counter} or another {hits_threat_se[0][0] if hits_threat_se else 'offensive'}-type."
            else:
                recommendation = "Use speed control (Tailwind/Trick Room) or priority moves to handle this threat."

            return success_response(
                f"Counters for {threat}",
                threat_info=threat_info,
                type_counters=type_counters,
                team_answers=team_answers if team_answers else "No team loaded or no answers found",
                meta_counters=meta_counters if meta_counters else "No suggestions available",
                recommendation=recommendation
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))

    @mcp.tool()
    async def evaluate_core(
        pokemon_list: list[str],
        suggest_partners: bool = True,
        max_partners: int = 3
    ) -> dict:
        """
        Evaluate a Pokemon core (2-4 Pokemon) for synergy.

        Answers: "Is Kyogre + Flutter Mane a good core?"

        Checks:
        - Type synergy (shared weaknesses, complementary resistances)
        - Speed control compatibility
        - Offensive coverage
        - Defensive gaps
        - Role redundancy

        Args:
            pokemon_list: List of 2-4 Pokemon names forming the core
            suggest_partners: Suggest Pokemon to complete the core (default: True)
            max_partners: Number of partners to suggest (default: 3)

        Returns:
            - core_pokemon: The Pokemon in this core
            - type_synergy: Weaknesses, resistances, gaps
            - speed_analysis: Speed tiers and control options
            - coverage: Offensive type coverage
            - synergy_score: 1-10 rating
            - issues: Problems with this core
            - suggested_partners: Pokemon that complement this core
        """
        from vgc_mcp_core.calc.stats import calculate_stat
        from vgc_mcp_core.calc.modifiers import get_type_effectiveness

        try:
            if len(pokemon_list) < 2:
                return error_response(ErrorCodes.VALIDATION_ERROR, "Core must have at least 2 Pokemon")
            if len(pokemon_list) > 4:
                return error_response(ErrorCodes.VALIDATION_ERROR, "Core should have at most 4 Pokemon")

            # Fetch all Pokemon data
            core_data = []
            all_types = []
            all_speeds = []
            all_weaknesses = []
            all_resistances = []

            type_list = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
                        "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
                        "Dragon", "Dark", "Steel", "Fairy"]

            for poke_name in pokemon_list:
                data = await pokeapi.get_pokemon(poke_name)
                if not data:
                    suggestions = suggest_pokemon_name(poke_name)
                    return error_response(
                        ErrorCodes.POKEMON_NOT_FOUND,
                        f"Pokemon '{poke_name}' not found",
                        suggestions=[f"Did you mean: {', '.join(suggestions)}?"] if suggestions else []
                    )

                types = await pokeapi.get_pokemon_types(poke_name)
                abilities = await pokeapi.get_pokemon_abilities(poke_name)
                stats = data["base_stats"]
                max_speed = calculate_stat(stats["speed"], 31, 252, 50, 1.1)

                # Calculate weaknesses/resistances
                weaknesses = [t for t in type_list if get_type_effectiveness(t, types) >= 2]
                resistances = [t for t in type_list if 0 < get_type_effectiveness(t, types) < 1]
                immunities = [t for t in type_list if get_type_effectiveness(t, types) == 0]

                core_data.append({
                    "name": poke_name,
                    "types": types,
                    "abilities": abilities,
                    "max_speed": max_speed,
                    "base_stats": stats,
                    "weaknesses": weaknesses,
                    "resistances": resistances,
                    "immunities": immunities
                })

                all_types.extend(types)
                all_speeds.append((poke_name, max_speed))
                all_weaknesses.extend(weaknesses)
                all_resistances.extend(resistances)

            # Type synergy analysis
            from collections import Counter
            weakness_counts = Counter(all_weaknesses)
            shared_weaknesses = [w for w, count in weakness_counts.items() if count >= 2]

            # Check if resistances cover weaknesses
            covered_weaknesses = []
            uncovered_weaknesses = []
            for weakness in set(all_weaknesses):
                if weakness in all_resistances:
                    covered_weaknesses.append(weakness)
                else:
                    uncovered_weaknesses.append(weakness)

            type_synergy = {
                "core_types": list(set(all_types)),
                "shared_weaknesses": shared_weaknesses,
                "covered_by_partner": covered_weaknesses,
                "uncovered_gaps": uncovered_weaknesses,
                "type_diversity": len(set(all_types))
            }

            # Speed analysis
            all_speeds.sort(key=lambda x: x[1], reverse=True)
            speed_tiers = {
                "order": [f"{name}: {speed}" for name, speed in all_speeds],
                "fastest": all_speeds[0][0],
                "slowest": all_speeds[-1][0],
                "speed_range": all_speeds[0][1] - all_speeds[-1][1]
            }

            # Check for speed control Pokemon
            speed_control_pokemon = []
            speed_control_abilities = ["drought", "drizzle", "sand-stream", "snow-warning",
                                       "electric-surge", "grassy-surge", "psychic-surge", "misty-surge"]
            for poke in core_data:
                abilities_lower = [a.lower().replace(" ", "-") for a in poke["abilities"]]
                if any(ability in speed_control_abilities for ability in abilities_lower):
                    speed_control_pokemon.append(f"{poke['name']} (weather/terrain)")
                if poke["base_stats"]["speed"] < 50:
                    speed_control_pokemon.append(f"{poke['name']} (Trick Room candidate)")

            speed_analysis = {
                **speed_tiers,
                "speed_control": speed_control_pokemon if speed_control_pokemon else "No obvious speed control"
            }

            # Offensive coverage
            stab_types = list(set(all_types))
            coverage_hits_se = {}
            for attack_type in stab_types:
                hits = [t for t in type_list if get_type_effectiveness(attack_type, [t]) >= 2]
                coverage_hits_se[attack_type] = hits

            all_se_hits = set()
            for hits in coverage_hits_se.values():
                all_se_hits.update(hits)

            uncovered_types = [t for t in type_list if t not in all_se_hits]

            coverage = {
                "stab_types": stab_types,
                "types_hit_se": list(all_se_hits),
                "types_not_covered": uncovered_types,
                "coverage_percent": f"{len(all_se_hits)}/{len(type_list)} types"
            }

            # Calculate synergy score
            score = 10
            issues = []

            # Deduct for shared weaknesses
            if len(shared_weaknesses) >= 3:
                score -= 3
                issues.append(f"Too many shared weaknesses: {', '.join(shared_weaknesses)}")
            elif len(shared_weaknesses) >= 2:
                score -= 1.5
                issues.append(f"Shared weaknesses: {', '.join(shared_weaknesses)}")
            elif len(shared_weaknesses) == 1:
                score -= 0.5

            # Deduct for uncovered gaps
            if len(uncovered_weaknesses) >= 4:
                score -= 2
                issues.append(f"Many uncovered weaknesses: {', '.join(uncovered_weaknesses[:4])}")
            elif len(uncovered_weaknesses) >= 2:
                score -= 1

            # Deduct for poor coverage
            if len(uncovered_types) >= 6:
                score -= 1.5
                issues.append(f"Limited offensive coverage - can't hit: {', '.join(uncovered_types[:4])}")
            elif len(uncovered_types) >= 4:
                score -= 0.5

            # Deduct for same-type redundancy
            type_redundancy = [t for t, count in Counter(all_types).items() if count > 1]
            if type_redundancy:
                score -= 0.5 * len(type_redundancy)
                issues.append(f"Type redundancy: multiple {', '.join(type_redundancy)}-types")

            # Bonus for speed diversity
            if speed_analysis["speed_range"] >= 50:
                score += 0.5  # Good speed diversity

            # Bonus for speed control
            if speed_control_pokemon:
                score += 0.5

            score = max(1, min(10, round(score, 1)))

            # Suggest partners
            suggested_partners = []
            if suggest_partners:
                # Find types that cover the gaps
                partner_types_needed = list(set(uncovered_weaknesses + shared_weaknesses))

                # Suggest Pokemon that resist shared weaknesses
                partner_suggestions = {
                    "Fairy": ["Gholdengo", "Kingambit", "Heatran"],
                    "Dragon": ["Sylveon", "Hatterene", "Dachsbun"],
                    "Ground": ["Landorus", "Rillaboom", "Amoonguss"],
                    "Fire": ["Palafin", "Dondozo", "Gastrodon"],
                    "Water": ["Rillaboom", "Amoonguss", "Cresselia"],
                    "Electric": ["Ting-Lu", "Garchomp", "Landorus"],
                    "Ice": ["Arcanine-Hisui", "Entei", "Incineroar"],
                    "Fighting": ["Cresselia", "Gholdengo", "Flutter Mane"],
                    "Dark": ["Kingambit", "Iron Hands", "Annihilape"],
                    "Ghost": ["Incineroar", "Kingambit", "Tyranitar"],
                    "Psychic": ["Kingambit", "Incineroar", "Tyranitar"],
                    "Rock": ["Rillaboom", "Iron Hands", "Palafin"],
                    "Steel": ["Incineroar", "Arcanine-Hisui", "Chi-Yu"]
                }

                for gap_type in partner_types_needed[:3]:
                    if gap_type in partner_suggestions:
                        for suggestion in partner_suggestions[gap_type]:
                            # Don't suggest Pokemon already in core
                            if suggestion.lower() not in [p.lower() for p in pokemon_list]:
                                suggested_partners.append({
                                    "pokemon": suggestion,
                                    "reason": f"Helps cover {gap_type} weakness"
                                })

                # Deduplicate
                seen = set()
                unique_partners = []
                for partner in suggested_partners:
                    if partner["pokemon"] not in seen:
                        seen.add(partner["pokemon"])
                        unique_partners.append(partner)
                suggested_partners = unique_partners[:max_partners]

            return success_response(
                f"Core evaluation: {' + '.join(pokemon_list)}",
                core_pokemon=[p["name"] for p in core_data],
                core_details=core_data,
                type_synergy=type_synergy,
                speed_analysis=speed_analysis,
                coverage=coverage,
                synergy_score=score,
                rating="Excellent" if score >= 8 else ("Good" if score >= 6 else ("Okay" if score >= 4 else "Needs work")),
                issues=issues if issues else ["No major issues found"],
                suggested_partners=suggested_partners if suggested_partners else "Core looks complete"
            )

        except Exception as e:
            return error_response(ErrorCodes.INTERNAL_ERROR, str(e))
