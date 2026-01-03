"""Integration tests verifying all VGC Pokemon can be fetched from PokeAPI.

These tests make actual API calls to PokeAPI to verify that all common VGC
Pokemon names resolve correctly through our form aliasing system.

Run with: pytest tests/test_pokeapi_forms.py -v
Skip with: pytest tests/test_pokeapi_forms.py -v -m "not integration"
"""

import pytest
from vgc_mcp_core.api.pokeapi import PokeAPIClient, POKEAPI_FORM_ALIASES
from vgc_mcp_core.utils.fuzzy import COMMON_POKEMON


# Pokemon that require form aliases (short name -> PokeAPI name)
ALIASED_POKEMON = [
    # Forces of Nature base forms
    ("landorus", "landorus-incarnate"),
    ("tornadus", "tornadus-incarnate"),
    ("thundurus", "thundurus-incarnate"),
    ("enamorus", "enamorus-incarnate"),
    # Urshifu base form
    ("urshifu", "urshifu-single-strike"),
    # Gender-dimorphic base forms
    ("indeedee", "indeedee-male"),
    ("basculegion", "basculegion-male"),
    ("meowstic", "meowstic-male"),
    # Ogerpon mask forms
    ("ogerpon-wellspring", "ogerpon-wellspring-mask"),
    ("ogerpon-hearthflame", "ogerpon-hearthflame-mask"),
    ("ogerpon-cornerstone", "ogerpon-cornerstone-mask"),
    ("ogerpon-teal", "ogerpon-teal-mask"),
    # Gender short forms
    ("indeedee-f", "indeedee-female"),
    ("indeedee-m", "indeedee-male"),
    ("meowstic-f", "meowstic-female"),
    ("meowstic-m", "meowstic-male"),
]


# VGC Pokemon that should work directly without aliasing
VGC_POKEMON_DIRECT = [
    # Paradox Pokemon
    "flutter-mane",
    "iron-hands",
    "iron-bundle",
    "iron-valiant",
    "iron-moth",
    "roaring-moon",
    "great-tusk",
    "iron-treads",
    "iron-crown",
    "iron-boulder",
    "raging-bolt",
    "gouging-fire",
    # Calyrex forms
    "calyrex",
    "calyrex-ice",
    "calyrex-shadow",
    # Therian forms
    "landorus-therian",
    "tornadus-therian",
    "thundurus-therian",
    # Regional forms
    "arcanine-hisui",
    "ninetales-alola",
    "lilligant-hisui",
    # Origin forms
    "giratina-origin",
    # Special forms
    "palafin-hero",
    "ursaluna-bloodmoon",
    # Common VGC Pokemon
    "incineroar",
    "rillaboom",
    "amoonguss",
    "grimmsnarl",
    "whimsicott",
    "dragapult",
    "garchomp",
    "tyranitar",
    "kingambit",
    "gholdengo",
    "ogerpon",
    "urshifu-rapid-strike",
    "urshifu-single-strike",
    "indeedee-female",
    "indeedee-male",
    "meowstic-female",
    "meowstic-male",
]


class TestFormAliasMapping:
    """Test that form aliases are correctly configured."""

    def test_all_expected_aliases_exist(self):
        """Verify all expected form aliases are in POKEAPI_FORM_ALIASES."""
        for short_name, expected_api_name in ALIASED_POKEMON:
            assert short_name in POKEAPI_FORM_ALIASES, \
                f"Missing alias for {short_name}"
            assert POKEAPI_FORM_ALIASES[short_name] == expected_api_name, \
                f"Wrong alias for {short_name}: expected {expected_api_name}, got {POKEAPI_FORM_ALIASES[short_name]}"

    def test_ogerpon_forms_in_common_pokemon(self):
        """Verify Ogerpon forms are in COMMON_POKEMON for fuzzy matching."""
        expected = ["ogerpon", "ogerpon-wellspring", "ogerpon-hearthflame", "ogerpon-cornerstone"]
        for pokemon in expected:
            assert pokemon in COMMON_POKEMON, f"Missing {pokemon} in COMMON_POKEMON"

    def test_meowstic_forms_in_common_pokemon(self):
        """Verify Meowstic forms are in COMMON_POKEMON for fuzzy matching."""
        expected = ["meowstic", "meowstic-male", "meowstic-female"]
        for pokemon in expected:
            assert pokemon in COMMON_POKEMON, f"Missing {pokemon} in COMMON_POKEMON"


@pytest.mark.integration
class TestPokeAPIIntegration:
    """Integration tests that make actual PokeAPI calls.

    These tests verify that Pokemon names resolve correctly through the API.
    They are marked with 'integration' and can be skipped with -m "not integration".
    """

    @pytest.fixture
    def client(self):
        """Create a real PokeAPI client."""
        return PokeAPIClient()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("short_name,api_name", ALIASED_POKEMON[:4])  # Test subset
    async def test_aliased_pokemon_resolve(self, client, short_name, api_name):
        """Test that aliased Pokemon names resolve correctly."""
        try:
            data = await client.get_pokemon(short_name)
            assert data is not None
            assert data.get("name") == api_name
        except Exception as e:
            pytest.fail(f"Failed to fetch {short_name} (expected {api_name}): {e}")
        finally:
            await client.close()

    @pytest.mark.asyncio
    @pytest.mark.parametrize("pokemon", VGC_POKEMON_DIRECT[:5])  # Test subset
    async def test_direct_pokemon_names(self, client, pokemon):
        """Test that direct Pokemon names work without aliasing."""
        try:
            data = await client.get_pokemon(pokemon)
            assert data is not None
            assert "name" in data
        except Exception as e:
            pytest.fail(f"Failed to fetch {pokemon}: {e}")
        finally:
            await client.close()

    @pytest.mark.asyncio
    async def test_ogerpon_wellspring_full_flow(self, client):
        """Test complete flow for Ogerpon-Wellspring form."""
        try:
            # Should resolve ogerpon-wellspring -> ogerpon-wellspring-mask
            data = await client.get_pokemon("ogerpon-wellspring")
            assert data["name"] == "ogerpon-wellspring-mask"

            # Verify types (Grass/Water)
            types = await client.get_pokemon_types("ogerpon-wellspring")
            assert "Grass" in types
            assert "Water" in types

            # Verify base stats
            stats = await client.get_base_stats("ogerpon-wellspring")
            assert stats.hp == 80
            assert stats.attack == 120
            assert stats.speed == 110
        finally:
            await client.close()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
