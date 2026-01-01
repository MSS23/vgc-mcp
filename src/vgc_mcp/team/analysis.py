"""Team analysis for type coverage, weaknesses, and speed tiers."""

from collections import defaultdict
from typing import Optional

from ..models.team import Team
from ..models.pokemon import PokemonBuild
from ..calc.modifiers import TYPE_CHART, get_type_effectiveness
from ..calc.stats import calculate_all_stats


ALL_TYPES = [
    "Normal", "Fire", "Water", "Electric", "Grass", "Ice",
    "Fighting", "Poison", "Ground", "Flying", "Psychic", "Bug",
    "Rock", "Ghost", "Dragon", "Dark", "Steel", "Fairy"
]


class TeamAnalyzer:
    """Analyze team composition for competitive insights."""

    def analyze_defensive_coverage(self, team: Team) -> dict:
        """
        Analyze team's defensive type matchups.

        Returns dict with:
        - weaknesses: Types that hit 2+ team members super effectively
        - resistances: Types that 2+ team members resist
        - immunities: Types that team has immunities to
        - major_weaknesses: Types that 3+ members are weak to
        - unresisted: Types with no resistances on team
        """
        weakness_count = defaultdict(int)
        resistance_count = defaultdict(int)
        immunity_count = defaultdict(int)
        weak_pokemon = defaultdict(list)
        resist_pokemon = defaultdict(list)
        immune_pokemon = defaultdict(list)

        for slot in team.slots:
            pokemon = slot.pokemon
            pokemon_types = [t.capitalize() for t in pokemon.types]

            for attack_type in ALL_TYPES:
                eff = get_type_effectiveness(attack_type, pokemon_types)

                if eff == 0:
                    immunity_count[attack_type] += 1
                    immune_pokemon[attack_type].append(pokemon.name)
                elif eff < 1:
                    resistance_count[attack_type] += 1
                    resist_pokemon[attack_type].append(pokemon.name)
                elif eff >= 2:
                    weakness_count[attack_type] += 1
                    weak_pokemon[attack_type].append(pokemon.name)

        # Find major weaknesses (3+ Pokemon weak)
        major_weaknesses = [
            {"type": t, "weak_pokemon": weak_pokemon[t]}
            for t, c in weakness_count.items()
            if c >= 3
        ]

        # Find unresisted types (no Pokemon resists or is immune)
        unresisted = [
            t for t in ALL_TYPES
            if t not in resistance_count and t not in immunity_count
        ]

        # Build summary
        weaknesses = {
            t: {"count": c, "pokemon": weak_pokemon[t]}
            for t, c in sorted(weakness_count.items(), key=lambda x: -x[1])
            if c >= 2
        }

        resistances = {
            t: {"count": c, "pokemon": resist_pokemon[t]}
            for t, c in sorted(resistance_count.items(), key=lambda x: -x[1])
            if c >= 2
        }

        immunities = {
            t: {"count": c, "pokemon": immune_pokemon[t]}
            for t, c in immunity_count.items()
        }

        return {
            "weaknesses": weaknesses,
            "resistances": resistances,
            "immunities": immunities,
            "major_weaknesses": major_weaknesses,
            "unresisted_types": unresisted
        }

    def analyze_offensive_coverage(self, team: Team) -> dict:
        """
        Analyze team's offensive type coverage based on Pokemon types.

        Note: This uses Pokemon types as proxy for STAB coverage.
        Full analysis would require knowing moves.
        """
        type_coverage = defaultdict(list)

        for slot in team.slots:
            pokemon = slot.pokemon

            for poke_type in pokemon.types:
                poke_type = poke_type.capitalize()
                if poke_type in TYPE_CHART:
                    for target_type, eff in TYPE_CHART[poke_type].items():
                        if eff >= 2:
                            type_coverage[target_type].append(pokemon.name)

        # Find types with no super-effective coverage
        no_coverage = [
            t for t in ALL_TYPES
            if t not in type_coverage
        ]

        # Sort by coverage count
        coverage_summary = {
            t: {"hits": pokemon_list, "count": len(pokemon_list)}
            for t, pokemon_list in sorted(
                type_coverage.items(),
                key=lambda x: -len(x[1])
            )
        }

        return {
            "super_effective_coverage": coverage_summary,
            "no_super_effective": no_coverage,
            "best_covered": list(coverage_summary.keys())[:5]
        }

    def analyze_speed_tiers(self, team: Team) -> list[dict]:
        """
        Analyze team's speed distribution.

        Returns list of Pokemon sorted by speed (fastest first).
        """
        speed_data = []

        for slot in team.slots:
            pokemon = slot.pokemon
            stats = calculate_all_stats(pokemon)

            speed_data.append({
                "slot": slot.slot_index + 1,
                "name": pokemon.name,
                "speed": stats["speed"],
                "base_speed": pokemon.base_stats.speed,
                "nature": pokemon.nature.value,
                "speed_evs": pokemon.evs.speed,
                "notes": self._get_speed_notes(pokemon, stats["speed"])
            })

        return sorted(speed_data, key=lambda x: x["speed"], reverse=True)

    def _get_speed_notes(self, pokemon: PokemonBuild, speed: int) -> list[str]:
        """Get notes about speed investment."""
        notes = []

        nature = pokemon.nature.value.lower()
        evs = pokemon.evs.speed

        # Check for common speed builds
        if nature in ["timid", "jolly"] and evs == 252:
            notes.append("Max Speed")
        elif nature in ["brave", "quiet", "relaxed", "sassy"] and evs == 0:
            notes.append("Min Speed (Trick Room)")
        elif evs == 0:
            notes.append("Uninvested")

        # Check for speed control synergy
        if speed < 60:
            notes.append("Trick Room candidate")

        return notes

    def analyze_roles(self, team: Team) -> dict:
        """
        Analyze team role distribution based on stats and types.

        Identifies:
        - Physical attackers
        - Special attackers
        - Physical walls
        - Special walls
        - Speed control (slow Pokemon for TR)
        - Support (based on common support types)
        """
        roles = {
            "physical_attackers": [],
            "special_attackers": [],
            "mixed_attackers": [],
            "physical_walls": [],
            "special_walls": [],
            "mixed_walls": [],
            "speed_control": [],
            "support_types": []
        }

        support_types = ["Grass", "Fairy", "Ghost", "Dark"]  # Common support typings

        for slot in team.slots:
            pokemon = slot.pokemon
            stats = calculate_all_stats(pokemon)
            base = pokemon.base_stats

            # Offense classification
            atk_ratio = base.attack / base.special_attack if base.special_attack > 0 else 999

            if atk_ratio > 1.3:
                roles["physical_attackers"].append(pokemon.name)
            elif atk_ratio < 0.77:
                roles["special_attackers"].append(pokemon.name)
            else:
                roles["mixed_attackers"].append(pokemon.name)

            # Defense classification
            def_ratio = base.defense / base.special_defense if base.special_defense > 0 else 999
            total_bulk = base.hp * base.defense * base.special_defense

            if total_bulk > 500000:  # Arbitrary threshold for "bulky"
                if def_ratio > 1.3:
                    roles["physical_walls"].append(pokemon.name)
                elif def_ratio < 0.77:
                    roles["special_walls"].append(pokemon.name)
                else:
                    roles["mixed_walls"].append(pokemon.name)

            # Speed control (slow = good for Trick Room)
            if stats["speed"] < 60:
                roles["speed_control"].append({
                    "name": pokemon.name,
                    "speed": stats["speed"]
                })

            # Support types
            for t in pokemon.types:
                if t.capitalize() in support_types:
                    if pokemon.name not in roles["support_types"]:
                        roles["support_types"].append(pokemon.name)

        return roles

    def get_summary(self, team: Team) -> dict:
        """
        Generate comprehensive team analysis summary.
        """
        if team.size == 0:
            return {"error": "No Pokemon on team to analyze"}

        return {
            "team_size": team.size,
            "pokemon": [slot.pokemon.name for slot in team.slots],
            "defensive_analysis": self.analyze_defensive_coverage(team),
            "offensive_analysis": self.analyze_offensive_coverage(team),
            "speed_tiers": self.analyze_speed_tiers(team),
            "roles": self.analyze_roles(team)
        }

    def get_quick_summary(self, team: Team) -> dict:
        """Get a quick summary without full analysis."""
        if team.size == 0:
            return {"error": "No Pokemon on team"}

        defensive = self.analyze_defensive_coverage(team)

        return {
            "team_size": team.size,
            "pokemon": [slot.pokemon.name for slot in team.slots],
            "major_weaknesses": defensive["major_weaknesses"],
            "unresisted_types": defensive["unresisted_types"],
            "speed_range": self._get_speed_range(team)
        }

    def _get_speed_range(self, team: Team) -> dict:
        """Get min/max speed on team."""
        speeds = []
        for slot in team.slots:
            stats = calculate_all_stats(slot.pokemon)
            speeds.append({
                "name": slot.pokemon.name,
                "speed": stats["speed"]
            })

        if not speeds:
            return {}

        speeds.sort(key=lambda x: x["speed"])
        return {
            "slowest": speeds[0],
            "fastest": speeds[-1]
        }
