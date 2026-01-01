"""UI component builders for VGC Team Builder.

Creates HTML strings for various UI components that can be
embedded in MCP UI resources.
"""

from typing import Any, Optional
from pathlib import Path

# Load shared styles
STYLES_PATH = Path(__file__).parent / "templates" / "shared" / "styles.css"


def get_shared_styles() -> str:
    """Load shared CSS styles."""
    try:
        return STYLES_PATH.read_text()
    except FileNotFoundError:
        return ""


def get_sprite_url(pokemon_name: str) -> str:
    """Get Pokemon sprite URL from PokemonDB."""
    # Normalize name for URL
    normalized = pokemon_name.lower().replace(" ", "-").replace(".", "")
    # Handle special forms
    if normalized.startswith("urshifu"):
        if "rapid" in normalized:
            normalized = "urshifu-rapid-strike"
        else:
            normalized = "urshifu"
    return f"https://img.pokemondb.net/sprites/home/normal/{normalized}.png"


def get_type_color(type_name: str) -> str:
    """Get CSS color for a Pokemon type."""
    type_colors = {
        "normal": "#A8A878",
        "fire": "#F08030",
        "water": "#6890F0",
        "electric": "#F8D030",
        "grass": "#78C850",
        "ice": "#98D8D8",
        "fighting": "#C03028",
        "poison": "#A040A0",
        "ground": "#E0C068",
        "flying": "#A890F0",
        "psychic": "#F85888",
        "bug": "#A8B820",
        "rock": "#B8A038",
        "ghost": "#705898",
        "dragon": "#7038F8",
        "dark": "#705848",
        "steel": "#B8B8D0",
        "fairy": "#EE99AC",
    }
    return type_colors.get(type_name.lower(), "#888888")


def create_damage_calc_ui(
    attacker: str,
    defender: str,
    move: str,
    damage_min: float,
    damage_max: float,
    ko_chance: str,
    type_effectiveness: float = 1.0,
    attacker_item: Optional[str] = None,
    defender_item: Optional[str] = None,
    move_type: Optional[str] = None,
    notes: Optional[list[str]] = None,
) -> str:
    """Create damage calculator UI HTML.

    Args:
        attacker: Attacking Pokemon name
        defender: Defending Pokemon name
        move: Move used
        damage_min: Minimum damage percentage
        damage_max: Maximum damage percentage
        ko_chance: KO probability string (e.g., "Guaranteed OHKO")
        type_effectiveness: Type effectiveness multiplier
        attacker_item: Attacker's held item
        defender_item: Defender's held item
        move_type: Type of the move
        notes: Additional notes to display

    Returns:
        HTML string for the damage calc UI
    """
    styles = get_shared_styles()

    # Determine KO badge class and color
    ko_class = "survive"
    if "OHKO" in ko_chance.upper():
        ko_class = "ohko"
    elif "2HKO" in ko_chance.upper():
        ko_class = "2hko"
    elif "3HKO" in ko_chance.upper():
        ko_class = "3hko"

    # Type effectiveness display
    eff_text = "Neutral"
    eff_color = "#888"
    if type_effectiveness >= 4:
        eff_text = "4x Super Effective"
        eff_color = "#f44336"
    elif type_effectiveness >= 2:
        eff_text = "Super Effective"
        eff_color = "#4caf50"
    elif type_effectiveness <= 0:
        eff_text = "Immune"
        eff_color = "#666"
    elif type_effectiveness <= 0.25:
        eff_text = "4x Resisted"
        eff_color = "#f44336"
    elif type_effectiveness <= 0.5:
        eff_text = "Resisted"
        eff_color = "#ff9800"

    # Build notes HTML
    notes_html = ""
    if notes:
        notes_html = '<div class="mt-2 text-muted" style="font-size: 12px;">'
        for note in notes:
            notes_html += f"<div>• {note}</div>"
        notes_html += "</div>"

    # Item display
    attacker_item_html = f'<div style="font-size: 11px; color: #a0a0a0;">@ {attacker_item}</div>' if attacker_item else ""
    defender_item_html = f'<div style="font-size: 11px; color: #a0a0a0;">@ {defender_item}</div>' if defender_item else ""

    # Move type badge
    move_type_html = ""
    if move_type:
        move_color = get_type_color(move_type)
        move_type_html = f'<span class="type-badge" style="background: {move_color}; font-size: 10px;">{move_type.upper()}</span>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{styles}</style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">Damage Calculation</span>
            <span class="ko-badge {ko_class}">{ko_chance}</span>
        </div>

        <div class="flex gap-2 items-center" style="margin-bottom: 16px;">
            <!-- Attacker -->
            <div style="flex: 1; text-align: center;">
                <img src="{get_sprite_url(attacker)}" class="pokemon-sprite" alt="{attacker}" style="width: 80px; height: 80px;">
                <div class="pokemon-name">{attacker}</div>
                {attacker_item_html}
            </div>

            <!-- Arrow and move -->
            <div style="text-align: center; padding: 0 16px;">
                <div style="font-size: 24px; color: #4da6ff;">→</div>
                <div style="font-size: 14px; font-weight: 600;">{move}</div>
                {move_type_html}
            </div>

            <!-- Defender -->
            <div style="flex: 1; text-align: center;">
                <img src="{get_sprite_url(defender)}" class="pokemon-sprite" alt="{defender}" style="width: 80px; height: 80px;">
                <div class="pokemon-name">{defender}</div>
                {defender_item_html}
            </div>
        </div>

        <!-- Damage bar -->
        <div class="damage-bar-container">
            <div class="damage-bar">
                <div class="damage-bar-range" style="left: {damage_min}%; width: {damage_max - damage_min}%;"></div>
                <div class="damage-bar-fill" style="width: {damage_max}%;"></div>
            </div>
            <div class="damage-label">
                <span>{damage_min:.1f}% - {damage_max:.1f}%</span>
                <span style="color: {eff_color};">{eff_text}</span>
            </div>
        </div>

        {notes_html}
    </div>
