"""Tests for API clients with mocked responses."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from vgc_mcp_core.api.pokeapi import PokeAPIClient, PokeAPIError
from vgc_mcp_core.api.cache import APICache
from vgc_mcp_core.models.pokemon import BaseStats
from vgc_mcp_core.models.move import Move, MoveCategory


# Sample PokeAPI responses
FLUTTER_MANE_RESPONSE = {
    "id": 987,
    "name": "flutter-mane",
    "types": [
        {"slot": 1, "type": {"name": "ghost", "url": "..."}},
        {"slot": 2, "type": {"name": "fairy", "url": "..."}}
    ],
    "stats": [
        {"base_stat": 55, "stat": {"name": "hp"}},
        {"base_stat": 55, "stat": {"name": "attack"}},
        {"base_stat": 55, "stat": {"name": "defense"}},
        {"base_stat": 135, "stat": {"name": "special-attack"}},
        {"base_stat": 135, "stat": {"name": "special-defense"}},
        {"base_stat": 135, "stat": {"name": "speed"}}
    ],
    "abilities": [
        {"ability": {"name": "protosynthesis"}, "is_hidden": False}
    ]
}

MOONBLAST_RESPONSE = {
    "id": 585,
    "name": "moonblast",
    "type": {"name": "fairy"},
    "power": 95,
    "pp": 15,
    "accuracy": 100,
    "damage_class": {"name": "special"},
    "target": {"name": "selected-pokemon"},
    "effect_chance": 30,
    "meta": {
        "ailment": {"name": "none"},
        "category": {"name": "damage+lower"},
        "stat_chance": 30
    }
}


class TestPokeAPIClient:
    """Test PokeAPIClient functionality."""

    @pytest.fixture
    def mock_cache(self):
        """Create a mock cache that returns None (cache miss)."""
        cache = MagicMock(spec=APICache)
        cache.get.return_value = None
        return cache

    @pytest.fixture
    def client(self, mock_cache):
        """Create client with mocked cache."""
        return PokeAPIClient(cache=mock_cache)

    def test_normalize_name_simple(self, client):
        """Test basic name normalization."""
        assert client._normalize_name("Flutter Mane") == "flutter-mane"
        assert client._normalize_name("Dragapult") == "dragapult"

    def test_normalize_name_with_apostrophe(self, client):
        """Test name normalization with apostrophes."""
        assert client._normalize_name("King's Rock") == "kings-rock"

    def test_normalize_name_form_aliases(self, client):
        """Test that form aliases are applied for PokeAPI."""
        # Base Landorus should become landorus-incarnate for PokeAPI
        assert client._normalize_name("landorus") == "landorus-incarnate"
        assert client._normalize_name("Urshifu") == "urshifu-single-strike"

    def test_normalize_name_explicit_forms_unchanged(self, client):
        """Test that explicit forms are not double-aliased."""
        # Already has form suffix - should stay
        assert client._normalize_name("landorus-therian") == "landorus-therian"
        assert client._normalize_name("urshifu-rapid-strike") == "urshifu-rapid-strike"

    @pytest.mark.asyncio
    async def test_get_pokemon_returns_data(self, client, mock_cache):
        """Test getting Pokemon data with mocked response."""
        # Mock the _fetch method
        with patch.object(client, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = FLUTTER_MANE_RESPONSE

            result = await client.get_pokemon("flutter-mane")

            assert result["name"] == "flutter-mane"
            assert len(result["types"]) == 2
            mock_fetch.assert_called_once_with("pokemon/flutter-mane")

    @pytest.mark.asyncio
    async def test_get_base_stats(self, client, mock_cache):
        """Test extracting base stats from Pokemon data."""
        with patch.object(client, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = FLUTTER_MANE_RESPONSE

            stats = await client.get_base_stats("flutter-mane")

            assert isinstance(stats, BaseStats)
            assert stats.hp == 55
            assert stats.special_attack == 135
            assert stats.speed == 135

    @pytest.mark.asyncio
    async def test_get_pokemon_types(self, client, mock_cache):
        """Test extracting Pokemon types."""
        with patch.object(client, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = FLUTTER_MANE_RESPONSE

            types = await client.get_pokemon_types("flutter-mane")

            assert types == ["Ghost", "Fairy"]

    @pytest.mark.asyncio
    async def test_get_pokemon_abilities(self, client, mock_cache):
        """Test extracting Pokemon abilities."""
        with patch.object(client, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = FLUTTER_MANE_RESPONSE

            abilities = await client.get_pokemon_abilities("flutter-mane")

            assert "Protosynthesis" in abilities

    @pytest.mark.asyncio
    async def test_get_move(self, client, mock_cache):
        """Test getting move data."""
        with patch.object(client, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.return_value = MOONBLAST_RESPONSE

            move = await client.get_move("moonblast")

            assert isinstance(move, Move)
            assert move.name == "moonblast"
            assert move.power == 95
            assert move.type == "Fairy"
            assert move.category == MoveCategory.SPECIAL

    @pytest.mark.asyncio
    async def test_cache_hit_skips_api_call(self, client, mock_cache):
        """Test that cache hits skip the API call."""
        mock_cache.get.return_value = FLUTTER_MANE_RESPONSE

        with patch.object(client, '_get_client') as mock_get_client:
            result = await client.get_pokemon("flutter-mane")

            assert result == FLUTTER_MANE_RESPONSE
            # _get_client should not be called when cache hits
            mock_get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_404_raises_error(self, client, mock_cache):
        """Test that 404 responses raise PokeAPIError."""
        import httpx

        with patch.object(client, '_fetch', new_callable=AsyncMock) as mock_fetch:
            mock_fetch.side_effect = PokeAPIError("Not found: pokemon/not-a-pokemon")

            with pytest.raises(PokeAPIError) as exc_info:
                await client.get_pokemon("not-a-pokemon")

            assert "Not found" in str(exc_info.value)


class TestAPICache:
    """Test API caching functionality."""

    def test_cache_set_and_get(self):
        """Test basic cache set and get."""
        cache = APICache()
        cache.set("pokeapi", "pokemon/pikachu", value={"name": "pikachu"})

        result = cache.get("pokeapi", "pokemon/pikachu")
        assert result == {"name": "pikachu"}

    def test_cache_miss_returns_none(self):
        """Test cache miss returns None."""
        cache = APICache()
        result = cache.get("pokeapi", "pokemon/not-cached")
        assert result is None

    def test_cache_different_sources(self):
        """Test that different sources have separate caches."""
        cache = APICache()
        cache.set("pokeapi", "test", value={"source": "pokeapi"})
        cache.set("smogon", "test", value={"source": "smogon"})

        assert cache.get("pokeapi", "test")["source"] == "pokeapi"
        assert cache.get("smogon", "test")["source"] == "smogon"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
