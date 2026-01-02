# -*- coding: utf-8 -*-
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


def get_sprite_url(pokemon_name: str, animated: bool = True) -> str:
    """Get Pokemon sprite URL - animated GIF from Showdown or static PNG fallback.

    Args:
        pokemon_name: Name of the Pokemon
        animated: If True, returns animated GIF from Pokemon Showdown.
                  If False, returns static PNG from PokemonDB.

    Returns:
        URL string for the Pokemon sprite
    """
    # Normalize name for URL
    normalized = pokemon_name.lower().replace(" ", "-").replace(".", "")
    # Handle special forms
    if normalized.startswith("urshifu"):
        if "rapid" in normalized:
            normalized = "urshifu-rapid-strike"
        else:
            normalized = "urshifu"

    if animated:
        # Pokemon Showdown animated sprites
        return f"https://play.pokemonshowdown.com/sprites/ani/{normalized}.gif"
    else:
        # Fallback to static PokemonDB sprites
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
    interactive: bool = False,
    attacker_evs: Optional[dict[str, int]] = None,
    defender_evs: Optional[dict[str, int]] = None,
    attacker_nature: str = "Serious",
    defender_nature: str = "Serious",
    attacker_base_stats: Optional[dict[str, int]] = None,
    defender_base_stats: Optional[dict[str, int]] = None,
    move_category: str = "special",
    move_power: int = 0,
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
                    {f'<optgroup label="⭐ {attacker} Smogon Moves">{smogon_options}</optgroup>' if smogon_options else ''}
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
                    <img src="{get_sprite_url(attacker)}" class="pokemon-sprite" alt="{attacker}">
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
                    <img src="{get_sprite_url(defender)}" class="pokemon-sprite" alt="{defender}">
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
            defenderBaseStats: {str(defender_base_stats).replace("'", '"')}
        }};

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

        // Calculate damage (simplified Gen 9 formula)
        function calculateDamage() {{
            const attackerEVs = getEVs('atk');
            const defenderEVs = getEVs('def');
            const attackerNature = document.getElementById('attacker-nature').value;
            const defenderNature = document.getElementById('defender-nature').value;
            const attackerItem = document.getElementById('attacker-item').value;
            const defenderItem = document.getElementById('defender-item').value;

            // Determine which stats to use
            const isPhysical = calcData.moveCategory === 'physical';
            const atkStatName = isPhysical ? 'attack' : 'special_attack';
            const defStatName = isPhysical ? 'defense' : 'special_defense';

            // Calculate stats
            const attackStat = calcStat(
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
            const baseDamage = Math.floor(Math.floor(Math.floor(2 * level / 5 + 2) * power * attackStat / defenseStat) / 50 + 2);

            // Apply modifiers
            let damage = baseDamage;
            damage = Math.floor(damage * itemMod);  // Item
            damage = Math.floor(damage * 1.5);  // STAB (assuming)
            damage = Math.floor(damage * calcData.typeEffectiveness);  // Type effectiveness

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

        // Determine KO chance
        function getKOChance(minPct, maxPct) {{
            if (minPct >= 100) return {{ text: 'Guaranteed OHKO', class: 'ohko' }};
            if (maxPct >= 100) return {{ text: 'Possible OHKO', class: 'ohko' }};
            if (minPct >= 50) return {{ text: 'Guaranteed 2HKO', class: '2hko' }};
            if (maxPct >= 50) return {{ text: 'Possible 2HKO', class: '2hko' }};
            if (minPct >= 33.4) return {{ text: 'Guaranteed 3HKO', class: '3hko' }};
            if (maxPct >= 33.4) return {{ text: 'Possible 3HKO', class: '3hko' }};
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
                <img src="{get_sprite_url(p)}" class="chip-sprite" alt="{p}">
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
            <img src="{get_sprite_url(threat_name)}" class="threat-sprite" alt="{threat_name}">
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

    sprite_url = get_sprite_url(pokemon_name)
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
        <img src="{sprite_url}" class="sprite" alt="{pokemon_name}">
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

    sprite_url = get_sprite_url(pokemon_name)

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
        <img src="{sprite_url}" class="sprite" alt="{pokemon_name}">
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
        {"".join(f'''
        <div class="stat-row">
            <div class="stat-label {'boosted' if stat_keys[i] == boosted_stat else 'lowered' if stat_keys[i] == lowered_stat else ''}">{stat_labels[i]}</div>
            <div class="stat-bar-container">
                <div class="stat-bar {stat_keys[i]}" style="width:{min(100, base_stats.get(stat_keys[i], 100) / 2)}%"></div>
                <div class="stat-values">
                    <span class="stat-base">{base_stats.get(stat_keys[i], 100)}</span>
                    <span class="stat-final">{final_stats[stat_keys[i]]}</span>
                </div>
            </div>
        </div>
        ''' for i in range(6))}
    </div>

    <div class="ev-section">
        <div class="section-title">EV Spread</div>
        <div class="ev-grid">
            {"".join(f'''
            <div class="ev-item">
                <div class="ev-label">{stat_labels[i]}</div>
                <div class="ev-value {'zero' if evs.get(stat_keys[i], 0) == 0 else ''}">{evs.get(stat_keys[i], 0)}</div>
            </div>
            ''' for i in range(6))}
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

    sprite_url = pokemon_sprite or get_sprite_url(pokemon_name)
    threats_json = json.dumps(threats[:10])  # Top 10 threats

    def get_ko_class(damage_min: float, damage_max: float) -> tuple[str, str]:
        """Return CSS class and label for damage range."""
        avg = (damage_min + damage_max) / 2
        if damage_min >= 100:
            return "ohko", "OHKO"
        elif damage_max >= 100:
            return "ohko-chance", f"{int(damage_min)}-{int(damage_max)}%"
        elif avg >= 50:
            return "twohko", "2HKO"
        elif avg >= 33:
            return "threehko", "3HKO"
        else:
            return "chip", f"{int(avg)}%"

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
        <img src="{sprite_url}" class="sprite" alt="{pokemon_name}">
        <div class="title">
            <div class="name">{pokemon_name}</div>
            <div class="subtitle">vs Top Meta Threats</div>
        </div>
        <div class="speed-badge">{pokemon_speed} Spe</div>
    </div>

    <div class="matrix">
        <div class="matrix-header">
            <div>Threat</div>
            <div>You → Them</div>
            <div>They → You</div>
            <div>Usage</div>
        </div>
        {"".join(f'''
        <div class="threat-row">
            <div class="threat-info">
                <img src="{get_sprite_url(t.get('name', ''))}" class="threat-sprite" onerror="this.style.display='none'">
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
                <span class="toggle-icon">🔄</span> Trick Room
            </div>
            <div class="toggle tailwind" onclick="toggleTailwind(this)">
                <span class="toggle-icon">💨</span> Tailwind
            </div>
        </div>
    </div>

    <div class="timeline" id="timeline">
        {"".join(f'''
        <div class="turn-item">
            <div class="turn-number {'opponent' if p.get('team') == 'opponent' else ''}">{i + 1}</div>
            <div class="turn-content">
                <div class="turn-header">
                    <img src="{get_sprite_url(p.get('name', ''))}" class="pokemon-sprite" onerror="this.style.display='none'">
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
                <img src="{get_sprite_url(p.get('name', ''))}" class="opp-sprite" onerror="this.style.display='none'">
                <span class="opp-name">{p.get('name', 'Unknown')}</span>
            </div>
            ''' for p in opponent_team)}
        </div>
    </div>

    <div class="selection-grid">
        <div class="selection-column">
            <div class="column-header bring">
                <span>✓</span> Bring <span class="count">{len(bring)}/4</span>
            </div>
            <div class="pokemon-list">
                {"".join(f'''
                <div class="pokemon-card selected" data-name="{p.get('name', '')}">
                    <img src="{get_sprite_url(p.get('name', ''))}" class="card-sprite" onerror="this.style.display='none'">
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
                <span>✗</span> Leave <span class="count">{len(leave)}</span>
            </div>
            <div class="pokemon-list">
                {"".join(f'''
                <div class="pokemon-card" data-name="{p.get('name', '')}">
                    <img src="{get_sprite_url(p.get('name', ''))}" class="card-sprite" onerror="this.style.display='none'">
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
                    {"".join(f'<div class="strat-mon"><img src="{get_sprite_url(name)}" class="strat-sprite">{name}</div>' for name in recommendations.get('lead_pair', []))}
                </div>
            </div>
            <div class="strat-section">
                <div class="strat-label">Back</div>
                <div class="strat-pokemon">
                    {"".join(f'<div class="strat-mon"><img src="{get_sprite_url(name)}" class="strat-sprite">{name}</div>' for name in recommendations.get('back_pair', []))}
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

    weather_icons = {"sun": "☀️", "rain": "🌧️", "sand": "🏜️", "snow": "❄️", "hail": "❄️"}
    terrain_icons = {"electric": "⚡", "grassy": "🌿", "psychic": "🔮", "misty": "💨"}

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
        <span class="title-icon">🔗</span>
        Ability Synergy
    </div>

    <div class="team-bar">
        {"".join(f'''
        <div class="team-member">
            <img src="{get_sprite_url(p.get('name', ''))}" class="team-sprite" onerror="this.style.display='none'">
            <div class="team-name">{p.get('name', 'Unknown')}</div>
            <div class="team-ability">{p.get('ability', '')}</div>
        </div>
        ''' for p in team)}
    </div>

    {f'''
    <div class="synergy-section">
        <div class="section-header weather">
            <span class="section-icon">{weather_icons.get(weather.get('type', ''), '🌤️')}</span>
            {weather.get('type', 'Weather').title()} Mode
        </div>
        <div class="section-content">
            <div class="flow-diagram">
                <div class="flow-node setter">
                    <img src="{get_sprite_url(weather.get('setter', ''))}" class="flow-sprite">
                    <div class="flow-name">{weather.get('setter', 'None')}</div>
                    <div class="flow-role">Setter</div>
                </div>
                <div class="flow-arrow">→</div>
                {"".join(f'''
                <div class="flow-node abuser">
                    <img src="{get_sprite_url(abuser)}" class="flow-sprite">
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
            <span class="section-icon">{terrain_icons.get(terrain.get('type', ''), '🌍')}</span>
            {terrain.get('type', 'Terrain').title()} Terrain
        </div>
        <div class="section-content">
            <div class="flow-diagram">
                <div class="flow-node setter">
                    <img src="{get_sprite_url(terrain.get('setter', ''))}" class="flow-sprite">
                    <div class="flow-name">{terrain.get('setter', 'None')}</div>
                    <div class="flow-role">Setter</div>
                </div>
                <div class="flow-arrow">→</div>
                {"".join(f'''
                <div class="flow-node abuser">
                    <img src="{get_sprite_url(abuser)}" class="flow-sprite">
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
            <span class="section-icon">😤</span>
            Intimidate Coverage
        </div>
        <div class="section-content">
            <div class="blocker-grid">
                <div class="blocker-group">
                    <div class="blocker-label">Blockers</div>
                    <div class="blocker-list">
                        {"".join(f'''
                        <div class="blocker-item">
                            <img src="{get_sprite_url(name)}" class="blocker-sprite">
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
                            <img src="{get_sprite_url(name)}" class="blocker-sprite">
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
            <span class="section-icon">✨</span>
            Ability Combos
        </div>
        <div class="section-content">
            {"".join(f'''
            <div class="combo-item">
                <div class="combo-pokemon">
                    {"".join(f'<img src="{get_sprite_url(name)}" class="combo-sprite">' for name in c.get('pokemon', [])[:2])}
                </div>
                <div class="combo-info">
                    <div class="combo-effect">{c.get('effect', '')}</div>
                    <div class="combo-rating">
                        {"".join(f'<span class="rating-star">★</span>' for _ in range(c.get('rating', 3)))}
                        {"".join(f'<span class="rating-star empty">★</span>' for _ in range(5 - c.get('rating', 3)))}
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
            <span class="section-icon">⚠️</span>
            Conflicts
        </div>
        <div class="section-content">
            {"".join(f'''
            <div class="conflict-item">
                <span class="conflict-icon">⚠️</span>
                <span class="conflict-text">{c.get('reason', '')}</span>
            </div>
            ''' for c in conflicts)}
        </div>
    </div>
    ''' if conflicts else ''}

    {f'''
    <div class="empty-state" style="margin-top:20px;">
        ✓ No major synergies or conflicts detected
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
            <span class="section-icon">💡</span>
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
        icon = "❌" if severity == "error" else "⚠️"
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
            <span class="section-icon">⚠️</span>
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
            {'✓ Tournament Ready' if tournament_ready else '✗ Not Tournament Ready'}
        </div>
        <div class="team-preview">
            {"".join(f'<img src="{get_sprite_url(p.get("name", ""))}" class="team-mon" onerror="this.style.display=\'none\'">' for p in team[:6])}
        </div>
    </div>

    <div class="section">
        <div class="section-header">
            <span class="section-icon">📊</span>
            Analysis
        </div>
        <div class="section-content">
            <div class="two-col">
                <div>
                    <div class="col-title strengths">Strengths</div>
                    <ul class="point-list">
                        {"".join(f'<li class="point-item"><span class="point-icon strength">✓</span>{s}</li>' for s in strengths[:5]) or '<li class="point-item" style="color:#64748b">No major strengths identified</li>'}
                    </ul>
                </div>
                <div>
                    <div class="col-title weaknesses">Weaknesses</div>
                    <ul class="point-list">
                        {"".join(f'<li class="point-item"><span class="point-icon weakness">✗</span>{w}</li>' for w in weaknesses[:5]) or '<li class="point-item" style="color:#64748b">No major weaknesses identified</li>'}
                    </ul>
                </div>
            </div>
        </div>
    </div>

    {_build_suggestions_section(suggestions, get_priority_class)}

    {_build_legality_section(legality_issues)}

    <div class="section">
        <div class="section-header">
            <span class="section-icon">🎯</span>
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
            <span class="section-icon">⚡</span>
            Speed Control
        </div>
        <div class="section-content">
            <div class="speed-info">
                <div class="speed-card">
                    <img src="{get_sprite_url(speed_control.get('fastest', ''))}" class="speed-sprite" onerror="this.style.display='none'">
                    <div>
                        <div class="speed-label">Fastest</div>
                        <div class="speed-name">{speed_control.get('fastest', 'N/A')}</div>
                    </div>
                </div>
                <div class="speed-card">
                    <img src="{get_sprite_url(speed_control.get('slowest', ''))}" class="speed-sprite" onerror="this.style.display='none'">
                    <div>
                        <div class="speed-label">Slowest</div>
                        <div class="speed-name">{speed_control.get('slowest', 'N/A')}</div>
                    </div>
                </div>
            </div>
            <div class="control-badges">
                <div class="control-badge {'active' if speed_control.get('has_trick_room') else 'inactive'}">
                    🔄 Trick Room
                </div>
                <div class="control-badge {'active' if speed_control.get('has_tailwind') else 'inactive'}">
                    💨 Tailwind
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
            <span class="analysis-icon">💡</span>
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
        result_emoji = "🟢"
    elif outspeed_percent >= 50:
        result_class = "good"
        result_emoji = "🟡"
    else:
        result_class = "poor"
        result_emoji = "🔴"

    # Create speed tier list
    tiers_html = ""
    for mark in speed_marks:
        tier_class = "outsped" if mark["outspeeds"] else "not-outsped"
        check = "✓" if mark["outspeeds"] else "✗"
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
        status_emoji = "✓"
    elif survival_chance > 0:
        status_class = "possible"
        status_text = f"{survival_chance:.1f}% to survive"
        status_emoji = "?"
    else:
        status_class = "faints"
        status_text = "Faints"
        status_emoji = "✗"

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
                    <img src="{get_sprite_url(attacker_name)}" class="pokemon-sprite" onerror="this.style.display='none'">
                    <span class="pokemon-name">{attacker_name}</span>
                </div>
                <div class="move-badge">{move_name} x{num_hits}</div>
                <div class="pokemon-side">
                    <span class="pokemon-name">{defender_name}</span>
                    <img src="{get_sprite_url(defender_name)}" class="pokemon-sprite" onerror="this.style.display='none'">
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