</body>
</html>"""


def create_team_roster_ui(
    team: list[dict[str, Any]],
    team_name: Optional[str] = None,
) -> str:
    """Create team roster UI HTML.

    Args:
        team: List of Pokemon dicts with keys: name, item, ability, moves, evs, types, tera_type
        team_name: Optional team name

    Returns:
        HTML string for the team roster UI
    """
    styles = get_shared_styles()

    # Build Pokemon cards
    cards_html = ""
    for i, pokemon in enumerate(team):
        name = pokemon.get("name", "Unknown")
        item = pokemon.get("item", "None")
        ability = pokemon.get("ability", "Unknown")
        moves = pokemon.get("moves", [])
        evs = pokemon.get("evs", {})
        types = pokemon.get("types", [])
        tera_type = pokemon.get("tera_type")

        # Type badges
        type_badges = " ".join(
            f'<span class="type-badge type-{t.lower()}">{t}</span>'
            for t in types
        )

        # Tera type if different
        tera_html = ""
        if tera_type and tera_type.lower() not in [t.lower() for t in types]:
            tera_color = get_type_color(tera_type)
            tera_html = f'<span class="type-badge" style="background: {tera_color}; border: 1px dashed white;">Tera {tera_type}</span>'

        # Moves
        moves_html = ""
        for move_data in moves[:4]:
            if isinstance(move_data, dict):
                move_name = move_data.get("name", "Unknown")
                move_type = move_data.get("type", "normal")
            else:
                move_name = str(move_data)
                move_type = "normal"
            move_color = get_type_color(move_type)
            moves_html += f'<span class="move-tag" style="background: {move_color};">{move_name}</span>'

        # EVs summary
        ev_parts = []
        for stat, val in evs.items():
            if val and val > 0:
                stat_abbr = {"hp": "HP", "attack": "Atk", "defense": "Def", "special_attack": "SpA", "special_defense": "SpD", "speed": "Spe"}.get(stat, stat)
                ev_parts.append(f"{val} {stat_abbr}")
        evs_text = " / ".join(ev_parts[:3]) if ev_parts else "No EVs"
        if len(ev_parts) > 3:
            evs_text += f" (+{len(ev_parts) - 3} more)"

        cards_html += f"""
        <div class="pokemon-card">
            <img src="{get_sprite_url(name)}" class="pokemon-sprite" alt="{name}">
            <div class="pokemon-info">
                <div class="pokemon-name">{name}</div>
                <div style="margin: 4px 0;">{type_badges} {tera_html}</div>
                <div class="pokemon-item">@ {item}</div>
                <div style="font-size: 11px; color: #a0a0a0;">{ability}</div>
                <div class="move-list mt-2">{moves_html}</div>
                <div style="font-size: 11px; color: #666; margin-top: 4px;">{evs_text}</div>
            </div>
        </div>
        """

    # Team header
    header_text = team_name if team_name else f"Team ({len(team)}/6)"
    slots_remaining = 6 - len(team)
    slots_html = f'<span class="text-muted">{slots_remaining} slots remaining</span>' if slots_remaining > 0 else ""

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{styles}</style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">{header_text}</span>
            {slots_html}
        </div>
        <div class="team-grid">
            {cards_html}
        </div>
    </div>
</body>
</html>"""


