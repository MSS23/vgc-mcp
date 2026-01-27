"""Ability synergy and interaction analysis for VGC."""

from dataclasses import dataclass
from typing import Optional


# ============================================================================
# INTIMIDATE INTERACTIONS
# ============================================================================

INTIMIDATE_ABILITIES: list[str] = [
    "intimidate",
]

# Abilities that block Intimidate
INTIMIDATE_BLOCKERS: list[str] = [
    "clear-body",
    "white-smoke",
    "full-metal-body",
    "inner-focus",
    "oblivious",
    "own-tempo",
    "scrappy",
    "hyper-cutter",
    "mirror-armor",  # Reflects the drop back
    "guard-dog",     # Attack raised instead, can't be forced out
]

# Abilities that punish Intimidate (gain stat boost)
INTIMIDATE_PUNISHERS: list[str] = [
    "defiant",       # +2 Attack when stat lowered
    "competitive",   # +2 Sp. Attack when stat lowered
    "rattled",       # +1 Speed when Intimidated
    "contrary",      # Stat changes reversed
]

# Common Intimidate users in VGC
INTIMIDATE_POKEMON: list[str] = [
    "incineroar", "landorus-therian", "arcanine", "hitmontop",
    "salamence", "gyarados", "krookodile", "staraptor",
    "scrafty", "mawile", "luxray", "arbok",
]

# ============================================================================
# WEATHER ABILITIES
# ============================================================================

WEATHER_SETTERS: dict[str, str] = {
    "drought": "sun",
    "drizzle": "rain",
    "sand-stream": "sand",
    "snow-warning": "snow",
    "orichalcum-pulse": "sun",  # Koraidon
    "desolate-land": "harsh-sun",  # Primal Groudon
    "primordial-sea": "heavy-rain",  # Primal Kyogre
    "delta-stream": "strong-winds",  # Mega Rayquaza
}

WEATHER_ABUSERS: dict[str, list[str]] = {
    "sun": [
        "chlorophyll",    # 2x Speed
        "solar-power",    # 1.5x Sp.Atk, HP drain
        "flower-gift",    # 1.5x Atk/Sp.Def for party
        "protosynthesis", # Highest stat boosted
        "harvest",        # 100% berry recovery
        "leaf-guard",     # Status immunity
        "dry-skin",       # Takes damage in sun (negative)
    ],
    "rain": [
        "swift-swim",     # 2x Speed
        "rain-dish",      # HP recovery
        "hydration",      # Status cured
        "dry-skin",       # HP recovery
    ],
    "sand": [
        "sand-rush",      # 2x Speed
        "sand-force",     # 1.3x Ground/Rock/Steel moves
        "sand-veil",      # Evasion boost
    ],
    "snow": [
        "slush-rush",     # 2x Speed
        "snow-cloak",     # Evasion boost
        "ice-body",       # HP recovery
    ],
}

# ============================================================================
# TERRAIN ABILITIES
# ============================================================================

TERRAIN_SETTERS: dict[str, str] = {
    "grassy-surge": "grassy",
    "electric-surge": "electric",
    "psychic-surge": "psychic",
    "misty-surge": "misty",
    "hadron-engine": "electric",  # Miraidon
}

TERRAIN_BENEFICIARIES: dict[str, list[str]] = {
    "grassy": [
        "grassy-glide",   # Priority in Grassy Terrain (move, not ability)
        "grass-pelt",     # 1.5x Defense
    ],
    "electric": [
        "surge-surfer",   # 2x Speed
        "quark-drive",    # Highest stat boosted
    ],
    "psychic": [
        # Blocks priority moves
    ],
    "misty": [
        # Halves Dragon damage, prevents status
    ],
}

# ============================================================================
# REDIRECTION ABILITIES
# ============================================================================

REDIRECT_ABILITIES: dict[str, str] = {
    "lightning-rod": "Electric",
    "storm-drain": "Water",
    "flash-fire": "Fire",
    "motor-drive": "Electric",
    "sap-sipper": "Grass",
    "dry-skin": "Water",
    "water-absorb": "Water",
    "volt-absorb": "Electric",
}

# ============================================================================
# SPEED MODIFYING ABILITIES
# ============================================================================

