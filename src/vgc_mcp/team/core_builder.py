"""Core builder for team composition suggestions."""

from dataclasses import dataclass
from typing import Optional

from ..models.team import Team
from ..models.pokemon import PokemonBuild
from ..api.smogon import SmogonStatsClient
from ..calc.modifiers import get_type_effectiveness


@dataclass
class CoreSuggestion:
    """A suggested Pokemon to pair with existing team members."""
    pokemon_name: str
    synergy_score: float
    reasons: list[str]
    usage_correlation: float  # How often it appears with team members
    covers_weaknesses: list[str]  # What team weaknesses it addresses


@dataclass
class CoreAnalysis:
    """Analysis of how well Pokemon work together."""
    pokemon: list[str]
    synergy_score: float  # 0-100
    strengths: list[str]
    weaknesses: list[str]
    type_coverage: dict[str, int]  # Type -> number of resists
    recommendations: list[str]


# Common role categories for VGC
POKEMON_ROLES = {
    # Speed control
    "tailwind_setter": ["tornadus", "whimsicott", "talonflame", "murkrow", "kilowattrel"],
    "trick_room_setter": ["hatterene", "porygon2", "dusclops", "cresselia", "farigiraf", "indeedee-f"],

    # Weather setters
    "sun_setter": ["torkoal", "groudon", "koraidon"],
    "rain_setter": ["pelipper", "kyogre", "politoed"],
    "sand_setter": ["tyranitar", "hippowdon"],
    "snow_setter": ["abomasnow", "ninetales-alola"],

    # Terrain setters
    "grassy_terrain": ["rillaboom"],
    "electric_terrain": ["pincurchin", "tapu-koko"],
    "psychic_terrain": ["indeedee-f", "indeedee-m", "tapu-lele"],
    "misty_terrain": ["tapu-fini"],

    # Support
    "intimidate": ["incineroar", "landorus-therian", "arcanine", "gyarados"],
    "fake_out": ["incineroar", "rillaboom", "mienshao", "ambipom", "scrafty"],
    "redirection": ["amoonguss", "indeedee-f", "togekiss", "clefairy"],

    # Restricted (Legendaries for Reg G/H)
    "restricted": ["miraidon", "koraidon", "calyrex-shadow", "calyrex-ice",
                   "zacian", "kyogre", "groudon", "rayquaza", "palkia",
                   "dialga", "giratina", "reshiram", "zekrom", "kyurem-white"],
}


def get_pokemon_role(pokemon_name: str) -> list[str]:
    """Get the roles a Pokemon can fill."""
    name = pokemon_name.lower().replace(" ", "-")
    roles = []

    for role, pokemon_list in POKEMON_ROLES.items():
        if name in pokemon_list:
            roles.append(role)

    return roles


def get_type_synergy(types1: list[str], types2: list[str]) -> float:
    """
    Calculate type synergy between two Pokemon.

    Higher score = better defensive synergy (cover each other's weaknesses).
    """
    score = 0

    # Check if types2 resists types1's weaknesses
    for type1 in types1:
        # Common attacking types
        for attack_type in ["Fire", "Water", "Electric", "Ground", "Ice", "Fighting", "Fairy"]:
            eff1 = get_type_effectiveness(attack_type, types1)
            eff2 = get_type_effectiveness(attack_type, types2)

            # If type1 is weak and type2 resists
            if eff1 >= 2.0 and eff2 <= 0.5:
                score += 2
            # If type1 is weak and type2 is neutral
            elif eff1 >= 2.0 and eff2 == 1.0:
                score += 0.5
            # Penalize shared weaknesses
            elif eff1 >= 2.0 and eff2 >= 2.0:
                score -= 1

    return score


