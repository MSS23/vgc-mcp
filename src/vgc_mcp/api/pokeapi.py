"""PokeAPI client with caching and retry logic."""

import asyncio
from typing import Optional

import httpx

from ..config import settings, logger
from ..models.pokemon import BaseStats
from ..models.move import Move, MoveCategory, SPREAD_TARGETS
from .cache import APICache


class PokeAPIError(Exception):
    """Error from PokeAPI."""
    pass


class PokeAPIClient:
    """Async client for PokeAPI v2 with connection pooling and retries."""

    def __init__(self, cache: Optional[APICache] = None):
        """Initialize client with optional cache."""
        self.cache = cache or APICache()
        self._client: Optional[httpx.AsyncClient] = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.API_TIMEOUT_SECONDS),
                headers={"User-Agent": "VGC-MCP-Server/0.1.0"},
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
        return self._client

    def _normalize_name(self, name: str) -> str:
        """Normalize Pokemon/move names for API.

        Examples:
            "Flutter Mane" -> "flutter-mane"
            "Urshifu-Rapid-Strike" -> "urshifu-rapid-strike"
            "King's Rock" -> "kings-rock"
        """
        return name.lower().replace(" ", "-").replace("'", "").replace("'", "")

    async def _fetch(self, endpoint: str) -> dict:
        """Fetch from API with caching and retry logic."""
        # Check cache first
        cached = self.cache.get("pokeapi", endpoint)
        if cached is not None:
            return cached

        # Fetch from API with retries
        client = await self._get_client()
        last_error: Optional[Exception] = None

        for attempt in range(settings.API_MAX_RETRIES):
            try:
                response = await client.get(f"{settings.POKEAPI_BASE_URL}/{endpoint}")
                response.raise_for_status()
                data = response.json()
                self.cache.set("pokeapi", endpoint, value=data)
                return data

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    raise PokeAPIError(f"Not found: {endpoint}") from e
                last_error = e
                logger.warning(f"PokeAPI request failed (attempt {attempt + 1}): {e}")

            except httpx.RequestError as e:
                last_error = e
                logger.warning(f"PokeAPI connection error (attempt {attempt + 1}): {e}")

            if attempt < settings.API_MAX_RETRIES - 1:
                await asyncio.sleep(settings.API_RETRY_DELAY * (attempt + 1))

        raise PokeAPIError(f"Failed after {settings.API_MAX_RETRIES} attempts: {last_error}")

    async def get_pokemon(self, name_or_id: str | int) -> dict:
        """Get Pokemon data including base stats, types, abilities."""
        name = self._normalize_name(str(name_or_id))
        return await self._fetch(f"pokemon/{name}")

    async def get_pokemon_species(self, name_or_id: str | int) -> dict:
        """Get Pokemon species data (for species clause)."""
        name = self._normalize_name(str(name_or_id))
        try:
            return await self._fetch(f"pokemon-species/{name}")
        except PokeAPIError:
            # Some Pokemon forms don't have species data, try base form
            base_name = name.split("-")[0]
            return await self._fetch(f"pokemon-species/{base_name}")

    async def get_base_stats(self, name_or_id: str | int) -> BaseStats:
        """Extract base stats from Pokemon data."""
        data = await self.get_pokemon(name_or_id)

        stats_dict = {}
        for stat_entry in data["stats"]:
            stat_name = stat_entry["stat"]["name"]
            # Convert API names to our model names
            if stat_name == "special-attack":
                stat_name = "special_attack"
            elif stat_name == "special-defense":
                stat_name = "special_defense"
            stats_dict[stat_name] = stat_entry["base_stat"]

        return BaseStats(
            hp=stats_dict["hp"],
            attack=stats_dict["attack"],
            defense=stats_dict["defense"],
            special_attack=stats_dict["special_attack"],
            special_defense=stats_dict["special_defense"],
            speed=stats_dict["speed"]
        )

    async def get_pokemon_types(self, name_or_id: str | int) -> list[str]:
        """Get Pokemon types."""
        data = await self.get_pokemon(name_or_id)
        return [t["type"]["name"].capitalize() for t in data["types"]]

    async def get_pokemon_abilities(self, name_or_id: str | int) -> list[str]:
        """Get Pokemon abilities."""
        data = await self.get_pokemon(name_or_id)
        return [
            a["ability"]["name"].replace("-", " ").title()
            for a in data["abilities"]
        ]

    async def get_move(self, name_or_id: str | int) -> Move:
        """Get move data."""
        name = self._normalize_name(str(name_or_id))
        data = await self._fetch(f"move/{name}")

        target = data.get("target", {}).get("name", "selected-pokemon")

        # Determine if move makes contact
        makes_contact = False
        if "meta" in data and data["meta"]:
            # Check meta category
            meta = data["meta"]
            if meta.get("category", {}).get("name") == "damage+raise":
                pass  # Continue checking
            # Contact is usually in the move's metadata

        return Move(
            name=data["name"],
            type=data["type"]["name"].capitalize(),
            category=MoveCategory(data["damage_class"]["name"]),
            power=data.get("power"),
            accuracy=data.get("accuracy"),
            pp=data.get("pp", 5),
            priority=data.get("priority", 0),
            target=target,
            effect_chance=data.get("effect_chance"),
            makes_contact=makes_contact
        )

    async def get_type(self, name: str) -> dict:
        """Get type data including damage relations."""
        name = self._normalize_name(name)
        return await self._fetch(f"type/{name}")

    async def get_ability(self, name_or_id: str | int) -> dict:
        """Get ability data."""
        name = self._normalize_name(str(name_or_id))
        return await self._fetch(f"ability/{name}")

    async def get_item(self, name_or_id: str | int) -> dict:
        """Get item data."""
        name = self._normalize_name(str(name_or_id))
        return await self._fetch(f"item/{name}")

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self) -> "PokeAPIClient":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