SPEED_ABILITIES: dict[str, dict] = {
    "swift-swim": {"condition": "rain", "multiplier": 2.0},
    "chlorophyll": {"condition": "sun", "multiplier": 2.0},
    "sand-rush": {"condition": "sand", "multiplier": 2.0},
    "slush-rush": {"condition": "snow", "multiplier": 2.0},
    "surge-surfer": {"condition": "electric-terrain", "multiplier": 2.0},
    "unburden": {"condition": "item-consumed", "multiplier": 2.0},
    "quick-feet": {"condition": "status", "multiplier": 1.5},
    "speed-boost": {"condition": "each-turn", "effect": "+1 Speed each turn"},
    "slow-start": {"condition": "first-5-turns", "multiplier": 0.5},
    "stall": {"condition": "always", "effect": "moves last in bracket"},
}

# ============================================================================
# PARTNER-AFFECTING ABILITIES
# ============================================================================

PARTNER_ABILITIES: dict[str, str] = {
    "friend-guard": "Reduces damage to allies by 25%",
    "flower-gift": "1.5x Atk/Sp.Def for party in sun",
    "power-spot": "Boosts allies' move power by 30%",
    "battery": "Boosts allies' Sp.Atk moves by 30%",
    "steely-spirit": "Boosts allies' Steel moves by 50%",
    "plus": "1.5x Sp.Atk if ally has Minus",
    "minus": "1.5x Sp.Atk if ally has Plus",
    "telepathy": "Immune to allies' moves",
}

# ============================================================================
# RUINOUS ABILITIES (Treasures of Ruin)
# ============================================================================

RUIN_ABILITIES: dict[str, str] = {
    "sword-of-ruin": "defense",      # Chien-Pao: Lowers foe Def to 0.75x
    "beads-of-ruin": "special_defense",  # Chi-Yu: Lowers foe SpD to 0.75x
    "tablets-of-ruin": "attack",     # Wo-Chien: Lowers foe Atk to 0.75x
    "vessel-of-ruin": "special_attack",  # Ting-Lu: Lowers foe SpA to 0.75x
}

RUIN_POKEMON: list[str] = [
    "chien-pao",  # Sword of Ruin
    "chi-yu",     # Beads of Ruin
    "wo-chien",   # Tablets of Ruin
    "ting-lu",    # Vessel of Ruin
]

# ============================================================================
# SUPPORT DATACLASSES
# ============================================================================


@dataclass
class AbilitySynergyResult:
    """Result of ability synergy analysis."""
    has_weather_setter: bool
    weather_type: Optional[str]
    weather_abusers: list[str]
    has_terrain_setter: bool
    terrain_type: Optional[str]
    has_intimidate: bool
    intimidate_answers: list[str]
    intimidate_punishers: list[str]
    redirect_abilities: list[str]
    partner_abilities: list[str]
    conflicts: list[str]
    recommendations: list[str]


@dataclass
class IntimidateAnalysis:
    """Analysis of Intimidate interactions."""
    has_intimidate: bool
    intimidate_users: list[str]
    blockers: list[str]
    punishers: list[str]
    vulnerable_count: int
    is_protected: bool
    recommendation: Optional[str]


@dataclass
class WeatherAnalysis:
    """Analysis of weather synergy."""
    has_setter: bool
    weather_type: Optional[str]
    setters: list[str]
    abusers: list[str]
    conflicts: list[str]
    synergy_score: float  # 0-1


def normalize_ability_name(ability: str) -> str:
    """Normalize ability name for lookup."""
    return ability.lower().replace(" ", "-").replace("'", "").strip()