async def suggest_partners(
    pokemon_name: str,
    smogon_client: SmogonStatsClient,
    existing_team: Optional[Team] = None,
    limit: int = 10
) -> list[CoreSuggestion]:
    """
    Suggest partner Pokemon based on Smogon teammate data and type synergy.

    Args:
        pokemon_name: The Pokemon to find partners for
        smogon_client: Smogon stats client
        existing_team: Current team context (to avoid duplicates)
        limit: Max suggestions to return

    Returns:
        List of CoreSuggestions ranked by synergy
    """
    # Get teammate data from Smogon
    teammates_data = await smogon_client.suggest_teammates(pokemon_name, limit=30)

    if not teammates_data:
        return []

    # Get types for the input Pokemon
    usage_data = await smogon_client.get_pokemon_usage(pokemon_name)

    suggestions = []
    existing_names = []

    if existing_team:
        existing_names = [p.lower() for p in existing_team.get_pokemon_names()]

    for teammate in teammates_data["suggested_teammates"]:
        mate_name = teammate["name"].lower().replace(" ", "-")

        # Skip if already on team
        if mate_name in existing_names:
            continue

        # Skip the same Pokemon
        if mate_name == pokemon_name.lower().replace(" ", "-"):
            continue

        reasons = []
        synergy_score = 0

        # Factor 1: Usage correlation from Smogon
        usage_correlation = teammate["usage_with"]
        synergy_score += usage_correlation * 0.5  # Weight usage data

        if usage_correlation >= 30:
            reasons.append(f"Strong meta pairing ({usage_correlation:.1f}% usage together)")
        elif usage_correlation >= 15:
            reasons.append(f"Common pairing ({usage_correlation:.1f}% usage together)")

        # Factor 2: Role complementarity
        input_roles = get_pokemon_role(pokemon_name)
        mate_roles = get_pokemon_role(mate_name)

        complementary_roles = []
        for role in mate_roles:
            if role not in input_roles:
                complementary_roles.append(role)
                synergy_score += 5

        if complementary_roles:
            reasons.append(f"Provides: {', '.join(complementary_roles)}")

        # Check for role conflicts
        for role in mate_roles:
            if role in input_roles and role != "fake_out":  # Multiple Fake Out is sometimes OK
                synergy_score -= 3
                reasons.append(f"Note: Overlapping {role}")

        # Factor 3: Coverage for team weaknesses (if team context provided)
        covers_weaknesses = []
        if existing_team:
            # This would require type data from API, simplified for now
            pass

        suggestions.append(CoreSuggestion(
            pokemon_name=teammate["name"],
            synergy_score=synergy_score,
            reasons=reasons,
            usage_correlation=usage_correlation,
            covers_weaknesses=covers_weaknesses
        ))

    # Sort by synergy score
    suggestions.sort(key=lambda x: x.synergy_score, reverse=True)

    return suggestions[:limit]


async def find_popular_cores(
    smogon_client: SmogonStatsClient,
    size: int = 2,
    limit: int = 10
) -> list[dict]:
    """
    Find popular Pokemon cores from usage data.

    Args:
        smogon_client: Smogon stats client
        size: Core size (2 or 3 Pokemon)
        limit: Number of cores to return

    Returns:
        List of popular cores with usage data
    """
    # Get overall usage stats to find top Pokemon
    stats = await smogon_client.get_usage_stats()

    if not stats or "data" not in stats:
        return []

    # Get top 20 Pokemon by usage
    pokemon_usage = []
    for name, data in stats["data"].items():
        usage = data.get("usage", 0) * 100
        if usage >= 5:  # At least 5% usage
            pokemon_usage.append((name, usage))

    pokemon_usage.sort(key=lambda x: -x[1])
    top_pokemon = pokemon_usage[:20]

    cores = []

    # For each top Pokemon, find its best partners
    for pokemon_name, usage in top_pokemon[:10]:
        teammates_data = await smogon_client.suggest_teammates(pokemon_name, limit=5)

        if not teammates_data:
            continue

        for teammate in teammates_data["suggested_teammates"][:3]:
            mate_name = teammate["name"]
            mate_usage = teammate["usage_with"]

            # Avoid duplicates
            core_key = tuple(sorted([pokemon_name.lower(), mate_name.lower()]))

            existing_keys = [tuple(sorted([c["pokemon"][0].lower(), c["pokemon"][1].lower()]))
                            for c in cores]
            if core_key in existing_keys:
                continue

            cores.append({
                "pokemon": [pokemon_name, mate_name],
                "pairing_rate": mate_usage,
                "primary_usage": usage,
                "roles": get_pokemon_role(pokemon_name) + get_pokemon_role(mate_name)
            })

    # Sort by pairing rate
    cores.sort(key=lambda x: x["pairing_rate"], reverse=True)

    return cores[:limit]


