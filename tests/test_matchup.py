"""Tests for matchup analysis."""

import pytest
from vgc_mcp.calc.matchup import (
    analyze_single_matchup,
    analyze_threat_matchup,
    find_team_threats,
    check_type_coverage,
    analyze_defensive_matchup,
    create_threat_pokemon,
    create_threat_move,
    COMMON_THREATS,
)
from vgc_mcp.models.pokemon import PokemonBuild, BaseStats, Nature, EVSpread
from vgc_mcp.models.move import Move, MoveCategory
from vgc_mcp.models.team import Team


def make_pokemon(
    name: str,
    types: list[str],
    base_hp: int = 80,
    base_atk: int = 80,
    base_def: int = 80,
    base_spa: int = 80,
    base_spd: int = 80,
    base_spe: int = 80,
    evs: EVSpread = None
) -> PokemonBuild:
    """Helper to create Pokemon for testing."""
    return PokemonBuild(
        name=name,
        base_stats=BaseStats(
            hp=base_hp, attack=base_atk, defense=base_def,
            special_attack=base_spa, special_defense=base_spd, speed=base_spe
        ),
        nature=Nature.SERIOUS,
        evs=evs or EVSpread(),
        types=types
    )


def make_team(pokemon_list: list[PokemonBuild]) -> Team:
    """Create a team from Pokemon list."""
    team = Team()
    for p in pokemon_list:
        team.add_pokemon(p)
    return team


class TestThreatCreation:
    """Test threat Pokemon creation."""

    def test_create_known_threat(self):
        """Can create a known threat Pokemon."""
        flutter = create_threat_pokemon("flutter-mane")

        assert flutter is not None
        assert flutter.name == "flutter-mane"
        assert "Ghost" in flutter.types
        assert "Fairy" in flutter.types

    def test_create_unknown_threat_returns_none(self):
        """Unknown threat returns None."""
        unknown = create_threat_pokemon("not-a-real-pokemon")
        assert unknown is None

    def test_create_threat_move(self):
        """Can create moves for threats."""
        move = create_threat_move("flutter-mane", "moonblast")

        assert move is not None
        assert move.name == "moonblast"
        assert move.type == "Fairy"
        assert move.category == MoveCategory.SPECIAL


class TestSingleMatchup:
    """Test single Pokemon matchup analysis."""

    def test_matchup_result_fields(self):
        """Matchup result has all expected fields."""
        attacker = make_pokemon("attacker", ["Fire"], base_atk=130)
        defender = make_pokemon("defender", ["Grass"], base_def=70)

        moves = [Move(
            name="flamethrower",
            type="Fire",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100
        )]

        result = analyze_single_matchup(attacker, defender, moves)

        assert hasattr(result, "attacker_name")
        assert hasattr(result, "defender_name")
        assert hasattr(result, "can_ohko")
        assert hasattr(result, "can_2hko")
        assert hasattr(result, "best_move")
        assert hasattr(result, "outspeeds")
        assert hasattr(result, "is_check")
        assert hasattr(result, "is_counter")

    def test_type_advantage_improves_matchup(self):
        """Type advantage should improve damage."""
        fire_attacker = make_pokemon("fire", ["Fire"], base_spa=130)
        grass_defender = make_pokemon("grass", ["Grass"], base_spd=70)
        water_defender = make_pokemon("water", ["Water"], base_spd=70)

        moves = [Move(
            name="flamethrower",
            type="Fire",
            category=MoveCategory.SPECIAL,
            power=90,
            accuracy=100
        )]

        vs_grass = analyze_single_matchup(fire_attacker, grass_defender, moves)
        vs_water = analyze_single_matchup(fire_attacker, water_defender, moves)

        # Should do more damage to Grass (2x) than Water (0.5x)
        # At minimum, damage_range string should differ
        assert vs_grass.damage_range != vs_water.damage_range


