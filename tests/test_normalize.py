"""Tests for name normalization utilities."""

import pytest
from vgc_mcp_core.utils.normalize import (
    normalize_name,
    normalize_pokemon_name,
    normalize_ability,
    normalize_item,
    normalize_move,
    clear_caches,
    ITEM_ALIASES,
    ABILITY_ALIASES,
)


class TestNormalizeItem:
    """Test item name normalization."""

    def setup_method(self):
        """Clear caches before each test."""
        clear_caches()

    def test_basic_hyphenation(self):
        """Spaces are converted to hyphens."""
        assert normalize_item("Life Orb") == "life-orb"
        assert normalize_item("Choice Band") == "choice-band"

    def test_underscores_converted(self):
        """Underscores are converted to hyphens."""
        assert normalize_item("life_orb") == "life-orb"

    def test_already_hyphenated(self):
        """Already hyphenated names stay the same."""
        assert normalize_item("life-orb") == "life-orb"
        assert normalize_item("choice-band") == "choice-band"

    def test_smogon_concatenated_format(self):
        """Smogon's concatenated format is properly converted."""
        assert normalize_item("lifeorb") == "life-orb"
        assert normalize_item("choiceband") == "choice-band"
        assert normalize_item("choicespecs") == "choice-specs"
        assert normalize_item("choicescarf") == "choice-scarf"
        assert normalize_item("assaultvest") == "assault-vest"
        assert normalize_item("focussash") == "focus-sash"
        assert normalize_item("boosterenergy") == "booster-energy"

    def test_case_insensitive(self):
        """Normalization is case insensitive."""
        assert normalize_item("LIFE ORB") == "life-orb"
        assert normalize_item("LifeOrb") == "life-orb"
        assert normalize_item("LIFEORB") == "life-orb"

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert normalize_item("") == ""

    def test_none_handling(self):
        """None returns empty string."""
        assert normalize_item(None) == ""  # type: ignore

    def test_whitespace_stripped(self):
        """Leading/trailing whitespace is stripped."""
        assert normalize_item("  life orb  ") == "life-orb"


class TestNormalizeAbility:
    """Test ability name normalization."""

    def setup_method(self):
        """Clear caches before each test."""
        clear_caches()

    def test_basic_hyphenation(self):
        """Spaces are converted to hyphens."""
        assert normalize_ability("Sheer Force") == "sheer-force"
        assert normalize_ability("Huge Power") == "huge-power"

    def test_already_hyphenated(self):
        """Already hyphenated names stay the same."""
        assert normalize_ability("sheer-force") == "sheer-force"
        assert normalize_ability("huge-power") == "huge-power"

    def test_smogon_concatenated_format(self):
        """Smogon's concatenated format is properly converted."""
        assert normalize_ability("sheerforce") == "sheer-force"
        assert normalize_ability("hugepower") == "huge-power"
        assert normalize_ability("purepower") == "pure-power"
        assert normalize_ability("gorillatactics") == "gorilla-tactics"
        assert normalize_ability("orichalcumpulse") == "orichalcum-pulse"
        assert normalize_ability("hadronengine") == "hadron-engine"
        assert normalize_ability("supremeoverlord") == "supreme-overlord"

    def test_apostrophes_removed(self):
        """Apostrophes are removed."""
        assert normalize_ability("Mind's Eye") == "minds-eye"

    def test_case_insensitive(self):
        """Normalization is case insensitive."""
        assert normalize_ability("SHEER FORCE") == "sheer-force"
        assert normalize_ability("SheerForce") == "sheer-force"

    def test_empty_string(self):
        """Empty string returns empty string."""
        assert normalize_ability("") == ""


class TestNormalizeMove:
    """Test move name normalization."""

    def setup_method(self):
        """Clear caches before each test."""
        clear_caches()

    def test_basic_hyphenation(self):
        """Spaces are converted to hyphens."""
        assert normalize_move("Flare Blitz") == "flare-blitz"
        assert normalize_move("Close Combat") == "close-combat"

    def test_apostrophes_removed(self):
        """Apostrophes are removed."""
        assert normalize_move("King's Shield") == "kings-shield"

    def test_case_insensitive(self):
        """Normalization is case insensitive."""
        assert normalize_move("FLARE BLITZ") == "flare-blitz"


class TestNormalizePokemonName:
    """Test Pokemon name normalization."""

    def setup_method(self):
        """Clear caches before each test."""
        clear_caches()

    def test_form_names(self):
        """Pokemon form names are properly normalized."""
        assert normalize_pokemon_name("Landorus-Incarnate") == "landorus-incarnate"
        assert normalize_pokemon_name("Ogerpon-Wellspring") == "ogerpon-wellspring"
        assert normalize_pokemon_name("Urshifu-Rapid-Strike") == "urshifu-rapid-strike"

    def test_case_insensitive(self):
        """Normalization is case insensitive."""
        assert normalize_pokemon_name("PIKACHU") == "pikachu"
        assert normalize_pokemon_name("Charizard") == "charizard"


class TestAliasesCompleteness:
    """Test that critical aliases are present."""

    def test_critical_item_aliases_exist(self):
        """Critical VGC items have aliases."""
        critical_items = [
            "lifeorb",
            "choiceband",
            "choicespecs",
            "choicescarf",
            "assaultvest",
            "focussash",
            "boosterenergy",
        ]
        for item in critical_items:
            assert item in ITEM_ALIASES, f"Missing item alias: {item}"

    def test_critical_ability_aliases_exist(self):
        """Critical VGC abilities have aliases."""
        critical_abilities = [
            "sheerforce",
            "hugepower",
            "purepower",
            "orichalcumpulse",
            "hadronengine",
        ]
        for ability in critical_abilities:
            assert ability in ABILITY_ALIASES, f"Missing ability alias: {ability}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
