"""PokeAPI client with caching and retry logic."""

import asyncio
from typing import Optional

import httpx

from ..config import logger, settings
from ..models.move import (
    MOVE_SECONDARY_EFFECTS,
    Move,
    MoveCategory,
    get_move_type_for_user,
    get_multi_hit_info,
    is_always_crit_move,
    move_makes_contact,
)
from ..models.pokemon import BaseStats
from ..utils.normalize import normalize_move, reorder_mega_prefix
from .cache import APICache

# Map base form names to PokeAPI's explicit form naming
# PokeAPI requires the explicit form suffix (e.g., "landorus-incarnate")
POKEAPI_FORM_ALIASES = {
    # Forces of Nature - PokeAPI uses explicit "-incarnate" suffix
    "landorus": "landorus-incarnate",
    "tornadus": "tornadus-incarnate",
    "thundurus": "thundurus-incarnate",
    "enamorus": "enamorus-incarnate",

    # Urshifu - PokeAPI uses explicit "-single-strike" suffix
    "urshifu": "urshifu-single-strike",

    # Gender-dimorphic Pokemon - PokeAPI uses explicit "-male" suffix
    "indeedee": "indeedee-male",
    "basculegion": "basculegion-male",
    "meowstic": "meowstic-male",

    # Short form aliases for gender-dimorphic Pokemon
    "indeedee-f": "indeedee-female",
    "indeedee-m": "indeedee-male",
    "meowstic-f": "meowstic-female",
    "meowstic-m": "meowstic-male",

    # Ogerpon mask forms - PokeAPI requires "-mask" suffix
    "ogerpon-wellspring": "ogerpon-wellspring-mask",
    "ogerpon-hearthflame": "ogerpon-hearthflame-mask",
    "ogerpon-cornerstone": "ogerpon-cornerstone-mask",
    "ogerpon-teal": "ogerpon-teal-mask",

    # Mega Evolution forms — PokeAPI uses `<species>-mega`. Users (and many
    # tools) write them as "Mega Charizard X", "Manectric-Mega", or
    # "Mega-Manectric". The rewriter in `_normalize_name` collapses all of
    # those to the canonical PokeAPI key. Mega forms are legal only in
    # Pokemon Champions Reg MA; the format inference picks up on this.
    "mega-charizard-x": "charizard-mega-x",
    "mega-charizard-y": "charizard-mega-y",
    "mega-mewtwo-x": "mewtwo-mega-x",
    "mega-mewtwo-y": "mewtwo-mega-y",
    "charizard-mega": "charizard-mega-y",  # default Mega Charizard -> Y form
    "mewtwo-mega": "mewtwo-mega-y",
}


class PokeAPIError(Exception):
    """Error from PokeAPI."""
    pass


