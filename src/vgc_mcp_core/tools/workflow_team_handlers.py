"""Handlers for team-level workflow tools (checks, imports, fixes, counters, cores)."""

from typing import Any, Optional

from vgc_mcp_core.formats.showdown import ShowdownParseError, parse_showdown_team
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.tools.build_helpers import build_pokemon
from vgc_mcp_core.utils.errors import ErrorCodes, error_response, success_response
from vgc_mcp_core.utils.fuzzy import suggest_pokemon_name


async def full_team_check(
    team_manager: Any,
    analyzer: Any,
    paste: Optional[str] = None,
    detailed: bool = True,
) -> dict[str, Any]:
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


async def import_and_analyze(
    pokeapi: Any,
    team_manager: Any,
    analyzer: Any,
    paste: str,
    load_to_team: bool = True,
) -> dict[str, Any]:
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
                    from vgc_mcp_core.models.pokemon import (
                        BaseStats,
                        EVSpread,
                        Nature,
                    )

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
                        nature = Nature(pokemon.nature.lower()) if pokemon.nature else Nature.SERIOUS
                    except ValueError:
                        nature = Nature.SERIOUS

                    build = build_pokemon(
                        name=pokemon_data["name"],
                        base_stats=base_stats,
                        types=pokemon_data.get("types", []),
                        nature=nature,
                        spread=evs,
                        ability=pokemon.ability,
                        item=pokemon.item,
                        moves=pokemon.moves[:4] if pokemon.moves else [],
                        tera_type=pokemon.tera_type,
                        level=50,
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


async def fix_team_issues(
    team_manager: Any,
    paste: Optional[str] = None,
) -> dict[str, Any]:
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
                "suggestion": "Keep your 2 best restricted, consider which has better synergy with the team"
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
            items_lower = {x.lower() for x in items}
            unused_items = [i for i in common_items if i.lower() not in items_lower]

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


async def add_pokemon_smart(
    pokeapi: Any,
    team_manager: Any,
    pokemon_name: str,
    role: str = 'auto',
) -> dict[str, Any]:
    from vgc_mcp_core.rules.regulation_router import auto_detect_regulation

    try:
        # Resolve base stats / types / abilities via the canonical helpers.
        # The raw PokeAPI response exposes a `stats` array (not a
        # `base_stats` dict), so indexing pokemon_data["base_stats"]
        # directly used to raise KeyError against the real client. Mirror
        # suggest_ev_spread and use the typed accessors instead.
        try:
            base_stats_model = await pokeapi.get_base_stats(pokemon_name)
            types = await pokeapi.get_pokemon_types(pokemon_name)
            abilities = await pokeapi.get_pokemon_abilities(pokemon_name)
        except Exception:
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

        base_stats = {
            "hp": base_stats_model.hp,
            "attack": base_stats_model.attack,
            "defense": base_stats_model.defense,
            "special_attack": base_stats_model.special_attack,
            "special_defense": base_stats_model.special_defense,
            "speed": base_stats_model.speed,
        }

        # Detect Champions vs mainline from the Pokemon name (mirrors
        # suggest_ev_spread ~lines 856-863). Explicit session regulation
        # wins; otherwise inference may set it. We surface whatever the
        # auto-detect resolved so the caller can tell the user.
        cfg = get_regulation_config()
        regulation_auto_detected = None
        try:
            detect = auto_detect_regulation([pokemon_name], cfg)
            # Only surface when the server actually inferred/applied a
            # regulation — a "skipped" action means the user already chose
            # one explicitly, so there's nothing new to report.
            if isinstance(detect, dict) and detect.get("action") != "skipped":
                regulation_auto_detected = detect
        except Exception:
            pass
        format_system = cfg.get_format_system() or "mainline"
        is_champions = format_system == "champions"

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
        from vgc_mcp_core.calc.conversion import evs_to_sps_spread
        from vgc_mcp_core.models.pokemon import (
            BaseStats,
            EVSpread,
            Nature,
        )

        ev_map = build["evs"]
        ability = abilities[0] if abilities else None
        species_name = pokemon_name

        try:
            nature = Nature(build["nature"].lower())
        except ValueError:
            nature = Nature.SERIOUS

        base_stats_obj = BaseStats(
            hp=base_stats["hp"],
            attack=base_stats["attack"],
            defense=base_stats["defense"],
            special_attack=base_stats["special_attack"],
            special_defense=base_stats["special_defense"],
            speed=base_stats["speed"],
        )

        # Champions branch: scale the role's EV spread to the SP grain.
        # 252 EV saturates to 32 SP and 4 EV maps to 1 SP, so converting
        # the mainline role template keeps the same final stats while
        # honoring the 32-per-stat / 66-total caps. The build carries
        # format_system='champions' + sps so all downstream calc/export
        # dispatches correctly and the paste emits an `SPs:` line.
        sp_map = None
        if is_champions:
            ev_obj = EVSpread(
                hp=ev_map.get("hp", 0),
                attack=ev_map.get("atk", 0),
                defense=ev_map.get("def", 0),
                special_attack=ev_map.get("spa", 0),
                special_defense=ev_map.get("spd", 0),
                speed=ev_map.get("spe", 0),
            )
            sp_obj = evs_to_sps_spread(ev_obj, round_mode="ceil")
            sp_map = {
                "hp": sp_obj.hp,
                "atk": sp_obj.attack,
                "def": sp_obj.defense,
                "spa": sp_obj.special_attack,
                "spd": sp_obj.special_defense,
                "spe": sp_obj.speed,
            }
            pokemon_build = build_pokemon(
                name=species_name,
                base_stats=base_stats_obj,
                types=types,
                nature=nature,
                champions=True,
                spread=sp_obj,
                ability=ability,
                level=50,
            )
        else:
            evs = EVSpread(
                hp=ev_map.get("hp", 0),
                attack=ev_map.get("atk", 0),
                defense=ev_map.get("def", 0),
                special_attack=ev_map.get("spa", 0),
                special_defense=ev_map.get("spd", 0),
                speed=ev_map.get("spe", 0)
            )
            pokemon_build = build_pokemon(
                name=species_name,
                base_stats=base_stats_obj,
                types=types,
                nature=nature,
                spread=evs,
                ability=ability,
                level=50,
            )

        # Build payload reflects the active format's units.
        build_payload = {
            "nature": build["nature"],
            "ability": pokemon_build.ability,
            "reasoning": build["description"],
        }
        if is_champions:
            build_payload["sps"] = sp_map
            build_payload["stat_units"] = "Stat Points (SPs)"
            build_payload["sp_budget_remaining"] = max(0, 66 - pokemon_build.sps.total)
        else:
            build_payload["evs"] = ev_map

        # Check team status
        if team_manager.is_full:
            return error_response(
                ErrorCodes.TEAM_FULL,
                "Team is full (6 Pokemon)",
                suggestions=[
                    "Use 'remove_from_team' to remove a Pokemon first",
                    "Use 'swap_team_pokemon' to replace a specific slot"
                ],
                suggested_build={
                    "pokemon": species_name,
                    "role": role,
                    **build_payload,
                }
            )

        # Add to team
        success, message, data = team_manager.add_pokemon(pokemon_build)

        if not success:
            return error_response(
                ErrorCodes.SPECIES_CLAUSE if "species" in message.lower() else ErrorCodes.INTERNAL_ERROR,
                message,
                suggestions=["This Pokemon or its variant may already be on the team"]
            )

        from vgc_mcp_core.formats.showdown import pokemon_build_to_showdown

        response_kwargs = dict(
            pokemon=species_name,
            slot=data.get("slot", team_manager.size),
            role=role,
            build=build_payload,
            team_size=team_manager.size,
            format_system=format_system,
            showdown_paste=pokemon_build_to_showdown(pokemon_build),
            tip="Use 'get_common_sets' to see common competitive sets, or 'swap_team_pokemon' to replace this slot with a custom build",
        )
        # Surface what the auto-detect resolved (documented contract).
        if regulation_auto_detected is not None:
            response_kwargs["regulation_auto_detected"] = regulation_auto_detected

        return success_response(
            f"Added {species_name} to team",
            **response_kwargs,
        )

    except Exception as e:
        return error_response(ErrorCodes.INTERNAL_ERROR, str(e))


async def check_team_vs_threat(
    pokeapi: Any,
    team_manager: Any,
    threat_pokemon: str,
    threat_nature: str = 'modest',
    threat_offensive_evs: int = 252,
    threat_item: Optional[str] = None,
    threat_ability: Optional[str] = None,
    check_moves: Optional[list[str]] = None,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.damage import calculate_damage
    from vgc_mcp_core.calc.modifiers import DamageModifiers
    from vgc_mcp_core.models.pokemon import BaseStats, EVSpread, Nature

    try:
        if team_manager.size == 0:
            return error_response(
                ErrorCodes.TEAM_EMPTY,
                "No team loaded",
                suggestions=["Load a team with 'import_showdown_team' first"]
            )

        threat_data = await pokeapi.get_pokemon(threat_pokemon)

        # Auto-detect ability
        if not threat_ability:
            abilities = await pokeapi.get_pokemon_abilities(threat_pokemon)
            if abilities:
                threat_ability = abilities[0].lower().replace(" ", "-")

        try:
            threat_nat = Nature(threat_nature.lower())
        except ValueError:
            threat_nat = Nature.MODEST

        is_physical = threat_data["base_stats"]["attack"] > threat_data["base_stats"]["special_attack"]

        threat_build = build_pokemon(
            name=threat_pokemon,
            base_stats=BaseStats(**threat_data["base_stats"]),
            types=threat_data.get("types", []),
            nature=threat_nat,
            spread=EVSpread(
                attack=threat_offensive_evs if is_physical else 0,
                special_attack=0 if is_physical else threat_offensive_evs
            ),
            ability=threat_ability,
            item=threat_item,
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
                        modifiers = DamageModifiers.from_scenario(
                            attacker_ability=threat_ability,
                            attacker_item=threat_item,
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
                            modifiers = DamageModifiers.from_scenario()
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


async def find_counter_for(
    pokeapi: Any,
    team_manager: Any,
    threat: str,
    check_team_first: bool = True,
    suggest_pokemon: bool = True,
    max_suggestions: int = 5,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.modifiers import get_type_effectiveness
    from vgc_mcp_core.calc.stats import calculate_stat

    try:
        # Get threat data
        threat_data = await pokeapi.get_pokemon(threat)

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
                recommendation = "Your team has a hard counter. Lead with or pivot to your answer."
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


async def evaluate_core(
    pokeapi: Any,
    pokemon_list: list[str],
    suggest_partners: bool = True,
    max_partners: int = 3,
) -> dict[str, Any]:
    from vgc_mcp_core.calc.modifiers import get_type_effectiveness
    from vgc_mcp_core.calc.stats import calculate_stat

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

            pokemon_list_lower = {p.lower() for p in pokemon_list}
            for gap_type in partner_types_needed[:3]:
                if gap_type in partner_suggestions:
                    for suggestion in partner_suggestions[gap_type]:
                        # Don't suggest Pokemon already in core
                        if suggestion.lower() not in pokemon_list_lower:
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
