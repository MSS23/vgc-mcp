# -*- coding: utf-8 -*-
"""Pokemon sprite and type color utilities."""


def get_sprite_url(pokemon_name: str, animated: bool = True) -> str:
    """Get Pokemon sprite URL - animated GIF from Showdown or static PNG fallback.

    Args:
        pokemon_name: Name of the Pokemon
        animated: If True, returns animated GIF from Pokemon Showdown.
                  If False, returns static PNG from PokemonDB.

    Returns:
        URL string for the Pokemon sprite
    """
    if animated:
        # Pokemon Showdown format: no spaces, forms use single hyphen
        # "Flutter Mane" -> "fluttermane"
        # "Urshifu-Rapid-Strike" -> "urshifu-rapidstrike"
        normalized = pokemon_name.lower().replace(" ", "").replace(".", "")

        # Collapse form hyphens: "rapid-strike" -> "rapidstrike"
        # But keep the base-form hyphen: "urshifu-rapidstrike"
        parts = normalized.split("-")
        if len(parts) >= 2:
            base = parts[0]
            form = "".join(parts[1:])
            normalized = f"{base}-{form}" if form else base

        return f"https://play.pokemonshowdown.com/sprites/ani/{normalized}.gif"
    else:
        # PokemonDB format: hyphenated names
        # "Flutter Mane" -> "flutter-mane"
        normalized = pokemon_name.lower().replace(" ", "-").replace(".", "")
        # Handle Urshifu forms for PokemonDB
        if normalized.startswith("urshifu"):
            if "rapid" in normalized:
                normalized = "urshifu-rapid-strike"
            else:
                normalized = "urshifu"
        return f"https://img.pokemondb.net/sprites/home/normal/{normalized}.png"


# SVG placeholder for broken sprites - simple pokeball silhouette
SPRITE_PLACEHOLDER = "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'%3E%3Ccircle cx='48' cy='48' r='40' fill='%23333' stroke='%23555' stroke-width='3'/%3E%3Cline x1='8' y1='48' x2='88' y2='48' stroke='%23555' stroke-width='3'/%3E%3Ccircle cx='48' cy='48' r='10' fill='%23555' stroke='%23666' stroke-width='2'/%3E%3C/svg%3E"


def get_sprite_html(
    pokemon_name: str,
    size: int = 80,
    css_class: str = "pokemon-sprite",
    animated: bool = True
) -> str:
    """Create a sprite img element with proper fallback handling.

    Includes onerror fallback to static sprite and placeholder if both fail.

    Args:
        pokemon_name: Name of the Pokemon
        size: Size in pixels (default 80)
        css_class: CSS class for the img element
        animated: Whether to try animated sprite first

    Returns:
        HTML img element string with fallback chain
    """
    primary_url = get_sprite_url(pokemon_name, animated=True)
    fallback_url = get_sprite_url(pokemon_name, animated=False)

    # Escape quotes in pokemon name for alt text
    safe_name = pokemon_name.replace("'", "&#39;").replace('"', "&quot;")

    return f'''<img src="{primary_url}" alt="{safe_name}" class="{css_class}" style="width:{size}px;height:{size}px;" onerror="if(this.src!=='{fallback_url}'){{this.src='{fallback_url}';}}else{{this.src='{SPRITE_PLACEHOLDER}';this.style.opacity='0.4';}}">'''


# Type color mapping
TYPE_COLORS = {
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
    "stellar": "#44AAFF",
}


def get_type_color(type_name: str) -> str:
    """Get CSS color for a Pokemon type."""
    return TYPE_COLORS.get(type_name.lower(), "#888888")