class PokeAPIClient:
    """Async client for PokeAPI v2 with connection pooling and retries."""

    # 404s are negatively cached in-memory for this many seconds so repeated
    # lookups of an unknown form don't re-hit the API each time.
    NEGATIVE_CACHE_TTL = 300.0

    def __init__(self, cache: Optional[APICache] = None):
        """Initialize client with optional cache."""
        self.cache = cache or APICache()
        self._client: Optional[httpx.AsyncClient] = None
        # In-flight request coalescing: concurrent identical fetches await one
        # shared task instead of each hitting the network.
        self._inflight: dict[str, "asyncio.Future[dict]"] = {}
        # endpoint -> monotonic timestamp when it 404'd (short-TTL negative cache)
        self._negative_cache: dict[str, float] = {}

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create HTTP client with connection pooling."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(settings.API_TIMEOUT_SECONDS),
                headers={"User-Agent": "VGC-MCP-Server/0.1.0"},
                limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
            )
        return self._client

    def _normalize_name(self, name: str, apply_form_aliases: bool = True) -> str:
        """Normalize Pokemon/move names for API.

        Examples:
            "Flutter Mane" -> "flutter-mane"
            "Urshifu-Rapid-Strike" -> "urshifu-rapid-strike"
            "King's Rock" -> "kings-rock"
            "Landorus" -> "landorus-incarnate" (with form aliases)
            "Mega Manectric" -> "manectric-mega"
            "Mega Charizard Y" -> "charizard-mega-y"

        Args:
            name: The name to normalize
            apply_form_aliases: If True, apply POKEAPI_FORM_ALIASES mapping
        """
        normalized = name.lower().replace(" ", "-").replace("'", "").replace("'", "")

        # Mega rewrite: PokeAPI keys are `<species>-mega` (e.g. `manectric-mega`)
        # but users commonly write "Mega Manectric" / "mega-manectric". Convert
        # leading `mega-<species>` to `<species>-mega`. Done before alias lookup
        # so explicit aliases (e.g. `mega-charizard-y` -> `charizard-mega-y`)
        # still take precedence.
        # The prefix is ALWAYS rewritten — there is no hardcoded "mega-capable"
        # allowlist (that omitted every Champions-era Mega). A genuine 404 from
        # PokeAPI is the "no such mega" signal.
        if apply_form_aliases and normalized.startswith("mega-"):
            normalized = reorder_mega_prefix(normalized)

        # Apply form aliases for Pokemon that need explicit form suffixes in PokeAPI
        if apply_form_aliases:
            normalized = POKEAPI_FORM_ALIASES.get(normalized, normalized)
        return normalized

    async def _fetch(self, endpoint: str) -> dict:
        """Fetch from API with caching, negative caching, and coalescing."""
        # Persistent (positive) cache first.
        cached = self.cache.get("pokeapi", endpoint)
        if cached is not None:
            return cached

        # Short-TTL negative cache: don't re-hit the API for a known-404 endpoint.
        neg_ts = self._negative_cache.get(endpoint)
        if neg_ts is not None:
            if asyncio.get_event_loop().time() - neg_ts < self.NEGATIVE_CACHE_TTL:
                raise PokeAPIError(f"Not found: {endpoint}")
            del self._negative_cache[endpoint]

        # In-flight coalescing: if an identical fetch is already running, await
        # the same task instead of issuing a second network request. Using a
        # shared Task means both owner and waiters retrieve its result/exception,
        # so there's no dangling future.
        existing = self._inflight.get(endpoint)
        if existing is not None:
            return await existing

        task: "asyncio.Task[dict]" = asyncio.ensure_future(self._do_fetch(endpoint))
        self._inflight[endpoint] = task
        try:
            return await task
        finally:
            self._inflight.pop(endpoint, None)

    async def _do_fetch(self, endpoint: str) -> dict:
        """Perform the actual HTTP fetch with retry logic."""
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
                    # Remember the 404 briefly so repeated unknown-form lookups
                    # short-circuit instead of re-hitting the API.
                    self._negative_cache[endpoint] = asyncio.get_event_loop().time()
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

    async def get_move(self, name_or_id: str | int, user_name: Optional[str] = None) -> Move:
        """Get move data.

        Args:
            name_or_id: Move name or ID
            user_name: Optional Pokemon name using the move. Used for form-dependent
                       move types like Ivy Cudgel (changes type based on Ogerpon form).
        """
        name = normalize_move(str(name_or_id))
        data = await self._fetch(f"move/{name}")

        target = data.get("target", {}).get("name", "selected-pokemon")

        # Determine if move makes contact. PokeAPI's REST endpoint doesn't
        # expose the contact flag, so resolve it from the curated table
        # (physical melee moves make contact; ranged/thrown ones don't).
        damage_class = data["damage_class"]["name"]
        makes_contact = move_makes_contact(data["name"], damage_class)

        # Get multi-hit info from our database (e.g., Surging Strikes: 3 hits, always crits)
        multi_hit_info = get_multi_hit_info(name)
        min_hits = 1
        max_hits = 1
        always_crit = False
        if multi_hit_info:
            min_hits, max_hits, always_crit = multi_hit_info

        # Also check for single-hit always-crit moves (e.g., Wicked Blow, Frost Breath)
        if not always_crit:
            always_crit = is_always_crit_move(name)

        # Determine move type (may vary by user form, e.g., Ivy Cudgel for Ogerpon)
        move_type = data["type"]["name"].capitalize()
        if user_name:
            move_type = get_move_type_for_user(name, user_name, move_type)

        # Get effect_chance from API, with fallback to our secondary effects database
        # This is critical for Sheer Force calculations - PokeAPI sometimes returns null
        effect_chance = data.get("effect_chance")
        if effect_chance is None:
            secondary_data = MOVE_SECONDARY_EFFECTS.get(name)
            if secondary_data:
                _, effect_chance = secondary_data

        return Move(
            name=data["name"],
            type=move_type,
            category=MoveCategory(data["damage_class"]["name"]),
            power=data.get("power"),
            accuracy=data.get("accuracy"),
            pp=data.get("pp", 5),
            priority=data.get("priority", 0),
            target=target,
            effect_chance=effect_chance,
            makes_contact=makes_contact,
            min_hits=min_hits,
            max_hits=max_hits,
            always_crit=always_crit
        )

    async def get_type(self, name: str) -> dict:
        """Get type data including damage relations."""
        name = self._normalize_name(name, apply_form_aliases=False)
        return await self._fetch(f"type/{name}")

    async def get_ability(self, name_or_id: str | int) -> dict:
        """Get ability data."""
        name = self._normalize_name(str(name_or_id), apply_form_aliases=False)
        return await self._fetch(f"ability/{name}")

    async def get_item(self, name_or_id: str | int) -> dict:
        """Get item data."""
        name = self._normalize_name(str(name_or_id), apply_form_aliases=False)
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
