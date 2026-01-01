"""Tests for team management."""

import pytest
from vgc_mcp.team.manager import TeamManager
from vgc_mcp.models.pokemon import PokemonBuild, Nature, BaseStats, EVSpread


def make_pokemon(name: str, types: list[str] = None) -> PokemonBuild:
    """Helper to create a Pokemon build for testing."""
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=80, attack=80, defense=80,
            special_attack=80, special_defense=80, speed=80
        ),
        nature=Nature.SERIOUS,
        evs=EVSpread(),
        types=types or ["Normal"]
    )


class TestTeamManager:
    """Test team management functionality."""

    def test_add_pokemon(self):
        """Can add Pokemon to empty team."""
        manager = TeamManager()
        pokemon = make_pokemon("pikachu", ["Electric"])

        success, message, data = manager.add_pokemon(pokemon)

        assert success
        assert manager.size == 1
        assert "pikachu" in manager.team.get_pokemon_names()

    def test_add_up_to_six(self):
        """Can add up to 6 Pokemon."""
        manager = TeamManager()

        names = ["pikachu", "charizard", "blastoise", "venusaur", "mewtwo", "mew"]
        for name in names:
            success, _, _ = manager.add_pokemon(make_pokemon(name))
            assert success

        assert manager.size == 6
        assert manager.is_full

    def test_cannot_exceed_six(self):
        """Cannot add 7th Pokemon."""
        manager = TeamManager()

        for i in range(6):
            manager.add_pokemon(make_pokemon(f"pokemon{i}"))

        success, message, data = manager.add_pokemon(make_pokemon("extra"))

        assert not success
        assert "full" in message.lower() or "team_full" in str(data)

    def test_species_clause(self):
        """Cannot add duplicate species."""
        manager = TeamManager()

        manager.add_pokemon(make_pokemon("pikachu"))
        success, message, data = manager.add_pokemon(make_pokemon("pikachu"))

        assert not success
        assert "species" in message.lower()

    def test_species_clause_forms(self):
        """Species clause applies to different forms."""
        manager = TeamManager()

        # Urshifu forms should trigger species clause
        urshifu1 = make_pokemon("urshifu-single-strike")
        urshifu2 = make_pokemon("urshifu-rapid-strike")

        manager.add_pokemon(urshifu1)
        success, message, _ = manager.add_pokemon(urshifu2)

        assert not success
        assert "species" in message.lower()

    def test_remove_pokemon(self):
        """Can remove Pokemon by slot."""
        manager = TeamManager()
        manager.add_pokemon(make_pokemon("pikachu"))
        manager.add_pokemon(make_pokemon("charizard"))

        success, message, _ = manager.remove_pokemon(0)

        assert success
        assert manager.size == 1
        assert "pikachu" not in manager.team.get_pokemon_names()
        assert "charizard" in manager.team.get_pokemon_names()

    def test_remove_by_name(self):
        """Can remove Pokemon by name."""
        manager = TeamManager()
        manager.add_pokemon(make_pokemon("pikachu"))
        manager.add_pokemon(make_pokemon("charizard"))

        success, _, _ = manager.remove_by_name("pikachu")

        assert success
        assert "pikachu" not in manager.team.get_pokemon_names()

    def test_swap_pokemon(self):
        """Can swap Pokemon in a slot."""
        manager = TeamManager()
        manager.add_pokemon(make_pokemon("pikachu"))

        new_pokemon = make_pokemon("raichu")
        success, message, data = manager.swap_pokemon(0, new_pokemon)

        assert success
        assert "pikachu" not in manager.team.get_pokemon_names()
        assert "raichu" in manager.team.get_pokemon_names()

    def test_reorder_team(self):
        """Can reorder Pokemon positions."""
        manager = TeamManager()
        manager.add_pokemon(make_pokemon("pikachu"))
        manager.add_pokemon(make_pokemon("charizard"))
        manager.add_pokemon(make_pokemon("blastoise"))

        success, _, _ = manager.reorder(0, 2)

        assert success
        names = manager.team.get_pokemon_names()
        assert names[0] == "blastoise"
        assert names[2] == "pikachu"

    def test_clear_team(self):
        """Can clear entire team."""
        manager = TeamManager()
        manager.add_pokemon(make_pokemon("pikachu"))
        manager.add_pokemon(make_pokemon("charizard"))

        success, _, data = manager.clear()

        assert success
        assert manager.size == 0
        assert data["removed_count"] == 2

    def test_get_team_summary(self):
        """Can get team summary."""
        manager = TeamManager()
        pokemon = make_pokemon("pikachu", ["Electric"])
        pokemon.item = "light-ball"
        pokemon.ability = "static"
        manager.add_pokemon(pokemon)

        summary = manager.get_team_summary()

        assert summary["size"] == 1
        assert len(summary["pokemon"]) == 1
        assert summary["pokemon"][0]["name"] == "pikachu"
        assert summary["pokemon"][0]["item"] == "light-ball"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
