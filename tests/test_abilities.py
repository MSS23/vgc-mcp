"""Tests for ability synergy and interaction analysis."""

import pytest
from vgc_mcp_core.calc.abilities import (
    analyze_intimidate_matchup,
    analyze_weather_synergy,
    analyze_terrain_synergy,
    find_redirect_abilities,
    find_partner_abilities,
    find_ability_conflicts,
    analyze_full_ability_synergy,
    get_speed_ability_effect,
    suggest_ability_additions,
    normalize_ability_name,
    INTIMIDATE_BLOCKERS,
    INTIMIDATE_PUNISHERS,
    WEATHER_SETTERS,
    WEATHER_ABUSERS,
    TERRAIN_SETTERS,
    REDIRECT_ABILITIES,
)


class TestIntimidateAnalysis:
    """Test Intimidate interaction analysis."""

    def test_has_intimidate(self):
        """Should detect Intimidate on team."""
        abilities = ["Intimidate", "Protean", "Swift Swim"]
        result = analyze_intimidate_matchup(abilities)
        assert result.has_intimidate is True

    def test_no_intimidate(self):
        """Should detect lack of Intimidate."""
        abilities = ["Protean", "Swift Swim"]
        result = analyze_intimidate_matchup(abilities)
        assert result.has_intimidate is False

    def test_blocker_detected(self):
        """Should detect Intimidate blockers."""
        abilities = ["Clear Body", "Swift Swim"]
        result = analyze_intimidate_matchup(abilities)
        assert len(result.blockers) > 0
        assert result.is_protected is True

    def test_punisher_detected(self):
        """Should detect Intimidate punishers."""
        abilities = ["Defiant", "Swift Swim"]
        result = analyze_intimidate_matchup(abilities)
        assert len(result.punishers) > 0
        assert result.is_protected is True

    def test_recommendation_when_vulnerable(self):
        """Should recommend protection when vulnerable."""
        abilities = ["Protean", "Swift Swim", "Blaze", "Torrent"]
        result = analyze_intimidate_matchup(abilities)
        assert result.recommendation is not None
        assert result.is_protected is False


class TestWeatherSynergy:
    """Test weather synergy analysis."""

    def test_drought_sets_sun(self):
        """Should detect Drought sets sun."""
        abilities = ["Drought", "Chlorophyll"]
        result = analyze_weather_synergy(abilities)
        assert result.has_setter is True
        assert result.weather_type == "sun"

    def test_drizzle_sets_rain(self):
        """Should detect Drizzle sets rain."""
        abilities = ["Drizzle", "Swift Swim"]
        result = analyze_weather_synergy(abilities)
        assert result.has_setter is True
        assert result.weather_type == "rain"

    def test_weather_abusers_detected(self):
        """Should detect weather abusers."""
        abilities = ["Drought", "Chlorophyll", "Solar Power"]
        result = analyze_weather_synergy(abilities)
        assert len(result.abusers) >= 2

    def test_weather_conflict(self):
        """Should detect conflicting weathers."""
        abilities = ["Drought", "Drizzle"]
        result = analyze_weather_synergy(abilities)
        assert len(result.conflicts) > 0

    def test_synergy_score(self):
        """Should calculate synergy score."""
        # No setter = 0
        no_setter = analyze_weather_synergy(["Blaze", "Torrent"])
        assert no_setter.synergy_score == 0.0

        # Setter + abusers = high
        with_abusers = analyze_weather_synergy(["Drought", "Chlorophyll", "Solar Power"])
        assert with_abusers.synergy_score > 0.5


class TestTerrainSynergy:
    """Test terrain synergy analysis."""

    def test_grassy_surge_detected(self):
        """Should detect Grassy Surge."""
        abilities = ["Grassy Surge", "Blaze"]
        result = analyze_terrain_synergy(abilities)
        assert result["has_setter"] is True
        assert result["terrain_type"] == "grassy"

    def test_electric_surge_detected(self):
        """Should detect Electric Surge."""
        abilities = ["Electric Surge", "Blaze"]
        result = analyze_terrain_synergy(abilities)
        assert result["has_setter"] is True
        assert result["terrain_type"] == "electric"

    def test_no_terrain(self):
        """Should handle no terrain setter."""
        abilities = ["Blaze", "Torrent"]
        result = analyze_terrain_synergy(abilities)
        assert result["has_setter"] is False


class TestRedirectAbilities:
    """Test redirect ability detection."""

    def test_lightning_rod(self):
        """Should detect Lightning Rod."""
        abilities = ["Lightning Rod", "Blaze"]
        result = find_redirect_abilities(abilities)
        assert len(result) == 1
        assert result[0]["redirects_type"] == "Electric"

    def test_storm_drain(self):
        """Should detect Storm Drain."""
        abilities = ["Storm Drain", "Blaze"]
        result = find_redirect_abilities(abilities)
        assert len(result) == 1
        assert result[0]["redirects_type"] == "Water"

    def test_multiple_redirects(self):
        """Should detect multiple redirects."""
        abilities = ["Lightning Rod", "Storm Drain"]
        result = find_redirect_abilities(abilities)
        assert len(result) == 2