def analyze_intimidate_matchup(
    team_abilities: list[str],
    team_pokemon: Optional[list[str]] = None
) -> IntimidateAnalysis:
    """
    Analyze team's Intimidate presence and protection.

    Args:
        team_abilities: List of abilities on the team
        team_pokemon: Optional list of Pokemon names

    Returns:
        IntimidateAnalysis with details
    """
    normalized = [normalize_ability_name(a) for a in team_abilities]

    # Check for Intimidate
    has_intimidate = "intimidate" in normalized
    intimidate_users = []
    if team_pokemon and has_intimidate:
        for i, ability in enumerate(normalized):
            if ability == "intimidate" and i < len(team_pokemon):
                intimidate_users.append(team_pokemon[i])

    # Check for blockers
    blockers = [a for a in team_abilities
                if normalize_ability_name(a) in INTIMIDATE_BLOCKERS]

    # Check for punishers
    punishers = [a for a in team_abilities
                 if normalize_ability_name(a) in INTIMIDATE_PUNISHERS]

    # Count vulnerable Pokemon (don't have blocker or punisher)
    protected_abilities = set(INTIMIDATE_BLOCKERS + INTIMIDATE_PUNISHERS)
    vulnerable = sum(1 for a in normalized if a not in protected_abilities)

    is_protected = len(blockers) > 0 or len(punishers) > 0

    # Generate recommendation
    recommendation = None
    if not is_protected and vulnerable >= 3:
        recommendation = (
            "Consider adding Defiant/Competitive user (e.g., Kingambit, Milotic) "
            "or Clear Body Pokemon to punish/block Intimidate"
        )

    return IntimidateAnalysis(
        has_intimidate=has_intimidate,
        intimidate_users=intimidate_users,
        blockers=blockers,
        punishers=punishers,
        vulnerable_count=vulnerable,
        is_protected=is_protected,
        recommendation=recommendation
    )


def analyze_weather_synergy(team_abilities: list[str]) -> WeatherAnalysis:
    """
    Analyze team's weather setting and abuse potential.

    Args:
        team_abilities: List of abilities on the team

    Returns:
        WeatherAnalysis with details
    """
    normalized = [normalize_ability_name(a) for a in team_abilities]

    # Find weather setters
    setters = []
    weather_types = []
    for ability in team_abilities:
        norm = normalize_ability_name(ability)
        if norm in WEATHER_SETTERS:
            setters.append(ability)
            weather_types.append(WEATHER_SETTERS[norm])

    # Check for conflicts (multiple different weathers)
    unique_weathers = list(set(weather_types))
    conflicts = []
    if len(unique_weathers) > 1:
        conflicts.append(f"Multiple weather types: {', '.join(unique_weathers)}")

    # Find weather abusers
    abusers = []
    primary_weather = unique_weathers[0] if unique_weathers else None

    if primary_weather and primary_weather in WEATHER_ABUSERS:
        for ability in team_abilities:
            norm = normalize_ability_name(ability)
            if norm in WEATHER_ABUSERS.get(primary_weather, []):
                abusers.append(ability)

    # Calculate synergy score
    if not setters:
        synergy_score = 0.0
    elif not abusers:
        synergy_score = 0.3  # Has setter but no abusers
    else:
        synergy_score = min(1.0, 0.5 + (len(abusers) * 0.2))

    return WeatherAnalysis(
        has_setter=len(setters) > 0,
        weather_type=primary_weather,
        setters=setters,
        abusers=abusers,
        conflicts=conflicts,
        synergy_score=synergy_score
    )


def analyze_terrain_synergy(team_abilities: list[str]) -> dict:
    """
    Analyze team's terrain setting potential.

    Args:
        team_abilities: List of abilities on the team

    Returns:
        Dict with terrain analysis
    """
    normalized = [normalize_ability_name(a) for a in team_abilities]

    setters = []
    terrain_types = []

    for ability in team_abilities:
        norm = normalize_ability_name(ability)
        if norm in TERRAIN_SETTERS:
            setters.append(ability)
            terrain_types.append(TERRAIN_SETTERS[norm])

    unique_terrains = list(set(terrain_types))
    conflicts = []
    if len(unique_terrains) > 1:
        conflicts.append(f"Multiple terrain types: {', '.join(unique_terrains)}")

    return {
        "has_setter": len(setters) > 0,
        "terrain_type": unique_terrains[0] if unique_terrains else None,
        "setters": setters,
        "conflicts": conflicts
    }


def find_redirect_abilities(team_abilities: list[str]) -> list[dict]:
    """Find redirection abilities on the team."""
    results = []

    for ability in team_abilities:
        norm = normalize_ability_name(ability)
        if norm in REDIRECT_ABILITIES:
            results.append({
                "ability": ability,
                "redirects_type": REDIRECT_ABILITIES[norm],
                "effect": f"Draws in {REDIRECT_ABILITIES[norm]} moves and gains benefit"
            })

    return results


def find_partner_abilities(team_abilities: list[str]) -> list[dict]:
    """Find abilities that benefit partners."""
    results = []

    for ability in team_abilities:
        norm = normalize_ability_name(ability)
        if norm in PARTNER_ABILITIES:
            results.append({
                "ability": ability,
                "effect": PARTNER_ABILITIES[norm]
            })

    return results


