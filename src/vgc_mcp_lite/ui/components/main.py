# -*- coding: utf-8 -*-
"""Main UI component builders for VGC Team Builder.

This module contains all the UI component builder functions.
Shared utilities (styles, sprites) are imported from sibling modules.
"""

import json
from typing import Any, Optional

# Import shared utilities from sibling modules
from .styles import get_shared_styles
from .sprites import (
    get_sprite_url,
    get_sprite_html,
    get_type_color,
    SPRITE_PLACEHOLDER,
)


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


def create_damage_calc_table_ui(
    attacker_name: str,
    calcs: list[dict[str, Any]],
    target_spreads: dict[str, list[dict[str, Any]]],
    title: Optional[str] = None,
) -> str:
    """Create damage calculation table with Smogon spread dropdowns.

    Generates a table showing damage calculations against multiple targets,
    with dropdowns populated from real Smogon usage data for each target's spreads.

    Args:
        attacker_name: Name of the attacking Pokemon
        calcs: List of calculation results, each containing:
            - move: Move name
            - target: Target Pokemon name
            - damage_min: Minimum damage %
            - damage_max: Maximum damage %
            - ko_chance: KO result string ("OHKO", "2HKO", etc.)
            - selected_spread_index: Optional index of selected spread (default 0)
        target_spreads: Dict mapping target name (lowercase) to list of Smogon spreads
            Each spread has: nature, evs, usage, item, ability
        title: Optional title for the table (defaults to "Damage Calculation Table")

    Returns:
        HTML string for the damage calculation table
    """
    import json

    styles = get_shared_styles()
    table_title = title or "Damage Calculation Table"

    def format_spread_option(spread: dict, index: int, selected: bool = False) -> str:
        """Format a Smogon spread as a dropdown option."""
        nature = spread.get("nature", "Serious")
        evs = spread.get("evs", {})
        usage = spread.get("usage", 0)
        item = spread.get("item", "")

        # Build EV string (only non-zero stats)
        # Support both abbreviated (hp, atk, def, spa, spd, spe) and full names (attack, defense, etc.)
        ev_parts = []
        stat_order = [
            (["hp"], "HP"),
            (["atk", "attack"], "Atk"),
            (["def", "defense"], "Def"),
            (["spa", "special_attack"], "SpA"),
            (["spd", "special_defense"], "SpD"),
            (["spe", "speed"], "Spe"),
        ]
        for stat_keys, label in stat_order:
            val = 0
            for key in stat_keys:
                if key in evs:
                    val = evs[key]
                    break
            if val > 0:
                ev_parts.append(f"{val} {label}")

        ev_str = " / ".join(ev_parts) if ev_parts else "No EVs"

        # Abbreviate common items
        item_abbrev = {
            "Assault Vest": "AV",
            "Choice Scarf": "Scarf",
            "Choice Specs": "Specs",
            "Choice Band": "Band",
            "Life Orb": "LO",
            "Focus Sash": "Sash",
            "Booster Energy": "BE",
            "Leftovers": "Lefties",
            "Rocky Helmet": "Helmet",
            "Safety Goggles": "Goggles",
        }
        item_display = item_abbrev.get(item, item[:8] + "..." if len(item) > 10 else item)
        item_suffix = f" ({item_display})" if item else ""

        # Build data attributes for JS recalculation
        evs_json = json.dumps(evs).replace('"', "&quot;")
        selected_attr = " selected" if selected else ""

        return f'''<option value="{index}" data-nature="{nature}" data-evs="{evs_json}" data-item="{item}"{selected_attr}>{nature} {ev_str}{item_suffix}</option>'''

    def get_ko_badge_class(ko_chance: str) -> str:
        """Get CSS class for KO badge based on result."""
        ko_upper = ko_chance.upper()
        if "OHKO" in ko_upper:
            return "ohko"
        elif "2HKO" in ko_upper:
            return "2hko"
        elif "3HKO" in ko_upper:
            return "3hko"
        elif "4HKO" in ko_upper:
            return "4hko"
        return "survive"

    # Build table rows
    rows_html = ""
    for i, calc in enumerate(calcs):
        move = calc.get("move", "Unknown Move")
        target = calc.get("target", "Unknown")
        damage_min = calc.get("damage_min", 0)
        damage_max = calc.get("damage_max", 0)
        ko_chance = calc.get("ko_chance", "")
        selected_idx = calc.get("selected_spread_index", 0)

        # Get spreads for this target
        target_key = target.lower().replace(" ", "-")
        spreads = target_spreads.get(target_key, target_spreads.get(target.lower(), []))

        # Build spread dropdown options
        if spreads:
            options_html = ""
            for j, spread in enumerate(spreads[:10]):  # Max 10 spreads
                options_html += format_spread_option(spread, j, selected=(j == selected_idx))
            dropdown_html = f'''<select class="spread-dropdown" data-target="{target_key}" data-row="{i}" onchange="updateDamageRow(this, {i})">{options_html}</select>'''
        else:
            dropdown_html = '<span class="text-muted">No data</span>'

        # Format damage display
        damage_str = f"{damage_min:.0f}-{damage_max:.0f}%"

        # KO badge
        ko_class = get_ko_badge_class(ko_chance)

        rows_html += f'''
                    <tr data-row="{i}">
                        <td>{move}</td>
                        <td>{target}</td>
                        <td>{dropdown_html}</td>
                        <td class="damage-cell">{damage_str}</td>
                        <td class="result-cell"><span class="ko-badge {ko_class}">{ko_chance}</span></td>
                    </tr>'''

    # JavaScript for dropdown interaction
    js_code = """
    <script>
    function updateDamageRow(select, rowIndex) {
        const option = select.options[select.selectedIndex];
        const nature = option.dataset.nature;
        const evs = JSON.parse(option.dataset.evs.replace(/&quot;/g, '"'));
        const item = option.dataset.item;

        // Dispatch custom event for parent to handle recalculation
        const event = new CustomEvent('spreadChanged', {
            detail: {
                rowIndex: rowIndex,
                target: select.dataset.target,
                nature: nature,
                evs: evs,
                item: item
            },
            bubbles: true
        });
        select.dispatchEvent(event);

        // Visual feedback
        const row = select.closest('tr');
        row.style.transition = 'background 0.3s ease';
        row.style.background = 'rgba(99, 102, 241, 0.15)';
        setTimeout(() => {
            row.style.background = '';
        }, 300);
    }
    </script>
    """

    return f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
    <style>
{styles}

/* Damage calc table specific styles */
.calc-table-container {{
    background: rgba(255, 255, 255, 0.03);
    backdrop-filter: blur(20px);
    -webkit-backdrop-filter: blur(20px);
    border-radius: 16px;
    border: 1px solid rgba(255, 255, 255, 0.08);
    padding: 20px;
    margin: 16px 0;
}}

.calc-table-title {{
    font-size: 18px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 16px;
    padding-bottom: 12px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: linear-gradient(135deg, #fff 0%, #a78bfa 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
}}

.modern-table {{
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
}}

.modern-table th {{
    text-align: left;
    padding: 12px 16px;
    background: rgba(99, 102, 241, 0.1);
    color: #a1a1aa;
    font-weight: 600;
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
}}

.modern-table th:first-child {{
    border-radius: 8px 0 0 0;
}}

.modern-table th:last-child {{
    border-radius: 0 8px 0 0;
}}

.modern-table td {{
    padding: 12px 16px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
    color: #e4e4e7;
}}

.modern-table tr:hover td {{
    background: rgba(255, 255, 255, 0.03);
}}

.modern-table tr:last-child td:first-child {{
    border-radius: 0 0 0 8px;
}}

.modern-table tr:last-child td:last-child {{
    border-radius: 0 0 8px 0;
}}

.spread-dropdown {{
    background: rgba(24, 24, 27, 0.8);
    border: 1px solid rgba(99, 102, 241, 0.3);
    border-radius: 8px;
    color: #e4e4e7;
    padding: 8px 12px;
    font-size: 13px;
    cursor: pointer;
    min-width: 280px;
    max-width: 350px;
    transition: all 0.2s ease;
}}

.spread-dropdown:hover {{
    border-color: rgba(139, 92, 246, 0.5);
    background: rgba(99, 102, 241, 0.1);
}}

.spread-dropdown:focus {{
    outline: none;
    border-color: #8b5cf6;
    box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.2);
}}

.spread-dropdown option {{
    background: #1a1a2e;
    color: #e4e4e7;
    padding: 8px;
}}

.damage-cell {{
    font-family: 'SF Mono', 'Consolas', monospace;
    font-weight: 600;
    color: #fff;
}}

.result-cell {{
    text-align: center;
}}

.ko-badge {{
    display: inline-block;
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
}}

