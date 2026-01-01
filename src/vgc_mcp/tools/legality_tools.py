"""MCP tools for VGC format legality checking."""

from typing import Optional
from mcp.server.fastmcp import FastMCP

from vgc_mcp_core.rules.regulation_loader import get_regulation_config
from vgc_mcp_core.rules.vgc_rules import get_regulation, list_regulations, validate_team_rules
from vgc_mcp_core.rules.restricted import (
    is_restricted, is_banned, count_restricted,
    find_banned, get_restricted_status, find_restricted,
    get_pokemon_legality
)
from vgc_mcp_core.rules.item_clause import check_item_clause, get_duplicate_items, suggest_alternative_items


def register_legality_tools(mcp: FastMCP, team_manager):
    """Register VGC legality checking tools with the MCP server."""

    @mcp.tool()
    async def validate_team_legality(regulation: Optional[str] = None) -> dict:
        """
        Validate full team legality for VGC tournament play.

        Checks:
        - Restricted Pokemon count (max 2 for Reg F, 1 for Reg G, 0 for Reg H)
        - Banned Pokemon (mythicals)
        - Item clause (no duplicate items)
        - Species clause (no duplicate species)
        - Team size (max 6)

        Args:
            regulation: VGC regulation to validate against (reg_f, reg_g, reg_h).
                       If None, uses the current regulation.

        Returns:
            Complete legality report with any violations
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        team = team_manager.get_current_team()

        if not team or len(team.slots) == 0:
            return {
                "valid": False,
                "error": "No team to validate. Add Pokemon first.",
                "regulation": reg_code
            }

        # Get regulation rules
        reg = get_regulation(reg_code)
        if not reg:
            available = config.list_regulation_codes()
            return {
                "valid": False,
                "error": f"Unknown regulation: {reg_code}. Valid: {', '.join(available)}"
            }

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

    @mcp.tool()
    async def check_restricted_count(regulation: Optional[str] = None) -> dict:
        """
        Check how many restricted (box legend) Pokemon are on the team.

        Restricted Pokemon include Koraidon, Miraidon, Kyogre, Groudon, etc.
        Different regulations have different limits.

        Args:
            regulation: VGC regulation (reg_f allows 2, reg_g allows 1, reg_h allows 0).
                       If None, uses the current regulation.

        Returns:
            Count of restricted Pokemon and whether it's within limits
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
            return {"error": f"Unknown regulation: {reg_code}"}

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

    @mcp.tool()
    async def check_item_clause_tool() -> dict:
        """
        Check if the team violates the item clause (no duplicate items).

        In VGC, each Pokemon must hold a different item.

        Returns:
            Validation result with any duplicate items found
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

    @mcp.tool()
    async def get_format_rules(regulation: Optional[str] = None) -> dict:
        """
        Get the rules for a specific VGC regulation.

        Args:
            regulation: VGC regulation (reg_f, reg_g, reg_h).
                       If None, uses the current regulation.

        Returns:
            Full rule set for the regulation
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

        reg = get_regulation(reg_code)

        if not reg:
            available = config.list_regulation_codes()
            return {
                "error": f"Unknown regulation: {reg_code}",
                "available": available
            }

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

    @mcp.tool()
    async def check_pokemon_legality(
        pokemon_name: str,
        regulation: Optional[str] = None
    ) -> dict:
        """
        Check if a specific Pokemon is legal, restricted, or banned.

        Args:
            pokemon_name: Name of the Pokemon to check
            regulation: VGC regulation to check against.
                       If None, uses the current regulation.

        Returns:
            Legality status and any restrictions
        """
        config = get_regulation_config()
        reg_code = regulation or config.current_regulation

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

    @mcp.tool()
    async def suggest_item_alternatives(
        item_name: str,
        pokemon_role: Optional[str] = None
    ) -> dict:
        """
        Suggest alternative items when there's a duplicate.

        Args:
            item_name: The duplicated item
            pokemon_role: Optional role hint (attacker, support, etc.)

        Returns:
            List of alternative item suggestions
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

    @mcp.tool()
    async def list_restricted_pokemon(regulation: Optional[str] = None) -> dict:
        """
        List all restricted (box legend) Pokemon for VGC.

        Args:
            regulation: VGC regulation. If None, uses the current regulation.

        Returns:
            Complete list of restricted Pokemon for the regulation
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

    @mcp.tool()
    async def list_banned_pokemon(regulation: Optional[str] = None) -> dict:
        """
        List all banned Pokemon for VGC.

        Banned Pokemon are typically mythicals that cannot be used
        in official VGC tournaments.

        Args:
            regulation: VGC regulation. If None, uses the current regulation.

        Returns:
            Complete list of banned Pokemon
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

    @mcp.tool()
    async def get_current_regulation_info() -> dict:
        """
        Get information about the currently active VGC regulation.

        Returns the regulation that is currently in effect based on date
        or manual override setting.

        Returns:
            Current regulation details including rules and dates
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

    @mcp.tool()
    async def list_available_regulations() -> dict:
        """
        List all available VGC regulations.

        Shows all regulations that can be used, with their key parameters
        and date ranges.

        Returns:
            List of all available regulations with summary info
        """
        config = get_regulation_config()
        regulations = config.list_regulations()

        return {
            "current": config.current_regulation,
            "regulations": regulations,
            "count": len(regulations),
            "message": f"Found {len(regulations)} available regulations. Current: {config.current_regulation}"
        }

    @mcp.tool()
    async def set_session_regulation(regulation: str) -> dict:
        """
        Override the current regulation for this session.

        This temporarily changes which regulation is used for validation
        until the server restarts or this is cleared.

        Args:
            regulation: Regulation code to use (e.g., "reg_f", "reg_g", "reg_h")

        Returns:
            Confirmation of the change
        """
        config = get_regulation_config()
        available = config.list_regulation_codes()

        # Normalize input
        reg_code = regulation.lower().replace(" ", "_").replace("-", "_")
        if not reg_code.startswith("reg_"):
            reg_code = f"reg_{reg_code}"

        if config.set_session_regulation(reg_code):
            reg_data = config.get_regulation(reg_code)
            return {
                "success": True,
                "regulation": reg_code,
                "name": reg_data.get("name", reg_code),
                "restricted_limit": reg_data.get("restricted_limit", 2),
                "message": f"Session regulation set to {reg_data.get('name', reg_code)}"
            }
        else:
            return {
                "success": False,
                "error": f"Unknown regulation: {regulation}",
                "available": available
            }

    @mcp.tool()
    async def clear_session_regulation() -> dict:
        """
        Clear the session regulation override.

        Reverts to using the default regulation detection (date-based or
        explicit setting in configuration).

        Returns:
            Confirmation with the now-active regulation
        """
        config = get_regulation_config()
        config.clear_session_override()

        return {
            "success": True,
            "current_regulation": config.current_regulation,
            "message": f"Session override cleared. Now using: {config.current_regulation}"
        }
