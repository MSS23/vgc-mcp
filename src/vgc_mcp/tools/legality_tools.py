"""MCP tools for VGC format legality checking."""

from typing import Annotated, Optional

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from vgc_mcp_core.rules.item_clause import (
    check_item_clause,
    suggest_alternative_items,
)
from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.rules.restricted import (
    find_restricted,
    get_restricted_status,
)
from vgc_mcp_core.rules.vgc_rules import get_regulation, validate_team_rules
from vgc_mcp_core.utils.errors import ErrorCodes, error_response


def register_legality_tools(mcp: FastMCP, team_manager):
    """Register VGC legality checking tools with the MCP server."""

    @mcp.tool(
        title="Validate Team Legality",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def validate_team_legality(
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation to validate against (e.g. 'reg_f', 'reg_g', 'reg_h'); uses the current session regulation if omitted",
        )] = None,
    ) -> dict:
        """Validate full team legality for VGC tournament play.

        Checks restricted Pokemon count (regulation-dependent limit), banned
        Pokemon (mythicals), item clause, species clause, and team size.
        Returns a complete legality report with any violations.
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return error_response(ErrorCodes.INTERNAL_ERROR, 'No team to validate. Add Pokemon first.', valid=False, regulation=reg_code)

        # Get regulation rules
        reg = get_regulation(reg_code)
        if not reg:
            available = config.list_regulation_codes()
            return error_response(ErrorCodes.INTERNAL_ERROR, f"Unknown regulation: {reg_code}. Valid: {', '.join(available)}", valid=False)

        # Run full validation
        result = validate_team_rules(team, reg_code)

        # Add regulation info
        result["regulation"] = {
            "name": reg.name,
            "code": reg.code,
            "restricted_limit": reg.restricted_limit,
            "description": reg.description
        }

        return result

    @mcp.tool(
        title="Check Restricted Pokemon Count",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_restricted_count(
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation (reg_f allows 2 restricted, reg_g allows 1, reg_h allows 0); uses the current session regulation if omitted",
        )] = None,
    ) -> dict:
        """Check how many restricted (box legend) Pokemon are on the team.

        Restricted Pokemon include Koraidon, Miraidon, Kyogre, Groudon, etc.
        Returns the count and whether it is within the regulation's limit.
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "count": 0,
                "valid": True,
                "message": "No Pokemon on team"
            }

        reg = get_regulation(reg_code)
        if not reg:
            return error_response(ErrorCodes.INTERNAL_ERROR, f'Unknown regulation: {reg_code}')

        # Get Pokemon names
        pokemon_names = [slot.pokemon.name for slot in team.slots]

        # Find restricted Pokemon
        restricted_on_team = find_restricted(pokemon_names, reg_code)

        count = len(restricted_on_team)
        limit = reg.restricted_limit
        valid = count <= limit

        return {
            "count": count,
            "limit": limit,
            "valid": valid,
            "restricted_pokemon": restricted_on_team,
            "regulation": reg_code,
            "message": f"{count}/{limit} restricted Pokemon" + (
                "" if valid else f" - OVER LIMIT by {count - limit}"
            )
        }

    @mcp.tool(
        title="Check Item Clause",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_item_clause_tool() -> dict:
        """Check if the current team violates the item clause (no duplicate items).

        In VGC, each Pokemon must hold a different item. Returns the validation
        result with any duplicate items found and which Pokemon hold them.
        """
        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "valid": True,
                "message": "No Pokemon on team"
            }

        # Collect items
        items = [slot.pokemon.item for slot in team.slots]

        # Check for duplicates
        result = check_item_clause(items)

        # Add Pokemon info for duplicates
        if result["duplicates"]:
            pokemon_with_items = {}
            for slot in team.slots:
                item = slot.pokemon.item
                if item:
                    normalized = item.lower().replace(" ", "-").replace("'", "").strip()
                    if normalized not in pokemon_with_items:
                        pokemon_with_items[normalized] = []
                    pokemon_with_items[normalized].append(slot.pokemon.name)

            result["duplicate_details"] = {
                item: pokemon_with_items.get(item, [])
                for item in result["duplicates"]
            }

        return result

    @mcp.tool(
        title="Get Format Rules",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_format_rules(
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation code (e.g. 'reg_f', 'reg_g', 'reg_h'); uses the current session regulation if omitted",
        )] = None,
    ) -> dict:
        """Get the full rule set for a specific VGC regulation.

        Returns restricted limit, item/species clauses, level, team size,
        bring limit, and descriptive notes.
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        reg = get_regulation(reg_code)

        if not reg:
            available = config.list_regulation_codes()
            return error_response(ErrorCodes.INTERNAL_ERROR, f'Unknown regulation: {reg_code}', available=available)

        return {
            "name": reg.name,
            "code": reg.code,
            "restricted_limit": reg.restricted_limit,
            "item_clause": reg.item_clause,
            "species_clause": reg.species_clause,
            "level": reg.level,
            "pokemon_limit": reg.pokemon_limit,
            "bring_limit": reg.bring_limit,
            "description": reg.description,
            "notes": [
                f"Bring {reg.bring_limit} Pokemon to each battle from your team of {reg.pokemon_limit}",
                f"Maximum {reg.restricted_limit} restricted (box legend) Pokemon allowed",
                "Item clause: Each Pokemon must hold a different item" if reg.item_clause else "Item clause not enforced",
                "Species clause: No duplicate Pokemon species" if reg.species_clause else "Species clause not enforced"
            ]
        }

    @mcp.tool(
        title="Check Pokemon Legality",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def check_pokemon_legality(
        pokemon_name: Annotated[str, Field(
            description="Name of the Pokemon to check (e.g. 'koraidon', 'flutter-mane')",
            min_length=1,
        )],
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation to check against; uses the current session regulation if omitted",
        )] = None,
    ) -> dict:
        """Check if a specific Pokemon is legal, restricted, or banned.

        For allowlist regulations (e.g. Reg MA Champions), legality is decided
        purely by the allowlist. Returns the legality status and any restrictions.
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        # Allowlist regulations (e.g. Reg MA Champions) decide legality purely
        # from the allowlist — there is no banlist/restricted concept.
        if config.get_legality_mode(reg_code) == "allowlist":
            on_list = config.is_pokemon_legal(pokemon_name, reg_code)
            if on_list:
                return {
                    "pokemon": pokemon_name,
                    "status": "allowed",
                    "regulation": reg_code,
                    "legal": True,
                    "restricted": False,
                    "message": f"{pokemon_name} is legal in {reg_code}",
                }
            return {
                "pokemon": pokemon_name,
                "status": "illegal",
                "regulation": reg_code,
                "legal": False,
                "restricted": False,
                "message": (
                    f"{pokemon_name} is NOT legal in {reg_code} "
                    f"(not on the Reg MA allowlist)"
                ),
            }

        status = get_restricted_status(pokemon_name, reg_code)

        result = {
            "pokemon": pokemon_name,
            "status": status,
            "regulation": reg_code
        }

        if status == "banned":
            result["message"] = f"{pokemon_name} is BANNED from VGC (mythical Pokemon)"
            result["legal"] = False
        elif status == "restricted":
            limit = config.get_restricted_limit(reg_code)
            result["message"] = f"{pokemon_name} is RESTRICTED (counts toward {limit} restricted limit)"
            result["legal"] = True
            result["restricted"] = True
        else:
            result["message"] = f"{pokemon_name} is fully legal with no restrictions"
            result["legal"] = True
            result["restricted"] = False

        return result

    @mcp.tool(
        title="Suggest Item Alternatives",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def suggest_item_alternatives(
        item_name: Annotated[str, Field(
            description="The duplicated item to find alternatives for (e.g. 'focus-sash')",
            min_length=1,
        )],
        pokemon_role: Annotated[Optional[str], Field(
            description="Optional role hint to tailor suggestions (e.g. 'attacker', 'support')",
        )] = None,
    ) -> dict:
        """Suggest alternative items when the item clause flags a duplicate.

        Returns a list of alternative item suggestions, optionally tailored to
        the Pokemon's role.
        """
        alternatives = suggest_alternative_items(item_name, pokemon_role)

        return {
            "current_item": item_name,
            "role": pokemon_role or "any",
            "alternatives": [
                item.replace("-", " ").title()
                for item in alternatives
            ],
            "message": f"Consider replacing one {item_name} with one of these alternatives"
        }

    @mcp.tool(
        title="List Restricted Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_restricted_pokemon(
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation code; uses the current session regulation if omitted",
        )] = None,
    ) -> dict:
        """List all restricted (box legend) Pokemon for a VGC regulation.

        Returns the complete restricted list plus the regulation's restricted limit.
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        restricted = config.get_restricted_pokemon(reg_code)

        return {
            "regulation": reg_code,
            "restricted_pokemon": sorted(list(restricted)),
            "count": len(restricted),
            "limit": config.get_restricted_limit(reg_code),
            "description": f"These Pokemon count toward the restricted limit ({config.get_restricted_limit(reg_code)} allowed in {reg_code})"
        }

    @mcp.tool(
        title="List Banned Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_banned_pokemon(
        regulation: Annotated[Optional[str], Field(
            description="VGC regulation code; uses the current session regulation if omitted",
        )] = None,
    ) -> dict:
        """List all banned Pokemon for a VGC regulation.

        Banned Pokemon are typically mythicals that cannot be used in official
        VGC tournaments.
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        banned = config.get_banned_pokemon(reg_code)

        return {
            "regulation": reg_code,
            "banned_pokemon": sorted(list(banned)),
            "count": len(banned),
            "description": "These Pokemon are banned from VGC and cannot be used"
        }

    @mcp.tool(
        title="Get Current Regulation Info",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def get_current_regulation_info() -> dict:
        """Get information about the currently active VGC regulation.

        Returns the regulation currently in effect (from date-based detection
        or a session/manual override), including its rules and date range.
        """
        config = get_regulation_config()
        reg_code = config.current_regulation
        reg_data = config.get_regulation(reg_code)

        return {
            "current_regulation": reg_code,
            "name": reg_data.get("name", reg_code),
            "description": reg_data.get("description", ""),
            "restricted_limit": reg_data.get("restricted_limit", 2),
            "item_clause": reg_data.get("item_clause", True),
            "species_clause": reg_data.get("species_clause", True),
            "start_date": reg_data.get("start_date"),
            "end_date": reg_data.get("end_date"),
            "smogon_formats": reg_data.get("smogon_formats", []),
            "message": f"Currently using {reg_data.get('name', reg_code)}"
        }

    @mcp.tool(
        title="List Available Regulations",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def list_available_regulations() -> dict:
        """List all available VGC regulations with key parameters and date ranges.

        Also reports which regulation is currently active.
        """
        config = get_regulation_config()
        regulations = config.list_regulations()

        return {
            "current": config.current_regulation,
            "regulations": regulations,
            "count": len(regulations),
            "message": f"Found {len(regulations)} available regulations. Current: {config.current_regulation}"
        }

    @mcp.tool(
        title="Set Session Regulation",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def set_session_regulation(
        regulation: Annotated[str, Field(
            description="Any reasonable regulation phrasing — 'Reg F'/'F'/'regulation_f', 'Reg G', 'Reg H', 'Reg I', 'Champions'/'Pokemon Champions'/'Reg MB'/'MB', or 'Reg MA'/'MA'",
            min_length=1,
        )],
    ) -> dict:
        """Override the current regulation for this session based on user phrasing.

        Routes natural inputs to the right format system:
        - "Reg F" / "G" / "H" / "I" -> mainline regulations (EVs, 252/508)
        - "Champions" / "Reg MB" -> reg_mb_champs (Stat Points, 32/66;
          current default Champions roster)
        - "Reg MA" -> reg_ma_champs (original Champions roster, subset of MB)

        Champions formats automatically use the matching gen9championsvgc2026regm*
        Smogon JSON files; mainline regulations use the gen9vgc2025/2026
        regulation-specific files. The format system flag flips downstream
        stat / damage calcs to the correct math. Returns confirmation with the
        resolved code and active format system.
        """
        from vgc_mcp_core.rules.regulation_router import (
            describe_regulation,
            resolve_regulation,
        )

        config = get_regulation_config()
        available = config.list_regulation_codes()

        reg_code = resolve_regulation(regulation, config)
        if reg_code is None or not config.set_session_regulation(reg_code):
            return error_response(
                ErrorCodes.INTERNAL_ERROR,
                f"Unknown regulation: {regulation!r}. "
                f"Try 'Reg F', 'Reg G', 'Reg H', 'Reg I', or 'Champions' / 'Reg MA'.",
                available=available,
            )

        info = describe_regulation(reg_code, config)
        info.update({
            "success": True,
            "regulation": reg_code,
            "restricted_limit": config.get_restricted_limit(reg_code),
            "message": (
                f"Session regulation set to {info['name']} "
                f"(format system: {info['format_system']}, units: {info['stat_units']})."
            ),
        })
        return info

    @mcp.tool(
        title="Auto-Detect Regulation From Pokemon",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def auto_detect_regulation_from_pokemon(
        pokemon_names: Annotated[list[str], Field(
            description="Pokemon names from the conversation. Pass whatever the user wrote — Mega forms, restricteds, partial names — the inference normalizes everything",
        )],
    ) -> dict:
        """ZERO-CONFIG REGULATION DETECTION — call this whenever a user mentions
        Pokemon and you don't know the format yet. Combines inference and
        session-set in one call.

        Behavior:
        - If the user already explicitly chose a regulation (via
          set_session_regulation), this is a no-op and returns
          `{"action": "skipped"}` — explicit user choice always wins.
        - Otherwise infers from Pokemon mentions and AUTO-SETS the session
          regulation if confidence is high or medium.
        - Returns action ("set" | "skipped" | "low_confidence"), the regulation
          code, format_system, stat units, confidence, and the reasoning so you
          can mention it to the user (e.g. "I noticed you have a Mega — using
          Champions Reg MA").

        Use when the user pastes a team, asks about a specific Pokemon or
        damage matchup, or anytime the active regulation is unclear.
        """
        from vgc_mcp_core.rules.regulation_router import (
            auto_detect_regulation,
            describe_regulation,
        )
        config = get_regulation_config()
        result = auto_detect_regulation(pokemon_names, config)
        if result.get("regulation"):
            info = describe_regulation(result["regulation"], config)
            result["format_system"] = info["format_system"]
            result["stat_units"] = info["stat_units"]
            result["regulation_name"] = info["name"]
        return result

    @mcp.tool(
        title="Infer Regulation From Team",
        annotations=ToolAnnotations(
            readOnlyHint=True,
            destructiveHint=False,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def infer_regulation_from_team(
        pokemon_names: Annotated[list[str], Field(
            description="Pokemon names from the team. Accepts any common phrasing — 'Mega Kangaskhan', 'Calyrex-Shadow', 'Urshifu Rapid Strike' — form variations are normalized internally",
        )],
    ) -> dict:
        """Infer the most likely VGC regulation from the Pokemon mentioned in a team.

        Use this whenever a user pastes a team or mentions specific Pokemon and
        you don't already know the regulation. Call BEFORE other tools so the
        session can be set with `set_session_regulation` to the inferred code.

        Detection rules (in order of confidence):
        - Any Mega form -> Champions Reg MA (Megas only exist in Champions).
        - Any Pokemon legal in Champions but banned in mainline -> Champions Reg MA.
        - 1 restricted Pokemon -> Reg G; 2+ restricteds -> Reg I (Reg F fallback).
        - 0 restricteds + no Mega -> Reg F primary, Reg MA as alternative.

        Returns the inferred regulation, confidence, reasons, alternatives,
        restricted/illegal Pokemon seen, format system, stat units, and a
        next_step hint. This tool only infers — it never changes the session.
        """
        from vgc_mcp_core.rules.regulation_router import (
            describe_regulation,
            infer_format_from_pokemon,
        )
        config = get_regulation_config()
        result = infer_format_from_pokemon(pokemon_names, config)
        if result.get("regulation"):
            info = describe_regulation(result["regulation"], config)
            result["format_system"] = info["format_system"]
            result["stat_units"] = info["stat_units"]
            result["regulation_name"] = info["name"]
            result["next_step"] = (
                f"Call set_session_regulation('{result['regulation']}') to apply, "
                f"or pass a phrase like 'Reg I' or 'Champions' which the router resolves."
            )
        else:
            result["next_step"] = (
                "Could not determine regulation from Pokemon list. Ask the user "
                "directly which regulation they're playing."
            )
        return result

    @mcp.tool(
        title="Clear Session Regulation",
        annotations=ToolAnnotations(
            readOnlyHint=False,
            destructiveHint=True,
            idempotentHint=True,
            openWorldHint=False,
        ),
    )
    async def clear_session_regulation() -> dict:
        """Clear the session regulation override.

        Reverts to the default regulation detection (date-based or explicit
        configuration setting). Returns confirmation with the now-active
        regulation.
        """
        config = get_regulation_config()
        config.clear_session_override()

        return {
            "success": True,
            "current_regulation": config.current_regulation,
            "message": f"Session override cleared. Now using: {config.current_regulation}"
        }
