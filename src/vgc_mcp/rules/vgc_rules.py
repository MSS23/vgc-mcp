"""VGC regulation definitions and rule sets.

This module provides VGC regulation definitions, loading data from the
unified regulations.json configuration file via RegulationConfig.
"""

from dataclasses import dataclass
from typing import Optional

from .regulation_loader import get_regulation_config


@dataclass
class VGCRegulation:
    """Definition of a VGC regulation format."""
    name: str
    code: str  # e.g., "reg_f"
    restricted_limit: int  # Max restricted Pokemon allowed
    item_clause: bool  # No duplicate held items
    species_clause: bool  # No duplicate Pokemon species
    level: int  # Battle level
    pokemon_limit: int  # Max Pokemon on team
    bring_limit: int  # Pokemon brought to each battle
    description: str


def _build_regulation_from_config(code: str) -> Optional[VGCRegulation]:
    """Build a VGCRegulation from the config data."""
    config = get_regulation_config()
    reg_data = config.get_regulation(code)

    if not reg_data:
        return None

    return VGCRegulation(
        name=reg_data.get("name", code),
        code=code,
        restricted_limit=reg_data.get("restricted_limit", 2),
        item_clause=reg_data.get("item_clause", True),
        species_clause=reg_data.get("species_clause", True),
        level=reg_data.get("level", 50),
        pokemon_limit=reg_data.get("pokemon_limit", 6),
        bring_limit=reg_data.get("bring_limit", 4),
        description=reg_data.get("description", "")
    )


def get_regulation(code: str = None) -> Optional[VGCRegulation]:
    """
    Get a VGC regulation by code.

    Args:
        code: Regulation code (e.g., "reg_f"). If None, returns current regulation.

    Returns:
        VGCRegulation or None if not found
    """
    config = get_regulation_config()

    if code is None:
        code = config.current_regulation

    code = code.lower().replace(" ", "_").replace("-", "_")

    # Handle various input formats
    if not code.startswith("reg_"):
        code = f"reg_{code}"

    return _build_regulation_from_config(code)


def list_regulations() -> list[dict]:
    """Get all available regulations with basic info."""
    config = get_regulation_config()
    regulations = []

    for code in config.list_regulation_codes():
        reg = _build_regulation_from_config(code)
        if reg:
            regulations.append({
                "code": reg.code,
                "name": reg.name,
                "restricted_limit": reg.restricted_limit,
                "description": reg.description
            })

    return regulations


def get_current_regulation() -> VGCRegulation:
    """Get the current/default regulation."""
    config = get_regulation_config()
    return _build_regulation_from_config(config.current_regulation)


def validate_team_rules(team, regulation_code: str = None) -> dict:
    """
    Validate a team against VGC regulation rules.

    Args:
        team: Team object to validate
        regulation_code: Regulation to validate against (default: current)

    Returns:
        Dict with validation results
    """
    from .restricted import get_restricted_status, count_restricted, find_banned
    from .item_clause import check_item_clause

    regulation = get_regulation(regulation_code)
    if not regulation:
        return {
            "valid": False,
            "error": f"Unknown regulation: {regulation_code}"
        }

    violations = []
    warnings = []

    # Get Pokemon names and items
    pokemon_names = [slot.pokemon.name for slot in team.slots]
    items = [slot.pokemon.item for slot in team.slots]

    # Check team size
    if len(team.slots) > regulation.pokemon_limit:
        violations.append(f"Team has {len(team.slots)} Pokemon (max {regulation.pokemon_limit})")

    # Check for banned Pokemon
    banned = find_banned(pokemon_names)
    if banned:
        violations.append(f"Banned Pokemon on team: {', '.join(banned)}")

    # Check restricted count
    restricted_count = count_restricted(pokemon_names)
    restricted_pokemon = [name for name in pokemon_names if get_restricted_status(name) == "restricted"]

    if restricted_count > regulation.restricted_limit:
        violations.append(
            f"Too many restricted Pokemon: {restricted_count}/{regulation.restricted_limit} "
            f"({', '.join(restricted_pokemon)})"
        )

    # Check item clause
    if regulation.item_clause:
        item_result = check_item_clause(items)
        if not item_result["valid"]:
            violations.append(item_result["message"])

    # Check species clause
    if regulation.species_clause:
        # Normalize names for comparison (handle forms)
        base_names = []
        for name in pokemon_names:
            # Extract base species (before first hyphen for most forms)
            base = name.lower().split("-")[0]
            base_names.append(base)

        seen = set()
        duplicates = []
        for name in base_names:
            if name in seen:
                duplicates.append(name)
            seen.add(name)

        if duplicates:
            violations.append(f"Species clause violation: duplicate {', '.join(set(duplicates))}")

    return {
        "valid": len(violations) == 0,
        "violations": violations,
        "warnings": warnings,
        "restricted_count": restricted_count,
        "restricted_limit": regulation.restricted_limit,
        "restricted_pokemon": restricted_pokemon,
        "team_size": len(team.slots),
        "message": (
            "Team is legal for " + regulation.name
            if len(violations) == 0
            else f"Team has {len(violations)} violation(s)"
        )
    }