def find_ability_conflicts(team_abilities: list[str]) -> list[str]:
    """
    Find conflicting abilities on the team.

    Args:
        team_abilities: List of abilities on the team

    Returns:
        List of conflict descriptions
    """
    conflicts = []
    normalized = [normalize_ability_name(a) for a in team_abilities]

    # Check for weather conflicts
    weather_setters_found = []
    for ability in team_abilities:
        norm = normalize_ability_name(ability)
        if norm in WEATHER_SETTERS:
            weather_setters_found.append((ability, WEATHER_SETTERS[norm]))

    if len(weather_setters_found) > 1:
        weathers = [w[1] for w in weather_setters_found]
        if len(set(weathers)) > 1:
            conflicts.append(
                f"Weather conflict: {', '.join(f'{a} ({w})' for a, w in weather_setters_found)}"
            )

    # Check for terrain conflicts
    terrain_setters_found = []
    for ability in team_abilities:
        norm = normalize_ability_name(ability)
        if norm in TERRAIN_SETTERS:
            terrain_setters_found.append((ability, TERRAIN_SETTERS[norm]))

    if len(terrain_setters_found) > 1:
        terrains = [t[1] for t in terrain_setters_found]
        if len(set(terrains)) > 1:
            conflicts.append(
                f"Terrain conflict: {', '.join(f'{a} ({t})' for a, t in terrain_setters_found)}"
            )

    # Check for specific anti-synergies
    if "cloud-nine" in normalized or "air-lock" in normalized:
        if any(norm in WEATHER_SETTERS or
               any(norm in abusers for abusers in WEATHER_ABUSERS.values())
               for norm in normalized):
            conflicts.append(
                "Cloud Nine/Air Lock negates weather - conflicts with weather strategy"
            )

    return conflicts


def analyze_full_ability_synergy(
    team_abilities: list[str],
    team_pokemon: Optional[list[str]] = None
) -> AbilitySynergyResult:
    """
    Perform full ability synergy analysis for a team.

    Args:
        team_abilities: List of abilities on the team
        team_pokemon: Optional list of Pokemon names

    Returns:
        AbilitySynergyResult with comprehensive analysis
    """
    # Analyze each category
    weather = analyze_weather_synergy(team_abilities)
    terrain = analyze_terrain_synergy(team_abilities)
    intimidate = analyze_intimidate_matchup(team_abilities, team_pokemon)
    redirects = find_redirect_abilities(team_abilities)
    partners = find_partner_abilities(team_abilities)
    conflicts = find_ability_conflicts(team_abilities)

    # Generate recommendations
    recommendations = []

    if intimidate.recommendation:
        recommendations.append(intimidate.recommendation)

    if weather.has_setter and not weather.abusers:
        recommendations.append(
            f"Consider adding {weather.weather_type} abusers to benefit from weather"
        )

    if not redirects and len(team_abilities) >= 4:
        recommendations.append(
            "Consider a redirect user (Lightning Rod, Storm Drain) for protection"
        )

    return AbilitySynergyResult(
        has_weather_setter=weather.has_setter,
        weather_type=weather.weather_type,
        weather_abusers=weather.abusers,
        has_terrain_setter=terrain["has_setter"],
        terrain_type=terrain["terrain_type"],
        has_intimidate=intimidate.has_intimidate,
        intimidate_answers=intimidate.blockers + intimidate.punishers,
        intimidate_punishers=intimidate.punishers,
        redirect_abilities=[r["ability"] for r in redirects],
        partner_abilities=[p["ability"] for p in partners],
        conflicts=conflicts + weather.conflicts + terrain["conflicts"],
        recommendations=recommendations
    )


def get_speed_ability_effect(
    ability: str,
    weather: Optional[str] = None,
    terrain: Optional[str] = None
) -> Optional[float]:
    """
    Get speed multiplier from ability given conditions.

    Args:
        ability: Pokemon's ability
        weather: Current weather
        terrain: Current terrain

    Returns:
        Speed multiplier if applicable, None otherwise
    """
    norm = normalize_ability_name(ability)

    if norm not in SPEED_ABILITIES:
        return None

    ability_data = SPEED_ABILITIES[norm]
    condition = ability_data.get("condition")

    # Check conditions
    if condition == "rain" and weather == "rain":
        return ability_data.get("multiplier", 1.0)
    elif condition == "sun" and weather == "sun":
        return ability_data.get("multiplier", 1.0)
    elif condition == "sand" and weather == "sand":
        return ability_data.get("multiplier", 1.0)
    elif condition == "snow" and weather == "snow":
        return ability_data.get("multiplier", 1.0)
    elif condition == "electric-terrain" and terrain == "electric":
        return ability_data.get("multiplier", 1.0)

    return None