def create_speed_tier_ui(
    pokemon_name: str,
    pokemon_speed: int,
    speed_tiers: list[dict[str, Any]],
    modifiers: Optional[dict[str, bool]] = None,
) -> str:
    """Create speed tier analyzer UI HTML.

    Args:
        pokemon_name: Name of the Pokemon being analyzed
        pokemon_speed: Calculated speed stat
        speed_tiers: List of dicts with keys: name, speed, common (bool)
        modifiers: Active modifiers dict (tailwind, trick_room, paralysis, choice_scarf)

    Returns:
        HTML string for the speed tier UI
    """
    styles = get_shared_styles()
    modifiers = modifiers or {}

    # Build modifier badges
    mod_badges = ""
    if modifiers.get("tailwind"):
        mod_badges += '<span class="ko-badge" style="background: #4da6ff;">Tailwind (2x)</span> '
    if modifiers.get("trick_room"):
        mod_badges += '<span class="ko-badge" style="background: #f85888;">Trick Room</span> '
    if modifiers.get("paralysis"):
        mod_badges += '<span class="ko-badge" style="background: #f8d030; color: #333;">Paralyzed (0.5x)</span> '
    if modifiers.get("choice_scarf"):
        mod_badges += '<span class="ko-badge" style="background: #ff9800;">Choice Scarf (1.5x)</span> '

    # Sort tiers by speed (descending, or ascending for Trick Room)
    sorted_tiers = sorted(speed_tiers, key=lambda x: x.get("speed", 0), reverse=not modifiers.get("trick_room"))

    # Build tier rows
    tiers_html = ""
    user_found = False

    for tier in sorted_tiers:
        tier_name = tier.get("name", "Unknown")
        tier_speed = tier.get("speed", 0)
        is_common = tier.get("common", False)

        # Determine if this is faster/slower than user's Pokemon
        if modifiers.get("trick_room"):
            is_faster = tier_speed < pokemon_speed
        else:
            is_faster = tier_speed > pokemon_speed

        # Check if this is the user's Pokemon position
        is_current = tier_name.lower() == pokemon_name.lower()

        # Insert user's Pokemon in correct position
        if not user_found and not is_faster and not is_current:
            user_found = True
            tiers_html += f"""
            <div class="speed-tier current">
                <span class="speed-value">{pokemon_speed}</span>
                <span class="speed-pokemon">{pokemon_name} ★</span>
            </div>
            """

        tier_class = "current" if is_current else ("faster" if is_faster else "slower")
        common_badge = '<span style="font-size: 10px; color: #4caf50;">●</span>' if is_common else ""

        tiers_html += f"""
        <div class="speed-tier {tier_class}">
            <span class="speed-value">{tier_speed}</span>
            <span class="speed-pokemon">{tier_name} {common_badge}</span>
        </div>
        """

    # If user's Pokemon is slowest, add at end
    if not user_found:
        tiers_html += f"""
        <div class="speed-tier current">
            <span class="speed-value">{pokemon_speed}</span>
            <span class="speed-pokemon">{pokemon_name} ★</span>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{styles}</style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">Speed Tier Analysis</span>
            <div>{mod_badges}</div>
        </div>
        <div style="font-size: 12px; color: #a0a0a0; margin-bottom: 8px;">
            <span style="color: #f44336;">●</span> Faster
            <span style="color: #4da6ff; margin-left: 12px;">●</span> Your Pokemon
            <span style="color: #4caf50; margin-left: 12px;">●</span> Slower
        </div>
        <div style="max-height: 400px; overflow-y: auto;">
            {tiers_html}
        </div>
    </div>
</body>
</html>"""


