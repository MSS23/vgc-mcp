# -*- coding: utf-8 -*-
"""UI component builders for VGC Team Builder.

Creates HTML strings for various UI components that can be
embedded in MCP UI resources.
"""

import json
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
    interactive: bool = False,
    attacker_evs: Optional[dict[str, int]] = None,
    defender_evs: Optional[dict[str, int]] = None,
    attacker_nature: str = "Serious",
    defender_nature: str = "Serious",
    attacker_base_stats: Optional[dict[str, int]] = None,
    defender_base_stats: Optional[dict[str, int]] = None,
    move_category: str = "special",
    move_power: int = 0,
    attacker_types: Optional[list[str]] = None,
    defender_types: Optional[list[str]] = None,
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
        interactive: If True, shows EV sliders and nature dropdowns for adjustment.
                    If False, shows a simple static damage display.
        attacker_evs: Attacker EV spread dict (only used when interactive=True)
        defender_evs: Defender EV spread dict (only used when interactive=True)
        attacker_nature: Attacker's nature (only used when interactive=True)
        defender_nature: Defender's nature (only used when interactive=True)
        attacker_base_stats: Attacker's base stats (only used when interactive=True)
        defender_base_stats: Defender's base stats (only used when interactive=True)
        move_category: "physical" or "special" (only used when interactive=True)
        move_power: Base power of the move (only used when interactive=True)

    Returns:
        HTML string for the damage calc UI
    """
    # Static (non-interactive) version - simpler and lightweight
    if not interactive:
        return _create_static_damage_calc_ui(
            attacker=attacker,
            defender=defender,
            move=move,
            damage_min=damage_min,
            damage_max=damage_max,
            ko_chance=ko_chance,
            type_effectiveness=type_effectiveness,
            attacker_item=attacker_item,
            defender_item=defender_item,
            move_type=move_type,
            notes=notes,
        )

    # Interactive version with EV sliders and nature dropdowns
    # Default EVs if not provided
    attacker_evs = attacker_evs or {"hp": 0, "attack": 0, "defense": 0, "special_attack": 252, "special_defense": 0, "speed": 252}
    defender_evs = defender_evs or {"hp": 252, "attack": 0, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 0}
    attacker_base_stats = attacker_base_stats or {"hp": 100, "attack": 100, "defense": 100, "special_attack": 100, "special_defense": 100, "speed": 100}
    defender_base_stats = defender_base_stats or {"hp": 100, "attack": 100, "defense": 100, "special_attack": 100, "special_defense": 100, "speed": 100}
    attacker_types = attacker_types or ["Normal"]
    defender_types = defender_types or ["Normal"]

    # Determine KO badge class
    ko_class = "survive"
    if "OHKO" in ko_chance.upper():
        ko_class = "ohko"
    elif "2HKO" in ko_chance.upper():
        ko_class = "2hko"
    elif "3HKO" in ko_chance.upper():
        ko_class = "3hko"

    # Type effectiveness display
    eff_text = "Neutral"
    eff_class = "neutral"
    if type_effectiveness >= 4:
        eff_text = "4x Super Effective"
        eff_class = "super4x"
    elif type_effectiveness >= 2:
        eff_text = "Super Effective"
        eff_class = "super"
    elif type_effectiveness <= 0:
        eff_text = "Immune"
        eff_class = "immune"
    elif type_effectiveness <= 0.25:
        eff_text = "4x Resisted"
        eff_class = "resist4x"
    elif type_effectiveness <= 0.5:
        eff_text = "Resisted"
        eff_class = "resist"

    # Move type color
    move_color = get_type_color(move_type) if move_type else "#888"

    # Nature options
    natures = ["Adamant", "Bold", "Brave", "Calm", "Careful", "Gentle", "Hasty",
               "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive",
               "Naughty", "Quiet", "Rash", "Relaxed", "Sassy", "Serious", "Timid"]

    attacker_nature_options = "".join(
        f'<option value="{n}" {"selected" if n == attacker_nature else ""}>{n}</option>'
        for n in natures
    )
    defender_nature_options = "".join(
        f'<option value="{n}" {"selected" if n == defender_nature else ""}>{n}</option>'
        for n in natures
    )

    # Ability options for damage calculation
    offensive_abilities = [
        ("adaptability", "Adaptability (2x STAB)"),
        ("huge-power", "Huge Power (2x Atk)"),
        ("pure-power", "Pure Power (2x Atk)"),
        ("gorilla-tactics", "Gorilla Tactics (1.5x Atk)"),
        ("hustle", "Hustle (1.5x Atk)"),
        ("guts", "Guts (1.5x Atk when statused)"),
        ("technician", "Technician (1.5x if BP<=60)"),
        ("sheer-force", "Sheer Force (1.3x)"),
        ("tough-claws", "Tough Claws (1.3x contact)"),
        ("analytic", "Analytic (1.3x moving last)"),
        ("iron-fist", "Iron Fist (1.2x punch)"),
        ("reckless", "Reckless (1.2x recoil)"),
        ("strong-jaw", "Strong Jaw (1.5x bite)"),
        ("mega-launcher", "Mega Launcher (1.5x pulse)"),
        ("sharpness", "Sharpness (1.5x slicing)"),
        ("rocky-payload", "Rocky Payload (1.5x Rock)"),
        ("transistor", "Transistor (1.3x Electric)"),
        ("dragons-maw", "Dragon's Maw (1.5x Dragon)"),
        ("steelworker", "Steelworker (1.5x Steel)"),
        ("steely-spirit", "Steely Spirit (1.5x Steel)"),
        ("water-bubble", "Water Bubble (2x Water)"),
        ("sand-force", "Sand Force (1.3x in Sand)"),
        ("neuroforce", "Neuroforce (1.25x SE)"),
        ("tinted-lens", "Tinted Lens (2x NVE)"),
        ("supreme-overlord", "Supreme Overlord"),
    ]
    defensive_abilities = [
        ("multiscale", "Multiscale (0.5x at full HP)"),
        ("shadow-shield", "Shadow Shield (0.5x at full)"),
        ("ice-scales", "Ice Scales (0.5x special)"),
        ("fur-coat", "Fur Coat (0.5x physical)"),
        ("filter", "Filter (0.75x SE)"),
        ("solid-rock", "Solid Rock (0.75x SE)"),
        ("prism-armor", "Prism Armor (0.75x SE)"),
        ("thick-fat", "Thick Fat (0.5x Fire/Ice)"),
        ("heatproof", "Heatproof (0.5x Fire)"),
        ("fluffy", "Fluffy (0.5x contact)"),
        ("punk-rock", "Punk Rock (0.5x sound)"),
        ("purifying-salt", "Purifying Salt (0.5x Ghost)"),
        ("water-bubble-def", "Water Bubble (0.5x Fire)"),
        ("tera-shell", "Tera Shell (all NVE at full HP)"),
    ]

    attacker_ability_options = '<option value="">(None)</option>'
    attacker_ability_options += '<optgroup label="Offensive">'
    for val, label in offensive_abilities:
        attacker_ability_options += f'<option value="{val}">{label}</option>'
    attacker_ability_options += '</optgroup>'

    defender_ability_options = '<option value="">(None)</option>'
    defender_ability_options += '<optgroup label="Defensive">'
    for val, label in defensive_abilities:
        defender_ability_options += f'<option value="{val}">{label}</option>'
    defender_ability_options += '</optgroup>'

    # Type options for Tera
    tera_types = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
                  "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
                  "Dragon", "Dark", "Steel", "Fairy", "Stellar"]
    tera_type_options = "".join(
        f'<option value="{t.lower()}">{t}</option>' for t in tera_types
    )

    # Common competitive items
    items = [
        "(none)", "Choice Specs", "Choice Band", "Choice Scarf", "Life Orb",
        "Assault Vest", "Focus Sash", "Leftovers", "Sitrus Berry", "Lum Berry",
        "Booster Energy", "Clear Amulet", "Covert Cloak", "Safety Goggles",
        "Rocky Helmet", "Eviolite", "Black Sludge", "Expert Belt", "Muscle Band",
        "Wise Glasses", "Scope Lens", "Wide Lens", "Loaded Dice", "Punching Glove",
        "Miracle Seed", "Charcoal", "Mystic Water", "Magnet", "Never-Melt Ice",
        "Soft Sand", "Sharp Beak", "Poison Barb", "Dragon Fang", "Spell Tag",
        "Twisted Spoon", "Silver Powder", "Hard Stone", "Black Belt", "Silk Scarf",
        "Metal Coat", "Black Glasses", "Fairy Feather"
    ]

    attacker_item_options = "".join(
        f'<option value="{i}" {"selected" if i == attacker_item or (i == "(none)" and not attacker_item) else ""}>{i}</option>'
        for i in items
    )
    defender_item_options = "".join(
        f'<option value="{i}" {"selected" if i == defender_item or (i == "(none)" and not defender_item) else ""}>{i}</option>'
        for i in items
    )

    # Comprehensive competitive moves for VGC with accurate data
    competitive_moves = {
        # Physical moves - Core
        "Close Combat": {"type": "fighting", "power": 120, "category": "physical"},
        "Earthquake": {"type": "ground", "power": 100, "category": "physical", "spread": True},
        "Rock Slide": {"type": "rock", "power": 75, "category": "physical", "spread": True},
        "Knock Off": {"type": "dark", "power": 65, "category": "physical"},
        "U-turn": {"type": "bug", "power": 70, "category": "physical"},
        "Brave Bird": {"type": "flying", "power": 120, "category": "physical"},
        "Flare Blitz": {"type": "fire", "power": 120, "category": "physical"},
        "Iron Head": {"type": "steel", "power": 80, "category": "physical"},
        "Play Rough": {"type": "fairy", "power": 90, "category": "physical"},
        "Icicle Crash": {"type": "ice", "power": 85, "category": "physical"},
        "Headlong Rush": {"type": "ground", "power": 120, "category": "physical"},
        "Sacred Sword": {"type": "fighting", "power": 90, "category": "physical"},
        "Stomping Tantrum": {"type": "ground", "power": 75, "category": "physical"},
        "Sucker Punch": {"type": "dark", "power": 70, "category": "physical"},
        "Extreme Speed": {"type": "normal", "power": 80, "category": "physical"},
        "Aqua Jet": {"type": "water", "power": 40, "category": "physical"},
        "Ice Shard": {"type": "ice", "power": 40, "category": "physical"},
        "Mach Punch": {"type": "fighting", "power": 40, "category": "physical"},
        "Bullet Punch": {"type": "steel", "power": 40, "category": "physical"},
        "Crunch": {"type": "dark", "power": 80, "category": "physical"},
        "Waterfall": {"type": "water", "power": 80, "category": "physical"},
        "Ice Punch": {"type": "ice", "power": 75, "category": "physical"},
        "Thunder Punch": {"type": "electric", "power": 75, "category": "physical"},
        "Fire Punch": {"type": "fire", "power": 75, "category": "physical"},
        "Drain Punch": {"type": "fighting", "power": 75, "category": "physical"},
        "Poison Jab": {"type": "poison", "power": 80, "category": "physical"},
        "Wild Charge": {"type": "electric", "power": 90, "category": "physical"},
        "Wood Hammer": {"type": "grass", "power": 120, "category": "physical"},
        "Power Whip": {"type": "grass", "power": 120, "category": "physical"},
        "Stone Edge": {"type": "rock", "power": 100, "category": "physical"},
        "Outrage": {"type": "dragon", "power": 120, "category": "physical"},
        "Dragon Claw": {"type": "dragon", "power": 80, "category": "physical"},
        "X-Scissor": {"type": "bug", "power": 80, "category": "physical"},
        "Lunge": {"type": "bug", "power": 80, "category": "physical"},
        "Superpower": {"type": "fighting", "power": 120, "category": "physical"},
        "High Horsepower": {"type": "ground", "power": 95, "category": "physical"},
        "Drill Run": {"type": "ground", "power": 80, "category": "physical"},
        "Poltergeist": {"type": "ghost", "power": 110, "category": "physical"},
        "Shadow Claw": {"type": "ghost", "power": 70, "category": "physical"},
        "Psychic Fangs": {"type": "psychic", "power": 85, "category": "physical"},
        "Zen Headbutt": {"type": "psychic", "power": 80, "category": "physical"},
        "Acrobatics": {"type": "flying", "power": 55, "category": "physical"},
        "Aerial Ace": {"type": "flying", "power": 60, "category": "physical"},
        "Flip Turn": {"type": "water", "power": 60, "category": "physical"},
        "Volt Switch": {"type": "electric", "power": 70, "category": "special"},
        "Facade": {"type": "normal", "power": 70, "category": "physical"},
        "Return": {"type": "normal", "power": 102, "category": "physical"},
        "Body Slam": {"type": "normal", "power": 85, "category": "physical"},
        "Double-Edge": {"type": "normal", "power": 120, "category": "physical"},
        "Giga Impact": {"type": "normal", "power": 150, "category": "physical"},
        # Signature physical
        "Glacial Lance": {"type": "ice", "power": 120, "category": "physical", "spread": True},
        "Wicked Blow": {"type": "dark", "power": 75, "category": "physical"},
        "Surging Strikes": {"type": "water", "power": 25, "category": "physical"},
        "Foul Play": {"type": "dark", "power": 95, "category": "physical"},
        "Body Press": {"type": "fighting", "power": 80, "category": "physical"},
        "Bitter Blade": {"type": "fire", "power": 90, "category": "physical"},
        "Collision Course": {"type": "fighting", "power": 100, "category": "physical"},
        "Kowtow Cleave": {"type": "dark", "power": 85, "category": "physical"},
        "Rage Fist": {"type": "ghost", "power": 50, "category": "physical"},
        "Last Respects": {"type": "ghost", "power": 50, "category": "physical"},
        "Population Bomb": {"type": "normal", "power": 20, "category": "physical"},
        "Tera Blast": {"type": "normal", "power": 80, "category": "special"},
        # Special moves - Core
        "Moonblast": {"type": "fairy", "power": 95, "category": "special"},
        "Shadow Ball": {"type": "ghost", "power": 80, "category": "special"},
        "Dazzling Gleam": {"type": "fairy", "power": 80, "category": "special", "spread": True},
        "Heat Wave": {"type": "fire", "power": 95, "category": "special", "spread": True},
        "Thunderbolt": {"type": "electric", "power": 90, "category": "special"},
        "Ice Beam": {"type": "ice", "power": 90, "category": "special"},
        "Hydro Pump": {"type": "water", "power": 110, "category": "special"},
        "Draco Meteor": {"type": "dragon", "power": 130, "category": "special"},
        "Energy Ball": {"type": "grass", "power": 90, "category": "special"},
        "Psychic": {"type": "psychic", "power": 90, "category": "special"},
        "Sludge Bomb": {"type": "poison", "power": 90, "category": "special"},
        "Aura Sphere": {"type": "fighting", "power": 80, "category": "special"},
        "Dark Pulse": {"type": "dark", "power": 80, "category": "special"},
        "Flash Cannon": {"type": "steel", "power": 80, "category": "special"},
        "Flamethrower": {"type": "fire", "power": 90, "category": "special"},
        "Surf": {"type": "water", "power": 90, "category": "special", "spread": True},
        "Blizzard": {"type": "ice", "power": 110, "category": "special", "spread": True},
        "Muddy Water": {"type": "water", "power": 90, "category": "special", "spread": True},
        "Hyper Voice": {"type": "normal", "power": 90, "category": "special", "spread": True},
        "Scald": {"type": "water", "power": 80, "category": "special"},
        "Fire Blast": {"type": "fire", "power": 110, "category": "special"},
        "Overheat": {"type": "fire", "power": 130, "category": "special"},
        "Thunder": {"type": "electric", "power": 110, "category": "special"},
        "Discharge": {"type": "electric", "power": 80, "category": "special", "spread": True},
        "Icy Wind": {"type": "ice", "power": 55, "category": "special", "spread": True},
        "Snarl": {"type": "dark", "power": 55, "category": "special", "spread": True},
        "Giga Drain": {"type": "grass", "power": 75, "category": "special"},
        "Leaf Storm": {"type": "grass", "power": 130, "category": "special"},
        "Pollen Puff": {"type": "bug", "power": 90, "category": "special"},
        "Bug Buzz": {"type": "bug", "power": 90, "category": "special"},
        "Earth Power": {"type": "ground", "power": 90, "category": "special"},
        "Power Gem": {"type": "rock", "power": 80, "category": "special"},
        "Ancient Power": {"type": "rock", "power": 60, "category": "special"},
        "Dragon Pulse": {"type": "dragon", "power": 85, "category": "special"},
        "Focus Blast": {"type": "fighting", "power": 120, "category": "special"},
        "Vacuum Wave": {"type": "fighting", "power": 40, "category": "special"},
        "Hex": {"type": "ghost", "power": 65, "category": "special"},
        "Psyshock": {"type": "psychic", "power": 80, "category": "special"},
        "Expanding Force": {"type": "psychic", "power": 80, "category": "special"},
        "Air Slash": {"type": "flying", "power": 75, "category": "special"},
        "Hurricane": {"type": "flying", "power": 110, "category": "special"},
        "Hyper Beam": {"type": "normal", "power": 150, "category": "special"},
        "Tri Attack": {"type": "normal", "power": 80, "category": "special"},
        "Weather Ball": {"type": "normal", "power": 50, "category": "special"},
        # Signature special
        "Astral Barrage": {"type": "ghost", "power": 120, "category": "special", "spread": True},
        "Make It Rain": {"type": "steel", "power": 120, "category": "special", "spread": True},
        "Electro Drift": {"type": "electric", "power": 100, "category": "special"},
        "Torch Song": {"type": "fire", "power": 80, "category": "special"},
        "Psyblade": {"type": "psychic", "power": 80, "category": "physical"},
        "Ivy Cudgel": {"type": "grass", "power": 100, "category": "physical"},
        "Blood Moon": {"type": "normal", "power": 140, "category": "special"},
        "Fickle Beam": {"type": "dragon", "power": 80, "category": "special"},
        "Lumina Crash": {"type": "psychic", "power": 80, "category": "special"},
    }

    # Pokemon-specific common moves from Smogon VGC usage data
    pokemon_moves = {
        "flutter mane": ["Moonblast", "Shadow Ball", "Dazzling Gleam", "Thunderbolt", "Icy Wind", "Psyshock", "Mystical Fire", "Perish Song", "Protect"],
        "incineroar": ["Flare Blitz", "Knock Off", "Parting Shot", "Fake Out", "U-turn", "Will-O-Wisp", "Snarl", "Protect"],
        "rillaboom": ["Wood Hammer", "Grassy Glide", "U-turn", "Knock Off", "Fake Out", "High Horsepower", "Protect"],
        "urshifu": ["Wicked Blow", "Close Combat", "Sucker Punch", "U-turn", "Protect", "Detect"],
        "urshifu-rapid-strike": ["Surging Strikes", "Close Combat", "Aqua Jet", "U-turn", "Protect", "Detect"],
        "calyrex-shadow": ["Astral Barrage", "Psyshock", "Nasty Plot", "Draining Kiss", "Protect"],
        "calyrex-ice": ["Glacial Lance", "High Horsepower", "Trick Room", "Protect"],
        "zacian": ["Behemoth Blade", "Sacred Sword", "Play Rough", "Close Combat", "Swords Dance", "Protect"],
        "kyogre": ["Water Spout", "Origin Pulse", "Ice Beam", "Thunder", "Protect"],
        "groudon": ["Precipice Blades", "Heat Crash", "Stone Edge", "Swords Dance", "Protect"],
        "miraidon": ["Electro Drift", "Draco Meteor", "Volt Switch", "Overheat", "Protect"],
        "koraidon": ["Collision Course", "Flare Blitz", "Dragon Claw", "Close Combat", "Protect"],
        "chien-pao": ["Icicle Crash", "Sucker Punch", "Sacred Sword", "Ice Shard", "Protect"],
        "chi-yu": ["Heat Wave", "Dark Pulse", "Overheat", "Snarl", "Protect"],
        "gholdengo": ["Make It Rain", "Shadow Ball", "Nasty Plot", "Trick", "Protect"],
        "amoonguss": ["Spore", "Pollen Puff", "Rage Powder", "Clear Smog", "Protect"],
        "dragapult": ["Dragon Darts", "Shadow Ball", "Draco Meteor", "Thunderbolt", "Phantom Force", "Protect"],
        "iron hands": ["Close Combat", "Wild Charge", "Fake Out", "Heavy Slam", "Protect"],
        "palafin": ["Jet Punch", "Close Combat", "Wave Crash", "Flip Turn", "Protect"],
        "tornadus": ["Bleakwind Storm", "Hurricane", "Tailwind", "Rain Dance", "Protect"],
        "landorus": ["Earth Power", "Sludge Bomb", "U-turn", "Protect"],
        "pelipper": ["Hurricane", "Hydro Pump", "Tailwind", "Protect"],
        "arcanine": ["Flare Blitz", "Wild Charge", "Extreme Speed", "Will-O-Wisp", "Protect"],
        "ogerpon": ["Ivy Cudgel", "Horn Leech", "U-turn", "Protect"],
        "farigiraf": ["Psychic", "Hyper Voice", "Trick Room", "Protect"],
        "indeedee-f": ["Follow Me", "Psychic", "Helping Hand", "Protect"],
        "gothitelle": ["Psychic", "Trick Room", "Fake Out", "Protect"],
        "hatterene": ["Dazzling Gleam", "Psychic", "Trick Room", "Protect"],
        "armarouge": ["Armor Cannon", "Psychic", "Trick Room", "Protect"],
        "dondozo": ["Wave Crash", "Order Up", "Earthquake", "Protect"],
        "tatsugiri": ["Draco Meteor", "Muddy Water", "Icy Wind", "Protect"],
        "annihilape": ["Rage Fist", "Close Combat", "Shadow Claw", "Protect"],
        "kingambit": ["Kowtow Cleave", "Sucker Punch", "Iron Head", "Protect"],
        "grimmsnarl": ["Spirit Break", "Fake Out", "Thunder Wave", "Taunt", "Protect"],
        "whimsicott": ["Moonblast", "Tailwind", "Encore", "Protect"],
    }

    # Generate move options grouped by category
    physical_moves = [(name, data) for name, data in competitive_moves.items() if data["category"] == "physical"]
    special_moves = [(name, data) for name, data in competitive_moves.items() if data["category"] == "special"]

    # Sort alphabetically
    physical_moves.sort(key=lambda x: x[0])
    special_moves.sort(key=lambda x: x[0])

    # Get Pokemon-specific moves from Smogon data
    attacker_key = attacker.lower().replace(" ", "-").replace(".", "")
    attacker_smogon_moves = pokemon_moves.get(attacker.lower(), pokemon_moves.get(attacker_key, []))

    # Build move options HTML with Pokemon-specific moves first
    current_move_option = f'<option value="{move}" data-type="{move_type or "normal"}" data-power="{move_power}" data-category="{move_category}" selected>{move}</option>'

    # Generate Smogon set moves (attacker's common moves)
    smogon_options = ""
    if attacker_smogon_moves:
        for move_name in attacker_smogon_moves:
            if move_name != move and move_name in competitive_moves:
                data = competitive_moves[move_name]
                smogon_options += f'<option value="{move_name}" data-type="{data["type"]}" data-power="{data["power"]}" data-category="{data["category"]}">{move_name}</option>'

    physical_options = "".join(
        f'<option value="{name}" data-type="{data["type"]}" data-power="{data["power"]}" data-category="physical">{name}</option>'
        for name, data in physical_moves if name != move
    )
    special_options = "".join(
        f'<option value="{name}" data-type="{data["type"]}" data-power="{data["power"]}" data-category="special">{name}</option>'
        for name, data in special_moves if name != move
    )

    # Build notes HTML
    notes_html = ""
    if notes:
        notes_items = "".join(f"<li>{note}</li>" for note in notes)
        notes_html = f'<ul class="notes-list">{notes_items}</ul>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%);
    color: #e4e4e7;
    line-height: 1.5;
    min-height: 100vh;
}}

/* Animated background particles */
body::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-image:
        radial-gradient(circle at 20% 80%, rgba(99, 102, 241, 0.05) 0%, transparent 50%),
        radial-gradient(circle at 80% 20%, rgba(139, 92, 246, 0.05) 0%, transparent 50%),
        radial-gradient(circle at 50% 50%, rgba(236, 72, 153, 0.03) 0%, transparent 50%);
    pointer-events: none;
    z-index: -1;
}}

.calc-container {{
    max-width: 920px;
    margin: 0 auto;
    padding: 24px;
}}

/* Header with move info - Glassmorphism style */
.calc-header {{
    text-align: center;
    margin-bottom: 28px;
    padding: 20px 24px;
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
    position: relative;
    overflow: hidden;
}}

.calc-header::before {{
    content: "";
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.1), transparent);
}}

.move-info {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 14px;
    flex-wrap: wrap;
}}

.move-name {{
    font-size: 22px;
    font-weight: 700;
    color: #fff;
}}

.move-select {{
    padding: 10px 18px;
    font-size: 16px;
    font-weight: 600;
    background: rgba(24, 24, 27, 0.8);
    backdrop-filter: blur(10px);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 12px;
    color: #fff;
    cursor: pointer;
    min-width: 200px;
    transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
}}

.move-select:hover {{
    border-color: rgba(139, 92, 246, 0.6);
    box-shadow: 0 4px 20px rgba(99, 102, 241, 0.25);
    transform: translateY(-1px);
}}

.move-select:focus {{
    outline: none;
    border-color: #8b5cf6;
    box-shadow: 0 0 0 4px rgba(139, 92, 246, 0.2), 0 4px 20px rgba(99, 102, 241, 0.3);
}}

.move-select option {{
    background: #1a1a2e;
    color: #fff;
    padding: 10px;
}}

.move-select optgroup {{
    background: #27272a;
    color: #a1a1aa;
    font-weight: 600;
    padding: 8px;
}}

.move-category {{
    font-size: 10px;
    padding: 6px 12px;
    border-radius: 8px;
    text-transform: uppercase;
    font-weight: 700;
    letter-spacing: 0.8px;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}}

.move-category.physical {{
    background: linear-gradient(135deg, #f97316 0%, #ea580c 100%);
    color: #fff;
}}

.move-category.special {{
    background: linear-gradient(135deg, #8b5cf6 0%, #6366f1 100%);
    color: #fff;
}}

.move-type-badge {{
    padding: 6px 14px;
    border-radius: 8px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.8px;
    color: #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}}

.move-power {{
    font-size: 13px;
    color: #71717a;
    font-weight: 600;
    background: rgba(255, 255, 255, 0.05);
    padding: 6px 12px;
    border-radius: 8px;
}}

/* Main layout - side by side */
.battle-layout {{
    display: grid;
    grid-template-columns: 1fr auto 1fr;
    gap: 20px;
    align-items: stretch;
    margin-bottom: 28px;
}}

@media (max-width: 720px) {{
    .battle-layout {{
        grid-template-columns: 1fr;
        gap: 16px;
    }}
    .vs-connector {{
        transform: rotate(90deg);
        padding: 8px;
    }}
}}

/* Pokemon cards - Enhanced glassmorphism */
.pokemon-card {{
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow:
        0 4px 24px rgba(0, 0, 0, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
}}

.pokemon-card:hover {{
    transform: translateY(-4px);
    box-shadow:
        0 20px 40px rgba(0, 0, 0, 0.3),
        inset 0 1px 0 rgba(255, 255, 255, 0.05);
}}

.pokemon-card.attacker {{
    border-color: rgba(251, 113, 133, 0.2);
    background: linear-gradient(180deg, rgba(251, 113, 133, 0.03) 0%, rgba(255, 255, 255, 0.02) 100%);
}}

.pokemon-card.attacker:hover {{
    border-color: rgba(251, 113, 133, 0.4);
    box-shadow:
        0 20px 40px rgba(0, 0, 0, 0.3),
        0 0 40px rgba(251, 113, 133, 0.1);
}}

.pokemon-card.defender {{
    border-color: rgba(96, 165, 250, 0.2);
    background: linear-gradient(180deg, rgba(96, 165, 250, 0.03) 0%, rgba(255, 255, 255, 0.02) 100%);
}}

.pokemon-card.defender:hover {{
    border-color: rgba(96, 165, 250, 0.4);
    box-shadow:
        0 20px 40px rgba(0, 0, 0, 0.3),
        0 0 40px rgba(96, 165, 250, 0.1);
}}

.card-header {{
    padding: 20px;
    display: flex;
    align-items: center;
    gap: 16px;
    background: rgba(255, 255, 255, 0.01);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    position: relative;
}}

.pokemon-sprite {{
    width: 96px;
    height: 96px;
    image-rendering: auto;
    filter: drop-shadow(0 8px 16px rgba(0, 0, 0, 0.4));
    transition: transform 0.3s ease;
}}

.pokemon-card:hover .pokemon-sprite {{
    transform: scale(1.05);
}}

.pokemon-details {{
    flex: 1;
}}

.pokemon-name {{
    font-size: 20px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 6px;
    letter-spacing: -0.02em;
}}

.pokemon-item {{
    font-size: 12px;
    color: #a1a1aa;
    display: flex;
    align-items: center;
    gap: 4px;
}}

.pokemon-item::before {{
    content: "@";
    color: #6366f1;
}}

.role-badge {{
    font-size: 9px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    padding: 4px 10px;
    border-radius: 6px;
    margin-top: 8px;
    display: inline-block;
}}

.role-badge.attacker {{
    background: linear-gradient(135deg, rgba(251, 113, 133, 0.2) 0%, rgba(251, 113, 133, 0.1) 100%);
    color: #fb7185;
    border: 1px solid rgba(251, 113, 133, 0.2);
}}

.role-badge.defender {{
    background: linear-gradient(135deg, rgba(96, 165, 250, 0.2) 0%, rgba(96, 165, 250, 0.1) 100%);
    color: #60a5fa;
    border: 1px solid rgba(96, 165, 250, 0.2);
}}

/* Nature & Item select */
.nature-row {{
    padding: 14px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    display: flex;
    align-items: center;
    gap: 14px;
}}

.nature-label {{
    font-size: 10px;
    color: #52525b;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 700;
    min-width: 50px;
}}

.nature-select {{
    flex: 1;
    padding: 10px 14px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: rgba(24, 24, 27, 0.6);
    color: #e4e4e7;
    font-size: 13px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s ease;
}}

.nature-select:hover {{
    border-color: rgba(99, 102, 241, 0.4);
    background: rgba(24, 24, 27, 0.8);
}}

.nature-select:focus {{
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}}

/* EV Grid - Modern input styling */
.ev-section {{
    padding: 20px;
}}

.ev-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}}

@media (max-width: 480px) {{
    .ev-grid {{
        grid-template-columns: repeat(2, 1fr);
    }}
}}

.ev-item {{
    display: flex;
    flex-direction: column;
    gap: 6px;
}}

.ev-label {{
    font-size: 9px;
    color: #52525b;
    text-transform: uppercase;
    letter-spacing: 1px;
    font-weight: 700;
    text-align: center;
}}

.ev-input {{
    width: 100%;
    padding: 12px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    background: rgba(24, 24, 27, 0.6);
    color: #fff;
    font-size: 15px;
    font-weight: 700;
    text-align: center;
    transition: all 0.3s ease;
    -moz-appearance: textfield;
}}

.ev-input::-webkit-outer-spin-button,
.ev-input::-webkit-inner-spin-button {{
    -webkit-appearance: none;
    margin: 0;
}}

.ev-input:hover {{
    border-color: rgba(99, 102, 241, 0.4);
    background: rgba(24, 24, 27, 0.8);
}}

.ev-input:focus {{
    outline: none;
    border-color: #6366f1;
    background: rgba(30, 30, 45, 0.8);
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}}

.ev-total {{
    margin-top: 16px;
    padding: 10px 16px;
    background: rgba(99, 102, 241, 0.08);
    border-radius: 12px;
    font-size: 12px;
    font-weight: 700;
    text-align: center;
    color: #a5b4fc;
    border: 1px solid rgba(99, 102, 241, 0.15);
}}

.ev-total.over-limit {{
    background: rgba(239, 68, 68, 0.1);
    color: #fca5a5;
    border-color: rgba(239, 68, 68, 0.2);
    animation: pulse-warning 2s infinite;
}}

@keyframes pulse-warning {{
    0%, 100% {{ opacity: 1; }}
    50% {{ opacity: 0.7; }}
}}

/* VS Connector - Glowing effect */
.vs-connector {{
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    padding: 24px 12px;
}}

.vs-circle {{
    width: 56px;
    height: 56px;
    background: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #a855f7 100%);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 15px;
    font-weight: 800;
    color: #fff;
    box-shadow:
        0 8px 24px rgba(99, 102, 241, 0.4),
        0 0 40px rgba(139, 92, 246, 0.2);
    animation: vs-pulse 3s ease-in-out infinite;
    position: relative;
}}

.vs-circle::before {{
    content: "";
    position: absolute;
    inset: -4px;
    border-radius: 50%;
    background: linear-gradient(135deg, rgba(99, 102, 241, 0.4), rgba(139, 92, 246, 0.2));
    z-index: -1;
    opacity: 0.5;
}}

@keyframes vs-pulse {{
    0%, 100% {{ transform: scale(1); box-shadow: 0 8px 24px rgba(99, 102, 241, 0.4), 0 0 40px rgba(139, 92, 246, 0.2); }}
    50% {{ transform: scale(1.05); box-shadow: 0 12px 32px rgba(99, 102, 241, 0.5), 0 0 60px rgba(139, 92, 246, 0.3); }}
}}

/* Damage Result Panel - Premium look */
.damage-panel {{
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 24px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    box-shadow:
        0 8px 32px rgba(0, 0, 0, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
}}

.damage-header {{
    padding: 18px 24px;
    background: rgba(255, 255, 255, 0.01);
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    display: flex;
    align-items: center;
    justify-content: space-between;
}}

.damage-title {{
    font-size: 11px;
    font-weight: 700;
    color: #71717a;
    text-transform: uppercase;
    letter-spacing: 1.5px;
}}

.effectiveness {{
    font-size: 10px;
    font-weight: 700;
    padding: 6px 12px;
    border-radius: 8px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.effectiveness.super {{
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.2) 0%, rgba(34, 197, 94, 0.1) 100%);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.2);
}}
.effectiveness.super4x {{
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.3) 0%, rgba(34, 197, 94, 0.15) 100%);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
}}
.effectiveness.neutral {{
    background: rgba(161, 161, 170, 0.15);
    color: #a1a1aa;
    border: 1px solid rgba(161, 161, 170, 0.15);
}}
.effectiveness.resist {{
    background: linear-gradient(135deg, rgba(251, 146, 60, 0.2) 0%, rgba(251, 146, 60, 0.1) 100%);
    color: #fb923c;
    border: 1px solid rgba(251, 146, 60, 0.2);
}}
.effectiveness.resist4x {{
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.2) 0%, rgba(239, 68, 68, 0.1) 100%);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.2);
}}
.effectiveness.immune {{
    background: rgba(113, 113, 122, 0.15);
    color: #71717a;
    border: 1px solid rgba(113, 113, 122, 0.15);
}}

.damage-body {{
    padding: 32px 24px;
}}

.damage-bar-wrapper {{
    margin-bottom: 28px;
}}

.damage-bar {{
    height: 24px;
    background: rgba(39, 39, 42, 0.8);
    border-radius: 12px;
    overflow: hidden;
    position: relative;
    box-shadow: inset 0 2px 4px rgba(0, 0, 0, 0.3);
}}

.damage-bar-fill {{
    height: 100%;
    border-radius: 12px;
    background: linear-gradient(90deg,
        #22c55e 0%,
        #84cc16 20%,
        #eab308 40%,
        #f97316 60%,
        #ef4444 80%,
        #dc2626 100%);
    transition: width 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    position: relative;
    box-shadow: 0 0 20px rgba(239, 68, 68, 0.3);
}}

.damage-bar-range {{
    position: absolute;
    top: 0;
    height: 100%;
    background: rgba(255, 255, 255, 0.2);
    border-radius: 12px;
    transition: all 0.5s cubic-bezier(0.4, 0, 0.2, 1);
    backdrop-filter: blur(2px);
}}

.damage-display {{
    text-align: center;
}}

.damage-numbers {{
    font-size: 48px;
    font-weight: 800;
    background: linear-gradient(135deg, #fff 0%, #e4e4e7 50%, #a1a1aa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    margin-bottom: 16px;
    letter-spacing: -0.02em;
    text-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
}}

.ko-badge {{
    display: inline-block;
    padding: 12px 28px;
    border-radius: 50px;
    font-size: 13px;
    font-weight: 800;
    text-transform: uppercase;
    letter-spacing: 1px;
    transition: all 0.3s ease;
}}

.ko-badge.ohko {{
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 50%, #b91c1c 100%);
    color: #fff;
    box-shadow:
        0 8px 24px rgba(220, 38, 38, 0.4),
        0 0 40px rgba(239, 68, 68, 0.2);
    animation: ko-glow-red 2s ease-in-out infinite;
}}

.ko-badge.2hko {{
    background: linear-gradient(135deg, #f97316 0%, #ea580c 50%, #c2410c 100%);
    color: #fff;
    box-shadow:
        0 8px 24px rgba(234, 88, 12, 0.4),
        0 0 40px rgba(249, 115, 22, 0.2);
}}

.ko-badge.3hko {{
    background: linear-gradient(135deg, #eab308 0%, #ca8a04 50%, #a16207 100%);
    color: #fff;
    box-shadow:
        0 8px 24px rgba(202, 138, 4, 0.3),
        0 0 40px rgba(234, 179, 8, 0.15);
}}

.ko-badge.survive {{
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 50%, #15803d 100%);
    color: #fff;
    box-shadow:
        0 8px 24px rgba(22, 163, 74, 0.4),
        0 0 40px rgba(34, 197, 94, 0.2);
    animation: ko-glow-green 2s ease-in-out infinite;
}}

@keyframes ko-glow-red {{
    0%, 100% {{ box-shadow: 0 8px 24px rgba(220, 38, 38, 0.4), 0 0 40px rgba(239, 68, 68, 0.2); }}
    50% {{ box-shadow: 0 8px 32px rgba(220, 38, 38, 0.5), 0 0 60px rgba(239, 68, 68, 0.3); }}
}}

@keyframes ko-glow-green {{
    0%, 100% {{ box-shadow: 0 8px 24px rgba(22, 163, 74, 0.4), 0 0 40px rgba(34, 197, 94, 0.2); }}
    50% {{ box-shadow: 0 8px 32px rgba(22, 163, 74, 0.5), 0 0 60px rgba(34, 197, 94, 0.3); }}
}}

/* Notes - Clean style */
.notes-list {{
    margin-top: 20px;
    padding: 16px 20px;
    background: rgba(99, 102, 241, 0.05);
    border-radius: 16px;
    border: 1px solid rgba(99, 102, 241, 0.1);
    list-style: none;
}}

.notes-list li {{
    font-size: 12px;
    color: #a1a1aa;
    padding: 6px 0;
    padding-left: 20px;
    position: relative;
    line-height: 1.6;
}}

.notes-list li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 8px;
    height: 8px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 50%;
    box-shadow: 0 0 8px rgba(99, 102, 241, 0.4);
}}

/* Scrollbar styling */
::-webkit-scrollbar {{
    width: 8px;
    height: 8px;
}}

::-webkit-scrollbar-track {{
    background: rgba(0, 0, 0, 0.2);
    border-radius: 4px;
}}

::-webkit-scrollbar-thumb {{
    background: rgba(99, 102, 241, 0.4);
    border-radius: 4px;
}}

::-webkit-scrollbar-thumb:hover {{
    background: rgba(99, 102, 241, 0.6);
}}

/* ===== TERA TOGGLE ===== */
.tera-row {{
    display: flex;
    align-items: center;
    gap: 10px;
}}

.tera-toggle {{
    position: relative;
    display: inline-block;
    width: 40px;
    height: 22px;
    flex-shrink: 0;
}}

.tera-toggle input {{
    opacity: 0;
    width: 0;
    height: 0;
}}

.tera-switch {{
    position: absolute;
    inset: 0;
    background: rgba(255, 255, 255, 0.1);
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.3s ease;
    border: 1px solid rgba(255, 255, 255, 0.08);
}}

.tera-switch::before {{
    content: "";
    position: absolute;
    width: 16px;
    height: 16px;
    left: 2px;
    top: 2px;
    background: #71717a;
    border-radius: 50%;
    transition: all 0.3s ease;
}}

.tera-toggle input:checked + .tera-switch {{
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-color: rgba(99, 102, 241, 0.4);
    box-shadow: 0 0 12px rgba(99, 102, 241, 0.4);
}}

.tera-toggle input:checked + .tera-switch::before {{
    transform: translateX(18px);
    background: #fff;
}}

.tera-select {{
    flex: 1;
    min-width: 0;
}}

/* ===== ADVANCED OPTIONS COLLAPSIBLE ===== */
.advanced-options {{
    margin-top: 24px;
    margin-bottom: 24px;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
}}

.advanced-options-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    padding: 16px 20px;
    cursor: pointer;
    font-size: 13px;
    font-weight: 600;
    color: #a1a1aa;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid transparent;
    transition: all 0.3s ease;
    list-style: none;
}}

.advanced-options-header::-webkit-details-marker {{
    display: none;
}}

.advanced-options-header:hover {{
    background: rgba(255, 255, 255, 0.04);
    color: #e4e4e7;
}}

.advanced-options[open] .advanced-options-header {{
    border-bottom-color: rgba(255, 255, 255, 0.06);
}}

.advanced-icon {{
    font-size: 16px;
}}

.chevron {{
    margin-left: auto;
    font-size: 10px;
    transition: transform 0.3s ease;
}}

.advanced-options[open] .chevron {{
    transform: rotate(180deg);
}}

.advanced-options-content {{
    padding: 20px;
    animation: fadeSlideIn 0.3s ease;
}}

@keyframes fadeSlideIn {{
    from {{
        opacity: 0;
        transform: translateY(-10px);
    }}
    to {{
        opacity: 1;
        transform: translateY(0);
    }}
}}

/* ===== OPTIONS SECTIONS ===== */
.options-section {{
    margin-bottom: 24px;
    padding-bottom: 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
}}

.options-section:last-child {{
    margin-bottom: 0;
    padding-bottom: 0;
    border-bottom: none;
}}

.section-title {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1.2px;
    color: #6366f1;
    margin-bottom: 14px;
}}

/* ===== FIELD DROPDOWNS ===== */
.field-row {{
    display: flex;
    gap: 16px;
}}

.field-group {{
    flex: 1;
}}

.field-label {{
    display: block;
    font-size: 10px;
    color: #71717a;
    margin-bottom: 6px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    font-weight: 600;
}}

.field-select {{
    width: 100%;
    padding: 10px 14px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: rgba(24, 24, 27, 0.6);
    color: #e4e4e7;
    font-size: 13px;
    cursor: pointer;
    transition: all 0.3s ease;
}}

.field-select:hover {{
    border-color: rgba(99, 102, 241, 0.4);
}}

.field-select:focus {{
    outline: none;
    border-color: #6366f1;
    box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.15);
}}

.field-select option {{
    background: #1a1a2e;
    color: #fff;
}}

/* ===== TOGGLE BUTTON GRID ===== */
.toggle-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

.field-toggle {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 10px 16px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 10px;
    background: rgba(24, 24, 27, 0.4);
    color: #a1a1aa;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.2s ease;
}}

.field-toggle:hover {{
    background: rgba(255, 255, 255, 0.05);
    border-color: rgba(255, 255, 255, 0.12);
    color: #e4e4e7;
}}

.field-toggle.active {{
    background: rgba(99, 102, 241, 0.15);
    border-color: rgba(99, 102, 241, 0.4);
    color: #a5b4fc;
}}

/* ===== RUIN ABILITY COLORS ===== */
.field-toggle.ruin.sword.active {{
    background: rgba(96, 165, 250, 0.15);
    border-color: rgba(96, 165, 250, 0.4);
    color: #60a5fa;
}}

.field-toggle.ruin.beads.active {{
    background: rgba(239, 68, 68, 0.15);
    border-color: rgba(239, 68, 68, 0.4);
    color: #f87171;
}}

.field-toggle.ruin.tablets.active {{
    background: rgba(34, 197, 94, 0.15);
    border-color: rgba(34, 197, 94, 0.4);
    color: #4ade80;
}}

.field-toggle.ruin.vessel.active {{
    background: rgba(168, 85, 247, 0.15);
    border-color: rgba(168, 85, 247, 0.4);
    color: #c084fc;
}}

.field-toggle.commander.active {{
    background: rgba(14, 165, 233, 0.15);
    border-color: rgba(14, 165, 233, 0.4);
    color: #38bdf8;
}}

/* ===== STAT STAGES ===== */
.stat-stages-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}}

.stage-group {{
    background: rgba(255, 255, 255, 0.02);
    border-radius: 12px;
    padding: 14px;
    border: 1px solid rgba(255, 255, 255, 0.04);
}}

.stage-label {{
    display: block;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #71717a;
    margin-bottom: 10px;
}}

.attacker-stages .stage-label {{ color: #fb7185; }}
.defender-stages .stage-label {{ color: #60a5fa; }}

.stage-row {{
    display: flex;
    align-items: center;
    gap: 12px;
}}

.stage-stat {{
    font-size: 11px;
    color: #a1a1aa;
    min-width: 55px;
    font-weight: 500;
}}

.stage-slider {{
    flex: 1;
    -webkit-appearance: none;
    height: 6px;
    border-radius: 3px;
    background: rgba(255, 255, 255, 0.1);
    outline: none;
}}

.stage-slider::-webkit-slider-thumb {{
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
    transition: transform 0.2s ease;
}}

.stage-slider::-webkit-slider-thumb:hover {{
    transform: scale(1.1);
}}

.stage-slider::-moz-range-thumb {{
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    cursor: pointer;
    border: none;
    box-shadow: 0 2px 8px rgba(99, 102, 241, 0.4);
}}

.stage-value {{
    font-size: 14px;
    font-weight: 700;
    font-family: 'SF Mono', 'Monaco', 'Inconsolata', 'Fira Code', monospace;
    color: #e4e4e7;
    min-width: 28px;
    text-align: right;
}}

/* ===== RESPONSIVE ===== */
@media (max-width: 600px) {{
    .stat-stages-grid {{
        grid-template-columns: 1fr;
    }}

    .field-row {{
        flex-direction: column;
    }}

    .toggle-grid {{
        justify-content: center;
    }}

    .tera-row {{
        flex-wrap: wrap;
    }}
}}
    </style>
</head>
<body>
    <div class="calc-container">
        <!-- Header with move info -->
        <div class="calc-header">
            <div class="move-info">
                <select class="move-select" id="move-select" onchange="onMoveChange()">
                    <optgroup label="Current Move">
                        {current_move_option}
                    </optgroup>
                    {f'<optgroup label="&#11088; {attacker} Smogon Moves">{smogon_options}</optgroup>' if smogon_options else ''}
                    <optgroup label="Physical Moves">
                        {physical_options}
                    </optgroup>
                    <optgroup label="Special Moves">
                        {special_options}
                    </optgroup>
                </select>
                <span class="move-type-badge" id="move-type-badge" style="background: {move_color};">{move_type.upper() if move_type else 'NORMAL'}</span>
                <span class="move-power" id="move-power-display">{move_power} BP</span>
                <span class="move-category {move_category}" id="move-category">{move_category.upper()}</span>
            </div>
        </div>

        <!-- Side by side Pokemon -->
        <div class="battle-layout">
            <!-- Attacker -->
            <div class="pokemon-card attacker">
                <div class="card-header">
                    {get_sprite_html(attacker, size=80, css_class="pokemon-sprite")}
                    <div class="pokemon-details">
                        <div class="pokemon-name">{attacker}</div>
                        <span class="role-badge attacker">Attacker</span>
                    </div>
                </div>
                <div class="nature-row">
                    <span class="nature-label">Item</span>
                    <select class="nature-select item-select" id="attacker-item" onchange="recalculateDamage()">
                        {attacker_item_options}
                    </select>
                </div>
                <div class="nature-row">
                    <span class="nature-label">Nature</span>
                    <select class="nature-select" id="attacker-nature" onchange="recalculateDamage()">
                        {attacker_nature_options}
                    </select>
                </div>
                <div class="nature-row">
                    <span class="nature-label">Ability</span>
                    <select class="nature-select ability-select" id="attacker-ability" onchange="recalculateDamage()">
                        {attacker_ability_options}
                    </select>
                </div>
                <div class="nature-row tera-row">
                    <span class="nature-label">Tera</span>
                    <label class="tera-toggle">
                        <input type="checkbox" id="attacker-tera-active" onchange="recalculateDamage()">
                        <span class="tera-switch"></span>
                    </label>
                    <select class="nature-select tera-select" id="attacker-tera-type" onchange="recalculateDamage()">
                        {tera_type_options}
                    </select>
                </div>
                <div class="ev-section">
                    <div class="ev-grid">
                        <div class="ev-item">
                            <span class="ev-label">HP</span>
                            <input type="number" class="ev-input" id="atk-hp" value="{attacker_evs.get('hp', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('attacker'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Attack</span>
                            <input type="number" class="ev-input" id="atk-attack" value="{attacker_evs.get('attack', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('attacker'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Defense</span>
                            <input type="number" class="ev-input" id="atk-defense" value="{attacker_evs.get('defense', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('attacker'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Sp. Atk</span>
                            <input type="number" class="ev-input" id="atk-spa" value="{attacker_evs.get('special_attack', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('attacker'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Sp. Def</span>
                            <input type="number" class="ev-input" id="atk-spd" value="{attacker_evs.get('special_defense', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('attacker'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Speed</span>
                            <input type="number" class="ev-input" id="atk-speed" value="{attacker_evs.get('speed', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('attacker'); recalculateDamage()">
                        </div>
                    </div>
                    <div class="ev-total" id="attacker-ev-total">Total: 0 / 508</div>
                </div>
            </div>

            <!-- VS Connector -->
            <div class="vs-connector">
                <div class="vs-circle">VS</div>
            </div>

            <!-- Defender -->
            <div class="pokemon-card defender">
                <div class="card-header">
                    {get_sprite_html(defender, size=80, css_class="pokemon-sprite")}
                    <div class="pokemon-details">
                        <div class="pokemon-name">{defender}</div>
                        <span class="role-badge defender">Defender</span>
                    </div>
                </div>
                <div class="nature-row">
                    <span class="nature-label">Item</span>
                    <select class="nature-select item-select" id="defender-item" onchange="recalculateDamage()">
                        {defender_item_options}
                    </select>
                </div>
                <div class="nature-row">
                    <span class="nature-label">Nature</span>
                    <select class="nature-select" id="defender-nature" onchange="recalculateDamage()">
                        {defender_nature_options}
                    </select>
                </div>
                <div class="nature-row">
                    <span class="nature-label">Ability</span>
                    <select class="nature-select ability-select" id="defender-ability" onchange="recalculateDamage()">
                        {defender_ability_options}
                    </select>
                </div>
                <div class="nature-row tera-row">
                    <span class="nature-label">Tera</span>
                    <label class="tera-toggle">
                        <input type="checkbox" id="defender-tera-active" onchange="recalculateDamage()">
                        <span class="tera-switch"></span>
                    </label>
                    <select class="nature-select tera-select" id="defender-tera-type" onchange="recalculateDamage()">
                        {tera_type_options}
                    </select>
                </div>
                <div class="ev-section">
                    <div class="ev-grid">
                        <div class="ev-item">
                            <span class="ev-label">HP</span>
                            <input type="number" class="ev-input" id="def-hp" value="{defender_evs.get('hp', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('defender'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Attack</span>
                            <input type="number" class="ev-input" id="def-attack" value="{defender_evs.get('attack', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('defender'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Defense</span>
                            <input type="number" class="ev-input" id="def-defense" value="{defender_evs.get('defense', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('defender'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Sp. Atk</span>
                            <input type="number" class="ev-input" id="def-spa" value="{defender_evs.get('special_attack', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('defender'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Sp. Def</span>
                            <input type="number" class="ev-input" id="def-spd" value="{defender_evs.get('special_defense', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('defender'); recalculateDamage()">
                        </div>
                        <div class="ev-item">
                            <span class="ev-label">Speed</span>
                            <input type="number" class="ev-input" id="def-speed" value="{defender_evs.get('speed', 0)}" min="0" max="252" step="4" oninput="updateEVTotal('defender'); recalculateDamage()">
                        </div>
                    </div>
                    <div class="ev-total" id="defender-ev-total">Total: 0 / 508</div>
                </div>
            </div>
        </div>

        <!-- Advanced Options (Collapsible) -->
        <details class="advanced-options">
            <summary class="advanced-options-header">
                <span class="advanced-icon">&#9881;</span>
                Advanced Options
                <span class="chevron">&#9660;</span>
            </summary>
            <div class="advanced-options-content">
                <!-- Field Conditions Section -->
                <div class="options-section">
                    <div class="section-title">Field Conditions</div>
                    <div class="field-row">
                        <div class="field-group">
                            <label class="field-label">Weather</label>
                            <select class="field-select" id="weather" onchange="recalculateDamage()">
                                <option value="">None</option>
                                <option value="sun">Sun</option>
                                <option value="rain">Rain</option>
                                <option value="sand">Sand</option>
                                <option value="snow">Snow</option>
                            </select>
                        </div>
                        <div class="field-group">
                            <label class="field-label">Terrain</label>
                            <select class="field-select" id="terrain" onchange="recalculateDamage()">
                                <option value="">None</option>
                                <option value="electric">Electric</option>
                                <option value="grassy">Grassy</option>
                                <option value="psychic">Psychic</option>
                                <option value="misty">Misty</option>
                            </select>
                        </div>
                    </div>
                </div>

                <!-- Screens & Support Section -->
                <div class="options-section">
                    <div class="section-title">Screens & Support</div>
                    <div class="toggle-grid">
                        <button type="button" class="field-toggle" id="reflect" onclick="toggleField(this)">
                            Reflect
                        </button>
                        <button type="button" class="field-toggle" id="light-screen" onclick="toggleField(this)">
                            Light Screen
                        </button>
                        <button type="button" class="field-toggle" id="aurora-veil" onclick="toggleField(this)">
                            Aurora Veil
                        </button>
                        <button type="button" class="field-toggle" id="helping-hand" onclick="toggleField(this)">
                            Helping Hand
                        </button>
                        <button type="button" class="field-toggle" id="friend-guard" onclick="toggleField(this)">
                            Friend Guard
                        </button>
                    </div>
                </div>

                <!-- Ruin Abilities Section -->
                <div class="options-section">
                    <div class="section-title">Ruin Abilities (On Field)</div>
                    <div class="toggle-grid ruin-grid">
                        <button type="button" class="field-toggle ruin sword" id="sword-of-ruin" onclick="toggleField(this)" title="Chien-Pao: -25% Def">
                            Sword of Ruin
                        </button>
                        <button type="button" class="field-toggle ruin beads" id="beads-of-ruin" onclick="toggleField(this)" title="Chi-Yu: -25% SpD">
                            Beads of Ruin
                        </button>
                        <button type="button" class="field-toggle ruin tablets" id="tablets-of-ruin" onclick="toggleField(this)" title="Wo-Chien: -25% Atk">
                            Tablets of Ruin
                        </button>
                        <button type="button" class="field-toggle ruin vessel" id="vessel-of-ruin" onclick="toggleField(this)" title="Ting-Lu: -25% SpA">
                            Vessel of Ruin
                        </button>
                        <button type="button" class="field-toggle commander" id="commander" onclick="toggleField(this)" title="Dondozo+Tatsugiri: 2x stats">
                            Commander
                        </button>
                    </div>
                </div>

                <!-- Stat Stages Section -->
                <div class="options-section">
                    <div class="section-title">Stat Stages</div>
                    <div class="stat-stages-grid">
                        <div class="stage-group attacker-stages">
                            <span class="stage-label">Attacker</span>
                            <div class="stage-row">
                                <span class="stage-stat">Atk/SpA</span>
                                <input type="range" class="stage-slider" id="atk-stage"
                                       min="-6" max="6" value="0" oninput="updateStageDisplay(this); recalculateDamage()">
                                <span class="stage-value" id="atk-stage-display">+0</span>
                            </div>
                        </div>
                        <div class="stage-group defender-stages">
                            <span class="stage-label">Defender</span>
                            <div class="stage-row">
                                <span class="stage-stat">Def/SpD</span>
                                <input type="range" class="stage-slider" id="def-stage"
                                       min="-6" max="6" value="0" oninput="updateStageDisplay(this); recalculateDamage()">
                                <span class="stage-value" id="def-stage-display">+0</span>
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </details>

        <!-- Damage Result -->
        <div class="damage-panel">
            <div class="damage-header">
                <span class="damage-title">Damage Output</span>
                <span class="effectiveness {eff_class}" id="effectiveness">{eff_text}</span>
            </div>
            <div class="damage-body">
                <div class="damage-bar-wrapper">
                    <div class="damage-bar">
                        <div class="damage-bar-fill" id="damage-fill" style="width: {min(damage_max, 100)}%;"></div>
                        <div class="damage-bar-range" id="damage-range" style="left: {min(damage_min, 100)}%; width: {min(damage_max - damage_min, 100 - damage_min)}%;"></div>
                    </div>
                </div>
                <div class="damage-display">
                    <div class="damage-numbers" id="damage-numbers">{damage_min:.1f}% - {damage_max:.1f}%</div>
                    <span class="ko-badge {ko_class}" id="ko-badge">{ko_chance}</span>
                </div>
                {notes_html}
            </div>
        </div>
    </div>

    <script>
        // Store base data for calculations
        const calcData = {{
            attacker: "{attacker}",
            defender: "{defender}",
            move: "{move}",
            moveType: "{move_type or 'normal'}",
            movePower: {move_power},
            moveCategory: "{move_category}",
            typeEffectiveness: {type_effectiveness},
            attackerItem: "{attacker_item or ''}",
            defenderItem: "{defender_item or ''}",
            attackerBaseStats: {str(attacker_base_stats).replace("'", '"')},
            defenderBaseStats: {str(defender_base_stats).replace("'", '"')},
            attackerTypes: {json.dumps([t.lower() for t in attacker_types])},
            defenderTypes: {json.dumps([t.lower() for t in defender_types])}
        }};

        // Type effectiveness chart for recalculating when Tera changes types
        const TYPE_CHART = {{
            normal: {{ rock: 0.5, ghost: 0, steel: 0.5 }},
            fire: {{ fire: 0.5, water: 0.5, grass: 2, ice: 2, bug: 2, rock: 0.5, dragon: 0.5, steel: 2 }},
            water: {{ fire: 2, water: 0.5, grass: 0.5, ground: 2, rock: 2, dragon: 0.5 }},
            electric: {{ water: 2, electric: 0.5, grass: 0.5, ground: 0, flying: 2, dragon: 0.5 }},
            grass: {{ fire: 0.5, water: 2, grass: 0.5, poison: 0.5, ground: 2, flying: 0.5, bug: 0.5, rock: 2, dragon: 0.5, steel: 0.5 }},
            ice: {{ fire: 0.5, water: 0.5, grass: 2, ice: 0.5, ground: 2, flying: 2, dragon: 2, steel: 0.5 }},
            fighting: {{ normal: 2, ice: 2, poison: 0.5, flying: 0.5, psychic: 0.5, bug: 0.5, rock: 2, ghost: 0, dark: 2, steel: 2, fairy: 0.5 }},
            poison: {{ grass: 2, poison: 0.5, ground: 0.5, rock: 0.5, ghost: 0.5, steel: 0, fairy: 2 }},
            ground: {{ fire: 2, electric: 2, grass: 0.5, poison: 2, flying: 0, bug: 0.5, rock: 2, steel: 2 }},
            flying: {{ electric: 0.5, grass: 2, fighting: 2, bug: 2, rock: 0.5, steel: 0.5 }},
            psychic: {{ fighting: 2, poison: 2, psychic: 0.5, dark: 0, steel: 0.5 }},
            bug: {{ fire: 0.5, grass: 2, fighting: 0.5, poison: 0.5, flying: 0.5, psychic: 2, ghost: 0.5, dark: 2, steel: 0.5, fairy: 0.5 }},
            rock: {{ fire: 2, ice: 2, fighting: 0.5, ground: 0.5, flying: 2, bug: 2, steel: 0.5 }},
            ghost: {{ normal: 0, psychic: 2, ghost: 2, dark: 0.5 }},
            dragon: {{ dragon: 2, steel: 0.5, fairy: 0 }},
            dark: {{ fighting: 0.5, psychic: 2, ghost: 2, dark: 0.5, fairy: 0.5 }},
            steel: {{ fire: 0.5, water: 0.5, electric: 0.5, ice: 2, rock: 2, steel: 0.5, fairy: 2 }},
            fairy: {{ fire: 0.5, fighting: 2, poison: 0.5, dragon: 2, dark: 2, steel: 0.5 }}
        }};

        // Calculate type effectiveness against defender types
        function getTypeEffectiveness(moveType, defenderTypes) {{
            let multiplier = 1.0;
            const chart = TYPE_CHART[moveType.toLowerCase()];
            if (!chart) return 1.0;
            for (const defType of defenderTypes) {{
                const eff = chart[defType.toLowerCase()];
                if (eff !== undefined) {{
                    multiplier *= eff;
                }}
            }}
            return multiplier;
        }}

        // Nature modifiers
        const natureModifiers = {{
            "Adamant": {{ "attack": 1.1, "special_attack": 0.9 }},
            "Bold": {{ "defense": 1.1, "attack": 0.9 }},
            "Brave": {{ "attack": 1.1, "speed": 0.9 }},
            "Calm": {{ "special_defense": 1.1, "attack": 0.9 }},
            "Careful": {{ "special_defense": 1.1, "special_attack": 0.9 }},
            "Gentle": {{ "special_defense": 1.1, "defense": 0.9 }},
            "Hasty": {{ "speed": 1.1, "defense": 0.9 }},
            "Impish": {{ "defense": 1.1, "special_attack": 0.9 }},
            "Jolly": {{ "speed": 1.1, "special_attack": 0.9 }},
            "Lax": {{ "defense": 1.1, "special_defense": 0.9 }},
            "Lonely": {{ "attack": 1.1, "defense": 0.9 }},
            "Mild": {{ "special_attack": 1.1, "defense": 0.9 }},
            "Modest": {{ "special_attack": 1.1, "attack": 0.9 }},
            "Naive": {{ "speed": 1.1, "special_defense": 0.9 }},
            "Naughty": {{ "attack": 1.1, "special_defense": 0.9 }},
            "Quiet": {{ "special_attack": 1.1, "speed": 0.9 }},
            "Rash": {{ "special_attack": 1.1, "special_defense": 0.9 }},
            "Relaxed": {{ "defense": 1.1, "speed": 0.9 }},
            "Sassy": {{ "special_defense": 1.1, "speed": 0.9 }},
            "Serious": {{}},
            "Timid": {{ "speed": 1.1, "attack": 0.9 }}
        }};

        // Calculate stat at level 50
        function calcStat(base, ev, iv, nature, statName, isHP) {{
            iv = iv || 31;
            let stat;
            if (isHP) {{
                stat = Math.floor(((2 * base + iv + Math.floor(ev / 4)) * 50) / 100) + 50 + 10;
            }} else {{
                stat = Math.floor(((2 * base + iv + Math.floor(ev / 4)) * 50) / 100) + 5;
                const mods = natureModifiers[nature] || {{}};
                if (mods[statName] === 1.1) stat = Math.floor(stat * 1.1);
                if (mods[statName] === 0.9) stat = Math.floor(stat * 0.9);
            }}
            return stat;
        }}

        // Get EVs from inputs
        function getEVs(prefix) {{
            return {{
                hp: parseInt(document.getElementById(prefix + '-hp').value) || 0,
                attack: parseInt(document.getElementById(prefix + '-attack').value) || 0,
                defense: parseInt(document.getElementById(prefix + '-defense').value) || 0,
                special_attack: parseInt(document.getElementById(prefix + '-spa').value) || 0,
                special_defense: parseInt(document.getElementById(prefix + '-spd').value) || 0,
                speed: parseInt(document.getElementById(prefix + '-speed').value) || 0
            }};
        }}

        // Update EV total display
        function updateEVTotal(side) {{
            const prefix = side === 'attacker' ? 'atk' : 'def';
            const evs = getEVs(prefix);
            const total = Object.values(evs).reduce((a, b) => a + b, 0);
            const display = document.getElementById(side + '-ev-total');
            display.textContent = `Total: ${{total}} / 508`;
            display.classList.toggle('over-limit', total > 508);
        }}

        // Item damage modifiers
        const itemModifiers = {{
            "Choice Specs": {{ type: "special_attack", mult: 1.5 }},
            "Choice Band": {{ type: "attack", mult: 1.5 }},
            "Life Orb": {{ type: "all", mult: 1.3 }},
            "Expert Belt": {{ type: "super_effective", mult: 1.2 }},
            "Muscle Band": {{ type: "attack", mult: 1.1 }},
            "Wise Glasses": {{ type: "special_attack", mult: 1.1 }},
            "Miracle Seed": {{ type: "Grass", mult: 1.2 }},
            "Charcoal": {{ type: "Fire", mult: 1.2 }},
            "Mystic Water": {{ type: "Water", mult: 1.2 }},
            "Magnet": {{ type: "Electric", mult: 1.2 }},
            "Never-Melt Ice": {{ type: "Ice", mult: 1.2 }},
            "Soft Sand": {{ type: "Ground", mult: 1.2 }},
            "Sharp Beak": {{ type: "Flying", mult: 1.2 }},
            "Poison Barb": {{ type: "Poison", mult: 1.2 }},
            "Dragon Fang": {{ type: "Dragon", mult: 1.2 }},
            "Spell Tag": {{ type: "Ghost", mult: 1.2 }},
            "Twisted Spoon": {{ type: "Psychic", mult: 1.2 }},
            "Silver Powder": {{ type: "Bug", mult: 1.2 }},
            "Hard Stone": {{ type: "Rock", mult: 1.2 }},
            "Black Belt": {{ type: "Fighting", mult: 1.2 }},
            "Silk Scarf": {{ type: "Normal", mult: 1.2 }},
            "Metal Coat": {{ type: "Steel", mult: 1.2 }},
            "Black Glasses": {{ type: "Dark", mult: 1.2 }},
            "Fairy Feather": {{ type: "Fairy", mult: 1.2 }}
        }};

        const defenseItemModifiers = {{
            "Assault Vest": {{ type: "special_defense", mult: 1.5 }},
            "Eviolite": {{ type: "both_defense", mult: 1.5 }}
        }};

        // Toggle field condition buttons
        function toggleField(button) {{
            button.classList.toggle('active');
            recalculateDamage();
        }}

        // Update stat stage display
        function updateStageDisplay(slider) {{
            const value = parseInt(slider.value);
            const displayId = slider.id + '-display';
            const display = document.getElementById(displayId);
            if (display) {{
                display.textContent = value >= 0 ? '+' + value : value.toString();
            }}
        }}

        // Get stat stage multiplier
        function getStageMultiplier(stage) {{
            if (stage >= 0) return (2 + stage) / 2;
            return 2 / (2 - stage);
        }}

        // Calculate damage (enhanced Gen 9 formula with all modifiers)
        function calculateDamage() {{
            const attackerEVs = getEVs('atk');
            const defenderEVs = getEVs('def');
            const attackerNature = document.getElementById('attacker-nature').value;
            const defenderNature = document.getElementById('defender-nature').value;
            const attackerItem = document.getElementById('attacker-item').value;
            const defenderItem = document.getElementById('defender-item').value;

            // Get abilities
            const attackerAbility = document.getElementById('attacker-ability')?.value || '';
            const defenderAbility = document.getElementById('defender-ability')?.value || '';

            // Get Tera state
            const attackerTeraActive = document.getElementById('attacker-tera-active')?.checked || false;
            const attackerTeraType = document.getElementById('attacker-tera-type')?.value || '';
            const defenderTeraActive = document.getElementById('defender-tera-active')?.checked || false;
            const defenderTeraType = document.getElementById('defender-tera-type')?.value || '';

            // Get field conditions
            const weather = document.getElementById('weather')?.value || '';
            const terrain = document.getElementById('terrain')?.value || '';

            // Get screens and support toggles
            const reflectUp = document.getElementById('reflect')?.classList.contains('active') || false;
            const lightScreenUp = document.getElementById('light-screen')?.classList.contains('active') || false;
            const auroraVeilUp = document.getElementById('aurora-veil')?.classList.contains('active') || false;
            const helpingHand = document.getElementById('helping-hand')?.classList.contains('active') || false;
            const friendGuard = document.getElementById('friend-guard')?.classList.contains('active') || false;

            // Get Ruin abilities
            const swordOfRuin = document.getElementById('sword-of-ruin')?.classList.contains('active') || false;
            const beadsOfRuin = document.getElementById('beads-of-ruin')?.classList.contains('active') || false;
            const tabletsOfRuin = document.getElementById('tablets-of-ruin')?.classList.contains('active') || false;
            const vesselOfRuin = document.getElementById('vessel-of-ruin')?.classList.contains('active') || false;
            const commanderActive = document.getElementById('commander')?.classList.contains('active') || false;

            // Get stat stages
            const atkStage = parseInt(document.getElementById('atk-stage')?.value || 0);
            const defStage = parseInt(document.getElementById('def-stage')?.value || 0);

            // Determine which stats to use
            const isPhysical = calcData.moveCategory === 'physical';
            const atkStatName = isPhysical ? 'attack' : 'special_attack';
            const defStatName = isPhysical ? 'defense' : 'special_defense';

            // Calculate base stats
            let attackStat = calcStat(
                calcData.attackerBaseStats[atkStatName],
                attackerEVs[atkStatName],
                31,
                attackerNature,
                atkStatName,
                false
            );

            let defenseStat = calcStat(
                calcData.defenderBaseStats[defStatName],
                defenderEVs[defStatName],
                31,
                defenderNature,
                defStatName,
                false
            );

            const defenderHP = calcStat(
                calcData.defenderBaseStats.hp,
                defenderEVs.hp,
                31,
                defenderNature,
                'hp',
                true
            );

            // Apply stat stage multipliers
            attackStat = Math.floor(attackStat * getStageMultiplier(atkStage));
            defenseStat = Math.floor(defenseStat * getStageMultiplier(defStage));

            // Apply Ruin ability effects
            if (swordOfRuin && isPhysical) {{
                defenseStat = Math.floor(defenseStat * 0.75);
            }}
            if (beadsOfRuin && !isPhysical) {{
                defenseStat = Math.floor(defenseStat * 0.75);
            }}
            if (tabletsOfRuin && isPhysical) {{
                attackStat = Math.floor(attackStat * 0.75);
            }}
            if (vesselOfRuin && !isPhysical) {{
                attackStat = Math.floor(attackStat * 0.75);
            }}

            // Apply Commander (+100% stats)
            if (commanderActive) {{
                attackStat = Math.floor(attackStat * 2);
            }}

            // Apply attacker ability modifiers
            let abilityMod = 1.0;
            if (attackerAbility === 'adaptability') {{
                // Will be applied to STAB
            }} else if (attackerAbility === 'huge-power' || attackerAbility === 'pure-power') {{
                if (isPhysical) attackStat = Math.floor(attackStat * 2);
            }} else if (attackerAbility === 'gorilla-tactics' || attackerAbility === 'hustle') {{
                if (isPhysical) attackStat = Math.floor(attackStat * 1.5);
            }} else if (attackerAbility === 'guts') {{
                if (isPhysical) attackStat = Math.floor(attackStat * 1.5);
            }} else if (attackerAbility === 'technician' && calcData.movePower <= 60) {{
                abilityMod = 1.5;
            }} else if (attackerAbility === 'sheer-force') {{
                abilityMod = 1.3;
            }} else if (attackerAbility === 'tough-claws') {{
                abilityMod = 1.3;
            }} else if (attackerAbility === 'analytic') {{
                abilityMod = 1.3;
            }} else if (attackerAbility === 'iron-fist' || attackerAbility === 'reckless') {{
                abilityMod = 1.2;
            }} else if (attackerAbility === 'strong-jaw' || attackerAbility === 'mega-launcher' || attackerAbility === 'sharpness') {{
                abilityMod = 1.5;
            }} else if (attackerAbility === 'water-bubble' && calcData.moveType.toLowerCase() === 'water') {{
                abilityMod = 2.0;
            }} else if (attackerAbility === 'transistor' && calcData.moveType.toLowerCase() === 'electric') {{
                abilityMod = 1.3;
            }} else if ((attackerAbility === 'dragons-maw' && calcData.moveType.toLowerCase() === 'dragon') ||
                       (attackerAbility === 'steelworker' && calcData.moveType.toLowerCase() === 'steel') ||
                       (attackerAbility === 'steely-spirit' && calcData.moveType.toLowerCase() === 'steel') ||
                       (attackerAbility === 'rocky-payload' && calcData.moveType.toLowerCase() === 'rock')) {{
                abilityMod = 1.5;
            }} else if (attackerAbility === 'sand-force' && weather === 'sand') {{
                if (['rock', 'ground', 'steel'].includes(calcData.moveType.toLowerCase())) {{
                    abilityMod = 1.3;
                }}
            }} else if (attackerAbility === 'neuroforce' && calcData.typeEffectiveness > 1) {{
                abilityMod = 1.25;
            }} else if (attackerAbility === 'tinted-lens' && calcData.typeEffectiveness < 1) {{
                abilityMod = 2.0;
            }}

            // Apply defender ability modifiers
            let defAbilityMod = 1.0;
            if (defenderAbility === 'multiscale' || defenderAbility === 'shadow-shield') {{
                defAbilityMod = 0.5;  // Assumes full HP
            }} else if (defenderAbility === 'ice-scales' && !isPhysical) {{
                defAbilityMod = 0.5;
            }} else if (defenderAbility === 'fur-coat' && isPhysical) {{
                defAbilityMod = 0.5;
            }} else if (defenderAbility === 'filter' || defenderAbility === 'solid-rock' || defenderAbility === 'prism-armor') {{
                if (calcData.typeEffectiveness > 1) defAbilityMod = 0.75;
            }} else if (defenderAbility === 'fluffy' && isPhysical) {{
                defAbilityMod = 0.5;
            }} else if (defenderAbility === 'punk-rock') {{
                // Sound moves - would need move data
                defAbilityMod = 0.5;
            }} else if (defenderAbility === 'thick-fat') {{
                if (['fire', 'ice'].includes(calcData.moveType.toLowerCase())) {{
                    defAbilityMod = 0.5;
                }}
            }} else if (defenderAbility === 'heatproof' || defenderAbility === 'water-bubble-def') {{
                if (calcData.moveType.toLowerCase() === 'fire') {{
                    defAbilityMod = 0.5;
                }}
            }} else if (defenderAbility === 'purifying-salt') {{
                if (calcData.moveType.toLowerCase() === 'ghost') {{
                    defAbilityMod = 0.5;
                }}
            }} else if (defenderAbility === 'tera-shell') {{
                defAbilityMod = 0.5;  // Assumes full HP
            }}

            // Defender item defense modifier
            const defItem = defenseItemModifiers[defenderItem];
            if (defItem) {{
                if (defItem.type === 'special_defense' && !isPhysical) {{
                    defenseStat = Math.floor(defenseStat * defItem.mult);
                }} else if (defItem.type === 'both_defense') {{
                    defenseStat = Math.floor(defenseStat * defItem.mult);
                }}
            }}

            // Attacker item modifier
            let itemMod = 1.0;
            const atkItem = itemModifiers[attackerItem];
            if (atkItem) {{
                if (atkItem.type === 'all') {{
                    itemMod = atkItem.mult;
                }} else if (atkItem.type === atkStatName) {{
                    itemMod = atkItem.mult;
                }} else if (atkItem.type === 'super_effective' && calcData.typeEffectiveness > 1) {{
                    itemMod = atkItem.mult;
                }} else if (atkItem.type.toLowerCase() === calcData.moveType.toLowerCase()) {{
                    itemMod = atkItem.mult;
                }}
            }}

            // Base damage formula
            const level = 50;
            const power = calcData.movePower;
            let baseDamage = Math.floor(Math.floor(Math.floor(2 * level / 5 + 2) * power * attackStat / defenseStat) / 50 + 2);

            // Apply modifiers
            let damage = baseDamage;

            // Weather modifier
            const moveType = calcData.moveType.toLowerCase();
            if (weather === 'sun') {{
                if (moveType === 'fire') damage = Math.floor(damage * 1.5);
                else if (moveType === 'water') damage = Math.floor(damage * 0.5);
            }} else if (weather === 'rain') {{
                if (moveType === 'water') damage = Math.floor(damage * 1.5);
                else if (moveType === 'fire') damage = Math.floor(damage * 0.5);
            }}

            // Terrain modifier (grounded assumed)
            if (terrain === 'electric' && moveType === 'electric') {{
                damage = Math.floor(damage * 1.3);
            }} else if (terrain === 'grassy' && moveType === 'grass') {{
                damage = Math.floor(damage * 1.3);
            }} else if (terrain === 'psychic' && moveType === 'psychic') {{
                damage = Math.floor(damage * 1.3);
            }} else if (terrain === 'misty' && moveType === 'dragon') {{
                damage = Math.floor(damage * 0.5);
            }}

            // Screen modifier (Doubles format = 2/3 reduction)
            if (isPhysical && reflectUp && !auroraVeilUp) {{
                damage = Math.floor(damage * (2/3));
            }} else if (!isPhysical && lightScreenUp && !auroraVeilUp) {{
                damage = Math.floor(damage * (2/3));
            }}
            if (auroraVeilUp) {{
                damage = Math.floor(damage * (2/3));
            }}

            // Apply item modifier
            damage = Math.floor(damage * itemMod);

            // Apply ability modifier
            damage = Math.floor(damage * abilityMod);

            // Determine effective move type (for Tera Blast)
            let effectiveMoveType = calcData.moveType.toLowerCase();
            if (calcData.move.toLowerCase() === 'tera blast' && attackerTeraActive && attackerTeraType) {{
                effectiveMoveType = attackerTeraType.toLowerCase();
            }}

            // Determine attacker's types for STAB calculation
            let attackerTypesForStab = [...calcData.attackerTypes];
            if (attackerTeraActive && attackerTeraType) {{
                // When Terastallized, can get STAB from Tera type
                attackerTypesForStab = [attackerTeraType.toLowerCase()];
            }}

            // STAB - only apply if move type matches attacker's types
            let stabMod = 1.0;
            const moveMatchesType = attackerTypesForStab.some(t => t === effectiveMoveType);
            const moveMatchesOriginalType = calcData.attackerTypes.some(t => t === effectiveMoveType);

            if (moveMatchesType) {{
                // Terastallized into matching type or using original type
                if (attackerTeraActive && moveMatchesOriginalType) {{
                    // Tera type matches original type AND move type = 2.0x STAB
                    stabMod = attackerAbility.toLowerCase() === 'adaptability' ? 2.25 : 2.0;
                }} else {{
                    stabMod = attackerAbility.toLowerCase() === 'adaptability' ? 2.0 : 1.5;
                }}
            }} else if (!attackerTeraActive && moveMatchesOriginalType) {{
                // Not Terastallized but move matches original type
                stabMod = attackerAbility.toLowerCase() === 'adaptability' ? 2.0 : 1.5;
            }}
            damage = Math.floor(damage * stabMod);

            // Determine defender's types for effectiveness calculation
            let defenderTypesForEff = [...calcData.defenderTypes];
            if (defenderTeraActive && defenderTeraType) {{
                // When Terastallized, defender becomes mono-type
                defenderTypesForEff = [defenderTeraType.toLowerCase()];
            }}

            // Type effectiveness - recalculate based on current types
            const typeEff = getTypeEffectiveness(effectiveMoveType, defenderTypesForEff);
            damage = Math.floor(damage * typeEff);

            // Apply defender ability modifier
            damage = Math.floor(damage * defAbilityMod);

            // Helping Hand (+50%)
            if (helpingHand) {{
                damage = Math.floor(damage * 1.5);
            }}

            // Friend Guard (-25%)
            if (friendGuard) {{
                damage = Math.floor(damage * 0.75);
            }}

            // Random roll range (0.85 to 1.0)
            const minDamage = Math.floor(damage * 0.85);
            const maxDamage = damage;

            // Calculate percentages
            const minPct = (minDamage / defenderHP) * 100;
            const maxPct = (maxDamage / defenderHP) * 100;

            return {{
                minPct: Math.min(minPct, 999),
                maxPct: Math.min(maxPct, 999),
                defenderHP: defenderHP
            }};
        }}

        // Calculate probability for KO at a given threshold
        // Pokemon damage has 16 rolls from 0.85 to 1.00 in even steps
        function calcKOProbability(minPct, maxPct, threshold) {{
            if (minPct >= threshold) return 100;
            if (maxPct < threshold) return 0;
            // Linear interpolation: how many of 16 rolls exceed threshold?
            const range = maxPct - minPct;
            if (range <= 0) return minPct >= threshold ? 100 : 0;
            const rollsAbove = Math.floor(((maxPct - threshold) / range) * 16) + 1;
            return Math.round((rollsAbove / 16) * 100);
        }}

        // Determine KO chance with probability
        function getKOChance(minPct, maxPct) {{
            // OHKO check
            if (minPct >= 100) return {{ text: 'Guaranteed OHKO', class: 'ohko' }};
            if (maxPct >= 100) {{
                const prob = calcKOProbability(minPct, maxPct, 100);
                return {{ text: prob + '% OHKO', class: 'ohko' }};
            }}
            // 2HKO check (need 50% per hit)
            if (minPct >= 50) return {{ text: 'Guaranteed 2HKO', class: '2hko' }};
            if (maxPct >= 50) {{
                const prob = calcKOProbability(minPct, maxPct, 50);
                return {{ text: prob + '% 2HKO', class: '2hko' }};
            }}
            // 3HKO check (need 33.4% per hit)
            if (minPct >= 33.4) return {{ text: 'Guaranteed 3HKO', class: '3hko' }};
            if (maxPct >= 33.4) {{
                const prob = calcKOProbability(minPct, maxPct, 33.4);
                return {{ text: prob + '% 3HKO', class: '3hko' }};
            }}
            // 4HKO check (need 25% per hit)
            if (minPct >= 25) return {{ text: '4HKO', class: 'survive' }};
            if (maxPct >= 25) {{
                const prob = calcKOProbability(minPct, maxPct, 25);
                return {{ text: prob + '% 4HKO', class: 'survive' }};
            }}
            return {{ text: 'Survives', class: 'survive' }};
        }}

        // Recalculate and update UI
        let recalcTimeout;
        function recalculateDamage() {{
            // Debounce to avoid too many recalculations
            clearTimeout(recalcTimeout);
            recalcTimeout = setTimeout(() => {{
                const result = calculateDamage();
                const ko = getKOChance(result.minPct, result.maxPct);

                // Update damage display
                document.getElementById('damage-numbers').textContent =
                    `${{result.minPct.toFixed(1)}}% - ${{result.maxPct.toFixed(1)}}%`;

                // Update damage bar
                const displayMax = Math.min(result.maxPct, 100);
                const displayMin = Math.min(result.minPct, 100);
                document.getElementById('damage-fill').style.width = displayMax + '%';
                document.getElementById('damage-range').style.left = displayMin + '%';
                document.getElementById('damage-range').style.width = (displayMax - displayMin) + '%';

                // Update KO badge
                const badge = document.getElementById('ko-badge');
                badge.textContent = ko.text;
                badge.className = 'ko-badge ' + ko.class;
            }}, 100);
        }}

        // Type color mapping for move display
        function getTypeColor(type) {{
            const colors = {{
                normal: '#A8A878', fire: '#F08030', water: '#6890F0', electric: '#F8D030',
                grass: '#78C850', ice: '#98D8D8', fighting: '#C03028', poison: '#A040A0',
                ground: '#E0C068', flying: '#A890F0', psychic: '#F85888', bug: '#A8B820',
                rock: '#B8A038', ghost: '#705898', dragon: '#7038F8', dark: '#705848',
                steel: '#B8B8D0', fairy: '#EE99AC'
            }};
            return colors[type.toLowerCase()] || '#888888';
        }}

        // Handle move selection change
        function onMoveChange() {{
            const select = document.getElementById('move-select');
            const selectedOption = select.options[select.selectedIndex];

            const moveType = selectedOption.dataset.type || 'normal';
            const movePower = parseInt(selectedOption.dataset.power) || 0;
            const moveCategory = selectedOption.dataset.category || 'special';

            // Update calcData with new move info
            calcData.movePower = movePower;
            calcData.moveType = moveType;
            calcData.moveCategory = moveCategory;

            // Update UI displays
            const typeBadge = document.getElementById('move-type-badge');
            typeBadge.textContent = moveType.toUpperCase();
            typeBadge.style.background = getTypeColor(moveType);

            document.getElementById('move-power-display').textContent = movePower + ' BP';

            const categoryBadge = document.getElementById('move-category');
            categoryBadge.textContent = moveCategory.toUpperCase();
            categoryBadge.className = 'move-category ' + moveCategory;

            // Recalculate damage with new move
            recalculateDamage();
        }}

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {{
            updateEVTotal('attacker');
            updateEVTotal('defender');

            // Add fallback for animated sprites that fail to load
            document.querySelectorAll('.pokemon-sprite').forEach(img => {{
                img.onerror = function() {{
                    const name = this.alt.toLowerCase().replace(/ /g, '-').replace(/\\./g, '');
                    this.src = 'https://img.pokemondb.net/sprites/home/normal/' + name + '.png';
                    this.onerror = null; // Prevent infinite loop
                }};
            }});
        }});
    </script>
</body>
</html>"""


def _create_static_damage_calc_ui(
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
    """Create static (non-interactive) damage calculator UI HTML.

    This is the lightweight version that just displays the result.
    For interactive editing of EVs/natures, use create_damage_calc_ui(interactive=True).
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
                {get_sprite_html(attacker, size=80, css_class="pokemon-sprite")}
                <div class="pokemon-name">{attacker}</div>
                {attacker_item_html}
            </div>

            <!-- Arrow and move -->
            <div style="text-align: center; padding: 0 16px;">
                <div style="font-size: 24px; color: #4da6ff;">&rarr;</div>
                <div style="font-size: 14px; font-weight: 600;">{move}</div>
                {move_type_html}
            </div>

            <!-- Defender -->
            <div style="flex: 1; text-align: center;">
                {get_sprite_html(defender, size=80, css_class="pokemon-sprite")}
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
    """Create team roster UI HTML with glassmorphism and staggered animations.

    Args:
        team: List of Pokemon dicts with keys: name, item, ability, moves, evs, types, tera_type
        team_name: Optional team name

    Returns:
        HTML string for the team roster UI
    """
    # Build Pokemon cards with staggered animation delays
    cards_html = ""
    for i, pokemon in enumerate(team):
        name = pokemon.get("name", "Unknown")
        item = pokemon.get("item", "None")
        ability = pokemon.get("ability", "Unknown")
        moves = pokemon.get("moves", [])
        evs = pokemon.get("evs", {})
        types = pokemon.get("types", [])
        tera_type = pokemon.get("tera_type")
        nature = pokemon.get("nature", "")

        # Get primary type for card gradient
        primary_type = types[0].lower() if types else "normal"

        # Type badges with enhanced styling
        type_badges = " ".join(
            f'<span class="type-badge-modern type-{t.lower()}">{t}</span>'
            for t in types
        )

        # Tera type badge with crystalline effect
        tera_html = ""
        if tera_type:
            tera_color = get_type_color(tera_type)
            tera_html = f'''<span class="tera-badge" style="--tera-color: {tera_color};">
                <span class="tera-icon">&#10022;</span> Tera {tera_type}
            </span>'''

        # Moves with type colors
        moves_html = ""
        for move_data in moves[:4]:
            if isinstance(move_data, dict):
                move_name = move_data.get("name", "Unknown")
                move_type = move_data.get("type", "normal")
            else:
                move_name = str(move_data)
                move_type = "normal"
            move_color = get_type_color(move_type)
            moves_html += f'<span class="move-pill" style="--move-color: {move_color};">{move_name}</span>'

        # EVs summary with stat colors
        ev_parts = []
        stat_colors = {
            "hp": "#ff5959", "attack": "#f5ac78", "defense": "#fae078",
            "special_attack": "#9db7f5", "special_defense": "#a7db8d", "speed": "#fa92b2"
        }
        for stat, val in evs.items():
            if val and val > 0:
                stat_abbr = {"hp": "HP", "attack": "Atk", "defense": "Def", "special_attack": "SpA", "special_defense": "SpD", "speed": "Spe"}.get(stat, stat)
                color = stat_colors.get(stat, "#888")
                ev_parts.append(f'<span style="color: {color};">{val} {stat_abbr}</span>')
        evs_html = " / ".join(ev_parts[:3]) if ev_parts else '<span style="color: #666;">No EVs</span>'
        if len(ev_parts) > 3:
            evs_html += f' <span style="color: #666;">(+{len(ev_parts) - 3})</span>'

        # Animation delay based on card index
        delay = i * 0.1

        cards_html += f"""
        <div class="team-card" style="animation-delay: {delay}s; --type-color: {get_type_color(primary_type)};">
            <div class="card-shine"></div>
            <div class="card-content">
                <div class="sprite-wrapper">
                    {get_sprite_html(name, size=72, css_class="team-sprite")}
                </div>
                <div class="pokemon-details">
                    <div class="pokemon-header">
                        <span class="poke-name">{name}</span>
                        {f'<span class="nature-tag">{nature}</span>' if nature else ''}
                    </div>
                    <div class="types-row">{type_badges} {tera_html}</div>
                    <div class="item-row">
                        <span class="item-icon">&#128188;</span>
                        <span class="item-name">{item}</span>
                    </div>
                    <div class="ability-row">{ability}</div>
                    <div class="moves-grid">{moves_html}</div>
                    <div class="evs-row">{evs_html}</div>
                </div>
            </div>
        </div>
        """

    # Team header with count
    header_text = team_name if team_name else "Team Roster"
    slots_remaining = 6 - len(team)
    slots_badge = f'<span class="slots-badge">{len(team)}/6</span>'
    empty_slots = ""
    if slots_remaining > 0:
        empty_slots = f'<span class="empty-slots">{slots_remaining} slot{"s" if slots_remaining != 1 else ""} remaining</span>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%);
    color: #e4e4e7;
    line-height: 1.5;
    min-height: 100vh;
    padding: 24px;
}}

/* Ambient background glow */
body::before {{
    content: "";
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background-image:
        radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.08) 0%, transparent 40%),
        radial-gradient(circle at 80% 70%, rgba(139, 92, 246, 0.06) 0%, transparent 40%);
    pointer-events: none;
    z-index: -1;
}}

/* Keyframe animations */
@keyframes fadeSlideIn {{
    0% {{ opacity: 0; transform: translateY(30px) scale(0.95); }}
    100% {{ opacity: 1; transform: translateY(0) scale(1); }}
}}

@keyframes shimmer {{
    0% {{ background-position: -200% 0; }}
    100% {{ background-position: 200% 0; }}
}}

@keyframes spriteBounce {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-6px); }}
}}

@keyframes pulseGlow {{
    0%, 100% {{ box-shadow: 0 0 20px var(--type-color, rgba(99, 102, 241, 0.3)); }}
    50% {{ box-shadow: 0 0 35px var(--type-color, rgba(99, 102, 241, 0.5)); }}
}}

/* Container */
.roster-container {{
    max-width: 1200px;
    margin: 0 auto;
}}

/* Header */
.roster-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 28px;
    padding: 20px 24px;
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}}

.header-title {{
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 12px;
}}

.slots-badge {{
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    padding: 6px 14px;
    border-radius: 20px;
    font-size: 13px;
    font-weight: 700;
    color: #fff;
    box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}}

.empty-slots {{
    font-size: 13px;
    color: #71717a;
}}

/* Team grid */
.team-grid-modern {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(320px, 1fr));
    gap: 20px;
}}

@media (max-width: 720px) {{
    .team-grid-modern {{
        grid-template-columns: 1fr;
    }}
}}

/* Team card - glassmorphism */
.team-card {{
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    position: relative;
    animation: fadeSlideIn 0.6s cubic-bezier(0.4, 0, 0.2, 1) backwards;
    transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow:
        0 4px 24px rgba(0, 0, 0, 0.2),
        inset 0 1px 0 rgba(255, 255, 255, 0.03);
}}

.team-card:hover {{
    transform: translateY(-6px);
    border-color: rgba(255, 255, 255, 0.12);
    box-shadow:
        0 20px 40px rgba(0, 0, 0, 0.3),
        0 0 30px var(--type-color, rgba(99, 102, 241, 0.15));
}}

/* Card shine effect */
.card-shine {{
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: linear-gradient(
        135deg,
        transparent 0%,
        rgba(255, 255, 255, 0.03) 40%,
        rgba(255, 255, 255, 0.08) 50%,
        rgba(255, 255, 255, 0.03) 60%,
        transparent 100%
    );
    background-size: 200% 200%;
    opacity: 0;
    transition: opacity 0.4s ease;
    pointer-events: none;
}}

.team-card:hover .card-shine {{
    opacity: 1;
    animation: shimmer 2s ease-in-out infinite;
}}

.card-content {{
    display: flex;
    gap: 16px;
    padding: 20px;
    position: relative;
    z-index: 1;
}}

/* Sprite wrapper */
.sprite-wrapper {{
    flex-shrink: 0;
    width: 96px;
    height: 96px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: radial-gradient(circle, rgba(255, 255, 255, 0.05) 0%, transparent 70%);
    border-radius: 16px;
}}

.team-sprite {{
    width: 80px;
    height: 80px;
    image-rendering: auto;
    filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4));
    transition: transform 0.3s ease;
}}

.team-card:hover .team-sprite {{
    animation: spriteBounce 0.6s ease;
}}

/* Pokemon details */
.pokemon-details {{
    flex: 1;
    min-width: 0;
}}

.pokemon-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
}}

.poke-name {{
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    letter-spacing: -0.02em;
}}

.nature-tag {{
    font-size: 10px;
    padding: 3px 8px;
    background: rgba(139, 92, 246, 0.2);
    color: #a78bfa;
    border-radius: 6px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

/* Type badges */
.types-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}}

.type-badge-modern {{
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #fff;
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}}

/* Type colors */
.type-normal {{ background: linear-gradient(135deg, #A8A878, #8a8a5c); }}
.type-fire {{ background: linear-gradient(135deg, #F08030, #c4682a); }}
.type-water {{ background: linear-gradient(135deg, #6890F0, #5070c0); }}
.type-electric {{ background: linear-gradient(135deg, #F8D030, #c4a828); }}
.type-grass {{ background: linear-gradient(135deg, #78C850, #5ca040); }}
.type-ice {{ background: linear-gradient(135deg, #98D8D8, #70b0b0); }}
.type-fighting {{ background: linear-gradient(135deg, #C03028, #901820); }}
.type-poison {{ background: linear-gradient(135deg, #A040A0, #803080); }}
.type-ground {{ background: linear-gradient(135deg, #E0C068, #b09048); }}
.type-flying {{ background: linear-gradient(135deg, #A890F0, #8070c0); }}
.type-psychic {{ background: linear-gradient(135deg, #F85888, #c04060); }}
.type-bug {{ background: linear-gradient(135deg, #A8B820, #889010); }}
.type-rock {{ background: linear-gradient(135deg, #B8A038, #907820); }}
.type-ghost {{ background: linear-gradient(135deg, #705898, #504070); }}
.type-dragon {{ background: linear-gradient(135deg, #7038F8, #5028c0); }}
.type-dark {{ background: linear-gradient(135deg, #705848, #503830); }}
.type-steel {{ background: linear-gradient(135deg, #B8B8D0, #9090a8); }}
.type-fairy {{ background: linear-gradient(135deg, #EE99AC, #c07088); }}

/* Tera badge */
.tera-badge {{
    display: inline-flex;
    align-items: center;
    gap: 4px;
    padding: 4px 10px;
    background: linear-gradient(135deg, rgba(255, 255, 255, 0.1), rgba(255, 255, 255, 0.05));
    border: 1px dashed var(--tera-color, #fff);
    border-radius: 6px;
    font-size: 10px;
    font-weight: 600;
    color: var(--tera-color, #fff);
}}

.tera-icon {{
    font-size: 12px;
}}

/* Item row */
.item-row {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 12px;
    color: #a1a1aa;
    margin-bottom: 4px;
}}

.item-icon {{
    font-size: 14px;
}}

.item-name {{
    font-weight: 500;
}}

/* Ability row */
.ability-row {{
    font-size: 11px;
    color: #71717a;
    font-style: italic;
    margin-bottom: 10px;
}}

/* Moves grid */
.moves-grid {{
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin-bottom: 10px;
}}

.move-pill {{
    padding: 4px 10px;
    background: var(--move-color, #888);
    border-radius: 12px;
    font-size: 11px;
    font-weight: 600;
    color: #fff;
    box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2);
    transition: transform 0.2s ease, box-shadow 0.2s ease;
}}

.move-pill:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
}}

/* EVs row */
.evs-row {{
    font-size: 11px;
    color: #888;
    padding-top: 8px;
    border-top: 1px solid rgba(255, 255, 255, 0.05);
}}
    </style>
</head>
<body>
    <div class="roster-container">
        <div class="roster-header">
            <div class="header-title">
                {header_text}
                {slots_badge}
            </div>
            {empty_slots}
        </div>
        <div class="team-grid-modern">
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
    """Create speed tier analyzer UI HTML with race track visualization.

    Args:
        pokemon_name: Name of the Pokemon being analyzed
        pokemon_speed: Calculated speed stat
        speed_tiers: List of dicts with keys: name, speed, common (bool)
        modifiers: Active modifiers dict (tailwind, trick_room, paralysis, choice_scarf)

    Returns:
        HTML string for the speed tier UI
    """
    modifiers = modifiers or {}

    # Calculate max speed for positioning
    all_speeds = [t.get("speed", 0) for t in speed_tiers] + [pokemon_speed]
    max_speed = max(all_speeds) if all_speeds else 200
    min_speed = min(all_speeds) if all_speeds else 0

    # Build modifier toggle buttons
    mod_buttons = ""
    tailwind_active = "active" if modifiers.get("tailwind") else ""
    trick_room_active = "active" if modifiers.get("trick_room") else ""
    scarf_active = "active" if modifiers.get("choice_scarf") else ""
    paralysis_active = "active" if modifiers.get("paralysis") else ""

    mod_buttons = f"""
    <div class="modifier-toggles">
        <button class="mod-btn tailwind {tailwind_active}" data-mod="tailwind">
            <span class="mod-icon">&#127744;</span> Tailwind
        </button>
        <button class="mod-btn trick-room {trick_room_active}" data-mod="trick_room">
            <span class="mod-icon">&#128302;</span> Trick Room
        </button>
        <button class="mod-btn scarf {scarf_active}" data-mod="choice_scarf">
            <span class="mod-icon">&#129507;</span> Scarf
        </button>
        <button class="mod-btn paralysis {paralysis_active}" data-mod="paralysis">
            <span class="mod-icon">&#9889;</span> Paralyzed
        </button>
    </div>
    """

    # Sort tiers by speed (descending, or ascending for Trick Room)
    is_trick_room = modifiers.get("trick_room", False)
    sorted_tiers = sorted(speed_tiers, key=lambda x: x.get("speed", 0), reverse=not is_trick_room)

    # Build race track lanes
    lanes_html = ""
    position = 1

    # Add user's Pokemon to the mix for sorting
    all_pokemon = sorted_tiers.copy()
    user_entry = {"name": pokemon_name, "speed": pokemon_speed, "is_user": True}
    all_pokemon.append(user_entry)

    # Re-sort with user included
    all_pokemon = sorted(all_pokemon, key=lambda x: x.get("speed", 0), reverse=not is_trick_room)

    for i, tier in enumerate(all_pokemon):
        tier_name = tier.get("name", "Unknown")
        tier_speed = tier.get("speed", 0)
        is_common = tier.get("common", False)
        is_user = tier.get("is_user", False)

        # Calculate position percentage (how far along the track)
        if max_speed > min_speed:
            if is_trick_room:
                # In Trick Room, lower speed = further along
                position_pct = 100 - ((tier_speed - min_speed) / (max_speed - min_speed) * 100)
            else:
                position_pct = (tier_speed - min_speed) / (max_speed - min_speed) * 100
        else:
            position_pct = 50

        # Determine lane class
        if is_user:
            lane_class = "user-lane"
            indicator = "&#9733;"
        elif is_trick_room:
            lane_class = "faster-lane" if tier_speed < pokemon_speed else "slower-lane"
            indicator = "&#9679;" if is_common else ""
        else:
            lane_class = "faster-lane" if tier_speed > pokemon_speed else "slower-lane"
            indicator = "&#9679;" if is_common else ""

        # Speed tie detection
        speed_tie = ""
        if tier_speed == pokemon_speed and not is_user:
            speed_tie = '<span class="speed-tie-badge">SPEED TIE</span>'
            lane_class = "tie-lane"

        # Animation delay based on position
        delay = i * 0.05

        lanes_html += f"""
        <div class="race-lane {lane_class}" style="animation-delay: {delay}s;">
            <div class="lane-position">#{position}</div>
            <div class="lane-sprite">
                {get_sprite_html(tier_name, size=48, css_class="racer-sprite")}
            </div>
            <div class="lane-info">
                <span class="racer-name">{tier_name} {indicator}</span>
                {speed_tie}
            </div>
            <div class="lane-track">
                <div class="track-bar">
                    <div class="track-fill" style="width: {position_pct}%;"></div>
                    <div class="track-marker" style="left: {position_pct}%;"></div>
                </div>
            </div>
            <div class="lane-speed">{tier_speed}</div>
        </div>
        """
        position += 1

    # Speed stat summary
    faster_count = sum(1 for t in speed_tiers if (t.get("speed", 0) > pokemon_speed) != is_trick_room)
    slower_count = sum(1 for t in speed_tiers if (t.get("speed", 0) < pokemon_speed) != is_trick_room)
    tie_count = sum(1 for t in speed_tiers if t.get("speed", 0) == pokemon_speed)

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%);
    color: #e4e4e7;
    line-height: 1.5;
    min-height: 100vh;
    padding: 24px;
}}

/* Keyframes */
@keyframes slideIn {{
    0% {{ opacity: 0; transform: translateX(-20px); }}
    100% {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes fillTrack {{
    0% {{ width: 0%; }}
    100% {{ width: var(--fill-width, 50%); }}
}}

@keyframes pulse {{
    0%, 100% {{ transform: scale(1); }}
    50% {{ transform: scale(1.1); }}
}}

@keyframes bounce {{
    0%, 100% {{ transform: translateY(0); }}
    50% {{ transform: translateY(-4px); }}
}}

/* Container */
.speed-container {{
    max-width: 900px;
    margin: 0 auto;
}}

/* Header */
.speed-header {{
    padding: 24px;
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}}

.header-top {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 20px;
}}

.header-title {{
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 12px;
}}

.header-title::before {{
    content: "&#127939;";
    font-size: 28px;
}}

.speed-summary {{
    display: flex;
    gap: 16px;
}}

.summary-stat {{
    padding: 8px 16px;
    border-radius: 12px;
    font-size: 13px;
    font-weight: 600;
}}

.summary-stat.faster {{
    background: rgba(239, 68, 68, 0.15);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.2);
}}

.summary-stat.slower {{
    background: rgba(34, 197, 94, 0.15);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.2);
}}

.summary-stat.ties {{
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.2);
}}

/* Modifier toggles */
.modifier-toggles {{
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
}}

.mod-btn {{
    padding: 10px 18px;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    background: rgba(255, 255, 255, 0.03);
    color: #71717a;
    font-size: 13px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s ease;
    display: flex;
    align-items: center;
    gap: 6px;
}}

.mod-btn:hover {{
    background: rgba(255, 255, 255, 0.08);
    border-color: rgba(255, 255, 255, 0.15);
    color: #a1a1aa;
}}

.mod-btn.active {{
    color: #fff;
}}

.mod-btn.tailwind.active {{
    background: linear-gradient(135deg, rgba(96, 165, 250, 0.3), rgba(59, 130, 246, 0.2));
    border-color: rgba(96, 165, 250, 0.4);
    box-shadow: 0 0 20px rgba(96, 165, 250, 0.2);
}}

.mod-btn.trick-room.active {{
    background: linear-gradient(135deg, rgba(248, 88, 136, 0.3), rgba(236, 72, 153, 0.2));
    border-color: rgba(248, 88, 136, 0.4);
    box-shadow: 0 0 20px rgba(248, 88, 136, 0.2);
}}

.mod-btn.scarf.active {{
    background: linear-gradient(135deg, rgba(251, 146, 60, 0.3), rgba(249, 115, 22, 0.2));
    border-color: rgba(251, 146, 60, 0.4);
    box-shadow: 0 0 20px rgba(251, 146, 60, 0.2);
}}

.mod-btn.paralysis.active {{
    background: linear-gradient(135deg, rgba(250, 204, 21, 0.3), rgba(234, 179, 8, 0.2));
    border-color: rgba(250, 204, 21, 0.4);
    box-shadow: 0 0 20px rgba(250, 204, 21, 0.2);
    color: #333;
}}

.mod-icon {{
    font-size: 16px;
}}

/* Race track */
.race-track {{
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}}

.track-header {{
    display: grid;
    grid-template-columns: 50px 64px 1fr 2fr 80px;
    gap: 12px;
    padding: 12px 20px;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #52525b;
}}

.lanes-container {{
    max-height: 500px;
    overflow-y: auto;
}}

/* Race lane */
.race-lane {{
    display: grid;
    grid-template-columns: 50px 64px 1fr 2fr 80px;
    gap: 12px;
    padding: 12px 20px;
    align-items: center;
    border-bottom: 1px solid rgba(255, 255, 255, 0.03);
    animation: slideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) backwards;
    transition: background 0.3s ease;
}}

.race-lane:hover {{
    background: rgba(255, 255, 255, 0.03);
}}

.race-lane:last-child {{
    border-bottom: none;
}}

/* Lane position */
.lane-position {{
    font-size: 14px;
    font-weight: 700;
    color: #52525b;
}}

/* Lane sprite */
.lane-sprite {{
    width: 48px;
    height: 48px;
    display: flex;
    align-items: center;
    justify-content: center;
}}

.racer-sprite {{
    width: 40px;
    height: 40px;
    image-rendering: auto;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
    transition: transform 0.3s ease;
}}

.race-lane:hover .racer-sprite {{
    animation: bounce 0.5s ease;
}}

/* Lane info */
.lane-info {{
    display: flex;
    flex-direction: column;
    gap: 4px;
}}

.racer-name {{
    font-size: 14px;
    font-weight: 600;
    color: #e4e4e7;
}}

.speed-tie-badge {{
    display: inline-block;
    padding: 2px 8px;
    background: linear-gradient(135deg, rgba(251, 191, 36, 0.3), rgba(234, 179, 8, 0.2));
    border: 1px solid rgba(251, 191, 36, 0.4);
    border-radius: 6px;
    font-size: 9px;
    font-weight: 700;
    color: #fbbf24;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    animation: pulse 2s infinite;
}}

/* Lane track visualization */
.lane-track {{
    position: relative;
}}

.track-bar {{
    height: 8px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    overflow: visible;
    position: relative;
}}

.track-fill {{
    height: 100%;
    border-radius: 4px;
    transition: width 0.6s cubic-bezier(0.4, 0, 0.2, 1);
}}

.track-marker {{
    position: absolute;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 16px;
    height: 16px;
    border-radius: 50%;
    transition: left 0.6s cubic-bezier(0.4, 0, 0.2, 1);
    box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
}}

/* Lane speed value */
.lane-speed {{
    font-size: 18px;
    font-weight: 800;
    text-align: right;
    font-variant-numeric: tabular-nums;
}}

/* Lane type styling */
.faster-lane .track-fill {{
    background: linear-gradient(90deg, rgba(239, 68, 68, 0.3), rgba(239, 68, 68, 0.6));
}}
.faster-lane .track-marker {{
    background: linear-gradient(135deg, #f87171, #ef4444);
}}
.faster-lane .lane-speed {{
    color: #f87171;
}}
.faster-lane .lane-position {{
    color: #f87171;
}}

.slower-lane .track-fill {{
    background: linear-gradient(90deg, rgba(34, 197, 94, 0.3), rgba(34, 197, 94, 0.6));
}}
.slower-lane .track-marker {{
    background: linear-gradient(135deg, #4ade80, #22c55e);
}}
.slower-lane .lane-speed {{
    color: #4ade80;
}}
.slower-lane .lane-position {{
    color: #4ade80;
}}

.user-lane {{
    background: rgba(99, 102, 241, 0.08);
}}
.user-lane .track-fill {{
    background: linear-gradient(90deg, rgba(99, 102, 241, 0.4), rgba(139, 92, 246, 0.7));
}}
.user-lane .track-marker {{
    background: linear-gradient(135deg, #a78bfa, #8b5cf6);
    box-shadow: 0 0 16px rgba(139, 92, 246, 0.5);
}}
.user-lane .lane-speed {{
    color: #a78bfa;
}}
.user-lane .lane-position {{
    color: #a78bfa;
}}
.user-lane .racer-name {{
    color: #fff;
}}

.tie-lane {{
    background: rgba(251, 191, 36, 0.05);
}}
.tie-lane .track-fill {{
    background: linear-gradient(90deg, rgba(251, 191, 36, 0.3), rgba(251, 191, 36, 0.6));
}}
.tie-lane .track-marker {{
    background: linear-gradient(135deg, #fbbf24, #f59e0b);
}}
.tie-lane .lane-speed {{
    color: #fbbf24;
}}

/* Scrollbar */
.lanes-container::-webkit-scrollbar {{
    width: 8px;
}}
.lanes-container::-webkit-scrollbar-track {{
    background: rgba(0, 0, 0, 0.2);
}}
.lanes-container::-webkit-scrollbar-thumb {{
    background: rgba(99, 102, 241, 0.4);
    border-radius: 4px;
}}
.lanes-container::-webkit-scrollbar-thumb:hover {{
    background: rgba(99, 102, 241, 0.6);
}}

/* Legend */
.track-legend {{
    display: flex;
    gap: 20px;
    padding: 16px 20px;
    background: rgba(255, 255, 255, 0.02);
    border-top: 1px solid rgba(255, 255, 255, 0.06);
    font-size: 12px;
}}

.legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    color: #71717a;
}}

.legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
}}

.legend-dot.faster {{ background: #f87171; }}
.legend-dot.yours {{ background: #a78bfa; }}
.legend-dot.slower {{ background: #4ade80; }}
.legend-dot.tie {{ background: #fbbf24; }}
    </style>
</head>
<body>
    <div class="speed-container">
        <div class="speed-header">
            <div class="header-top">
                <div class="header-title">Speed Tier Analysis</div>
                <div class="speed-summary">
                    <span class="summary-stat faster">{faster_count} Faster</span>
                    <span class="summary-stat ties">{tie_count} Ties</span>
                    <span class="summary-stat slower">{slower_count} Slower</span>
                </div>
            </div>
            {mod_buttons}
        </div>

        <div class="race-track">
            <div class="track-header">
                <span>Rank</span>
                <span>Pokemon</span>
                <span>Name</span>
                <span>Position</span>
                <span>Speed</span>
            </div>
            <div class="lanes-container">
                {lanes_html}
            </div>
            <div class="track-legend">
                <div class="legend-item"><span class="legend-dot faster"></span> Outspeeds you</div>
                <div class="legend-item"><span class="legend-dot yours"></span> Your Pokemon</div>
                <div class="legend-item"><span class="legend-dot slower"></span> You outspeed</div>
                <div class="legend-item"><span class="legend-dot tie"></span> Speed tie</div>
            </div>
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
            indicator = "&#128994;"
        elif verdict == "unfavorable":
            row_color = "rgba(244, 67, 54, 0.1)"
            indicator = "&#128308;"
        else:
            row_color = "transparent"
            indicator = "&#128993;"

        rows_html += f"""
        <div style="display: flex; align-items: center; padding: 8px; background: {row_color}; border-radius: 4px; margin: 4px 0;">
            <span style="font-size: 16px; margin-right: 8px;">{indicator}</span>
            {get_sprite_html(opponent, size=40, css_class="matchup-sprite")}
            <div style="flex: 1; margin-left: 8px;">
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
                <span style="color: #4caf50;">&#10003; {favorable}</span>
                <span style="color: #888; margin: 0 8px;">~ {neutral}</span>
                <span style="color: #f44336;">&#10007; {unfavorable}</span>
            </div>
        </div>
        <div style="max-height: 350px; overflow-y: auto;">
            {rows_html}
        </div>
    </div>
</body>
</html>"""


def create_threat_analysis_ui(
    threat_name: str,
    threat_speed: int,
    ohko_by: list[str],
    twohko_by: list[str],
    checks: list[str],
    counters: list[str],
    threatened: list[str],
    survives: list[str],
    notes: list[str] | None = None,
) -> str:
    """Create an interactive threat analysis UI.

    Args:
        threat_name: Name of the threat Pokemon
        threat_speed: Speed stat of the threat
        ohko_by: List of team Pokemon that can OHKO the threat
        twohko_by: List of team Pokemon that can 2HKO the threat
        checks: List of team Pokemon that check the threat
        counters: List of team Pokemon that counter the threat
        threatened: List of team Pokemon threatened by this threat
        survives: List of team Pokemon that survive the threat's attack
        notes: Additional notes

    Returns:
        HTML string for the threat analysis UI
    """
    # Build category sections
    def build_pokemon_list(pokemon_list: list[str], empty_msg: str) -> str:
        if not pokemon_list:
            return f'<div class="empty-list">{empty_msg}</div>'
        items = "".join(
            f'''<div class="pokemon-chip">
                {get_sprite_html(p, size=32, css_class="chip-sprite")}
                <span>{p}</span>
            </div>'''
            for p in pokemon_list
        )
        return f'<div class="pokemon-list">{items}</div>'

    ohko_html = build_pokemon_list(ohko_by, "None can OHKO")
    twohko_html = build_pokemon_list(twohko_by, "None can 2HKO")
    checks_html = build_pokemon_list(checks, "No checks available")
    counters_html = build_pokemon_list(counters, "No counters available")
    threatened_html = build_pokemon_list(threatened, "No Pokemon threatened")
    survives_html = build_pokemon_list(survives, "None survive")

    # Notes section
    notes_html = ""
    if notes:
        notes_items = "".join(f"<li>{note}</li>" for note in notes)
        notes_html = f'<ul class="notes-list">{notes_items}</ul>'

    # Calculate threat level
    threat_level = "low"
    threat_color = "#22c55e"
    if len(threatened) >= 4:
        threat_level = "critical"
        threat_color = "#dc2626"
    elif len(threatened) >= 2:
        threat_level = "high"
        threat_color = "#ea580c"
    elif len(threatened) >= 1:
        threat_level = "moderate"
        threat_color = "#eab308"

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: #0f0f1a;
    color: #e4e4e7;
    line-height: 1.5;
}}

.threat-container {{
    max-width: 600px;
    margin: 0 auto;
    padding: 20px;
}}

.threat-header {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.1) 0%, rgba(220, 38, 38, 0.05) 100%);
    border-radius: 16px;
    border: 1px solid rgba(239, 68, 68, 0.2);
    margin-bottom: 20px;
}}

.threat-sprite {{
    width: 96px;
    height: 96px;
    image-rendering: pixelated;
    filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
}}

.threat-info {{
    flex: 1;
}}

.threat-name {{
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 4px;
}}

.threat-stats {{
    display: flex;
    gap: 16px;
    margin-top: 8px;
}}

.stat-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    font-size: 13px;
    color: #a1a1aa;
}}

.stat-item .label {{
    text-transform: uppercase;
    font-size: 10px;
    font-weight: 600;
    color: #71717a;
}}

.stat-item .value {{
    font-weight: 700;
    color: #e4e4e7;
}}

.threat-level {{
    padding: 6px 16px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    background: {threat_color};
    color: #fff;
}}

.category {{
    background: linear-gradient(180deg, #1a1a2e 0%, #151521 100%);
    border-radius: 12px;
    border: 1px solid #2a2a3e;
    margin-bottom: 12px;
    overflow: hidden;
}}

.category-header {{
    padding: 12px 16px;
    background: rgba(255, 255, 255, 0.02);
    border-bottom: 1px solid #2a2a3e;
    display: flex;
    align-items: center;
    justify-content: space-between;
}}

.category-title {{
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.category-title.good {{ color: #4ade80; }}
.category-title.warning {{ color: #fbbf24; }}
.category-title.danger {{ color: #f87171; }}
.category-title.info {{ color: #60a5fa; }}

.category-count {{
    font-size: 12px;
    font-weight: 600;
    color: #71717a;
}}

.category-body {{
    padding: 12px 16px;
}}

.pokemon-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

.pokemon-chip {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 6px 12px 6px 6px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 20px;
    font-size: 13px;
    font-weight: 500;
}}

.chip-sprite {{
    width: 28px;
    height: 28px;
    image-rendering: pixelated;
}}

.empty-list {{
    font-size: 13px;
    color: #52525b;
    font-style: italic;
}}

.notes-list {{
    margin-top: 12px;
    padding: 12px 16px;
    background: rgba(99, 102, 241, 0.05);
    border-radius: 8px;
    border: 1px solid rgba(99, 102, 241, 0.1);
    list-style: none;
}}

.notes-list li {{
    font-size: 12px;
    color: #a1a1aa;
    padding: 4px 0;
    padding-left: 16px;
    position: relative;
}}

.notes-list li::before {{
    content: "";
    position: absolute;
    left: 0;
    top: 50%;
    transform: translateY(-50%);
    width: 6px;
    height: 6px;
    background: #6366f1;
    border-radius: 50%;
}}
    </style>
</head>
<body>
    <div class="threat-container">
        <div class="threat-header">
            {get_sprite_html(threat_name, size=64, css_class="threat-sprite")}
            <div class="threat-info">
                <div class="threat-name">{threat_name.replace('-', ' ').title()}</div>
                <div class="threat-stats">
                    <div class="stat-item">
                        <span class="label">Speed</span>
                        <span class="value">{threat_speed}</span>
                    </div>
                </div>
            </div>
            <span class="threat-level">{threat_level} Threat</span>
        </div>

        <div class="category">
            <div class="category-header">
                <span class="category-title good">Can OHKO</span>
                <span class="category-count">{len(ohko_by)}</span>
            </div>
            <div class="category-body">{ohko_html}</div>
        </div>

        <div class="category">
            <div class="category-header">
                <span class="category-title good">Can 2HKO</span>
                <span class="category-count">{len(twohko_by)}</span>
            </div>
            <div class="category-body">{twohko_html}</div>
        </div>

        <div class="category">
            <div class="category-header">
                <span class="category-title info">Checks</span>
                <span class="category-count">{len(checks)}</span>
            </div>
            <div class="category-body">{checks_html}</div>
        </div>

        <div class="category">
            <div class="category-header">
                <span class="category-title info">Counters</span>
                <span class="category-count">{len(counters)}</span>
            </div>
            <div class="category-body">{counters_html}</div>
        </div>

        <div class="category">
            <div class="category-header">
                <span class="category-title danger">Threatened By</span>
                <span class="category-count">{len(threatened)}</span>
            </div>
            <div class="category-body">{threatened_html}</div>
        </div>

        <div class="category">
            <div class="category-header">
                <span class="category-title warning">Survives Attack</span>
                <span class="category-count">{len(survives)}</span>
            </div>
            <div class="category-body">{survives_html}</div>
        </div>

        {notes_html}
    </div>
</body>
</html>"""


def create_usage_stats_ui(
    pokemon_name: str,
    usage_percent: float,
    items: list[dict[str, Any]],
    abilities: list[dict[str, Any]],
    moves: list[dict[str, Any]],
    spreads: list[dict[str, Any]],
    tera_types: list[dict[str, Any]] | None = None,
    teammates: list[dict[str, Any]] | None = None,
) -> str:
    """Create an interactive usage statistics UI component.

    Shows competitive usage data with visual bars and organized sections.
    """
    # Format items
    items_html = ""
    for item in items[:8]:
        name = item.get("name", "Unknown")
        pct = item.get("percent", 0)
        items_html += f'''
        <div class="stat-row">
            <span class="stat-name">{name}</span>
            <div class="stat-bar-container">
                <div class="stat-bar" style="width: {min(pct, 100)}%"></div>
            </div>
            <span class="stat-percent">{pct:.1f}%</span>
        </div>'''

    # Format abilities
    abilities_html = ""
    for ability in abilities[:4]:
        name = ability.get("name", "Unknown")
        pct = ability.get("percent", 0)
        abilities_html += f'''
        <div class="stat-row">
            <span class="stat-name">{name}</span>
            <div class="stat-bar-container">
                <div class="stat-bar ability" style="width: {min(pct, 100)}%"></div>
            </div>
            <span class="stat-percent">{pct:.1f}%</span>
        </div>'''

    # Format moves
    moves_html = ""
    for move in moves[:10]:
        name = move.get("name", "Unknown")
        pct = move.get("percent", 0)
        moves_html += f'''
        <div class="stat-row">
            <span class="stat-name">{name}</span>
            <div class="stat-bar-container">
                <div class="stat-bar move" style="width: {min(pct, 100)}%"></div>
            </div>
            <span class="stat-percent">{pct:.1f}%</span>
        </div>'''

    # Format spreads
    spreads_html = ""
    for spread in spreads[:5]:
        nature = spread.get("nature", "Serious")
        evs = spread.get("evs", {})
        pct = spread.get("percent", 0)
        ev_str = "/".join(f"{v}" for v in [
            evs.get("hp", 0), evs.get("atk", 0), evs.get("def", 0),
            evs.get("spa", 0), evs.get("spd", 0), evs.get("spe", 0)
        ])
        spreads_html += f'''
        <div class="spread-row">
            <span class="spread-nature">{nature}</span>
            <span class="spread-evs">{ev_str}</span>
            <span class="spread-percent">{pct:.1f}%</span>
        </div>'''

    # Format tera types if available
    tera_html = ""
    if tera_types:
        tera_items = ""
        for tera in tera_types[:6]:
            t_type = tera.get("type", "Normal")
            pct = tera.get("percent", 0)
            tera_items += f'''
            <div class="tera-item {t_type.lower()}">
                <span class="tera-type">{t_type}</span>
                <span class="tera-percent">{pct:.1f}%</span>
            </div>'''
        tera_html = f'''
        <div class="section">
            <div class="section-header">Tera Types</div>
            <div class="tera-grid">{tera_items}</div>
        </div>'''

    # Format teammates if available
    teammates_html = ""
    if teammates:
        teammate_items = ""
        for mate in teammates[:6]:
            name = mate.get("name", "Unknown")
            pct = mate.get("percent", 0)
            teammate_items += f'''
            <div class="teammate-item">
                <span class="teammate-name">{name}</span>
                <span class="teammate-percent">{pct:.1f}%</span>
            </div>'''
        teammates_html = f'''
        <div class="section">
            <div class="section-header">Common Teammates</div>
            <div class="teammates-grid">{teammate_items}</div>
        </div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            color: #e8e8e8;
            padding: 20px;
            min-height: 100vh;
        }}

        .container {{
            max-width: 900px;
            margin: 0 auto;
        }}

        .header {{
            text-align: center;
            margin-bottom: 24px;
            padding-bottom: 16px;
            border-bottom: 2px solid #3d5a80;
        }}

        .pokemon-name {{
            font-size: 28px;
            font-weight: 700;
            text-transform: capitalize;
            color: #ffffff;
            margin-bottom: 8px;
        }}

        .usage-badge {{
            display: inline-block;
            background: linear-gradient(135deg, #4a90d9 0%, #357abd 100%);
            padding: 8px 20px;
            border-radius: 20px;
            font-size: 18px;
            font-weight: 600;
        }}

        .grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}

        @media (max-width: 700px) {{
            .grid {{
                grid-template-columns: 1fr;
            }}
        }}

        .section {{
            background: rgba(255, 255, 255, 0.05);
            border-radius: 12px;
            padding: 16px;
            border: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .section-header {{
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: #8ab4f8;
            margin-bottom: 12px;
            padding-bottom: 8px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}

        .stat-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 6px 0;
        }}

        .stat-name {{
            flex: 0 0 120px;
            font-size: 13px;
            color: #d0d0d0;
            text-transform: capitalize;
        }}

        .stat-bar-container {{
            flex: 1;
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: 4px;
            overflow: hidden;
        }}

        .stat-bar {{
            height: 100%;
            background: linear-gradient(90deg, #4a90d9 0%, #64b5f6 100%);
            border-radius: 4px;
            transition: width 0.3s ease;
        }}

        .stat-bar.ability {{
            background: linear-gradient(90deg, #7c4dff 0%, #b388ff 100%);
        }}

        .stat-bar.move {{
            background: linear-gradient(90deg, #00bfa5 0%, #64ffda 100%);
        }}

        .stat-percent {{
            flex: 0 0 50px;
            text-align: right;
            font-size: 12px;
            color: #a0a0a0;
            font-weight: 500;
        }}

        .spread-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: 6px;
            margin-bottom: 6px;
        }}

        .spread-nature {{
            flex: 0 0 70px;
            font-size: 12px;
            font-weight: 600;
            color: #ffd54f;
        }}

        .spread-evs {{
            flex: 1;
            font-size: 11px;
            font-family: 'Consolas', monospace;
            color: #b0b0b0;
        }}

        .spread-percent {{
            font-size: 12px;
            color: #a0a0a0;
            font-weight: 500;
        }}

        .tera-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
        }}

        .tera-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.08);
            border-radius: 8px;
            min-width: 70px;
        }}

        .tera-type {{
            font-size: 12px;
            font-weight: 600;
            text-transform: capitalize;
        }}

        .tera-percent {{
            font-size: 10px;
            color: #a0a0a0;
        }}

        /* Tera type colors */
        .tera-item.normal {{ background: linear-gradient(135deg, #a8a878 0%, #8a8a5c 100%); }}
        .tera-item.fire {{ background: linear-gradient(135deg, #f08030 0%, #c65d1a 100%); }}
        .tera-item.water {{ background: linear-gradient(135deg, #6890f0 0%, #4a6fc4 100%); }}
        .tera-item.electric {{ background: linear-gradient(135deg, #f8d030 0%, #c9a820 100%); }}
        .tera-item.grass {{ background: linear-gradient(135deg, #78c850 0%, #5ca935 100%); }}
        .tera-item.ice {{ background: linear-gradient(135deg, #98d8d8 0%, #7ab8b8 100%); }}
        .tera-item.fighting {{ background: linear-gradient(135deg, #c03028 0%, #9d2721 100%); }}
        .tera-item.poison {{ background: linear-gradient(135deg, #a040a0 0%, #803380 100%); }}
        .tera-item.ground {{ background: linear-gradient(135deg, #e0c068 0%, #b8994d 100%); }}
        .tera-item.flying {{ background: linear-gradient(135deg, #a890f0 0%, #8a70c8 100%); }}
        .tera-item.psychic {{ background: linear-gradient(135deg, #f85888 0%, #d04070 100%); }}
        .tera-item.bug {{ background: linear-gradient(135deg, #a8b820 0%, #8a9a18 100%); }}
        .tera-item.rock {{ background: linear-gradient(135deg, #b8a038 0%, #93802c 100%); }}
        .tera-item.ghost {{ background: linear-gradient(135deg, #705898 0%, #554374 100%); }}
        .tera-item.dragon {{ background: linear-gradient(135deg, #7038f8 0%, #5828c8 100%); }}
        .tera-item.dark {{ background: linear-gradient(135deg, #705848 0%, #564436 100%); }}
        .tera-item.steel {{ background: linear-gradient(135deg, #b8b8d0 0%, #9898b0 100%); }}
        .tera-item.fairy {{ background: linear-gradient(135deg, #ee99ac 0%, #d07088 100%); }}

        .teammates-grid {{
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
        }}

        .teammate-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: 6px;
        }}

        .teammate-name {{
            font-size: 13px;
            color: #d0d0d0;
            text-transform: capitalize;
        }}

        .teammate-percent {{
            font-size: 11px;
            color: #a0a0a0;
        }}

        .full-width {{
            grid-column: 1 / -1;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <div class="pokemon-name">{pokemon_name}</div>
            <div class="usage-badge">{usage_percent:.2f}% Usage</div>
        </div>

        <div class="grid">
            <div class="section">
                <div class="section-header">Items</div>
                {items_html}
            </div>

            <div class="section">
                <div class="section-header">Abilities</div>
                {abilities_html}
            </div>

            <div class="section full-width">
                <div class="section-header">Moves</div>
                {moves_html}
            </div>

            <div class="section full-width">
                <div class="section-header">EV Spreads</div>
                {spreads_html}
            </div>

            {tera_html}
            {teammates_html}
        </div>
    </div>
</body>
</html>'''


def create_speed_outspeed_ui(
    pokemon_name: str,
    base_speed: int,
    current_speed: int,
    nature: str,
    speed_evs: int,
    speed_distribution: list[dict],
    outspeed_percentage: float,
    mode: str = "meta",
    target_pokemon: Optional[str] = None,
    format_info: Optional[dict] = None,
    pokemon_base_speeds: Optional[dict[str, int]] = None,
) -> str:
    """Create an interactive speed outspeed percentage UI.

    Shows what percentage of the meta (or a specific target) your Pokemon
    outspeeds, with an interactive slider to adjust Speed EVs in real-time.

    Args:
        pokemon_name: Your Pokemon's name
        base_speed: Base speed stat
        current_speed: Current calculated speed stat
        nature: Current nature
        speed_evs: Current Speed EVs
        speed_distribution: Pre-computed distribution from build_speed_distribution_data()
        outspeed_percentage: Initial outspeed percentage
        mode: "meta" for meta-wide, "single" for single target
        target_pokemon: Target Pokemon name (for single mode)
        format_info: Format metadata (name, month)
        pokemon_base_speeds: Dict mapping Pokemon names to their base speed stats

    Returns:
        HTML string for the interactive speed outspeed UI
    """
    import json

    sprite_html = get_sprite_html(pokemon_name, size=72, css_class="sprite")
    format_name = format_info.get("format", "VGC") if format_info else "VGC"
    format_month = format_info.get("month", "") if format_info else ""

    # Default to empty dict if not provided
    if pokemon_base_speeds is None:
        pokemon_base_speeds = {}

    # Nature options
    natures = [
        "Adamant", "Bold", "Brave", "Calm", "Careful", "Gentle", "Hasty",
        "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive",
        "Naughty", "Quiet", "Rash", "Relaxed", "Sassy", "Serious", "Timid"
    ]
    nature_options = "".join(
        f'<option value="{n}" {"selected" if n == nature else ""}>{n}</option>'
        for n in natures
    )

    # Build speed tier data for JS
    # In single mode: show speed spreads for target Pokemon only
    # In meta mode: aggregate by Pokemon name
    if mode == "single" and target_pokemon:
        # For single target, build list of speed tiers/spreads for that Pokemon
        speed_tiers = []
        for entry in speed_distribution:
            speed = entry.get("speed", 0)
            pokemon_at_speed = entry.get("pokemon_at_speed", [])
            # Get the total usage for this speed tier
            total_usage = sum(p.get("usage_pct", 0) for p in pokemon_at_speed)
            if total_usage > 0:
                # Get representative spread info
                rep = pokemon_at_speed[0] if pokemon_at_speed else {}
                speed_tiers.append({
                    "speed": speed,
                    "usage_pct": round(total_usage, 1),
                    "nature": rep.get("nature", "Serious"),
                    "evs": rep.get("evs", 0),
                })
        # Sort by speed descending
        sorted_pokemon = sorted(speed_tiers, key=lambda x: x["speed"], reverse=True)
        mode_display = f"vs {target_pokemon} Speed Spreads"
    else:
        # Meta mode: aggregate by Pokemon name
        pokemon_speed_data: dict[str, dict] = {}
        for entry in speed_distribution:
            for poke in entry.get("pokemon_at_speed", []):
                name = poke.get("name", "Unknown")
                common_speed = entry.get("speed", 0)
                usage = poke.get("usage_pct", 0)
                if name not in pokemon_speed_data:
                    # Get base speed from lookup, fallback to estimating from common speed
                    poke_base = pokemon_base_speeds.get(name, 0)
                    # Calculate theoretical max: Jolly/Timid (1.1x) + 252 EVs at level 50
                    # Formula: floor((floor((2*base + 31 + 63) * 50/100) + 5) * 1.1)
                    if poke_base > 0:
                        inner = (2 * poke_base + 31 + 63) * 50 // 100
                        theoretical_max = int((inner + 5) * 1.1)
                    else:
                        theoretical_max = common_speed  # Fallback
                    pokemon_speed_data[name] = {
                        "name": name,
                        "base_speed": poke_base,
                        "max_speed": theoretical_max,
                        "common_max": common_speed,
                        "total_usage": 0
                    }
                # Track highest commonly used speed
                pokemon_speed_data[name]["common_max"] = max(
                    pokemon_speed_data[name]["common_max"], common_speed
                )
                pokemon_speed_data[name]["total_usage"] += usage

        # Sort by theoretical max speed descending
        sorted_pokemon = sorted(pokemon_speed_data.values(), key=lambda x: x["max_speed"], reverse=True)
        mode_display = "vs Top Meta Pokemon"

    # Serialize distribution for JavaScript
    distribution_json = json.dumps(speed_distribution)
    pokemon_list_json = json.dumps(sorted_pokemon[:20])

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: #0f0f1a;
    color: #e4e4e7;
    line-height: 1.4;
}}
.container {{ max-width: 600px; margin: 0 auto; padding: 16px; }}

/* Header */
.header {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px;
    background: linear-gradient(135deg, rgba(59,130,246,0.15) 0%, rgba(37,99,235,0.05) 100%);
    border-radius: 16px;
    border: 1px solid rgba(59,130,246,0.3);
    margin-bottom: 16px;
}}
.sprite {{ width: 80px; height: 80px; image-rendering: pixelated; }}
.info {{ flex: 1; }}
.name {{ font-size: 1.4rem; font-weight: 700; text-transform: capitalize; }}
.speed-display {{ color: #94a3b8; margin-top: 4px; }}
.speed-display .val {{ color: #60a5fa; font-weight: 600; font-size: 1.2rem; }}
.base {{ color: #64748b; font-size: 0.85rem; }}
.result {{
    text-align: center;
    background: rgba(0,0,0,0.4);
    padding: 12px 16px;
    border-radius: 12px;
}}
.pct {{ font-size: 2.2rem; font-weight: 700; color: #4ade80; line-height: 1; }}
.pct.low {{ color: #f87171; }}
.pct.med {{ color: #fbbf24; }}
.label {{ font-size: 0.75rem; color: #64748b; margin-top: 4px; }}

/* Controls */
.controls {{
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 16px;
}}
.row {{ margin-bottom: 12px; }}
.row:last-child {{ margin-bottom: 0; }}
.row label {{ display: block; font-size: 0.8rem; color: #64748b; margin-bottom: 6px; }}
.row select {{
    width: 100%;
    padding: 8px 12px;
    background: rgba(0,0,0,0.4);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 8px;
    color: #e4e4e7;
    font-size: 0.9rem;
}}
.ev-row {{ display: flex; justify-content: space-between; align-items: center; }}
.ev-val {{ font-weight: 600; color: #60a5fa; }}
input[type="range"] {{
    width: 100%;
    height: 6px;
    border-radius: 3px;
    background: linear-gradient(90deg, #1e3a5f, #3b82f6);
    -webkit-appearance: none;
    cursor: pointer;
}}
input[type="range"]::-webkit-slider-thumb {{
    -webkit-appearance: none;
    width: 18px; height: 18px;
    border-radius: 50%;
    background: #60a5fa;
    cursor: pointer;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
}}

/* Pokemon Lists */
.lists {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
    margin-bottom: 16px;
}}
.list-section {{
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 12px;
}}
.list-section.slower {{ border: 1px solid rgba(74,222,128,0.3); }}
.list-section.faster {{ border: 1px solid rgba(248,113,113,0.3); }}
.list-header {{
    font-size: 0.85rem;
    font-weight: 600;
    margin-bottom: 8px;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.list-header.slower {{ color: #4ade80; }}
.list-header.faster {{ color: #f87171; }}
.count-badge {{
    background: rgba(255,255,255,0.1);
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.75rem;
}}
.pokemon-list {{
    max-height: 200px;
    overflow-y: auto;
}}
.pokemon-row {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 4px 0;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.pokemon-row:last-child {{ border-bottom: none; }}
.pokemon-row img {{
    width: 32px;
    height: 32px;
    image-rendering: pixelated;
}}
.pokemon-row .pokemon-info {{
    flex: 1;
    min-width: 0;
}}
.pokemon-row .pokemon-name {{
    font-size: 0.85rem;
    font-weight: 500;
    text-transform: capitalize;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}}
.pokemon-row .pokemon-speed {{
    font-size: 0.75rem;
    color: #64748b;
}}

/* Bar Chart */
.bar-section {{
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    padding: 16px;
    margin-bottom: 12px;
}}
.bar-title {{ font-size: 0.85rem; color: #94a3b8; margin-bottom: 10px; }}
.bar-container {{
    position: relative;
    height: 32px;
    background: rgba(0,0,0,0.4);
    border-radius: 6px;
    overflow: hidden;
}}
.bar-fill {{
    height: 100%;
    border-radius: 6px;
    transition: width 0.2s, background 0.2s;
}}
.bar-fill.high {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
.bar-fill.med {{ background: linear-gradient(90deg, #eab308, #fbbf24); }}
.bar-fill.low {{ background: linear-gradient(90deg, #dc2626, #f87171); }}
.bar-labels {{
    display: flex;
    justify-content: space-between;
    font-size: 0.7rem;
    color: #475569;
    margin-top: 4px;
}}

.footer {{ text-align: center; font-size: 0.75rem; color: #475569; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        {sprite_html}
        <div class="info">
            <div class="name">{pokemon_name}</div>
            <div class="speed-display">Speed: <span class="val" id="speed-val">{current_speed}</span></div>
            <div class="base">Base {base_speed}</div>
        </div>
        <div class="result">
            <div class="pct" id="pct-display">{outspeed_percentage:.1f}%</div>
            <div class="label">{"of " + target_pokemon + " outsped" if mode == "single" and target_pokemon else "of meta outsped"}</div>
        </div>
    </div>

    <div class="controls">
        <div class="row">
            <label>Nature</label>
            <select id="nature-sel" onchange="update()">{nature_options}</select>
        </div>
        <div class="row">
            <label class="ev-row"><span>Speed EVs</span><span class="ev-val" id="ev-val">{speed_evs}</span></label>
            <input type="range" id="ev-slider" min="0" max="252" step="4" value="{speed_evs}" oninput="update()">
        </div>
    </div>

    <div class="bar-section">
        <div class="bar-title">{mode_display}</div>
        <div class="bar-container">
            <div class="bar-fill high" id="bar-fill" style="width:{outspeed_percentage}%"></div>
        </div>
        <div class="bar-labels"><span>0%</span><span>50%</span><span>100%</span></div>
    </div>

    <div class="lists">
        <div class="list-section slower">
            <div class="list-header slower">
                {"Slower Spreads" if mode == "single" else "You Outspeed"} <span class="count-badge" id="slower-count">0</span>
            </div>
            <div class="pokemon-list" id="slower-list"></div>
        </div>
        <div class="list-section faster">
            <div class="list-header faster">
                {"Faster Spreads" if mode == "single" else "Outspeed You"} <span class="count-badge" id="faster-count">0</span>
            </div>
            <div class="pokemon-list" id="faster-list"></div>
        </div>
    </div>

    <div class="footer">{format_name} {format_month}</div>
</div>

<script>
const BASE = {base_speed};
const DIST = {distribution_json};
const DATA = {pokemon_list_json};
const MODE = "{mode}";
const TARGET = "{target_pokemon or ''}";
const NATURE_MODS = {{
    "Jolly":1.1,"Timid":1.1,"Hasty":1.1,"Naive":1.1,
    "Brave":0.9,"Quiet":0.9,"Relaxed":0.9,"Sassy":0.9,
    "Adamant":1,"Bold":1,"Calm":1,"Careful":1,"Gentle":1,
    "Impish":1,"Lax":1,"Lonely":1,"Mild":1,"Modest":1,
    "Naughty":1,"Rash":1,"Serious":1
}};

function calcSpeed(base, evs, nature) {{
    const mod = NATURE_MODS[nature] || 1;
    const inner = Math.floor((2*base + 31 + Math.floor(evs/4)) * 50/100);
    return Math.floor((inner + 5) * mod);
}}

function getPct(speed) {{
    let pct = 0;
    for (const e of DIST) {{
        if (e.speed < speed) pct = e.cumulative_outspeed_pct;
        else break;
    }}
    return pct;
}}

function getSpriteUrl(name) {{
    const n = name.toLowerCase().replace(/ /g, '-').replace(/\\./g, '');
    return 'https://play.pokemonshowdown.com/sprites/ani/' + n + '.gif';
}}

function update() {{
    const evs = parseInt(document.getElementById('ev-slider').value);
    const nature = document.getElementById('nature-sel').value;
    const speed = calcSpeed(BASE, evs, nature);
    const pct = getPct(speed);

    document.getElementById('ev-val').textContent = evs;
    document.getElementById('speed-val').textContent = speed;
    document.getElementById('pct-display').textContent = pct.toFixed(1) + '%';

    const pctEl = document.getElementById('pct-display');
    pctEl.className = 'pct ' + (pct >= 60 ? '' : pct >= 35 ? 'med' : 'low');

    const bar = document.getElementById('bar-fill');
    bar.style.width = pct + '%';
    bar.className = 'bar-fill ' + (pct >= 60 ? 'high' : pct >= 35 ? 'med' : 'low');

    // Different rendering for single vs meta mode
    if (MODE === 'single') {{
        // Single target mode: DATA contains speed tiers for target Pokemon
        const slower = [], faster = [];
        for (const tier of DATA) {{
            if (tier.speed < speed) slower.push(tier);
            else faster.push(tier);
        }}

        document.getElementById('slower-count').textContent = slower.length;
        document.getElementById('faster-count').textContent = faster.length;

        // Render speed tier lists for single Pokemon
        const renderTierList = (list, containerId, sortAsc) => {{
            const el = document.getElementById(containerId);
            if (list.length === 0) {{
                el.innerHTML = '<div style="color:#64748b;font-size:0.8rem;padding:8px;">None</div>';
                return;
            }}
            const sorted = sortAsc
                ? list.sort((a,b) => a.speed - b.speed)
                : list.sort((a,b) => b.speed - a.speed);
            el.innerHTML = sorted.map(t => `
                <div class="pokemon-row">
                    <img src="${{getSpriteUrl(TARGET)}}" onerror="this.style.display='none'">
                    <div class="pokemon-info">
                        <div class="pokemon-name">${{t.speed}} Spe</div>
                        <div class="pokemon-speed">${{t.nature}} ${{t.evs}} EVs (${{t.usage_pct}}%)</div>
                    </div>
                </div>
            `).join('');
        }};

        renderTierList(slower, 'slower-list', false);
        renderTierList(faster, 'faster-list', true);
    }} else {{
        // Meta mode: DATA contains Pokemon with max speeds
        const slower = [], faster = [];
        for (const p of DATA) {{
            const compSpeed = p.common_max || p.max_speed;
            if (compSpeed < speed) slower.push(p);
            else faster.push(p);
        }}

        document.getElementById('slower-count').textContent = slower.length;
        document.getElementById('faster-count').textContent = faster.length;

        // Render Pokemon lists for meta mode
        const renderList = (list, containerId) => {{
            const el = document.getElementById(containerId);
            if (list.length === 0) {{
                el.innerHTML = '<div style="color:#64748b;font-size:0.8rem;padding:8px;">None</div>';
                return;
            }}
            el.innerHTML = list.map(p => `
                <div class="pokemon-row">
                    <img src="${{getSpriteUrl(p.name)}}" onerror="this.style.display='none'">
                    <div class="pokemon-info">
                        <div class="pokemon-name">${{p.name}}</div>
                        <div class="pokemon-speed">Max ${{p.max_speed}} Spe</div>
                    </div>
                </div>
            `).join('');
        }};

        renderList(slower.sort((a,b) => b.max_speed - a.max_speed), 'slower-list');
        renderList(faster.sort((a,b) => a.max_speed - b.max_speed), 'faster-list');
    }}
}}

update();
</script>
</body>
</html>'''


def create_stats_card_ui(
    pokemon_name: str,
    base_stats: dict[str, int],
    evs: dict[str, int],
    ivs: dict[str, int],
    nature: str,
    level: int = 50,
    ability: Optional[str] = None,
    item: Optional[str] = None,
    types: Optional[list[str]] = None,
    tera_type: Optional[str] = None,
) -> str:
    """Create a stats card UI with radar chart visualization.

    Args:
        pokemon_name: Pokemon name
        base_stats: Base stats dict (hp, attack, defense, special_attack, special_defense, speed)
        evs: EV spread dict
        ivs: IV spread dict
        nature: Nature name
        level: Pokemon level (default 50)
        ability: Pokemon ability
        item: Held item
        types: Pokemon types list
        tera_type: Tera type if any

    Returns:
        HTML string for the stats card UI
    """
    import json
    import math

    sprite_html = get_sprite_html(pokemon_name, size=96, css_class="sprite")

    # Nature modifiers
    nature_mods = {
        "adamant": {"attack": 1.1, "special_attack": 0.9},
        "bold": {"defense": 1.1, "attack": 0.9},
        "brave": {"attack": 1.1, "speed": 0.9},
        "calm": {"special_defense": 1.1, "attack": 0.9},
        "careful": {"special_defense": 1.1, "special_attack": 0.9},
        "gentle": {"special_defense": 1.1, "defense": 0.9},
        "hasty": {"speed": 1.1, "defense": 0.9},
        "impish": {"defense": 1.1, "special_attack": 0.9},
        "jolly": {"speed": 1.1, "special_attack": 0.9},
        "lax": {"defense": 1.1, "special_defense": 0.9},
        "lonely": {"attack": 1.1, "defense": 0.9},
        "mild": {"special_attack": 1.1, "defense": 0.9},
        "modest": {"special_attack": 1.1, "attack": 0.9},
        "naive": {"speed": 1.1, "special_defense": 0.9},
        "naughty": {"attack": 1.1, "special_defense": 0.9},
        "quiet": {"special_attack": 1.1, "speed": 0.9},
        "rash": {"special_attack": 1.1, "special_defense": 0.9},
        "relaxed": {"defense": 1.1, "speed": 0.9},
        "sassy": {"special_defense": 1.1, "speed": 0.9},
        "serious": {},
        "timid": {"speed": 1.1, "attack": 0.9},
    }

    def calc_stat(stat_name: str, base: int, ev: int, iv: int) -> int:
        nature_mod = nature_mods.get(nature.lower(), {}).get(stat_name, 1.0)
        if stat_name == "hp":
            if base == 1:  # Shedinja
                return 1
            return math.floor((2 * base + iv + ev // 4) * level / 100) + level + 10
        else:
            return math.floor((math.floor((2 * base + iv + ev // 4) * level / 100) + 5) * nature_mod)

    # Calculate final stats
    stat_keys = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
    stat_labels = ["HP", "Atk", "Def", "SpA", "SpD", "Spe"]
    final_stats = {}
    for key in stat_keys:
        base = base_stats.get(key, 100)
        ev = evs.get(key, 0)
        iv = ivs.get(key, 31)
        final_stats[key] = calc_stat(key, base, ev, iv)

    # Determine nature effects for display
    nature_info = nature_mods.get(nature.lower(), {})
    boosted_stat = None
    lowered_stat = None
    for stat, mod in nature_info.items():
        if mod > 1:
            boosted_stat = stat
        elif mod < 1:
            lowered_stat = stat

    # Type badges
    types = types or []
    type_badges = "".join(
        f'<span class="type-badge" style="background:{get_type_color(t)}">{t.upper()}</span>'
        for t in types
    )

    # Build stats data for JS
    stats_data = json.dumps({
        "base": base_stats,
        "evs": evs,
        "ivs": ivs,
        "final": final_stats
    })

    # Pre-build stat rows to avoid nested f-string issues
    stat_rows_html = ""
    for i in range(6):
        stat_class = 'boosted' if stat_keys[i] == boosted_stat else ('lowered' if stat_keys[i] == lowered_stat else '')
        bar_width = min(100, base_stats.get(stat_keys[i], 100) / 2)
        stat_rows_html += f'''
        <div class="stat-row">
            <div class="stat-label {stat_class}">{stat_labels[i]}</div>
            <div class="stat-bar-container">
                <div class="stat-bar {stat_keys[i]}" style="width:{bar_width}%"></div>
                <div class="stat-values">
                    <span class="stat-base">{base_stats.get(stat_keys[i], 100)}</span>
                    <span class="stat-final">{final_stats[stat_keys[i]]}</span>
                </div>
            </div>
        </div>
        '''

    # Pre-build EV items to avoid nested f-string issues
    ev_items_html = ""
    for i in range(6):
        ev_val = evs.get(stat_keys[i], 0)
        zero_class = 'zero' if ev_val == 0 else ''
        ev_items_html += f'''
            <div class="ev-item">
                <div class="ev-label">{stat_labels[i]}</div>
                <div class="ev-value {zero_class}">{ev_val}</div>
            </div>
            '''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    color: #e4e4e7;
    min-height: 100vh;
    padding: 16px;
}}
.card {{
    max-width: 420px;
    margin: 0 auto;
    background: rgba(255,255,255,0.03);
    border-radius: 20px;
    border: 1px solid rgba(255,255,255,0.1);
    overflow: hidden;
}}
.header {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.1) 100%);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.sprite {{
    width: 96px;
    height: 96px;
    image-rendering: pixelated;
    filter: drop-shadow(0 4px 12px rgba(0,0,0,0.3));
}}
.info {{ flex: 1; }}
.name {{
    font-size: 1.5rem;
    font-weight: 700;
    text-transform: capitalize;
    margin-bottom: 6px;
}}
.types {{ display: flex; gap: 6px; margin-bottom: 8px; }}
.type-badge {{
    padding: 3px 10px;
    border-radius: 12px;
    font-size: 0.7rem;
    font-weight: 600;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}}
.meta {{
    font-size: 0.85rem;
    color: #94a3b8;
}}
.meta span {{ color: #a78bfa; font-weight: 500; }}

.stats-section {{
    padding: 20px;
}}
.section-title {{
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #64748b;
    margin-bottom: 16px;
}}
.stat-row {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 12px;
}}
.stat-label {{
    width: 36px;
    font-size: 0.8rem;
    font-weight: 600;
    color: #94a3b8;
}}
.stat-label.boosted {{ color: #4ade80; }}
.stat-label.lowered {{ color: #f87171; }}
.stat-bar-container {{
    flex: 1;
    height: 24px;
    background: rgba(0,0,0,0.3);
    border-radius: 6px;
    overflow: hidden;
    position: relative;
}}
.stat-bar {{
    height: 100%;
    border-radius: 6px;
    transition: width 0.3s ease;
}}
.stat-bar.hp {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
.stat-bar.attack {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
.stat-bar.defense {{ background: linear-gradient(90deg, #f59e0b, #fbbf24); }}
.stat-bar.special_attack {{ background: linear-gradient(90deg, #6366f1, #818cf8); }}
.stat-bar.special_defense {{ background: linear-gradient(90deg, #8b5cf6, #a78bfa); }}
.stat-bar.speed {{ background: linear-gradient(90deg, #ec4899, #f472b6); }}
.stat-values {{
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    display: flex;
    gap: 8px;
    font-size: 0.75rem;
}}
.stat-final {{
    font-weight: 700;
    color: #fff;
    text-shadow: 0 1px 3px rgba(0,0,0,0.5);
}}
.stat-base {{
    color: #94a3b8;
}}

.ev-section {{
    padding: 16px 20px;
    background: rgba(0,0,0,0.2);
    border-top: 1px solid rgba(255,255,255,0.05);
}}
.ev-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 8px;
}}
.ev-item {{
    text-align: center;
    padding: 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 8px;
}}
.ev-label {{
    font-size: 0.7rem;
    color: #64748b;
    margin-bottom: 4px;
}}
.ev-value {{
    font-size: 0.9rem;
    font-weight: 600;
    color: #a78bfa;
}}
.ev-value.zero {{ color: #475569; }}

.nature-bar {{
    padding: 12px 20px;
    background: rgba(139,92,246,0.1);
    border-top: 1px solid rgba(139,92,246,0.2);
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-size: 0.85rem;
}}
.nature-name {{ font-weight: 600; color: #a78bfa; }}
.nature-effect {{ color: #94a3b8; }}
.nature-boost {{ color: #4ade80; }}
.nature-lower {{ color: #f87171; }}
    </style>
</head>
<body>
<div class="card">
    <div class="header">
        {sprite_html}
        <div class="info">
            <div class="name">{pokemon_name}</div>
            <div class="types">{type_badges}</div>
            <div class="meta">
                {f'<span>{ability}</span> · ' if ability else ''}{f'{item}' if item else ''}
                {f' · Tera: {tera_type}' if tera_type else ''}
            </div>
        </div>
    </div>

    <div class="stats-section">
        <div class="section-title">Stats (Level {level})</div>
        {stat_rows_html}
    </div>

    <div class="ev-section">
        <div class="section-title">EV Spread</div>
        <div class="ev-grid">
            {ev_items_html}
        </div>
    </div>

    <div class="nature-bar">
        <span class="nature-name">{nature}</span>
        <span class="nature-effect">
            {f'<span class="nature-boost">+{boosted_stat.replace("_", " ").title()}</span>' if boosted_stat else ''}
            {f' / <span class="nature-lower">-{lowered_stat.replace("_", " ").title()}</span>' if lowered_stat else ''}
            {' Neutral' if not boosted_stat and not lowered_stat else ''}
        </span>
    </div>
</div>
</body>
</html>'''


def create_threat_matrix_ui(
    pokemon_name: str,
    pokemon_speed: int,
    threats: list[dict],
    pokemon_sprite: Optional[str] = None,
) -> str:
    """Create a threat matchup matrix UI.

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat
        threats: List of threat dicts with:
            - name: Threat Pokemon name
            - your_damage_min: Min damage you deal (%)
            - your_damage_max: Max damage you deal (%)
            - their_damage_min: Min damage they deal (%)
            - their_damage_max: Max damage they deal (%)
            - your_move: Move you use
            - their_move: Move they use
            - their_speed: Their speed stat
            - usage_percent: Usage % in meta
        pokemon_sprite: Optional sprite URL override

    Returns:
        HTML string for the threat matrix UI
    """
    import json

    sprite_html = get_sprite_html(pokemon_name, size=72, css_class="sprite") if not pokemon_sprite else f'<img src="{pokemon_sprite}" class="sprite" alt="{pokemon_name}" style="width:72px;height:72px;">'
    threats_json = json.dumps(threats[:10])  # Top 10 threats

    def calc_ko_probability(damage_min: float, damage_max: float, threshold: float) -> int:
        """Calculate probability of exceeding threshold (16 damage rolls)."""
        if damage_min >= threshold:
            return 100
        if damage_max < threshold:
            return 0
        dmg_range = damage_max - damage_min
        if dmg_range <= 0:
            return 100 if damage_min >= threshold else 0
        rolls_above = int(((damage_max - threshold) / dmg_range) * 16) + 1
        return round((rolls_above / 16) * 100)

    def get_ko_class(damage_min: float, damage_max: float) -> tuple[str, str]:
        """Return CSS class and label for damage range."""
        # OHKO check
        if damage_min >= 100:
            return "ohko", "OHKO"
        if damage_max >= 100:
            prob = calc_ko_probability(damage_min, damage_max, 100)
            return "ohko", f"{prob}% OHKO"
        # 2HKO check (need 50% per hit)
        if damage_min >= 50:
            return "twohko", "2HKO"
        if damage_max >= 50:
            prob = calc_ko_probability(damage_min, damage_max, 50)
            return "twohko", f"{prob}% 2HKO"
        # 3HKO check (need 33.4% per hit)
        if damage_min >= 33.4:
            return "threehko", "3HKO"
        if damage_max >= 33.4:
            prob = calc_ko_probability(damage_min, damage_max, 33.4)
            return "threehko", f"{prob}% 3HKO"
        # 4HKO check (need 25% per hit)
        if damage_min >= 25:
            return "chip", "4HKO"
        if damage_max >= 25:
            prob = calc_ko_probability(damage_min, damage_max, 25)
            return "chip", f"{prob}% 4HKO"
        return "chip", f"{int((damage_min + damage_max) / 2)}%"

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    color: #e4e4e7;
    min-height: 100vh;
    padding: 16px;
}}
.container {{ max-width: 700px; margin: 0 auto; }}
.header {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 20px;
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 16px;
}}
.sprite {{ width: 80px; height: 80px; image-rendering: pixelated; }}
.title {{ flex: 1; }}
.name {{ font-size: 1.4rem; font-weight: 700; text-transform: capitalize; }}
.subtitle {{ color: #94a3b8; font-size: 0.9rem; margin-top: 4px; }}
.speed-badge {{
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    padding: 8px 16px;
    border-radius: 12px;
    font-weight: 600;
}}

.matrix {{
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    overflow: hidden;
}}
.matrix-header {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 80px;
    padding: 12px 16px;
    background: rgba(0,0,0,0.3);
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #64748b;
}}
.threat-row {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr 80px;
    padding: 12px 16px;
    align-items: center;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    transition: background 0.2s;
}}
.threat-row:hover {{ background: rgba(255,255,255,0.03); }}
.threat-row:last-child {{ border-bottom: none; }}

.threat-info {{
    display: flex;
    align-items: center;
    gap: 10px;
}}
.threat-sprite {{
    width: 40px;
    height: 40px;
    image-rendering: pixelated;
}}
.threat-name {{
    font-weight: 500;
    text-transform: capitalize;
    font-size: 0.9rem;
}}
.threat-speed {{
    font-size: 0.75rem;
    color: #64748b;
}}

.damage-cell {{
    display: flex;
    flex-direction: column;
    gap: 4px;
}}
.damage-badge {{
    display: inline-flex;
    align-items: center;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 0.8rem;
    font-weight: 600;
    width: fit-content;
}}
.damage-badge.ohko {{ background: rgba(239,68,68,0.2); color: #f87171; }}
.damage-badge.ohko-chance {{ background: rgba(249,115,22,0.2); color: #fb923c; }}
.damage-badge.twohko {{ background: rgba(234,179,8,0.2); color: #fbbf24; }}
.damage-badge.threehko {{ background: rgba(34,197,94,0.2); color: #4ade80; }}
.damage-badge.chip {{ background: rgba(148,163,184,0.1); color: #94a3b8; }}
.damage-move {{
    font-size: 0.7rem;
    color: #64748b;
}}

.usage-bar {{
    height: 6px;
    background: rgba(255,255,255,0.1);
    border-radius: 3px;
    overflow: hidden;
}}
.usage-fill {{
    height: 100%;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    border-radius: 3px;
}}
.usage-text {{
    font-size: 0.7rem;
    color: #64748b;
    text-align: right;
    margin-top: 4px;
}}

.legend {{
    display: flex;
    gap: 16px;
    padding: 12px 16px;
    background: rgba(0,0,0,0.2);
    font-size: 0.75rem;
    justify-content: center;
}}
.legend-item {{
    display: flex;
    align-items: center;
    gap: 6px;
}}
.legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
}}
.legend-dot.ohko {{ background: #f87171; }}
.legend-dot.twohko {{ background: #fbbf24; }}
.legend-dot.threehko {{ background: #4ade80; }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        {sprite_html}
        <div class="title">
            <div class="name">{pokemon_name}</div>
            <div class="subtitle">vs Top Meta Threats</div>
        </div>
        <div class="speed-badge">{pokemon_speed} Spe</div>
    </div>

    <div class="matrix">
        <div class="matrix-header">
            <div>Threat</div>
            <div>You &rarr; Them</div>
            <div>They &rarr; You</div>
            <div>Usage</div>
        </div>
        {"".join(f'''
        <div class="threat-row">
            <div class="threat-info">
                {get_sprite_html(t.get('name', ''), size=40, css_class="threat-sprite")}
                <div>
                    <div class="threat-name">{t.get('name', 'Unknown')}</div>
                    <div class="threat-speed">{t.get('their_speed', '?')} Spe</div>
                </div>
            </div>
            <div class="damage-cell">
                <span class="damage-badge {get_ko_class(t.get('your_damage_min', 0), t.get('your_damage_max', 0))[0]}">{get_ko_class(t.get('your_damage_min', 0), t.get('your_damage_max', 0))[1]}</span>
                <span class="damage-move">{t.get('your_move', '')}</span>
            </div>
            <div class="damage-cell">
                <span class="damage-badge {get_ko_class(t.get('their_damage_min', 0), t.get('their_damage_max', 0))[0]}">{get_ko_class(t.get('their_damage_min', 0), t.get('their_damage_max', 0))[1]}</span>
                <span class="damage-move">{t.get('their_move', '')}</span>
            </div>
            <div>
                <div class="usage-bar"><div class="usage-fill" style="width:{min(100, t.get('usage_percent', 0) * 2)}%"></div></div>
                <div class="usage-text">{format(t.get('usage_percent', 0), '.1f')}%</div>
            </div>
        </div>
        ''' for t in threats[:10])}
        <div class="legend">
            <div class="legend-item"><div class="legend-dot ohko"></div>OHKO</div>
            <div class="legend-item"><div class="legend-dot twohko"></div>2HKO</div>
            <div class="legend-item"><div class="legend-dot threehko"></div>3HKO+</div>
        </div>
    </div>
</div>
</body>
</html>'''


def create_turn_order_ui(
    pokemon_list: list[dict],
    trick_room: bool = False,
    tailwind_pokemon: Optional[list[str]] = None,
    paralysis_pokemon: Optional[list[str]] = None,
) -> str:
    """Create a turn order timeline UI.

    Args:
        pokemon_list: List of Pokemon dicts with:
            - name: Pokemon name
            - speed: Current speed stat
            - move: Move being used
            - priority: Move priority (-7 to +5)
            - team: "yours" or "opponent"
        trick_room: Whether Trick Room is active
        tailwind_pokemon: List of Pokemon with Tailwind boost
        paralysis_pokemon: List of paralyzed Pokemon

    Returns:
        HTML string for the turn order UI
    """
    import json

    tailwind_pokemon = tailwind_pokemon or []
    paralysis_pokemon = paralysis_pokemon or []

    # Calculate effective speeds
    def get_effective_speed(p: dict) -> int:
        speed = p.get("speed", 100)
        name = p.get("name", "")
        if name in tailwind_pokemon:
            speed *= 2
        if name in paralysis_pokemon:
            speed //= 2
        return speed

    # Sort by priority first, then speed (reversed if Trick Room)
    sorted_pokemon = sorted(
        pokemon_list,
        key=lambda p: (-p.get("priority", 0), -get_effective_speed(p) if not trick_room else get_effective_speed(p))
    )

    pokemon_json = json.dumps(pokemon_list)

    def get_priority_badge(priority: int) -> str:
        if priority > 0:
            return f'<span class="priority-badge positive">+{priority}</span>'
        elif priority < 0:
            return f'<span class="priority-badge negative">{priority}</span>'
        return ""

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    color: #e4e4e7;
    min-height: 100vh;
    padding: 16px;
}}
.container {{ max-width: 500px; margin: 0 auto; }}
.header {{
    text-align: center;
    padding: 20px;
    margin-bottom: 16px;
}}
.title {{ font-size: 1.3rem; font-weight: 700; margin-bottom: 8px; }}
.toggles {{
    display: flex;
    gap: 12px;
    justify-content: center;
}}
.toggle {{
    display: flex;
    align-items: center;
    gap: 6px;
    padding: 8px 14px;
    background: rgba(255,255,255,0.05);
    border-radius: 20px;
    cursor: pointer;
    transition: all 0.2s;
    border: 1px solid transparent;
    font-size: 0.85rem;
}}
.toggle:hover {{ background: rgba(255,255,255,0.08); }}
.toggle.active {{
    background: rgba(236,72,153,0.2);
    border-color: rgba(236,72,153,0.4);
    color: #f472b6;
}}
.toggle.tailwind.active {{
    background: rgba(59,130,246,0.2);
    border-color: rgba(59,130,246,0.4);
    color: #60a5fa;
}}
.toggle-icon {{ font-size: 1rem; }}

.timeline {{
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    padding: 16px;
    position: relative;
}}
.timeline::before {{
    content: '';
    position: absolute;
    left: 40px;
    top: 60px;
    bottom: 60px;
    width: 2px;
    background: linear-gradient(180deg, rgba(99,102,241,0.5) 0%, rgba(236,72,153,0.5) 100%);
}}
.turn-item {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 12px 0;
    position: relative;
}}
.turn-number {{
    width: 50px;
    height: 50px;
    background: linear-gradient(135deg, #6366f1, #8b5cf6);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-weight: 700;
    font-size: 1.1rem;
    flex-shrink: 0;
    z-index: 1;
    box-shadow: 0 4px 12px rgba(99,102,241,0.3);
}}
.turn-number.opponent {{
    background: linear-gradient(135deg, #dc2626, #ef4444);
    box-shadow: 0 4px 12px rgba(220,38,38,0.3);
}}
.turn-content {{
    flex: 1;
    background: rgba(255,255,255,0.03);
    padding: 12px 16px;
    border-radius: 12px;
    border: 1px solid rgba(255,255,255,0.05);
}}
.turn-header {{
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 6px;
}}
.pokemon-sprite {{
    width: 36px;
    height: 36px;
    image-rendering: pixelated;
}}
.pokemon-name {{
    font-weight: 600;
    text-transform: capitalize;
    flex: 1;
}}
.speed-stat {{
    font-size: 0.85rem;
    color: #a78bfa;
    font-weight: 500;
}}
.priority-badge {{
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 0.75rem;
    font-weight: 600;
}}
.priority-badge.positive {{
    background: rgba(251,191,36,0.2);
    color: #fbbf24;
}}
.priority-badge.negative {{
    background: rgba(148,163,184,0.2);
    color: #94a3b8;
}}
.move-name {{
    font-size: 0.85rem;
    color: #94a3b8;
}}
.modifier-badges {{
    display: flex;
    gap: 6px;
    margin-top: 6px;
}}
.mod-badge {{
    padding: 2px 8px;
    border-radius: 8px;
    font-size: 0.7rem;
    font-weight: 500;
}}
.mod-badge.tailwind {{
    background: rgba(59,130,246,0.2);
    color: #60a5fa;
}}
.mod-badge.paralysis {{
    background: rgba(234,179,8,0.2);
    color: #fbbf24;
}}
.mod-badge.tr {{
    background: rgba(236,72,153,0.2);
    color: #f472b6;
}}

.legend {{
    display: flex;
    gap: 20px;
    justify-content: center;
    padding: 16px;
    font-size: 0.8rem;
    color: #64748b;
}}
.legend-item {{ display: flex; align-items: center; gap: 6px; }}
.legend-dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
}}
.legend-dot.yours {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); }}
.legend-dot.opponent {{ background: linear-gradient(135deg, #dc2626, #ef4444); }}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="title">Turn Order</div>
        <div class="toggles">
            <div class="toggle {'active' if trick_room else ''}" onclick="toggleTR(this)">
                <span class="toggle-icon">&#128260;</span> Trick Room
            </div>
            <div class="toggle tailwind" onclick="toggleTailwind(this)">
                <span class="toggle-icon">&#128168;</span> Tailwind
            </div>
        </div>
    </div>

    <div class="timeline" id="timeline">
        {"".join(f'''
        <div class="turn-item">
            <div class="turn-number {'opponent' if p.get('team') == 'opponent' else ''}">{i + 1}</div>
            <div class="turn-content">
                <div class="turn-header">
                    {get_sprite_html(p.get('name', ''), size=40, css_class="pokemon-sprite")}
                    <span class="pokemon-name">{p.get('name', 'Unknown')}</span>
                    <span class="speed-stat">{get_effective_speed(p)} Spe</span>
                    {get_priority_badge(p.get('priority', 0))}
                </div>
                <div class="move-name">{p.get('move', 'Attack')}</div>
                <div class="modifier-badges">
                    {f'<span class="mod-badge tailwind">Tailwind</span>' if p.get('name', '') in tailwind_pokemon else ''}
                    {f'<span class="mod-badge paralysis">Paralyzed</span>' if p.get('name', '') in paralysis_pokemon else ''}
                    {f'<span class="mod-badge tr">Trick Room</span>' if trick_room else ''}
                </div>
            </div>
        </div>
        ''' for i, p in enumerate(sorted_pokemon))}
    </div>

    <div class="legend">
        <div class="legend-item"><div class="legend-dot yours"></div>Your Team</div>
        <div class="legend-item"><div class="legend-dot opponent"></div>Opponent</div>
    </div>
</div>

<script>
const POKEMON = {pokemon_json};
let trickRoom = {'true' if trick_room else 'false'};
let tailwind = false;

function toggleTR(el) {{
    trickRoom = !trickRoom;
    el.classList.toggle('active');
    // In a full implementation, this would re-sort and re-render
}}

function toggleTailwind(el) {{
    tailwind = !tailwind;
    el.classList.toggle('active');
    // In a full implementation, this would re-calculate speeds
}}
</script>
</body>
</html>'''


def create_bring_selector_ui(
    your_team: list[dict],
    opponent_team: list[dict],
    recommendations: Optional[dict] = None,
) -> str:
    """Create a bring/leave selector UI for team preview.

    Args:
        your_team: Your 6 Pokemon with:
            - name: Pokemon name
            - score: Matchup score (0-100)
            - types: List of types
            - item: Held item
            - recommended: Whether to bring (True/False)
            - reasons: List of reasons for recommendation
        opponent_team: Opponent's 6 Pokemon with:
            - name: Pokemon name
            - types: List of types
        recommendations: Optional dict with:
            - lead_pair: [name1, name2]
            - back_pair: [name1, name2]
            - strategy: Strategy description

    Returns:
        HTML string for the bring selector UI
    """
    import json

    recommendations = recommendations or {}
    your_team_json = json.dumps(your_team)
    opp_team_json = json.dumps(opponent_team)

    # Split into recommended and not recommended
    bring = [p for p in your_team if p.get("recommended", False)]
    leave = [p for p in your_team if not p.get("recommended", False)]

    def get_score_class(score: int) -> str:
        if score >= 80:
            return "excellent"
        elif score >= 60:
            return "good"
        elif score >= 40:
            return "neutral"
        else:
            return "poor"

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    color: #e4e4e7;
    min-height: 100vh;
    padding: 16px;
}}
.container {{ max-width: 700px; margin: 0 auto; }}

.opponent-preview {{
    background: rgba(220,38,38,0.1);
    border: 1px solid rgba(220,38,38,0.3);
    border-radius: 16px;
    padding: 16px;
    margin-bottom: 16px;
}}
.opponent-title {{
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #f87171;
    margin-bottom: 12px;
}}
.opponent-grid {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}
.opp-pokemon {{
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,0,0,0.3);
    padding: 6px 12px;
    border-radius: 20px;
}}
.opp-sprite {{
    width: 32px;
    height: 32px;
    image-rendering: pixelated;
}}
.opp-name {{
    font-size: 0.85rem;
    text-transform: capitalize;
}}

.selection-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 16px;
}}
.selection-column {{
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    overflow: hidden;
}}
.column-header {{
    padding: 14px 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.column-header.bring {{
    background: linear-gradient(135deg, rgba(34,197,94,0.2) 0%, rgba(22,163,74,0.1) 100%);
    color: #4ade80;
    border-bottom: 1px solid rgba(34,197,94,0.2);
}}
.column-header.leave {{
    background: linear-gradient(135deg, rgba(148,163,184,0.15) 0%, rgba(100,116,139,0.1) 100%);
    color: #94a3b8;
    border-bottom: 1px solid rgba(148,163,184,0.2);
}}
.column-header .count {{
    background: rgba(255,255,255,0.1);
    padding: 2px 10px;
    border-radius: 10px;
    font-size: 0.8rem;
}}

.pokemon-list {{ padding: 8px; }}
.pokemon-card {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: rgba(0,0,0,0.2);
    border-radius: 12px;
    margin-bottom: 8px;
    cursor: pointer;
    transition: all 0.2s;
    border: 2px solid transparent;
}}
.pokemon-card:hover {{
    background: rgba(255,255,255,0.05);
}}
.pokemon-card.selected {{
    border-color: rgba(34,197,94,0.5);
    background: rgba(34,197,94,0.1);
}}
.pokemon-card:last-child {{ margin-bottom: 0; }}
.card-sprite {{
    width: 48px;
    height: 48px;
    image-rendering: pixelated;
}}
.card-info {{ flex: 1; }}
.card-name {{
    font-weight: 600;
    text-transform: capitalize;
    margin-bottom: 4px;
}}
.card-item {{
    font-size: 0.75rem;
    color: #64748b;
}}
.card-types {{
    display: flex;
    gap: 4px;
    margin-top: 4px;
}}
.type-dot {{
    width: 8px;
    height: 8px;
    border-radius: 50%;
}}
.card-score {{
    text-align: center;
}}
.score-value {{
    font-size: 1.4rem;
    font-weight: 700;
}}
.score-value.excellent {{ color: #4ade80; }}
.score-value.good {{ color: #a3e635; }}
.score-value.neutral {{ color: #fbbf24; }}
.score-value.poor {{ color: #f87171; }}
.score-label {{
    font-size: 0.65rem;
    text-transform: uppercase;
    color: #64748b;
    letter-spacing: 0.5px;
}}

.strategy-box {{
    background: linear-gradient(135deg, rgba(99,102,241,0.15) 0%, rgba(139,92,246,0.1) 100%);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 16px;
    padding: 16px;
}}
.strategy-title {{
    font-size: 0.8rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: #a78bfa;
    margin-bottom: 12px;
    display: flex;
    align-items: center;
    gap: 8px;
}}
.strategy-content {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}}
.strat-section {{
    background: rgba(0,0,0,0.2);
    padding: 12px;
    border-radius: 10px;
}}
.strat-label {{
    font-size: 0.7rem;
    color: #64748b;
    margin-bottom: 8px;
    text-transform: uppercase;
}}
.strat-pokemon {{
    display: flex;
    gap: 8px;
}}
.strat-mon {{
    display: flex;
    align-items: center;
    gap: 4px;
    background: rgba(255,255,255,0.05);
    padding: 4px 10px;
    border-radius: 16px;
    font-size: 0.85rem;
    text-transform: capitalize;
}}
.strat-sprite {{
    width: 24px;
    height: 24px;
    image-rendering: pixelated;
}}
.strategy-text {{
    grid-column: 1 / -1;
    font-size: 0.9rem;
    color: #c4b5fd;
    line-height: 1.5;
}}
    </style>
</head>
<body>
<div class="container">
    <div class="opponent-preview">
        <div class="opponent-title">Opponent's Team</div>
        <div class="opponent-grid">
            {"".join(f'''
            <div class="opp-pokemon">
                {get_sprite_html(p.get('name', ''), size=48, css_class="opp-sprite")}
                <span class="opp-name">{p.get('name', 'Unknown')}</span>
            </div>
            ''' for p in opponent_team)}
        </div>
    </div>

    <div class="selection-grid">
        <div class="selection-column">
            <div class="column-header bring">
                <span>&#10003;</span> Bring <span class="count">{len(bring)}/4</span>
            </div>
            <div class="pokemon-list">
                {"".join(f'''
                <div class="pokemon-card selected" data-name="{p.get('name', '')}">
                    {get_sprite_html(p.get('name', ''), size=48, css_class="card-sprite")}
                    <div class="card-info">
                        <div class="card-name">{p.get('name', 'Unknown')}</div>
                        <div class="card-item">{p.get('item', '')}</div>
                        <div class="card-types">
                            {"".join(f'<div class="type-dot" style="background:{get_type_color(t)}"></div>' for t in p.get('types', []))}
                        </div>
                    </div>
                    <div class="card-score">
                        <div class="score-value {get_score_class(p.get('score', 50))}">{p.get('score', 50)}</div>
                        <div class="score-label">Score</div>
                    </div>
                </div>
                ''' for p in bring)}
            </div>
        </div>

        <div class="selection-column">
            <div class="column-header leave">
                <span>&#10007;</span> Leave <span class="count">{len(leave)}</span>
            </div>
            <div class="pokemon-list">
                {"".join(f'''
                <div class="pokemon-card" data-name="{p.get('name', '')}">
                    {get_sprite_html(p.get('name', ''), size=48, css_class="card-sprite")}
                    <div class="card-info">
                        <div class="card-name">{p.get('name', 'Unknown')}</div>
                        <div class="card-item">{p.get('item', '')}</div>
                        <div class="card-types">
                            {"".join(f'<div class="type-dot" style="background:{get_type_color(t)}"></div>' for t in p.get('types', []))}
                        </div>
                    </div>
                    <div class="card-score">
                        <div class="score-value {get_score_class(p.get('score', 50))}">{p.get('score', 50)}</div>
                        <div class="score-label">Score</div>
                    </div>
                </div>
                ''' for p in leave) if leave else '<div style="padding:20px;text-align:center;color:#64748b;font-size:0.85rem;">All Pokemon recommended!</div>'}
            </div>
        </div>
    </div>

    {f'''
    <div class="strategy-box">
        <div class="strategy-title">&#128161; Recommended Strategy</div>
        <div class="strategy-content">
            <div class="strat-section">
                <div class="strat-label">Lead</div>
                <div class="strat-pokemon">
                    {"".join(f'<div class="strat-mon">{get_sprite_html(name, size=32, css_class="strat-sprite")}{name}</div>' for name in recommendations.get('lead_pair', []))}
                </div>
            </div>
            <div class="strat-section">
                <div class="strat-label">Back</div>
                <div class="strat-pokemon">
                    {"".join(f'<div class="strat-mon">{get_sprite_html(name, size=32, css_class="strat-sprite")}{name}</div>' for name in recommendations.get('back_pair', []))}
                </div>
            </div>
            <div class="strategy-text">{recommendations.get('strategy', '')}</div>
        </div>
    </div>
    ''' if recommendations.get('lead_pair') else ''}
</div>
</body>
</html>'''


def create_ability_synergy_ui(
    team: list[dict],
    synergies: dict,
) -> str:
    """Create an ability synergy network UI.

    Args:
        team: List of Pokemon with:
            - name: Pokemon name
            - ability: Ability name
            - types: List of types
        synergies: Dict with:
            - weather: {setter: name, abusers: [names], type: "sun"|"rain"|"sand"|"snow"}
            - terrain: {setter: name, abusers: [names], type: "electric"|"grassy"|"psychic"|"misty"}
            - intimidate: {blockers: [names], punishers: [names]}
            - conflicts: [{pokemon: [names], reason: str}]
            - combos: [{pokemon: [names], effect: str, rating: int}]

    Returns:
        HTML string for the ability synergy UI
    """
    import json

    team_json = json.dumps(team)
    synergies_json = json.dumps(synergies)

    weather = synergies.get("weather", {})
    terrain = synergies.get("terrain", {})
    intimidate = synergies.get("intimidate", {})
    conflicts = synergies.get("conflicts", [])
    combos = synergies.get("combos", [])

    weather_icons = {"sun": "&#9728;", "rain": "&#127783;️", "sand": "&#127964;️", "snow": "&#10052;️", "hail": "&#10052;️"}
    terrain_icons = {"electric": "&#9889;", "grassy": "&#127807;", "psychic": "&#128302;", "misty": "&#128168;"}

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    color: #e4e4e7;
    min-height: 100vh;
    padding: 16px;
}}
.container {{ max-width: 600px; margin: 0 auto; }}
.title {{
    font-size: 1.3rem;
    font-weight: 700;
    text-align: center;
    margin-bottom: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 10px;
}}
.title-icon {{ font-size: 1.5rem; }}

.team-bar {{
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-bottom: 20px;
    flex-wrap: wrap;
}}
.team-member {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 8px;
    background: rgba(255,255,255,0.03);
    border-radius: 12px;
    min-width: 70px;
}}
.team-sprite {{
    width: 48px;
    height: 48px;
    image-rendering: pixelated;
}}
.team-name {{
    font-size: 0.7rem;
    text-transform: capitalize;
    color: #94a3b8;
    margin-top: 4px;
    text-align: center;
}}
.team-ability {{
    font-size: 0.65rem;
    color: #64748b;
}}

.synergy-section {{
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 12px;
    overflow: hidden;
}}
.section-header {{
    padding: 14px 16px;
    display: flex;
    align-items: center;
    gap: 10px;
    font-weight: 600;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.section-header.weather {{
    background: linear-gradient(135deg, rgba(251,191,36,0.15) 0%, rgba(234,179,8,0.1) 100%);
}}
.section-header.terrain {{
    background: linear-gradient(135deg, rgba(34,197,94,0.15) 0%, rgba(22,163,74,0.1) 100%);
}}
.section-header.intimidate {{
    background: linear-gradient(135deg, rgba(239,68,68,0.15) 0%, rgba(220,38,38,0.1) 100%);
}}
.section-header.combos {{
    background: linear-gradient(135deg, rgba(139,92,246,0.15) 0%, rgba(124,58,237,0.1) 100%);
}}
.section-header.conflicts {{
    background: linear-gradient(135deg, rgba(251,113,133,0.15) 0%, rgba(244,63,94,0.1) 100%);
}}
.section-icon {{ font-size: 1.2rem; }}
.section-content {{ padding: 16px; }}

.flow-diagram {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 12px;
    flex-wrap: wrap;
}}
.flow-node {{
    display: flex;
    flex-direction: column;
    align-items: center;
    padding: 10px 14px;
    background: rgba(0,0,0,0.3);
    border-radius: 12px;
}}
.flow-node.setter {{
    background: linear-gradient(135deg, rgba(251,191,36,0.2) 0%, rgba(234,179,8,0.1) 100%);
    border: 1px solid rgba(251,191,36,0.3);
}}
.flow-node.abuser {{
    background: linear-gradient(135deg, rgba(34,197,94,0.2) 0%, rgba(22,163,74,0.1) 100%);
    border: 1px solid rgba(34,197,94,0.3);
}}
.flow-sprite {{
    width: 40px;
    height: 40px;
    image-rendering: pixelated;
}}
.flow-name {{
    font-size: 0.8rem;
    text-transform: capitalize;
    margin-top: 4px;
}}
.flow-role {{
    font-size: 0.65rem;
    color: #64748b;
    text-transform: uppercase;
}}
.flow-arrow {{
    font-size: 1.5rem;
    color: #64748b;
}}

.blocker-grid {{
    display: flex;
    gap: 16px;
    flex-wrap: wrap;
}}
.blocker-group {{
    flex: 1;
    min-width: 120px;
}}
.blocker-label {{
    font-size: 0.7rem;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 8px;
}}
.blocker-list {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}
.blocker-item {{
    display: flex;
    align-items: center;
    gap: 6px;
    background: rgba(0,0,0,0.3);
    padding: 6px 10px;
    border-radius: 20px;
    font-size: 0.8rem;
    text-transform: capitalize;
}}
.blocker-sprite {{
    width: 24px;
    height: 24px;
    image-rendering: pixelated;
}}

.combo-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: rgba(0,0,0,0.2);
    border-radius: 12px;
    margin-bottom: 8px;
}}
.combo-item:last-child {{ margin-bottom: 0; }}
.combo-pokemon {{
    display: flex;
    gap: 4px;
}}
.combo-sprite {{
    width: 36px;
    height: 36px;
    image-rendering: pixelated;
}}
.combo-info {{ flex: 1; }}
.combo-effect {{
    font-size: 0.9rem;
    margin-bottom: 4px;
}}
.combo-rating {{
    display: flex;
    gap: 2px;
}}
.rating-star {{ color: #fbbf24; font-size: 0.8rem; }}
.rating-star.empty {{ color: #475569; }}

.conflict-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    background: rgba(244,63,94,0.1);
    border: 1px solid rgba(244,63,94,0.2);
    border-radius: 12px;
    margin-bottom: 8px;
}}
.conflict-item:last-child {{ margin-bottom: 0; }}
.conflict-icon {{ font-size: 1.2rem; }}
.conflict-text {{ font-size: 0.9rem; }}

.empty-state {{
    text-align: center;
    padding: 20px;
    color: #64748b;
    font-size: 0.9rem;
}}
    </style>
</head>
<body>
<div class="container">
    <div class="title">
        <span class="title-icon">&#128279;</span>
        Ability Synergy
    </div>

    <div class="team-bar">
        {"".join(f'''
        <div class="team-member">
            {get_sprite_html(p.get('name', ''), size=48, css_class="team-sprite")}
            <div class="team-name">{p.get('name', 'Unknown')}</div>
            <div class="team-ability">{p.get('ability', '')}</div>
        </div>
        ''' for p in team)}
    </div>

    {f'''
    <div class="synergy-section">
        <div class="section-header weather">
            <span class="section-icon">{weather_icons.get(weather.get('type', ''), '&#127780;️')}</span>
            {weather.get('type', 'Weather').title()} Mode
        </div>
        <div class="section-content">
            <div class="flow-diagram">
                <div class="flow-node setter">
                    {get_sprite_html(weather.get('setter', ''), size=48, css_class="flow-sprite")}
                    <div class="flow-name">{weather.get('setter', 'None')}</div>
                    <div class="flow-role">Setter</div>
                </div>
                <div class="flow-arrow">&rarr;</div>
                {"".join(f'''
                <div class="flow-node abuser">
                    {get_sprite_html(abuser, size=48, css_class="flow-sprite")}
                    <div class="flow-name">{abuser}</div>
                    <div class="flow-role">Abuser</div>
                </div>
                ''' for abuser in weather.get('abusers', [])[:3])}
            </div>
        </div>
    </div>
    ''' if weather.get('setter') else ''}

    {f'''
    <div class="synergy-section">
        <div class="section-header terrain">
            <span class="section-icon">{terrain_icons.get(terrain.get('type', ''), '&#127757;')}</span>
            {terrain.get('type', 'Terrain').title()} Terrain
        </div>
        <div class="section-content">
            <div class="flow-diagram">
                <div class="flow-node setter">
                    {get_sprite_html(terrain.get('setter', ''), size=48, css_class="flow-sprite")}
                    <div class="flow-name">{terrain.get('setter', 'None')}</div>
                    <div class="flow-role">Setter</div>
                </div>
                <div class="flow-arrow">&rarr;</div>
                {"".join(f'''
                <div class="flow-node abuser">
                    {get_sprite_html(abuser, size=48, css_class="flow-sprite")}
                    <div class="flow-name">{abuser}</div>
                    <div class="flow-role">Abuser</div>
                </div>
                ''' for abuser in terrain.get('abusers', [])[:3])}
            </div>
        </div>
    </div>
    ''' if terrain.get('setter') else ''}

    {f'''
    <div class="synergy-section">
        <div class="section-header intimidate">
            <span class="section-icon">&#128548;</span>
            Intimidate Coverage
        </div>
        <div class="section-content">
            <div class="blocker-grid">
                <div class="blocker-group">
                    <div class="blocker-label">Blockers</div>
                    <div class="blocker-list">
                        {"".join(f'''
                        <div class="blocker-item">
                            {get_sprite_html(name, size=32, css_class="blocker-sprite")}
                            {name}
                        </div>
                        ''' for name in intimidate.get('blockers', [])) or '<span style="color:#64748b;font-size:0.8rem;">None</span>'}
                    </div>
                </div>
                <div class="blocker-group">
                    <div class="blocker-label">Punishers</div>
                    <div class="blocker-list">
                        {"".join(f'''
                        <div class="blocker-item">
                            {get_sprite_html(name, size=32, css_class="blocker-sprite")}
                            {name}
                        </div>
                        ''' for name in intimidate.get('punishers', [])) or '<span style="color:#64748b;font-size:0.8rem;">None</span>'}
                    </div>
                </div>
            </div>
        </div>
    </div>
    ''' if intimidate.get('blockers') or intimidate.get('punishers') else ''}

    {f'''
    <div class="synergy-section">
        <div class="section-header combos">
            <span class="section-icon">&#10024;</span>
            Ability Combos
        </div>
        <div class="section-content">
            {"".join(f'''
            <div class="combo-item">
                <div class="combo-pokemon">
                    {"".join(f'{get_sprite_html(name, size=32, css_class="combo-sprite")}' for name in c.get('pokemon', [])[:2])}
                </div>
                <div class="combo-info">
                    <div class="combo-effect">{c.get('effect', '')}</div>
                    <div class="combo-rating">
                        {"".join(f'<span class="rating-star">&#9733;</span>' for _ in range(c.get('rating', 3)))}
                        {"".join(f'<span class="rating-star empty">&#9733;</span>' for _ in range(5 - c.get('rating', 3)))}
                    </div>
                </div>
            </div>
            ''' for c in combos[:4])}
        </div>
    </div>
    ''' if combos else ''}

    {f'''
    <div class="synergy-section">
        <div class="section-header conflicts">
            <span class="section-icon">&#9888;</span>
            Conflicts
        </div>
        <div class="section-content">
            {"".join(f'''
            <div class="conflict-item">
                <span class="conflict-icon">&#9888;</span>
                <span class="conflict-text">{c.get('reason', '')}</span>
            </div>
            ''' for c in conflicts)}
        </div>
    </div>
    ''' if conflicts else ''}

    {f'''
    <div class="empty-state" style="margin-top:20px;">
        &#10003; No major synergies or conflicts detected
    </div>
    ''' if not weather.get('setter') and not terrain.get('setter') and not combos and not conflicts else ''}
</div>
</body>
</html>'''


def _build_suggestions_section(suggestions: list[dict], get_priority_class) -> str:
    """Build the suggestions section HTML for team report."""
    if not suggestions:
        return ''

    items_html = ''
    for s in suggestions[:3]:
        priority = s.get("priority", "low")
        priority_class = get_priority_class(priority)
        items_html += f'''
            <div class="suggestion-item {priority_class}">
                <div class="suggestion-content">
                    <div class="suggestion-action">{s.get("action", "")}</div>
                    <div class="suggestion-reason">{s.get("reason", "")}</div>
                </div>
                <span class="priority-tag {priority_class}">{priority}</span>
            </div>'''

    return f'''
    <div class="section">
        <div class="section-header">
            <span class="section-icon">&#128161;</span>
            Suggestions
        </div>
        <div class="section-content">
            {items_html}
        </div>
    </div>'''


def _build_legality_section(legality_issues: list[dict]) -> str:
    """Build the legality issues section HTML for team report."""
    if not legality_issues:
        return ''

    items_html = ''
    for i in legality_issues[:5]:
        severity = i.get("severity", "warning")
        icon = "&#10060;" if severity == "error" else "&#9888;"
        items_html += f'''
            <div class="legality-item {severity}">
                <span class="legality-icon">{icon}</span>
                <div class="legality-content">
                    <div class="legality-issue">{i.get("issue", "")}</div>
                    <div class="legality-fix">{i.get("fix", "")}</div>
                </div>
            </div>'''

    return f'''
    <div class="section">
        <div class="section-header">
            <span class="section-icon">&#9888;</span>
            Legality Issues
        </div>
        <div class="section-content">
            {items_html}
        </div>
    </div>'''


def create_team_report_ui(
    team_name: str,
    grade: str,
    tournament_ready: bool,
    strengths: list[str],
    weaknesses: list[str],
    suggestions: list[dict],
    legality_issues: list[dict],
    type_coverage: dict,
    speed_control: dict,
    team: list[dict],
) -> str:
    """Create a comprehensive team report card UI.

    Args:
        team_name: Team name or identifier
        grade: Letter grade (A+, A, B+, B, C+, C, D, F)
        tournament_ready: Whether team is legal for tournament
        strengths: List of strength descriptions
        weaknesses: List of weakness descriptions
        suggestions: List of suggestion dicts with:
            - action: What to do
            - reason: Why
            - priority: "high", "medium", "low"
        legality_issues: List of issue dicts with:
            - issue: Description
            - severity: "error", "warning"
            - fix: How to fix
        type_coverage: Dict with:
            - super_effective: List of types
            - weak_to: List of types
            - resists: List of types
        speed_control: Dict with:
            - has_trick_room: bool
            - has_tailwind: bool
            - fastest: name
            - slowest: name
        team: List of team Pokemon for display

    Returns:
        HTML string for the team report UI
    """
    import json

    def get_grade_color(g: str) -> str:
        if g.startswith('A'):
            return '#4ade80'
        elif g.startswith('B'):
            return '#a3e635'
        elif g.startswith('C'):
            return '#fbbf24'
        elif g.startswith('D'):
            return '#fb923c'
        else:
            return '#f87171'

    def get_priority_class(p: str) -> str:
        return {"high": "high", "medium": "medium", "low": "low"}.get(p, "low")

    team_json = json.dumps(team)

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 100%);
    color: #e4e4e7;
    min-height: 100vh;
    padding: 16px;
}}
.container {{ max-width: 650px; margin: 0 auto; }}

.header {{
    background: linear-gradient(135deg, rgba(99,102,241,0.2) 0%, rgba(139,92,246,0.15) 100%);
    border: 1px solid rgba(99,102,241,0.3);
    border-radius: 20px;
    padding: 24px;
    text-align: center;
    margin-bottom: 16px;
}}
.team-title {{
    font-size: 1.1rem;
    color: #94a3b8;
    margin-bottom: 12px;
}}
.grade-display {{
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 80px;
    height: 80px;
    font-size: 2.5rem;
    font-weight: 800;
    border-radius: 50%;
    background: rgba(0,0,0,0.3);
    color: {get_grade_color(grade)};
    margin-bottom: 12px;
    box-shadow: 0 0 30px {get_grade_color(grade)}40;
}}
.ready-badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 8px 16px;
    border-radius: 20px;
    font-size: 0.85rem;
    font-weight: 600;
}}
.ready-badge.ready {{
    background: rgba(34,197,94,0.2);
    color: #4ade80;
    border: 1px solid rgba(34,197,94,0.3);
}}
.ready-badge.not-ready {{
    background: rgba(239,68,68,0.2);
    color: #f87171;
    border: 1px solid rgba(239,68,68,0.3);
}}

.team-preview {{
    display: flex;
    justify-content: center;
    gap: 8px;
    margin-top: 16px;
    flex-wrap: wrap;
}}
.team-mon {{
    width: 48px;
    height: 48px;
    image-rendering: pixelated;
}}

.section {{
    background: rgba(255,255,255,0.03);
    border-radius: 16px;
    border: 1px solid rgba(255,255,255,0.1);
    margin-bottom: 12px;
    overflow: hidden;
}}
.section-header {{
    padding: 14px 16px;
    font-weight: 600;
    display: flex;
    align-items: center;
    gap: 10px;
    background: rgba(0,0,0,0.2);
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.section-icon {{ font-size: 1.1rem; }}
.section-content {{ padding: 16px; }}

.two-col {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}}
.col-title {{
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
}}
.col-title.strengths {{ color: #4ade80; }}
.col-title.weaknesses {{ color: #f87171; }}

.point-list {{ list-style: none; }}
.point-item {{
    display: flex;
    align-items: flex-start;
    gap: 8px;
    padding: 8px 0;
    font-size: 0.9rem;
    color: #c4b5fd;
    border-bottom: 1px solid rgba(255,255,255,0.05);
}}
.point-item:last-child {{ border-bottom: none; }}
.point-icon {{ flex-shrink: 0; }}
.point-icon.strength {{ color: #4ade80; }}
.point-icon.weakness {{ color: #f87171; }}

.suggestion-item {{
    display: flex;
    gap: 12px;
    padding: 12px;
    background: rgba(0,0,0,0.2);
    border-radius: 12px;
    margin-bottom: 8px;
    border-left: 3px solid;
}}
.suggestion-item:last-child {{ margin-bottom: 0; }}
.suggestion-item.high {{ border-color: #f87171; }}
.suggestion-item.medium {{ border-color: #fbbf24; }}
.suggestion-item.low {{ border-color: #4ade80; }}
.suggestion-content {{ flex: 1; }}
.suggestion-action {{
    font-weight: 500;
    margin-bottom: 4px;
}}
.suggestion-reason {{
    font-size: 0.85rem;
    color: #94a3b8;
}}
.priority-tag {{
    font-size: 0.7rem;
    text-transform: uppercase;
    padding: 3px 8px;
    border-radius: 8px;
    font-weight: 600;
}}
.priority-tag.high {{ background: rgba(239,68,68,0.2); color: #f87171; }}
.priority-tag.medium {{ background: rgba(234,179,8,0.2); color: #fbbf24; }}
.priority-tag.low {{ background: rgba(34,197,94,0.2); color: #4ade80; }}

.legality-item {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    border-radius: 10px;
    margin-bottom: 8px;
}}
.legality-item:last-child {{ margin-bottom: 0; }}
.legality-item.error {{
    background: rgba(239,68,68,0.1);
    border: 1px solid rgba(239,68,68,0.2);
}}
.legality-item.warning {{
    background: rgba(234,179,8,0.1);
    border: 1px solid rgba(234,179,8,0.2);
}}
.legality-icon {{ font-size: 1.2rem; }}
.legality-content {{ flex: 1; }}
.legality-issue {{ font-weight: 500; margin-bottom: 4px; }}
.legality-fix {{ font-size: 0.85rem; color: #94a3b8; }}

.coverage-grid {{
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
}}
.coverage-col {{
    background: rgba(0,0,0,0.2);
    padding: 12px;
    border-radius: 10px;
}}
.coverage-label {{
    font-size: 0.7rem;
    text-transform: uppercase;
    color: #64748b;
    margin-bottom: 8px;
}}
.type-list {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}}
.type-chip {{
    padding: 3px 8px;
    border-radius: 8px;
    font-size: 0.7rem;
    font-weight: 500;
    color: white;
    text-shadow: 0 1px 2px rgba(0,0,0,0.3);
}}

.speed-info {{
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 12px;
}}
.speed-card {{
    background: rgba(0,0,0,0.2);
    padding: 12px;
    border-radius: 10px;
    display: flex;
    align-items: center;
    gap: 10px;
}}
.speed-sprite {{
    width: 40px;
    height: 40px;
    image-rendering: pixelated;
}}
.speed-label {{
    font-size: 0.7rem;
    color: #64748b;
    text-transform: uppercase;
}}
.speed-name {{
    font-weight: 500;
    text-transform: capitalize;
}}
.control-badges {{
    display: flex;
    gap: 8px;
    margin-top: 12px;
}}
.control-badge {{
    padding: 6px 12px;
    border-radius: 16px;
    font-size: 0.8rem;
    font-weight: 500;
    display: flex;
    align-items: center;
    gap: 6px;
}}
.control-badge.active {{
    background: rgba(139,92,246,0.2);
    color: #a78bfa;
}}
.control-badge.inactive {{
    background: rgba(100,116,139,0.2);
    color: #64748b;
}}
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <div class="team-title">{team_name}</div>
        <div class="grade-display">{grade}</div>
        <div class="ready-badge {'ready' if tournament_ready else 'not-ready'}">
            {'&#10003; Tournament Ready' if tournament_ready else '&#10007; Not Tournament Ready'}
        </div>
        <div class="team-preview">
            {"".join(f'{get_sprite_html(p.get("name", ""), size=48, css_class="team-mon")}' for p in team[:6])}
        </div>
    </div>

    <div class="section">
        <div class="section-header">
            <span class="section-icon">&#128202;</span>
            Analysis
        </div>
        <div class="section-content">
            <div class="two-col">
                <div>
                    <div class="col-title strengths">Strengths</div>
                    <ul class="point-list">
                        {"".join(f'<li class="point-item"><span class="point-icon strength">&#10003;</span>{s}</li>' for s in strengths[:5]) or '<li class="point-item" style="color:#64748b">No major strengths identified</li>'}
                    </ul>
                </div>
                <div>
                    <div class="col-title weaknesses">Weaknesses</div>
                    <ul class="point-list">
                        {"".join(f'<li class="point-item"><span class="point-icon weakness">&#10007;</span>{w}</li>' for w in weaknesses[:5]) or '<li class="point-item" style="color:#64748b">No major weaknesses identified</li>'}
                    </ul>
                </div>
            </div>
        </div>
    </div>

    {_build_suggestions_section(suggestions, get_priority_class)}

    {_build_legality_section(legality_issues)}

    <div class="section">
        <div class="section-header">
            <span class="section-icon">&#127919;</span>
            Type Coverage
        </div>
        <div class="section-content">
            <div class="coverage-grid">
                <div class="coverage-col">
                    <div class="coverage-label">Super Effective</div>
                    <div class="type-list">
                        {"".join(f'<span class="type-chip" style="background:{get_type_color(t)}">{t}</span>' for t in type_coverage.get("super_effective", [])[:6]) or '<span style="color:#64748b;font-size:0.8rem;">Limited</span>'}
                    </div>
                </div>
                <div class="coverage-col">
                    <div class="coverage-label">Resists</div>
                    <div class="type-list">
                        {"".join(f'<span class="type-chip" style="background:{get_type_color(t)}">{t}</span>' for t in type_coverage.get("resists", [])[:6]) or '<span style="color:#64748b;font-size:0.8rem;">Limited</span>'}
                    </div>
                </div>
                <div class="coverage-col">
                    <div class="coverage-label">Weak To</div>
                    <div class="type-list">
                        {"".join(f'<span class="type-chip" style="background:{get_type_color(t)}">{t}</span>' for t in type_coverage.get("weak_to", [])[:6]) or '<span style="color:#64748b;font-size:0.8rem;">None</span>'}
                    </div>
                </div>
            </div>
        </div>
    </div>

    <div class="section">
        <div class="section-header">
            <span class="section-icon">&#9889;</span>
            Speed Control
        </div>
        <div class="section-content">
            <div class="speed-info">
                <div class="speed-card">
                    {get_sprite_html(speed_control.get('fastest', ''), size=48, css_class="speed-sprite")}
                    <div>
                        <div class="speed-label">Fastest</div>
                        <div class="speed-name">{speed_control.get('fastest', 'N/A')}</div>
                    </div>
                </div>
                <div class="speed-card">
                    {get_sprite_html(speed_control.get('slowest', ''), size=48, css_class="speed-sprite")}
                    <div>
                        <div class="speed-label">Slowest</div>
                        <div class="speed-name">{speed_control.get('slowest', 'N/A')}</div>
                    </div>
                </div>
            </div>
            <div class="control-badges">
                <div class="control-badge {'active' if speed_control.get('has_trick_room') else 'inactive'}">
                    &#128260; Trick Room
                </div>
                <div class="control-badge {'active' if speed_control.get('has_tailwind') else 'inactive'}">
                    &#128168; Tailwind
                </div>
            </div>
        </div>
    </div>
</div>
</body>
</html>'''


def create_summary_table_ui(
    title: str,
    rows: list[dict[str, str]],
    highlight_rows: list[str] | None = None,
    analysis: str | None = None,
) -> str:
    """Create a styled summary table UI HTML.

    Args:
        title: Table title (e.g., "Damage Calculation")
        rows: List of dicts with 'metric' and 'value' keys
        highlight_rows: List of metric names to highlight
        analysis: Optional prose summary to show above table

    Returns:
        HTML string for the summary table UI
    """
    styles = get_shared_styles()
    highlight_rows = highlight_rows or []

    # Build table rows
    rows_html = ""
    for row in rows:
        metric = row.get("metric", "")
        value = row.get("value", "")
        is_highlight = metric in highlight_rows

        row_class = "highlight" if is_highlight else ""
        rows_html += f"""
        <tr class="{row_class}">
            <td class="metric-cell">{metric}</td>
            <td class="value-cell">{value}</td>
        </tr>
        """

    # Analysis section
    analysis_html = ""
    if analysis:
        analysis_html = f"""
        <div class="analysis-box">
            <span class="analysis-icon">&#128161;</span>
            <span class="analysis-text">{analysis}</span>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {styles}
        .summary-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        .summary-table th {{
            background: var(--bg-secondary);
            padding: 10px 12px;
            text-align: left;
            font-weight: 600;
            border-bottom: 2px solid var(--accent-blue);
        }}
        .summary-table td {{
            padding: 8px 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        }}
        .summary-table tr:hover {{
            background: rgba(77, 166, 255, 0.1);
        }}
        .summary-table tr.highlight {{
            background: rgba(77, 166, 255, 0.2);
        }}
        .summary-table tr.highlight td {{
            font-weight: 600;
        }}
        .metric-cell {{
            color: var(--text-secondary);
            width: 40%;
        }}
        .value-cell {{
            color: var(--text-primary);
            font-weight: 500;
        }}
        .analysis-box {{
            background: rgba(76, 175, 80, 0.15);
            border-left: 3px solid var(--accent-green);
            padding: 10px 12px;
            margin-bottom: 12px;
            border-radius: 0 6px 6px 0;
            display: flex;
            align-items: flex-start;
            gap: 8px;
        }}
        .analysis-icon {{
            font-size: 16px;
        }}
        .analysis-text {{
            color: var(--text-primary);
            font-size: 13px;
            line-height: 1.4;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">{title}</span>
        </div>
        {analysis_html}
        <table class="summary-table">
            <thead>
                <tr>
                    <th>Metric</th>
                    <th>Value</th>
                </tr>
            </thead>
            <tbody>
                {rows_html}
            </tbody>
        </table>
    </div>
</body>
</html>"""


def create_speed_outspeed_graph_ui(
    pokemon_name: str,
    pokemon_speed: int,
    target_pokemon: str,
    target_spreads: list[dict[str, Any]],
    outspeed_percent: float,
) -> str:
    """Create a cumulative speed outspeed graph UI HTML.

    Shows what percentage of a target Pokemon's common spreads you outspeed.

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat
        target_pokemon: The target Pokemon to compare against
        target_spreads: List of dicts with 'speed' and 'usage' (percentage) keys
        outspeed_percent: Percentage of spreads outsped (0-100)

    Returns:
        HTML string for the speed outspeed graph UI
    """
    styles = get_shared_styles()

    # Sort spreads by speed
    sorted_spreads = sorted(target_spreads, key=lambda x: x.get("speed", 0))

    # Calculate cumulative percentages and build bar data
    bars_html = ""
    cumulative = 0
    speed_marks = []

    for spread in sorted_spreads:
        speed = spread.get("speed", 0)
        usage = spread.get("usage", 0)
        cumulative += usage

        # Determine if we outspeed this spread
        outspeeds = pokemon_speed > speed
        bar_class = "outsped" if outspeeds else "not-outsped"

        # Add to marks for display
        speed_marks.append({
            "speed": speed,
            "cumulative": cumulative,
            "outspeeds": outspeeds,
            "usage": usage,
        })

        # Create visual bar segment
        bars_html += f"""
        <div class="spread-bar {bar_class}" style="width: {usage}%;" title="{speed} Spe: {usage:.1f}% usage">
            <span class="speed-label">{speed}</span>
        </div>
        """

    # Result color
    if outspeed_percent >= 80:
        result_class = "excellent"
        result_emoji = "&#128994;"
    elif outspeed_percent >= 50:
        result_class = "good"
        result_emoji = "&#128993;"
    else:
        result_class = "poor"
        result_emoji = "&#128308;"

    # Create speed tier list
    tiers_html = ""
    for mark in speed_marks:
        tier_class = "outsped" if mark["outspeeds"] else "not-outsped"
        check = "&#10003;" if mark["outspeeds"] else "&#10007;"
        tiers_html += f"""
        <div class="tier-row {tier_class}">
            <span class="tier-check">{check}</span>
            <span class="tier-speed">{mark['speed']} Spe</span>
            <span class="tier-usage">{mark['usage']:.1f}%</span>
        </div>
        """

    # Add marker for your Pokemon
    marker_position = outspeed_percent

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {styles}
        .outspeed-container {{
            padding: 4px;
        }}
        .result-banner {{
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 16px;
            text-align: center;
            margin-bottom: 16px;
        }}
        .result-banner.excellent {{ border-left: 4px solid #4caf50; }}
        .result-banner.good {{ border-left: 4px solid #ff9800; }}
        .result-banner.poor {{ border-left: 4px solid #f44336; }}
        .result-percent {{
            font-size: 32px;
            font-weight: 700;
            color: var(--text-primary);
        }}
        .result-text {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}
        .graph-container {{
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 16px;
            margin-bottom: 16px;
        }}
        .graph-title {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 12px;
        }}
        .bar-chart {{
            display: flex;
            height: 40px;
            border-radius: 6px;
            overflow: hidden;
            position: relative;
        }}
        .spread-bar {{
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 10px;
            color: white;
            min-width: 20px;
            transition: transform 0.2s;
        }}
        .spread-bar:hover {{
            transform: scaleY(1.1);
        }}
        .spread-bar.outsped {{
            background: linear-gradient(135deg, #4caf50, #2e7d32);
        }}
        .spread-bar.not-outsped {{
            background: linear-gradient(135deg, #f44336, #c62828);
        }}
        .speed-label {{
            font-weight: 600;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}
        .marker {{
            position: absolute;
            top: -8px;
            left: {marker_position}%;
            transform: translateX(-50%);
            background: var(--accent-blue);
            color: white;
            padding: 2px 6px;
            border-radius: 4px;
            font-size: 10px;
            font-weight: 600;
            white-space: nowrap;
        }}
        .marker::after {{
            content: '';
            position: absolute;
            bottom: -4px;
            left: 50%;
            transform: translateX(-50%);
            border-left: 4px solid transparent;
            border-right: 4px solid transparent;
            border-top: 4px solid var(--accent-blue);
        }}
        .tier-list {{
            max-height: 200px;
            overflow-y: auto;
        }}
        .tier-row {{
            display: flex;
            align-items: center;
            padding: 6px 8px;
            border-radius: 4px;
            margin-bottom: 4px;
            font-size: 12px;
        }}
        .tier-row.outsped {{
            background: rgba(76, 175, 80, 0.15);
        }}
        .tier-row.not-outsped {{
            background: rgba(244, 67, 54, 0.15);
        }}
        .tier-check {{
            width: 20px;
            font-weight: 600;
        }}
        .tier-row.outsped .tier-check {{ color: #4caf50; }}
        .tier-row.not-outsped .tier-check {{ color: #f44336; }}
        .tier-speed {{
            flex: 1;
            color: var(--text-primary);
        }}
        .tier-usage {{
            color: var(--text-secondary);
        }}
        .legend {{
            display: flex;
            gap: 16px;
            font-size: 11px;
            color: var(--text-secondary);
            margin-top: 8px;
        }}
        .legend-item {{
            display: flex;
            align-items: center;
            gap: 4px;
        }}
        .legend-dot {{
            width: 10px;
            height: 10px;
            border-radius: 2px;
        }}
        .legend-dot.green {{ background: #4caf50; }}
        .legend-dot.red {{ background: #f44336; }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">Speed Matchup vs {target_pokemon}</span>
        </div>
        <div class="outspeed-container">
            <div class="result-banner {result_class}">
                <div class="result-percent">{result_emoji} {outspeed_percent:.1f}%</div>
                <div class="result-text">
                    {pokemon_name} ({pokemon_speed} Spe) outspeeds {outspeed_percent:.1f}% of {target_pokemon} spreads
                </div>
            </div>

            <div class="graph-container">
                <div class="graph-title">Speed Distribution (by usage)</div>
                <div style="position: relative; padding-top: 16px;">
                    <div class="marker">▼ {pokemon_name}</div>
                    <div class="bar-chart">
                        {bars_html}
                    </div>
                </div>
                <div class="legend">
                    <div class="legend-item">
                        <div class="legend-dot green"></div>
                        <span>Outsped</span>
                    </div>
                    <div class="legend-item">
                        <div class="legend-dot red"></div>
                        <span>Not outsped</span>
                    </div>
                </div>
            </div>

            <div class="graph-container">
                <div class="graph-title">Speed Tiers ({len(target_spreads)} common spreads)</div>
                <div class="tier-list">
                    {tiers_html}
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""


def create_multi_hit_survival_ui(
    defender_name: str,
    attacker_name: str,
    move_name: str,
    num_hits: int,
    per_hit_min: float,
    per_hit_max: float,
    total_min: float,
    total_max: float,
    hp_remaining_min: float,
    hp_remaining_max: float,
    survival_chance: float,
    survives: bool,
) -> str:
    """Create a multi-hit survival visualization UI.

    Args:
        defender_name: Defending Pokemon
        attacker_name: Attacking Pokemon
        move_name: Move name
        num_hits: Number of hits
        per_hit_min: Min damage per hit (%)
        per_hit_max: Max damage per hit (%)
        total_min: Total min damage (%)
        total_max: Total max damage (%)
        hp_remaining_min: Min HP remaining (%)
        hp_remaining_max: Max HP remaining (%)
        survival_chance: Chance to survive (0-100)
        survives: Whether guaranteed to survive

    Returns:
        HTML string for the multi-hit survival UI
    """
    styles = get_shared_styles()

    # Survival status
    if survives:
        status_class = "survives"
        status_text = "Survives"
        status_emoji = "&#10003;"
    elif survival_chance > 0:
        status_class = "possible"
        status_text = f"{survival_chance:.1f}% to survive"
        status_emoji = "?"
    else:
        status_class = "faints"
        status_text = "Faints"
        status_emoji = "&#10007;"

    # Build hit visualization
    hits_html = ""
    for i in range(num_hits):
        hits_html += f"""
        <div class="hit-segment" style="width: {100/num_hits}%;">
            <div class="hit-bar" style="height: {min(100, per_hit_max)}%;"></div>
            <div class="hit-label">Hit {i+1}</div>
        </div>
        """

    # HP bar
    hp_remaining_avg = (hp_remaining_min + hp_remaining_max) / 2
    hp_color = "#4caf50" if hp_remaining_avg > 50 else ("#ff9800" if hp_remaining_avg > 25 else "#f44336")

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {styles}
        .survival-container {{
            padding: 4px;
        }}
        .matchup-header {{
            display: flex;
            align-items: center;
            justify-content: space-between;
            margin-bottom: 16px;
        }}
        .pokemon-side {{
            display: flex;
            align-items: center;
            gap: 8px;
        }}
        .pokemon-sprite {{
            width: 50px;
            height: 50px;
            object-fit: contain;
        }}
        .pokemon-name {{
            font-weight: 600;
            font-size: 14px;
        }}
        .move-badge {{
            background: var(--bg-secondary);
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 12px;
            color: var(--accent-blue);
        }}
        .status-banner {{
            text-align: center;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 16px;
        }}
        .status-banner.survives {{
            background: rgba(76, 175, 80, 0.2);
            border: 1px solid #4caf50;
        }}
        .status-banner.possible {{
            background: rgba(255, 152, 0, 0.2);
            border: 1px solid #ff9800;
        }}
        .status-banner.faints {{
            background: rgba(244, 67, 54, 0.2);
            border: 1px solid #f44336;
        }}
        .status-emoji {{
            font-size: 24px;
        }}
        .status-text {{
            font-size: 16px;
            font-weight: 600;
            margin-top: 4px;
        }}
        .hits-visualization {{
            display: flex;
            height: 80px;
            background: var(--bg-secondary);
            border-radius: 8px;
            overflow: hidden;
            margin-bottom: 16px;
        }}
        .hit-segment {{
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-end;
            border-right: 1px solid rgba(255,255,255,0.1);
        }}
        .hit-segment:last-child {{
            border-right: none;
        }}
        .hit-bar {{
            width: 80%;
            background: linear-gradient(to top, #f44336, #ff9800);
            border-radius: 4px 4px 0 0;
            transition: height 0.3s;
        }}
        .hit-label {{
            font-size: 10px;
            color: var(--text-secondary);
            padding: 4px;
        }}
        .hp-section {{
            background: var(--bg-secondary);
            border-radius: 8px;
            padding: 12px;
        }}
        .hp-label {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-bottom: 8px;
        }}
        .hp-bar-container {{
            height: 24px;
            background: rgba(255,255,255,0.1);
            border-radius: 12px;
            overflow: hidden;
            position: relative;
        }}
        .hp-bar {{
            height: 100%;
            background: {hp_color};
            border-radius: 12px;
            transition: width 0.3s;
        }}
        .hp-text {{
            position: absolute;
            right: 8px;
            top: 50%;
            transform: translateY(-50%);
            font-size: 12px;
            font-weight: 600;
            color: white;
            text-shadow: 0 1px 2px rgba(0,0,0,0.5);
        }}
        .damage-stats {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 12px;
            margin-top: 16px;
        }}
        .stat-box {{
            background: var(--bg-secondary);
            padding: 10px;
            border-radius: 6px;
            text-align: center;
        }}
        .stat-label {{
            font-size: 10px;
            color: var(--text-secondary);
            text-transform: uppercase;
        }}
        .stat-value {{
            font-size: 16px;
            font-weight: 600;
            margin-top: 4px;
        }}
    </style>
</head>
<body>
    <div class="card">
        <div class="card-header">
            <span class="card-title">Multi-Hit Survival Analysis</span>
        </div>
        <div class="survival-container">
            <div class="matchup-header">
                <div class="pokemon-side">
                    {get_sprite_html(attacker_name, size=48, css_class="pokemon-sprite")}
                    <span class="pokemon-name">{attacker_name}</span>
                </div>
                <div class="move-badge">{move_name} x{num_hits}</div>
                <div class="pokemon-side">
                    <span class="pokemon-name">{defender_name}</span>
                    {get_sprite_html(defender_name, size=48, css_class="pokemon-sprite")}
                </div>
            </div>

            <div class="status-banner {status_class}">
                <div class="status-emoji">{status_emoji}</div>
                <div class="status-text">{status_text}</div>
            </div>

            <div class="hits-visualization">
                {hits_html}
            </div>

            <div class="hp-section">
                <div class="hp-label">HP Remaining after {num_hits} hits</div>
                <div class="hp-bar-container">
                    <div class="hp-bar" style="width: {max(0, hp_remaining_avg)}%;"></div>
                    <span class="hp-text">{hp_remaining_min:.0f}-{hp_remaining_max:.0f}%</span>
                </div>
            </div>

            <div class="damage-stats">
                <div class="stat-box">
                    <div class="stat-label">Per Hit</div>
                    <div class="stat-value">{per_hit_min:.1f}-{per_hit_max:.1f}%</div>
                </div>
                <div class="stat-box">
                    <div class="stat-label">Total Damage</div>
                    <div class="stat-value">{total_min:.1f}-{total_max:.1f}%</div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""


def create_calc_history_ui(
    calculations: list[dict[str, Any]],
) -> str:
    """Create calculation history UI HTML.

    Args:
        calculations: List of calc dicts with keys: attacker, defender, move, damage_min, damage_max, ko_chance, timestamp

    Returns:
        HTML string for the calc history UI
    """
    # Build history entries
    entries_html = ""
    for i, calc in enumerate(calculations[:10]):  # Show last 10
        attacker = calc.get("attacker", "Unknown")
        defender = calc.get("defender", "Unknown")
        move = calc.get("move", "Unknown")
        dmg_min = calc.get("damage_min", 0)
        dmg_max = calc.get("damage_max", 0)
        ko_chance = calc.get("ko_chance", "")
        timestamp = calc.get("timestamp", "")

        # KO badge styling
        ko_class = "survive"
        if "OHKO" in ko_chance.upper():
            ko_class = "ohko"
        elif "2HKO" in ko_chance.upper():
            ko_class = "2hko"
        elif "3HKO" in ko_chance.upper():
            ko_class = "3hko"

        delay = i * 0.05

        entries_html += f"""
        <div class="history-entry" style="animation-delay: {delay}s;">
            <div class="entry-pokemon">
                {get_sprite_html(attacker, size=40, css_class="entry-sprite")}
                <span class="entry-arrow">&#10140;</span>
                {get_sprite_html(defender, size=40, css_class="entry-sprite")}
            </div>
            <div class="entry-details">
                <div class="entry-move">{move}</div>
                <div class="entry-damage">{dmg_min:.1f}% - {dmg_max:.1f}%</div>
            </div>
            <div class="entry-ko-badge {ko_class}">{ko_chance}</div>
        </div>
        """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%);
    color: #e4e4e7;
    line-height: 1.5;
    min-height: 100vh;
    padding: 24px;
}}

@keyframes fadeSlideIn {{
    0% {{ opacity: 0; transform: translateX(-10px); }}
    100% {{ opacity: 1; transform: translateX(0); }}
}}

.history-container {{
    max-width: 600px;
    margin: 0 auto;
}}

.history-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 20px 24px;
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px 20px 0 0;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: none;
}}

.history-title {{
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    display: flex;
    align-items: center;
    gap: 10px;
}}

.history-title::before {{
    content: "&#128202;";
    font-size: 20px;
}}

.history-count {{
    font-size: 12px;
    color: #71717a;
}}

.history-list {{
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 0 0 20px 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
}}

.history-entry {{
    display: flex;
    align-items: center;
    gap: 16px;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    animation: fadeSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) backwards;
    transition: background 0.3s ease;
    cursor: pointer;
}}

.history-entry:hover {{
    background: rgba(255, 255, 255, 0.04);
}}

.history-entry:last-child {{
    border-bottom: none;
}}

.entry-pokemon {{
    display: flex;
    align-items: center;
    gap: 8px;
}}

.entry-sprite {{
    width: 40px;
    height: 40px;
    image-rendering: auto;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
}}

.entry-arrow {{
    font-size: 16px;
    color: #6366f1;
}}

.entry-details {{
    flex: 1;
}}

.entry-move {{
    font-size: 14px;
    font-weight: 600;
    color: #e4e4e7;
}}

.entry-damage {{
    font-size: 12px;
    color: #71717a;
}}

.entry-ko-badge {{
    padding: 6px 12px;
    border-radius: 20px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.entry-ko-badge.ohko {{
    background: linear-gradient(135deg, rgba(239, 68, 68, 0.2), rgba(220, 38, 38, 0.15));
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.3);
}}

.entry-ko-badge.2hko {{
    background: linear-gradient(135deg, rgba(249, 115, 22, 0.2), rgba(234, 88, 12, 0.15));
    color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.3);
}}

.entry-ko-badge.3hko {{
    background: linear-gradient(135deg, rgba(234, 179, 8, 0.2), rgba(202, 138, 4, 0.15));
    color: #fbbf24;
    border: 1px solid rgba(234, 179, 8, 0.3);
}}

.entry-ko-badge.survive {{
    background: linear-gradient(135deg, rgba(34, 197, 94, 0.2), rgba(22, 163, 74, 0.15));
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.3);
}}

.empty-state {{
    text-align: center;
    padding: 40px 20px;
    color: #52525b;
}}

.empty-icon {{
    font-size: 40px;
    margin-bottom: 12px;
}}

.empty-text {{
    font-size: 14px;
}}
    </style>
</head>
<body>
    <div class="history-container">
        <div class="history-header">
            <div class="history-title">Calculation History</div>
            <span class="history-count">{len(calculations)} calculations</span>
        </div>
        <div class="history-list">
            {entries_html if entries_html else '<div class="empty-state"><div class="empty-icon">&#128203;</div><div class="empty-text">No calculations yet</div></div>'}
        </div>
    </div>
</body>
</html>"""


def create_team_synergy_ui(
    team: list[dict[str, Any]],
    synergies: dict[str, Any],
) -> str:
    """Create team synergy visualization UI HTML.

    Args:
        team: List of Pokemon dicts with keys: name, types, ability, item
        synergies: Dict with keys: weather_setters, terrain_setters, speed_control, redirectors, etc.

    Returns:
        HTML string for the team synergy UI
    """
    # Build synergy categories
    weather = synergies.get("weather_setters", [])
    terrain = synergies.get("terrain_setters", [])
    speed_ctrl = synergies.get("speed_control", [])
    redirectors = synergies.get("redirectors", [])
    fake_out = synergies.get("fake_out_users", [])
    intimidate = synergies.get("intimidate", [])
    priority = synergies.get("priority_users", [])

    def build_synergy_row(label: str, icon: str, pokemon_list: list[str], color: str) -> str:
        if not pokemon_list:
            return ""
        sprites = "".join(
            get_sprite_html(p, size=40, css_class="synergy-sprite")
            for p in pokemon_list
        )
        return f"""
        <div class="synergy-row">
            <div class="synergy-label" style="--synergy-color: {color};">
                <span class="synergy-icon">{icon}</span>
                <span>{label}</span>
            </div>
            <div class="synergy-pokemon">{sprites}</div>
        </div>
        """

    synergy_rows = ""
    synergy_rows += build_synergy_row("Weather Control", "&#9748;", weather, "#60a5fa")
    synergy_rows += build_synergy_row("Terrain Control", "&#127793;", terrain, "#4ade80")
    synergy_rows += build_synergy_row("Speed Control", "&#128168;", speed_ctrl, "#f472b6")
    synergy_rows += build_synergy_row("Redirectors", "&#127919;", redirectors, "#fbbf24")
    synergy_rows += build_synergy_row("Fake Out", "&#9995;", fake_out, "#fb923c")
    synergy_rows += build_synergy_row("Intimidate", "&#128567;", intimidate, "#f87171")
    synergy_rows += build_synergy_row("Priority Moves", "&#9889;", priority, "#a78bfa")

    # Type coverage summary
    team_types = []
    for p in team:
        team_types.extend(p.get("types", []))
    unique_types = list(set(t.lower() for t in team_types))

    type_coverage_html = ""
    for t in unique_types:
        type_coverage_html += f'<span class="type-mini type-{t}">{t.title()}</span>'

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%);
    color: #e4e4e7;
    line-height: 1.5;
    min-height: 100vh;
    padding: 24px;
}}

@keyframes fadeIn {{
    0% {{ opacity: 0; transform: translateY(10px); }}
    100% {{ opacity: 1; transform: translateY(0); }}
}}

.synergy-container {{
    max-width: 700px;
    margin: 0 auto;
}}

.synergy-header {{
    padding: 24px;
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    margin-bottom: 20px;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}}

.header-title {{
    font-size: 24px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 12px;
}}

.header-title::before {{
    content: "&#128279;";
    font-size: 28px;
}}

.type-coverage {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
}}

.type-mini {{
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    color: #fff;
}}

/* Type colors */
.type-normal {{ background: linear-gradient(135deg, #A8A878, #8a8a5c); }}
.type-fire {{ background: linear-gradient(135deg, #F08030, #c4682a); }}
.type-water {{ background: linear-gradient(135deg, #6890F0, #5070c0); }}
.type-electric {{ background: linear-gradient(135deg, #F8D030, #c4a828); }}
.type-grass {{ background: linear-gradient(135deg, #78C850, #5ca040); }}
.type-ice {{ background: linear-gradient(135deg, #98D8D8, #70b0b0); }}
.type-fighting {{ background: linear-gradient(135deg, #C03028, #901820); }}
.type-poison {{ background: linear-gradient(135deg, #A040A0, #803080); }}
.type-ground {{ background: linear-gradient(135deg, #E0C068, #b09048); }}
.type-flying {{ background: linear-gradient(135deg, #A890F0, #8070c0); }}
.type-psychic {{ background: linear-gradient(135deg, #F85888, #c04060); }}
.type-bug {{ background: linear-gradient(135deg, #A8B820, #889010); }}
.type-rock {{ background: linear-gradient(135deg, #B8A038, #907820); }}
.type-ghost {{ background: linear-gradient(135deg, #705898, #504070); }}
.type-dragon {{ background: linear-gradient(135deg, #7038F8, #5028c0); }}
.type-dark {{ background: linear-gradient(135deg, #705848, #503830); }}
.type-steel {{ background: linear-gradient(135deg, #B8B8D0, #9090a8); }}
.type-fairy {{ background: linear-gradient(135deg, #EE99AC, #c07088); }}

.synergy-card {{
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    overflow: hidden;
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
}}

.synergy-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    animation: fadeIn 0.4s ease backwards;
}}

.synergy-row:last-child {{
    border-bottom: none;
}}

.synergy-label {{
    display: flex;
    align-items: center;
    gap: 10px;
    font-size: 14px;
    font-weight: 600;
    color: var(--synergy-color, #e4e4e7);
}}

.synergy-icon {{
    font-size: 20px;
}}

.synergy-pokemon {{
    display: flex;
    gap: 4px;
}}

.synergy-sprite {{
    width: 40px;
    height: 40px;
    image-rendering: auto;
    filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.3));
    transition: transform 0.2s ease;
    cursor: pointer;
}}

.synergy-sprite:hover {{
    transform: scale(1.15);
}}

.empty-synergy {{
    text-align: center;
    padding: 40px 20px;
    color: #52525b;
    font-size: 14px;
}}
    </style>
</head>
<body>
    <div class="synergy-container">
        <div class="synergy-header">
            <div class="header-title">Team Synergy</div>
            <div class="type-coverage">
                {type_coverage_html if type_coverage_html else '<span style="color: #52525b;">No types found</span>'}
            </div>
        </div>

        <div class="synergy-card">
            {synergy_rows if synergy_rows else '<div class="empty-synergy">No synergies detected. Add Pokemon with weather abilities, terrains, Tailwind, etc.</div>'}
        </div>
    </div>
</body>
</html>"""


def create_battle_preview_ui(
    your_leads: list[dict[str, Any]],
    opponent_leads: list[dict[str, Any]],
    turn_preview: Optional[list[dict[str, Any]]] = None,
) -> str:
    """Create battle preview UI HTML showing lead matchup.

    Args:
        your_leads: List of your lead Pokemon dicts (2 Pokemon)
        opponent_leads: List of opponent lead Pokemon dicts (2 Pokemon)
        turn_preview: Optional list of predicted actions/outcomes

    Returns:
        HTML string for the battle preview UI
    """
    # Build your side
    your_html = ""
    for i, pokemon in enumerate(your_leads[:2]):
        name = pokemon.get("name", "Unknown")
        types = pokemon.get("types", [])
        item = pokemon.get("item", "")
        delay = i * 0.1

        type_badges = "".join(
            f'<span class="preview-type type-{t.lower()}">{t[:3]}</span>'
            for t in types
        )

        your_html += f"""
        <div class="preview-pokemon your-side" style="animation-delay: {delay}s;">
            {get_sprite_html(name, size=56, css_class="preview-sprite")}
            <div class="preview-name">{name}</div>
            <div class="preview-types">{type_badges}</div>
            {f'<div class="preview-item">@ {item}</div>' if item else ''}
        </div>
        """

    # Build opponent side
    opp_html = ""
    for i, pokemon in enumerate(opponent_leads[:2]):
        name = pokemon.get("name", "Unknown")
        types = pokemon.get("types", [])
        delay = i * 0.1 + 0.2

        type_badges = "".join(
            f'<span class="preview-type type-{t.lower()}">{t[:3]}</span>'
            for t in types
        )

        opp_html += f"""
        <div class="preview-pokemon opp-side" style="animation-delay: {delay}s;">
            {get_sprite_html(name, size=56, css_class="preview-sprite")}
            <div class="preview-name">{name}</div>
            <div class="preview-types">{type_badges}</div>
        </div>
        """

    # Build turn preview if provided
    turn_html = ""
    if turn_preview:
        for action in turn_preview[:4]:
            actor = action.get("actor", "")
            move = action.get("move", "")
            target = action.get("target", "")
            result = action.get("result", "")

            turn_html += f"""
            <div class="turn-action">
                <span class="action-actor">{actor}</span>
                <span class="action-move">{move}</span>
                <span class="action-arrow">&#10140;</span>
                <span class="action-target">{target}</span>
                {f'<span class="action-result">{result}</span>' if result else ''}
            </div>
            """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
* {{
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}}

body {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%);
    color: #e4e4e7;
    line-height: 1.5;
    min-height: 100vh;
    padding: 24px;
}}

@keyframes slideInLeft {{
    0% {{ opacity: 0; transform: translateX(-30px); }}
    100% {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes slideInRight {{
    0% {{ opacity: 0; transform: translateX(30px); }}
    100% {{ opacity: 1; transform: translateX(0); }}
}}

@keyframes vsGlow {{
    0%, 100% {{ box-shadow: 0 0 20px rgba(239, 68, 68, 0.4); }}
    50% {{ box-shadow: 0 0 40px rgba(239, 68, 68, 0.6); }}
}}

.battle-container {{
    max-width: 800px;
    margin: 0 auto;
}}

.battle-header {{
    text-align: center;
    padding: 20px;
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 20px 20px 0 0;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-bottom: none;
}}

.battle-title {{
    font-size: 24px;
    font-weight: 700;
    color: #fff;
}}

.battle-field {{
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 40px;
    padding: 40px;
    background: linear-gradient(180deg, rgba(34, 197, 94, 0.05) 0%, rgba(59, 130, 246, 0.05) 100%);
    border: 1px solid rgba(255, 255, 255, 0.06);
    position: relative;
}}

.field-side {{
    display: flex;
    gap: 20px;
}}

.preview-pokemon {{
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(10px);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 16px;
    text-align: center;
    min-width: 120px;
}}

.your-side {{
    animation: slideInLeft 0.5s cubic-bezier(0.4, 0, 0.2, 1) backwards;
    border-color: rgba(96, 165, 250, 0.3);
}}

.opp-side {{
    animation: slideInRight 0.5s cubic-bezier(0.4, 0, 0.2, 1) backwards;
    border-color: rgba(248, 113, 113, 0.3);
}}

.preview-sprite {{
    width: 80px;
    height: 80px;
    image-rendering: auto;
    filter: drop-shadow(0 4px 8px rgba(0, 0, 0, 0.3));
}}

.opp-side .preview-sprite {{
    transform: scaleX(-1);
}}

.preview-name {{
    font-size: 14px;
    font-weight: 700;
    color: #fff;
    margin-top: 8px;
}}

.preview-types {{
    display: flex;
    justify-content: center;
    gap: 4px;
    margin-top: 6px;
}}

.preview-type {{
    padding: 2px 6px;
    border-radius: 4px;
    font-size: 9px;
    font-weight: 700;
    color: #fff;
}}

/* Type colors */
.type-normal {{ background: #A8A878; }}
.type-fire {{ background: #F08030; }}
.type-water {{ background: #6890F0; }}
.type-electric {{ background: #F8D030; }}
.type-grass {{ background: #78C850; }}
.type-ice {{ background: #98D8D8; }}
.type-fighting {{ background: #C03028; }}
.type-poison {{ background: #A040A0; }}
.type-ground {{ background: #E0C068; }}
.type-flying {{ background: #A890F0; }}
.type-psychic {{ background: #F85888; }}
.type-bug {{ background: #A8B820; }}
.type-rock {{ background: #B8A038; }}
.type-ghost {{ background: #705898; }}
.type-dragon {{ background: #7038F8; }}
.type-dark {{ background: #705848; }}
.type-steel {{ background: #B8B8D0; }}
.type-fairy {{ background: #EE99AC; }}

.preview-item {{
    font-size: 11px;
    color: #71717a;
    margin-top: 4px;
}}

.vs-badge {{
    position: absolute;
    left: 50%;
    top: 50%;
    transform: translate(-50%, -50%);
    width: 60px;
    height: 60px;
    background: linear-gradient(135deg, #ef4444, #dc2626);
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 18px;
    font-weight: 800;
    color: #fff;
    animation: vsGlow 2s ease-in-out infinite;
    z-index: 10;
}}

.turn-preview {{
    background: rgba(255, 255, 255, 0.02);
    border-radius: 0 0 20px 20px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-top: none;
    padding: 20px;
}}

.turn-title {{
    font-size: 12px;
    font-weight: 700;
    color: #52525b;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 12px;
}}

.turn-action {{
    display: flex;
    align-items: center;
    gap: 8px;
    padding: 8px 12px;
    background: rgba(255, 255, 255, 0.02);
    border-radius: 8px;
    margin-bottom: 8px;
    font-size: 13px;
}}

.action-actor {{
    font-weight: 600;
    color: #60a5fa;
}}

.action-move {{
    font-weight: 600;
    color: #e4e4e7;
}}

.action-arrow {{
    color: #6366f1;
}}

.action-target {{
    color: #f87171;
}}

.action-result {{
    margin-left: auto;
    font-size: 11px;
    color: #71717a;
    padding: 2px 8px;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
}}

.side-label {{
    font-size: 10px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    margin-bottom: 10px;
    text-align: center;
}}

.side-label.your {{ color: #60a5fa; }}
.side-label.opp {{ color: #f87171; }}
    </style>
</head>
<body>
    <div class="battle-container">
        <div class="battle-header">
            <div class="battle-title">Battle Preview</div>
        </div>

        <div class="battle-field">
            <div class="your-side-wrapper">
                <div class="side-label your">Your Leads</div>
                <div class="field-side">
                    {your_html}
                </div>
            </div>

            <div class="vs-badge">VS</div>

            <div class="opp-side-wrapper">
                <div class="side-label opp">Opponent</div>
                <div class="field-side">
                    {opp_html}
                </div>
            </div>
        </div>

        {f'<div class="turn-preview"><div class="turn-title">Predicted Turn 1</div>{turn_html}</div>' if turn_html else ''}
    </div>
</body>
</html>"""


def create_speed_histogram_ui(
    pokemon_name: str,
    pokemon_speed: int,
    target_pokemon: str,
    speed_distribution: list[dict[str, Any]],
    stats: Optional[dict[str, Any]] = None,
    base_speed: Optional[int] = None,
    nature: str = "Serious",
    speed_evs: int = 0,
) -> str:
    """Create a histogram-style speed distribution UI like Pikalytics.

    Shows speed distribution as vertical bars with your Pokemon's position highlighted.
    Includes interactive controls for Nature, Speed EVs, and modifiers (Tailwind, Scarf, Paralysis).

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat (initial calculated value)
        target_pokemon: The target Pokemon being analyzed
        speed_distribution: List of dicts with 'speed' and 'count' or 'usage' keys
        stats: Optional dict with 'median', 'mean', 'min', 'max', 'iqr_low', 'iqr_high'
        base_speed: Your Pokemon's base speed stat (for recalculation). If None, controls are hidden.
        nature: Your Pokemon's current nature (default "Serious")
        speed_evs: Your Pokemon's current Speed EVs (default 0)

    Returns:
        HTML string for the speed histogram UI
    """
    styles = get_shared_styles()

    # Calculate statistics if not provided
    speeds = [s.get("speed", 0) for s in speed_distribution]
    usages = [s.get("usage", s.get("count", 1)) for s in speed_distribution]

    if not stats:
        if speeds:
            sorted_speeds = sorted(speeds)
            stats = {
                "min": min(speeds),
                "max": max(speeds),
                "median": sorted_speeds[len(sorted_speeds) // 2],
                "mean": sum(speeds) / len(speeds),
            }
        else:
            stats = {"min": 0, "max": 200, "median": 100, "mean": 100}

    # Normalize for bar heights
    max_usage = max(usages) if usages else 1

    # Build histogram bars
    bars_html = ""
    speed_min = stats.get("min", min(speeds) if speeds else 50)
    speed_max = stats.get("max", max(speeds) if speeds else 150)
    speed_range = speed_max - speed_min if speed_max > speed_min else 1

    # Sort by speed for display
    sorted_dist = sorted(speed_distribution, key=lambda x: x.get("speed", 0))

    for entry in sorted_dist:
        speed = entry.get("speed", 0)
        usage = entry.get("usage", entry.get("count", 1))
        height_pct = (usage / max_usage) * 100 if max_usage > 0 else 0

        # Determine if this is the user's Pokemon speed range
        is_user_speed = abs(speed - pokemon_speed) <= 2
        bar_class = "user-bar" if is_user_speed else ""

        # Position along x-axis
        x_pos = ((speed - speed_min) / speed_range) * 100 if speed_range > 0 else 50

        bars_html += f"""
        <div class="histogram-bar {bar_class}"
             style="left: {x_pos}%; height: {height_pct}%;"
             title="{speed} Spe: {usage:.1f}% usage">
        </div>
        """

    # Add user's Pokemon marker
    user_x_pos = ((pokemon_speed - speed_min) / speed_range) * 100 if speed_range > 0 else 50
    user_x_pos = max(0, min(100, user_x_pos))

    # Calculate outspeed percentage
    outsped_count = sum(1 for s in speeds if pokemon_speed > s)
    outspeed_pct = (outsped_count / len(speeds) * 100) if speeds else 0

    # Determine result class
    if outspeed_pct >= 80:
        result_class = "excellent"
    elif outspeed_pct >= 50:
        result_class = "good"
    else:
        result_class = "poor"

    # Pre-build distribution JSON for JavaScript
    distribution_json = json.dumps([
        {"speed": s.get("speed", 0), "usage": s.get("usage", s.get("count", 1))}
        for s in speed_distribution
    ])

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {styles}

        .histogram-container {{
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: var(--space-lg);
            border: 1px solid var(--glass-border);
        }}

        .histogram-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: var(--space-lg);
        }}

        .histogram-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .histogram-subtitle {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 4px;
        }}

        .histogram-stats {{
            text-align: right;
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .histogram-stats .stat-row {{
            margin-bottom: 2px;
        }}

        .histogram-stats .stat-label {{
            color: var(--text-muted);
        }}

        .histogram-stats .stat-value {{
            color: var(--text-primary);
            font-weight: 600;
            font-family: 'SF Mono', monospace;
        }}

        .histogram-chart {{
            position: relative;
            height: 180px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-md);
            overflow: hidden;
        }}

        .histogram-bars {{
            position: absolute;
            bottom: 0;
            left: 0;
            right: 0;
            height: 100%;
            display: flex;
            align-items: flex-end;
            padding: 0 4px;
        }}

        .histogram-bar {{
            position: absolute;
            bottom: 0;
            width: 8px;
            min-height: 4px;
            background: linear-gradient(to top, #dc2626, #dc2626);
            border-radius: 2px 2px 0 0;
            transform: translateX(-50%);
            transition: all 0.2s ease;
        }}

        .histogram-bar:hover {{
            background: linear-gradient(to top, #ef4444, #f87171);
            transform: translateX(-50%) scaleY(1.05);
        }}

        .histogram-bar.user-bar {{
            background: linear-gradient(to top, #22c55e, #4ade80);
            box-shadow: 0 0 10px rgba(34, 197, 94, 0.5);
        }}

        .user-marker {{
            position: absolute;
            bottom: -30px;
            left: {user_x_pos}%;
            transform: translateX(-50%);
            text-align: center;
            z-index: 10;
        }}

        .user-marker-line {{
            position: absolute;
            bottom: 0;
            left: {user_x_pos}%;
            width: 2px;
            height: 100%;
            background: linear-gradient(to top, var(--accent-primary), transparent);
            transform: translateX(-50%);
        }}

        .user-marker-label {{
            background: var(--gradient-primary);
            color: white;
            padding: 4px 8px;
            border-radius: var(--radius-sm);
            font-size: 11px;
            font-weight: 600;
            white-space: nowrap;
            box-shadow: var(--glow-primary);
        }}

        .user-marker-speed {{
            font-size: 10px;
            color: var(--text-secondary);
            margin-top: 2px;
        }}

        .histogram-axis {{
            display: flex;
            justify-content: space-between;
            padding: 0 4px;
            font-size: 10px;
            color: var(--text-muted);
            margin-top: 40px;
        }}

        .outspeed-result {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: var(--space-md);
            padding: var(--space-md);
            background: var(--glass-bg);
            border-radius: var(--radius-md);
            margin-top: var(--space-md);
        }}

        .outspeed-percent {{
            font-size: 28px;
            font-weight: 700;
        }}

        .outspeed-percent.excellent {{ color: var(--accent-success); }}
        .outspeed-percent.good {{ color: var(--accent-warning); }}
        .outspeed-percent.poor {{ color: var(--accent-danger); }}

        .outspeed-text {{
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .range-input {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            margin-top: var(--space-md);
            padding: var(--space-sm);
            background: var(--glass-bg);
            border-radius: var(--radius-md);
            font-size: 12px;
        }}

        .range-label {{
            color: var(--text-secondary);
        }}

        .range-value {{
            background: var(--bg-elevated);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            padding: 4px 8px;
            color: var(--text-primary);
            font-family: 'SF Mono', monospace;
            width: 50px;
            text-align: center;
        }}

        .tier-zone {{
            position: absolute;
            top: 0;
            height: 100%;
            opacity: 0.1;
        }}

        .tier-zone.slow {{ background: #ef4444; left: 0; width: 33%; }}
        .tier-zone.medium {{ background: #f59e0b; left: 33%; width: 34%; }}
        .tier-zone.fast {{ background: #22c55e; left: 67%; width: 33%; }}

        /* Speed Controls Section */
        .speed-controls {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            margin-bottom: var(--space-lg);
        }}

        .speed-controls-title {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--accent-primary);
            margin-bottom: var(--space-md);
        }}

        .controls-row {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            margin-bottom: var(--space-sm);
            flex-wrap: wrap;
        }}

        .control-group {{
            display: flex;
            align-items: center;
            gap: var(--space-xs);
        }}

        .control-label {{
            font-size: 11px;
            color: var(--text-secondary);
            font-weight: 600;
        }}

        .nature-select {{
            padding: 6px 10px;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            background: var(--bg-elevated);
            color: var(--text-primary);
            font-size: 12px;
            cursor: pointer;
        }}

        .nature-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }}

        .ev-slider {{
            width: 120px;
            -webkit-appearance: none;
            height: 6px;
            border-radius: 3px;
            background: rgba(255, 255, 255, 0.1);
        }}

        .ev-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: var(--gradient-primary);
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(99, 102, 241, 0.4);
        }}

        .ev-value {{
            font-family: 'SF Mono', monospace;
            font-size: 12px;
            font-weight: 700;
            color: var(--text-primary);
            min-width: 30px;
        }}

        .final-speed {{
            background: var(--gradient-primary);
            color: white;
            padding: 6px 12px;
            border-radius: var(--radius-sm);
            font-size: 14px;
            font-weight: 700;
            margin-left: auto;
        }}

        .modifier-toggles {{
            display: flex;
            gap: var(--space-xs);
            margin-top: var(--space-sm);
        }}

        .modifier-btn {{
            padding: 6px 12px;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            background: var(--bg-elevated);
            color: var(--text-secondary);
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .modifier-btn:hover {{
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.15);
        }}

        .modifier-btn.active {{
            background: var(--accent-primary);
            border-color: var(--accent-primary);
            color: white;
        }}

        .modifier-btn.active.tailwind {{
            background: #3b82f6;
            border-color: #3b82f6;
        }}

        .modifier-btn.active.scarf {{
            background: #f59e0b;
            border-color: #f59e0b;
        }}

        .modifier-btn.active.paralysis {{
            background: #eab308;
            border-color: #eab308;
            color: #1a1a2e;
        }}

        .base-speed-info {{
            font-size: 11px;
            color: var(--text-muted);
        }}
    </style>
</head>
<body>
    <div class="histogram-container">
        <div class="histogram-header">
            <div>
                <div class="histogram-title">Speed Distribution: {target_pokemon}</div>
                <div class="histogram-subtitle">Base {stats.get('base', 60)} Speed</div>
            </div>
            <div class="histogram-stats">
                <div class="stat-row"><span class="stat-label">Median:</span> <span class="stat-value">{stats.get('median', 0)}</span></div>
                <div class="stat-row"><span class="stat-label">IQR:</span> <span class="stat-value">{stats.get('iqr_low', 0)} - {stats.get('iqr_high', 0)}</span></div>
                <div class="stat-row"><span class="stat-label">Mean:</span> <span class="stat-value">{stats.get('mean', 0):.1f}</span></div>
            </div>
        </div>

        {"" if base_speed is None else f'''
        <div class="speed-controls">
            <div class="speed-controls-title">Your Speed Controls</div>
            <div class="controls-row">
                <div class="control-group">
                    <span class="control-label">Nature:</span>
                    <select id="nature-select" class="nature-select" onchange="updateSpeed()">
                        <optgroup label="+Speed Natures">
                            <option value="Timid" {"selected" if nature == "Timid" else ""}>Timid (+Spe, -Atk)</option>
                            <option value="Jolly" {"selected" if nature == "Jolly" else ""}>Jolly (+Spe, -SpA)</option>
                            <option value="Hasty" {"selected" if nature == "Hasty" else ""}>Hasty (+Spe, -Def)</option>
                            <option value="Naive" {"selected" if nature == "Naive" else ""}>Naive (+Spe, -SpD)</option>
                        </optgroup>
                        <optgroup label="-Speed Natures">
                            <option value="Brave" {"selected" if nature == "Brave" else ""}>Brave (+Atk, -Spe)</option>
                            <option value="Relaxed" {"selected" if nature == "Relaxed" else ""}>Relaxed (+Def, -Spe)</option>
                            <option value="Quiet" {"selected" if nature == "Quiet" else ""}>Quiet (+SpA, -Spe)</option>
                            <option value="Sassy" {"selected" if nature == "Sassy" else ""}>Sassy (+SpD, -Spe)</option>
                        </optgroup>
                        <optgroup label="Neutral Natures">
                            <option value="Hardy" {"selected" if nature == "Hardy" else ""}>Hardy</option>
                            <option value="Docile" {"selected" if nature == "Docile" else ""}>Docile</option>
                            <option value="Serious" {"selected" if nature == "Serious" else ""}>Serious</option>
                            <option value="Bashful" {"selected" if nature == "Bashful" else ""}>Bashful</option>
                            <option value="Quirky" {"selected" if nature == "Quirky" else ""}>Quirky</option>
                            <option value="Adamant" {"selected" if nature == "Adamant" else ""}>Adamant (+Atk, -SpA)</option>
                            <option value="Naughty" {"selected" if nature == "Naughty" else ""}>Naughty (+Atk, -SpD)</option>
                            <option value="Lonely" {"selected" if nature == "Lonely" else ""}>Lonely (+Atk, -Def)</option>
                            <option value="Bold" {"selected" if nature == "Bold" else ""}>Bold (+Def, -Atk)</option>
                            <option value="Impish" {"selected" if nature == "Impish" else ""}>Impish (+Def, -SpA)</option>
                            <option value="Lax" {"selected" if nature == "Lax" else ""}>Lax (+Def, -SpD)</option>
                            <option value="Modest" {"selected" if nature == "Modest" else ""}>Modest (+SpA, -Atk)</option>
                            <option value="Mild" {"selected" if nature == "Mild" else ""}>Mild (+SpA, -Def)</option>
                            <option value="Rash" {"selected" if nature == "Rash" else ""}>Rash (+SpA, -SpD)</option>
                            <option value="Calm" {"selected" if nature == "Calm" else ""}>Calm (+SpD, -Atk)</option>
                            <option value="Gentle" {"selected" if nature == "Gentle" else ""}>Gentle (+SpD, -Def)</option>
                            <option value="Careful" {"selected" if nature == "Careful" else ""}>Careful (+SpD, -SpA)</option>
                        </optgroup>
                    </select>
                </div>
                <div class="control-group">
                    <span class="control-label">Speed EVs:</span>
                    <input type="range" id="speed-evs" class="ev-slider" min="0" max="252" step="4" value="{speed_evs}" oninput="updateSpeed()">
                    <span id="ev-display" class="ev-value">{speed_evs}</span>
                </div>
                <div class="control-group">
                    <span class="base-speed-info">Base: {base_speed}</span>
                </div>
                <div class="final-speed">
                    <span id="final-speed">{pokemon_speed}</span> Spe
                </div>
            </div>
            <div class="modifier-toggles">
                <button id="tailwind-btn" class="modifier-btn tailwind" onclick="toggleModifier(this, &apos;tailwind&apos;)">Tailwind (2x)</button>
                <button id="scarf-btn" class="modifier-btn scarf" onclick="toggleModifier(this, &apos;scarf&apos;)">Choice Scarf (1.5x)</button>
                <button id="paralysis-btn" class="modifier-btn paralysis" onclick="toggleModifier(this, &apos;paralysis&apos;)">Paralysis (0.5x)</button>
            </div>
        </div>
        '''}

        <div class="histogram-chart">
            <div class="tier-zone slow"></div>
            <div class="tier-zone medium"></div>
            <div class="tier-zone fast"></div>
            <div id="user-marker-line" class="user-marker-line" style="left: {user_x_pos}%;"></div>
            <div class="histogram-bars">
                {bars_html}
            </div>
        </div>

        <div class="histogram-axis">
            <span>{speed_min}</span>
            <span>{(speed_min + speed_max) // 2}</span>
            <span>{speed_max}</span>
        </div>

        <div id="user-marker" class="user-marker" style="left: {user_x_pos}%;">
            <div class="user-marker-label">{pokemon_name}</div>
            <div id="user-marker-speed" class="user-marker-speed">{pokemon_speed} Spe</div>
        </div>

        <div class="outspeed-result">
            <div id="outspeed-percent" class="outspeed-percent {result_class}">{outspeed_pct:.1f}%</div>
            <div id="outspeed-text" class="outspeed-text">
                <strong>{pokemon_name}</strong> outspeeds <span id="outspeed-count">{outspeed_pct:.0f}</span>% of {target_pokemon} spreads
            </div>
        </div>

        <div class="range-input">
            <span class="range-label">Range:</span>
            <input type="text" class="range-value" value="{speed_min}">
            <span>-</span>
            <input type="text" class="range-value" value="{speed_max}">
            <button class="btn" style="padding: 4px 8px; font-size: 11px;">Reset</button>
        </div>
    </div>

    {"" if base_speed is None else f'''
    <script>
        // Speed distribution data
        const DISTRIBUTION = {distribution_json};
        const TOTAL_USAGE = DISTRIBUTION.reduce((sum, e) => sum + e.usage, 0);
        const SPEED_MIN = {speed_min};
        const SPEED_MAX = {speed_max};
        const BASE_SPEED = {base_speed};

        // Nature speed modifiers
        const NATURE_MODS = {{
            "Timid": 1.1, "Jolly": 1.1, "Hasty": 1.1, "Naive": 1.1,
            "Brave": 0.9, "Relaxed": 0.9, "Quiet": 0.9, "Sassy": 0.9
        }};

        // Active modifiers
        let modifiers = {{ tailwind: false, scarf: false, paralysis: false }};

        // Calculate speed stat at level 50 (31 IVs assumed)
        function calcSpeed(base, evs, nature) {{
            const mod = NATURE_MODS[nature] || 1.0;
            const inner = Math.floor((2 * base + 31 + Math.floor(evs / 4)) * 50 / 100);
            return Math.floor((inner + 5) * mod);
        }}

        // Apply active modifiers
        function applyModifiers(speed) {{
            let finalSpeed = speed;
            if (modifiers.tailwind) finalSpeed *= 2;
            if (modifiers.scarf) finalSpeed *= 1.5;
            if (modifiers.paralysis) finalSpeed *= 0.5;
            return Math.floor(finalSpeed);
        }}

        // Calculate outspeed percentage
        function calcOutspeedPct(mySpeed) {{
            let outsped = 0;
            for (const entry of DISTRIBUTION) {{
                if (mySpeed > entry.speed) outsped += entry.usage;
            }}
            return TOTAL_USAGE > 0 ? (outsped / TOTAL_USAGE) * 100 : 0;
        }}

        // Toggle modifier button
        function toggleModifier(btn, mod) {{
            modifiers[mod] = !modifiers[mod];
            btn.classList.toggle("active", modifiers[mod]);
            updateSpeed();
        }}

        // Update UI on input change
        function updateSpeed() {{
            const evs = parseInt(document.getElementById("speed-evs").value) || 0;
            const nature = document.getElementById("nature-select").value;

            // Update EV display
            document.getElementById("ev-display").textContent = evs;

            // Calculate base speed (before modifiers)
            let speed = calcSpeed(BASE_SPEED, evs, nature);

            // Apply modifiers
            speed = applyModifiers(speed);

            // Update final speed display
            document.getElementById("final-speed").textContent = speed;

            // Update position marker
            const speedRange = SPEED_MAX - SPEED_MIN;
            let pct = speedRange > 0 ? ((speed - SPEED_MIN) / speedRange) * 100 : 50;
            pct = Math.max(0, Math.min(100, pct));

            document.getElementById("user-marker-line").style.left = pct + "%";
            document.getElementById("user-marker").style.left = pct + "%";
            document.getElementById("user-marker-speed").textContent = speed + " Spe";

            // Update outspeed percentage
            const outspeedPct = calcOutspeedPct(speed);
            const outspeedEl = document.getElementById("outspeed-percent");
            outspeedEl.textContent = outspeedPct.toFixed(1) + "%";

            // Update result class
            outspeedEl.classList.remove("excellent", "good", "poor");
            if (outspeedPct >= 80) outspeedEl.classList.add("excellent");
            else if (outspeedPct >= 50) outspeedEl.classList.add("good");
            else outspeedEl.classList.add("poor");

            document.getElementById("outspeed-count").textContent = Math.round(outspeedPct);
        }}
    </script>
    '''}
</body>
</html>"""


def create_interactive_speed_histogram_ui(
    pokemon_name: str,
    pokemon_speed: int,
    initial_target: str,
    all_targets_data: dict[str, dict[str, Any]],
) -> str:
    """Create an interactive histogram with a dropdown to switch between target Pokemon.

    Pre-loads speed distribution data for multiple Pokemon so the dropdown can
    switch between them client-side without needing additional API calls.

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat
        initial_target: The initially selected target Pokemon
        all_targets_data: Dict mapping Pokemon names to their data:
            {
                "Pokemon Name": {
                    "base_speed": int,
                    "distribution": [{"speed": int, "usage": float}, ...],
                    "stats": {"min": int, "max": int, "median": int, "mean": float}
                },
                ...
            }

    Returns:
        HTML string for the interactive speed histogram UI
    """
    styles = get_shared_styles()
    targets_json = json.dumps(all_targets_data)
    initial_data = all_targets_data.get(initial_target, {})
    initial_dist = initial_data.get("distribution", [])
    initial_stats = initial_data.get("stats", {})
    initial_base = initial_data.get("base_speed", 100)
    speeds = [s.get("speed", 0) for s in initial_dist]
    usages = [s.get("usage", s.get("count", 1)) for s in initial_dist]
    if not initial_stats and speeds:
        sorted_speeds = sorted(speeds)
        initial_stats = {
            "min": min(speeds), "max": max(speeds),
            "median": sorted_speeds[len(sorted_speeds) // 2],
            "mean": sum(speeds) / len(speeds) if speeds else 0,
        }
    speed_min = initial_stats.get("min", 50)
    speed_max = initial_stats.get("max", 200)
    speed_range = speed_max - speed_min if speed_max > speed_min else 1
    max_usage = max(usages) if usages else 1
    bars_html = ""
    sorted_dist = sorted(initial_dist, key=lambda x: x.get("speed", 0))
    for entry in sorted_dist:
        speed = entry.get("speed", 0)
        usage = entry.get("usage", entry.get("count", 1))
        height_pct = (usage / max_usage) * 100 if max_usage > 0 else 0
        is_user_speed = abs(speed - pokemon_speed) <= 2
        bar_class = "user-bar" if is_user_speed else ""
        x_pos = ((speed - speed_min) / speed_range) * 100 if speed_range > 0 else 50
        bars_html += f'<div class="histogram-bar {bar_class}" style="left: {x_pos}%; height: {height_pct}%;" title="{speed} Spe: {usage:.1f}% usage"></div>'
    user_x_pos = ((pokemon_speed - speed_min) / speed_range) * 100 if speed_range > 0 else 50
    user_x_pos = max(0, min(100, user_x_pos))
    outsped_usage = sum(u for s, u in zip(speeds, usages) if pokemon_speed > s)
    total_usage = sum(usages) if usages else 1
    outspeed_pct = (outsped_usage / total_usage * 100) if total_usage > 0 else 0
    result_class = "excellent" if outspeed_pct >= 80 else "good" if outspeed_pct >= 50 else "poor"
    dropdown_options = "".join(
        f'<option value="{n}" {"selected" if n == initial_target else ""}>{n.replace("-", " ").title()}</option>'
        for n in sorted(all_targets_data.keys())
    )
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><style>{styles}
.histogram-container{{background:var(--bg-card);border-radius:var(--radius-lg);padding:var(--space-lg);border:1px solid var(--glass-border)}}
.histogram-header{{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--space-lg)}}
.histogram-title{{font-size:16px;font-weight:600;color:var(--text-primary)}}
.histogram-subtitle{{font-size:12px;color:var(--text-secondary);margin-top:4px}}
.histogram-stats{{text-align:right;font-size:12px;color:var(--text-secondary)}}
.histogram-stats .stat-row{{margin-bottom:2px}}
.histogram-stats .stat-label{{color:var(--text-muted)}}
.histogram-stats .stat-value{{color:var(--text-primary);font-weight:600;font-family:'SF Mono',monospace}}
.histogram-chart{{position:relative;height:180px;background:rgba(255,255,255,0.02);border-radius:var(--radius-md);margin-bottom:var(--space-md);overflow:hidden}}
.histogram-bars{{position:absolute;bottom:0;left:0;right:0;height:100%;padding:0 4px}}
.histogram-bar{{position:absolute;bottom:0;width:8px;min-height:4px;background:linear-gradient(to top,#dc2626,#dc2626);border-radius:2px 2px 0 0;transform:translateX(-50%);transition:all 0.3s ease}}
.histogram-bar:hover{{background:linear-gradient(to top,#ef4444,#f87171);transform:translateX(-50%) scaleY(1.05)}}
.histogram-bar.user-bar{{background:linear-gradient(to top,#22c55e,#4ade80);box-shadow:0 0 10px rgba(34,197,94,0.5)}}
.user-marker{{position:absolute;bottom:-30px;text-align:center;z-index:10;transition:left 0.3s ease}}
.user-marker-line{{position:absolute;bottom:0;width:2px;height:100%;background:linear-gradient(to top,var(--accent-primary),transparent);transform:translateX(-50%);transition:left 0.3s ease}}
.user-marker-label{{background:var(--gradient-primary);color:white;padding:4px 8px;border-radius:var(--radius-sm);font-size:11px;font-weight:600;white-space:nowrap;box-shadow:var(--glow-primary)}}
.user-marker-speed{{font-size:10px;color:var(--text-secondary);margin-top:2px}}
.histogram-axis{{display:flex;justify-content:space-between;padding:0 4px;font-size:10px;color:var(--text-muted);margin-top:40px}}
.outspeed-result{{display:flex;align-items:center;justify-content:center;gap:var(--space-md);padding:var(--space-md);background:var(--glass-bg);border-radius:var(--radius-md);margin-top:var(--space-md)}}
.outspeed-percent{{font-size:28px;font-weight:700;transition:color 0.3s ease}}
.outspeed-percent.excellent{{color:var(--accent-success)}}.outspeed-percent.good{{color:var(--accent-warning)}}.outspeed-percent.poor{{color:var(--accent-danger)}}
.outspeed-text{{font-size:13px;color:var(--text-secondary)}}
.pokemon-selector{{display:flex;align-items:center;gap:var(--space-sm);margin-top:var(--space-md);padding:var(--space-sm) var(--space-md);background:var(--glass-bg);border-radius:var(--radius-md);font-size:12px}}
.selector-label{{color:var(--text-secondary)}}
.pokemon-dropdown{{background:var(--bg-elevated);border:1px solid var(--glass-border);border-radius:var(--radius-sm);padding:6px 12px;color:var(--text-primary);font-size:13px;cursor:pointer;transition:border-color var(--duration-fast);min-width:180px}}
.pokemon-dropdown:hover,.pokemon-dropdown:focus{{border-color:var(--accent-primary);outline:none}}
.tier-zone{{position:absolute;top:0;height:100%;opacity:0.1}}
.tier-zone.slow{{background:#ef4444;left:0;width:33%}}.tier-zone.medium{{background:#f59e0b;left:33%;width:34%}}.tier-zone.fast{{background:#22c55e;left:67%;width:33%}}
.loading-overlay{{position:absolute;top:0;left:0;right:0;bottom:0;background:rgba(10,10,26,0.8);display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity 0.2s ease}}
.loading-overlay.active{{opacity:1;pointer-events:auto}}
.loading-spinner{{width:24px;height:24px;border:3px solid var(--glass-border);border-top-color:var(--accent-primary);border-radius:50%;animation:spin 0.8s linear infinite}}
@keyframes spin{{to{{transform:rotate(360deg)}}}}
</style></head><body>
<div class="histogram-container">
<div class="histogram-header"><div>
<div class="histogram-title" id="histogram-title">Speed Distribution: {initial_target.replace("-", " ").title()}</div>
<div class="histogram-subtitle" id="histogram-subtitle">Base {initial_base} Speed</div>
</div><div class="histogram-stats">
<div class="stat-row"><span class="stat-label">Median:</span> <span class="stat-value" id="stat-median">{initial_stats.get('median', 0)}</span></div>
<div class="stat-row"><span class="stat-label">IQR:</span> <span class="stat-value" id="stat-iqr">{initial_stats.get('iqr_low', speed_min)} - {initial_stats.get('iqr_high', speed_max)}</span></div>
<div class="stat-row"><span class="stat-label">Mean:</span> <span class="stat-value" id="stat-mean">{initial_stats.get('mean', 0):.1f}</span></div>
</div></div>
<div class="histogram-chart" id="histogram-chart">
<div class="tier-zone slow"></div><div class="tier-zone medium"></div><div class="tier-zone fast"></div>
<div class="user-marker-line" id="user-marker-line" style="left:{user_x_pos}%"></div>
<div class="histogram-bars" id="histogram-bars">{bars_html}</div>
<div class="loading-overlay" id="loading-overlay"><div class="loading-spinner"></div></div>
</div>
<div class="histogram-axis"><span id="axis-min">{speed_min}</span><span id="axis-mid">{(speed_min + speed_max) // 2}</span><span id="axis-max">{speed_max}</span></div>
<div class="user-marker" id="user-marker" style="left:{user_x_pos}%;transform:translateX(-50%)">
<div class="user-marker-label">{pokemon_name}</div><div class="user-marker-speed">{pokemon_speed} Spe</div>
</div>
<div class="outspeed-result">
<div class="outspeed-percent {result_class}" id="outspeed-percent">{outspeed_pct:.1f}%</div>
<div class="outspeed-text" id="outspeed-text"><strong>{pokemon_name}</strong> outspeeds {outspeed_pct:.0f}% of <span id="target-name-display">{initial_target.replace("-", " ").title()}</span> spreads</div>
</div>
<div class="pokemon-selector"><span class="selector-label">Compare to:</span>
<select class="pokemon-dropdown" id="pokemon-dropdown" onchange="updateHistogram(this.value)">{dropdown_options}</select>
</div></div>
<script>
const allTargetsData={targets_json};
const userPokemonName="{pokemon_name}";
const userPokemonSpeed={pokemon_speed};
function updateHistogram(targetName){{const data=allTargetsData[targetName];if(!data)return;
document.getElementById('loading-overlay').classList.add('active');
setTimeout(()=>{{const distribution=data.distribution||[];const stats=data.stats||{{}};const baseSpeed=data.base_speed||100;
const displayName=targetName.split('-').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');
document.getElementById('histogram-title').textContent='Speed Distribution: '+displayName;
document.getElementById('histogram-subtitle').textContent='Base '+baseSpeed+' Speed';
document.getElementById('target-name-display').textContent=displayName;
const speeds=distribution.map(s=>s.speed||0);const usages=distribution.map(s=>s.usage||s.count||1);
let speedMin=stats.min,speedMax=stats.max,median=stats.median,mean=stats.mean,iqrLow=stats.iqr_low,iqrHigh=stats.iqr_high;
if(speeds.length>0){{if(speedMin===undefined)speedMin=Math.min(...speeds);if(speedMax===undefined)speedMax=Math.max(...speeds);
if(median===undefined){{const sorted=[...speeds].sort((a,b)=>a-b);median=sorted[Math.floor(sorted.length/2)];}}
if(mean===undefined)mean=speeds.reduce((a,b)=>a+b,0)/speeds.length;if(iqrLow===undefined)iqrLow=speedMin;if(iqrHigh===undefined)iqrHigh=speedMax;}}
else{{speedMin=speedMin||50;speedMax=speedMax||200;median=median||100;mean=mean||100;iqrLow=iqrLow||speedMin;iqrHigh=iqrHigh||speedMax;}}
document.getElementById('stat-median').textContent=median;
document.getElementById('stat-iqr').textContent=iqrLow+' - '+iqrHigh;
document.getElementById('stat-mean').textContent=mean.toFixed(1);
document.getElementById('axis-min').textContent=speedMin;
document.getElementById('axis-mid').textContent=Math.floor((speedMin+speedMax)/2);
document.getElementById('axis-max').textContent=speedMax;
const barsContainer=document.getElementById('histogram-bars');barsContainer.innerHTML='';
const speedRange=speedMax-speedMin||1;const maxUsage=Math.max(...usages,1);
const sortedDist=[...distribution].sort((a,b)=>(a.speed||0)-(b.speed||0));
sortedDist.forEach(entry=>{{const speed=entry.speed||0;const usage=entry.usage||entry.count||1;
const heightPct=(usage/maxUsage)*100;const isUserSpeed=Math.abs(speed-userPokemonSpeed)<=2;
const xPos=((speed-speedMin)/speedRange)*100;
const bar=document.createElement('div');bar.className='histogram-bar'+(isUserSpeed?' user-bar':'');
bar.style.left=xPos+'%';bar.style.height=heightPct+'%';bar.title=speed+' Spe: '+usage.toFixed(1)+'% usage';
barsContainer.appendChild(bar);}});
const userXPos=Math.max(0,Math.min(100,((userPokemonSpeed-speedMin)/speedRange)*100));
document.getElementById('user-marker').style.left=userXPos+'%';
document.getElementById('user-marker-line').style.left=userXPos+'%';
let outspeedUsage=0,totalUsage=0;
for(let i=0;i<speeds.length;i++){{totalUsage+=usages[i];if(userPokemonSpeed>speeds[i])outspeedUsage+=usages[i];}}
const outspeedPct=totalUsage>0?(outspeedUsage/totalUsage*100):0;
const outspeedEl=document.getElementById('outspeed-percent');
outspeedEl.textContent=outspeedPct.toFixed(1)+'%';
outspeedEl.className='outspeed-percent '+(outspeedPct>=80?'excellent':outspeedPct>=50?'good':'poor');
document.getElementById('outspeed-text').innerHTML='<strong>'+userPokemonName+'</strong> outspeeds '+Math.round(outspeedPct)+'% of <span id="target-name-display">'+displayName+'</span> spreads';
document.getElementById('loading-overlay').classList.remove('active');}},150);}}
console.log('Interactive Speed Histogram initialized with',Object.keys(allTargetsData).length,'targets');
</script></body></html>'''


def create_spread_cards_ui(
    pokemon_name: str,
    spreads: list[dict[str, Any]],
    show_count: int = 3,
    selected_index: Optional[int] = None,
) -> str:
    """Create spread selection cards UI showing multiple spreads.

    Args:
        pokemon_name: Pokemon name
        spreads: List of spread dicts with 'nature', 'evs', 'usage', 'item', 'ability'
        show_count: Number of spreads to show initially (default 3)
        selected_index: Index of currently selected spread (optional)

    Returns:
        HTML string for the spread cards UI
    """
    styles = get_shared_styles()

    # Build spread cards
    cards_html = ""
    for i, spread in enumerate(spreads[:show_count]):
        nature = spread.get("nature", "Serious")
        evs = spread.get("evs", {})
        usage = spread.get("usage", 0)
        item = spread.get("item", "")
        ability = spread.get("ability", "")

        # Format EVs
        ev_parts = []
        ev_order = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
        ev_labels = {"hp": "HP", "attack": "Atk", "defense": "Def",
                     "special_attack": "SpA", "special_defense": "SpD", "speed": "Spe"}

        for stat in ev_order:
            val = evs.get(stat, 0)
            if val > 0:
                ev_parts.append(f"{val} {ev_labels[stat]}")

        ev_str = " / ".join(ev_parts) if ev_parts else "No EVs"

        is_selected = i == selected_index
        selected_class = "selected" if is_selected else ""
        rank_emoji = ["&#129351;", "&#129352;", "&#129353;"][i] if i < 3 else f"#{i+1}"

        cards_html += f"""
        <div class="spread-card {selected_class}" data-index="{i}">
            <div class="spread-rank">{rank_emoji}</div>
            <div class="spread-content">
                <div class="spread-header">
                    <span class="spread-nature">{nature}</span>
                    <span class="spread-usage">{usage:.1f}%</span>
                </div>
                <div class="spread-evs">{ev_str}</div>
                <div class="spread-details">
                    {f'<span class="spread-item">@ {item}</span>' if item else ''}
                    {f'<span class="spread-ability">{ability}</span>' if ability else ''}
                </div>
            </div>
            <div class="spread-select">
                {'<span class="selected-check">&#10003;</span>' if is_selected else '<span class="select-btn">Select</span>'}
            </div>
        </div>
        """

    # Show more button if there are more spreads
    more_count = len(spreads) - show_count
    show_more_html = ""
    if more_count > 0:
        show_more_html = f"""
        <button class="show-more-btn" onclick="this.style.display='none'; document.querySelectorAll('.hidden-spread').forEach(el => el.style.display='flex');">
            Show {more_count} more spreads
        </button>
        """

        # Add hidden spreads
        for i, spread in enumerate(spreads[show_count:], start=show_count):
            nature = spread.get("nature", "Serious")
            evs = spread.get("evs", {})
            usage = spread.get("usage", 0)
            item = spread.get("item", "")
            ability = spread.get("ability", "")

            ev_parts = []
            for stat in ev_order:
                val = evs.get(stat, 0)
                if val > 0:
                    ev_parts.append(f"{val} {ev_labels[stat]}")
            ev_str = " / ".join(ev_parts) if ev_parts else "No EVs"

            is_selected = i == selected_index
            selected_class = "selected" if is_selected else ""

            cards_html += f"""
            <div class="spread-card hidden-spread {selected_class}" data-index="{i}" style="display: none;">
                <div class="spread-rank">#{i+1}</div>
                <div class="spread-content">
                    <div class="spread-header">
                        <span class="spread-nature">{nature}</span>
                        <span class="spread-usage">{usage:.1f}%</span>
                    </div>
                    <div class="spread-evs">{ev_str}</div>
                    <div class="spread-details">
                        {f'<span class="spread-item">@ {item}</span>' if item else ''}
                        {f'<span class="spread-ability">{ability}</span>' if ability else ''}
                    </div>
                </div>
                <div class="spread-select">
                    {'<span class="selected-check">&#10003;</span>' if is_selected else '<span class="select-btn">Select</span>'}
                </div>
            </div>
            """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {styles}

        .spreads-container {{
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: var(--space-lg);
            border: 1px solid var(--glass-border);
        }}

        .spreads-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-md);
        }}

        .spreads-title {{
            font-size: 16px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .spreads-count {{
            font-size: 12px;
            color: var(--text-secondary);
            background: var(--glass-bg);
            padding: 4px 8px;
            border-radius: var(--radius-full);
        }}

        .spread-card {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-md);
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-sm);
            cursor: pointer;
            transition: all var(--duration-fast) var(--ease-smooth);
        }}

        .spread-card:hover {{
            background: var(--glass-bg-hover);
            border-color: var(--glass-border-hover);
            transform: translateX(4px);
        }}

        .spread-card.selected {{
            background: rgba(99, 102, 241, 0.15);
            border-color: var(--accent-primary);
            box-shadow: var(--glow-primary);
        }}

        .spread-rank {{
            font-size: 20px;
            width: 36px;
            text-align: center;
        }}

        .spread-content {{
            flex: 1;
        }}

        .spread-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 4px;
        }}

        .spread-nature {{
            font-weight: 600;
            color: var(--text-primary);
        }}

        .spread-usage {{
            font-size: 12px;
            color: var(--accent-primary);
            font-weight: 600;
            background: rgba(99, 102, 241, 0.2);
            padding: 2px 8px;
            border-radius: var(--radius-full);
        }}

        .spread-evs {{
            font-size: 13px;
            color: var(--text-secondary);
            font-family: 'SF Mono', monospace;
            margin-bottom: 4px;
        }}

        .spread-details {{
            display: flex;
            gap: var(--space-sm);
            font-size: 11px;
        }}

        .spread-item {{
            color: var(--accent-warning);
        }}

        .spread-ability {{
            color: var(--accent-info);
        }}

        .spread-select {{
            width: 60px;
            text-align: center;
        }}

        .select-btn {{
            font-size: 11px;
            color: var(--text-muted);
            padding: 4px 8px;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            transition: all var(--duration-fast);
        }}

        .spread-card:hover .select-btn {{
            color: var(--accent-primary);
            border-color: var(--accent-primary);
        }}

        .selected-check {{
            font-size: 18px;
            color: var(--accent-success);
        }}

        .show-more-btn {{
            width: 100%;
            padding: var(--space-sm);
            background: var(--glass-bg);
            border: 1px dashed var(--glass-border);
            border-radius: var(--radius-md);
            color: var(--text-secondary);
            font-size: 13px;
            cursor: pointer;
            transition: all var(--duration-fast);
            margin-top: var(--space-sm);
        }}

        .show-more-btn:hover {{
            background: var(--glass-bg-hover);
            border-color: var(--accent-primary);
            color: var(--accent-primary);
        }}
    </style>
</head>
<body>
    <div class="spreads-container">
        <div class="spreads-header">
            <div class="spreads-title">Common Spreads: {pokemon_name}</div>
            <div class="spreads-count">{len(spreads)} spreads</div>
        </div>

        <div class="spreads-list">
            {cards_html}
        </div>

        {show_more_html}
    </div>
</body>
</html>"""


def create_pokemon_build_card_ui(
    pokemon_name: str,
    base_stats: dict,
    types: list[str],
    abilities: list[str],
    moves: list[str],
    items: Optional[list[str]] = None,
    initial_evs: Optional[dict] = None,
    initial_nature: str = "Adamant",
    initial_ability: Optional[str] = None,
    initial_item: Optional[str] = None,
    initial_tera: Optional[str] = None,
    initial_moves: Optional[list[str]] = None,
    usage_speed_tiers: Optional[list[dict]] = None,
) -> str:
    """Create an interactive Pokemon build editor card with EV sliders.

    Features:
    - Pokemon sprite and type display
    - EV sliders (0-252) for all 6 stats
    - Nature, ability, item, tera type selectors
    - Move selectors (4 slots)
    - Real-time stat calculation
    - Speed tier display showing how you compare to usage stats of this Pokemon

    Args:
        pokemon_name: Name of the Pokemon
        base_stats: Dict with hp, attack, defense, special_attack, special_defense, speed
        types: List of Pokemon types
        abilities: List of available abilities
        moves: List of available moves for this Pokemon
        items: List of common items (optional, uses defaults if not provided)
        initial_evs: Starting EV spread (optional)
        initial_nature: Starting nature (default: Adamant)
        initial_ability: Starting ability (optional, uses first)
        initial_item: Starting item (optional)
        initial_tera: Starting tera type (optional, uses first type)
        initial_moves: Starting moves (optional)
        usage_speed_tiers: List of speed tiers from usage data for THIS Pokemon
            Each entry: {speed: int, usage_pct: float, nature: str, evs: int}
            Shows how your build compares to common spreads of the same Pokemon

    Returns:
        Complete HTML string for the build card
    """
    from .design_system import DESIGN_TOKENS, ANIMATIONS, TYPE_COLORS

    # Default items if not provided
    if items is None:
        items = [
            "Life Orb", "Choice Band", "Choice Specs", "Choice Scarf",
            "Assault Vest", "Focus Sash", "Leftovers", "Sitrus Berry",
            "Clear Amulet", "Covert Cloak", "Safety Goggles", "Rocky Helmet",
            "Eviolite", "Light Clay", "Mystic Water", "Charcoal"
        ]

    # Default EVs
    if initial_evs is None:
        initial_evs = {"hp": 0, "attack": 0, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 0}

    # Default selections
    if initial_ability is None and abilities:
        initial_ability = abilities[0]
    if initial_tera is None and types:
        initial_tera = types[0]
    if initial_moves is None:
        initial_moves = moves[:4] if len(moves) >= 4 else moves + [""] * (4 - len(moves))

    # Generate sprite HTML
    sprite_html = get_sprite_html(pokemon_name, size=96)

    # Type badges
    type_badges = "".join([
        f'<span class="type-badge" style="background:{get_type_color(t)}">{t}</span>'
        for t in types
    ])

    # Nature options (all 25 natures with stat effects)
    natures = {
        "Hardy": (None, None), "Lonely": ("attack", "defense"), "Brave": ("attack", "speed"),
        "Adamant": ("attack", "special_attack"), "Naughty": ("attack", "special_defense"),
        "Bold": ("defense", "attack"), "Docile": (None, None), "Relaxed": ("defense", "speed"),
        "Impish": ("defense", "special_attack"), "Lax": ("defense", "special_defense"),
        "Timid": ("speed", "attack"), "Hasty": ("speed", "defense"), "Serious": (None, None),
        "Jolly": ("speed", "special_attack"), "Naive": ("speed", "special_defense"),
        "Modest": ("special_attack", "attack"), "Mild": ("special_attack", "defense"),
        "Quiet": ("special_attack", "speed"), "Bashful": (None, None), "Rash": ("special_attack", "special_defense"),
        "Calm": ("special_defense", "attack"), "Gentle": ("special_defense", "defense"),
        "Sassy": ("special_defense", "speed"), "Careful": ("special_defense", "special_attack"), "Quirky": (None, None),
    }

    nature_options = "".join([
        f'<option value="{n}" {"selected" if n == initial_nature else ""}>{n}</option>'
        for n in natures.keys()
    ])

    # Ability options
    ability_options = "".join([
        f'<option value="{a}" {"selected" if a == initial_ability else ""}>{a.replace("-", " ").title()}</option>'
        for a in abilities
    ])

    # Item options
    item_options = '<option value="">-- No Item --</option>' + "".join([
        f'<option value="{i}" {"selected" if i == initial_item else ""}>{i}</option>'
        for i in items
    ])

    # Tera type options (all 18 types)
    all_types = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting", "Poison",
                 "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"]
    tera_options = "".join([
        f'<option value="{t}" {"selected" if t == initial_tera else ""}>{t}</option>'
        for t in all_types
    ])

    # Move options
    move_options_html = '<option value="">-- Select Move --</option>' + "".join([
        f'<option value="{m}">{m.replace("-", " ").title()}</option>'
        for m in moves
    ])

    # Move selectors (4 slots)
    move_selectors = ""
    for i in range(4):
        selected_move = initial_moves[i] if i < len(initial_moves) else ""
        move_selectors += f'''
        <select class="move-select" id="move-{i}" onchange="updateBuild()">
            <option value="">-- Move {i+1} --</option>
            {"".join([f'<option value="{m}" {"selected" if m == selected_move else ""}>{m.replace("-", " ").title()}</option>' for m in moves])}
        </select>
        '''

    # EV slider rows
    stat_labels = ["HP", "Attack", "Defense", "Sp. Atk", "Sp. Def", "Speed"]
    stat_keys = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
    stat_colors = ["#22c55e", "#ef4444", "#3b82f6", "#a855f7", "#84cc16", "#f59e0b"]

    ev_rows = ""
    for i, (label, key, color) in enumerate(zip(stat_labels, stat_keys, stat_colors)):
        ev_val = initial_evs.get(key, 0)
        base_val = base_stats.get(key, 100)
        ev_rows += f'''
        <div class="ev-row">
            <div class="ev-label">{label}</div>
            <div class="ev-base">{base_val}</div>
            <input type="range" class="ev-slider" id="ev-{key}"
                   min="0" max="252" step="4" value="{ev_val}"
                   style="--slider-color: {color}"
                   oninput="document.getElementById('ev-val-{key}').textContent=this.value;updateEVs()">
            <div class="ev-value-container">
                <div class="ev-value" id="ev-val-{key}">{ev_val}</div>
                <span class="ev-warning" id="warn-{key}" style="display:none"></span>
            </div>
            <button class="ev-lock-btn" id="lock-{key}" onclick="toggleLock('{key}')" title="Lock this stat">
                <span class="lock-icon">&#128275;</span>
            </button>
            <div class="stat-final" id="stat-{key}">--</div>
        </div>
        '''

    # Speed tiers JSON for JavaScript (usage data for this Pokemon)
    import json
    speed_tiers_json = json.dumps(usage_speed_tiers or [])

    # Base stats JSON for JavaScript
    base_stats_json = json.dumps(base_stats)

    # Natures JSON for JavaScript
    natures_json = json.dumps({k: list(v) for k, v in natures.items()})

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{pokemon_name} Build Editor</title>
    <style>
        {DESIGN_TOKENS}
        {ANIMATIONS}

        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: var(--font-family);
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            padding: var(--space-md);
        }}

        .build-card {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg);
            max-width: 480px;
            margin: 0 auto;
            overflow: hidden;
            box-shadow: var(--shadow-lg);
            animation: fadeSlideIn 0.4s var(--ease-smooth);
        }}

        /* Header Section */
        .card-header {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-lg);
            background: linear-gradient(135deg, rgba(99, 102, 241, 0.1) 0%, rgba(139, 92, 246, 0.05) 100%);
            border-bottom: 1px solid var(--glass-border);
        }}

        .sprite-container {{
            flex-shrink: 0;
        }}

        .pokemon-sprite {{
            width: 96px;
            height: 96px;
            image-rendering: pixelated;
            filter: drop-shadow(0 4px 12px rgba(0, 0, 0, 0.4));
            transition: transform 0.3s var(--ease-bounce);
        }}

        .pokemon-sprite:hover {{
            transform: scale(1.1);
        }}

        .pokemon-info {{
            flex: 1;
        }}

        .pokemon-name {{
            font-size: var(--font-size-xl);
            font-weight: var(--font-weight-bold);
            margin-bottom: var(--space-xs);
        }}

        .type-badges {{
            display: flex;
            gap: var(--space-xs);
            margin-bottom: var(--space-sm);
        }}

        .type-badge {{
            padding: 2px 10px;
            border-radius: var(--radius-full);
            font-size: var(--font-size-xs);
            font-weight: var(--font-weight-medium);
            text-transform: uppercase;
            color: white;
            text-shadow: 0 1px 2px rgba(0,0,0,0.3);
        }}

        .tera-row {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}

        .tera-label {{
            font-size: var(--font-size-sm);
            color: var(--text-secondary);
        }}

        .tera-select {{
            background: var(--bg-elevated);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            padding: 4px 8px;
            font-size: var(--font-size-sm);
        }}

        /* Controls Section */
        .controls-section {{
            padding: var(--space-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .control-row {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: var(--space-md);
            margin-bottom: var(--space-sm);
        }}

        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .control-label {{
            font-size: var(--font-size-xs);
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}

        .control-select {{
            background: var(--bg-elevated);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            padding: 8px 12px;
            font-size: var(--font-size-sm);
            cursor: pointer;
            transition: border-color var(--duration-fast);
        }}

        .control-select:hover {{
            border-color: var(--accent-primary);
        }}

        .control-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }}

        /* EV Section */
        .ev-section {{
            padding: var(--space-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .ev-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-md);
        }}

        .ev-title {{
            font-size: var(--font-size-md);
            font-weight: var(--font-weight-medium);
        }}

        .ev-total {{
            font-size: var(--font-size-sm);
            padding: 4px 12px;
            background: var(--bg-elevated);
            border-radius: var(--radius-full);
            transition: all var(--duration-fast);
        }}

        .ev-total.over {{
            background: rgba(239, 68, 68, 0.2);
            color: var(--accent-danger);
        }}

        .ev-total.max {{
            background: rgba(34, 197, 94, 0.2);
            color: var(--accent-success);
        }}

        .ev-header-row {{
            display: grid;
            grid-template-columns: 70px 40px 1fr 70px 28px 60px;
            gap: var(--space-sm);
            margin-bottom: var(--space-xs);
            padding-bottom: var(--space-xs);
            border-bottom: 1px solid var(--glass-border);
        }}

        .ev-header {{
            font-size: 10px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            font-weight: 600;
        }}

        .ev-row {{
            display: grid;
            grid-template-columns: 70px 40px 1fr 70px 28px 60px;
            /* Label | Base | Slider | EVs+Warning | Lock | Final */
            align-items: center;
            gap: var(--space-sm);
            margin-bottom: var(--space-sm);
        }}

        .ev-label {{
            font-size: var(--font-size-sm);
            font-weight: var(--font-weight-medium);
        }}

        .ev-label.boosted {{
            color: var(--accent-success);
        }}

        .ev-label.lowered {{
            color: var(--accent-danger);
        }}

        .ev-base {{
            font-size: var(--font-size-xs);
            color: var(--text-muted);
            text-align: center;
        }}

        .ev-slider {{
            -webkit-appearance: none;
            appearance: none;
            width: 100%;
            height: 6px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-full);
            cursor: pointer;
        }}

        .ev-slider::-webkit-slider-thumb {{
            -webkit-appearance: none;
            appearance: none;
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: var(--slider-color, var(--accent-primary));
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
            transition: transform var(--duration-fast);
        }}

        .ev-slider::-webkit-slider-thumb:hover {{
            transform: scale(1.2);
        }}

        .ev-slider::-moz-range-thumb {{
            width: 18px;
            height: 18px;
            border-radius: 50%;
            background: var(--slider-color, var(--accent-primary));
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 6px rgba(0, 0, 0, 0.3);
        }}

        .ev-value {{
            font-family: var(--font-mono);
            font-size: 16px;
            font-weight: 700;
            text-align: center;
            color: #a78bfa;
            min-width: 50px;
        }}

        /* EV Value Container for warning badge */
        .ev-value-container {{
            display: flex;
            align-items: center;
            justify-content: center;
            min-width: 70px;
        }}

        /* Wasted EV Warning */
        .ev-value.wasted {{
            color: #ef4444 !important;
            animation: pulse-warning 1s ease-in-out infinite;
        }}

        @keyframes pulse-warning {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.6; }}
        }}

        .ev-warning {{
            font-size: 10px;
            color: #ef4444;
            background: rgba(239, 68, 68, 0.2);
            padding: 2px 4px;
            border-radius: 4px;
            margin-left: 4px;
            font-weight: 600;
        }}

        /* Nature Suggestion */
        .nature-suggestion {{
            margin-top: var(--space-sm);
            padding: var(--space-sm) var(--space-md);
            background: rgba(234, 179, 8, 0.1);
            border: 1px solid rgba(234, 179, 8, 0.3);
            border-radius: var(--radius-sm);
            font-size: 12px;
            color: #fbbf24;
        }}

        .stat-final {{
            font-family: var(--font-mono);
            font-size: 16px;
            font-weight: 700;
            text-align: right;
            color: #ffffff;
        }}

        /* Lock Button */
        .ev-lock-btn {{
            width: 24px;
            height: 24px;
            padding: 0;
            background: transparent;
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-sm);
            cursor: pointer;
            opacity: 0.5;
            transition: all var(--duration-fast);
            display: flex;
            align-items: center;
            justify-content: center;
        }}

        .ev-lock-btn:hover {{
            opacity: 0.8;
            border-color: rgba(255, 255, 255, 0.2);
        }}

        .ev-lock-btn.locked {{
            opacity: 1;
            background: rgba(99, 102, 241, 0.2);
            border-color: var(--accent-primary);
        }}

        .lock-icon {{
            font-size: 12px;
        }}

        .ev-slider:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
        }}

        /* Optimize Button */
        .ev-header-actions {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}

        .optimize-btn {{
            padding: 4px 12px;
            background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
            border: none;
            border-radius: var(--radius-sm);
            color: white;
            font-size: 12px;
            font-weight: 600;
            cursor: pointer;
            transition: all var(--duration-fast);
        }}

        .optimize-btn:hover {{
            transform: scale(1.05);
            box-shadow: 0 4px 12px rgba(99, 102, 241, 0.4);
        }}

        .optimize-btn:disabled {{
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
        }}

        /* Moves Section */
        .moves-section {{
            padding: var(--space-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .moves-title {{
            font-size: var(--font-size-md);
            font-weight: var(--font-weight-medium);
            margin-bottom: var(--space-sm);
        }}

        .moves-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: var(--space-sm);
        }}

        .move-select {{
            background: var(--bg-elevated);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
            padding: 8px 10px;
            font-size: var(--font-size-sm);
            cursor: pointer;
        }}

        .move-select:hover {{
            border-color: var(--accent-primary);
        }}

        /* Speed Tier Section - Redesigned */
        .speed-section {{
            padding: var(--space-lg);
            background: linear-gradient(180deg, rgba(99, 102, 241, 0.05) 0%, transparent 100%);
        }}

        .speed-section-title {{
            font-size: 16px;
            font-weight: var(--font-weight-bold);
            margin-bottom: var(--space-md);
            color: var(--text-primary);
        }}

        /* Header Stats Grid */
        .speed-header-stats {{
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: var(--space-sm);
            margin-bottom: var(--space-lg);
        }}

        .speed-stat-box {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            padding: var(--space-sm) var(--space-md);
            text-align: center;
        }}

        .speed-stat-box.highlight {{
            border-color: var(--accent-success);
            background: rgba(34, 197, 94, 0.1);
        }}

        .speed-stat-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}

        .speed-stat-value {{
            font-family: var(--font-mono);
            font-size: 24px;
            font-weight: var(--font-weight-bold);
            color: var(--accent-primary);
        }}

        .speed-stat-box.highlight .speed-stat-value {{
            color: var(--accent-success);
        }}

        /* Main Percentage Display */
        .speed-percentage-display {{
            text-align: center;
            margin-bottom: var(--space-lg);
            padding: var(--space-md);
            background: var(--glass-bg);
            border-radius: var(--radius-md);
        }}

        .speed-pct-large {{
            font-size: 42px;
            font-weight: var(--font-weight-bold);
            color: var(--accent-primary);
            line-height: 1;
        }}

        .speed-pct-label {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-top: var(--space-xs);
        }}

        /* Progress Bar */
        .speed-progress-container {{
            height: 12px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-full);
            overflow: hidden;
            margin-bottom: var(--space-lg);
            position: relative;
        }}

        .speed-progress-bar {{
            height: 100%;
            background: linear-gradient(90deg, var(--accent-success) 0%, var(--accent-primary) 100%);
            border-radius: var(--radius-full);
            transition: width 0.3s var(--ease-smooth);
        }}

        /* Speed Tier Table */
        .speed-tier-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 14px;
        }}

        .speed-tier-table th {{
            text-align: left;
            padding: 10px 12px;
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            border-bottom: 1px solid var(--glass-border);
            background: rgba(0, 0, 0, 0.2);
        }}

        .speed-tier-table th:last-child {{
            text-align: right;
        }}

        .speed-tier-table td {{
            padding: 12px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .speed-tier-table tr:last-child td {{
            border-bottom: none;
        }}

        .speed-tier-table .speed-col {{
            font-family: var(--font-mono);
            font-size: 18px;
            font-weight: var(--font-weight-bold);
        }}

        .speed-tier-table .nature-col {{
            color: var(--text-secondary);
            font-size: 14px;
        }}

        .speed-tier-table .usage-col {{
            color: var(--text-muted);
            font-size: 14px;
            text-align: center;
        }}

        .speed-tier-table .result-col {{
            text-align: right;
            font-weight: var(--font-weight-bold);
            font-size: 14px;
        }}

        .result-outspeed {{
            color: #22c55e;
        }}

        .result-tie {{
            color: #f59e0b;
        }}

        .result-outsped {{
            color: #ef4444;
        }}
    </style>
</head>
<body>
    <div class="build-card">
        <!-- Header -->
        <div class="card-header">
            <div class="sprite-container">
                {sprite_html}
            </div>
            <div class="pokemon-info">
                <div class="pokemon-name">{pokemon_name}</div>
                <div class="type-badges">{type_badges}</div>
                <div class="tera-row">
                    <span class="tera-label">Tera:</span>
                    <select class="tera-select" id="tera-type" onchange="updateBuild()">
                        {tera_options}
                    </select>
                </div>
            </div>
        </div>

        <!-- Controls -->
        <div class="controls-section">
            <div class="control-row">
                <div class="control-group">
                    <label class="control-label">Ability</label>
                    <select class="control-select" id="ability" onchange="updateBuild()">
                        {ability_options}
                    </select>
                </div>
                <div class="control-group">
                    <label class="control-label">Item</label>
                    <select class="control-select" id="item" onchange="updateBuild()">
                        {item_options}
                    </select>
                </div>
            </div>
            <div class="control-row">
                <div class="control-group">
                    <label class="control-label">Nature</label>
                    <select class="control-select" id="nature" onchange="updateNature()">
                        {nature_options}
                    </select>
                </div>
                <div class="control-group">
                    <label class="control-label">Total EVs</label>
                    <div class="ev-total" id="ev-total">0 / 508</div>
                </div>
            </div>
            <div class="nature-suggestion" id="nature-suggestion" style="display:none"></div>
        </div>

        <!-- EV Sliders -->
        <div class="ev-section">
            <div class="ev-header" style="display:flex;justify-content:space-between;align-items:center;padding:var(--space-sm) var(--space-md);border-bottom:1px solid var(--glass-border);">
                <span class="ev-title">EV Spread</span>
            </div>
            <div class="ev-header-row">
                <div class="ev-header">Stat</div>
                <div class="ev-header">Base</div>
                <div class="ev-header"></div>
                <div class="ev-header">EVs</div>
                <div class="ev-header"></div>
                <div class="ev-header">Final</div>
            </div>
            {ev_rows}
        </div>

        <!-- Moves -->
        <div class="moves-section">
            <div class="moves-title">Moves</div>
            <div class="moves-grid">
                {move_selectors}
            </div>
        </div>

        <!-- Speed Tier -->
        <div class="speed-section">
            <div class="speed-section-title">Speed Self-Comparison</div>

            <!-- Header Stats: Your Speed, Common Max, Common Min -->
            <div class="speed-header-stats">
                <div class="speed-stat-box highlight">
                    <div class="speed-stat-label">Your Speed</div>
                    <div class="speed-stat-value" id="speed-display">--</div>
                </div>
                <div class="speed-stat-box">
                    <div class="speed-stat-label">Common Max</div>
                    <div class="speed-stat-value" id="speed-max">--</div>
                </div>
                <div class="speed-stat-box">
                    <div class="speed-stat-label">Common Min</div>
                    <div class="speed-stat-value" id="speed-min">--</div>
                </div>
            </div>

            <!-- Main Percentage Display -->
            <div class="speed-percentage-display">
                <div class="speed-pct-large"><span id="speed-pct">~0</span>%</div>
                <div class="speed-pct-label">Faster than this % of {pokemon_name} builds (est.)</div>
            </div>

            <!-- Progress Bar -->
            <div class="speed-progress-container">
                <div class="speed-progress-bar" id="speed-bar" style="width: 0%"></div>
            </div>

            <!-- Speed Tier Table -->
            <table class="speed-tier-table" id="speed-tier-table">
                <thead>
                    <tr>
                        <th>Speed</th>
                        <th>Spread</th>
                        <th>Usage</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody id="speed-tier-tbody">
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const BASE_STATS = {base_stats_json};
        const NATURES = {natures_json};
        const SPEED_TIERS = {speed_tiers_json};

        const STAT_KEYS = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed'];
        const NATURE_STAT_MAP = {{
            'attack': 'attack',
            'defense': 'defense',
            'special_attack': 'special_attack',
            'special_defense': 'special_defense',
            'speed': 'speed'
        }};

        function calcStat(base, ev, iv, natureMod, isHP) {{
            iv = iv || 31;
            if (isHP) {{
                return Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 50 + 10;
            }}
            return Math.floor((Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 5) * natureMod);
        }}

        function getNatureMods(natureName) {{
            const nature = NATURES[natureName];
            const mods = {{}};
            STAT_KEYS.forEach(k => mods[k] = 1.0);
            if (nature && nature[0]) {{
                mods[nature[0]] = 1.1;
            }}
            if (nature && nature[1]) {{
                mods[nature[1]] = 0.9;
            }}
            return mods;
        }}

        // Valid EV breakpoints at Level 50: 0, 4, 12, 20, 28, ... 244, 252
        // Pattern: First point at 4 EVs, then +8 for each additional stat point
        const EV_BREAKPOINTS = [0, 4, 12, 20, 28, 36, 44, 52, 60, 68, 76, 84, 92, 100, 108, 116, 124, 132, 140, 148, 156, 164, 172, 180, 188, 196, 204, 212, 220, 228, 236, 244, 252];

        function isValidBreakpoint(evs) {{
            return EV_BREAKPOINTS.includes(evs);
        }}

        function getNearestBreakpoint(evs) {{
            // Find highest breakpoint <= evs
            for (let i = EV_BREAKPOINTS.length - 1; i >= 0; i--) {{
                if (EV_BREAKPOINTS[i] <= evs) {{
                    return EV_BREAKPOINTS[i];
                }}
            }}
            return 0;
        }}

        function getWastedEVs(evs) {{
            const nearest = getNearestBreakpoint(evs);
            return evs - nearest;  // How many EVs are wasted
        }}

        // Check if a +Speed nature could achieve same speed with fewer EVs
        function checkNatureOptimization(currentEVs, targetStat, currentNature) {{
            const base = BASE_STATS['speed'];
            const currentMods = getNatureMods(currentNature);

            // If already using +Speed nature, no optimization possible
            if (currentMods.speed === 1.1) return null;

            // Calculate what EVs would be needed with +Speed nature (1.1x)
            for (let testEV = 0; testEV <= 252; testEV += 4) {{
                const statWith110 = calcStat(base, testEV, 31, 1.1, false);
                if (statWith110 >= targetStat) {{
                    const evSaved = currentEVs - testEV;
                    if (evSaved >= 8) {{  // Only suggest if saving at least 8 EVs
                        return {{
                            suggestedNature: 'Jolly/Timid',
                            newEVs: testEV,
                            evSaved: evSaved,
                            sameSpeed: statWith110
                        }};
                    }}
                    break;
                }}
            }}
            return null;
        }}

        function updateNature() {{
            const nature = document.getElementById('nature').value;
            const [boosted, lowered] = NATURES[nature] || [null, null];

            // Update label colors
            STAT_KEYS.forEach(key => {{
                const label = document.querySelector(`#ev-${{key}}`).closest('.ev-row').querySelector('.ev-label');
                label.classList.remove('boosted', 'lowered');
                if (boosted === key) label.classList.add('boosted');
                if (lowered === key) label.classList.add('lowered');
            }});

            updateEVs();
        }}

        function updateEVs() {{
            // Calculate total EVs and check for wasted EVs
            let total = 0;
            const nature = document.getElementById('nature').value;
            const natureMods = getNatureMods(nature);

            STAT_KEYS.forEach(key => {{
                const val = parseInt(document.getElementById(`ev-${{key}}`).value) || 0;
                total += val;

                const evDisplay = document.getElementById(`ev-val-${{key}}`);
                evDisplay.textContent = val;

                // Check for wasted EVs at non-breakpoints
                const wasted = getWastedEVs(val);
                const warningEl = document.getElementById(`warn-${{key}}`);

                if (wasted > 0) {{
                    evDisplay.classList.add('wasted');
                    evDisplay.title = `Wasting ${{wasted}} EVs! Use ${{getNearestBreakpoint(val)}} instead.`;
                    if (warningEl) {{
                        warningEl.textContent = `-${{wasted}}`;
                        warningEl.style.display = 'inline-block';
                    }}
                }} else {{
                    evDisplay.classList.remove('wasted');
                    evDisplay.title = '';
                    if (warningEl) warningEl.style.display = 'none';
                }}
            }});

            // Update total display
            const totalEl = document.getElementById('ev-total');
            totalEl.textContent = `${{total}} / 508`;
            totalEl.classList.remove('over', 'max');
            if (total > 508) totalEl.classList.add('over');
            else if (total === 508) totalEl.classList.add('max');

            // Calculate final stats
            STAT_KEYS.forEach(key => {{
                const base = BASE_STATS[key] || 100;
                const ev = parseInt(document.getElementById(`ev-${{key}}`).value) || 0;
                const stat = calcStat(base, ev, 31, natureMods[key], key === 'hp');
                document.getElementById(`stat-${{key}}`).textContent = stat;
            }});

            updateSpeedTier();

            // Check nature optimization for speed
            const speedEVs = parseInt(document.getElementById('ev-speed').value) || 0;
            const speedStat = parseInt(document.getElementById('stat-speed').textContent) || 0;
            const suggestionEl = document.getElementById('nature-suggestion');

            if (suggestionEl) {{
                const optimization = checkNatureOptimization(speedEVs, speedStat, nature);
                if (optimization && speedEVs > 0) {{
                    suggestionEl.innerHTML = `&#128161; Use ${{optimization.suggestedNature}} nature with ${{optimization.newEVs}} Spe EVs to save ${{optimization.evSaved}} EVs`;
                    suggestionEl.style.display = 'block';
                }} else {{
                    suggestionEl.style.display = 'none';
                }}
            }}
        }}

        function updateSpeedTier() {{
            const speed = parseInt(document.getElementById('stat-speed').textContent) || 0;
            document.getElementById('speed-display').textContent = speed;

            if (SPEED_TIERS.length === 0) {{
                document.getElementById('speed-pct').textContent = '--';
                document.getElementById('speed-bar').style.width = '50%';
                document.getElementById('speed-max').textContent = '--';
                document.getElementById('speed-min').textContent = '--';
                document.getElementById('speed-tier-tbody').innerHTML = '<tr><td colspan="4" style="text-align:center;color:var(--text-muted);">No usage data available</td></tr>';
                return;
            }}

            // Sort tiers by speed (ascending for table, highest first in display)
            const sortedTiers = [...SPEED_TIERS].sort((a, b) => a.speed - b.speed);

            // Calculate min/max for header stats
            const minSpeed = sortedTiers[0].speed;
            const maxSpeed = sortedTiers[sortedTiers.length - 1].speed;
            document.getElementById('speed-min').textContent = minSpeed;
            document.getElementById('speed-max').textContent = maxSpeed;

            // Calculate cumulative percentages
            let cumulative = 0;
            const tiers = sortedTiers.map(t => {{
                cumulative += t.usage_pct || 1;
                return {{ ...t, cumPct: cumulative }};
            }});
            const total = cumulative;

            // Find bounds and interpolate for smooth progression
            let pct = 0;
            if (speed <= tiers[0].speed) {{
                pct = 0;  // Slower than or equal to slowest tier
            }} else if (speed > tiers[tiers.length - 1].speed) {{
                pct = 100;  // Faster than fastest tier
            }} else {{
                // Find lower and upper bounds
                let lower = {{ speed: tiers[0].speed, cumPct: 0 }};
                let upper = tiers[tiers.length - 1];

                for (let i = 0; i < tiers.length; i++) {{
                    if (tiers[i].speed < speed) {{
                        lower = tiers[i];
                    }} else {{
                        upper = tiers[i];
                        break;
                    }}
                }}

                // Interpolate between lower and upper bounds
                const lowerPct = (lower.cumPct / total) * 100;
                const upperPct = (upper.cumPct / total) * 100;
                const ratio = (speed - lower.speed) / (upper.speed - lower.speed);
                pct = lowerPct + ratio * (upperPct - lowerPct);
            }}

            document.getElementById('speed-pct').textContent = '~' + pct.toFixed(1);
            document.getElementById('speed-bar').style.width = pct + '%';

            // Build the speed tier table (sorted by speed descending for display)
            const tableRows = [...SPEED_TIERS]
                .sort((a, b) => b.speed - a.speed)  // Highest speed first
                .map(tier => {{
                    let result, resultClass;
                    if (speed > tier.speed) {{
                        result = 'Outspeed';
                        resultClass = 'result-outspeed';
                    }} else if (speed === tier.speed) {{
                        result = '= Tie';
                        resultClass = 'result-tie';
                    }} else {{
                        result = 'Outsped';
                        resultClass = 'result-outsped';
                    }}

                    const evDisplay = tier.evs !== undefined ? `${{tier.evs}} Spe` : '';
                    const natureDisplay = tier.nature || '';
                    const spreadDisplay = [natureDisplay, evDisplay].filter(Boolean).join(' ');
                    const usagePct = tier.usage_pct !== undefined ? tier.usage_pct.toFixed(1) + '%' : '--';

                    return `<tr>
                        <td class="speed-col">${{tier.speed}}</td>
                        <td class="nature-col">${{spreadDisplay || '--'}}</td>
                        <td class="usage-col">${{usagePct}}</td>
                        <td class="result-col ${{resultClass}}">${{result}}</td>
                    </tr>`;
                }})
                .join('');

            document.getElementById('speed-tier-tbody').innerHTML = tableRows;
        }}

        // Track locked stats for optimization
        const lockedStats = new Set();

        function toggleLock(statKey) {{
            const btn = document.getElementById(`lock-${{statKey}}`);
            const slider = document.getElementById(`ev-${{statKey}}`);

            if (lockedStats.has(statKey)) {{
                lockedStats.delete(statKey);
                btn.classList.remove('locked');
                btn.innerHTML = '<span class="lock-icon">&#128275;</span>';
                slider.disabled = false;
            }} else {{
                lockedStats.add(statKey);
                btn.classList.add('locked');
                btn.innerHTML = '<span class="lock-icon">&#128274;</span>';
                slider.disabled = true;
            }}
        }}

        function optimizeSpread() {{
            const nature = document.getElementById('nature').value;
            const natureMods = getNatureMods(nature);

            // Get locked EVs and calculate remaining
            let lockedTotal = 0;
            lockedStats.forEach(key => {{
                lockedTotal += parseInt(document.getElementById(`ev-${{key}}`).value) || 0;
            }});
            let remaining = 508 - lockedTotal;

            // Get unlocked stats
            const unlocked = STAT_KEYS.filter(k => !lockedStats.has(k));

            // Figure out which defensive stats to optimize (HP, Def, SpD)
            const bulkStats = unlocked.filter(k => ['hp', 'defense', 'special_defense'].includes(k));
            const otherUnlocked = unlocked.filter(k => !bulkStats.includes(k));

            // Reset unlocked non-bulk stats to 0
            otherUnlocked.forEach(key => {{
                setEV(key, 0);
            }});

            // Reset bulk stats to 0 before redistributing
            bulkStats.forEach(key => {{
                setEV(key, 0);
            }});

            // Distribute remaining EVs to bulk stats using diminishing returns optimization
            // Add 4 EVs where marginal gain is highest
            if (bulkStats.length > 0 && remaining > 0) {{
                while (remaining >= 4) {{
                    let bestStat = null;
                    let bestGain = -1;

                    bulkStats.forEach(stat => {{
                        const currentEV = parseInt(document.getElementById(`ev-${{stat}}`).value) || 0;
                        if (currentEV >= 252) return; // Already maxed

                        const base = BASE_STATS[stat] || 100;
                        const mod = natureMods[stat] || 1.0;

                        // Calculate marginal gain for adding 4 EVs
                        const currentStat = calcStat(base, currentEV, 31, mod, stat === 'hp');
                        const newStat = calcStat(base, currentEV + 4, 31, mod, stat === 'hp');
                        const gain = newStat - currentStat;

                        // Weight HP gains higher (benefits both physical and special bulk)
                        const weight = stat === 'hp' ? 2 : 1;
                        const weightedGain = gain * weight;

                        if (weightedGain > bestGain) {{
                            bestGain = weightedGain;
                            bestStat = stat;
                        }}
                    }});

                    if (bestStat === null) break; // All stats maxed

                    const currentEV = parseInt(document.getElementById(`ev-${{bestStat}}`).value) || 0;
                    setEV(bestStat, Math.min(252, currentEV + 4));
                    remaining -= 4;
                }}
            }}

            updateEVs();
        }}

        function setEV(statKey, value) {{
            const slider = document.getElementById(`ev-${{statKey}}`);
            const display = document.getElementById(`ev-val-${{statKey}}`);
            slider.value = value;
            display.textContent = value;
        }}

        function updateBuild() {{
            // Placeholder for future build export functionality
            console.log('Build updated');
        }}

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {{
            updateNature();
        }});

        // Initialize immediately as well
        updateNature();
    </script>
</body>
</html>'''


def create_pokepaste_team_grid_ui(
    pokemon_list: list[dict],
    team_name: Optional[str] = None,
    paste_url: Optional[str] = None,
) -> str:
    """Create a team grid UI from Pokepaste data with full build details."""
    # Nature stat modifiers
    NATURE_MODS = {
        "hardy": (None, None), "lonely": ("atk", "def"), "brave": ("atk", "spe"),
        "adamant": ("atk", "spa"), "naughty": ("atk", "spd"),
        "bold": ("def", "atk"), "docile": (None, None), "relaxed": ("def", "spe"),
        "impish": ("def", "spa"), "lax": ("def", "spd"),
        "timid": ("spe", "atk"), "hasty": ("spe", "def"), "serious": (None, None),
        "jolly": ("spe", "spa"), "naive": ("spe", "spd"),
        "modest": ("spa", "atk"), "mild": ("spa", "def"),
        "quiet": ("spa", "spe"), "bashful": (None, None), "rash": ("spa", "spd"),
        "calm": ("spd", "atk"), "gentle": ("spd", "def"),
        "sassy": ("spd", "spe"), "careful": ("spd", "spa"), "quirky": (None, None),
    }

    def calc_stat(base, iv, ev, level, nature_mod, is_hp):
        if is_hp:
            return int((2 * base + iv + ev // 4) * level / 100) + level + 10
        return int(((2 * base + iv + ev // 4) * level / 100 + 5) * nature_mod)

    def get_nature_mods_local(nature):
        mods = {"hp": 1.0, "atk": 1.0, "def": 1.0, "spa": 1.0, "spd": 1.0, "spe": 1.0}
        nature_data = NATURE_MODS.get(nature.lower(), (None, None))
        if nature_data[0]:
            mods[nature_data[0]] = 1.1
        if nature_data[1]:
            mods[nature_data[1]] = 0.9
        return mods

    STAT_COLORS = {
        "hp": "#ff5959", "atk": "#f5ac78", "def": "#fae078",
        "spa": "#9db7f5", "spd": "#a7db8d", "spe": "#fa92b2"
    }

    cards_html = ""
    for i, pokemon in enumerate(pokemon_list):
        species = pokemon.get("species", "Unknown")
        types = pokemon.get("types", [])
        item = pokemon.get("item", "")
        ability = pokemon.get("ability", "")
        nature = pokemon.get("nature", "Serious")
        evs = pokemon.get("evs", {})
        ivs = pokemon.get("ivs", {})
        moves = pokemon.get("moves", [])
        tera_type = pokemon.get("tera_type")
        level = pokemon.get("level", 50)
        base_stats = pokemon.get("base_stats", {})

        ev_total = sum(evs.get(s, 0) for s in ["hp", "atk", "def", "spa", "spd", "spe"])
        primary_type = types[0].lower() if types else "normal"

        type_badges = " ".join(
            f'<span class="type-badge type-{t.lower()}">{t.upper()}</span>'
            for t in types
        )

        tera_html = ""
        if tera_type:
            tera_color = get_type_color(tera_type)
            tera_html = f'<span class="tera-badge" style="--tera-color: {tera_color};"><span class="tera-icon">&#10022;</span> {tera_type}</span>'

        ev_cells = ""
        for stat, label in [("hp", "HP"), ("atk", "Atk"), ("def", "Def"), ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe")]:
            val = evs.get(stat, 0)
            color = STAT_COLORS.get(stat, "#888")
            ev_cells += f'<div class="ev-cell"><span class="ev-label">{label}</span><span class="ev-value" style="color: {color};">{val}</span></div>'

        iv_parts = []
        for stat, label in [("hp", "HP"), ("atk", "Atk"), ("def", "Def"), ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe")]:
            iv_val = ivs.get(stat, 31)
            if iv_val != 31:
                iv_parts.append(f"{iv_val} {label}")
        ivs_html = f'<div class="ivs-note">IVs: {", ".join(iv_parts)}</div>' if iv_parts else ""

        moves_html = ""
        for move in moves[:4]:
            if isinstance(move, dict):
                move_name = move.get("name", "Unknown")
                move_type = move.get("type", "normal")
            else:
                move_name = str(move)
                move_type = "normal"
            move_color = get_type_color(move_type)
            moves_html += f'<span class="move-pill" style="--move-color: {move_color};">{move_name}</span>'

        nature_mods = get_nature_mods_local(nature)
        final_stats = {}
        for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            base = base_stats.get(stat, 80)
            iv = ivs.get(stat, 31)
            ev = evs.get(stat, 0)
            mod = nature_mods.get(stat, 1.0)
            final_stats[stat] = calc_stat(base, iv, ev, level, mod, stat == "hp")

        stats_display = " / ".join(
            f'<span style="color: {STAT_COLORS.get(s, "#888")};">{final_stats.get(s, "?")}</span>'
            for s in ["hp", "atk", "def", "spa", "spd", "spe"]
        )

        nature_info = NATURE_MODS.get(nature.lower(), (None, None))
        nature_display = nature
        if nature_info[0] and nature_info[1]:
            boost_label = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}.get(nature_info[0], "")
            drop_label = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}.get(nature_info[1], "")
            nature_display = f'{nature} <span class="nature-hint">(+{boost_label} -{drop_label})</span>'

        delay = i * 0.1
        cards_html += f"""
        <div class="paste-card" style="animation-delay: {delay}s; --type-color: {get_type_color(primary_type)};">
            <div class="card-shine"></div>
            <div class="card-header">
                <div class="sprite-area">{get_sprite_html(species, size=80, css_class="paste-sprite")}</div>
                <div class="header-info">
                    <div class="species-name">{species}</div>
                    <div class="types-row">{type_badges}</div>
                    {f'<div class="tera-row">{tera_html}</div>' if tera_html else ''}
                </div>
            </div>
            <div class="card-body">
                <div class="item-ability-row">
                    <div class="item-display"><span class="label">@</span><span class="value">{item or 'None'}</span></div>
                    <div class="ability-display"><span class="value">{ability or 'Unknown'}</span></div>
                </div>
                <div class="nature-ev-row">
                    <div class="nature-display">{nature_display}</div>
                    <div class="ev-total">EVs: {ev_total}/508</div>
                </div>
                <div class="ev-grid">{ev_cells}</div>
                {ivs_html}
                <div class="moves-section"><div class="moves-grid">{moves_html}</div></div>
                <div class="final-stats"><span class="stats-label">Stats:</span><span class="stats-values">{stats_display}</span></div>
            </div>
        </div>"""

    header_title = team_name if team_name else "Team"
    pokemon_count = len(pokemon_list)
    url_display = ""
    if paste_url:
        short_url = paste_url.replace("https://", "").replace("http://", "")
        url_display = f'<a href="{paste_url}" class="paste-link" target="_blank">{short_url}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{header_title}</title>
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%); color: #e4e4e7; line-height: 1.5; min-height: 100vh; padding: 24px; }}
body::before {{ content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-image: radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.08) 0%, transparent 40%), radial-gradient(circle at 80% 70%, rgba(139, 92, 246, 0.06) 0%, transparent 40%); pointer-events: none; z-index: -1; }}
@keyframes fadeSlideIn {{ 0% {{ opacity: 0; transform: translateY(20px) scale(0.98); }} 100% {{ opacity: 1; transform: translateY(0) scale(1); }} }}
@keyframes shimmer {{ 0% {{ background-position: -200% 0; }} 100% {{ background-position: 200% 0; }} }}
.team-container {{ max-width: 1400px; margin: 0 auto; }}
.team-header {{ display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 12px; margin-bottom: 24px; padding: 16px 20px; background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.08); }}
.header-left {{ display: flex; align-items: center; gap: 12px; }}
.team-title {{ font-size: 22px; font-weight: 700; color: #fff; }}
.team-count {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); padding: 4px 12px; border-radius: 16px; font-size: 12px; font-weight: 700; color: #fff; }}
.paste-link {{ font-size: 13px; color: #71717a; text-decoration: none; transition: color 0.2s; }}
.paste-link:hover {{ color: #a78bfa; }}
.team-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); gap: 20px; }}
@media (max-width: 720px) {{ .team-grid {{ grid-template-columns: 1fr; }} }}
.paste-card {{ background: rgba(255, 255, 255, 0.02); backdrop-filter: blur(20px); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.06); overflow: hidden; position: relative; animation: fadeSlideIn 0.5s ease backwards; transition: all 0.3s ease; box-shadow: 0 4px 20px rgba(0, 0, 0, 0.2); }}
.paste-card:hover {{ transform: translateY(-4px); border-color: rgba(255, 255, 255, 0.12); box-shadow: 0 12px 32px rgba(0, 0, 0, 0.3), 0 0 20px var(--type-color, rgba(99, 102, 241, 0.2)); }}
.card-shine {{ position: absolute; top: 0; left: 0; right: 0; bottom: 0; background: linear-gradient(135deg, transparent 0%, rgba(255,255,255,0.03) 40%, rgba(255,255,255,0.06) 50%, rgba(255,255,255,0.03) 60%, transparent 100%); background-size: 200% 200%; opacity: 0; transition: opacity 0.3s; pointer-events: none; }}
.paste-card:hover .card-shine {{ opacity: 1; animation: shimmer 2s ease-in-out infinite; }}
.card-header {{ display: flex; gap: 14px; padding: 16px 16px 12px; background: linear-gradient(180deg, rgba(255,255,255,0.03) 0%, transparent 100%); border-bottom: 1px solid rgba(255, 255, 255, 0.04); }}
.sprite-area {{ flex-shrink: 0; width: 80px; height: 80px; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle, rgba(255, 255, 255, 0.05) 0%, transparent 70%); border-radius: 12px; }}
.paste-sprite {{ width: 72px; height: 72px; image-rendering: auto; filter: drop-shadow(0 3px 8px rgba(0, 0, 0, 0.4)); }}
.header-info {{ flex: 1; min-width: 0; }}
.species-name {{ font-size: 18px; font-weight: 700; color: #fff; margin-bottom: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }}
.types-row {{ display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 6px; }}
.type-badge {{ padding: 3px 8px; border-radius: 4px; font-size: 10px; font-weight: 700; letter-spacing: 0.5px; color: #fff; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2); }}
.type-normal {{ background: linear-gradient(135deg, #A8A878, #8a8a5c); }}
.type-fire {{ background: linear-gradient(135deg, #F08030, #c4682a); }}
.type-water {{ background: linear-gradient(135deg, #6890F0, #5070c0); }}
.type-electric {{ background: linear-gradient(135deg, #F8D030, #c4a828); }}
.type-grass {{ background: linear-gradient(135deg, #78C850, #5ca040); }}
.type-ice {{ background: linear-gradient(135deg, #98D8D8, #70b0b0); }}
.type-fighting {{ background: linear-gradient(135deg, #C03028, #901820); }}
.type-poison {{ background: linear-gradient(135deg, #A040A0, #803080); }}
.type-ground {{ background: linear-gradient(135deg, #E0C068, #b09048); }}
.type-flying {{ background: linear-gradient(135deg, #A890F0, #8070c0); }}
.type-psychic {{ background: linear-gradient(135deg, #F85888, #c04060); }}
.type-bug {{ background: linear-gradient(135deg, #A8B820, #889010); }}
.type-rock {{ background: linear-gradient(135deg, #B8A038, #907820); }}
.type-ghost {{ background: linear-gradient(135deg, #705898, #504070); }}
.type-dragon {{ background: linear-gradient(135deg, #7038F8, #5028c0); }}
.type-dark {{ background: linear-gradient(135deg, #705848, #503830); }}
.type-steel {{ background: linear-gradient(135deg, #B8B8D0, #9090a8); }}
.type-fairy {{ background: linear-gradient(135deg, #EE99AC, #c07088); }}
.tera-row {{ margin-top: 4px; }}
.tera-badge {{ display: inline-flex; align-items: center; gap: 4px; padding: 3px 8px; background: linear-gradient(135deg, rgba(255,255,255,0.08), rgba(255,255,255,0.04)); border: 1px dashed var(--tera-color, #fff); border-radius: 4px; font-size: 10px; font-weight: 600; color: var(--tera-color, #fff); }}
.tera-icon {{ font-size: 11px; }}
.card-body {{ padding: 12px 16px 16px; }}
.item-ability-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; padding-bottom: 8px; border-bottom: 1px solid rgba(255, 255, 255, 0.05); }}
.item-display, .ability-display {{ font-size: 12px; }}
.item-display .label {{ color: #f59e0b; margin-right: 4px; }}
.item-display .value {{ color: #e4e4e7; font-weight: 500; }}
.ability-display .value {{ color: #a78bfa; font-style: italic; }}
.nature-ev-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px; }}
.nature-display {{ font-size: 13px; font-weight: 600; color: #e4e4e7; }}
.nature-hint {{ font-weight: 400; font-size: 11px; color: #71717a; }}
.ev-total {{ font-size: 11px; color: #71717a; background: rgba(255, 255, 255, 0.05); padding: 2px 8px; border-radius: 8px; }}
.ev-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 4px; margin-bottom: 8px; background: rgba(0, 0, 0, 0.2); border-radius: 8px; padding: 8px; }}
.ev-cell {{ text-align: center; }}
.ev-label {{ display: block; font-size: 9px; color: #71717a; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 2px; }}
.ev-value {{ font-family: 'SF Mono', 'Consolas', monospace; font-size: 13px; font-weight: 700; }}
.ivs-note {{ font-size: 11px; color: #f87171; margin-bottom: 8px; padding: 4px 8px; background: rgba(248, 113, 113, 0.1); border-radius: 4px; border-left: 2px solid #f87171; }}
.moves-section {{ margin-bottom: 10px; }}
.moves-grid {{ display: flex; flex-wrap: wrap; gap: 5px; }}
.move-pill {{ padding: 4px 10px; background: var(--move-color, #888); border-radius: 10px; font-size: 11px; font-weight: 600; color: #fff; box-shadow: 0 2px 6px rgba(0, 0, 0, 0.2); }}
.final-stats {{ padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.05); font-size: 12px; }}
.stats-label {{ color: #71717a; margin-right: 6px; }}
.stats-values {{ font-family: 'SF Mono', 'Consolas', monospace; font-weight: 600; }}
    </style>
</head>
<body>
    <div class="team-container">
        <div class="team-header">
            <div class="header-left">
                <span class="team-title">{header_title}</span>
                <span class="team-count">{pokemon_count} Pokemon</span>
            </div>
            {url_display}
        </div>
        <div class="team-grid">{cards_html}</div>
    </div>
</body>
</html>"""


def create_build_report_ui(
    initial_team: list[dict],
    final_team: list[dict],
    conversation: list[dict],
    changes: list[dict],
    takeaways: list[str],
    title: Optional[str] = None,
    created_date: Optional[str] = None,
    paste_url: Optional[str] = None,
) -> str:
    """
    Generate a shareable team build report HTML page.

    Creates a self-contained HTML document showing the full team building
    journey: starting state, discussion points, changes made, and conclusions.
    Designed for non-technical users to follow the conversation.

    Args:
        initial_team: Starting team state (list of pokemon dicts)
        final_team: Final team state after changes (list of pokemon dicts)
        conversation: List of Q&A exchanges, each dict with:
            - question: str
            - answer: str
            - visual: Optional dict with type and html content
        changes: List of changes made, each dict with:
            - pokemon: str (species name)
            - field: str (what changed, e.g., "EVs", "Tera Type")
            - before: str
            - after: str
            - reason: str (why the change was made)
        takeaways: List of key conclusion strings
        title: Optional report title
        created_date: Optional date string (defaults to today)
        paste_url: Optional source pokepaste URL

    Returns:
        Complete self-contained HTML string
    """
    import datetime

    report_title = title or "VGC Team Build Report"
    date_str = created_date or datetime.date.today().strftime("%B %d, %Y")

    NATURE_MODS = {
        "hardy": (None, None), "lonely": ("atk", "def"), "brave": ("atk", "spe"),
        "adamant": ("atk", "spa"), "naughty": ("atk", "spd"),
        "bold": ("def", "atk"), "docile": (None, None), "relaxed": ("def", "spe"),
        "impish": ("def", "spa"), "lax": ("def", "spd"),
        "timid": ("spe", "atk"), "hasty": ("spe", "def"), "serious": (None, None),
        "jolly": ("spe", "spa"), "naive": ("spe", "spd"),
        "modest": ("spa", "atk"), "mild": ("spa", "def"),
        "quiet": ("spa", "spe"), "bashful": (None, None), "rash": ("spa", "spd"),
        "calm": ("spd", "atk"), "gentle": ("spd", "def"),
        "sassy": ("spd", "spe"), "careful": ("spd", "spa"), "quirky": (None, None),
    }

    STAT_COLORS = {
        "hp": "#ff5959", "atk": "#f5ac78", "def": "#fae078",
        "spa": "#9db7f5", "spd": "#a7db8d", "spe": "#fa92b2"
    }

    def calc_stat(base, iv, ev, level, nature_mod, is_hp):
        if is_hp:
            return int((2 * base + iv + ev // 4) * level / 100) + level + 10
        return int(((2 * base + iv + ev // 4) * level / 100 + 5) * nature_mod)

    def get_nature_mods_local(nature):
        mods = {"hp": 1.0, "atk": 1.0, "def": 1.0, "spa": 1.0, "spd": 1.0, "spe": 1.0}
        nature_data = NATURE_MODS.get(nature.lower(), (None, None))
        if nature_data[0]:
            mods[nature_data[0]] = 1.1
        if nature_data[1]:
            mods[nature_data[1]] = 0.9
        return mods

    def generate_mini_team_grid(pokemon_list: list[dict]) -> str:
        if not pokemon_list:
            return '<div class="empty-team">No team data</div>'

        cards_html = ""
        for i, pokemon in enumerate(pokemon_list[:6]):
            species = pokemon.get("species", "Unknown")
            types = pokemon.get("types", [])
            item = pokemon.get("item", "")
            ability = pokemon.get("ability", "")
            nature = pokemon.get("nature", "Serious")
            evs = pokemon.get("evs", {})
            ivs = pokemon.get("ivs", {})
            moves = pokemon.get("moves", [])
            tera_type = pokemon.get("tera_type")
            level = pokemon.get("level", 50)
            base_stats = pokemon.get("base_stats", {})
            speed_tier_pct = pokemon.get("speed_tier_pct")  # Optional speed tier %

            ev_total = sum(evs.get(s, 0) for s in ["hp", "atk", "def", "spa", "spd", "spe"])
            primary_type = types[0].lower() if types else "normal"

            type_badges = " ".join(
                f'<span class="type-badge type-{t.lower()}">{t.upper()}</span>'
                for t in types
            )

            tera_html = ""
            if tera_type:
                tera_color = get_type_color(tera_type)
                tera_html = f'<span class="tera-badge" style="--tera-color: {tera_color};"><span class="tera-icon">&#10022;</span> {tera_type}</span>'

            ev_cells = ""
            for stat, label in [("hp", "HP"), ("atk", "Atk"), ("def", "Def"), ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe")]:
                val = evs.get(stat, 0)
                color = STAT_COLORS.get(stat, "#888")
                ev_cells += f'<div class="ev-cell"><span class="ev-label">{label}</span><span class="ev-value" style="color: {color};">{val}</span></div>'

            iv_parts = []
            for stat, label in [("hp", "HP"), ("atk", "Atk"), ("def", "Def"), ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe")]:
                iv_val = ivs.get(stat, 31)
                if iv_val != 31:
                    iv_parts.append(f"{iv_val} {label}")
            ivs_html = f'<div class="ivs-note">IVs: {", ".join(iv_parts)}</div>' if iv_parts else ""

            moves_html = ""
            for move in moves[:4]:
                move_name = move.get("name", move) if isinstance(move, dict) else str(move)
                moves_html += f'<span class="move-pill">{move_name}</span>'

            nature_mods = get_nature_mods_local(nature)
            final_stats = {}
            for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
                base = base_stats.get(stat, 80)
                iv = ivs.get(stat, 31)
                ev = evs.get(stat, 0)
                mod = nature_mods.get(stat, 1.0)
                final_stats[stat] = calc_stat(base, iv, ev, level, mod, stat == "hp")

            stats_display = " / ".join(
                f'<span style="color: {STAT_COLORS.get(s, "#888")};">{final_stats.get(s, "?")}</span>'
                for s in ["hp", "atk", "def", "spa", "spd", "spe"]
            )

            # Speed tier bar if provided
            speed_tier_html = ""
            if speed_tier_pct is not None:
                pct = float(speed_tier_pct)
                bar_color = "#10b981" if pct >= 70 else "#f59e0b" if pct >= 40 else "#ef4444"
                speed_tier_html = f'''
                <div class="speed-tier-row">
                    <span class="speed-tier-label">Speed Tier</span>
                    <div class="speed-tier-bar-bg">
                        <div class="speed-tier-bar" style="width: {pct}%; background: {bar_color};"></div>
                    </div>
                    <span class="speed-tier-pct">{pct:.0f}%</span>
                </div>'''

            delay = i * 0.08
            cards_html += f"""
            <div class="mini-card" style="animation-delay: {delay}s; --type-color: {get_type_color(primary_type)};">
                <div class="mini-header">
                    <div class="mini-sprite">{get_sprite_html(species, size=56, css_class="sprite-img")}</div>
                    <div class="mini-info">
                        <div class="mini-name">{species}</div>
                        <div class="mini-types">{type_badges}</div>
                        {f'<div class="mini-tera">{tera_html}</div>' if tera_html else ''}
                    </div>
                </div>
                <div class="mini-details">
                    <div class="mini-row"><span class="mini-label">@</span> {item or 'None'} <span class="mini-ability">{ability}</span></div>
                    <div class="mini-row"><span class="mini-nature">{nature}</span> <span class="mini-ev-total">{ev_total}/508 EVs</span></div>
                    <div class="mini-ev-grid">{ev_cells}</div>
                    {ivs_html}
                    <div class="mini-moves">{moves_html}</div>
                    <div class="mini-stats">{stats_display}</div>
                    {speed_tier_html}
                </div>
            </div>"""

        return f'<div class="mini-team-grid">{cards_html}</div>'

    def generate_damage_calc_visual(calc_data: dict) -> str:
        """Generate HTML for a damage calc visual."""
        attacker = calc_data.get("attacker", "Attacker")
        defender = calc_data.get("defender", "Defender")
        move = calc_data.get("move", "Move")
        damage_range = calc_data.get("damage_range", "0-0%")
        rolls = calc_data.get("rolls", "")
        ko_chance = calc_data.get("ko_chance", "")

        try:
            low, high = damage_range.replace("%", "").split("-")
            avg_pct = (float(low) + float(high)) / 2
        except:
            avg_pct = 50

        bar_color = "#ef4444" if avg_pct >= 100 else "#f59e0b" if avg_pct >= 50 else "#10b981"
        ko_html = f'<span class="calc-ko">{ko_chance}</span>' if ko_chance else ""

        return f'''
        <div class="damage-calc-card">
            <div class="calc-header">
                <span class="calc-attacker">{attacker}</span>
                <span class="calc-arrow">&#8594;</span>
                <span class="calc-defender">{defender}</span>
            </div>
            <div class="calc-move">{move}</div>
            <div class="calc-result">
                <div class="calc-bar-bg">
                    <div class="calc-bar" style="width: {min(avg_pct, 100)}%; background: {bar_color};"></div>
                </div>
                <span class="calc-damage">{damage_range}</span>
                {ko_html}
            </div>
            {f'<div class="calc-rolls">{rolls}</div>' if rolls else ''}
        </div>'''

    def generate_speed_tier_visual(speed_data: dict) -> str:
        """Generate HTML for a speed tier comparison visual."""
        pokemon = speed_data.get("pokemon", "Pokemon")
        speed_stat = speed_data.get("speed", 0)
        tier_pct = speed_data.get("tier_pct", 50)
        outspeeds = speed_data.get("outspeeds", [])
        outsped_by = speed_data.get("outsped_by", [])

        bar_color = "#10b981" if tier_pct >= 70 else "#f59e0b" if tier_pct >= 40 else "#ef4444"

        outspeeds_html = ""
        if outspeeds:
            items = ", ".join(outspeeds[:5])
            outspeeds_html = f'<div class="speed-list outspeed-list"><span class="speed-list-label">Outspeeds:</span> {items}</div>'

        outsped_html = ""
        if outsped_by:
            items = ", ".join(outsped_by[:5])
            outsped_html = f'<div class="speed-list outsped-list"><span class="speed-list-label">Outsped by:</span> {items}</div>'

        return f'''
        <div class="speed-tier-card">
            <div class="speed-header">
                <span class="speed-pokemon">{pokemon}</span>
                <span class="speed-stat">{speed_stat} Spe</span>
            </div>
            <div class="speed-tier-display">
                <div class="speed-bar-container">
                    <div class="speed-bar-bg">
                        <div class="speed-bar-fill" style="width: {tier_pct}%; background: {bar_color};"></div>
                    </div>
                    <span class="speed-pct-label">{tier_pct:.0f}% of meta</span>
                </div>
            </div>
            {outspeeds_html}
            {outsped_html}
        </div>'''

    def generate_conversation_html(conv_list: list[dict]) -> str:
        if not conv_list:
            return '<div class="no-content">No discussion recorded</div>'

        html = ""
        for i, item in enumerate(conv_list):
            question = item.get("question", "")
            answer = item.get("answer", "")
            visual = item.get("visual", {})
            delay = i * 0.1

            visual_html = ""
            if visual:
                visual_type = visual.get("type", "")
                visual_data = visual.get("data", {})
                raw_html = visual.get("html", visual.get("content", ""))

                if visual_type == "damage_calc" and visual_data:
                    visual_html = f'<div class="conv-visual">{generate_damage_calc_visual(visual_data)}</div>'
                elif visual_type == "speed_tier" and visual_data:
                    visual_html = f'<div class="conv-visual">{generate_speed_tier_visual(visual_data)}</div>'
                elif raw_html:
                    visual_html = f'<div class="conv-visual">{raw_html}</div>'

            html += f"""
            <div class="conv-exchange" style="animation-delay: {delay}s;">
                <div class="conv-question">
                    <div class="conv-icon">Q</div>
                    <div class="conv-text">{question}</div>
                </div>
                <div class="conv-answer">
                    <div class="conv-icon answer-icon">A</div>
                    <div class="conv-text">{answer}</div>
                    {visual_html}
                </div>
            </div>"""
        return html

    def generate_changes_html(changes_list: list[dict]) -> str:
        if not changes_list:
            return '<div class="no-content">No changes made</div>'

        html = ""
        for i, change in enumerate(changes_list):
            pokemon = change.get("pokemon", "Unknown")
            field = change.get("field", "")
            before = change.get("before", "")
            after = change.get("after", "")
            reason = change.get("reason", "")
            delay = i * 0.08

            html += f"""
            <div class="change-item" style="animation-delay: {delay}s;">
                <div class="change-header">
                    <span class="change-pokemon">{pokemon}</span>
                    <span class="change-field">{field}</span>
                </div>
                <div class="change-diff">
                    <span class="change-before">{before}</span>
                    <span class="change-arrow">&#8594;</span>
                    <span class="change-after">{after}</span>
                </div>
                <div class="change-reason">{reason}</div>
            </div>"""
        return html

    def generate_takeaways_html(takeaway_list: list[str]) -> str:
        if not takeaway_list:
            return '<div class="no-content">No key takeaways</div>'
        items = "".join(f'<li class="takeaway-item">{t}</li>' for t in takeaway_list)
        return f'<ul class="takeaway-list">{items}</ul>'

    initial_team_html = generate_mini_team_grid(initial_team)
    final_team_html = generate_mini_team_grid(final_team)
    conversation_html = generate_conversation_html(conversation)
    changes_html = generate_changes_html(changes)
    takeaways_html = generate_takeaways_html(takeaways)

    source_html = ""
    if paste_url:
        short_url = paste_url.replace("https://", "").replace("http://", "")
        source_html = f'<a href="{paste_url}" class="source-link" target="_blank">Source: {short_url}</a>'

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{report_title}</title>
    <style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%); color: #e4e4e7; line-height: 1.6; min-height: 100vh; }}
body::before {{ content: ""; position: fixed; top: 0; left: 0; width: 100%; height: 100%; background-image: radial-gradient(circle at 20% 30%, rgba(99, 102, 241, 0.08) 0%, transparent 40%), radial-gradient(circle at 80% 70%, rgba(139, 92, 246, 0.06) 0%, transparent 40%); pointer-events: none; z-index: -1; }}
@keyframes fadeSlideIn {{ 0% {{ opacity: 0; transform: translateY(16px); }} 100% {{ opacity: 1; transform: translateY(0); }} }}
.report-container {{ max-width: 1000px; margin: 0 auto; padding: 32px 24px; }}
.report-header {{ text-align: center; margin-bottom: 40px; padding: 32px; background: rgba(255, 255, 255, 0.03); backdrop-filter: blur(20px); border-radius: 20px; border: 1px solid rgba(255, 255, 255, 0.08); animation: fadeSlideIn 0.5s ease; }}
.report-title {{ font-size: 28px; font-weight: 800; color: #fff; margin-bottom: 8px; background: linear-gradient(135deg, #fff 0%, #a78bfa 100%); -webkit-background-clip: text; -webkit-text-fill-color: transparent; background-clip: text; }}
.report-date {{ font-size: 14px; color: #71717a; }}
.source-link {{ display: inline-block; margin-top: 12px; font-size: 12px; color: #6366f1; text-decoration: none; }}
.source-link:hover {{ color: #a78bfa; }}
.share-buttons {{ display: flex; justify-content: center; gap: 12px; margin-top: 16px; }}
.share-btn {{ padding: 8px 16px; background: rgba(99, 102, 241, 0.15); border: 1px solid rgba(99, 102, 241, 0.3); border-radius: 8px; color: #a78bfa; font-size: 13px; font-weight: 600; cursor: pointer; transition: all 0.2s; }}
.share-btn:hover {{ background: rgba(99, 102, 241, 0.25); border-color: rgba(99, 102, 241, 0.5); }}
.report-section {{ margin-bottom: 32px; animation: fadeSlideIn 0.5s ease backwards; }}
.section-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 16px; padding-bottom: 12px; border-bottom: 1px solid rgba(255, 255, 255, 0.08); }}
.section-icon {{ width: 36px; height: 36px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, rgba(99, 102, 241, 0.2), rgba(139, 92, 246, 0.2)); border-radius: 10px; font-size: 18px; }}
.section-title {{ font-size: 18px; font-weight: 700; color: #fff; }}
.section-content {{ background: rgba(255, 255, 255, 0.02); backdrop-filter: blur(10px); border-radius: 16px; border: 1px solid rgba(255, 255, 255, 0.06); padding: 20px; }}
.mini-team-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 16px; }}
@media (max-width: 640px) {{ .mini-team-grid {{ grid-template-columns: 1fr; }} }}
.mini-card {{ background: rgba(0, 0, 0, 0.3); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.06); padding: 12px; animation: fadeSlideIn 0.4s ease backwards; transition: all 0.2s; }}
.mini-card:hover {{ border-color: rgba(255, 255, 255, 0.12); box-shadow: 0 4px 16px rgba(0, 0, 0, 0.3); }}
.mini-header {{ display: flex; gap: 10px; margin-bottom: 10px; }}
.mini-sprite {{ width: 56px; height: 56px; display: flex; align-items: center; justify-content: center; background: radial-gradient(circle, rgba(255, 255, 255, 0.05) 0%, transparent 70%); border-radius: 8px; }}
.sprite-img {{ width: 48px; height: 48px; image-rendering: auto; }}
.mini-info {{ flex: 1; }}
.mini-name {{ font-size: 14px; font-weight: 700; color: #fff; margin-bottom: 4px; }}
.mini-types {{ display: flex; flex-wrap: wrap; gap: 4px; }}
.mini-tera {{ margin-top: 4px; }}
.mini-details {{ font-size: 11px; }}
.mini-row {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; color: #a1a1aa; }}
.mini-label {{ color: #f59e0b; font-weight: 600; }}
.mini-ability {{ color: #a78bfa; font-style: italic; }}
.mini-nature {{ font-weight: 600; color: #e4e4e7; }}
.mini-ev-total {{ color: #71717a; }}
.mini-ev-grid {{ display: grid; grid-template-columns: repeat(6, 1fr); gap: 2px; margin-bottom: 6px; background: rgba(0, 0, 0, 0.3); border-radius: 6px; padding: 6px; }}
.ev-cell {{ text-align: center; }}
.ev-label {{ display: block; font-size: 8px; color: #71717a; text-transform: uppercase; }}
.ev-value {{ font-family: 'SF Mono', 'Consolas', monospace; font-size: 11px; font-weight: 700; }}
.ivs-note {{ font-size: 10px; color: #f87171; margin-bottom: 6px; padding: 3px 6px; background: rgba(248, 113, 113, 0.1); border-radius: 4px; border-left: 2px solid #f87171; }}
.mini-moves {{ display: flex; flex-wrap: wrap; gap: 4px; margin-bottom: 6px; }}
.move-pill {{ padding: 2px 8px; background: rgba(99, 102, 241, 0.3); border-radius: 8px; font-size: 10px; font-weight: 600; color: #e4e4e7; }}
.mini-stats {{ font-family: 'SF Mono', 'Consolas', monospace; font-size: 10px; color: #a1a1aa; padding-top: 6px; border-top: 1px solid rgba(255, 255, 255, 0.05); }}
.speed-tier-row {{ display: flex; align-items: center; gap: 8px; margin-top: 6px; padding-top: 6px; border-top: 1px solid rgba(255, 255, 255, 0.05); }}
.speed-tier-label {{ font-size: 9px; color: #71717a; white-space: nowrap; }}
.speed-tier-bar-bg {{ flex: 1; height: 6px; background: rgba(255, 255, 255, 0.1); border-radius: 3px; overflow: hidden; }}
.speed-tier-bar {{ height: 100%; border-radius: 3px; transition: width 0.3s ease; }}
.speed-tier-pct {{ font-size: 10px; font-weight: 700; color: #e4e4e7; min-width: 32px; text-align: right; }}
.type-badge {{ padding: 2px 6px; border-radius: 3px; font-size: 9px; font-weight: 700; letter-spacing: 0.3px; color: #fff; }}
.type-normal {{ background: linear-gradient(135deg, #A8A878, #8a8a5c); }}
.type-fire {{ background: linear-gradient(135deg, #F08030, #c4682a); }}
.type-water {{ background: linear-gradient(135deg, #6890F0, #5070c0); }}
.type-electric {{ background: linear-gradient(135deg, #F8D030, #c4a828); }}
.type-grass {{ background: linear-gradient(135deg, #78C850, #5ca040); }}
.type-ice {{ background: linear-gradient(135deg, #98D8D8, #70b0b0); }}
.type-fighting {{ background: linear-gradient(135deg, #C03028, #901820); }}
.type-poison {{ background: linear-gradient(135deg, #A040A0, #803080); }}
.type-ground {{ background: linear-gradient(135deg, #E0C068, #b09048); }}
.type-flying {{ background: linear-gradient(135deg, #A890F0, #8070c0); }}
.type-psychic {{ background: linear-gradient(135deg, #F85888, #c04060); }}
.type-bug {{ background: linear-gradient(135deg, #A8B820, #889010); }}
.type-rock {{ background: linear-gradient(135deg, #B8A038, #907820); }}
.type-ghost {{ background: linear-gradient(135deg, #705898, #504070); }}
.type-dragon {{ background: linear-gradient(135deg, #7038F8, #5028c0); }}
.type-dark {{ background: linear-gradient(135deg, #705848, #503830); }}
.type-steel {{ background: linear-gradient(135deg, #B8B8D0, #9090a8); }}
.type-fairy {{ background: linear-gradient(135deg, #EE99AC, #c07088); }}
.tera-badge {{ display: inline-flex; align-items: center; gap: 3px; padding: 2px 6px; background: rgba(255, 255, 255, 0.05); border: 1px dashed var(--tera-color, #fff); border-radius: 3px; font-size: 9px; font-weight: 600; color: var(--tera-color, #fff); }}
.tera-icon {{ font-size: 10px; }}
.conv-exchange {{ margin-bottom: 20px; animation: fadeSlideIn 0.4s ease backwards; }}
.conv-exchange:last-child {{ margin-bottom: 0; }}
.conv-question, .conv-answer {{ display: flex; gap: 12px; margin-bottom: 12px; }}
.conv-icon {{ flex-shrink: 0; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; background: linear-gradient(135deg, #6366f1, #8b5cf6); border-radius: 8px; font-size: 12px; font-weight: 800; color: #fff; }}
.answer-icon {{ background: linear-gradient(135deg, #10b981, #059669); }}
.conv-text {{ flex: 1; background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 12px 16px; font-size: 14px; line-height: 1.6; }}
.conv-question .conv-text {{ background: rgba(99, 102, 241, 0.1); border: 1px solid rgba(99, 102, 241, 0.2); }}
.conv-answer .conv-text {{ background: rgba(16, 185, 129, 0.08); border: 1px solid rgba(16, 185, 129, 0.15); }}
.conv-visual {{ margin-left: 40px; margin-top: 8px; padding: 12px; background: rgba(0, 0, 0, 0.3); border-radius: 12px; border: 1px solid rgba(255, 255, 255, 0.06); overflow-x: auto; }}
.change-item {{ background: rgba(0, 0, 0, 0.2); border-radius: 12px; padding: 16px; margin-bottom: 12px; border-left: 3px solid #f59e0b; animation: fadeSlideIn 0.4s ease backwards; }}
.change-item:last-child {{ margin-bottom: 0; }}
.change-header {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; }}
.change-pokemon {{ font-weight: 700; color: #fff; font-size: 15px; }}
.change-field {{ font-size: 12px; color: #71717a; background: rgba(255, 255, 255, 0.05); padding: 2px 8px; border-radius: 4px; }}
.change-diff {{ display: flex; align-items: center; gap: 12px; margin-bottom: 8px; font-family: 'SF Mono', 'Consolas', monospace; font-size: 14px; }}
.change-before {{ color: #f87171; text-decoration: line-through; opacity: 0.8; }}
.change-arrow {{ color: #71717a; }}
.change-after {{ color: #34d399; font-weight: 600; }}
.change-reason {{ font-size: 13px; color: #a1a1aa; font-style: italic; padding-left: 12px; border-left: 2px solid rgba(255, 255, 255, 0.1); }}
.takeaway-list {{ list-style: none; }}
.takeaway-item {{ position: relative; padding: 12px 16px 12px 40px; margin-bottom: 8px; background: rgba(16, 185, 129, 0.08); border-radius: 10px; border: 1px solid rgba(16, 185, 129, 0.15); font-size: 14px; line-height: 1.5; }}
.takeaway-item:last-child {{ margin-bottom: 0; }}
.takeaway-item::before {{ content: "\\2713"; position: absolute; left: 14px; top: 50%; transform: translateY(-50%); color: #10b981; font-weight: 700; font-size: 14px; }}
.no-content {{ text-align: center; color: #71717a; font-style: italic; padding: 24px; }}
.empty-team {{ text-align: center; color: #71717a; font-style: italic; padding: 40px; }}
.report-footer {{ text-align: center; margin-top: 40px; padding-top: 24px; border-top: 1px solid rgba(255, 255, 255, 0.06); font-size: 12px; color: #52525b; }}
.report-footer a {{ color: #6366f1; text-decoration: none; }}
.report-footer a:hover {{ color: #a78bfa; }}
/* Damage Calc Card Styles */
.damage-calc-card {{ background: rgba(0, 0, 0, 0.3); border-radius: 10px; padding: 14px; border: 1px solid rgba(255, 255, 255, 0.08); }}
.calc-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 8px; font-size: 13px; font-weight: 600; }}
.calc-attacker {{ color: #f87171; }}
.calc-arrow {{ color: #71717a; font-size: 16px; }}
.calc-defender {{ color: #60a5fa; }}
.calc-move {{ font-size: 12px; color: #a78bfa; font-weight: 600; margin-bottom: 10px; padding: 4px 10px; background: rgba(167, 139, 250, 0.15); border-radius: 6px; display: inline-block; }}
.calc-result {{ display: flex; align-items: center; gap: 10px; }}
.calc-bar-bg {{ flex: 1; height: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 5px; overflow: hidden; }}
.calc-bar {{ height: 100%; border-radius: 5px; transition: width 0.4s ease; }}
.calc-damage {{ font-family: 'SF Mono', 'Consolas', monospace; font-size: 13px; font-weight: 700; color: #fff; min-width: 70px; text-align: right; }}
.calc-ko {{ font-size: 11px; font-weight: 700; padding: 3px 8px; background: linear-gradient(135deg, #ef4444, #dc2626); border-radius: 4px; color: #fff; }}
.calc-rolls {{ font-size: 10px; color: #71717a; margin-top: 8px; font-family: 'SF Mono', 'Consolas', monospace; }}
/* Speed Tier Visual Card Styles */
.speed-tier-card {{ background: rgba(0, 0, 0, 0.3); border-radius: 10px; padding: 14px; border: 1px solid rgba(255, 255, 255, 0.08); }}
.speed-header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; }}
.speed-pokemon {{ font-size: 14px; font-weight: 700; color: #fff; }}
.speed-stat {{ font-family: 'SF Mono', 'Consolas', monospace; font-size: 13px; font-weight: 600; color: #fa92b2; }}
.speed-tier-display {{ margin-bottom: 10px; }}
.speed-bar-container {{ display: flex; align-items: center; gap: 10px; }}
.speed-bar-bg {{ flex: 1; height: 10px; background: rgba(255, 255, 255, 0.1); border-radius: 5px; overflow: hidden; }}
.speed-bar-fill {{ height: 100%; border-radius: 5px; transition: width 0.4s ease; }}
.speed-pct-label {{ font-size: 12px; font-weight: 700; color: #e4e4e7; min-width: 75px; text-align: right; }}
.speed-list {{ font-size: 11px; color: #a1a1aa; margin-bottom: 6px; }}
.speed-list:last-child {{ margin-bottom: 0; }}
.speed-list-label {{ font-weight: 600; color: #71717a; margin-right: 4px; }}
.outspeed-list .speed-list-label {{ color: #10b981; }}
.outsped-list .speed-list-label {{ color: #f87171; }}
    </style>
</head>
<body>
    <div class="report-container">
        <header class="report-header">
            <h1 class="report-title">{report_title}</h1>
            <div class="report-date">Created: {date_str}</div>
            {source_html}
            <div class="share-buttons">
                <button class="share-btn" onclick="navigator.clipboard.writeText(window.location.href).then(() => alert('Link copied!'))">Copy Link</button>
                <button class="share-btn" onclick="window.print()">Print / Save PDF</button>
            </div>
        </header>
        <section class="report-section" style="animation-delay: 0.1s;">
            <div class="section-header">
                <div class="section-icon">&#128203;</div>
                <h2 class="section-title">Starting Team</h2>
            </div>
            <div class="section-content">{initial_team_html}</div>
        </section>
        <section class="report-section" style="animation-delay: 0.2s;">
            <div class="section-header">
                <div class="section-icon">&#128172;</div>
                <h2 class="section-title">Discussion</h2>
            </div>
            <div class="section-content">{conversation_html}</div>
        </section>
        <section class="report-section" style="animation-delay: 0.3s;">
            <div class="section-header">
                <div class="section-icon">&#128260;</div>
                <h2 class="section-title">Changes Made</h2>
            </div>
            <div class="section-content">{changes_html}</div>
        </section>
        <section class="report-section" style="animation-delay: 0.4s;">
            <div class="section-header">
                <div class="section-icon">&#9989;</div>
                <h2 class="section-title">Final Team</h2>
            </div>
            <div class="section-content">{final_team_html}</div>
        </section>
        <section class="report-section" style="animation-delay: 0.5s;">
            <div class="section-header">
                <div class="section-icon">&#128221;</div>
                <h2 class="section-title">Key Takeaways</h2>
            </div>
            <div class="section-content">{takeaways_html}</div>
        </section>
        <footer class="report-footer">
            Generated with <a href="https://github.com/anthropics/claude-code" target="_blank">VGC MCP Server</a>
        </footer>
    </div>
</body>
</html>"""