class TestPartnerAbilities:
    """Test partner-affecting ability detection."""

    def test_friend_guard(self):
        """Should detect Friend Guard."""
        abilities = ["Friend Guard", "Blaze"]
        result = find_partner_abilities(abilities)
        assert len(result) == 1

    def test_power_spot(self):
        """Should detect Power Spot."""
        abilities = ["Power Spot", "Blaze"]
        result = find_partner_abilities(abilities)
        assert len(result) == 1


class TestAbilityConflicts:
    """Test ability conflict detection."""

    def test_weather_conflict(self):
        """Should detect weather conflicts."""
        abilities = ["Drought", "Drizzle"]
        conflicts = find_ability_conflicts(abilities)
        assert len(conflicts) > 0
        assert "weather" in conflicts[0].lower()

    def test_terrain_conflict(self):
        """Should detect terrain conflicts."""
        abilities = ["Grassy Surge", "Electric Surge"]
        conflicts = find_ability_conflicts(abilities)
        assert len(conflicts) > 0
        assert "terrain" in conflicts[0].lower()

    def test_no_conflict(self):
        """Should return empty for no conflicts."""
        abilities = ["Blaze", "Torrent", "Overgrow"]
        conflicts = find_ability_conflicts(abilities)
        assert len(conflicts) == 0


class TestFullSynergyAnalysis:
    """Test complete synergy analysis."""

    def test_full_analysis_structure(self):
        """Should return complete analysis."""
        abilities = ["Intimidate", "Drought", "Chlorophyll", "Defiant"]
        result = analyze_full_ability_synergy(abilities)

        assert hasattr(result, "has_weather_setter")
        assert hasattr(result, "has_intimidate")
        assert hasattr(result, "intimidate_answers")
        assert hasattr(result, "conflicts")
        assert hasattr(result, "recommendations")

    def test_full_analysis_recommendations(self):
        """Should provide recommendations."""
        # Team without protection
        abilities = ["Blaze", "Torrent", "Overgrow", "Swarm"]
        result = analyze_full_ability_synergy(abilities)

        # Should recommend Intimidate protection
        assert len(result.recommendations) > 0


class TestSpeedAbilities:
    """Test speed-modifying abilities."""

    def test_chlorophyll_in_sun(self):
        """Chlorophyll should double speed in sun."""
        multiplier = get_speed_ability_effect("Chlorophyll", weather="sun")
        assert multiplier == 2.0

    def test_chlorophyll_no_sun(self):
        """Chlorophyll should not boost without sun."""
        multiplier = get_speed_ability_effect("Chlorophyll", weather="rain")
        assert multiplier is None

    def test_swift_swim_in_rain(self):
        """Swift Swim should double speed in rain."""
        multiplier = get_speed_ability_effect("Swift Swim", weather="rain")
        assert multiplier == 2.0

    def test_surge_surfer_in_terrain(self):
        """Surge Surfer should double speed in Electric Terrain."""
        multiplier = get_speed_ability_effect("Surge Surfer", terrain="electric")
        assert multiplier == 2.0


class TestAbilitySuggestions:
    """Test ability suggestion logic."""

    def test_suggests_intimidate_counter(self):
        """Should suggest Intimidate counters."""
        abilities = ["Blaze", "Torrent"]
        suggestions = suggest_ability_additions(abilities)

        ability_names = [s["ability"] for s in suggestions]
        assert "defiant" in ability_names or "competitive" in ability_names

    def test_rain_style_suggestions(self):
        """Should suggest rain abilities for rain team."""
        abilities = ["Blaze", "Torrent"]
        suggestions = suggest_ability_additions(abilities, team_style="rain")

        ability_names = [s["ability"] for s in suggestions]
        assert "drizzle" in ability_names or "swift-swim" in ability_names


class TestNormalization:
    """Test ability name normalization."""

    def test_normalize_spaces(self):
        """Should handle spaces."""
        assert normalize_ability_name("Swift Swim") == "swift-swim"

    def test_normalize_case(self):
        """Should handle case."""
        assert normalize_ability_name("INTIMIDATE") == "intimidate"


class TestAbilityLists:
    """Test ability list completeness."""

    def test_intimidate_blockers(self):
        """Should include common blockers."""
        assert "clear-body" in INTIMIDATE_BLOCKERS
        assert "inner-focus" in INTIMIDATE_BLOCKERS

    def test_intimidate_punishers(self):
        """Should include common punishers."""
        assert "defiant" in INTIMIDATE_PUNISHERS
        assert "competitive" in INTIMIDATE_PUNISHERS

    def test_weather_setters(self):
        """Should include all weather setters."""
        assert "drought" in WEATHER_SETTERS
        assert "drizzle" in WEATHER_SETTERS
        assert "sand-stream" in WEATHER_SETTERS

    def test_weather_abusers(self):
        """Should include weather abusers."""
        assert "chlorophyll" in WEATHER_ABUSERS["sun"]
        assert "swift-swim" in WEATHER_ABUSERS["rain"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