.ko-badge.ohko {{
    background: linear-gradient(135deg, #ef4444 0%, #dc2626 100%);
    color: #fff;
    box-shadow: 0 2px 8px rgba(239, 68, 68, 0.3);
}}

.ko-badge.2hko {{
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    color: #fff;
    box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
}}

.ko-badge.3hko {{
    background: linear-gradient(135deg, #eab308 0%, #ca8a04 100%);
    color: #1a1a1a;
    box-shadow: 0 2px 8px rgba(234, 179, 8, 0.3);
}}

.ko-badge.4hko {{
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: #fff;
    box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
}}

.ko-badge.survive {{
    background: linear-gradient(135deg, #22c55e 0%, #16a34a 100%);
    color: #fff;
    box-shadow: 0 2px 8px rgba(34, 197, 94, 0.3);
}}

.text-muted {{
    color: #71717a;
    font-style: italic;
}}
    </style>
</head>
<body style="background: linear-gradient(135deg, #0c0c14 0%, #12121f 50%, #0a0a12 100%); min-height: 100vh; padding: 20px; font-family: 'Inter', sans-serif;">
    <div class="calc-table-container">
        <div class="calc-table-title">{table_title}</div>
        <table class="modern-table" id="damage-table">
            <thead>
                <tr>
                    <th>Move</th>
                    <th>Target</th>
                    <th>Spread</th>
                    <th>Damage</th>
                    <th>Result</th>
                </tr>
            </thead>
            <tbody>{rows_html}
            </tbody>
        </table>
    </div>
    {js_code}
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
        evs_html = " / ".join(ev_parts) if ev_parts else '<span style="color: #666;">No EVs</span>'

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
    user_base_speed: Optional[int] = None,
) -> str:
    """Create speed tier analyzer UI HTML with race track visualization.

    Args:
        pokemon_name: Name of the Pokemon being analyzed
        pokemon_speed: Calculated speed stat
        speed_tiers: List of dicts with keys: name, speed, common (bool)
        modifiers: Active modifiers dict (tailwind, trick_room, paralysis, choice_scarf)
        user_base_speed: Base speed stat for the user's Pokemon (for JS recalculation)

    Returns:
        HTML string for the speed tier UI
    """
    # Store user's base speed for JavaScript interactivity
    base_speed_for_js = user_base_speed if user_base_speed else pokemon_speed
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
        <div class="race-lane {lane_class}" data-speed="{tier_speed}" data-base-speed="{tier_speed}" data-is-user="{'true' if is_user else 'false'}" style="animation-delay: {delay}s;">
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
    <script>
    (function() {{
        // User's Pokemon data
        const userBaseSpeed = {base_speed_for_js};
        const userCurrentSpeed = {pokemon_speed};

        // Modifier state
        const modifiers = {{
            tailwind: {'true' if modifiers.get('tailwind') else 'false'},
            trick_room: {'true' if modifiers.get('trick_room') else 'false'},
            choice_scarf: {'true' if modifiers.get('choice_scarf') else 'false'},
            paralysis: {'true' if modifiers.get('paralysis') else 'false'}
        }};

        // Apply speed modifiers (Tailwind x2, Scarf x1.5, Paralysis x0.5)
        function applyModifiers(speed) {{
            let modified = speed;
            if (modifiers.tailwind) modified *= 2;
            if (modifiers.choice_scarf) modified *= 1.5;
            if (modifiers.paralysis) modified *= 0.5;
            return Math.floor(modified);
        }}

        // Toggle modifier and update UI
        function toggleModifier(btn, mod) {{
            modifiers[mod] = !modifiers[mod];
            btn.classList.toggle('active', modifiers[mod]);
            updateSpeedTiers();
        }}

        // Update all speed tiers based on current modifiers
        function updateSpeedTiers() {{
            const lanesContainer = document.querySelector('.lanes-container');
            const lanes = Array.from(lanesContainer.querySelectorAll('.race-lane'));

            // Recalculate user's speed with modifiers
            const userLane = lanes.find(l => l.dataset.isUser === 'true');
            const newUserSpeed = applyModifiers(userCurrentSpeed);

            // Update user's displayed speed
            if (userLane) {{
                userLane.dataset.speed = newUserSpeed;
                userLane.querySelector('.lane-speed').textContent = newUserSpeed;
            }}

            // Get all speeds for range calculation
            const allSpeeds = lanes.map(l => parseInt(l.dataset.speed));
            const maxSpeed = Math.max(...allSpeeds);
            const minSpeed = Math.min(...allSpeeds);

            // Sort lanes: Trick Room = ascending (slowest first), Normal = descending
            lanes.sort((a, b) => {{
                const speedA = parseInt(a.dataset.speed);
                const speedB = parseInt(b.dataset.speed);
                return modifiers.trick_room ? (speedA - speedB) : (speedB - speedA);
            }});

            // Re-append in sorted order and update positions, classes, and track bars
            lanes.forEach((lane, idx) => {{
                // Update position number
                lane.querySelector('.lane-position').textContent = '#' + (idx + 1);
                lanesContainer.appendChild(lane);

                const laneSpeed = parseInt(lane.dataset.speed);
                const isUser = lane.dataset.isUser === 'true';

                // Update lane class based on new comparison
                if (!isUser) {{
                    lane.classList.remove('faster-lane', 'slower-lane', 'tie-lane');

                    // Check for speed tie with user
                    const speedTieBadge = lane.querySelector('.speed-tie-badge');
                    if (speedTieBadge) speedTieBadge.remove();

                    if (laneSpeed === newUserSpeed) {{
                        lane.classList.add('tie-lane');
                        // Add speed tie badge
                        const nameSpan = lane.querySelector('.racer-name');
                        if (nameSpan && !lane.querySelector('.speed-tie-badge')) {{
                            const badge = document.createElement('span');
                            badge.className = 'speed-tie-badge';
                            badge.textContent = 'SPEED TIE';
                            nameSpan.parentNode.appendChild(badge);
                        }}
                    }} else if (modifiers.trick_room) {{
                        // In Trick Room, lower speed = moves first = "faster"
                        lane.classList.add(laneSpeed < newUserSpeed ? 'faster-lane' : 'slower-lane');
                    }} else {{
                        lane.classList.add(laneSpeed > newUserSpeed ? 'faster-lane' : 'slower-lane');
                    }}
                }}

                // Update track bar position
                let positionPct = 50;
                if (maxSpeed > minSpeed) {{
                    if (modifiers.trick_room) {{
                        positionPct = 100 - ((laneSpeed - minSpeed) / (maxSpeed - minSpeed) * 100);
                    }} else {{
                        positionPct = (laneSpeed - minSpeed) / (maxSpeed - minSpeed) * 100;
                    }}
                }}
                const trackFill = lane.querySelector('.track-fill');
                const trackMarker = lane.querySelector('.track-marker');
                if (trackFill) trackFill.style.width = positionPct + '%';
                if (trackMarker) trackMarker.style.left = positionPct + '%';
            }});

            // Update summary counts
            updateSummaryCounts(newUserSpeed, lanes);
        }}

        // Update the Faster/Ties/Slower counts in the header
        function updateSummaryCounts(userSpeed, lanes) {{
            let faster = 0, slower = 0, ties = 0;

            lanes.forEach(lane => {{
                if (lane.dataset.isUser === 'true') return;
                const speed = parseInt(lane.dataset.speed);
                if (speed === userSpeed) {{
                    ties++;
                }} else if (modifiers.trick_room ? speed < userSpeed : speed > userSpeed) {{
                    faster++;
                }} else {{
                    slower++;
                }}
            }});

            const fasterEl = document.querySelector('.summary-stat.faster');
            const tiesEl = document.querySelector('.summary-stat.ties');
            const slowerEl = document.querySelector('.summary-stat.slower');

            if (fasterEl) fasterEl.textContent = faster + ' Faster';
            if (tiesEl) tiesEl.textContent = ties + ' Ties';
            if (slowerEl) slowerEl.textContent = slower + ' Slower';
        }}

        // Attach click handlers to modifier buttons
        document.querySelectorAll('.mod-btn').forEach(btn => {{
            btn.addEventListener('click', () => {{
                const mod = btn.dataset.mod;
                toggleModifier(btn, mod);
            }});
        }});
    }})();
    </script>
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
    rating: int = 0,
    format_name: str = "VGC",
    month_display: str = "",
) -> str:
    """Create an interactive usage statistics UI component.

    Shows competitive usage data with visual bars and organized sections.

    Args:
        pokemon_name: Pokemon name
        usage_percent: Overall usage percentage
        items: List of item dicts with 'name' and 'percent' keys
        abilities: List of ability dicts with 'name' and 'percent' keys
        moves: List of move dicts with 'name' and 'percent' keys
        spreads: List of spread dicts with 'nature', 'evs', and 'percent' keys
        tera_types: Optional list of tera type dicts with 'type' and 'percent' keys
        teammates: Optional list of teammate dicts with 'name' and 'percent' keys
        rating: ELO rating cutoff (0, 1500, 1630, 1760)
        format_name: Format name for display (e.g., "VGC Reg F")
        month_display: Month display string (e.g., "December 2025 Usage Stats")
    """
    # Generate sprite HTML
    sprite_html = get_sprite_html(pokemon_name, size=96, css_class="usage-sprite")

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
        ev_labels = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}
        ev_parts = []
        for stat in ["hp", "atk", "def", "spa", "spd", "spe"]:
            val = evs.get(stat, 0)
            if val > 0:
                ev_parts.append(f"{val} {ev_labels[stat]}")
        ev_str = " / ".join(ev_parts) if ev_parts else "No EVs"
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

        .usage-sprite {{
            width: 96px;
            height: 96px;
            margin-bottom: 8px;
            image-rendering: pixelated;
        }}

        .format-badge {{
            display: inline-block;
            background: rgba(255, 255, 255, 0.1);
            padding: 4px 12px;
            border-radius: 12px;
            font-size: 12px;
            color: #a0a0a0;
            margin-top: 8px;
        }}

        .header-row {{
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 12px;
            margin-top: 8px;
            flex-wrap: wrap;
        }}

        .elo-selector {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .elo-selector label {{
            font-size: 12px;
            color: #a0a0a0;
        }}

        .elo-selector select {{
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.2);
            border-radius: 8px;
            padding: 4px 8px;
            font-size: 12px;
            color: #e0e0e0;
            cursor: pointer;
        }}

        .elo-selector select:hover {{
            border-color: rgba(255, 255, 255, 0.4);
        }}

        .month-display {{
            font-size: 11px;
            color: #808080;
            margin-top: 4px;
        }}

        .rating-notice {{
            display: none;
            background: rgba(74, 144, 217, 0.2);
            border: 1px solid rgba(74, 144, 217, 0.4);
            border-radius: 8px;
            padding: 8px 12px;
            font-size: 11px;
            color: #8ab4f8;
            margin-top: 8px;
            text-align: center;
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
            {sprite_html}
            <div class="pokemon-name">{pokemon_name}</div>
            <div class="usage-badge">{usage_percent:.2f}% Usage</div>
            <div class="header-row">
                <div class="format-badge">{format_name}</div>
                <div class="elo-selector">
                    <label>ELO Rating:</label>
                    <select id="elo-select" onchange="changeRating(this.value)">
                        <option value="0" {'selected' if rating == 0 else ''}>All</option>
                        <option value="1500" {'selected' if rating == 1500 else ''}>1500+</option>
                        <option value="1630" {'selected' if rating == 1630 else ''}>1630+</option>
                        <option value="1760" {'selected' if rating == 1760 else ''}>1760+</option>
                    </select>
                </div>
            </div>
            {f'<div class="month-display">{month_display}</div>' if month_display else ''}
            <div id="rating-notice" class="rating-notice"></div>
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
    <script>
        const currentRating = {rating};
        const pokemonName = "{pokemon_name}";

        function changeRating(newRating) {{
            newRating = parseInt(newRating);
            if (newRating !== currentRating) {{
                const notice = document.getElementById('rating-notice');
                notice.innerHTML = 'To see ' + newRating + '+ ELO data, ask Claude:<br><code>get_usage_stats("' + pokemonName + '", rating=' + newRating + ')</code>';
                notice.style.display = 'block';
            }} else {{
                document.getElementById('rating-notice').style.display = 'none';
            }}
        }}
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


def create_calc_history_ui(
    calculations: list[dict[str, Any]],
) -> str:
    """Create calculation history UI HTML with expandable details.

    Args:
        calculations: List of calc dicts with keys:
            Basic: attacker, defender, move, damage_min, damage_max, ko_chance, timestamp
            Attacker details: attacker_item, attacker_ability, attacker_nature, attacker_evs, attacker_tera, attacker_tera_active
            Defender details: defender_item, defender_ability, defender_nature, defender_evs, defender_tera, defender_tera_active
            Move details: move_type, base_power, type_effectiveness, modifiers, damage_hp_min, damage_hp_max, defender_hp

    Returns:
        HTML string for the calc history UI with expandable cards
    """
    import html as html_module
    import json

    # Type colors for move type badges and tera
    type_colors = {
        "normal": "#A8A878", "fire": "#F08030", "water": "#6890F0", "electric": "#F8D030",
        "grass": "#78C850", "ice": "#98D8D8", "fighting": "#C03028", "poison": "#A040A0",
        "ground": "#E0C068", "flying": "#A890F0", "psychic": "#F85888", "bug": "#A8B820",
        "rock": "#B8A038", "ghost": "#705898", "dragon": "#7038F8", "dark": "#705848",
        "steel": "#B8B8D0", "fairy": "#EE99AC",
    }

    def format_evs(evs: dict) -> str:
        """Format EVs as compact string like '252 HP / 4 Atk / 252 Spe'."""
        if not evs:
            return "No EVs"
        parts = []
        stat_names = {"hp": "HP", "atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}
        for stat, name in stat_names.items():
            val = evs.get(stat, 0)
            if val > 0:
                parts.append(f"{val} {name}")
        return " / ".join(parts) if parts else "No EVs"

    def get_effectiveness_text(mult: float) -> tuple[str, str]:
        """Get effectiveness text and CSS class."""
        if mult >= 4:
            return "4x Super Effective", "super-effective-4x"
        elif mult >= 2:
            return "Super Effective", "super-effective"
        elif mult == 1:
            return "Neutral", "neutral"
        elif mult >= 0.5:
            return "Resisted", "resisted"
        elif mult >= 0.25:
            return "4x Resisted", "resisted-4x"
        else:
            return "Immune", "immune"

    # Build history entries
    entries_html = ""
    for i, calc in enumerate(calculations[:10]):  # Show last 10
        # Basic fields
        attacker = calc.get("attacker", "Unknown")
        defender = calc.get("defender", "Unknown")
        move = calc.get("move", "Unknown")
        dmg_min = calc.get("damage_min", 0)
        dmg_max = calc.get("damage_max", 0)
        ko_chance = calc.get("ko_chance", "")

        # Attacker details
        atk_item = calc.get("attacker_item", "")
        atk_ability = calc.get("attacker_ability", "")
        atk_nature = calc.get("attacker_nature", "")
        atk_evs = calc.get("attacker_evs", {})
        atk_tera = calc.get("attacker_tera", "")
        atk_tera_active = calc.get("attacker_tera_active", False)

        # Defender details
        def_item = calc.get("defender_item", "")
        def_ability = calc.get("defender_ability", "")
        def_nature = calc.get("defender_nature", "")
        def_evs = calc.get("defender_evs", {})
        def_tera = calc.get("defender_tera", "")
        def_tera_active = calc.get("defender_tera_active", False)

        # Move details
        move_type = calc.get("move_type", "")
        base_power = calc.get("base_power", 0)
        type_eff = calc.get("type_effectiveness", 1.0)
        modifiers = calc.get("modifiers", [])
        dmg_hp_min = calc.get("damage_hp_min", 0)
        dmg_hp_max = calc.get("damage_hp_max", 0)
        defender_hp = calc.get("defender_hp", 0)

        # KO badge styling
        ko_class = "survive"
        if "OHKO" in ko_chance.upper():
            ko_class = "ohko"
        elif "2HKO" in ko_chance.upper():
            ko_class = "2hko"
        elif "3HKO" in ko_chance.upper():
            ko_class = "3hko"

        delay = i * 0.05

        # Format EVs
        atk_ev_str = format_evs(atk_evs)
        def_ev_str = format_evs(def_evs)

        # Move type color
        move_type_color = type_colors.get(move_type.lower(), "#888") if move_type else "#888"

        # Tera badges
        atk_tera_color = type_colors.get(atk_tera.lower(), "#888") if atk_tera else "#888"
        def_tera_color = type_colors.get(def_tera.lower(), "#888") if def_tera else "#888"

        atk_tera_html = ""
        if atk_tera:
            active_class = "active" if atk_tera_active else ""
            atk_tera_html = f'<span class="tera-badge {active_class}" style="background: {atk_tera_color};">Tera {atk_tera}</span>'

        def_tera_html = ""
        if def_tera:
            active_class = "active" if def_tera_active else ""
            def_tera_html = f'<span class="tera-badge {active_class}" style="background: {def_tera_color};">Tera {def_tera}</span>'

        # Type effectiveness
        eff_text, eff_class = get_effectiveness_text(type_eff)
        eff_html = f'<span class="effectiveness-badge {eff_class}">{eff_text}</span>' if type_eff != 1.0 else ""

        # Modifiers as pills
        modifiers_html = ""
        if modifiers:
            for mod in modifiers[:6]:  # Limit to 6 modifiers
                modifiers_html += f'<span class="modifier-pill">{html_module.escape(str(mod))}</span>'

        # HP bar calculations
        avg_dmg = (dmg_min + dmg_max) / 2
        hp_remaining = max(0, 100 - avg_dmg)
        dmg_range_width = dmg_max - dmg_min
        dmg_range_left = 100 - dmg_max

        # Check if we have detailed data
        has_details = bool(atk_item or atk_ability or atk_nature or def_item or def_ability or def_nature or move_type)

        entries_html += f"""
        <div class="history-entry" data-index="{i}" style="animation-delay: {delay}s;">
            <div class="entry-summary" onclick="toggleCalcDetails({i})">
                <div class="entry-pokemon">
                    {get_sprite_html(attacker, size=40, css_class="entry-sprite")}
                    <span class="entry-arrow">&#10140;</span>
                    {get_sprite_html(defender, size=40, css_class="entry-sprite")}
                </div>
                <div class="entry-info">
                    <div class="entry-move">{html_module.escape(move)}</div>
                    <div class="entry-damage">{dmg_min:.1f}% - {dmg_max:.1f}%</div>
                </div>
                <div class="entry-ko-badge {ko_class}">{html_module.escape(ko_chance)}</div>
                <div class="expand-icon">&#9660;</div>
            </div>
            <div class="entry-details" id="details-{i}">
                <!-- Attacker Section -->
                <div class="detail-section attacker-section">
                    <div class="section-header">
                        {get_sprite_html(attacker, size=32, css_class="mini-sprite")}
                        <span class="pokemon-name">{html_module.escape(attacker)}</span>
                        {atk_tera_html}
                    </div>
                    <div class="spread-line">
                        <span class="nature">{html_module.escape(atk_nature) if atk_nature else "Unknown Nature"}</span>
                        <span class="evs">{html_module.escape(atk_ev_str)}</span>
                    </div>
                    <div class="equip-line">
                        <span class="item">@ {html_module.escape(atk_item) if atk_item else "No Item"}</span>
                        <span class="ability">[{html_module.escape(atk_ability) if atk_ability else "Unknown"}]</span>
                    </div>
                </div>

                <!-- Move Section -->
                <div class="detail-section move-section">
                    <div class="move-header">
                        <span class="move-name">{html_module.escape(move)}</span>
                        {f'<span class="move-type-badge" style="background: {move_type_color};">{html_module.escape(move_type.capitalize())}</span>' if move_type else ""}
                        {f'<span class="base-power">{base_power} BP</span>' if base_power else ""}
                    </div>
                    {eff_html}
                    {f'<div class="modifiers">{modifiers_html}</div>' if modifiers_html else ""}
                </div>

                <!-- Defender Section -->
                <div class="detail-section defender-section">
                    <div class="section-header">
                        {get_sprite_html(defender, size=32, css_class="mini-sprite")}
                        <span class="pokemon-name">{html_module.escape(defender)}</span>
                        {def_tera_html}
                    </div>
                    <div class="spread-line">
                        <span class="nature">{html_module.escape(def_nature) if def_nature else "Unknown Nature"}</span>
                        <span class="evs">{html_module.escape(def_ev_str)}</span>
                    </div>
                    <div class="equip-line">
                        <span class="item">@ {html_module.escape(def_item) if def_item else "No Item"}</span>
                        <span class="ability">[{html_module.escape(def_ability) if def_ability else "Unknown"}]</span>
                    </div>
                </div>

                <!-- Damage Summary -->
                <div class="detail-section damage-section">
                    <div class="damage-values">
                        {f'<span class="damage-hp">{dmg_hp_min}-{dmg_hp_max} / {defender_hp} HP</span>' if defender_hp else ""}
                        <span class="damage-pct">{dmg_min:.1f}% - {dmg_max:.1f}%</span>
                    </div>
                    <div class="hp-bar">
                        <div class="hp-fill" style="width: {hp_remaining}%;"></div>
                        <div class="damage-range" style="left: {dmg_range_left}%; width: {dmg_range_width}%;"></div>
                    </div>
                    <div class="ko-verdict {ko_class}">{html_module.escape(ko_chance)}</div>
                </div>
            </div>
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
    max-width: 700px;
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

/* Expandable entry card */
.history-entry {{
    border-bottom: 1px solid rgba(255, 255, 255, 0.04);
    animation: fadeSlideIn 0.4s cubic-bezier(0.4, 0, 0.2, 1) backwards;
    transition: background 0.3s ease;
}}

.history-entry:last-child {{
    border-bottom: none;
}}

.history-entry.expanded {{
    background: rgba(255, 255, 255, 0.04);
}}

/* Summary row (always visible) */
.entry-summary {{
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 14px 20px;
    cursor: pointer;
    transition: background 0.2s ease;
}}

.entry-summary:hover {{
    background: rgba(255, 255, 255, 0.03);
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

.entry-info {{
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

.expand-icon {{
    font-size: 12px;
    color: #71717a;
    transition: transform 0.3s ease;
    margin-left: 8px;
}}

.history-entry.expanded .expand-icon {{
    transform: rotate(180deg);
}}

/* Expanded details panel */
.entry-details {{
    display: none;
    padding: 0 20px 16px;
    border-top: 1px solid rgba(255, 255, 255, 0.06);
}}

.history-entry.expanded .entry-details {{
    display: block;
}}

/* Detail sections */
.detail-section {{
    padding: 12px;
    margin-top: 12px;
    background: rgba(0, 0, 0, 0.25);
    border-radius: 8px;
}}

.attacker-section {{
    border-left: 3px solid #60a5fa;
}}

.defender-section {{
    border-left: 3px solid #f87171;
}}

.move-section {{
    border-left: 3px solid #a78bfa;
}}

.damage-section {{
    border-left: 3px solid #fbbf24;
}}

.section-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 8px;
    flex-wrap: wrap;
}}

.pokemon-name {{
    font-weight: 600;
    font-size: 14px;
    color: #fff;
}}

.mini-sprite {{
    width: 32px;
    height: 32px;
    image-rendering: auto;
}}

.spread-line, .equip-line {{
    font-size: 12px;
    color: #a1a1aa;
    margin-top: 4px;
}}

.nature {{
    color: #fbbf24;
    font-weight: 500;
}}

.evs {{
    margin-left: 8px;
    color: #71717a;
}}

.item {{
    color: #a78bfa;
}}

.ability {{
    color: #60a5fa;
    margin-left: 8px;
}}

/* Tera badge */
.tera-badge {{
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    color: #fff;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
}}

.tera-badge.active {{
    box-shadow: 0 0 8px currentColor;
}}

/* Move section */
.move-header {{
    display: flex;
    align-items: center;
    gap: 8px;
    flex-wrap: wrap;
}}

.move-name {{
    font-weight: 600;
    font-size: 14px;
    color: #fff;
}}

.move-type-badge {{
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    color: #fff;
    text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
    text-transform: capitalize;
}}

.base-power {{
    font-size: 11px;
    color: #71717a;
    margin-left: 4px;
}}

/* Type effectiveness badges */
.effectiveness-badge {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 10px;
    font-weight: 600;
    margin-top: 8px;
}}

.effectiveness-badge.super-effective-4x {{
    background: rgba(239, 68, 68, 0.3);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
}}

.effectiveness-badge.super-effective {{
    background: rgba(249, 115, 22, 0.3);
    color: #fb923c;
    border: 1px solid rgba(249, 115, 22, 0.4);
}}

.effectiveness-badge.neutral {{
    background: rgba(161, 161, 170, 0.2);
    color: #a1a1aa;
    border: 1px solid rgba(161, 161, 170, 0.3);
}}

.effectiveness-badge.resisted {{
    background: rgba(34, 197, 94, 0.2);
    color: #4ade80;
    border: 1px solid rgba(34, 197, 94, 0.3);
}}

.effectiveness-badge.resisted-4x {{
    background: rgba(34, 197, 94, 0.3);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.5);
}}

.effectiveness-badge.immune {{
    background: rgba(113, 113, 122, 0.3);
    color: #a1a1aa;
    border: 1px solid rgba(113, 113, 122, 0.4);
}}

/* Modifiers */
.modifiers {{
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
    margin-top: 8px;
}}

.modifier-pill {{
    font-size: 10px;
    padding: 2px 6px;
    background: rgba(255, 255, 255, 0.08);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 4px;
    color: #a1a1aa;
}}

/* Damage section */
.damage-values {{
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 8px;
}}

.damage-hp {{
    font-size: 14px;
    font-weight: 600;
    color: #fff;
}}

.damage-pct {{
    font-size: 12px;
    color: #71717a;
}}

/* HP bar */
.hp-bar {{
    height: 10px;
    background: #22c55e;
    border-radius: 5px;
    position: relative;
    overflow: hidden;
    margin-bottom: 8px;
}}

.hp-fill {{
    position: absolute;
    left: 0;
    top: 0;
    height: 100%;
    background: #22c55e;
    border-radius: 5px;
}}

.damage-range {{
    position: absolute;
    top: 0;
    height: 100%;
    background: linear-gradient(90deg, #ef4444, #f87171);
    opacity: 0.9;
}}

.ko-verdict {{
    font-size: 13px;
    font-weight: 600;
    text-transform: uppercase;
}}

.ko-verdict.ohko {{ color: #f87171; }}
.ko-verdict.2hko {{ color: #fb923c; }}
.ko-verdict.3hko {{ color: #fbbf24; }}
.ko-verdict.survive {{ color: #4ade80; }}

/* Empty state */
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

    <script>
    function toggleCalcDetails(index) {{
        const entry = document.querySelector(`.history-entry[data-index="${{index}}"]`);
        if (!entry) return;

        const isExpanded = entry.classList.contains('expanded');

        // Close all other entries
        document.querySelectorAll('.history-entry.expanded').forEach(e => {{
            if (e !== entry) {{
                e.classList.remove('expanded');
            }}
        }});

        // Toggle this entry
        if (isExpanded) {{
            entry.classList.remove('expanded');
        }} else {{
            entry.classList.add('expanded');
        }}
    }}
    </script>
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
    base_speed: Optional[int] = None,
    nature: str = "Serious",
    speed_evs: int = 0,
    all_pokemon_names: Optional[list[str]] = None,
) -> str:
    """Create an interactive Pikalytics-style histogram with searchable Pokemon dropdown.

    Features:
    - Pikalytics-style red bar histogram with green user-bar highlight
    - Searchable Pokemon dropdown to switch targets (shows all Pokemon if provided)
    - Speed controls (Nature/EVs/modifiers) to adjust your Pokemon's speed
    - Y-axis with percentage labels, grid lines

    Args:
        pokemon_name: Your Pokemon's name
        pokemon_speed: Your Pokemon's speed stat (initial calculated value)
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
        base_speed: Your Pokemon's base speed stat (for recalculation). If None, speed controls hidden.
        nature: Your Pokemon's current nature (default "Serious")
        speed_evs: Your Pokemon's current Speed EVs (default 0)
        all_pokemon_names: Optional list of all Pokemon names for dropdown.
            If provided, shows all Pokemon in dropdown (even if not in all_targets_data).
            Pokemon not in all_targets_data will show a message to re-run with that target.

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
    # Include user's speed in range calculation so they're always visible on chart
    speed_min = min(initial_stats.get("min", 50), pokemon_speed)
    speed_max = max(initial_stats.get("max", 200), pokemon_speed)
    speed_range = speed_max - speed_min if speed_max > speed_min else 1
    max_usage = max(usages) if usages else 1

    # Build histogram bars - Pikalytics style (red bars, green for user speed)
    bars_html = ""
    sorted_dist = sorted(initial_dist, key=lambda x: x.get("speed", 0))
    for entry in sorted_dist:
        speed = entry.get("speed", 0)
        usage = entry.get("usage", entry.get("count", 1))
        height_pct = (usage / max_usage) * 95 if max_usage > 0 else 0
        x_pos = ((speed - speed_min) / speed_range) * 100 if speed_range > 0 else 50
        is_user_speed = abs(speed - pokemon_speed) <= 2
        bar_class = "user-bar" if is_user_speed else ""
        bars_html += f'<div class="hist-bar {bar_class}" data-speed="{speed}" style="left:{x_pos}%;height:{height_pct}%;" title="{speed} Spe: {usage:.1f}%"></div>'

    # Calculate user speed marker position
    user_x_pos = ((pokemon_speed - speed_min) / speed_range) * 100 if speed_range > 0 else 50
    user_x_pos = max(0, min(100, user_x_pos))

    # Calculate outspeed percentage
    outsped_usage = sum(u for s, u in zip(speeds, usages) if pokemon_speed > s)
    total_usage = sum(usages) if usages else 1
    outspeed_pct = (outsped_usage / total_usage * 100) if total_usage > 0 else 0
    result_class = "excellent" if outspeed_pct >= 80 else "good" if outspeed_pct >= 50 else "poor"

    # Generate X-axis labels
    x_labels = []
    num_labels = 8
    for i in range(num_labels):
        speed_val = int(speed_min + (speed_range * i / (num_labels - 1)))
        x_labels.append(speed_val)
    x_labels_html = " ".join(f'<span>{v}</span>' for v in x_labels)

    # Build datalist options for searchable dropdown
    # If all_pokemon_names provided, show all of them (even if not loaded)
    # Otherwise, just show loaded Pokemon from all_targets_data
    if all_pokemon_names:
        # Mark which Pokemon have loaded data
        loaded_keys = set(all_targets_data.keys())
        datalist_options = "".join(
            f'<option value="{n.replace("-", " ").title()}" data-key="{n.lower().replace(" ", "-")}" data-loaded="{"true" if n.lower().replace(" ", "-") in loaded_keys else "false"}"></option>'
            for n in sorted(all_pokemon_names)
        )
    else:
        datalist_options = "".join(
            f'<option value="{n.replace("-", " ").title()}" data-key="{n}" data-loaded="true"></option>'
            for n in sorted(all_targets_data.keys())
        )
    return f'''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<style>
{styles}
.histogram-container {{background:var(--bg-card);border-radius:var(--radius-lg);padding:var(--space-lg);border:1px solid var(--glass-border)}}
.histogram-header {{display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:var(--space-lg)}}
.histogram-title {{font-size:16px;font-weight:600;color:var(--text-primary)}}
.histogram-subtitle {{font-size:12px;color:var(--text-secondary);margin-top:4px}}
.histogram-stats {{text-align:right;font-size:12px;color:var(--text-secondary)}}
.histogram-stats .stat-row {{margin-bottom:2px}}
.histogram-stats .stat-label {{color:var(--text-muted)}}
.histogram-stats .stat-value {{color:var(--text-primary);font-weight:600;font-family:'SF Mono',monospace}}
.pokemon-selector {{display:flex;align-items:center;gap:var(--space-sm);margin-bottom:var(--space-lg);padding:var(--space-sm) var(--space-md);background:var(--glass-bg);border-radius:var(--radius-md)}}
.selector-label {{font-size:12px;color:var(--text-secondary);font-weight:600}}
.pokemon-search {{flex:1;max-width:250px;padding:8px 12px;background:var(--bg-elevated);border:1px solid var(--glass-border);border-radius:var(--radius-sm);color:var(--text-primary);font-size:13px}}
.pokemon-search:focus {{outline:none;border-color:var(--accent-primary);box-shadow:0 0 0 2px rgba(99,102,241,0.2)}}
.speed-controls {{background:var(--glass-bg);border:1px solid var(--glass-border);border-radius:var(--radius-md);padding:var(--space-md);margin-bottom:var(--space-lg)}}
.speed-controls-title {{font-size:11px;font-weight:700;text-transform:uppercase;letter-spacing:1px;color:var(--accent-primary);margin-bottom:var(--space-md)}}
.controls-row {{display:flex;align-items:center;gap:var(--space-md);margin-bottom:var(--space-sm);flex-wrap:wrap}}
.control-group {{display:flex;align-items:center;gap:var(--space-xs)}}
.control-label {{font-size:11px;color:var(--text-secondary);font-weight:600}}
.nature-select {{padding:6px 10px;border:1px solid var(--glass-border);border-radius:var(--radius-sm);background:var(--bg-elevated);color:var(--text-primary);font-size:12px}}
.ev-slider {{width:120px;-webkit-appearance:none;height:6px;border-radius:3px;background:rgba(255,255,255,0.1)}}
.ev-slider::-webkit-slider-thumb {{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;background:var(--gradient-primary);cursor:pointer}}
.ev-value {{font-family:'SF Mono',monospace;font-size:12px;font-weight:700;color:var(--text-primary);min-width:30px}}
.final-speed {{background:var(--gradient-primary);color:white;padding:6px 12px;border-radius:var(--radius-sm);font-size:14px;font-weight:700;margin-left:auto}}
.modifier-toggles {{display:flex;gap:var(--space-xs);margin-top:var(--space-sm)}}
.modifier-btn {{padding:6px 12px;border:1px solid var(--glass-border);border-radius:var(--radius-sm);background:var(--bg-elevated);color:var(--text-secondary);font-size:11px;font-weight:600;cursor:pointer}}
.modifier-btn.active {{background:var(--accent-primary);border-color:var(--accent-primary);color:white}}
.modifier-btn.active.tailwind {{background:#3b82f6;border-color:#3b82f6}}
.modifier-btn.active.scarf {{background:#f59e0b;border-color:#f59e0b}}
.modifier-btn.active.paralysis {{background:#eab308;border-color:#eab308;color:#1a1a2e}}
.base-speed-info {{font-size:13px;color:var(--text-muted)}}
.chart-wrapper {{display:flex;gap:12px;margin-bottom:var(--space-md)}}
.y-axis {{display:flex;flex-direction:column;justify-content:space-between;font-size:14px;font-family:'SF Mono',monospace;color:var(--text-muted);width:40px;text-align:right}}
.chart-area {{flex:1;position:relative}}
.histogram-chart {{position:relative;height:280px;border-left:2px solid rgba(255,255,255,0.2);border-bottom:2px solid rgba(255,255,255,0.2)}}
.grid-lines {{position:absolute;top:0;left:0;right:0;bottom:0;pointer-events:none}}
.grid-line {{position:absolute;left:0;right:0;height:1px;background:rgba(255,255,255,0.08)}}
.bars-container {{position:absolute;bottom:0;left:0;right:0;height:100%;padding:0 4px}}
.hist-bar {{position:absolute;bottom:0;width:14px;background:#dc2626;border-radius:2px 2px 0 0;transform:translateX(-50%);min-height:4px}}
.hist-bar.user-bar {{background:#22c55e;box-shadow:0 0 12px rgba(34,197,94,0.6)}}
.user-speed-marker {{position:absolute;bottom:0;width:3px;height:100%;background:linear-gradient(to top,#22c55e,rgba(34,197,94,0.3));transform:translateX(-50%);z-index:10}}
.user-speed-label {{position:absolute;top:-28px;background:#22c55e;color:white;padding:4px 8px;border-radius:4px;font-size:12px;font-weight:700;transform:translateX(-50%);white-space:nowrap;box-shadow:0 2px 8px rgba(34,197,94,0.4)}}
.histogram-axis {{display:flex;justify-content:space-between;padding:8px 0 0 0;font-size:13px;color:var(--text-muted);font-family:'SF Mono',monospace}}
.outspeed-result {{display:flex;align-items:center;justify-content:center;gap:var(--space-lg);padding:var(--space-lg);background:var(--glass-bg);border-radius:var(--radius-md);margin-top:var(--space-lg)}}
.outspeed-percent {{font-size:42px;font-weight:700}}
.outspeed-percent.excellent {{color:var(--accent-success)}}
.outspeed-percent.good {{color:var(--accent-warning)}}
.outspeed-percent.poor {{color:var(--accent-danger)}}
.outspeed-text {{font-size:16px;color:var(--text-secondary)}}
</style>
</head>
<body>
<div class="histogram-container">
    <div class="histogram-header">
        <div>
            <div class="histogram-title" id="histogram-title">Speed Distribution: {initial_target.replace("-", " ").title()}</div>
            <div class="histogram-subtitle" id="histogram-subtitle">Base {initial_base} Speed</div>
        </div>
        <div class="histogram-stats">
            <div class="stat-row"><span class="stat-label">Median:</span> <span class="stat-value" id="stat-median">{initial_stats.get('median', 0)}</span></div>
            <div class="stat-row"><span class="stat-label">IQR:</span> <span class="stat-value" id="stat-iqr">{initial_stats.get('iqr_low', speed_min)} - {initial_stats.get('iqr_high', speed_max)}</span></div>
            <div class="stat-row"><span class="stat-label">Mean:</span> <span class="stat-value" id="stat-mean">{initial_stats.get('mean', 0):.1f}</span></div>
        </div>
    </div>
    <div class="pokemon-selector">
        <span class="selector-label">Compare to:</span>
        <input type="text" id="pokemon-search" class="pokemon-search" list="pokemon-options" value="{initial_target.replace("-", " ").title()}" placeholder="Search Pokemon...">
        <datalist id="pokemon-options">{datalist_options}</datalist>
    </div>
    {"" if base_speed is None else f'''<div class="speed-controls">
        <div class="speed-controls-title">Your Speed Controls</div>
        <div class="controls-row">
            <div class="control-group"><span class="control-label">Nature:</span>
                <select id="nature-select" class="nature-select" onchange="updateSpeed()">
                    <optgroup label="+Speed"><option value="Timid" {"selected" if nature=="Timid" else ""}>Timid</option><option value="Jolly" {"selected" if nature=="Jolly" else ""}>Jolly</option></optgroup>
                    <optgroup label="-Speed"><option value="Brave" {"selected" if nature=="Brave" else ""}>Brave</option><option value="Relaxed" {"selected" if nature=="Relaxed" else ""}>Relaxed</option><option value="Quiet" {"selected" if nature=="Quiet" else ""}>Quiet</option><option value="Sassy" {"selected" if nature=="Sassy" else ""}>Sassy</option></optgroup>
                    <optgroup label="Neutral"><option value="Serious" {"selected" if nature=="Serious" else ""}>Serious</option><option value="Adamant" {"selected" if nature=="Adamant" else ""}>Adamant</option><option value="Modest" {"selected" if nature=="Modest" else ""}>Modest</option></optgroup>
                </select>
            </div>
            <div class="control-group"><span class="control-label">Speed EVs:</span>
                <input type="range" id="speed-evs" class="ev-slider" min="0" max="252" step="4" value="{speed_evs}" oninput="updateSpeed()">
                <span id="ev-display" class="ev-value">{speed_evs}</span>
            </div>
            <div class="control-group"><span class="base-speed-info">Base: {base_speed}</span></div>
            <div class="final-speed"><span id="final-speed">{pokemon_speed}</span> Spe</div>
        </div>
        <div class="modifier-toggles">
            <button class="modifier-btn tailwind" onclick="toggleModifier(this,&apos;tailwind&apos;)">Tailwind (2x)</button>
            <button class="modifier-btn scarf" onclick="toggleModifier(this,&apos;scarf&apos;)">Choice Scarf (1.5x)</button>
            <button class="modifier-btn paralysis" onclick="toggleModifier(this,&apos;paralysis&apos;)">Paralysis (0.5x)</button>
        </div>
    </div>'''}
    <div class="chart-wrapper">
        <div class="y-axis"><span>30%</span><span>25%</span><span>20%</span><span>15%</span><span>10%</span><span>5%</span><span>0%</span></div>
        <div class="chart-area">
            <div class="histogram-chart">
                <div class="grid-lines"><div class="grid-line" style="bottom:16.67%"></div><div class="grid-line" style="bottom:33.33%"></div><div class="grid-line" style="bottom:50%"></div><div class="grid-line" style="bottom:66.67%"></div><div class="grid-line" style="bottom:83.33%"></div></div>
                <div class="bars-container" id="bars-container">{bars_html}</div>
                <div class="user-speed-marker" id="user-speed-marker" style="left:{user_x_pos}%"><div class="user-speed-label">{pokemon_speed}</div></div>
            </div>
            <div class="histogram-axis" id="histogram-axis">{x_labels_html}</div>
        </div>
    </div>
    <div class="outspeed-result">
        <div id="outspeed-percent" class="outspeed-percent {result_class}">{outspeed_pct:.1f}%</div>
        <div class="outspeed-text"><strong>{pokemon_name}</strong> outspeeds <span id="outspeed-count">{outspeed_pct:.0f}</span>% of <span id="target-name-display">{initial_target.replace("-", " ").title()}</span> spreads</div>
    </div>
</div>
<script>
const allTargetsData={targets_json};
const userPokemonName="{pokemon_name}";
let currentUserSpeed={pokemon_speed};
let currentTarget="{initial_target}";
const nameToKey={{}};
Object.keys(allTargetsData).forEach(key=>{{const d=key.split('-').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');nameToKey[d]=key;nameToKey[d.toLowerCase()]=key;nameToKey[key]=key;}});
{"" if base_speed is None else f'''const BASE_SPEED={base_speed};
const NATURE_MODS={{"Timid":1.1,"Jolly":1.1,"Hasty":1.1,"Naive":1.1,"Brave":0.9,"Relaxed":0.9,"Quiet":0.9,"Sassy":0.9}};
let modifiers={{tailwind:false,scarf:false,paralysis:false}};
function calcSpeed(b,e,n){{const m=NATURE_MODS[n]||1;return Math.floor((Math.floor((2*b+31+Math.floor(e/4))*50/100)+5)*m);}}
function applyModifiers(s){{let f=s;if(modifiers.tailwind)f*=2;if(modifiers.scarf)f*=1.5;if(modifiers.paralysis)f*=0.5;return Math.floor(f);}}
function toggleModifier(btn,mod){{modifiers[mod]=!modifiers[mod];btn.classList.toggle("active",modifiers[mod]);updateSpeed();}}
function updateSpeed(){{const e=parseInt(document.getElementById("speed-evs").value)||0;const n=document.getElementById("nature-select").value;document.getElementById("ev-display").textContent=e;let s=applyModifiers(calcSpeed(BASE_SPEED,e,n));document.getElementById("final-speed").textContent=s;currentUserSpeed=s;updateHistogram(currentTarget);}}'''}
document.getElementById('pokemon-search').addEventListener('change',function(){{const v=this.value.trim();const k=nameToKey[v]||nameToKey[v.toLowerCase()]||v.toLowerCase().replace(/ /g,'-');if(k&&allTargetsData[k]){{currentTarget=k;updateHistogram(k);hideNotLoadedMessage();}}else if(v){{showNotLoadedMessage(v);}}}});
function showNotLoadedMessage(name){{let msg=document.getElementById('not-loaded-msg');if(!msg){{msg=document.createElement('div');msg.id='not-loaded-msg';msg.style.cssText='padding:12px 16px;background:rgba(234,179,8,0.15);border:1px solid rgba(234,179,8,0.3);border-radius:8px;color:#fbbf24;font-size:13px;margin:12px 0;';document.querySelector('.pokemon-selector').after(msg);}}msg.innerHTML='<strong>'+name+'</strong> is not loaded. Re-run the tool with <code>targets=[\\"'+name+'\\"]</code> to load its data.';msg.style.display='block';}}
function hideNotLoadedMessage(){{const msg=document.getElementById('not-loaded-msg');if(msg)msg.style.display='none';}}
function updateHistogram(t){{const d=allTargetsData[t];if(!d)return;const dist=d.distribution||[];const st=d.stats||{{}};const base=d.base_speed||100;const dn=t.split('-').map(w=>w.charAt(0).toUpperCase()+w.slice(1)).join(' ');
document.getElementById('histogram-title').textContent='Speed Distribution: '+dn;document.getElementById('histogram-subtitle').textContent='Base '+base+' Speed';document.getElementById('target-name-display').textContent=dn;
const speeds=dist.map(s=>s.speed||0);const usages=dist.map(s=>s.usage||s.count||1);let sMin=st.min,sMax=st.max,med=st.median,mean=st.mean,iqrL=st.iqr_low,iqrH=st.iqr_high;
if(speeds.length>0){{if(sMin===undefined)sMin=Math.min(...speeds);if(sMax===undefined)sMax=Math.max(...speeds);if(med===undefined){{const so=[...speeds].sort((a,b)=>a-b);med=so[Math.floor(so.length/2)];}}if(mean===undefined)mean=speeds.reduce((a,b)=>a+b,0)/speeds.length;if(iqrL===undefined)iqrL=sMin;if(iqrH===undefined)iqrH=sMax;}}else{{sMin=50;sMax=200;med=100;mean=100;iqrL=sMin;iqrH=sMax;}}
sMin=Math.min(sMin,currentUserSpeed);sMax=Math.max(sMax,currentUserSpeed);
document.getElementById('stat-median').textContent=med;document.getElementById('stat-iqr').textContent=iqrL+' - '+iqrH;document.getElementById('stat-mean').textContent=mean.toFixed(1);
const range=sMax-sMin||1;const ax=document.getElementById('histogram-axis');let ah='';for(let i=0;i<8;i++)ah+='<span>'+Math.round(sMin+(range*i/7))+'</span>';ax.innerHTML=ah;
const bc=document.getElementById('bars-container');bc.innerHTML='';const mx=Math.max(...usages,1);[...dist].sort((a,b)=>(a.speed||0)-(b.speed||0)).forEach(e=>{{const sp=e.speed||0;const us=e.usage||e.count||1;const h=(us/mx)*95;const x=((sp-sMin)/range)*100;const bar=document.createElement('div');bar.className='hist-bar'+(Math.abs(sp-currentUserSpeed)<=2?' user-bar':'');bar.dataset.speed=sp;bar.style.left=x+'%';bar.style.height=h+'%';bar.title=sp+' Spe: '+us.toFixed(1)+'%';bc.appendChild(bar);}});
const userMarker=document.getElementById('user-speed-marker');const userX=((currentUserSpeed-sMin)/range)*100;userMarker.style.left=Math.max(0,Math.min(100,userX))+'%';userMarker.querySelector('.user-speed-label').textContent=currentUserSpeed;
let ou=0,tu=0;for(let i=0;i<speeds.length;i++){{tu+=usages[i];if(currentUserSpeed>speeds[i])ou+=usages[i];}}const op=tu>0?(ou/tu*100):0;
const oe=document.getElementById('outspeed-percent');oe.textContent=op.toFixed(1)+'%';oe.className='outspeed-percent '+(op>=80?'excellent':op>=50?'good':'poor');document.getElementById('outspeed-count').textContent=Math.round(op);}}
console.log('Interactive Speed Histogram initialized with',Object.keys(allTargetsData).length,'targets');
</script>
</body></html>'''


def create_spread_cards_ui(
    pokemon_name: str,
    spreads: list[dict[str, Any]],
    show_count: int = 5,
    selected_index: Optional[int] = None,
    top_moves: Optional[list[str]] = None,
    top_tera: Optional[str] = None,
) -> str:
    """Create spread selection cards UI showing multiple spreads.

    Shows top N spreads as prominent cards, plus a collapsible dropdown
    to browse all available spreads.

    Args:
        pokemon_name: Pokemon name
        spreads: List of spread dicts with 'nature', 'evs', 'usage', 'item', 'ability'
        show_count: Number of spreads to show as cards (default 5)
        selected_index: Index of currently selected spread (optional)
        top_moves: Top 4 moves to display (from Pokemon usage data)
        top_tera: Most common tera type (from Pokemon usage data)

    Returns:
        HTML string for the spread cards UI
    """
    styles = get_shared_styles()

    # Type colors for tera badges
    tera_colors = {
        "normal": "#A8A878", "fire": "#F08030", "water": "#6890F0", "electric": "#F8D030",
        "grass": "#78C850", "ice": "#98D8D8", "fighting": "#C03028", "poison": "#A040A0",
        "ground": "#E0C068", "flying": "#A890F0", "psychic": "#F85888", "bug": "#A8B820",
        "rock": "#B8A038", "ghost": "#705898", "dragon": "#7038F8", "dark": "#705848",
        "steel": "#B8B8D0", "fairy": "#EE99AC",
    }

    # Build moves HTML (same for all spreads)
    moves_html = ""
    if top_moves:
        moves_list = top_moves[:4]  # Show top 4 moves
        moves_html = "".join(f'<span class="move-pill">{move}</span>' for move in moves_list)

    # Build tera HTML (same for all spreads)
    tera_html = ""
    tera_color = "#888"
    if top_tera:
        tera_color = tera_colors.get(top_tera.lower(), "#888")
        tera_html = f'<span class="tera-badge" style="background: {tera_color};">Tera {top_tera}</span>'

    # Store for data attributes (JSON-safe)
    moves_json = ",".join(top_moves[:4]) if top_moves else ""

    # EV formatting helpers
    ev_order = ["hp", "attack", "defense", "special_attack", "special_defense", "speed"]
    ev_labels = {"hp": "HP", "attack": "Atk", "defense": "Def",
                 "special_attack": "SpA", "special_defense": "SpD", "speed": "Spe"}

    def format_evs_full(evs: dict) -> str:
        """Format EVs as '252 HP / 4 Atk / 252 Spe'"""
        parts = []
        for stat in ev_order:
            val = evs.get(stat, 0)
            if val > 0:
                parts.append(f"{val} {ev_labels[stat]}")
        return " / ".join(parts) if parts else "No EVs"

    def format_evs_compact(evs: dict) -> str:
        """Format EVs as compact '252/4/0/0/4/252'"""
        return "/".join(str(evs.get(s, 0)) for s in ev_order)

    # Build spread cards (top N)
    cards_html = ""
    for i, spread in enumerate(spreads[:show_count]):
        nature = spread.get("nature", "Serious")
        evs = spread.get("evs", {})
        usage = spread.get("usage", 0)
        item = spread.get("item", "")
        ability = spread.get("ability", "")

        ev_str = format_evs_full(evs)
        ev_compact = format_evs_compact(evs)

        is_selected = i == selected_index
        selected_class = "selected" if is_selected else ""
        rank_emoji = ["&#129351;", "&#129352;", "&#129353;"][i] if i < 3 else f"#{i+1}"

        cards_html += f"""
        <div class="spread-card {selected_class}" data-index="{i}" data-nature="{nature}" data-evs="{ev_str}" data-evs-compact="{ev_compact}" data-usage="{usage:.1f}" data-item="{item}" data-ability="{ability}" data-moves="{moves_json}" data-tera="{top_tera or ''}" onclick="selectSpread({i})">
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
                    {tera_html}
                </div>
                {f'<div class="spread-moves">{moves_html}</div>' if moves_html else ''}
            </div>
            <div class="spread-select">
                {'<span class="selected-check">&#10003;</span>' if is_selected else '<span class="select-btn">Select</span>'}
            </div>
        </div>
        """

    # Build "All Spreads" dropdown with all spreads in compact format
    dropdown_rows = ""
    for i, spread in enumerate(spreads):
        nature = spread.get("nature", "Serious")
        evs = spread.get("evs", {})
        usage = spread.get("usage", 0)
        item = spread.get("item", "")
        ability = spread.get("ability", "")

        ev_compact = format_evs_compact(evs)
        ev_full = format_evs_full(evs)

        is_selected = i == selected_index
        row_class = "selected" if is_selected else ""
        in_top = "in-top" if i < show_count else ""

        dropdown_rows += f'''
        <div class="spread-row {row_class} {in_top}" data-index="{i}" data-nature="{nature}" data-evs="{ev_full}" data-evs-compact="{ev_compact}" data-usage="{usage:.1f}" data-item="{item}" data-ability="{ability}" onclick="selectSpread({i})">
            <span class="row-rank">#{i+1}</span>
            <span class="row-nature">{nature}</span>
            <span class="row-evs">{ev_compact}</span>
            <span class="row-usage">{usage:.1f}%</span>
        </div>
        '''

    dropdown_html = f'''
    <details class="all-spreads-dropdown">
        <summary class="all-spreads-summary">
            <span class="dropdown-label">&#9662; All Spreads</span>
            <span class="dropdown-badge">{len(spreads)} total</span>
        </summary>
        <div class="all-spreads-list">
            {dropdown_rows}
        </div>
    </details>
    '''

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
            font-size: 18px;
            font-weight: 700;
            color: #ffffff;
            letter-spacing: 0.5px;
        }}

        .spread-usage {{
            font-size: 15px;
            color: #a5b4fc;
            font-weight: 700;
            background: rgba(99, 102, 241, 0.25);
            padding: 5px 12px;
            border-radius: 12px;
        }}

        .spread-evs {{
            font-size: 14px;
            color: #e0e0e0;
            font-family: 'SF Mono', 'Consolas', 'Monaco', monospace;
            margin-bottom: 8px;
            letter-spacing: 0.3px;
            line-height: 1.4;
        }}

        .spread-details {{
            display: flex;
            flex-wrap: wrap;
            gap: 8px;
            font-size: 13px;
            margin-bottom: 6px;
        }}

        .spread-item {{
            color: #fbbf24;
            font-weight: 600;
            background: rgba(251, 191, 36, 0.15);
            padding: 2px 8px;
            border-radius: 4px;
        }}

        .spread-ability {{
            color: #60a5fa;
            font-weight: 600;
            background: rgba(96, 165, 250, 0.15);
            padding: 2px 8px;
            border-radius: 4px;
        }}

        .tera-badge {{
            padding: 3px 10px;
            border-radius: 4px;
            font-size: 12px;
            font-weight: 700;
            color: #fff;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.4);
        }}

        .spread-moves {{
            display: flex;
            flex-wrap: wrap;
            gap: 4px;
            margin-top: 6px;
        }}

        .move-pill {{
            font-size: 12px;
            padding: 4px 10px;
            background: rgba(255, 255, 255, 0.1);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 6px;
            color: #d1d5db;
            font-weight: 500;
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

        /* All Spreads Dropdown */
        .all-spreads-dropdown {{
            margin-top: var(--space-md);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            overflow: hidden;
        }}

        .all-spreads-summary {{
            padding: var(--space-sm) var(--space-md);
            cursor: pointer;
            display: flex;
            justify-content: space-between;
            align-items: center;
            background: var(--glass-bg);
            list-style: none;
            user-select: none;
            transition: all var(--duration-fast);
        }}

        .all-spreads-summary::-webkit-details-marker {{
            display: none;
        }}

        .all-spreads-summary:hover {{
            background: var(--glass-bg-hover);
        }}

        .all-spreads-dropdown[open] .all-spreads-summary {{
            border-bottom: 1px solid var(--glass-border);
        }}

        .dropdown-label {{
            font-size: 13px;
            color: var(--text-secondary);
            font-weight: 500;
        }}

        .all-spreads-dropdown[open] .dropdown-label {{
            color: var(--accent-primary);
        }}

        .dropdown-badge {{
            font-size: 11px;
            color: var(--text-muted);
            background: var(--glass-bg);
            padding: 2px 8px;
            border-radius: var(--radius-full);
        }}

        .all-spreads-list {{
            max-height: 300px;
            overflow-y: auto;
            padding: var(--space-xs);
            background: var(--bg-card);
        }}

        .spread-row {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            padding: var(--space-sm) var(--space-md);
            border-radius: var(--radius-sm);
            cursor: pointer;
            font-size: 14px;
            transition: all var(--duration-fast);
        }}

        .spread-row:hover {{
            background: var(--glass-bg-hover);
        }}

        .spread-row.selected {{
            background: rgba(99, 102, 241, 0.15);
            border-left: 3px solid var(--accent-primary);
        }}

        .spread-row.in-top {{
            opacity: 0.7;
        }}

        .spread-row.in-top::after {{
            content: '(shown above)';
            font-size: 11px;
            color: var(--text-muted);
            margin-left: auto;
        }}

        .row-rank {{
            width: 36px;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 14px;
        }}

        .row-nature {{
            width: 90px;
            color: #ffffff;
            font-weight: 700;
            font-size: 15px;
        }}

        .row-evs {{
            flex: 1;
            color: #e0e0e0;
            font-family: 'SF Mono', 'Consolas', monospace;
            font-size: 14px;
            letter-spacing: 0.3px;
        }}

        .row-usage {{
            width: 55px;
            text-align: right;
            color: var(--accent-primary);
            font-weight: 600;
            font-size: 14px;
        }}

        /* Scrollbar styling for dropdown list */
        .all-spreads-list::-webkit-scrollbar {{
            width: 6px;
        }}

        .all-spreads-list::-webkit-scrollbar-track {{
            background: var(--bg-card);
        }}

        .all-spreads-list::-webkit-scrollbar-thumb {{
            background: var(--glass-border);
            border-radius: 3px;
        }}

        .all-spreads-list::-webkit-scrollbar-thumb:hover {{
            background: var(--text-muted);
        }}

        /* Selected Spread Preview */
        .selected-spread-preview {{
            margin-top: var(--space-lg);
            padding: var(--space-lg);
            background: rgba(99, 102, 241, 0.1);
            border: 2px solid var(--accent-primary);
            border-radius: var(--radius-lg);
            display: none;
        }}

        .selected-spread-preview.visible {{
            display: block;
        }}

        .preview-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: var(--space-md);
        }}

        .preview-title {{
            font-size: 12px;
            text-transform: uppercase;
            letter-spacing: 1px;
            color: var(--accent-primary);
            font-weight: 600;
        }}

        .preview-rank {{
            font-size: 14px;
            color: var(--text-muted);
            background: var(--glass-bg);
            padding: 4px 12px;
            border-radius: var(--radius-full);
        }}

        .preview-nature {{
            font-size: 24px;
            font-weight: 700;
            color: var(--text-primary);
            margin-bottom: var(--space-xs);
        }}

        .preview-evs {{
            font-size: 22px;
            font-family: 'SF Mono', monospace;
            color: var(--text-primary);
            margin-bottom: var(--space-sm);
            letter-spacing: 1px;
        }}

        .preview-usage-container {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            margin-top: var(--space-sm);
        }}

        .preview-usage-label {{
            font-size: 14px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
        }}

        .preview-usage {{
            font-size: 22px;
            color: #ffffff;
            font-weight: 700;
            background: var(--gradient-primary);
            padding: 8px 18px;
            border-radius: var(--radius-full);
            display: inline-block;
            box-shadow: var(--glow-primary);
        }}

        .preview-details {{
            font-size: 14px;
            color: var(--text-muted);
            margin-top: var(--space-md);
            display: flex;
            gap: var(--space-lg);
        }}

        .preview-item {{
            color: var(--accent-warning);
        }}

        .preview-ability {{
            color: var(--accent-info);
        }}

        .preview-tera .tera-badge {{
            padding: 3px 10px;
            border-radius: var(--radius-sm);
            font-size: 11px;
            font-weight: 600;
            color: #fff;
            text-shadow: 0 1px 2px rgba(0, 0, 0, 0.3);
        }}

        .preview-moves {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: var(--space-sm);
        }}

        .preview-moves .move-pill {{
            font-size: 11px;
            padding: 3px 8px;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-sm);
            color: var(--text-primary);
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

        {dropdown_html}

        <div class="selected-spread-preview" id="selected-preview">
            <div class="preview-header">
                <div class="preview-title">Selected Spread</div>
                <div class="preview-rank" id="preview-rank"></div>
            </div>
            <div class="preview-nature" id="preview-nature"></div>
            <div class="preview-evs" id="preview-evs"></div>
            <div class="preview-usage-container">
                <span class="preview-usage-label">Usage</span>
                <span class="preview-usage" id="preview-usage"></span>
            </div>
            <div class="preview-details">
                <span class="preview-item" id="preview-item"></span>
                <span class="preview-ability" id="preview-ability"></span>
                <span class="preview-tera" id="preview-tera"></span>
            </div>
            <div class="preview-moves" id="preview-moves"></div>
        </div>
    </div>

    <script>
    function selectSpread(index) {{
        // Update selection state on cards
        document.querySelectorAll('.spread-card').forEach(el => {{
            el.classList.remove('selected');
            const selectArea = el.querySelector('.spread-select');
            if (selectArea) {{
                selectArea.innerHTML = '<span class="select-btn">Select</span>';
            }}
        }});

        // Update selection state on dropdown rows
        document.querySelectorAll('.spread-row').forEach(el => {{
            el.classList.remove('selected');
        }});

        // Select the card if it exists (in top N)
        const card = document.querySelector(`.spread-card[data-index="${{index}}"]`);
        if (card) {{
            card.classList.add('selected');
            const selectArea = card.querySelector('.spread-select');
            if (selectArea) {{
                selectArea.innerHTML = '<span class="selected-check">&#10003;</span>';
            }}
        }}

        // Select the dropdown row
        const row = document.querySelector(`.spread-row[data-index="${{index}}"]`);
        if (row) {{
            row.classList.add('selected');
        }}

        // Close dropdown
        const dropdown = document.querySelector('.all-spreads-dropdown');
        if (dropdown) {{
            dropdown.removeAttribute('open');
        }}

        // Get spread data from either card or row
        const sourceEl = card || row;
        if (sourceEl) {{
            const nature = sourceEl.dataset.nature || '';
            const evs = sourceEl.dataset.evs || '';
            const usage = sourceEl.dataset.usage || '0';
            const item = sourceEl.dataset.item || '';
            const ability = sourceEl.dataset.ability || '';
            const moves = sourceEl.dataset.moves || '';
            const tera = sourceEl.dataset.tera || '';

            // Update preview section
            const preview = document.getElementById('selected-preview');
            document.getElementById('preview-rank').textContent = `#${{index + 1}}`;
            document.getElementById('preview-nature').textContent = nature;
            document.getElementById('preview-evs').textContent = evs;
            document.getElementById('preview-usage').textContent = `${{usage}}%`;
            document.getElementById('preview-item').textContent = item ? `@ ${{item}}` : '';
            document.getElementById('preview-ability').textContent = ability || '';

            // Update tera
            const teraEl = document.getElementById('preview-tera');
            if (tera) {{
                teraEl.innerHTML = `<span class="tera-badge" style="background: ${{getTeraColor(tera)}};">Tera ${{tera}}</span>`;
            }} else {{
                teraEl.innerHTML = '';
            }}

            // Update moves
            const movesEl = document.getElementById('preview-moves');
            if (moves) {{
                const moveList = moves.split(',').filter(m => m.trim());
                movesEl.innerHTML = moveList.map(m => `<span class="move-pill">${{m.trim()}}</span>`).join('');
            }} else {{
                movesEl.innerHTML = '';
            }}

            // Show preview
            preview.classList.add('visible');
        }}

        // Scroll to card if it exists, otherwise scroll to preview
        if (card) {{
            card.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        }} else {{
            const preview = document.getElementById('selected-preview');
            preview.scrollIntoView({{ behavior: 'smooth', block: 'center' }});
        }}
    }}

    function getTeraColor(type) {{
        const colors = {{
            normal: '#A8A878', fire: '#F08030', water: '#6890F0', electric: '#F8D030',
            grass: '#78C850', ice: '#98D8D8', fighting: '#C03028', poison: '#A040A0',
            ground: '#E0C068', flying: '#A890F0', psychic: '#F85888', bug: '#A8B820',
            rock: '#B8A038', ghost: '#705898', dragon: '#7038F8', dark: '#705848',
            steel: '#B8B8D0', fairy: '#EE99AC'
        }};
        return colors[type.toLowerCase()] || '#888';
    }}
    </script>
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
    build_id: Optional[str] = None,
) -> str:
    """Create an interactive Pokemon build editor card with EV sliders.

    Features:
    - Pokemon sprite and type display
    - EV sliders (0-252) for all 6 stats
    - Nature, ability, item, tera type selectors
    - Move selectors (4 slots)
    - Real-time stat calculation
    - Speed tier display showing how you compare to usage stats of this Pokemon
    - Auto-save state for bidirectional sync with chat commands

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
    from ..design_system import DESIGN_TOKENS, ANIMATIONS, TYPE_COLORS

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

    # Opponent speed data for Speed vs Opponent section
    from vgc_mcp_core.calc.speed import META_SPEED_TIERS
    opponent_speed_json = json.dumps(META_SPEED_TIERS)

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

        .save-indicator {{
            font-size: 12px;
            color: var(--accent-success);
            opacity: 0;
            transition: opacity 0.3s ease;
        }}
        .save-indicator.visible {{
            opacity: 1;
        }}
        .save-indicator::before {{
            content: "Saved";
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

        /* Speed vs Opponent Section */
        .speed-vs-opponent {{
            padding: var(--space-lg);
            background: linear-gradient(180deg, rgba(239, 68, 68, 0.05) 0%, transparent 100%);
            border-top: 1px solid var(--glass-border);
        }}

        .speed-vs-opponent-title {{
            font-size: 16px;
            font-weight: var(--font-weight-bold);
            margin-bottom: var(--space-md);
            color: var(--text-primary);
        }}

        .opponent-selector {{
            margin-bottom: var(--space-md);
        }}

        .opponent-selector label {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-right: var(--space-sm);
        }}

        .opponent-select {{
            padding: 8px 12px;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            background: var(--bg-elevated);
            color: var(--text-primary);
            font-size: 14px;
            cursor: pointer;
            min-width: 200px;
        }}

        .opponent-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
        }}

        /* Modifier Toggle Buttons */
        .opponent-modifiers {{
            display: flex;
            flex-direction: column;
            gap: var(--space-sm);
            margin-bottom: var(--space-lg);
        }}

        .modifier-group {{
            display: flex;
            flex-wrap: wrap;
            align-items: center;
            gap: var(--space-xs);
        }}

        .modifier-group-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            width: 100px;
            flex-shrink: 0;
        }}

        .mod-btn {{
            padding: 6px 10px;
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-sm);
            background: var(--bg-elevated);
            color: var(--text-secondary);
            font-size: 11px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .mod-btn:hover {{
            background: rgba(255, 255, 255, 0.05);
            border-color: rgba(255, 255, 255, 0.15);
        }}

        .mod-btn.active {{
            background: var(--accent-primary);
            border-color: var(--accent-primary);
            color: white;
        }}

        .mod-btn.active.debuff {{
            background: #ef4444;
            border-color: #ef4444;
        }}

        .mod-btn.active.buff {{
            background: #3b82f6;
            border-color: #3b82f6;
        }}

        .mod-btn.active.weather {{
            background: #f59e0b;
            border-color: #f59e0b;
            color: #1a1a2e;
        }}

        .mod-btn.active.terrain {{
            background: #a855f7;
            border-color: #a855f7;
        }}

        .mod-btn:disabled {{
            opacity: 0.3;
            cursor: not-allowed;
        }}

        /* Speed Comparison Display */
        .speed-comparison-display {{
            display: grid;
            grid-template-columns: 1fr auto 1fr;
            gap: var(--space-md);
            align-items: center;
            margin-bottom: var(--space-lg);
            padding: var(--space-md);
            background: var(--glass-bg);
            border-radius: var(--radius-md);
        }}

        .speed-box {{
            text-align: center;
        }}

        .speed-box-label {{
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 4px;
        }}

        .speed-box-value {{
            font-family: var(--font-mono);
            font-size: 28px;
            font-weight: var(--font-weight-bold);
        }}

        .speed-box-value.your-speed {{
            color: var(--accent-success);
        }}

        .speed-box-value.opp-speed {{
            color: #ef4444;
        }}

        .vs-indicator {{
            font-size: 18px;
            font-weight: 700;
            color: var(--text-muted);
        }}

        /* Opponent Outspeed Result */
        .opp-outspeed-result {{
            text-align: center;
            margin-bottom: var(--space-md);
        }}

        .opp-outspeed-pct {{
            font-size: 36px;
            font-weight: var(--font-weight-bold);
            color: var(--accent-success);
        }}

        .opp-outspeed-pct.poor {{
            color: #ef4444;
        }}

        .opp-outspeed-pct.fair {{
            color: #f59e0b;
        }}

        .opp-outspeed-text {{
            font-size: 14px;
            color: var(--text-secondary);
        }}

        /* Opponent Speed Table */
        .opp-speed-table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}

        .opp-speed-table th {{
            text-align: left;
            padding: 8px 10px;
            font-size: 11px;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            border-bottom: 1px solid var(--glass-border);
            background: rgba(0, 0, 0, 0.2);
        }}

        .opp-speed-table th:last-child {{
            text-align: right;
        }}

        .opp-speed-table td {{
            padding: 10px;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .opp-speed-table tr:last-child td {{
            border-bottom: none;
        }}

        .opp-speed-base {{
            font-family: var(--font-mono);
            font-weight: 600;
            color: var(--text-secondary);
        }}

        .opp-speed-modified {{
            font-family: var(--font-mono);
            font-weight: 700;
            font-size: 15px;
        }}

        .opp-result-col {{
            text-align: right;
            font-weight: 600;
        }}
    </style>
</head>
<body>
    <div class="build-card" id="build-card" data-build-id="{build_id or ''}" data-state="">
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
        </div>

        <!-- EV Sliders -->
        <div class="ev-section">
            <div class="ev-header" style="display:flex;justify-content:space-between;align-items:center;padding:var(--space-sm) var(--space-md);border-bottom:1px solid var(--glass-border);">
                <span class="ev-title">EV Spread</span>
                <span id="save-indicator" class="save-indicator"></span>
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

        <!-- Speed vs Opponent Section -->
        <div class="speed-vs-opponent">
            <div class="speed-vs-opponent-title">Speed vs Opponent</div>

            <!-- Opponent Pokemon Selector -->
            <div class="opponent-selector">
                <label>Target Pokemon:</label>
                <select id="opponent-pokemon" class="opponent-select" onchange="updateOpponentComparison()">
                    <option value="">Select opponent...</option>
                </select>
            </div>

            <!-- Opponent Modifiers -->
            <div class="opponent-modifiers">
                <div class="modifier-group">
                    <span class="modifier-group-label">Your Debuffs:</span>
                    <button class="mod-btn debuff" data-mod="icy-wind" onclick="toggleOppMod(this)">Icy Wind</button>
                    <button class="mod-btn debuff" data-mod="electroweb" onclick="toggleOppMod(this)">Electroweb</button>
                    <button class="mod-btn debuff" data-mod="twave" onclick="toggleOppMod(this)">T-Wave</button>
                    <button class="mod-btn debuff" data-mod="scary-face" onclick="toggleOppMod(this)">Scary Face</button>
                </div>
                <div class="modifier-group">
                    <span class="modifier-group-label">Opp Buffs:</span>
                    <button class="mod-btn buff" data-mod="opp-tailwind" onclick="toggleOppMod(this)">Tailwind</button>
                    <button class="mod-btn buff" data-mod="opp-scarf" onclick="toggleOppMod(this)">Choice Scarf</button>
                    <button class="mod-btn buff" id="booster-btn" data-mod="opp-booster" onclick="toggleOppMod(this)" disabled title="Only for Paradox Pokemon">Booster Energy</button>
                </div>
                <div class="modifier-group">
                    <span class="modifier-group-label">Field:</span>
                    <button class="mod-btn weather" id="sun-btn" data-mod="sun" onclick="toggleOppMod(this)" disabled title="Protosynthesis - Paradox only">Sun</button>
                    <button class="mod-btn terrain" id="eterrain-btn" data-mod="e-terrain" onclick="toggleOppMod(this)" disabled title="Quark Drive - Paradox only">E-Terrain</button>
                </div>
            </div>

            <!-- Speed Comparison Display -->
            <div class="speed-comparison-display" id="opp-comparison" style="display: none;">
                <div class="speed-box">
                    <div class="speed-box-label">Your Speed</div>
                    <div class="speed-box-value your-speed" id="opp-your-speed">--</div>
                </div>
                <div class="vs-indicator">vs</div>
                <div class="speed-box">
                    <div class="speed-box-label">Opp Max (modified)</div>
                    <div class="speed-box-value opp-speed" id="opp-max-speed">--</div>
                </div>
            </div>

            <!-- Opponent Outspeed Result -->
            <div class="opp-outspeed-result" id="opp-result" style="display: none;">
                <div class="opp-outspeed-pct" id="opp-outspeed-pct">--%</div>
                <div class="opp-outspeed-text">
                    You outspeed <span id="opp-outspeed-count">--</span>% of <span id="opp-name-display">--</span> spreads
                </div>
            </div>

            <!-- Opponent Speed Table -->
            <table class="opp-speed-table" id="opp-speed-table" style="display: none;">
                <thead>
                    <tr>
                        <th>Base</th>
                        <th>Modified</th>
                        <th>Spread</th>
                        <th>Usage</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody id="opp-speed-tbody">
                    <!-- Populated by JavaScript -->
                </tbody>
            </table>
        </div>
    </div>

    <script>
        const BASE_STATS = {base_stats_json};
        const NATURES = {natures_json};
        const SPEED_TIERS = {speed_tiers_json};
        const OPPONENT_SPEED_DATA = {opponent_speed_json};

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
        }}

        function updateSpeedTier() {{
            const baseSpeed = parseInt(document.getElementById('stat-speed').textContent) || 0;
            const speed = getYourSpeedWithItem();

            // Show item modifier if active
            const itemSelect = document.getElementById('item');
            const item = itemSelect ? itemSelect.value : '';
            const mult = YOUR_ITEM_MODS[item];
            if (mult) {{
                document.getElementById('speed-display').innerHTML = `${{speed}} <span style="color:var(--text-muted);font-size:0.8em;">(${{baseSpeed}} &#215; ${{mult}})</span>`;
            }} else {{
                document.getElementById('speed-display').textContent = speed;
            }}

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
            // Recalculate speed when item changes
            updateSpeedTier();
            updateOpponentComparison();
            // Auto-save state for bidirectional sync
            autoSave();
        }}

        // ===== AUTO-SAVE STATE FOR CHAT SYNC =====

        // Serialize current build state for sync with chat commands
        function serializeState() {{
            return JSON.stringify({{
                evs: {{
                    hp: parseInt(document.getElementById('ev-hp')?.value) || 0,
                    attack: parseInt(document.getElementById('ev-attack')?.value) || 0,
                    defense: parseInt(document.getElementById('ev-defense')?.value) || 0,
                    special_attack: parseInt(document.getElementById('ev-special_attack')?.value) || 0,
                    special_defense: parseInt(document.getElementById('ev-special_defense')?.value) || 0,
                    speed: parseInt(document.getElementById('ev-speed')?.value) || 0
                }},
                nature: document.getElementById('nature')?.value || '',
                ability: document.getElementById('ability')?.value || '',
                item: document.getElementById('item')?.value || '',
                tera_type: document.getElementById('tera-type')?.value || '',
                moves: [0,1,2,3].map(i => document.getElementById('move-'+i)?.value || '')
            }});
        }}

        // Debounced auto-save to data-state attribute
        let saveTimer;
        function autoSave() {{
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => {{
                const card = document.getElementById('build-card');
                if (card) {{
                    card.dataset.state = serializeState();
                    showSaveIndicator();
                }}
            }}, 300);
        }}

        function showSaveIndicator() {{
            const indicator = document.getElementById('save-indicator');
            if (indicator) {{
                indicator.classList.add('visible');
                setTimeout(() => indicator.classList.remove('visible'), 1500);
            }}
        }}

        // ===== YOUR ITEM SPEED MODIFIERS =====
        const YOUR_ITEM_MODS = {{
            'Choice Scarf': 1.5,
            'Iron Ball': 0.5
        }};

        function getYourSpeedWithItem() {{
            const baseSpeed = parseInt(document.getElementById('stat-speed').textContent) || 0;
            const itemSelect = document.getElementById('item');
            const item = itemSelect ? itemSelect.value : '';
            const mult = YOUR_ITEM_MODS[item] || 1.0;
            return Math.floor(baseSpeed * mult);
        }}

        // ===== SPEED VS OPPONENT SECTION =====

        // Opponent modifier definitions
        // paradoxType: "any" = all paradox, "ancient" = Protosynthesis only, "future" = Quark Drive only
        const OPP_MODS = {{
            'icy-wind': {{ mult: 2/3, name: 'Icy Wind', type: 'debuff' }},
            'electroweb': {{ mult: 2/3, name: 'Electroweb', type: 'debuff' }},
            'twave': {{ mult: 0.5, name: 'Thunder Wave', type: 'debuff' }},
            'scary-face': {{ mult: 0.5, name: 'Scary Face', type: 'debuff' }},
            'opp-tailwind': {{ mult: 2.0, name: 'Tailwind', type: 'buff' }},
            'opp-scarf': {{ mult: 1.5, name: 'Choice Scarf', type: 'buff' }},
            'opp-booster': {{ mult: 1.5, name: 'Booster Energy', type: 'buff', paradoxType: 'any' }},
            'sun': {{ mult: 1.5, name: 'Protosynthesis (Sun)', type: 'weather', paradoxType: 'ancient' }},
            'e-terrain': {{ mult: 1.5, name: 'Quark Drive (E-Terrain)', type: 'terrain', paradoxType: 'future' }}
        }};

        // Track active opponent modifiers
        let activeOppMods = new Set();

        // Populate opponent dropdown
        function populateOpponentDropdown() {{
            const select = document.getElementById('opponent-pokemon');
            if (!select || !OPPONENT_SPEED_DATA) return;

            // Sort by base speed descending
            const sorted = Object.entries(OPPONENT_SPEED_DATA)
                .sort((a, b) => b[1].base - a[1].base);

            sorted.forEach(([name, data]) => {{
                const opt = document.createElement('option');
                opt.value = name;
                opt.textContent = `${{name.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ')}} (Base ${{data.base}})`;
                select.appendChild(opt);
            }});
        }}

        // Toggle opponent modifier
        function toggleOppMod(btn) {{
            if (btn.disabled) return;

            const mod = btn.dataset.mod;

            if (activeOppMods.has(mod)) {{
                activeOppMods.delete(mod);
                btn.classList.remove('active');
            }} else {{
                activeOppMods.add(mod);
                btn.classList.add('active');
            }}

            updateOpponentComparison();
        }}

        // Get nature speed modifier
        function getNatureSpeedMod(nature) {{
            const plusSpeed = ['Timid', 'Jolly', 'Hasty', 'Naive'];
            const minusSpeed = ['Brave', 'Relaxed', 'Quiet', 'Sassy'];

            if (plusSpeed.includes(nature)) return 1.1;
            if (minusSpeed.includes(nature)) return 0.9;
            return 1.0;
        }}

        // Calculate opponent speed with modifiers
        // paradoxType: "ancient", "future", or null
        function calcOppSpeed(baseSpeed, evs, nature, mods, oppParadoxType) {{
            // Calculate base stat
            const natureMod = getNatureSpeedMod(nature);
            const inner = Math.floor((2 * baseSpeed + 31 + Math.floor(evs / 4)) * 50 / 100);
            let speed = Math.floor((inner + 5) * natureMod);

            // Apply modifiers
            let buffMult = 1.0;
            let debuffMult = 1.0;

            mods.forEach(mod => {{
                const modData = OPP_MODS[mod];
                if (!modData) return;

                // Check if this modifier requires a specific paradox type
                if (modData.paradoxType) {{
                    // 'any' means any paradox Pokemon
                    if (modData.paradoxType === 'any' && !oppParadoxType) return;
                    // Specific type must match
                    if (modData.paradoxType !== 'any' && modData.paradoxType !== oppParadoxType) return;
                }}

                if (modData.type === 'debuff') {{
                    debuffMult *= modData.mult;
                }} else {{
                    buffMult *= modData.mult;
                }}
            }});

            return Math.floor(speed * buffMult * debuffMult);
        }}

        // Update opponent comparison
        function updateOpponentComparison() {{
            const oppSelect = document.getElementById('opponent-pokemon');
            const oppName = oppSelect.value;

            // Hide if no opponent selected
            if (!oppName || !OPPONENT_SPEED_DATA[oppName]) {{
                document.getElementById('opp-comparison').style.display = 'none';
                document.getElementById('opp-result').style.display = 'none';
                document.getElementById('opp-speed-table').style.display = 'none';
                return;
            }}

            const oppData = OPPONENT_SPEED_DATA[oppName];
            const paradoxType = oppData.paradox_type || null;  // "ancient", "future", or null

            // Enable/disable paradox-only buttons based on paradox type
            const boosterBtn = document.getElementById('booster-btn');
            const sunBtn = document.getElementById('sun-btn');
            const eterrainBtn = document.getElementById('eterrain-btn');

            // Booster Energy works for ANY paradox Pokemon
            boosterBtn.disabled = !paradoxType;
            boosterBtn.title = paradoxType ? 'Booster Energy (1.5x Speed)' : 'Only for Paradox Pokemon';
            if (!paradoxType) {{
                activeOppMods.delete('opp-booster');
                boosterBtn.classList.remove('active');
            }}

            // Sun (Protosynthesis) only works for ANCIENT paradox
            sunBtn.disabled = paradoxType !== 'ancient';
            sunBtn.title = paradoxType === 'ancient' ? 'Sun - Protosynthesis (1.5x Speed)' : 'Only for Ancient Paradox (Protosynthesis)';
            if (paradoxType !== 'ancient') {{
                activeOppMods.delete('sun');
                sunBtn.classList.remove('active');
            }}

            // Electric Terrain (Quark Drive) only works for FUTURE paradox
            eterrainBtn.disabled = paradoxType !== 'future';
            eterrainBtn.title = paradoxType === 'future' ? 'Electric Terrain - Quark Drive (1.5x Speed)' : 'Only for Future Paradox (Quark Drive)';
            if (paradoxType !== 'future') {{
                activeOppMods.delete('e-terrain');
                eterrainBtn.classList.remove('active');
            }}

            // Get your current speed (with item modifier)
            const yourSpeed = getYourSpeedWithItem();

            // Calculate opponent spreads with modifiers
            const spreads = oppData.spreads || [];
            const modsArray = Array.from(activeOppMods);

            let processedSpreads = spreads.map(spread => {{
                const baseSpd = calcOppSpeed(oppData.base, spread.evs, spread.nature, [], paradoxType);
                const modifiedSpd = calcOppSpeed(oppData.base, spread.evs, spread.nature, modsArray, paradoxType);
                return {{
                    ...spread,
                    baseSpeed: baseSpd,
                    modifiedSpeed: modifiedSpd,
                    result: yourSpeed > modifiedSpd ? 'Outspeed' : (yourSpeed === modifiedSpd ? 'Tie' : 'Outsped')
                }};
            }});

            // Sort by modified speed descending
            processedSpreads.sort((a, b) => b.modifiedSpeed - a.modifiedSpeed);

            // Calculate outspeed percentage
            let outspeedUsage = 0;
            let totalUsage = 0;
            processedSpreads.forEach(s => {{
                totalUsage += s.usage;
                if (s.result === 'Outspeed') outspeedUsage += s.usage;
            }});
            const outspeedPct = totalUsage > 0 ? (outspeedUsage / totalUsage * 100) : 0;

            // Update UI
            document.getElementById('opp-comparison').style.display = 'grid';
            document.getElementById('opp-result').style.display = 'block';
            document.getElementById('opp-speed-table').style.display = 'table';

            document.getElementById('opp-your-speed').textContent = yourSpeed;
            document.getElementById('opp-max-speed').textContent = processedSpreads.length > 0 ? processedSpreads[0].modifiedSpeed : '--';

            const pctEl = document.getElementById('opp-outspeed-pct');
            pctEl.textContent = outspeedPct.toFixed(1) + '%';
            pctEl.className = 'opp-outspeed-pct' + (outspeedPct >= 80 ? '' : (outspeedPct >= 50 ? ' fair' : ' poor'));

            document.getElementById('opp-outspeed-count').textContent = outspeedPct.toFixed(0);
            document.getElementById('opp-name-display').textContent = oppName.split('-').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

            // Build table
            const tbody = document.getElementById('opp-speed-tbody');
            tbody.innerHTML = processedSpreads.map(s => {{
                const resultClass = s.result === 'Outspeed' ? 'result-outspeed' : (s.result === 'Tie' ? 'result-tie' : 'result-outsped');
                return `<tr>
                    <td class="opp-speed-base">${{s.baseSpeed}}</td>
                    <td class="opp-speed-modified">${{s.modifiedSpeed}}</td>
                    <td>${{s.nature}} ${{s.evs}} Spe</td>
                    <td>${{s.usage}}%</td>
                    <td class="opp-result-col ${{resultClass}}">${{s.result}}</td>
                </tr>`;
            }}).join('');
        }}

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {{
            updateNature();
            populateOpponentDropdown();
        }});

        // Initialize immediately as well
        updateNature();
        populateOpponentDropdown();
    </script>
</body>
</html>'''


def create_pokepaste_team_grid_ui(
    pokemon_list: list[dict],
    team_name: Optional[str] = None,
    paste_url: Optional[str] = None,
    editable: bool = False,
) -> str:
    """Create a team grid UI from Pokepaste data with full build details.

    Args:
        pokemon_list: List of Pokemon dicts with species, types, evs, etc.
        team_name: Optional team name for header
        paste_url: Optional pokepaste URL to link
        editable: If True, enables inline editing of EVs, item, nature, tera type
    """
    import json

    # All Pokemon types for tera dropdown
    ALL_TYPES = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice", "Fighting",
                 "Poison", "Ground", "Flying", "Psychic", "Bug", "Rock", "Ghost",
                 "Dragon", "Dark", "Steel", "Fairy"]

    # Common VGC items for datalist
    COMMON_ITEMS = [
        "Choice Scarf", "Choice Band", "Choice Specs", "Life Orb", "Assault Vest",
        "Focus Sash", "Leftovers", "Sitrus Berry", "Lum Berry", "Safety Goggles",
        "Covert Cloak", "Clear Amulet", "Rocky Helmet", "Eviolite", "Black Sludge",
        "Weakness Policy", "Booster Energy", "Expert Belt", "Mystic Water",
        "Charcoal", "Magnet", "Miracle Seed", "Sharp Beak", "Poison Barb",
        "Soft Sand", "Hard Stone", "Spell Tag", "Dragon Fang", "Black Glasses",
        "Metal Coat", "Silk Scarf", "Never-Melt Ice", "Twisted Spoon", "Silver Powder",
        "Wide Lens", "Scope Lens", "Bright Powder", "White Herb", "Mental Herb",
        "Power Herb", "Loaded Dice", "Punching Glove", "Throat Spray", "Terrain Extender",
    ]

    # Common VGC moves for datalist (top moves in VGC)
    COMMON_MOVES = [
        # Protect variants
        "Protect", "Detect", "Wide Guard", "Quick Guard", "Follow Me", "Rage Powder",
        # Priority
        "Fake Out", "Sucker Punch", "Extreme Speed", "Mach Punch", "Bullet Punch",
        "Aqua Jet", "Ice Shard", "Shadow Sneak", "Quick Attack", "Grassy Glide",
        # Speed control
        "Tailwind", "Trick Room", "Icy Wind", "Electroweb", "Scary Face", "Thunder Wave",
        # Weather/terrain
        "Rain Dance", "Sunny Day", "Sandstorm", "Snowscape", "Electric Terrain",
        "Grassy Terrain", "Psychic Terrain", "Misty Terrain",
        # Support moves
        "Helping Hand", "Ally Switch", "Taunt", "Will-O-Wisp", "Thunder Wave",
        "Spore", "Sleep Powder", "Yawn", "Encore", "Disable", "Heal Pulse",
        "Life Dew", "Pollen Puff", "Coaching", "Instruct",
        # Common physical attacks
        "Close Combat", "Drain Punch", "Superpower", "Low Kick", "Sacred Sword",
        "Earthquake", "High Horsepower", "Stomping Tantrum", "Rock Slide", "Stone Edge",
        "Iron Head", "Heavy Slam", "Flash Cannon", "Meteor Mash",
        "Brave Bird", "Aerial Ace", "Acrobatics", "Fly",
        "U-turn", "Flip Turn", "Volt Switch", "Parting Shot",
        "Knock Off", "Crunch", "Foul Play", "Night Slash",
        "Dragon Claw", "Outrage", "Breaking Swipe", "Scale Shot",
        "Poison Jab", "Gunk Shot", "Sludge Bomb",
        "Wood Hammer", "Power Whip", "Seed Bomb", "Horn Leech",
        "Waterfall", "Liquidation", "Aqua Tail", "Wave Crash", "Surging Strikes",
        "Flare Blitz", "Fire Punch", "Blaze Kick",
        "Wild Charge", "Thunder Punch", "Plasma Fists", "Bolt Strike",
        "Ice Punch", "Icicle Crash", "Triple Axel", "Ice Spinner",
        "Psychic Fangs", "Zen Headbutt",
        "Play Rough", "Spirit Break", "Dazzling Gleam",
        "Shadow Claw", "Phantom Force", "Poltergeist",
        "X-Scissor", "First Impression", "Leech Life", "U-turn",
        "Body Slam", "Double-Edge", "Facade", "Last Resort", "Extreme Speed",
        # Common special attacks
        "Moonblast", "Dazzling Gleam", "Draining Kiss",
        "Thunderbolt", "Thunder", "Volt Switch", "Discharge",
        "Ice Beam", "Blizzard", "Freeze-Dry", "Icy Wind",
        "Flamethrower", "Fire Blast", "Heat Wave", "Overheat", "Lava Plume",
        "Hydro Pump", "Scald", "Surf", "Water Spout", "Muddy Water",
        "Energy Ball", "Leaf Storm", "Giga Drain", "Solar Beam",
        "Psychic", "Psyshock", "Expanding Force", "Stored Power",
        "Dark Pulse", "Night Daze", "Snarl",
        "Dragon Pulse", "Draco Meteor", "Spacial Rend",
        "Sludge Bomb", "Sludge Wave", "Venoshock",
        "Shadow Ball", "Hex", "Astral Barrage",
        "Aura Sphere", "Focus Blast", "Vacuum Wave",
        "Earth Power", "Mud Shot", "Scorching Sands",
        "Air Slash", "Hurricane", "Bleakwind Storm",
        "Bug Buzz", "Pollen Puff",
        "Flash Cannon", "Make It Rain",
        "Power Gem", "Ancient Power", "Meteor Beam",
        "Hyper Voice", "Boomburst", "Hyper Beam", "Tera Blast",
        # Signature/notable moves
        "Wicked Blow", "Surging Strikes", "Behemoth Blade", "Behemoth Bash",
        "Spirit Shackle", "Spectral Thief", "Bitter Blade", "Fickle Beam",
        "Population Bomb", "Tidy Up", "Rage Fist", "Comeuppance",
        "Collision Course", "Electro Drift", "Gigaton Hammer", "Blood Moon",
        "Foul Play", "Body Press", "Stored Power", "Psyshield Bash",
    ]

    # Common VGC abilities for datalist
    COMMON_ABILITIES = [
        # Weather setters/abusers
        "Drought", "Drizzle", "Sand Stream", "Snow Warning", "Protosynthesis", "Quark Drive",
        "Chlorophyll", "Swift Swim", "Sand Rush", "Slush Rush", "Solar Power",
        # Terrain
        "Electric Surge", "Grassy Surge", "Psychic Surge", "Misty Surge",
        # Intimidate and anti-intimidate
        "Intimidate", "Clear Body", "White Smoke", "Hyper Cutter", "Inner Focus",
        "Defiant", "Competitive", "Mirror Armor", "Own Tempo", "Oblivious",
        # Offensive abilities
        "Huge Power", "Pure Power", "Guts", "Sheer Force", "Tough Claws",
        "Strong Jaw", "Iron Fist", "Technician", "Skill Link", "Adaptability",
        "Hustle", "Gorilla Tactics", "Unseen Fist", "Neuroforce", "Mold Breaker",
        "Teravolt", "Turboblaze", "Scrappy", "No Guard", "Sniper",
        # Defensive abilities
        "Multiscale", "Marvel Scale", "Thick Fat", "Water Absorb", "Volt Absorb",
        "Flash Fire", "Storm Drain", "Sap Sipper", "Dry Skin", "Levitate",
        "Immunity", "Magic Bounce", "Magic Guard", "Fur Coat", "Ice Scales",
        "Filter", "Solid Rock", "Fluffy", "Heatproof", "Well-Baked Body",
        "Earth Eater", "Bulletproof", "Soundproof", "Regenerator",
        # Speed control
        "Speed Boost", "Prankster", "Gale Wings", "Triage",
        # Utility
        "Fake Out immunity", "Pressure", "Unaware", "Trace", "Imposter",
        "Moxie", "Beast Boost", "Soul-Heart", "Battle Bond", "Libero", "Protean",
        "Friend Guard", "Telepathy", "Flower Veil", "Aroma Veil", "Sweet Veil",
        "Hospitality", "Minds Eye", "Supersweet Syrup", "Embody Aspect",
        # Common abilities
        "Blaze", "Torrent", "Overgrow", "Swarm", "Analytic", "Download",
        "Compound Eyes", "Super Luck", "Serene Grace", "Effect Spore",
        "Flame Body", "Static", "Poison Point", "Cute Charm", "Synchronize",
        "Natural Cure", "Shed Skin", "Poison Heal", "Rattled",
    ]

    # All natures
    ALL_NATURES = [
        "Hardy", "Lonely", "Brave", "Adamant", "Naughty",
        "Bold", "Docile", "Relaxed", "Impish", "Lax",
        "Timid", "Hasty", "Serious", "Jolly", "Naive",
        "Modest", "Mild", "Quiet", "Bashful", "Rash",
        "Calm", "Gentle", "Sassy", "Careful", "Quirky",
    ]

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
        species = pokemon.get("species") or pokemon.get("name", "Unknown")
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

        # Tera type - editable dropdown or static badge
        tera_html = ""
        if editable:
            tera_options = "".join(
                f'<option value="{t}" {"selected" if t.lower() == (tera_type or "").lower() else ""}>{t}</option>'
                for t in ALL_TYPES
            )
            tera_color = get_type_color(tera_type) if tera_type else "#888"
            tera_html = f'''<div class="tera-editor">
                <span class="tera-icon">&#10022;</span>
                <select class="tera-select" id="poke-{i}-tera" data-pokemon-index="{i}" style="--tera-color: {tera_color};" onchange="onTeraChange(this, {i})">
                    <option value="">None</option>
                    {tera_options}
                </select>
            </div>'''
        elif tera_type:
            tera_color = get_type_color(tera_type)
            tera_html = f'<span class="tera-badge" style="--tera-color: {tera_color};"><span class="tera-icon">&#10022;</span> {tera_type}</span>'

        # EV cells - editable inputs with +/- buttons or static display
        ev_cells = ""
        for stat, label in [("hp", "HP"), ("atk", "Atk"), ("def", "Def"), ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe")]:
            val = evs.get(stat, 0)
            color = STAT_COLORS.get(stat, "#888")
            if editable:
                ev_cells += f'''<div class="ev-cell" data-stat="{stat}">
                    <span class="ev-label">{label}</span>
                    <div class="ev-control">
                        <button type="button" class="ev-btn" onclick="adjustEV({i}, '{stat}', -8)">-</button>
                        <input type="number" class="ev-input" id="poke-{i}-ev-{stat}" value="{val}" min="0" max="252" data-pokemon-index="{i}" data-stat="{stat}" style="color: {color};" oninput="onEVChange(this, {i}, '{stat}')" onblur="snapToValidEV(this, {i}, '{stat}')">
                        <button type="button" class="ev-btn" onclick="adjustEV({i}, '{stat}', 8)">+</button>
                    </div>
                </div>'''
            else:
                ev_cells += f'<div class="ev-cell"><span class="ev-label">{label}</span><span class="ev-value" style="color: {color};">{val}</span></div>'

        iv_parts = []
        for stat, label in [("hp", "HP"), ("atk", "Atk"), ("def", "Def"), ("spa", "SpA"), ("spd", "SpD"), ("spe", "Spe")]:
            iv_val = ivs.get(stat, 31)
            if iv_val != 31:
                iv_parts.append(f"{iv_val} {label}")
        ivs_html = f'<div class="ivs-note">IVs: {", ".join(iv_parts)}</div>' if iv_parts else ""

        # IV toggles for editable mode (0 Atk / 0 Spe)
        if editable:
            atk_iv_0 = ivs.get("atk", 31) == 0
            spe_iv_0 = ivs.get("spe", 31) == 0
            iv_toggles_html = f'''<div class="iv-toggles">
                <label class="iv-toggle">
                    <input type="checkbox" id="poke-{i}-iv-0atk" {"checked" if atk_iv_0 else ""} onchange="onIVToggle(this, {i}, 'atk')">
                    <span>0 Atk IV</span>
                </label>
                <label class="iv-toggle">
                    <input type="checkbox" id="poke-{i}-iv-0spe" {"checked" if spe_iv_0 else ""} onchange="onIVToggle(this, {i}, 'spe')">
                    <span>0 Spe IV</span>
                </label>
            </div>'''
        else:
            iv_toggles_html = ""

        moves_html = ""
        for j, move in enumerate(moves[:4]):
            if isinstance(move, dict):
                move_name = move.get("name", "Unknown")
                move_type = move.get("type", "normal")
            else:
                move_name = str(move)
                move_type = "normal"
            move_color = get_type_color(move_type)
            if editable:
                moves_html += f'''<div class="move-slot">
                    <input type="text" class="move-input" id="poke-{i}-move-{j}"
                           value="{move_name}" list="move-options"
                           data-pokemon-index="{i}" data-move-slot="{j}"
                           style="--move-color: {move_color};"
                           onchange="onMoveChange(this, {i}, {j})"
                           onfocus="this.select()">
                </div>'''
            else:
                moves_html += f'<span class="move-pill" style="--move-color: {move_color};">{move_name}</span>'
        # Fill remaining slots if editable
        if editable:
            for j in range(len(moves), 4):
                moves_html += f'''<div class="move-slot">
                    <input type="text" class="move-input" id="poke-{i}-move-{j}"
                           value="" list="move-options"
                           data-pokemon-index="{i}" data-move-slot="{j}"
                           placeholder="Add move..."
                           onchange="onMoveChange(this, {i}, {j})"
                           onfocus="this.select()">
                </div>'''

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
        nature_hint = ""
        if nature_info[0] and nature_info[1]:
            boost_label = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}.get(nature_info[0], "")
            drop_label = {"atk": "Atk", "def": "Def", "spa": "SpA", "spd": "SpD", "spe": "Spe"}.get(nature_info[1], "")
            nature_hint = f'(+{boost_label} -{drop_label})'

        # Build editable or static item display
        if editable:
            item_html = f'''<div class="item-display">
                <span class="label">@</span>
                <input type="text" class="item-input" id="poke-{i}-item" value="{item or ''}" list="item-options" placeholder="None" data-pokemon-index="{i}" onchange="onItemChange(this, {i})">
            </div>'''
        else:
            item_html = f'<div class="item-display"><span class="label">@</span><span class="value">{item or "None"}</span></div>'

        # Build editable or static ability display
        if editable:
            ability_html = f'''<div class="ability-display">
                <input type="text" class="ability-input" id="poke-{i}-ability" value="{ability or ''}" list="ability-options" placeholder="Ability" data-pokemon-index="{i}" onchange="onAbilityChange(this, {i})">
            </div>'''
        else:
            ability_html = f'<div class="ability-display"><span class="value">{ability or "Unknown"}</span></div>'

        # Build editable or static nature display
        if editable:
            nature_options = "".join(
                f'<option value="{n}" {"selected" if n.lower() == nature.lower() else ""}>{n}</option>'
                for n in ALL_NATURES
            )
            nature_html = f'''<div class="nature-display">
                <select class="nature-select" id="poke-{i}-nature" data-pokemon-index="{i}" onchange="onNatureChange(this, {i})">
                    {nature_options}
                </select>
                <span class="nature-hint" id="poke-{i}-nature-hint">{nature_hint}</span>
            </div>'''
        else:
            nature_display = f'{nature} <span class="nature-hint">{nature_hint}</span>' if nature_hint else nature
            nature_html = f'<div class="nature-display">{nature_display}</div>'

        # Build editable or static EV total display
        if editable:
            ev_total_html = f'<div class="ev-total" id="poke-{i}-ev-total"><span class="ev-total-value">{ev_total}</span><span class="ev-total-max">/508</span></div>'
        else:
            ev_total_html = f'<div class="ev-total">EVs: {ev_total}/508</div>'

        # Build stats display with IDs for editable mode
        if editable:
            stats_display = " / ".join(
                f'<span id="poke-{i}-stat-{s}" style="color: {STAT_COLORS.get(s, "#888")};">{final_stats.get(s, "?")}</span>'
                for s in ["hp", "atk", "def", "spa", "spd", "spe"]
            )
        else:
            stats_display = " / ".join(
                f'<span style="color: {STAT_COLORS.get(s, "#888")};">{final_stats.get(s, "?")}</span>'
                for s in ["hp", "atk", "def", "spa", "spd", "spe"]
            )

        delay = i * 0.1
        cards_html += f"""
        <div class="paste-card" data-pokemon-index="{i}" style="animation-delay: {delay}s; --type-color: {get_type_color(primary_type)};">
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
                    {item_html}
                    {ability_html}
                </div>
                <div class="nature-ev-row">
                    {nature_html}
                    {ev_total_html}
                </div>
                <div class="ev-grid">{ev_cells}</div>
                {"" if not editable else f'<div class="ev-warning" id="poke-{i}-ev-warning"></div>'}
                {iv_toggles_html}
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
.move-slot {{ flex: 1; min-width: 45%; }}
.move-input {{ width: 100%; background: rgba(255, 255, 255, 0.05); border: 1px solid var(--move-color, rgba(255, 255, 255, 0.15)); border-radius: 8px; padding: 5px 8px; font-size: 11px; font-weight: 600; color: #fff; transition: all 0.2s; box-shadow: inset 0 1px 2px rgba(0, 0, 0, 0.1); }}
.move-input:focus {{ outline: none; border-color: #6366f1; background: rgba(99, 102, 241, 0.1); box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2); }}
.move-input::placeholder {{ color: #52525b; font-style: italic; }}
.final-stats {{ padding-top: 8px; border-top: 1px solid rgba(255, 255, 255, 0.05); font-size: 12px; }}
.stats-label {{ color: #71717a; margin-right: 6px; }}
.stats-values {{ font-family: 'SF Mono', 'Consolas', monospace; font-weight: 600; }}
/* Editable field styles */
.ev-control {{ display: flex; align-items: center; justify-content: center; gap: 2px; }}
.ev-btn {{ width: 20px; height: 20px; border: 1px solid rgba(255, 255, 255, 0.15); background: rgba(255, 255, 255, 0.05); color: #e4e4e7; border-radius: 4px; cursor: pointer; font-size: 12px; font-weight: bold; display: flex; align-items: center; justify-content: center; transition: all 0.15s; }}
.ev-btn:hover {{ background: rgba(99, 102, 241, 0.3); border-color: #6366f1; }}
.ev-btn:active {{ background: #6366f1; transform: scale(0.95); }}
.ev-input {{ width: 40px; background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; padding: 3px 2px; font-family: 'SF Mono', 'Consolas', monospace; font-size: 12px; font-weight: 700; text-align: center; color: inherit; transition: border-color 0.2s, background 0.2s; -moz-appearance: textfield; }}
.ev-input::-webkit-outer-spin-button, .ev-input::-webkit-inner-spin-button {{ -webkit-appearance: none; margin: 0; }}
.ev-input:focus {{ outline: none; border-color: #6366f1; background: rgba(99, 102, 241, 0.1); }}
.ev-input.invalid {{ border-color: #ef4444; background: rgba(239, 68, 68, 0.1); }}
.iv-toggles {{ display: flex; justify-content: center; gap: 12px; margin-top: 6px; font-size: 10px; }}
.iv-toggle {{ display: flex; align-items: center; gap: 4px; color: #71717a; cursor: pointer; }}
.iv-toggle input {{ width: 12px; height: 12px; cursor: pointer; }}
.iv-toggle input:checked + span {{ color: #06b6d4; }}
.item-input {{ background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #e4e4e7; font-weight: 500; width: 120px; transition: border-color 0.2s; }}
.item-input:focus {{ outline: none; border-color: #f59e0b; }}
.item-input::placeholder {{ color: #71717a; }}
.ability-input {{ background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #a78bfa; font-weight: 500; width: 120px; transition: border-color 0.2s; }}
.ability-input:focus {{ outline: none; border-color: #a78bfa; background: rgba(167, 139, 250, 0.1); }}
.ability-input::placeholder {{ color: #71717a; }}
.nature-select, .tera-select {{ background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.1); border-radius: 4px; padding: 4px 8px; font-size: 12px; color: #e4e4e7; font-weight: 600; cursor: pointer; transition: border-color 0.2s; }}
.nature-select:focus, .tera-select:focus {{ outline: none; border-color: #6366f1; }}
.nature-select option, .tera-select option {{ background: #1a1a2e; color: #e4e4e7; }}
.tera-editor {{ display: inline-flex; align-items: center; gap: 4px; }}
.tera-select {{ color: var(--tera-color, #e4e4e7); border-color: var(--tera-color, rgba(255, 255, 255, 0.1)); border-style: dashed; }}
.ev-total.over-limit {{ background: rgba(239, 68, 68, 0.2); color: #f87171; }}
.ev-total.at-limit {{ background: rgba(34, 197, 94, 0.2); color: #22c55e; }}
.ev-total.incomplete {{ background: rgba(251, 191, 36, 0.2); color: #fbbf24; }}
.ev-warning {{ display: none; font-size: 10px; margin-top: 4px; padding: 4px 8px; border-radius: 4px; border-left: 2px solid; }}
.ev-warning.visible {{ display: block; }}
.ev-warning.incomplete {{ color: #fbbf24; background: rgba(251, 191, 36, 0.1); border-color: #fbbf24; }}
.ev-warning.over {{ color: #f87171; background: rgba(239, 68, 68, 0.1); border-color: #f87171; }}
.change-summary {{ margin-top: 20px; padding: 16px; background: rgba(99, 102, 241, 0.08); border: 1px solid rgba(99, 102, 241, 0.2); border-radius: 12px; display: none; }}
.change-summary.visible {{ display: block; animation: fadeSlideIn 0.3s ease; }}
.export-section {{ margin-top: 20px; display: flex; gap: 12px; justify-content: center; flex-wrap: wrap; }}
.export-btn {{ display: inline-flex; align-items: center; gap: 8px; padding: 12px 24px; border-radius: 12px; font-size: 14px; font-weight: 600; cursor: pointer; transition: all 0.2s; border: none; }}
.export-btn .btn-icon {{ font-size: 16px; }}
.export-btn.primary {{ background: linear-gradient(135deg, #6366f1, #8b5cf6); color: #fff; box-shadow: 0 4px 15px rgba(99, 102, 241, 0.3); }}
.export-btn.primary:hover {{ transform: translateY(-2px); box-shadow: 0 6px 20px rgba(99, 102, 241, 0.4); }}
.export-btn.secondary {{ background: rgba(255, 255, 255, 0.05); border: 1px solid rgba(255, 255, 255, 0.15); color: #e4e4e7; }}
.export-btn.secondary:hover {{ background: rgba(255, 255, 255, 0.1); border-color: rgba(255, 255, 255, 0.25); }}
.export-btn:active {{ transform: scale(0.98); }}
.copy-toast {{ position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%); background: linear-gradient(135deg, #22c55e, #16a34a); color: #fff; padding: 12px 24px; border-radius: 12px; font-weight: 600; box-shadow: 0 4px 20px rgba(34, 197, 94, 0.3); opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 1000; }}
.copy-toast.visible {{ opacity: 1; }}
.change-summary-header {{ display: flex; align-items: center; gap: 8px; margin-bottom: 12px; font-size: 14px; font-weight: 600; color: #a78bfa; }}
.change-count {{ font-size: 12px; color: #71717a; font-weight: 400; }}
.change-list {{ display: flex; flex-direction: column; gap: 6px; }}
.change-item {{ font-size: 12px; color: #e4e4e7; padding: 6px 10px; background: rgba(255, 255, 255, 0.03); border-radius: 6px; border-left: 2px solid #6366f1; }}
.change-item .pokemon-name {{ font-weight: 600; color: #fff; }}
.change-item .field-name {{ color: #a78bfa; }}
.change-item .old-value {{ color: #f87171; text-decoration: line-through; }}
.change-item .new-value {{ color: #22c55e; }}
    </style>
</head>
<body>
    <div class="team-container" data-team-state="" data-is-dirty="false">
        <div class="team-header">
            <div class="header-left">
                <span class="team-title">{header_title}</span>
                <span class="team-count">{pokemon_count} Pokemon</span>
            </div>
            {url_display}
        </div>
        <div class="team-grid">{cards_html}</div>
        {"" if not editable else '''<div class="change-summary" id="change-summary">
            <div class="change-summary-header">
                <span>Changes Made</span>
                <span class="change-count" id="change-count">(0 changes)</span>
            </div>
            <div class="change-list" id="change-list"></div>
        </div>'''}
        {"" if not editable else '''<div class="export-section">
            <button class="export-btn primary" onclick="copyShowdownFormat()">
                <span class="btn-icon">&#128203;</span>
                Copy Showdown Format
            </button>
            <button class="export-btn secondary" onclick="openPokepaste()">
                <span class="btn-icon">&#128279;</span>
                Create Pokepaste Link
            </button>
        </div>'''}
    </div>
    {"" if not editable else f'''<datalist id="item-options">
        {"".join(f'<option value="{item}">' for item in COMMON_ITEMS)}
    </datalist>'''}
    {"" if not editable else f'''<datalist id="move-options">
        {"".join(f'<option value="{move}">' for move in COMMON_MOVES)}
    </datalist>'''}
    {"" if not editable else f'''<datalist id="ability-options">
        {"".join(f'<option value="{ability}">' for ability in COMMON_ABILITIES)}
    </datalist>'''}
    {"" if not editable else f'''<script>
        // Initial team state
        const INITIAL_TEAM_STATE = {json.dumps(pokemon_list, default=str)};
        let teamState = JSON.parse(JSON.stringify(INITIAL_TEAM_STATE));
        let changeHistory = [];
        let isDirty = false;

        // Nature modifiers
        const NATURE_MODS = {{
            hardy: [null, null], lonely: ["atk", "def"], brave: ["atk", "spe"],
            adamant: ["atk", "spa"], naughty: ["atk", "spd"],
            bold: ["def", "atk"], docile: [null, null], relaxed: ["def", "spe"],
            impish: ["def", "spa"], lax: ["def", "spd"],
            timid: ["spe", "atk"], hasty: ["spe", "def"], serious: [null, null],
            jolly: ["spe", "spa"], naive: ["spe", "spd"],
            modest: ["spa", "atk"], mild: ["spa", "def"],
            quiet: ["spa", "spe"], bashful: [null, null], rash: ["spa", "spd"],
            calm: ["spd", "atk"], gentle: ["spd", "def"],
            sassy: ["spd", "spe"], careful: ["spd", "spa"], quirky: [null, null]
        }};

        const STAT_COLORS = {{
            hp: "#ff5959", atk: "#f5ac78", def: "#fae078",
            spa: "#9db7f5", spd: "#a7db8d", spe: "#fa92b2"
        }};

        const TYPE_COLORS = {{
            normal: "#A8A878", fire: "#F08030", water: "#6890F0", electric: "#F8D030",
            grass: "#78C850", ice: "#98D8D8", fighting: "#C03028", poison: "#A040A0",
            ground: "#E0C068", flying: "#A890F0", psychic: "#F85888", bug: "#A8B820",
            rock: "#B8A038", ghost: "#705898", dragon: "#7038F8", dark: "#705848",
            steel: "#B8B8D0", fairy: "#EE99AC"
        }};

        function calcStat(base, ev, iv, natureMod, isHP) {{
            iv = iv || 31;
            if (isHP) {{
                return Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 50 + 10;
            }}
            return Math.floor((Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 5) * natureMod);
        }}

        function getNatureMods(natureName) {{
            const mods = {{ hp: 1.0, atk: 1.0, def: 1.0, spa: 1.0, spd: 1.0, spe: 1.0 }};
            const nature = NATURE_MODS[natureName.toLowerCase()];
            if (nature && nature[0]) mods[nature[0]] = 1.1;
            if (nature && nature[1]) mods[nature[1]] = 0.9;
            return mods;
        }}

        function recalculateFinalStats(pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const nature = pokemon.nature || "Serious";
            const mods = getNatureMods(nature);
            const statKeys = ["hp", "atk", "def", "spa", "spd", "spe"];

            statKeys.forEach(stat => {{
                const base = (pokemon.base_stats && pokemon.base_stats[stat]) || 80;
                const iv = (pokemon.ivs && pokemon.ivs[stat]) || 31;
                const ev = (pokemon.evs && pokemon.evs[stat]) || 0;
                const finalStat = calcStat(base, ev, iv, mods[stat], stat === "hp");
                const statEl = document.getElementById(`poke-${{pokemonIndex}}-stat-${{stat}}`);
                if (statEl) statEl.textContent = finalStat;
            }});
        }}

        function updateEVTotal(pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const evs = pokemon.evs || {{}};
            const total = (evs.hp || 0) + (evs.atk || 0) + (evs.def || 0) +
                          (evs.spa || 0) + (evs.spd || 0) + (evs.spe || 0);
            const totalEl = document.getElementById(`poke-${{pokemonIndex}}-ev-total`);
            if (totalEl) {{
                const valueEl = totalEl.querySelector('.ev-total-value');
                if (valueEl) valueEl.textContent = total;
                totalEl.classList.toggle('over-limit', total > 508);
                totalEl.classList.toggle('at-limit', total === 508);
                totalEl.classList.toggle('incomplete', total < 508 && total > 0);
            }}

            // Update warning message
            const warningEl = document.getElementById(`poke-${{pokemonIndex}}-ev-warning`);
            if (warningEl) {{
                if (total > 508) {{
                    warningEl.textContent = `Over limit by ${{total - 508}} EVs`;
                    warningEl.className = 'ev-warning visible over';
                }} else if (total < 508) {{
                    warningEl.textContent = `${{508 - total}} EVs remaining`;
                    warningEl.className = 'ev-warning visible incomplete';
                }} else {{
                    warningEl.className = 'ev-warning';
                }}
            }}
            return total;
        }}

        function recordChange(pokemonIndex, field, oldValue, newValue) {{
            const pokemon = teamState[pokemonIndex];
            changeHistory.push({{
                pokemonIndex,
                pokemonName: pokemon.species,
                field,
                oldValue: String(oldValue),
                newValue: String(newValue),
                timestamp: Date.now()
            }});
            isDirty = true;
            updateChangeSummary();
            emitTeamChange();
        }}

        function updateChangeSummary() {{
            const summaryEl = document.getElementById('change-summary');
            const countEl = document.getElementById('change-count');
            const listEl = document.getElementById('change-list');
            if (!summaryEl) return;

            if (changeHistory.length > 0) {{
                summaryEl.classList.add('visible');
                countEl.textContent = `(${{changeHistory.length}} change${{changeHistory.length !== 1 ? 's' : ''}})`;
                const recentChanges = changeHistory.slice(-10);
                listEl.innerHTML = recentChanges.map(c => `
                    <div class="change-item">
                        <span class="pokemon-name">${{c.pokemonName}}</span>:
                        <span class="field-name">${{c.field}}</span>
                        <span class="old-value">${{c.oldValue || 'None'}}</span> &#8594;
                        <span class="new-value">${{c.newValue || 'None'}}</span>
                    </div>
                `).join('');
            }} else {{
                summaryEl.classList.remove('visible');
            }}
        }}

        function emitTeamChange() {{
            const container = document.querySelector('.team-container');
            if (container) {{
                container.setAttribute('data-team-state', JSON.stringify(teamState));
                container.setAttribute('data-is-dirty', isDirty ? 'true' : 'false');
            }}
            console.log('VGC_TEAM_UPDATE', {{ team: teamState, changes: changeHistory, isDirty }});
        }}

        function onEVChange(input, pokemonIndex, stat) {{
            let value = parseInt(input.value) || 0;
            value = Math.max(0, Math.min(252, value));

            const pokemon = teamState[pokemonIndex];
            if (!pokemon.evs) pokemon.evs = {{}};
            const oldValue = pokemon.evs[stat] || 0;

            // Check total
            const currentTotal = updateEVTotal(pokemonIndex);
            const newTotal = currentTotal - oldValue + value;

            if (newTotal > 508) {{
                value = Math.max(0, 508 - (currentTotal - oldValue));
                input.classList.add('invalid');
            }} else {{
                input.classList.remove('invalid');
            }}

            if (value !== oldValue) {{
                pokemon.evs[stat] = value;
                input.value = value;
                recordChange(pokemonIndex, `${{stat.toUpperCase()}} EVs`, oldValue, value);
                updateEVTotal(pokemonIndex);
                recalculateFinalStats(pokemonIndex);
            }}
        }}

        function onItemChange(input, pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const oldValue = pokemon.item || '';
            const newValue = input.value.trim();
            if (newValue !== oldValue) {{
                pokemon.item = newValue;
                recordChange(pokemonIndex, 'Item', oldValue, newValue);
            }}
        }}

        function onAbilityChange(input, pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const oldValue = pokemon.ability || '';
            const newValue = input.value.trim();
            if (newValue !== oldValue) {{
                pokemon.ability = newValue;
                recordChange(pokemonIndex, 'Ability', oldValue, newValue);
            }}
        }}

        function onMoveChange(input, pokemonIndex, moveSlot) {{
            const pokemon = teamState[pokemonIndex];
            if (!pokemon.moves) pokemon.moves = ['', '', '', ''];
            // Ensure moves array has 4 slots
            while (pokemon.moves.length < 4) pokemon.moves.push('');

            const oldValue = pokemon.moves[moveSlot] || '';
            const newValue = input.value.trim();
            if (newValue !== oldValue) {{
                pokemon.moves[moveSlot] = newValue;
                recordChange(pokemonIndex, `Move ${{moveSlot + 1}}`, oldValue || '(empty)', newValue || '(empty)');
            }}
        }}

        function onNatureChange(select, pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const oldValue = pokemon.nature || 'Serious';
            const newValue = select.value;
            if (newValue !== oldValue) {{
                pokemon.nature = newValue;

                // Update nature hint
                const hintEl = document.getElementById(`poke-${{pokemonIndex}}-nature-hint`);
                if (hintEl) {{
                    const [boosted, lowered] = NATURE_MODS[newValue.toLowerCase()] || [null, null];
                    if (boosted && lowered) {{
                        const labelMap = {{ atk: 'Atk', def: 'Def', spa: 'SpA', spd: 'SpD', spe: 'Spe' }};
                        hintEl.textContent = `(+${{labelMap[boosted]}} -${{labelMap[lowered]}})`;
                    }} else {{
                        hintEl.textContent = '';
                    }}
                }}

                recordChange(pokemonIndex, 'Nature', oldValue, newValue);
                recalculateFinalStats(pokemonIndex);
            }}
        }}

        function onTeraChange(select, pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const oldValue = pokemon.tera_type || '';
            const newValue = select.value;
            if (newValue !== oldValue) {{
                pokemon.tera_type = newValue;
                const teraColor = TYPE_COLORS[newValue.toLowerCase()] || '#888';
                select.style.setProperty('--tera-color', teraColor);
                recordChange(pokemonIndex, 'Tera Type', oldValue, newValue);
            }}
        }}

        // Valid EV values: 0, 4, 12, 20, 28, ... 252 (first 4, then +8 increments)
        function getValidEVValues() {{
            const valid = [0, 4];
            for (let v = 12; v <= 252; v += 8) valid.push(v);
            return valid;
        }}

        function getCurrentEVTotal(pokemonIndex) {{
            const pokemon = teamState[pokemonIndex];
            const evs = pokemon.evs || {{}};
            return (evs.hp || 0) + (evs.atk || 0) + (evs.def || 0) +
                   (evs.spa || 0) + (evs.spd || 0) + (evs.spe || 0);
        }}

        function adjustEV(pokemonIndex, stat, delta) {{
            const input = document.getElementById(`poke-${{pokemonIndex}}-ev-${{stat}}`);
            if (!input) return;

            const pokemon = teamState[pokemonIndex];
            if (!pokemon.evs) pokemon.evs = {{}};
            let currentVal = pokemon.evs[stat] || 0;
            let newVal;

            if (delta > 0) {{
                // Incrementing: 0->4->12->20->28->36...->252
                if (currentVal === 0) newVal = 4;
                else if (currentVal < 252) newVal = Math.min(252, currentVal + 8);
                else newVal = 252;
            }} else {{
                // Decrementing: 252->244->236...->12->4->0
                if (currentVal <= 4) newVal = 0;
                else newVal = Math.max(4, currentVal - 8);
            }}

            // Check total EV limit (508 max)
            const totalBefore = getCurrentEVTotal(pokemonIndex);
            const totalAfter = totalBefore - currentVal + newVal;
            if (totalAfter > 508) {{
                // Cap to what's available
                newVal = currentVal + (508 - totalBefore);
                if (newVal < 4 && newVal > 0) newVal = 4;
                if (newVal < 0) newVal = 0;
            }}

            if (newVal !== currentVal) {{
                pokemon.evs[stat] = newVal;
                input.value = newVal;
                recordChange(pokemonIndex, `${{stat.toUpperCase()}} EVs`, currentVal, newVal);
                updateEVTotal(pokemonIndex);
                recalculateFinalStats(pokemonIndex);
            }}
        }}

        function snapToValidEV(input, pokemonIndex, stat) {{
            // Auto-correct typed value to nearest valid EV
            const validValues = getValidEVValues();
            let val = parseInt(input.value) || 0;
            val = Math.max(0, Math.min(252, val));

            // Find nearest valid value
            let nearest = validValues.reduce((prev, curr) =>
                Math.abs(curr - val) < Math.abs(prev - val) ? curr : prev
            );

            const pokemon = teamState[pokemonIndex];
            if (!pokemon.evs) pokemon.evs = {{}};
            const oldVal = pokemon.evs[stat] || 0;

            // Check total EV limit
            const totalBefore = getCurrentEVTotal(pokemonIndex);
            const totalAfter = totalBefore - oldVal + nearest;
            if (totalAfter > 508) {{
                nearest = Math.max(0, oldVal + (508 - totalBefore));
                // Re-snap to valid value
                nearest = validValues.reduce((prev, curr) =>
                    curr <= nearest && curr > prev ? curr : prev, 0);
            }}

            if (nearest !== oldVal) {{
                pokemon.evs[stat] = nearest;
                input.value = nearest;
                recordChange(pokemonIndex, `${{stat.toUpperCase()}} EVs`, oldVal, nearest);
                updateEVTotal(pokemonIndex);
                recalculateFinalStats(pokemonIndex);
            }} else {{
                input.value = nearest;
            }}
        }}

        function onIVToggle(checkbox, pokemonIndex, stat) {{
            const pokemon = teamState[pokemonIndex];
            if (!pokemon.ivs) pokemon.ivs = {{ hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }};

            const newIV = checkbox.checked ? 0 : 31;
            const oldIV = pokemon.ivs[stat] !== undefined ? pokemon.ivs[stat] : 31;

            if (newIV !== oldIV) {{
                pokemon.ivs[stat] = newIV;
                recordChange(pokemonIndex, `${{stat.toUpperCase()}} IV`, oldIV, newIV);
                recalculateFinalStats(pokemonIndex);
            }}
        }}

        // Format EVs for Showdown export
        function formatEVsForExport(evs) {{
            if (!evs) return '';
            const parts = [];
            const order = [['hp', 'HP'], ['atk', 'Atk'], ['def', 'Def'], ['spa', 'SpA'], ['spd', 'SpD'], ['spe', 'Spe']];
            for (const [key, label] of order) {{
                if (evs[key] && evs[key] > 0) {{
                    parts.push(`${{evs[key]}} ${{label}}`);
                }}
            }}
            return parts.join(' / ');
        }}

        // Format IVs for Showdown export (only non-31 IVs)
        function formatIVsForExport(ivs) {{
            if (!ivs) return '';
            const parts = [];
            const order = [['hp', 'HP'], ['atk', 'Atk'], ['def', 'Def'], ['spa', 'SpA'], ['spd', 'SpD'], ['spe', 'Spe']];
            for (const [key, label] of order) {{
                if (ivs[key] !== undefined && ivs[key] !== 31) {{
                    parts.push(`${{ivs[key]}} ${{label}}`);
                }}
            }}
            return parts.join(' / ');
        }}

        // Generate Showdown-compatible text for the team
        function generateShowdownText() {{
            let output = '';
            for (const poke of teamState) {{
                // Species @ Item
                const name = poke.species || poke.name || 'Unknown';
                const item = poke.item || '';
                output += item ? `${{name}} @ ${{item}}\\n` : `${{name}}\\n`;

                // Ability
                if (poke.ability) {{
                    output += `Ability: ${{poke.ability}}\\n`;
                }}

                // Tera Type
                if (poke.tera_type) {{
                    output += `Tera Type: ${{poke.tera_type}}\\n`;
                }}

                // EVs
                const evStr = formatEVsForExport(poke.evs);
                if (evStr) {{
                    output += `EVs: ${{evStr}}\\n`;
                }}

                // Nature
                if (poke.nature) {{
                    output += `${{poke.nature}} Nature\\n`;
                }}

                // IVs (only if any are not 31)
                const ivStr = formatIVsForExport(poke.ivs);
                if (ivStr) {{
                    output += `IVs: ${{ivStr}}\\n`;
                }}

                // Moves
                const moves = poke.moves || [];
                for (const move of moves) {{
                    if (move && move.trim()) {{
                        output += `- ${{move}}\\n`;
                    }}
                }}

                output += '\\n';
            }}
            return output.trim();
        }}

        // Copy team to clipboard in Showdown format
        function copyShowdownFormat() {{
            const showdownText = generateShowdownText();
            navigator.clipboard.writeText(showdownText).then(() => {{
                showToast('Team copied to clipboard!');
            }}).catch(err => {{
                console.error('Copy failed:', err);
                showToast('Copy failed - check console', true);
            }});
        }}

        // Open Pokepaste in new tab with team
        function openPokepaste() {{
            const showdownText = generateShowdownText();
            navigator.clipboard.writeText(showdownText).then(() => {{
                showToast('Team copied! Opening pokepast.es...');
                setTimeout(() => {{
                    window.open('https://pokepast.es/create', '_blank');
                }}, 500);
            }}).catch(err => {{
                // Fallback: just open the page
                window.open('https://pokepast.es/create', '_blank');
            }});
        }}

        // Show toast notification
        function showToast(message, isError = false) {{
            let toast = document.getElementById('copy-toast');
            if (!toast) {{
                toast = document.createElement('div');
                toast.id = 'copy-toast';
                toast.className = 'copy-toast';
                document.body.appendChild(toast);
            }}
            toast.textContent = message;
            if (isError) {{
                toast.style.background = 'linear-gradient(135deg, #ef4444, #dc2626)';
            }} else {{
                toast.style.background = 'linear-gradient(135deg, #22c55e, #16a34a)';
            }}
            toast.classList.add('visible');
            setTimeout(() => {{
                toast.classList.remove('visible');
            }}, 2500);
        }}

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {{
            for (let i = 0; i < teamState.length; i++) {{
                updateEVTotal(i);
            }}
            emitTeamChange();
        }});
    </script>'''}
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
            species = pokemon.get("species") or pokemon.get("name", "Unknown")
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


def create_team_diff_ui(diff) -> str:
    """Create HTML UI for team version diff visualization.

    Args:
        diff: TeamDiff object from vgc_mcp_core.diff

    Returns:
        Complete HTML string for the diff visualization
    """
    from vgc_mcp_core.diff.models import ChangeType, FieldType

    styles = get_shared_styles()
    summary = diff.summary

    # Build summary badges
    badges_html = ""
    if summary.get("modified", 0) > 0:
        badges_html += f'<span class="diff-badge modified">{summary["modified"]} modified</span>'
    if summary.get("added", 0) > 0:
        badges_html += f'<span class="diff-badge added">{summary["added"]} added</span>'
    if summary.get("removed", 0) > 0:
        badges_html += f'<span class="diff-badge removed">{summary["removed"]} removed</span>'

    # Build sections for each type of change
    sections_html = ""

    # REMOVED Pokemon
    removed_pokemon = [d for d in diff.pokemon_diffs if d.change_type == ChangeType.REMOVED]
    if removed_pokemon:
        removed_cards = ""
        for i, pokemon_diff in enumerate(removed_pokemon):
            sprite_url = get_sprite_url(pokemon_diff.species)
            removed_cards += f'''
            <div class="diff-pokemon-card removed" style="animation-delay: {i * 0.1}s;">
                <div class="pokemon-header">
                    <img src="{sprite_url}" alt="{pokemon_diff.species}" class="pokemon-sprite"
                         onerror="this.src='https://img.pokemondb.net/sprites/home/normal/{pokemon_diff.species.lower().replace(' ', '-')}.png'">
                    <div class="pokemon-info">
                        <span class="pokemon-name">{pokemon_diff.species}</span>
                        <span class="change-type-badge removed">Removed</span>
                    </div>
                </div>
                <div class="removed-note">No longer on team in {diff.version2_name}</div>
            </div>
            '''
        sections_html += f'''
        <div class="diff-section">
            <div class="section-header removed">
                <span class="section-icon">&#10060;</span>
                <span class="section-title">Removed</span>
            </div>
            <div class="section-content">{removed_cards}</div>
        </div>
        '''

    # ADDED Pokemon
    added_pokemon = [d for d in diff.pokemon_diffs if d.change_type == ChangeType.ADDED]
    if added_pokemon:
        added_cards = ""
        for i, pokemon_diff in enumerate(added_pokemon):
            sprite_url = get_sprite_url(pokemon_diff.species)
            data = pokemon_diff.pokemon_data or {}

            # Format details for added Pokemon
            details = []
            if data.get("item"):
                details.append(f"@ {data['item']}")
            if data.get("ability"):
                details.append(data["ability"])
            if data.get("nature"):
                details.append(f"{data['nature']} Nature")

            details_html = " | ".join(details) if details else ""

            added_cards += f'''
            <div class="diff-pokemon-card added" style="animation-delay: {i * 0.1}s;">
                <div class="pokemon-header">
                    <img src="{sprite_url}" alt="{pokemon_diff.species}" class="pokemon-sprite"
                         onerror="this.src='https://img.pokemondb.net/sprites/home/normal/{pokemon_diff.species.lower().replace(' ', '-')}.png'">
                    <div class="pokemon-info">
                        <span class="pokemon-name">{pokemon_diff.species}</span>
                        <span class="change-type-badge added">New</span>
                    </div>
                </div>
                <div class="added-details">{details_html}</div>
            </div>
            '''
        sections_html += f'''
        <div class="diff-section">
            <div class="section-header added">
                <span class="section-icon">&#10004;</span>
                <span class="section-title">Added</span>
            </div>
            <div class="section-content">{added_cards}</div>
        </div>
        '''

    # MODIFIED Pokemon
    modified_pokemon = [d for d in diff.pokemon_diffs if d.change_type == ChangeType.MODIFIED]
    if modified_pokemon:
        modified_cards = ""
        for i, pokemon_diff in enumerate(modified_pokemon):
            sprite_url = get_sprite_url(pokemon_diff.species)

            # Build changes list
            changes_html = ""
            for change in pokemon_diff.changes:
                field_name = change.field.value.replace("_", " ").title()

                # Format before/after based on field type
                if change.field == FieldType.MOVES and change.move_changes:
                    mc = change.move_changes
                    before_html = ""
                    after_html = ""
                    if mc.removed:
                        before_html = f'<span class="diff-before">-{", ".join(mc.removed)}</span>'
                    if mc.added:
                        after_html = f'<span class="diff-after">+{", ".join(mc.added)}</span>'
                    diff_content = f"{before_html} {after_html}".strip()
                else:
                    diff_content = f'''
                    <span class="diff-before">{change.before}</span>
                    <span class="diff-arrow">&#8594;</span>
                    <span class="diff-after">{change.after}</span>
                    '''

                changes_html += f'''
                <div class="change-row">
                    <div class="change-field">{field_name}</div>
                    <div class="change-diff">{diff_content}</div>
                    <div class="change-reason">{change.reason}</div>
                </div>
                '''

            modified_cards += f'''
            <div class="diff-pokemon-card modified" style="animation-delay: {i * 0.1}s;">
                <div class="pokemon-header">
                    <img src="{sprite_url}" alt="{pokemon_diff.species}" class="pokemon-sprite"
                         onerror="this.src='https://img.pokemondb.net/sprites/home/normal/{pokemon_diff.species.lower().replace(' ', '-')}.png'">
                    <div class="pokemon-info">
                        <span class="pokemon-name">{pokemon_diff.species}</span>
                        <span class="changes-count">{len(pokemon_diff.changes)} change{'s' if len(pokemon_diff.changes) != 1 else ''}</span>
                    </div>
                </div>
                <div class="changes-list">{changes_html}</div>
            </div>
            '''
        sections_html += f'''
        <div class="diff-section">
            <div class="section-header modified">
                <span class="section-icon">&#9998;</span>
                <span class="section-title">Modified</span>
            </div>
            <div class="section-content">{modified_cards}</div>
        </div>
        '''

    # Unchanged Pokemon footer
    unchanged_html = ""
    if diff.unchanged:
        unchanged_list = ", ".join(diff.unchanged)
        unchanged_html = f'''
        <div class="unchanged-section">
            <span class="unchanged-label">Unchanged:</span>
            <span class="unchanged-list">{unchanged_list}</span>
        </div>
        '''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        {styles}

        .diff-container {{
            background: var(--bg-card);
            border-radius: var(--radius-lg);
            padding: var(--space-lg);
            border: 1px solid var(--glass-border);
            max-width: 800px;
            margin: 0 auto;
        }}

        .diff-header {{
            margin-bottom: var(--space-lg);
            padding-bottom: var(--space-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .diff-title {{
            font-size: 20px;
            font-weight: 600;
            color: var(--text-primary);
            margin-bottom: var(--space-xs);
        }}

        .diff-versions {{
            font-size: 13px;
            color: var(--text-secondary);
            margin-bottom: var(--space-sm);
        }}

        .diff-badges {{
            display: flex;
            gap: var(--space-sm);
            flex-wrap: wrap;
        }}

        .diff-badge {{
            font-size: 12px;
            padding: 4px 10px;
            border-radius: var(--radius-full);
            font-weight: 500;
        }}

        .diff-badge.modified {{
            background: rgba(245, 158, 11, 0.2);
            color: #f59e0b;
        }}

        .diff-badge.added {{
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }}

        .diff-badge.removed {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }}

        .diff-section {{
            margin-bottom: var(--space-lg);
        }}

        .section-header {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            padding: var(--space-sm) var(--space-md);
            border-radius: var(--radius-md);
            margin-bottom: var(--space-sm);
            font-weight: 600;
            font-size: 14px;
        }}

        .section-header.removed {{
            background: rgba(239, 68, 68, 0.1);
            color: #ef4444;
        }}

        .section-header.added {{
            background: rgba(34, 197, 94, 0.1);
            color: #22c55e;
        }}

        .section-header.modified {{
            background: rgba(245, 158, 11, 0.1);
            color: #f59e0b;
        }}

        .section-icon {{
            font-size: 16px;
        }}

        .diff-pokemon-card {{
            background: var(--glass-bg);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            padding: var(--space-md);
            margin-bottom: var(--space-sm);
            animation: fadeSlideIn 0.4s ease backwards;
        }}

        .diff-pokemon-card.removed {{
            border-left: 3px solid #ef4444;
        }}

        .diff-pokemon-card.added {{
            border-left: 3px solid #22c55e;
        }}

        .diff-pokemon-card.modified {{
            border-left: 3px solid #f59e0b;
        }}

        .pokemon-header {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
            margin-bottom: var(--space-sm);
        }}

        .pokemon-sprite {{
            width: 48px;
            height: 48px;
            image-rendering: pixelated;
        }}

        .pokemon-info {{
            display: flex;
            flex-direction: column;
            gap: 2px;
        }}

        .pokemon-name {{
            font-weight: 600;
            color: var(--text-primary);
            font-size: 16px;
        }}

        .change-type-badge {{
            font-size: 11px;
            padding: 2px 6px;
            border-radius: var(--radius-sm);
            font-weight: 500;
        }}

        .change-type-badge.removed {{
            background: rgba(239, 68, 68, 0.2);
            color: #ef4444;
        }}

        .change-type-badge.added {{
            background: rgba(34, 197, 94, 0.2);
            color: #22c55e;
        }}

        .changes-count {{
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .removed-note, .added-details {{
            font-size: 13px;
            color: var(--text-secondary);
            padding-left: 60px;
        }}

        .changes-list {{
            padding-left: 60px;
        }}

        .change-row {{
            padding: var(--space-sm) 0;
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .change-row:last-child {{
            border-bottom: none;
        }}

        .change-field {{
            font-size: 12px;
            font-weight: 600;
            color: var(--text-secondary);
            text-transform: uppercase;
            margin-bottom: 4px;
        }}

        .change-diff {{
            font-size: 14px;
            margin-bottom: 4px;
        }}

        .diff-before {{
            color: #f87171;
            text-decoration: line-through;
            opacity: 0.8;
        }}

        .diff-arrow {{
            color: var(--text-muted);
            margin: 0 8px;
        }}

        .diff-after {{
            color: #4ade80;
            font-weight: 600;
        }}

        .change-reason {{
            font-size: 12px;
            color: var(--text-secondary);
            font-style: italic;
            padding-left: 12px;
            border-left: 2px solid rgba(255, 255, 255, 0.1);
        }}

        .unchanged-section {{
            padding: var(--space-md);
            background: var(--glass-bg);
            border-radius: var(--radius-md);
            font-size: 13px;
            color: var(--text-secondary);
        }}

        .unchanged-label {{
            font-weight: 500;
            margin-right: var(--space-xs);
        }}

        .unchanged-list {{
            color: var(--text-muted);
        }}

        @keyframes fadeSlideIn {{
            from {{
                opacity: 0;
                transform: translateY(10px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
    </style>
</head>
<body>
    <div class="diff-container">
        <div class="diff-header">
            <div class="diff-title">Team Version Diff</div>
            <div class="diff-versions">{diff.version1_name} &#8594; {diff.version2_name}</div>
            <div class="diff-badges">{badges_html}</div>
        </div>

        {sections_html}

        {unchanged_html}
    </div>
</body>
</html>'''


def create_defensive_benchmark_ui(
    pokemon: dict,
    defensive_benchmarks: list[dict],
    offensive_benchmarks: list[dict] | None = None,
    interactive: bool = True,
) -> str:
    """Create a defensive benchmark visualization showing damage taken and dealt.

    Args:
        pokemon: Your Pokemon data with keys:
            - name: str
            - nature: str
            - evs: dict or str (e.g., {"hp": 4, "defense": 0, ...} or "4 HP / 0 Def / 252 SpA / 252 Spe")
            - item: str (optional)
            - stats: dict with hp, def, spd, spe, etc. (calculated stats)
            - base_stats: dict with base stats (for recalculation)
            - types: list[str] (optional)
        defensive_benchmarks: List of threats with damage calculations:
            - threat: str (Pokemon name)
            - spread: str (e.g., "Adamant 252 Atk")
            - item: str
            - calcs: list of {move, damage, result, move_type, move_power, move_category (optional)}
            - base_stats: dict (for recalculation)
            - types: list[str]
        offensive_benchmarks: List of targets with your damage output (optional):
            - target: str (Pokemon name)
            - spread: str
            - item: str
            - calcs: list of {move, damage, result, move_type, move_power, move_category (optional)}
            - base_stats: dict (for recalculation)
            - types: list[str]
        interactive: bool - if True, allows changing EVs/items/moves dynamically

    Returns:
        HTML string for the defensive benchmark UI
    """
    shared_styles = get_shared_styles()

    # Build your Pokemon card
    poke_name = pokemon.get("name", "Pokemon")
    poke_nature = pokemon.get("nature", "Serious")
    poke_evs = pokemon.get("evs", {})
    poke_item = pokemon.get("item", "")
    poke_stats = pokemon.get("stats", {})
    poke_base_stats = pokemon.get("base_stats", {})
    poke_types = pokemon.get("types", [])

    # Convert evs string to dict if needed
    if isinstance(poke_evs, str):
        ev_dict = {"hp": 0, "attack": 0, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 0}
        # Parse "4 HP / 252 SpA / 252 Spe" format
        for part in poke_evs.split("/"):
            part = part.strip()
            if "HP" in part:
                ev_dict["hp"] = int(part.replace("HP", "").strip())
            elif "Atk" in part and "SpA" not in part:
                ev_dict["attack"] = int(part.replace("Atk", "").strip())
            elif "Def" in part and "SpD" not in part:
                ev_dict["defense"] = int(part.replace("Def", "").strip())
            elif "SpA" in part:
                ev_dict["special_attack"] = int(part.replace("SpA", "").strip())
            elif "SpD" in part:
                ev_dict["special_defense"] = int(part.replace("SpD", "").strip())
            elif "Spe" in part:
                ev_dict["speed"] = int(part.replace("Spe", "").strip())
        poke_evs = ev_dict
    elif not isinstance(poke_evs, dict):
        poke_evs = {"hp": 0, "attack": 0, "defense": 0, "special_attack": 0, "special_defense": 0, "speed": 0}

    sprite_html = get_sprite_html(poke_name, size=96, css_class="pokemon-sprite")

    # Type badges
    type_badges_html = ""
    for t in poke_types:
        type_badges_html += f'<span class="type-badge type-{t.lower()}">{t}</span>'

    # Nature options
    natures = ["Adamant", "Bold", "Brave", "Calm", "Careful", "Gentle", "Hasty",
               "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive",
               "Naughty", "Quiet", "Rash", "Relaxed", "Sassy", "Serious", "Timid"]

    nature_options = "".join(
        f'<option value="{n}" {"selected" if n.lower() == poke_nature.lower() else ""}>{n}</option>'
        for n in natures
    )

    # Common items
    items = [
        "(none)", "Focus Sash", "Choice Specs", "Choice Band", "Choice Scarf", "Life Orb",
        "Assault Vest", "Leftovers", "Sitrus Berry", "Lum Berry",
        "Booster Energy", "Clear Amulet", "Covert Cloak", "Safety Goggles",
        "Rocky Helmet", "Eviolite", "Expert Belt"
    ]
    item_options = "".join(
        f'<option value="{i}" {"selected" if i == poke_item or (i == "(none)" and not poke_item) else ""}>{i}</option>'
        for i in items
    )

    # Build defensive benchmark rows
    def_rows_html = ""
    for i, benchmark in enumerate(defensive_benchmarks):
        threat_name = benchmark.get("threat", "Unknown")
        threat_spread = benchmark.get("spread", "")
        threat_item = benchmark.get("item", "")
        calcs = benchmark.get("calcs", [])
        common_spreads = benchmark.get("common_spreads", [])
        available_moves = benchmark.get("available_moves", [])

        threat_sprite = get_sprite_html(threat_name, size=48, css_class="threat-sprite")

        # Build spread dropdown if common spreads provided
        spread_dropdown_html = ""
        if common_spreads and interactive:
            spread_options = "".join(
                f'<option value="{idx}" {"selected" if s.get("spread") == threat_spread and s.get("item") == threat_item else ""}>'
                f'{s.get("spread")} | {s.get("item")} ({s.get("usage", 0):.1f}%)</option>'
                for idx, s in enumerate(common_spreads)
            )
            spread_dropdown_html = f'''
                <select class="spread-select" id="threat-spread-{i}" onchange="updateThreatCalc({i})">
                    {spread_options}
                </select>'''

        # Build move dropdown from available_moves or calcs
        move_dropdown_html = ""
        if interactive:
            # Use available_moves if provided, otherwise use calcs
            move_options_list = available_moves if available_moves else [
                {"name": c.get("move"), "type": c.get("move_type", "")} for c in calcs
            ]
            if len(move_options_list) > 1:
                move_options = "".join(
                    f'<option value="{idx}" data-type="{m.get("type", "")}">{m.get("name")}</option>'
                    for idx, m in enumerate(move_options_list)
                )
                move_dropdown_html = f'''
                    <select class="move-select" id="threat-move-{i}" onchange="updateThreatCalc({i})">
                        {move_options}
                    </select>'''

        # Get first calc for initial display
        first_calc = calcs[0] if calcs else {}
        move_name = first_calc.get("move", "")
        damage = first_calc.get("damage", "")
        result = first_calc.get("result", "")
        move_type = first_calc.get("move_type", "")

        # Determine badge class
        badge_class = "survive"
        if "OHKO" in result.upper():
            badge_class = "ohko"
        elif "2HKO" in result.upper():
            badge_class = "twohko"
        elif "3HKO" in result.upper():
            badge_class = "threehko"
        elif "4HKO" in result.upper():
            badge_class = "fourhko"

        # Move display - either dropdown or static
        if move_dropdown_html:
            move_display = move_dropdown_html
        else:
            move_type_html = ""
            if move_type:
                move_type_html = f'<span class="type-badge type-{move_type.lower()}" style="font-size:10px;padding:2px 6px;">{move_type}</span>'
            move_display = f'{move_type_html} {move_name}'

        # Spread display
        spread_display = spread_dropdown_html if spread_dropdown_html else f'''
                        <div class="threat-spread">{threat_spread}</div>
                        <div class="threat-item">{threat_item}</div>'''

        def_rows_html += f'''
        <tr class="threat-row" data-threat-idx="{i}" style="animation-delay: {i * 0.05}s;">
            <td class="threat-cell">
                <div class="threat-info">
                    {threat_sprite}
                    <div class="threat-details">
                        <div class="threat-name">{threat_name}</div>
                        {spread_display}
                    </div>
                </div>
            </td>
            <td class="move-cell" id="threat-move-cell-{i}">{move_display}</td>
            <td class="damage-cell" id="def-damage-{i}">{damage}</td>
            <td class="result-cell"><span class="ko-badge {badge_class}" id="def-result-{i}">{result}</span></td>
        </tr>'''

    # Build offensive benchmark rows (if provided)
    off_rows_html = ""
    if offensive_benchmarks:
        for i, benchmark in enumerate(offensive_benchmarks):
            target_name = benchmark.get("target", "Unknown")
            target_spread = benchmark.get("spread", "")
            target_item = benchmark.get("item", "")
            calcs = benchmark.get("calcs", [])
            common_spreads = benchmark.get("common_spreads", [])

            target_sprite = get_sprite_html(target_name, size=48, css_class="threat-sprite")

            # Build spread dropdown if common spreads provided
            spread_dropdown_html = ""
            if common_spreads and interactive:
                spread_options = "".join(
                    f'<option value="{idx}" {"selected" if s.get("spread") == target_spread and s.get("item") == target_item else ""}>'
                    f'{s.get("spread")} | {s.get("item")} ({s.get("usage", 0):.1f}%)</option>'
                    for idx, s in enumerate(common_spreads)
                )
                spread_dropdown_html = f'''
                    <select class="spread-select" id="target-spread-{i}" onchange="updateTargetSpread({i}, this.value)">
                        {spread_options}
                    </select>'''

            for j, calc in enumerate(calcs):
                move_name = calc.get("move", "")
                damage = calc.get("damage", "")
                result = calc.get("result", "")
                move_type = calc.get("move_type", "")

                badge_class = "survive"
                if "OHKO" in result.upper():
                    badge_class = "ohko"
                elif "2HKO" in result.upper():
                    badge_class = "twohko"
                elif "3HKO" in result.upper():
                    badge_class = "threehko"
                elif "4HKO" in result.upper():
                    badge_class = "fourhko"

                move_type_html = ""
                if move_type:
                    move_type_html = f'<span class="type-badge type-{move_type.lower()}" style="font-size:10px;padding:2px 6px;">{move_type}</span>'

                if j == 0:
                    spread_display = spread_dropdown_html if spread_dropdown_html else f'''
                                    <div class="threat-spread">{target_spread}</div>
                                    <div class="threat-item">{target_item}</div>'''
                    off_rows_html += f'''
                    <tr class="threat-row" data-target-idx="{i}" style="animation-delay: {i * 0.05}s;">
                        <td class="threat-cell" rowspan="{len(calcs)}">
                            <div class="threat-info">
                                {target_sprite}
                                <div class="threat-details">
                                    <div class="threat-name">{target_name}</div>
                                    {spread_display}
                                </div>
                            </div>
                        </td>
                        <td class="move-cell">{move_type_html} {move_name}</td>
                        <td class="damage-cell" id="off-damage-{i}-{j}">{damage}</td>
                        <td class="result-cell"><span class="ko-badge {badge_class}" id="off-result-{i}-{j}">{result}</span></td>
                    </tr>'''
                else:
                    off_rows_html += f'''
                    <tr class="threat-row-continued" data-target-idx="{i}">
                        <td class="move-cell">{move_type_html} {move_name}</td>
                        <td class="damage-cell" id="off-damage-{i}-{j}">{damage}</td>
                        <td class="result-cell"><span class="ko-badge {badge_class}" id="off-result-{i}-{j}">{result}</span></td>
                    </tr>'''

    # Serialize benchmark data for JavaScript
    import json
    defensive_benchmarks_json = json.dumps(defensive_benchmarks)
    offensive_benchmarks_json = json.dumps(offensive_benchmarks if offensive_benchmarks else [])

    # Offensive section HTML
    offensive_section = ""
    if offensive_benchmarks:
        offensive_section = f'''
        <div class="benchmark-section">
            <div class="section-header">
                <span class="section-icon">&#9876;</span>
                OFFENSIVE BENCHMARKS (Damage You Deal)
            </div>
            <table class="benchmark-table">
                <thead>
                    <tr>
                        <th>Target</th>
                        <th>Your Move</th>
                        <th>Damage</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {off_rows_html}
                </tbody>
            </table>
        </div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        {shared_styles}

        .benchmark-container {{
            max-width: 800px;
            margin: 0 auto;
            padding: var(--space-md);
        }}

        .pokemon-hero {{
            background: var(--glass-shine), var(--glass-bg);
            backdrop-filter: blur(var(--glass-blur));
            border-radius: var(--radius-xl);
            border: 1px solid var(--glass-border);
            padding: var(--space-lg);
            margin-bottom: var(--space-lg);
            display: flex;
            align-items: center;
            gap: var(--space-lg);
            animation: fadeSlideIn 0.4s var(--ease-smooth);
        }}

        .pokemon-hero:hover {{
            border-color: var(--glass-border-hover);
            box-shadow: var(--shadow-xl), var(--glow-primary);
        }}

        .pokemon-sprite {{
            width: 96px;
            height: 96px;
            object-fit: contain;
            animation: spriteBounce 2s ease-in-out infinite;
        }}

        .pokemon-details {{
            flex: 1;
        }}

        .pokemon-name {{
            font-size: 24px;
            font-weight: 700;
            background: var(--gradient-primary);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: var(--space-xs);
        }}

        .pokemon-types {{
            display: flex;
            gap: var(--space-xs);
            margin-bottom: var(--space-sm);
        }}

        .pokemon-spread {{
            font-size: 14px;
            color: var(--text-secondary);
            margin-bottom: var(--space-xs);
        }}

        .pokemon-stats {{
            font-size: 13px;
            color: var(--text-muted);
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .benchmark-section {{
            background: var(--glass-bg);
            border-radius: var(--radius-lg);
            border: 1px solid var(--glass-border);
            margin-bottom: var(--space-lg);
            overflow: hidden;
            animation: fadeSlideIn 0.4s var(--ease-smooth) 0.1s backwards;
        }}

        .section-header {{
            background: rgba(99, 102, 241, 0.15);
            padding: var(--space-md);
            font-weight: 600;
            font-size: 14px;
            color: var(--text-primary);
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            border-bottom: 1px solid var(--glass-border);
        }}

        .section-icon {{
            font-size: 18px;
        }}

        .benchmark-table {{
            width: 100%;
            border-collapse: collapse;
        }}

        .benchmark-table th {{
            background: rgba(255, 255, 255, 0.03);
            padding: var(--space-sm) var(--space-md);
            text-align: left;
            font-weight: 600;
            font-size: 12px;
            color: var(--text-secondary);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            border-bottom: 1px solid var(--glass-border);
        }}

        .benchmark-table td {{
            padding: var(--space-sm) var(--space-md);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            vertical-align: middle;
        }}

        .threat-row {{
            animation: fadeSlideIn 0.3s var(--ease-smooth) backwards;
        }}

        .threat-row:hover td,
        .threat-row-continued:hover td {{
            background: var(--glass-bg-hover);
        }}

        .threat-cell {{
            background: rgba(255, 255, 255, 0.02);
            border-right: 1px solid rgba(255, 255, 255, 0.05);
        }}

        .threat-info {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}

        .threat-sprite {{
            width: 48px;
            height: 48px;
            object-fit: contain;
        }}

        .threat-details {{
            flex: 1;
        }}

        .threat-name {{
            font-weight: 600;
            font-size: 14px;
            color: var(--text-primary);
        }}

        .threat-spread {{
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .threat-item {{
            font-size: 11px;
            color: var(--text-muted);
            font-style: italic;
        }}

        .move-cell {{
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: var(--space-xs);
        }}

        .damage-cell {{
            font-family: 'SF Mono', 'Fira Code', monospace;
            font-size: 13px;
            font-weight: 600;
            color: var(--text-primary);
        }}

        .result-cell {{
            text-align: center;
        }}

        .ko-badge {{
            display: inline-flex;
            align-items: center;
            padding: 4px 12px;
            border-radius: var(--radius-full);
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
        }}

        .ko-badge.ohko {{
            background: var(--gradient-danger);
            box-shadow: var(--glow-danger);
            animation: pulseGlowDanger 2s infinite;
        }}

        .ko-badge.twohko {{
            background: var(--gradient-warning);
            box-shadow: var(--glow-warning);
        }}

        .ko-badge.threehko {{
            background: linear-gradient(135deg, #eab308, #facc15);
            color: #000;
        }}

        .ko-badge.fourhko {{
            background: linear-gradient(135deg, #84cc16, #a3e635);
            color: #000;
        }}

        .ko-badge.survive {{
            background: var(--gradient-success);
            box-shadow: var(--glow-success);
        }}

        /* Interactive controls */
        .pokemon-controls {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: var(--space-md);
            margin-top: var(--space-md);
            padding-top: var(--space-md);
            border-top: 1px solid var(--glass-border);
        }}

        .control-group {{
            display: flex;
            flex-direction: column;
            gap: var(--space-xs);
        }}

        .control-label {{
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }}

        .control-select {{
            padding: 8px 12px;
            border-radius: var(--radius-md);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.8);
            color: var(--text-primary);
            font-size: 13px;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .control-select:hover {{
            border-color: var(--accent-primary);
        }}

        .control-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 3px rgba(99, 102, 241, 0.2);
        }}

        .control-select option {{
            background: #1a1a2e;
            color: #fff;
        }}

        .ev-grid {{
            display: grid;
            grid-template-columns: repeat(6, 1fr);
            gap: var(--space-sm);
            margin-top: var(--space-sm);
        }}

        .ev-item {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }}

        .ev-label {{
            font-size: 10px;
            font-weight: 600;
            color: var(--text-muted);
            text-transform: uppercase;
        }}

        .ev-input {{
            width: 100%;
            padding: 6px 4px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.8);
            color: var(--text-primary);
            font-size: 13px;
            font-weight: 600;
            text-align: center;
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .ev-input:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }}

        .ev-total {{
            text-align: center;
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: var(--space-sm);
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.03);
            border-radius: var(--radius-sm);
        }}

        .ev-total.over-limit {{
            color: var(--accent-danger);
            background: rgba(239, 68, 68, 0.1);
        }}

        .spread-select {{
            width: 100%;
            padding: 6px 10px;
            border-radius: var(--radius-md);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.9);
            color: var(--text-primary);
            font-size: 11px;
            cursor: pointer;
            margin-top: 4px;
            transition: all 0.2s ease;
        }}

        .spread-select:hover {{
            border-color: var(--accent-primary);
        }}

        .spread-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }}

        .spread-select option {{
            background: #1a1a2e;
            color: #fff;
            padding: 4px;
        }}

        .move-select {{
            padding: 6px 10px;
            border-radius: var(--radius-md);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.9);
            color: var(--text-primary);
            font-size: 12px;
            cursor: pointer;
            transition: all 0.2s ease;
            min-width: 120px;
        }}

        .move-select:hover {{
            border-color: var(--accent-primary);
        }}

        .move-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }}

        .move-select option {{
            background: #1a1a2e;
            color: #fff;
            padding: 4px;
        }}

        .calculated-stats {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
            margin-top: var(--space-sm);
            padding: var(--space-sm);
            background: rgba(255, 255, 255, 0.02);
            border-radius: var(--radius-md);
        }}

        .stat-chip {{
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: var(--radius-full);
            font-size: 12px;
        }}

        .stat-chip-label {{
            color: var(--text-muted);
            font-weight: 500;
        }}

        .stat-chip-value {{
            color: var(--text-primary);
            font-weight: 700;
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        @media (max-width: 600px) {{
            .pokemon-controls {{
                grid-template-columns: 1fr;
            }}
            .ev-grid {{
                grid-template-columns: repeat(3, 1fr);
            }}
        }}

        /* Battle Modifiers Section */
        .modifiers-section {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg);
            padding: 16px;
            margin-bottom: var(--space-lg);
        }}

        .modifiers-title {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }}

        .modifiers-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }}

        .modifier-group {{
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .modifier-toggle {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .modifier-toggle:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: var(--accent-primary);
        }}

        .modifier-toggle input[type="checkbox"] {{
            width: 14px;
            height: 14px;
            accent-color: var(--accent-primary);
            cursor: pointer;
        }}

        .modifier-toggle input[type="checkbox"]:checked + .toggle-label {{
            color: var(--accent-primary);
            font-weight: 600;
        }}

        .toggle-label {{
            font-size: 12px;
            color: var(--text-secondary);
            user-select: none;
        }}

        .modifier-select {{
            padding: 6px 10px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.8);
            color: var(--text-primary);
            font-size: 11px;
            cursor: pointer;
            min-width: 90px;
        }}

        .modifier-select:hover {{
            border-color: var(--accent-primary);
        }}

        .modifiers-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 16px;
            margin-top: 12px;
            padding-top: 12px;
            border-top: 1px solid rgba(255, 255, 255, 0.05);
        }}

        /* Stat Stages Section */
        .stat-stages-section {{
            background: rgba(255, 255, 255, 0.02);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-lg);
            padding: 16px;
            margin-bottom: var(--space-lg);
        }}

        .stages-title {{
            font-size: 11px;
            font-weight: 700;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: 12px;
        }}

        .stat-stages-grid {{
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }}

        .stage-group {{
            background: rgba(255, 255, 255, 0.02);
            border-radius: var(--radius-md);
            padding: 12px;
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

        .stage-row {{
            display: flex;
            align-items: center;
            gap: 10px;
            margin-bottom: 8px;
        }}

        .stage-row:last-child {{
            margin-bottom: 0;
        }}

        .stage-stat {{
            font-size: 11px;
            font-weight: 600;
            color: var(--text-secondary);
            min-width: 30px;
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
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            cursor: pointer;
            box-shadow: 0 2px 6px rgba(99, 102, 241, 0.4);
            transition: transform 0.15s ease;
        }}

        .stage-slider::-webkit-slider-thumb:hover {{
            transform: scale(1.15);
        }}

        .stage-slider::-moz-range-thumb {{
            width: 16px;
            height: 16px;
            border-radius: 50%;
            background: linear-gradient(135deg, #6366f1, #8b5cf6);
            cursor: pointer;
            border: none;
            box-shadow: 0 2px 6px rgba(99, 102, 241, 0.4);
        }}

        .stage-value {{
            font-size: 13px;
            font-weight: 700;
            font-family: 'SF Mono', 'Monaco', 'Fira Code', monospace;
            min-width: 28px;
            text-align: right;
        }}

        .stage-value.negative {{
            color: #ef4444;
        }}

        .stage-value.positive {{
            color: #22c55e;
        }}

        .stage-value.neutral {{
            color: #71717a;
        }}

        @media (max-width: 600px) {{
            .stat-stages-grid {{
                grid-template-columns: 1fr;
            }}
            .modifiers-grid {{
                flex-direction: column;
                align-items: stretch;
            }}
        }}
    </style>
</head>
<body>
    <div class="benchmark-container">
        <div class="pokemon-hero">
            {sprite_html}
            <div class="pokemon-details">
                <div class="pokemon-name">{poke_name}</div>
                <div class="pokemon-types">{type_badges_html}</div>

                <div class="pokemon-controls">
                    <div class="control-group">
                        <label class="control-label">Nature</label>
                        <select class="control-select" id="pokemon-nature" onchange="recalculateAll()">
                            {nature_options}
                        </select>
                    </div>
                    <div class="control-group">
                        <label class="control-label">Item</label>
                        <select class="control-select" id="pokemon-item" onchange="recalculateAll()">
                            {item_options}
                        </select>
                    </div>
                </div>

                <div class="ev-grid">
                    <div class="ev-item">
                        <span class="ev-label">HP</span>
                        <input type="number" class="ev-input" id="ev-hp" value="{poke_evs.get('hp', 0)}" min="0" max="252" step="4" oninput="updateEVTotal(); recalculateAll()">
                    </div>
                    <div class="ev-item">
                        <span class="ev-label">Atk</span>
                        <input type="number" class="ev-input" id="ev-atk" value="{poke_evs.get('attack', 0)}" min="0" max="252" step="4" oninput="updateEVTotal(); recalculateAll()">
                    </div>
                    <div class="ev-item">
                        <span class="ev-label">Def</span>
                        <input type="number" class="ev-input" id="ev-def" value="{poke_evs.get('defense', 0)}" min="0" max="252" step="4" oninput="updateEVTotal(); recalculateAll()">
                    </div>
                    <div class="ev-item">
                        <span class="ev-label">SpA</span>
                        <input type="number" class="ev-input" id="ev-spa" value="{poke_evs.get('special_attack', 0)}" min="0" max="252" step="4" oninput="updateEVTotal(); recalculateAll()">
                    </div>
                    <div class="ev-item">
                        <span class="ev-label">SpD</span>
                        <input type="number" class="ev-input" id="ev-spd" value="{poke_evs.get('special_defense', 0)}" min="0" max="252" step="4" oninput="updateEVTotal(); recalculateAll()">
                    </div>
                    <div class="ev-item">
                        <span class="ev-label">Spe</span>
                        <input type="number" class="ev-input" id="ev-spe" value="{poke_evs.get('speed', 0)}" min="0" max="252" step="4" oninput="updateEVTotal(); recalculateAll()">
                    </div>
                </div>
                <div class="ev-total" id="ev-total">Total: 0 / 508</div>

                <div class="calculated-stats" id="calculated-stats">
                    <div class="stat-chip"><span class="stat-chip-label">HP:</span><span class="stat-chip-value" id="stat-hp">-</span></div>
                    <div class="stat-chip"><span class="stat-chip-label">Def:</span><span class="stat-chip-value" id="stat-def">-</span></div>
                    <div class="stat-chip"><span class="stat-chip-label">SpD:</span><span class="stat-chip-value" id="stat-spd">-</span></div>
                    <div class="stat-chip"><span class="stat-chip-label">Spe:</span><span class="stat-chip-value" id="stat-spe">-</span></div>
                </div>
            </div>
        </div>

        <!-- Battle Modifiers Section -->
        <div class="modifiers-section">
            <div class="modifiers-title">Battle Modifiers</div>
            <div class="modifiers-grid">
                <!-- Tera Toggle -->
                <div class="modifier-group">
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-tera" onchange="recalculateDamage()">
                        <span class="toggle-label">Tera</span>
                    </label>
                    <select class="modifier-select" id="tera-type" onchange="recalculateDamage()">
                        <option value="">Select Type</option>
                        <option value="normal">Normal</option>
                        <option value="fire">Fire</option>
                        <option value="water">Water</option>
                        <option value="electric">Electric</option>
                        <option value="grass">Grass</option>
                        <option value="ice">Ice</option>
                        <option value="fighting">Fighting</option>
                        <option value="poison">Poison</option>
                        <option value="ground">Ground</option>
                        <option value="flying">Flying</option>
                        <option value="psychic">Psychic</option>
                        <option value="bug">Bug</option>
                        <option value="rock">Rock</option>
                        <option value="ghost">Ghost</option>
                        <option value="dragon">Dragon</option>
                        <option value="dark">Dark</option>
                        <option value="steel">Steel</option>
                        <option value="fairy">Fairy</option>
                        <option value="stellar">Stellar</option>
                    </select>
                </div>

                <!-- Screens -->
                <label class="modifier-toggle">
                    <input type="checkbox" id="mod-reflect" onchange="recalculateDamage()">
                    <span class="toggle-label">Reflect</span>
                </label>
                <label class="modifier-toggle">
                    <input type="checkbox" id="mod-lightscreen" onchange="recalculateDamage()">
                    <span class="toggle-label">Light Screen</span>
                </label>

                <!-- Ability Effects -->
                <label class="modifier-toggle">
                    <input type="checkbox" id="mod-intimidate" onchange="recalculateDamage()">
                    <span class="toggle-label">Intimidate (-1)</span>
                </label>
                <label class="modifier-toggle">
                    <input type="checkbox" id="mod-friendguard" onchange="recalculateDamage()">
                    <span class="toggle-label">Friend Guard</span>
                </label>
            </div>

            <div class="modifiers-row">
                <div class="control-group">
                    <label class="control-label">Weather</label>
                    <select class="modifier-select" id="mod-weather" onchange="recalculateDamage()">
                        <option value="none">None</option>
                        <option value="sun">Sun</option>
                        <option value="rain">Rain</option>
                        <option value="sand">Sand</option>
                        <option value="snow">Snow</option>
                    </select>
                </div>
                <div class="control-group">
                    <label class="control-label">Terrain</label>
                    <select class="modifier-select" id="mod-terrain" onchange="recalculateDamage()">
                        <option value="none">None</option>
                        <option value="grassy">Grassy</option>
                        <option value="electric">Electric</option>
                        <option value="psychic">Psychic</option>
                        <option value="misty">Misty</option>
                    </select>
                </div>
            </div>
        </div>

        <!-- Stat Stages Section -->
        <div class="stat-stages-section">
            <div class="stages-title">Stat Stages</div>
            <div class="stat-stages-grid">
                <!-- Attacker Stages (for threats) -->
                <div class="stage-group">
                    <span class="stage-label">Attacker (Threats)</span>
                    <div class="stage-row">
                        <span class="stage-stat">Atk</span>
                        <input type="range" class="stage-slider" id="atk-stage" min="-6" max="6" value="0" oninput="updateStageDisplay(this); recalculateDamage()">
                        <span class="stage-value neutral" id="atk-stage-display">+0</span>
                    </div>
                    <div class="stage-row">
                        <span class="stage-stat">SpA</span>
                        <input type="range" class="stage-slider" id="spa-stage" min="-6" max="6" value="0" oninput="updateStageDisplay(this); recalculateDamage()">
                        <span class="stage-value neutral" id="spa-stage-display">+0</span>
                    </div>
                </div>

                <!-- Defender Stages (your Pokemon) -->
                <div class="stage-group">
                    <span class="stage-label">Defender (You)</span>
                    <div class="stage-row">
                        <span class="stage-stat">Def</span>
                        <input type="range" class="stage-slider" id="def-stage" min="-6" max="6" value="0" oninput="updateStageDisplay(this); recalculateDamage()">
                        <span class="stage-value neutral" id="def-stage-display">+0</span>
                    </div>
                    <div class="stage-row">
                        <span class="stage-stat">SpD</span>
                        <input type="range" class="stage-slider" id="spd-stage" min="-6" max="6" value="0" oninput="updateStageDisplay(this); recalculateDamage()">
                        <span class="stage-value neutral" id="spd-stage-display">+0</span>
                    </div>
                </div>
            </div>
        </div>

        <div class="benchmark-section">
            <div class="section-header">
                <span class="section-icon">&#128737;</span>
                DEFENSIVE BENCHMARKS (Damage You Take)
            </div>
            <table class="benchmark-table">
                <thead>
                    <tr>
                        <th>Threat</th>
                        <th>Move</th>
                        <th>Damage</th>
                        <th>Result</th>
                    </tr>
                </thead>
                <tbody>
                    {def_rows_html}
                </tbody>
            </table>
        </div>

        {offensive_section}
    </div>

    <script>
        // Pokemon base stats for recalculation
        const baseStats = {{
            hp: {poke_base_stats.get('hp', 55)},
            attack: {poke_base_stats.get('attack', 55)},
            defense: {poke_base_stats.get('defense', 55)},
            special_attack: {poke_base_stats.get('special_attack', 55)},
            special_defense: {poke_base_stats.get('special_defense', 55)},
            speed: {poke_base_stats.get('speed', 55)}
        }};

        // Your Pokemon's types for tera calculations
        const pokemonTypes = {json.dumps(poke_types)};

        // Nature modifiers
        const natureModifiers = {{
            adamant: {{ attack: 1.1, special_attack: 0.9 }},
            bold: {{ defense: 1.1, attack: 0.9 }},
            brave: {{ attack: 1.1, speed: 0.9 }},
            calm: {{ special_defense: 1.1, attack: 0.9 }},
            careful: {{ special_defense: 1.1, special_attack: 0.9 }},
            gentle: {{ special_defense: 1.1, defense: 0.9 }},
            hasty: {{ speed: 1.1, defense: 0.9 }},
            impish: {{ defense: 1.1, special_attack: 0.9 }},
            jolly: {{ speed: 1.1, special_attack: 0.9 }},
            lax: {{ defense: 1.1, special_defense: 0.9 }},
            lonely: {{ attack: 1.1, defense: 0.9 }},
            mild: {{ special_attack: 1.1, defense: 0.9 }},
            modest: {{ special_attack: 1.1, attack: 0.9 }},
            naive: {{ speed: 1.1, special_defense: 0.9 }},
            naughty: {{ attack: 1.1, special_defense: 0.9 }},
            quiet: {{ special_attack: 1.1, speed: 0.9 }},
            rash: {{ special_attack: 1.1, special_defense: 0.9 }},
            relaxed: {{ defense: 1.1, speed: 0.9 }},
            sassy: {{ special_defense: 1.1, speed: 0.9 }},
            serious: {{}},
            timid: {{ speed: 1.1, attack: 0.9 }}
        }};

        // Type effectiveness chart (defender type -> attacker move type -> multiplier)
        const TYPE_CHART = {{
            normal: {{ fighting: 2, ghost: 0 }},
            fire: {{ water: 2, ground: 2, rock: 2, fire: 0.5, grass: 0.5, ice: 0.5, bug: 0.5, steel: 0.5, fairy: 0.5 }},
            water: {{ electric: 2, grass: 2, fire: 0.5, water: 0.5, ice: 0.5, steel: 0.5 }},
            electric: {{ ground: 2, electric: 0.5, flying: 0.5, steel: 0.5 }},
            grass: {{ fire: 2, ice: 2, poison: 2, flying: 2, bug: 2, water: 0.5, electric: 0.5, grass: 0.5, ground: 0.5 }},
            ice: {{ fire: 2, fighting: 2, rock: 2, steel: 2, ice: 0.5 }},
            fighting: {{ flying: 2, psychic: 2, fairy: 2, bug: 0.5, rock: 0.5, dark: 0.5 }},
            poison: {{ ground: 2, psychic: 2, fighting: 0.5, poison: 0.5, bug: 0.5, grass: 0.5, fairy: 0.5 }},
            ground: {{ water: 2, grass: 2, ice: 2, electric: 0, poison: 0.5, rock: 0.5 }},
            flying: {{ electric: 2, ice: 2, rock: 2, ground: 0, fighting: 0.5, bug: 0.5, grass: 0.5 }},
            psychic: {{ bug: 2, ghost: 2, dark: 2, fighting: 0.5, psychic: 0.5 }},
            bug: {{ fire: 2, flying: 2, rock: 2, fighting: 0.5, ground: 0.5, grass: 0.5 }},
            rock: {{ water: 2, grass: 2, fighting: 2, ground: 2, steel: 2, normal: 0.5, fire: 0.5, poison: 0.5, flying: 0.5 }},
            ghost: {{ ghost: 2, dark: 2, normal: 0, fighting: 0, poison: 0.5, bug: 0.5 }},
            dragon: {{ ice: 2, dragon: 2, fairy: 2, fire: 0.5, water: 0.5, electric: 0.5, grass: 0.5 }},
            dark: {{ fighting: 2, bug: 2, fairy: 2, psychic: 0, ghost: 0.5, dark: 0.5 }},
            steel: {{ fire: 2, fighting: 2, ground: 2, poison: 0, normal: 0.5, grass: 0.5, ice: 0.5, flying: 0.5, psychic: 0.5, bug: 0.5, rock: 0.5, dragon: 0.5, steel: 0.5, fairy: 0.5 }},
            fairy: {{ poison: 2, steel: 2, fighting: 0.5, bug: 0.5, dragon: 0, dark: 0.5 }}
        }};

        // Stage multipliers (Gen 9)
        const stageMultipliers = {{
            '-6': 2/8, '-5': 2/7, '-4': 2/6, '-3': 2/5, '-2': 2/4, '-1': 2/3,
            '0': 1,
            '+1': 3/2, '+2': 4/2, '+3': 5/2, '+4': 6/2, '+5': 7/2, '+6': 8/2
        }};

        // Update stage display with +/- prefix and color
        function updateStageDisplay(slider) {{
            const display = document.getElementById(slider.id + '-display');
            const value = parseInt(slider.value);
            display.textContent = value >= 0 ? `+${{value}}` : `${{value}}`;
            display.className = 'stage-value ' +
                (value < 0 ? 'negative' : value > 0 ? 'positive' : 'neutral');
        }}

        // Get all stat stages
        function getStatStages() {{
            return {{
                atk: parseInt(document.getElementById('atk-stage')?.value || 0),
                spa: parseInt(document.getElementById('spa-stage')?.value || 0),
                def: parseInt(document.getElementById('def-stage')?.value || 0),
                spd: parseInt(document.getElementById('spd-stage')?.value || 0)
            }};
        }}

        // Apply stage modifier to stat
        function applyStage(stat, stage) {{
            const key = stage >= 0 ? `+${{stage}}` : `${{stage}}`;
            const mult = stageMultipliers[key] || 1;
            return Math.floor(stat * mult);
        }}

        // Get modifiers state
        function getModifiers() {{
            return {{
                tera: document.getElementById('mod-tera')?.checked || false,
                teraType: document.getElementById('tera-type')?.value || '',
                reflect: document.getElementById('mod-reflect')?.checked || false,
                lightScreen: document.getElementById('mod-lightscreen')?.checked || false,
                intimidate: document.getElementById('mod-intimidate')?.checked || false,
                friendGuard: document.getElementById('mod-friendguard')?.checked || false,
                weather: document.getElementById('mod-weather')?.value || 'none',
                terrain: document.getElementById('mod-terrain')?.value || 'none'
            }};
        }}

        // Get type effectiveness
        function getTypeEffectiveness(moveType, defenderTypes, teraType = null) {{
            const defTypes = teraType ? [teraType] : defenderTypes;
            let mult = 1;
            for (const defType of defTypes) {{
                const chart = TYPE_CHART[defType.toLowerCase()];
                if (chart && chart[moveType.toLowerCase()] !== undefined) {{
                    mult *= chart[moveType.toLowerCase()];
                }}
            }}
            return mult;
        }}

        // Calculate damage modifier from all active modifiers
        function calcModifierMultiplier(isPhysical, moveType) {{
            const mods = getModifiers();
            let modifier = 1.0;

            // Screens (0.67x in doubles)
            if (isPhysical && mods.reflect) {{
                modifier *= 0.67;
            }}
            if (!isPhysical && mods.lightScreen) {{
                modifier *= 0.67;
            }}

            // Friend Guard (0.75x)
            if (mods.friendGuard) {{
                modifier *= 0.75;
            }}

            // Weather effects
            if (mods.weather === 'sun') {{
                if (moveType && moveType.toLowerCase() === 'fire') modifier *= 1.5;
                if (moveType && moveType.toLowerCase() === 'water') modifier *= 0.5;
            }} else if (mods.weather === 'rain') {{
                if (moveType && moveType.toLowerCase() === 'water') modifier *= 1.5;
                if (moveType && moveType.toLowerCase() === 'fire') modifier *= 0.5;
            }}

            // Terrain effects
            if (mods.terrain === 'grassy' && moveType && moveType.toLowerCase() === 'ground') {{
                modifier *= 0.5;  // Earthquake/Bulldoze halved
            }}
            if (mods.terrain === 'psychic' && !isPhysical && moveType && moveType.toLowerCase() === 'psychic') {{
                modifier *= 1.3;  // Psychic moves boosted
            }}
            if (mods.terrain === 'electric' && !isPhysical && moveType && moveType.toLowerCase() === 'electric') {{
                modifier *= 1.3;  // Electric moves boosted
            }}

            // Tera type effectiveness change
            if (mods.tera && mods.teraType && moveType) {{
                const teraEff = getTypeEffectiveness(moveType, pokemonTypes, mods.teraType);
                const normalEff = getTypeEffectiveness(moveType, pokemonTypes, null);
                if (normalEff !== 0) {{
                    modifier *= teraEff / normalEff;
                }} else if (teraEff !== 0) {{
                    // Was immune, now takes damage
                    modifier *= teraEff;
                }}
            }}

            return modifier;
        }}

        // Calculate stat from base, EV, IV, nature
        function calcStat(base, ev, iv, nature, statName, isHP) {{
            if (isHP) {{
                return Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 50 + 10;
            }}
            let stat = Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 5;
            const mod = natureModifiers[nature.toLowerCase()];
            if (mod && mod[statName]) {{
                stat = Math.floor(stat * mod[statName]);
            }}
            return stat;
        }}

        // Get current EVs from inputs
        function getEVs() {{
            return {{
                hp: parseInt(document.getElementById('ev-hp').value) || 0,
                attack: parseInt(document.getElementById('ev-atk').value) || 0,
                defense: parseInt(document.getElementById('ev-def').value) || 0,
                special_attack: parseInt(document.getElementById('ev-spa').value) || 0,
                special_defense: parseInt(document.getElementById('ev-spd').value) || 0,
                speed: parseInt(document.getElementById('ev-spe').value) || 0
            }};
        }}

        // Update EV total display
        function updateEVTotal() {{
            const evs = getEVs();
            const total = Object.values(evs).reduce((a, b) => a + b, 0);
            const display = document.getElementById('ev-total');
            display.textContent = `Total: ${{total}} / 508`;
            display.classList.toggle('over-limit', total > 508);
        }}

        // Recalculate all stats and update display
        function recalculateAll() {{
            const nature = document.getElementById('pokemon-nature').value;
            const evs = getEVs();

            // Calculate stats
            const hp = calcStat(baseStats.hp, evs.hp, 31, nature, 'hp', true);
            const def = calcStat(baseStats.defense, evs.defense, 31, nature, 'defense', false);
            const spd = calcStat(baseStats.special_defense, evs.special_defense, 31, nature, 'special_defense', false);
            const spe = calcStat(baseStats.speed, evs.speed, 31, nature, 'speed', false);

            // Update stat display
            document.getElementById('stat-hp').textContent = hp;
            document.getElementById('stat-def').textContent = def;
            document.getElementById('stat-spd').textContent = spd;
            document.getElementById('stat-spe').textContent = spe;

                // Recalculate all damage values
            recalculateDamage();
        }}

        // Threat and target benchmark data for damage recalculation
        const defensiveBenchmarks = {defensive_benchmarks_json};
        const offensiveBenchmarks = {offensive_benchmarks_json};

        // Gen 9 damage formula (simplified for client-side)
        function calcDamage(attackerLevel, attackStat, defenseStat, basePower, hp, modifiers = 1.0) {{
            // Base damage formula: ((2 * L / 5 + 2) * P * A / D) / 50 + 2
            const baseDmg = Math.floor(Math.floor(Math.floor(2 * attackerLevel / 5 + 2) * basePower * attackStat / defenseStat) / 50) + 2;
            // Apply modifiers (STAB, type effectiveness, items, etc.)
            const modified = Math.floor(baseDmg * modifiers);
            // 16 damage rolls from 0.85 to 1.0
            const minDmg = Math.floor(modified * 0.85);
            const maxDmg = modified;
            const minPct = Math.round(minDmg / hp * 1000) / 10;
            const maxPct = Math.round(maxDmg / hp * 1000) / 10;
            return {{ minDmg, maxDmg, minPct, maxPct }};
        }}

        // Get KO result string from damage percentage
        function getKOResult(minPct, maxPct) {{
            if (minPct >= 100) return 'OHKO';
            if (maxPct >= 100) {{
                // Calculate OHKO chance based on rolls
                const rolls = 16;
                let koRolls = 0;
                for (let i = 0; i < rolls; i++) {{
                    const roll = 0.85 + (i / (rolls - 1)) * 0.15;
                    if ((minPct / 0.85) * roll >= 100) koRolls++;
                }}
                const chance = Math.round(koRolls / rolls * 10000) / 100;
                return `${{chance}}% OHKO`;
            }}
            if (minPct >= 50) return '2HKO';
            if (minPct >= 33.4) return '3HKO';
            if (minPct >= 25) return '4HKO';
            return 'Survives';
        }}

        // Get badge class from result
        function getBadgeClass(result) {{
            if (result.includes('OHKO')) return 'ohko';
            if (result.includes('2HKO')) return 'twohko';
            if (result.includes('3HKO')) return 'threehko';
            if (result.includes('4HKO')) return 'fourhko';
            return 'survive';
        }}

        // Parse spread string to get attack EV
        function parseSpreadAttack(spread) {{
            const match = spread.match(/(\\d+)\\s*Atk/i);
            return match ? parseInt(match[1]) : 252;
        }}

        // Parse spread string to get defense/spd EV
        function parseSpreadDefense(spread, isSpa = false) {{
            if (isSpa) {{
                const match = spread.match(/(\\d+)\\s*SpD/i);
                return match ? parseInt(match[1]) : 0;
            }}
            const match = spread.match(/(\\d+)\\s*(?:Def|HP)/i);
            return match ? parseInt(match[1]) : 0;
        }}

        // Update threat calc when spread or move changes
        function updateThreatCalc(threatIdx) {{
            const benchmark = defensiveBenchmarks[threatIdx];
            if (!benchmark) return;

            // Get selected spread index (default to 0 if no dropdown)
            const spreadSelect = document.getElementById(`threat-spread-${{threatIdx}}`);
            const spreadIdx = spreadSelect ? parseInt(spreadSelect.value) : 0;

            // Get selected move index (default to 0 if no dropdown)
            const moveSelect = document.getElementById(`threat-move-${{threatIdx}}`);
            const moveIdx = moveSelect ? parseInt(moveSelect.value) : 0;

            // Get the calc for the selected move
            const calcs = benchmark.calcs || [];
            const calc = calcs[moveIdx];
            if (!calc) return;

            // Get damage for the selected spread
            const damagePerSpread = calc.damage_per_spread || [];
            const damageData = damagePerSpread[spreadIdx] || damagePerSpread[0];

            if (damageData) {{
                // Update damage cell
                const damageCell = document.getElementById(`def-damage-${{threatIdx}}`);
                if (damageCell) {{
                    damageCell.textContent = damageData.damage;
                }}

                // Update result badge
                const resultCell = document.getElementById(`def-result-${{threatIdx}}`);
                if (resultCell) {{
                    resultCell.textContent = damageData.result;
                    resultCell.className = 'ko-badge ' + getBadgeClass(damageData.result);
                }}
            }}
        }}

        // Legacy function name for backwards compatibility
        function updateThreatSpread(threatIdx, spreadIdx) {{
            updateThreatCalc(threatIdx);
        }}

        // Update target spread and recalculate damage
        function updateTargetSpread(targetIdx, spreadIdx) {{
            const benchmark = offensiveBenchmarks[targetIdx];
            if (!benchmark || !benchmark.common_spreads) return;

            const newSpread = benchmark.common_spreads[spreadIdx];
            if (!newSpread) return;

            // Update damage cells for this target
            benchmark.calcs.forEach((calc, calcIdx) => {{
                const damageCell = document.getElementById(`off-damage-${{targetIdx}}-${{calcIdx}}`);
                const resultCell = document.getElementById(`off-result-${{targetIdx}}-${{calcIdx}}`);

                if (damageCell && resultCell && calc.damage_per_spread) {{
                    const newDamage = calc.damage_per_spread[spreadIdx];
                    if (newDamage) {{
                        damageCell.textContent = newDamage.damage;
                        const badge = resultCell.querySelector('.ko-badge') || resultCell;
                        badge.textContent = newDamage.result;
                        badge.className = 'ko-badge ' + getBadgeClass(newDamage.result);
                    }}
                }}
            }});
        }}

        // Recalculate all damage based on current EVs and modifiers
        function recalculateDamage() {{
            const nature = document.getElementById('pokemon-nature').value;
            const evs = getEVs();
            const mods = getModifiers();
            const stages = getStatStages();

            // Calculate your defensive stats with stage modifiers
            const hp = calcStat(baseStats.hp, evs.hp, 31, nature, 'hp', true);
            let def = calcStat(baseStats.defense, evs.defense, 31, nature, 'defense', false);
            let spd = calcStat(baseStats.special_defense, evs.special_defense, 31, nature, 'special_defense', false);

            // Apply defender stage modifiers
            def = applyStage(def, stages.def);
            spd = applyStage(spd, stages.spd);

            // Update stat display
            document.getElementById('stat-hp').textContent = hp;
            document.getElementById('stat-def').textContent = def + (stages.def !== 0 ? ` (${{stages.def >= 0 ? '+' : ''}}${{stages.def}})` : '');
            document.getElementById('stat-spd').textContent = spd + (stages.spd !== 0 ? ` (${{stages.spd >= 0 ? '+' : ''}}${{stages.spd}})` : '');

            // Recalculate each defensive benchmark
            defensiveBenchmarks.forEach((benchmark, idx) => {{
                const calcs = benchmark.calcs || [];
                if (calcs.length === 0) return;

                // Get selected move index
                const moveSelect = document.getElementById(`threat-move-${{idx}}`);
                const moveIdx = moveSelect ? parseInt(moveSelect.value) : 0;
                const calc = calcs[moveIdx] || calcs[0];

                // Determine if physical or special
                const isPhysical = (calc.move_category || 'physical').toLowerCase() === 'physical';
                const moveType = calc.move_type || '';
                const basePower = calc.move_power || 80;

                // Get attacker's attack stat (simplified - use base stats or stored value)
                const threatBaseStats = benchmark.base_stats || {{}};
                let attackStat = isPhysical ?
                    (threatBaseStats.attack || 100) :
                    (threatBaseStats.special_attack || 100);

                // Apply attacker stage modifier
                let atkStage = isPhysical ? stages.atk : stages.spa;
                // Intimidate applies -1 to physical attacks
                if (mods.intimidate && isPhysical) {{
                    atkStage = Math.max(-6, atkStage - 1);
                }}
                attackStat = applyStage(attackStat, atkStage);

                // Get defender's effective defensive stat
                const defStat = isPhysical ? def : spd;

                // Calculate modifier multiplier
                const modMult = calcModifierMultiplier(isPhysical, moveType);

                // Calculate damage (simplified formula)
                const baseDmg = Math.floor(Math.floor(Math.floor(2 * 50 / 5 + 2) * basePower * attackStat / defStat) / 50) + 2;
                const minDmg = Math.floor(baseDmg * 0.85 * modMult);
                const maxDmg = Math.floor(baseDmg * modMult);
                const minPct = Math.round(minDmg / hp * 1000) / 10;
                const maxPct = Math.round(maxDmg / hp * 1000) / 10;

                // Update damage display
                const damageCell = document.getElementById(`def-damage-${{idx}}`);
                if (damageCell) {{
                    damageCell.textContent = `${{minPct.toFixed(1)}}-${{maxPct.toFixed(1)}}%`;
                }}

                // Update result badge
                const resultCell = document.getElementById(`def-result-${{idx}}`);
                if (resultCell) {{
                    const result = getKOResult(minPct, maxPct);
                    resultCell.textContent = result;
                    resultCell.className = 'ko-badge ' + getBadgeClass(result);
                }}
            }});

            // Show active modifiers summary
            const activeMods = [];
            if (mods.tera && mods.teraType) activeMods.push(`Tera ${{mods.teraType}}`);
            if (mods.reflect) activeMods.push('Reflect');
            if (mods.lightScreen) activeMods.push('L.Screen');
            if (mods.intimidate) activeMods.push('Intimidate');
            if (mods.friendGuard) activeMods.push('F.Guard');
            if (mods.weather !== 'none') activeMods.push(mods.weather.charAt(0).toUpperCase() + mods.weather.slice(1));
            if (mods.terrain !== 'none') activeMods.push(mods.terrain.charAt(0).toUpperCase() + mods.terrain.slice(1) + ' Terrain');

            // Update modifiers title to show active count
            const modTitle = document.querySelector('.modifiers-title');
            if (modTitle) {{
                modTitle.textContent = activeMods.length > 0 ?
                    `Battle Modifiers (${{activeMods.length}} active)` :
                    'Battle Modifiers';
            }}
        }}

        // Initialize on load
        document.addEventListener('DOMContentLoaded', () => {{
            updateEVTotal();
            recalculateAll();
        }});
    </script>
</body>
</html>'''


def create_dual_survival_ui(
    pokemon: dict,
    hits: list[dict],
    survival_chance: float,
    survival_rolls: str = "",
    interactive: bool = True,
) -> str:
    """Create a dual survival visualization showing sequential hits and survival.

    Args:
        pokemon: Your Pokemon data with keys:
            - name: str
            - hp: int (max HP)
            - types: list[str] (optional)
            - nature: str (optional, for interactive mode)
            - evs: dict (optional, for interactive mode)
            - base_stats: dict (optional, for interactive mode)
        hits: List of incoming attacks (can be same or different attackers):
            - attacker: str (Pokemon name)
            - move: str
            - spread: str (e.g., "Adamant 116 Atk")
            - item: str (optional)
            - damage_range: [min_dmg, max_dmg] in raw HP
            - damage_pct: str (e.g., "45-53%")
        survival_chance: Overall survival percentage (0-100)
        survival_rolls: String like "7/16" showing roll counts
        interactive: bool - if True, allows changing EVs dynamically

    Returns:
        HTML string for the dual survival UI
    """
    shared_styles = get_shared_styles()

    poke_name = pokemon.get("name", "Pokemon")
    poke_hp = pokemon.get("hp", 100)
    poke_types = pokemon.get("types", [])
    poke_nature = pokemon.get("nature", "Serious")
    poke_item = pokemon.get("item", "")
    poke_tera_type = pokemon.get("tera_type", "")
    poke_evs = pokemon.get("evs", {
        "hp": 0, "attack": 0, "defense": 0,
        "special_attack": 0, "special_defense": 0, "speed": 0
    })
    poke_base_stats = pokemon.get("base_stats", {
        "hp": 80, "attack": 80, "defense": 80,
        "special_attack": 80, "special_defense": 80, "speed": 80
    })

    # Ensure evs is a dict with all stats
    if not isinstance(poke_evs, dict):
        poke_evs = {
            "hp": 0, "attack": 0, "defense": 0,
            "special_attack": 0, "special_defense": 0, "speed": 0
        }

    # Build full EV spread summary string (show all stats)
    ev_parts = [
        f"{poke_evs.get('hp', 0)} HP",
        f"{poke_evs.get('attack', 0)} Atk",
        f"{poke_evs.get('defense', 0)} Def",
        f"{poke_evs.get('special_attack', 0)} SpA",
        f"{poke_evs.get('special_defense', 0)} SpD",
        f"{poke_evs.get('speed', 0)} Spe",
    ]
    spread_summary = f"{poke_nature} | {' / '.join(ev_parts)}"

    # Item display
    item_display = f"Item: {poke_item}" if poke_item else "No Item"

    # Nature options for interactive mode
    natures = ["Adamant", "Bold", "Brave", "Calm", "Careful", "Gentle", "Hasty",
               "Impish", "Jolly", "Lax", "Lonely", "Mild", "Modest", "Naive",
               "Naughty", "Quiet", "Rash", "Relaxed", "Sassy", "Serious", "Timid"]

    nature_options = "".join(
        f'<option value="{n}" {"selected" if n.lower() == poke_nature.lower() else ""}>{n}</option>'
        for n in natures
    )

    sprite_html = get_sprite_html(poke_name, size=64, css_class="pokemon-sprite")

    # Type badges
    type_badges_html = ""
    for t in poke_types:
        type_badges_html += f'<span class="type-badge type-{t.lower()}">{t}</span>'

    # Calculate cumulative HP through hits
    hits_html = ""
    current_hp_min = poke_hp
    current_hp_max = poke_hp

    for i, hit in enumerate(hits):
        attacker = hit.get("attacker", "Unknown")
        move = hit.get("move", "Unknown Move")
        spread = hit.get("spread", "")
        item = hit.get("item", "")
        damage_range = hit.get("damage_range", [0, 0])
        damage_pct = hit.get("damage_pct", "0%")

        min_dmg = damage_range[0] if len(damage_range) > 0 else 0
        max_dmg = damage_range[1] if len(damage_range) > 1 else min_dmg

        attacker_sprite = get_sprite_html(attacker, size=48, css_class="attacker-sprite")

        # HP after this hit
        hp_after_min = max(0, current_hp_min - max_dmg)
        hp_after_max = max(0, current_hp_max - min_dmg)

        hp_after_min_pct = round((hp_after_min / poke_hp) * 100, 1)
        hp_after_max_pct = round((hp_after_max / poke_hp) * 100, 1)

        # Damage bar width (average of min/max damage)
        avg_dmg_pct = ((min_dmg + max_dmg) / 2 / poke_hp) * 100
        bar_width = min(100, avg_dmg_pct)

        # HP bar color based on remaining HP
        avg_remaining = (hp_after_min_pct + hp_after_max_pct) / 2
        if avg_remaining > 50:
            hp_color = "var(--accent-success)"
        elif avg_remaining > 25:
            hp_color = "var(--accent-warning)"
        else:
            hp_color = "var(--accent-danger)"

        # Calculate HP bar position (cumulative damage)
        cumulative_dmg_min = poke_hp - current_hp_max
        cumulative_dmg_max = poke_hp - current_hp_min
        bar_left = (cumulative_dmg_min / poke_hp) * 100

        hits_html += f'''
        <div class="hit-card" style="animation-delay: {i * 0.15}s;">
            <div class="hit-header">
                <span class="hit-number">HIT {i + 1}</span>
                <span class="hit-label">{attacker} - {move}</span>
            </div>
            <div class="hit-content">
                <div class="attacker-info">
                    {attacker_sprite}
                    <div class="attacker-details">
                        <div class="attacker-spread">{spread}</div>
                        <div class="attacker-item">{item}</div>
                    </div>
                </div>
                <div class="damage-display">
                    <div class="hp-bar-container">
                        <div class="hp-bar-track">
                            <div class="hp-bar-remaining" style="width: {hp_after_max_pct}%; background: {hp_color};"></div>
                            <div class="hp-bar-damage" style="left: {hp_after_min_pct}%; width: {bar_width}%;"></div>
                        </div>
                        <div class="hp-bar-text">{damage_pct} ({min_dmg}-{max_dmg} dmg)</div>
                    </div>
                    <div class="hp-remaining">
                        HP Remaining: {hp_after_min}-{hp_after_max} ({hp_after_min_pct}-{hp_after_max_pct}%)
                    </div>
                </div>
            </div>
        </div>'''

        # Update current HP for next hit
        current_hp_min = hp_after_min
        current_hp_max = hp_after_max

    # Verdict section
    verdict_class = "survive"
    verdict_text = "SURVIVES"
    status_text = ""

    if survival_chance <= 0:
        verdict_class = "ko"
        verdict_text = "KNOCKED OUT"
        status_text = "Cannot survive this combination"
    elif survival_chance < 25:
        verdict_class = "danger"
        verdict_text = f"SURVIVES {survival_chance:.2f}%"
        status_text = "HIGH RISK - needs defensive investment or support"
    elif survival_chance < 50:
        verdict_class = "warning"
        verdict_text = f"SURVIVES {survival_chance:.2f}%"
        status_text = "RISKY - consider bulk investment"
    elif survival_chance < 75:
        verdict_class = "caution"
        verdict_text = f"SURVIVES {survival_chance:.2f}%"
        status_text = "MODERATE - survives most of the time"
    elif survival_chance < 100:
        verdict_class = "good"
        verdict_text = f"SURVIVES {survival_chance:.2f}%"
        status_text = "RELIABLE - survives majority of rolls"
    else:
        verdict_text = "GUARANTEED SURVIVAL"
        status_text = "Always survives this combination"

    rolls_display = f" ({survival_rolls})" if survival_rolls else ""

    return f'''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        {shared_styles}

        .survival-container {{
            max-width: 700px;
            margin: 0 auto;
            padding: var(--space-md);
        }}

        .survival-header {{
            background: var(--glass-shine), var(--glass-bg);
            backdrop-filter: blur(var(--glass-blur));
            border-radius: var(--radius-xl);
            border: 1px solid var(--glass-border);
            padding: var(--space-lg);
            margin-bottom: var(--space-lg);
            animation: fadeSlideIn 0.4s var(--ease-smooth);
        }}

        .survival-title {{
            font-size: 20px;
            font-weight: 700;
            background: var(--gradient-primary);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            margin-bottom: var(--space-md);
            display: flex;
            align-items: center;
            gap: var(--space-sm);
        }}

        .pokemon-row {{
            display: flex;
            align-items: center;
            gap: var(--space-md);
        }}

        .pokemon-sprite {{
            width: 64px;
            height: 64px;
            object-fit: contain;
        }}

        .pokemon-info {{
            flex: 1;
        }}

        .pokemon-name {{
            font-size: 18px;
            font-weight: 600;
        }}

        .pokemon-spread {{
            font-size: 12px;
            color: var(--text-secondary);
            margin-top: 2px;
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .pokemon-item {{
            font-size: 12px;
            color: var(--accent-warning);
            font-style: italic;
            margin-top: 2px;
        }}

        .pokemon-hp {{
            font-size: 14px;
            color: var(--text-secondary);
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .pokemon-types {{
            display: flex;
            gap: var(--space-xs);
            margin-top: var(--space-xs);
        }}

        .hit-card {{
            background: var(--glass-bg);
            border-radius: var(--radius-lg);
            border: 1px solid var(--glass-border);
            margin-bottom: var(--space-md);
            overflow: hidden;
            animation: fadeSlideIn 0.4s var(--ease-smooth) backwards;
        }}

        .hit-header {{
            background: rgba(255, 255, 255, 0.03);
            padding: var(--space-sm) var(--space-md);
            display: flex;
            align-items: center;
            gap: var(--space-md);
            border-bottom: 1px solid var(--glass-border);
        }}

        .hit-number {{
            background: var(--gradient-primary);
            padding: 2px 10px;
            border-radius: var(--radius-full);
            font-size: 11px;
            font-weight: 700;
        }}

        .hit-label {{
            font-weight: 600;
            font-size: 14px;
        }}

        .hit-content {{
            padding: var(--space-md);
            display: flex;
            gap: var(--space-md);
            align-items: center;
        }}

        .attacker-info {{
            display: flex;
            align-items: center;
            gap: var(--space-sm);
            min-width: 180px;
        }}

        .attacker-sprite {{
            width: 48px;
            height: 48px;
            object-fit: contain;
        }}

        .attacker-details {{
            flex: 1;
        }}

        .attacker-spread {{
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .attacker-item {{
            font-size: 11px;
            color: var(--text-muted);
            font-style: italic;
        }}

        .damage-display {{
            flex: 1;
        }}

        .hp-bar-container {{
            position: relative;
            margin-bottom: var(--space-sm);
        }}

        .hp-bar-track {{
            height: 24px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-full);
            overflow: hidden;
            position: relative;
        }}

        .hp-bar-remaining {{
            height: 100%;
            border-radius: var(--radius-full);
            transition: width 0.5s var(--ease-smooth);
            position: absolute;
            left: 0;
            top: 0;
        }}

        .hp-bar-damage {{
            height: 100%;
            background: rgba(239, 68, 68, 0.5);
            position: absolute;
            top: 0;
            border-left: 2px solid var(--accent-danger);
            border-right: 2px solid var(--accent-danger);
        }}

        .hp-bar-text {{
            position: absolute;
            top: 50%;
            left: 50%;
            transform: translate(-50%, -50%);
            font-size: 12px;
            font-weight: 700;
            text-shadow: 0 1px 3px rgba(0, 0, 0, 0.8);
        }}

        .hp-remaining {{
            font-size: 12px;
            color: var(--text-secondary);
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .verdict-card {{
            background: var(--glass-shine), var(--glass-bg);
            backdrop-filter: blur(var(--glass-blur));
            border-radius: var(--radius-xl);
            border: 1px solid var(--glass-border);
            padding: var(--space-lg);
            text-align: center;
            animation: fadeSlideIn 0.4s var(--ease-smooth) 0.3s backwards;
        }}

        .verdict-label {{
            font-size: 12px;
            color: var(--text-muted);
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: var(--space-sm);
        }}

        .verdict-result {{
            font-size: 24px;
            font-weight: 700;
            margin-bottom: var(--space-sm);
        }}

        .verdict-result.survive {{
            color: var(--accent-success);
            text-shadow: 0 0 20px rgba(34, 197, 94, 0.5);
        }}

        .verdict-result.good {{
            color: #4ade80;
            text-shadow: 0 0 20px rgba(74, 222, 128, 0.5);
        }}

        .verdict-result.caution {{
            color: #facc15;
            text-shadow: 0 0 20px rgba(250, 204, 21, 0.5);
        }}

        .verdict-result.warning {{
            color: var(--accent-warning);
            text-shadow: 0 0 20px rgba(245, 158, 11, 0.5);
        }}

        .verdict-result.danger {{
            color: #f87171;
            text-shadow: 0 0 20px rgba(248, 113, 113, 0.5);
        }}

        .verdict-result.ko {{
            color: var(--accent-danger);
            text-shadow: 0 0 20px rgba(239, 68, 68, 0.5);
            animation: pulseGlowDanger 2s infinite;
        }}

        .verdict-rolls {{
            font-size: 14px;
            color: var(--text-secondary);
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .verdict-status {{
            font-size: 13px;
            color: var(--text-muted);
            margin-top: var(--space-sm);
            padding-top: var(--space-sm);
            border-top: 1px solid var(--glass-border);
        }}

        .survival-bar {{
            height: 8px;
            background: rgba(255, 255, 255, 0.1);
            border-radius: var(--radius-full);
            overflow: hidden;
            margin: var(--space-md) 0;
        }}

        .survival-bar-fill {{
            height: 100%;
            border-radius: var(--radius-full);
            transition: width 0.8s var(--ease-smooth);
        }}

        .survival-bar-fill.survive {{ background: var(--gradient-success); }}
        .survival-bar-fill.good {{ background: linear-gradient(90deg, #22c55e, #4ade80); }}
        .survival-bar-fill.caution {{ background: linear-gradient(90deg, #eab308, #facc15); }}
        .survival-bar-fill.warning {{ background: var(--gradient-warning); }}
        .survival-bar-fill.danger {{ background: linear-gradient(90deg, #ef4444, #f87171); }}
        .survival-bar-fill.ko {{ background: var(--gradient-danger); }}

        /* Interactive controls */
        .spread-controls {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
            margin-top: var(--space-md);
            padding-top: var(--space-md);
            border-top: 1px solid var(--glass-border);
        }}

        .control-group {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}

        .control-label {{
            font-size: 10px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
        }}

        .control-select, .ev-input {{
            padding: 6px 10px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.8);
            color: var(--text-primary);
            font-size: 12px;
            font-weight: 600;
            text-align: center;
        }}

        .control-select {{
            min-width: 100px;
        }}

        .ev-input {{
            width: 50px;
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        .control-select:focus, .ev-input:focus {{
            outline: none;
            border-color: var(--accent-primary);
            box-shadow: 0 0 0 2px rgba(99, 102, 241, 0.2);
        }}

        .control-select option {{
            background: #1a1a2e;
            color: #fff;
        }}

        .stat-display {{
            display: flex;
            gap: var(--space-md);
            margin-top: var(--space-sm);
            padding: var(--space-sm);
            background: rgba(255, 255, 255, 0.02);
            border-radius: var(--radius-md);
        }}

        .stat-chip {{
            display: flex;
            align-items: center;
            gap: 4px;
            padding: 4px 10px;
            background: rgba(255, 255, 255, 0.05);
            border-radius: var(--radius-full);
            font-size: 12px;
        }}

        .stat-chip-label {{
            color: var(--text-muted);
            font-weight: 500;
        }}

        .stat-chip-value {{
            color: var(--text-primary);
            font-weight: 700;
            font-family: 'SF Mono', 'Fira Code', monospace;
        }}

        /* Modifiers section */
        .modifiers-section {{
            margin-top: var(--space-md);
            padding-top: var(--space-md);
            border-top: 1px solid var(--glass-border);
        }}

        .modifiers-title {{
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            color: var(--text-muted);
            margin-bottom: var(--space-sm);
        }}

        .modifiers-grid {{
            display: flex;
            flex-wrap: wrap;
            gap: var(--space-sm);
            margin-bottom: var(--space-sm);
        }}

        .modifiers-row {{
            display: flex;
            gap: var(--space-md);
            margin-top: var(--space-sm);
        }}

        .modifier-group {{
            display: flex;
            align-items: center;
            gap: var(--space-xs);
        }}

        .modifier-toggle {{
            display: flex;
            align-items: center;
            gap: 6px;
            padding: 6px 12px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid var(--glass-border);
            border-radius: var(--radius-md);
            cursor: pointer;
            transition: all 0.2s ease;
            font-size: 12px;
            color: var(--text-secondary);
        }}

        .modifier-toggle:hover {{
            background: rgba(255, 255, 255, 0.06);
            border-color: var(--accent-primary);
        }}

        .modifier-toggle input[type="checkbox"] {{
            width: 14px;
            height: 14px;
            accent-color: var(--accent-primary);
            cursor: pointer;
        }}

        .modifier-toggle input[type="checkbox"]:checked + .toggle-label {{
            color: var(--accent-primary);
            font-weight: 600;
        }}

        .toggle-label {{
            user-select: none;
        }}

        .modifier-select {{
            padding: 6px 10px;
            border-radius: var(--radius-sm);
            border: 1px solid var(--glass-border);
            background: rgba(24, 24, 27, 0.8);
            color: var(--text-primary);
            font-size: 11px;
            cursor: pointer;
            min-width: 90px;
        }}

        .modifier-select:focus {{
            outline: none;
            border-color: var(--accent-primary);
        }}

        .modifier-select option {{
            background: #1a1a2e;
            color: #fff;
        }}

        .active-modifiers {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
            margin-top: var(--space-sm);
            min-height: 24px;
        }}

        .modifier-badge {{
            display: inline-flex;
            align-items: center;
            gap: 4px;
            padding: 4px 8px;
            background: rgba(99, 102, 241, 0.2);
            border: 1px solid rgba(99, 102, 241, 0.4);
            border-radius: var(--radius-full);
            font-size: 10px;
            font-weight: 600;
            color: var(--accent-primary);
        }}

        .modifier-badge.negative {{
            background: rgba(239, 68, 68, 0.2);
            border-color: rgba(239, 68, 68, 0.4);
            color: var(--accent-danger);
        }}

        .modifier-badge.positive {{
            background: rgba(34, 197, 94, 0.2);
            border-color: rgba(34, 197, 94, 0.4);
            color: var(--accent-success);
        }}
    </style>
</head>
<body>
    <div class="survival-container">
        <div class="survival-header">
            <div class="survival-title">
                <span>&#128737;</span> DUAL SURVIVAL CHECK
            </div>
            <div class="pokemon-row">
                {sprite_html}
                <div class="pokemon-info">
                    <div class="pokemon-name">{poke_name}</div>
                    <div class="pokemon-spread" id="spread-display">{spread_summary}</div>
                    <div class="pokemon-item" id="item-display">{item_display}</div>
                    <div class="pokemon-hp" id="hp-display">HP: {poke_hp} (100%)</div>
                    <div class="pokemon-types">{type_badges_html}</div>
                </div>
            </div>

            <div class="spread-controls">
                <div class="control-group">
                    <label class="control-label">Nature</label>
                    <select class="control-select" id="pokemon-nature" onchange="recalculateDamage()">
                        {nature_options}
                    </select>
                </div>
                <div class="control-group">
                    <label class="control-label">HP</label>
                    <input type="number" class="ev-input" id="ev-hp" value="{poke_evs.get('hp', 0)}" min="0" max="252" step="4" oninput="recalculateDamage()">
                </div>
                <div class="control-group">
                    <label class="control-label">Def</label>
                    <input type="number" class="ev-input" id="ev-def" value="{poke_evs.get('defense', 0)}" min="0" max="252" step="4" oninput="recalculateDamage()">
                </div>
                <div class="control-group">
                    <label class="control-label">SpD</label>
                    <input type="number" class="ev-input" id="ev-spd" value="{poke_evs.get('special_defense', 0)}" min="0" max="252" step="4" oninput="recalculateDamage()">
                </div>
            </div>

            <div class="stat-display">
                <div class="stat-chip"><span class="stat-chip-label">HP:</span><span class="stat-chip-value" id="stat-hp">{poke_hp}</span></div>
                <div class="stat-chip"><span class="stat-chip-label">Def:</span><span class="stat-chip-value" id="stat-def">-</span></div>
                <div class="stat-chip"><span class="stat-chip-label">SpD:</span><span class="stat-chip-value" id="stat-spd">-</span></div>
            </div>

            <div class="modifiers-section">
                <div class="modifiers-title">Battle Modifiers</div>
                <div class="modifiers-grid">
                    <div class="modifier-group">
                        <label class="modifier-toggle">
                            <input type="checkbox" id="mod-tera" onchange="recalculateDamage()">
                            <span class="toggle-label">Tera</span>
                        </label>
                        <select class="modifier-select" id="tera-type" onchange="recalculateDamage()">
                            <option value="">Select Type</option>
                            <option value="normal">Normal</option>
                            <option value="fire">Fire</option>
                            <option value="water">Water</option>
                            <option value="electric">Electric</option>
                            <option value="grass">Grass</option>
                            <option value="ice">Ice</option>
                            <option value="fighting">Fighting</option>
                            <option value="poison">Poison</option>
                            <option value="ground">Ground</option>
                            <option value="flying">Flying</option>
                            <option value="psychic">Psychic</option>
                            <option value="bug">Bug</option>
                            <option value="rock">Rock</option>
                            <option value="ghost">Ghost</option>
                            <option value="dragon">Dragon</option>
                            <option value="dark">Dark</option>
                            <option value="steel">Steel</option>
                            <option value="fairy">Fairy</option>
                            <option value="stellar">Stellar</option>
                        </select>
                    </div>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-reflect" onchange="recalculateDamage()">
                        <span class="toggle-label">Reflect</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-lightscreen" onchange="recalculateDamage()">
                        <span class="toggle-label">Light Screen</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-intimidate" onchange="recalculateDamage()">
                        <span class="toggle-label">Intimidate (-1)</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-friendguard" onchange="recalculateDamage()">
                        <span class="toggle-label">Friend Guard</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-swordofruin" onchange="recalculateDamage()">
                        <span class="toggle-label">Sword of Ruin</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-beadsofruin" onchange="recalculateDamage()">
                        <span class="toggle-label">Beads of Ruin</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-tabletsofruin" onchange="recalculateDamage()">
                        <span class="toggle-label">Tablets of Ruin</span>
                    </label>
                    <label class="modifier-toggle">
                        <input type="checkbox" id="mod-vesselofruin" onchange="recalculateDamage()">
                        <span class="toggle-label">Vessel of Ruin</span>
                    </label>
                </div>
                <div class="modifiers-row">
                    <div class="control-group">
                        <label class="control-label">Weather</label>
                        <select class="modifier-select" id="mod-weather" onchange="recalculateDamage()">
                            <option value="none">None</option>
                            <option value="sun">Sun</option>
                            <option value="rain">Rain</option>
                            <option value="sand">Sand</option>
                            <option value="snow">Snow</option>
                        </select>
                    </div>
                    <div class="control-group">
                        <label class="control-label">Terrain</label>
                        <select class="modifier-select" id="mod-terrain" onchange="recalculateDamage()">
                            <option value="none">None</option>
                            <option value="grassy">Grassy</option>
                            <option value="electric">Electric</option>
                            <option value="psychic">Psychic</option>
                            <option value="misty">Misty</option>
                        </select>
                    </div>
                </div>
            </div>
        </div>

        {hits_html}

        <div class="verdict-card">
            <div class="verdict-label">Final Verdict</div>
            <div class="survival-bar">
                <div class="survival-bar-fill {verdict_class}" id="survival-bar-fill" style="width: {survival_chance}%;"></div>
            </div>
            <div class="verdict-result {verdict_class}" id="verdict-result">{verdict_text}{rolls_display}</div>
            <div class="verdict-status" id="verdict-status">{status_text}</div>
        </div>
    </div>

    <script>
        // Pokemon base stats for recalculation
        const baseStats = {{
            hp: {poke_base_stats.get('hp', 80)},
            defense: {poke_base_stats.get('defense', 80)},
            special_defense: {poke_base_stats.get('special_defense', 80)}
        }};

        // Original Pokemon types for Tera calculation
        const originalTypes = {poke_types};

        // Type chart for effectiveness calculation
        const typeChart = {{
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

        // Nature modifiers
        const natureModifiers = {{
            adamant: {{ attack: 1.1, special_attack: 0.9 }},
            bold: {{ defense: 1.1, attack: 0.9 }},
            brave: {{ attack: 1.1, speed: 0.9 }},
            calm: {{ special_defense: 1.1, attack: 0.9 }},
            careful: {{ special_defense: 1.1, special_attack: 0.9 }},
            gentle: {{ special_defense: 1.1, defense: 0.9 }},
            hasty: {{ speed: 1.1, defense: 0.9 }},
            impish: {{ defense: 1.1, special_attack: 0.9 }},
            jolly: {{ speed: 1.1, special_attack: 0.9 }},
            lax: {{ defense: 1.1, special_defense: 0.9 }},
            lonely: {{ attack: 1.1, defense: 0.9 }},
            mild: {{ special_attack: 1.1, defense: 0.9 }},
            modest: {{ special_attack: 1.1, attack: 0.9 }},
            naive: {{ speed: 1.1, special_defense: 0.9 }},
            naughty: {{ attack: 1.1, special_defense: 0.9 }},
            quiet: {{ special_attack: 1.1, speed: 0.9 }},
            rash: {{ special_attack: 1.1, special_defense: 0.9 }},
            relaxed: {{ defense: 1.1, speed: 0.9 }},
            sassy: {{ special_defense: 1.1, speed: 0.9 }},
            serious: {{}},
            timid: {{ speed: 1.1, attack: 0.9 }}
        }};

        // Calculate stat from base, EV, IV, nature
        function calcStat(base, ev, iv, nature, statName, isHP) {{
            if (isHP) {{
                return Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 50 + 10;
            }}
            let stat = Math.floor((2 * base + iv + Math.floor(ev / 4)) * 50 / 100) + 5;
            const mod = natureModifiers[nature.toLowerCase()];
            if (mod && mod[statName]) {{
                stat = Math.floor(stat * mod[statName]);
            }}
            return stat;
        }}

        // Get type effectiveness
        function getTypeEffectiveness(attackType, defenderTypes) {{
            let mult = 1;
            defenderTypes.forEach(defType => {{
                const chart = typeChart[attackType.toLowerCase()];
                if (chart && chart[defType.toLowerCase()] !== undefined) {{
                    mult *= chart[defType.toLowerCase()];
                }}
            }});
            return mult;
        }}

        // Get current modifiers
        function getModifiers() {{
            return {{
                tera: document.getElementById('mod-tera')?.checked || false,
                teraType: document.getElementById('tera-type')?.value || '',
                reflect: document.getElementById('mod-reflect')?.checked || false,
                lightScreen: document.getElementById('mod-lightscreen')?.checked || false,
                intimidate: document.getElementById('mod-intimidate')?.checked || false,
                friendGuard: document.getElementById('mod-friendguard')?.checked || false,
                swordOfRuin: document.getElementById('mod-swordofruin')?.checked || false,
                beadsOfRuin: document.getElementById('mod-beadsofruin')?.checked || false,
                tabletsOfRuin: document.getElementById('mod-tabletsofruin')?.checked || false,
                vesselOfRuin: document.getElementById('mod-vesselofruin')?.checked || false,
                weather: document.getElementById('mod-weather')?.value || 'none',
                terrain: document.getElementById('mod-terrain')?.value || 'none'
            }};
        }}

        // Calculate damage modifier from all active modifiers
        function calcDamageModifier(isPhysical, moveType) {{
            const mods = getModifiers();
            let modifier = 1.0;

            // Screens (0.5x in singles, 0.67x in doubles - using doubles value)
            if (isPhysical && mods.reflect) {{
                modifier *= 0.67;
            }}
            if (!isPhysical && mods.lightScreen) {{
                modifier *= 0.67;
            }}

            // Intimidate (-1 Atk stage = 2/3 modifier to attack stat)
            if (isPhysical && mods.intimidate) {{
                modifier *= (2/3);
            }}

            // Friend Guard (0.75x)
            if (mods.friendGuard) {{
                modifier *= 0.75;
            }}

            // Ruinous abilities - affect stats, not damage directly
            // Sword of Ruin: 0.75x defender's Defense (physical attacks do more damage)
            if (isPhysical && mods.swordOfRuin) {{
                modifier *= 1 / 0.75;  // ~1.33x damage
            }}
            // Beads of Ruin: 0.75x defender's Sp.Def (special attacks do more damage)
            if (!isPhysical && mods.beadsOfRuin) {{
                modifier *= 1 / 0.75;  // ~1.33x damage
            }}
            // Tablets of Ruin: 0.75x attacker's Attack (physical attacks do less damage)
            if (isPhysical && mods.tabletsOfRuin) {{
                modifier *= 0.75;
            }}
            // Vessel of Ruin: 0.75x attacker's Sp.Atk (special attacks do less damage)
            if (!isPhysical && mods.vesselOfRuin) {{
                modifier *= 0.75;
            }}

            // Weather effects
            if (mods.weather === 'sun') {{
                if (moveType?.toLowerCase() === 'fire') modifier *= 1.5;
                if (moveType?.toLowerCase() === 'water') modifier *= 0.5;
            }} else if (mods.weather === 'rain') {{
                if (moveType?.toLowerCase() === 'water') modifier *= 1.5;
                if (moveType?.toLowerCase() === 'fire') modifier *= 0.5;
            }}

            // Grassy Terrain (0.5x ground moves)
            if (mods.terrain === 'grassy' && moveType?.toLowerCase() === 'ground') {{
                modifier *= 0.5;
            }}

            return modifier;
        }}

        // Get defender types (considering Tera)
        function getDefenderTypes() {{
            const mods = getModifiers();
            if (mods.tera && mods.teraType) {{
                return [mods.teraType];
            }}
            return originalTypes.map(t => t.toLowerCase());
        }}

        // Recalculate all damage values
        function recalculateDamage() {{
            const nature = document.getElementById('pokemon-nature').value;
            const hpEV = parseInt(document.getElementById('ev-hp').value) || 0;
            const defEV = parseInt(document.getElementById('ev-def').value) || 0;
            const spdEV = parseInt(document.getElementById('ev-spd').value) || 0;

            // Calculate stats
            const hp = calcStat(baseStats.hp, hpEV, 31, nature, 'hp', true);
            const def = calcStat(baseStats.defense, defEV, 31, nature, 'defense', false);
            const spd = calcStat(baseStats.special_defense, spdEV, 31, nature, 'special_defense', false);

            // Update stat display
            document.getElementById('stat-hp').textContent = hp;
            document.getElementById('stat-def').textContent = def;
            document.getElementById('stat-spd').textContent = spd;
            document.getElementById('hp-display').textContent = `HP: ${{hp}} (100%)`;

            // Update spread display
            const spreadParts = [
                `${{hpEV}} HP`,
                `${{parseInt(document.getElementById('ev-hp').value) || 0}} Atk`,
                `${{defEV}} Def`,
                `0 SpA`,
                `${{spdEV}} SpD`,
                `0 Spe`
            ];
            document.getElementById('spread-display').textContent = `${{nature}} | ${{hpEV}} HP / 0 Atk / ${{defEV}} Def / 0 SpA / ${{spdEV}} SpD / 0 Spe`;

            // Get modifier summary
            const mods = getModifiers();
            const activeMods = [];
            if (mods.tera && mods.teraType) activeMods.push(`Tera ${{mods.teraType}}`);
            if (mods.reflect) activeMods.push('Reflect (-33%)');
            if (mods.lightScreen) activeMods.push('L.Screen (-33%)');
            if (mods.intimidate) activeMods.push('Intimidate (-33%)');
            if (mods.friendGuard) activeMods.push('F.Guard (-25%)');
            if (mods.swordOfRuin) activeMods.push('Sword of Ruin (+33% phys)');
            if (mods.beadsOfRuin) activeMods.push('Beads of Ruin (+33% spec)');
            if (mods.tabletsOfRuin) activeMods.push('Tablets of Ruin (-25% phys)');
            if (mods.vesselOfRuin) activeMods.push('Vessel of Ruin (-25% spec)');
            if (mods.weather !== 'none') activeMods.push(mods.weather.charAt(0).toUpperCase() + mods.weather.slice(1));
            if (mods.terrain !== 'none') activeMods.push(mods.terrain.charAt(0).toUpperCase() + mods.terrain.slice(1) + ' Terrain');

            // Note: Full damage recalculation would need the original attacker stats
            // This shows the modifiers that would apply
            console.log('Active modifiers:', activeMods);
            console.log('Damage modifier:', calcDamageModifier(true, null));
        }}

        // Initialize on load
        document.addEventListener('DOMContentLoaded', recalculateDamage);
    </script>
</body>
</html>'''