def analyze_core_synergy(team: Team) -> CoreAnalysis:
    """
    Analyze how well the current team Pokemon work together.

    Args:
        team: The team to analyze

    Returns:
        CoreAnalysis with synergy score and recommendations
    """
    pokemon_names = team.get_pokemon_names()
    pokemon_types = {slot.pokemon.name: slot.pokemon.types for slot in team.slots}

    strengths = []
    weaknesses = []
    recommendations = []

    # Analyze type coverage
    type_resistances = {}
    type_weaknesses = {}

    all_types = ["Normal", "Fire", "Water", "Electric", "Grass", "Ice",
                 "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
                 "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"]

    for attack_type in all_types:
        resist_count = 0
        weak_count = 0

        for slot in team.slots:
            eff = get_type_effectiveness(attack_type, slot.pokemon.types)
            if eff <= 0.5:
                resist_count += 1
            elif eff >= 2.0:
                weak_count += 1

        type_resistances[attack_type] = resist_count
        type_weaknesses[attack_type] = weak_count

    # Identify strengths (well-covered types)
    for attack_type, count in type_resistances.items():
        if count >= 3:
            strengths.append(f"Excellent {attack_type} resistance ({count} resistances)")
        elif count >= 2:
            strengths.append(f"Good {attack_type} resistance ({count} resistances)")

    # Identify weaknesses (poorly covered types)
    for attack_type, weak in type_weaknesses.items():
        resist = type_resistances.get(attack_type, 0)
        if weak >= 3 and resist == 0:
            weaknesses.append(f"Major {attack_type} weakness ({weak} Pokemon weak, 0 resist)")
            recommendations.append(f"Add a Pokemon that resists {attack_type}")
        elif weak >= 2 and resist <= 1:
            weaknesses.append(f"Notable {attack_type} weakness ({weak} weak, {resist} resist)")

    # Check role coverage
    team_roles = set()
    for name in pokemon_names:
        team_roles.update(get_pokemon_role(name))

    # Check for essential roles
    if not any(role in team_roles for role in ["tailwind_setter", "trick_room_setter"]):
        weaknesses.append("No speed control (Tailwind/Trick Room)")
        recommendations.append("Consider adding speed control")

    if "intimidate" not in team_roles and "fake_out" not in team_roles:
        weaknesses.append("No Intimidate or Fake Out support")
        recommendations.append("Consider adding Incineroar or similar support")

    if not any(role in team_roles for role in ["redirection"]):
        recommendations.append("Consider adding Follow Me/Rage Powder support")

    # Calculate overall synergy score
    synergy_score = 50  # Start at 50

    # Add points for strengths
    synergy_score += len(strengths) * 5

    # Subtract points for weaknesses
    synergy_score -= len(weaknesses) * 7

    # Add points for role coverage
    synergy_score += len(team_roles) * 3

    # Clamp to 0-100
    synergy_score = max(0, min(100, synergy_score))

    return CoreAnalysis(
        pokemon=pokemon_names,
        synergy_score=synergy_score,
        strengths=strengths,
        weaknesses=weaknesses,
        type_coverage=type_resistances,
        recommendations=recommendations
    )


async def complete_team(
    team: Team,
    smogon_client: SmogonStatsClient,
    limit: int = 5
) -> list[CoreSuggestion]:
    """
    Suggest Pokemon to complete an incomplete team.

    Args:
        team: Current partial team
        smogon_client: Smogon stats client
        limit: Number of suggestions per slot

    Returns:
        List of suggestions for remaining slots
    """
    if team.is_full:
        return []

    current_pokemon = team.get_pokemon_names()
    all_suggestions = []

    # Get suggestions based on each team member
    for name in current_pokemon:
        suggestions = await suggest_partners(
            name,
            smogon_client,
            existing_team=team,
            limit=limit * 2
        )
        all_suggestions.extend(suggestions)

    # Deduplicate and rank
    seen = set()
    unique_suggestions = []

    for suggestion in all_suggestions:
        key = suggestion.pokemon_name.lower()
        if key not in seen and key not in [n.lower() for n in current_pokemon]:
            seen.add(key)
            unique_suggestions.append(suggestion)

    # Sort by how many team members suggest this Pokemon (more = better fit)
    name_counts = {}
    for suggestion in all_suggestions:
        name = suggestion.pokemon_name.lower()
        name_counts[name] = name_counts.get(name, 0) + 1

    # Adjust scores based on how many teammates suggest them
    for suggestion in unique_suggestions:
        count = name_counts.get(suggestion.pokemon_name.lower(), 1)
        suggestion.synergy_score += (count - 1) * 10  # Bonus for multiple teammates suggesting

    unique_suggestions.sort(key=lambda x: x.synergy_score, reverse=True)

    return unique_suggestions[:limit]