def create_coverage_ui(
    pokemon_name: str,
    moves: list[dict[str, Any]],
    coverage: dict[str, float],
) -> str:
    """Create type coverage analyzer UI HTML.

    Args:
        pokemon_name: Name of the Pokemon
        moves: List of move dicts with keys: name, type, power
        coverage: Dict mapping type names to effectiveness multipliers

    Returns:
        HTML string for the coverage UI
    """
    styles = get_shared_styles()

    all_types = [
        "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
        "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
        "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
    ]

    # Build moves display
    moves_html = ""
    for move in moves:
        move_name = move.get("name", "Unknown")
        move_type = move.get("type", "normal")
        power = move.get("power", "-")
        move_color = get_type_color(move_type)
        moves_html += f"""
        <div style="display: inline-flex; align-items: center; margin: 4px; padding: 4px 8px; background: {move_color}; border-radius: 4px;">
            <span style="font-weight: 600;">{move_name}</span>
            <span style="margin-left: 8px; font-size: 11px; opacity: 0.8;">{power} BP</span>
        </div>
        """

    # Build coverage grid
    grid_html = ""
    for type_name in all_types:
        eff = coverage.get(type_name.lower(), 1.0)

        # Determine cell class and text
        if eff >= 2:
            cell_class = "super"
            text = "2x"
        elif eff == 0:
            cell_class = "immune"
            text = "0"
        elif eff < 1:
            cell_class = "resist"
            text = "½"
        else:
            cell_class = "neutral"
            text = "1x"

        type_color = get_type_color(type_name)
        grid_html += f"""
        <div class="coverage-cell {cell_class}" title="{type_name}: {eff}x" style="border: 2px solid {type_color};">
            <span style="font-size: 9px;">{type_name[:3].upper()}</span>
        </div>
        """

    # Count coverage stats
    super_eff = sum(1 for e in coverage.values() if e >= 2)
    neutral = sum(1 for e in coverage.values() if e == 1)
    resisted = sum(1 for e in coverage.values() if 0 < e < 1)
    immune = sum(1 for e in coverage.values() if e == 0)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{styles}</style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">{pokemon_name} Coverage</span>
        </div>

        <div style="margin-bottom: 16px;">
            {moves_html}
        </div>

        <div class="coverage-grid">
            {grid_html}
        </div>

        <div class="flex justify-between mt-2" style="font-size: 12px;">
            <span style="color: #4caf50;">Super: {super_eff}</span>
            <span style="color: #888;">Neutral: {neutral}</span>
            <span style="color: #ff9800;">Resisted: {resisted}</span>
            <span style="color: #666;">Immune: {immune}</span>
        </div>
    </div>
</body>
</html>"""


def create_matchup_summary_ui(
    pokemon_name: str,
    matchups: list[dict[str, Any]],
) -> str:
    """Create matchup summary UI HTML.

    Args:
        pokemon_name: Name of the Pokemon being analyzed
        matchups: List of matchup dicts with keys: opponent, damage_taken, damage_dealt, verdict

    Returns:
        HTML string for the matchup summary UI
    """
    styles = get_shared_styles()

    # Build matchup rows
    rows_html = ""
    for matchup in matchups:
        opponent = matchup.get("opponent", "Unknown")
        dmg_taken = matchup.get("damage_taken", "?")
        dmg_dealt = matchup.get("damage_dealt", "?")
        verdict = matchup.get("verdict", "neutral")

        # Verdict styling
        if verdict == "favorable":
            row_color = "rgba(76, 175, 80, 0.1)"
            indicator = "🟢"
        elif verdict == "unfavorable":
            row_color = "rgba(244, 67, 54, 0.1)"
            indicator = "🔴"
        else:
            row_color = "transparent"
            indicator = "🟡"

        rows_html += f"""
        <div style="display: flex; align-items: center; padding: 8px; background: {row_color}; border-radius: 4px; margin: 4px 0;">
            <span style="font-size: 16px; margin-right: 8px;">{indicator}</span>
            <img src="{get_sprite_url(opponent)}" style="width: 40px; height: 40px; margin-right: 8px;">
            <div style="flex: 1;">
                <div style="font-weight: 500;">{opponent}</div>
                <div style="font-size: 11px; color: #a0a0a0;">
                    Takes: {dmg_taken} | Deals: {dmg_dealt}
                </div>
            </div>
        </div>
        """

    # Count verdicts
    favorable = sum(1 for m in matchups if m.get("verdict") == "favorable")
    unfavorable = sum(1 for m in matchups if m.get("verdict") == "unfavorable")
    neutral = len(matchups) - favorable - unfavorable

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>{styles}</style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">{pokemon_name} Matchups</span>
            <div style="font-size: 12px;">
                <span style="color: #4caf50;">✓ {favorable}</span>
                <span style="color: #888; margin: 0 8px;">~ {neutral}</span>
                <span style="color: #f44336;">✗ {unfavorable}</span>
            </div>
        </div>
        <div style="max-height: 350px; overflow-y: auto;">
            {rows_html}
        </div>
    </div>
</body>
</html>"""