def apply_ruin_abilities(
    attacker_ability: Optional[str],
    defender_ability: Optional[str],
    modifiers
) -> None:
    """
    Apply Ruinous abilities to DamageModifiers in-place.

    Ruinous abilities affect the opposing Pokemon:
    - Sword of Ruin: Attacker has it → Defender's Def lowered
    - Beads of Ruin: Attacker has it → Defender's SpD lowered
    - Tablets of Ruin: Defender has it → Attacker's Atk lowered
    - Vessel of Ruin: Defender has it → Attacker's SpA lowered

    Args:
        attacker_ability: Attacker's ability name
        defender_ability: Defender's ability name
        modifiers: DamageModifiers object to update
    """
    # Normalize abilities
    atk_norm = normalize_ability_name(attacker_ability) if attacker_ability else None
    def_norm = normalize_ability_name(defender_ability) if defender_ability else None

    # Attacker's Ruinous abilities affect defender's stats
    if atk_norm == "sword-of-ruin":
        modifiers.sword_of_ruin = True
    elif atk_norm == "beads-of-ruin":
        modifiers.beads_of_ruin = True

    # Defender's Ruinous abilities affect attacker's stats
    if def_norm == "tablets-of-ruin":
        modifiers.tablets_of_ruin = True
    elif def_norm == "vessel-of-ruin":
        modifiers.vessel_of_ruin = True


def suggest_ability_additions(
    current_abilities: list[str],
    team_style: Optional[str] = None
) -> list[dict]:
    """
    Suggest abilities that would improve team synergy.

    Args:
        current_abilities: Current team abilities
        team_style: Optional team archetype ("rain", "sun", "trick-room", etc.)

    Returns:
        List of suggested abilities with reasons
    """
    suggestions = []
    normalized = [normalize_ability_name(a) for a in current_abilities]

    # Check for Intimidate protection
    has_protection = any(a in INTIMIDATE_BLOCKERS + INTIMIDATE_PUNISHERS
                        for a in normalized)
    if not has_protection:
        suggestions.append({
            "ability": "defiant",
            "reason": "Punishes Intimidate with +2 Attack",
            "pokemon_examples": ["kingambit", "braviary", "bisharp"]
        })
        suggestions.append({
            "ability": "competitive",
            "reason": "Punishes Intimidate with +2 Sp. Attack",
            "pokemon_examples": ["milotic", "gothitelle", "wigglytuff"]
        })

    # Suggest based on team style
    if team_style == "rain":
        if "drizzle" not in normalized:
            suggestions.append({
                "ability": "drizzle",
                "reason": "Sets up rain for team",
                "pokemon_examples": ["pelipper", "politoed", "kyogre"]
            })
        if "swift-swim" not in normalized:
            suggestions.append({
                "ability": "swift-swim",
                "reason": "Doubles Speed in rain",
                "pokemon_examples": ["barraskewda", "floatzel", "ludicolo"]
            })

    elif team_style == "sun":
        if "drought" not in normalized:
            suggestions.append({
                "ability": "drought",
                "reason": "Sets up sun for team",
                "pokemon_examples": ["torkoal", "ninetales", "koraidon"]
            })
        if "chlorophyll" not in normalized:
            suggestions.append({
                "ability": "chlorophyll",
                "reason": "Doubles Speed in sun",
                "pokemon_examples": ["venusaur", "lilligant", "leafeon"]
            })

    elif team_style == "trick-room":
        suggestions.append({
            "ability": "telepathy",
            "reason": "Immune to ally's spread moves in Trick Room",
            "pokemon_examples": ["oranguru", "gardevoir", "beheeyem"]
        })

    # General suggestions
    if not any(a in REDIRECT_ABILITIES for a in normalized):
        suggestions.append({
            "ability": "lightning-rod",
            "reason": "Redirects Electric moves, protects partner",
            "pokemon_examples": ["raichu", "togedemaru", "seaking"]
        })

    return suggestions[:5]  # Return top 5 suggestions