class TestThreatMatchup:
    """Test threat matchup analysis."""

    def test_analyze_known_threat(self):
        """Can analyze matchup vs known threat."""
        # Create a team with varied Pokemon
        water = make_pokemon("water-mon", ["Water"], base_def=100, base_spd=100)
        steel = make_pokemon("steel-mon", ["Steel"], base_def=120, base_spd=100)

        team = make_team([water, steel])
        analysis = analyze_threat_matchup(team, "flutter-mane")

        assert analysis.threat_name == "flutter-mane"
        assert analysis.threat_speed > 0
        assert isinstance(analysis.ohko_by, list)
        assert isinstance(analysis.threatened, list)

    def test_analyze_unknown_threat(self):
        """Unknown threat returns error in notes."""
        water = make_pokemon("water-mon", ["Water"])
        team = make_team([water])

        analysis = analyze_threat_matchup(team, "not-a-pokemon")

        assert any("Unknown" in note for note in analysis.notes)


class TestFindTeamThreats:
    """Test team-wide threat finding."""

    def test_returns_threat_summary(self):
        """Should return a threat summary object."""
        water = make_pokemon("water-mon", ["Water"])
        fire = make_pokemon("fire-mon", ["Fire"])
        team = make_team([water, fire])

        summary = find_team_threats(team)

        assert hasattr(summary, "major_threats")
        assert hasattr(summary, "moderate_threats")
        assert hasattr(summary, "checks_available")
        assert hasattr(summary, "counters_available")
        assert hasattr(summary, "coverage_gaps")


class TestTypeCoverage:
    """Test type coverage checking."""

    def test_has_coverage(self):
        """Should identify super effective coverage."""
        fire = make_pokemon("fire-mon", ["Fire"])
        team = make_team([fire])

        coverage = check_type_coverage(team, "Grass")

        assert coverage["has_coverage"] == True
        assert len(coverage["super_effective"]) > 0

    def test_lacks_coverage(self):
        """Should identify when coverage is missing."""
        water = make_pokemon("water-mon", ["Water"])
        team = make_team([water])

        coverage = check_type_coverage(team, "Dragon")

        assert coverage["has_coverage"] == False


class TestDefensiveMatchup:
    """Test defensive matchup analysis."""

    def test_identifies_resistances(self):
        """Should identify Pokemon that resist a type."""
        water = make_pokemon("water-mon", ["Water"])
        fire = make_pokemon("fire-mon", ["Fire"])
        team = make_team([water, fire])

        matchup = analyze_defensive_matchup(team, "Fire")

        # Water resists Fire (0.5x)
        assert "water-mon" in matchup["resists"]
        # Fire also resists Fire (0.5x) - this is correct Pokemon type mechanics
        assert "fire-mon" in matchup["resists"]

    def test_identifies_weaknesses(self):
        """Should identify Pokemon weak to a type."""
        grass = make_pokemon("grass-mon", ["Grass"])
        team = make_team([grass])

        matchup = analyze_defensive_matchup(team, "Fire")

        assert "grass-mon" in matchup["weak"]

    def test_identifies_immunities(self):
        """Should identify immune Pokemon."""
        normal = make_pokemon("normal-mon", ["Normal"])
        ghost = make_pokemon("ghost-mon", ["Ghost"])
        team = make_team([normal, ghost])

        matchup = analyze_defensive_matchup(team, "Normal")

        assert "ghost-mon" in matchup["immune"]

    def test_safe_switch_ins_count(self):
        """Should count safe switch-ins correctly."""
        water = make_pokemon("water-mon", ["Water"])
        fire = make_pokemon("fire-mon", ["Fire"])
        grass = make_pokemon("grass-mon", ["Grass"])
        team = make_team([water, fire, grass])

        matchup = analyze_defensive_matchup(team, "Fire")

        # Water resists Fire (0.5x), Fire resists Fire (0.5x), Grass is weak (2x)
        # Safe switch-ins = immune + resists = 0 + 2 = 2
        assert matchup["safe_switch_ins"] == 2


class TestCommonThreats:
    """Test that common threats data is valid."""

    def test_all_threats_have_required_fields(self):
        """All threat entries should have required fields."""
        required_fields = ["base_stats", "types", "nature", "evs", "ability", "item", "moves", "move_data"]

        for threat_name, threat_data in COMMON_THREATS.items():
            for field in required_fields:
                assert field in threat_data, f"{threat_name} missing {field}"

    def test_all_threat_moves_have_data(self):
        """All moves in threat movesets should have move_data."""
        for threat_name, threat_data in COMMON_THREATS.items():
            moves = threat_data["moves"]
            move_data = threat_data["move_data"]

            for move in moves:
                assert move in move_data, f"{threat_name} missing data for {move}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
