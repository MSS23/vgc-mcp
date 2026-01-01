# api/ - External API Clients

Async HTTP clients for fetching Pokemon data from external sources.

## Files

| File | Purpose |
|------|---------|
| `cache.py` | Disk-based API response caching (using diskcache) |
| `pokeapi.py` | PokeAPI v2 client for Pokemon/move data |
| `smogon.py` | Smogon usage statistics (chaos.json format) |
| `pokepaste.py` | PokePaste URL fetching and parsing |

## APICache

Persistent disk cache to avoid repeated API calls:

```python
from vgc_mcp.api.cache import APICache

cache = APICache()  # Uses data/cache/ directory
cache.set("pokeapi", "pokemon/pikachu", data)
cached = cache.get("pokeapi", "pokemon/pikachu")
```

- Default TTL: 24 hours
- Location: `data/cache/`
- Shared between all API clients

## PokeAPIClient

Fetches Pokemon data from [PokeAPI](https://pokeapi.co/):

```python
from vgc_mcp.api.pokeapi import PokeAPIClient

pokeapi = PokeAPIClient(cache)

# Get base stats as BaseStats object
base_stats = await pokeapi.get_base_stats("flutter-mane")

# Get types as list of strings
types = await pokeapi.get_pokemon_types("incineroar")  # ["Fire", "Dark"]

# Get move data as Move object
move = await pokeapi.get_move("moonblast")

# Get abilities
abilities = await pokeapi.get_pokemon_abilities("dondozo")
```

### Name Normalization
Names are automatically normalized:
- "Flutter Mane" -> "flutter-mane"
- "King's Rock" -> "kings-rock"

## SmogonStatsClient

Fetches competitive usage data from Smogon:

```python
from vgc_mcp.api.smogon import SmogonStatsClient

smogon = SmogonStatsClient(cache)

# Get usage stats for a Pokemon
usage = await smogon.get_pokemon_usage("flutter-mane")
# Returns: {
#   "usage_percent": 45.2,
#   "abilities": {"Protosynthesis": 99.5},
#   "items": {"Choice Specs": 45.0, "Booster Energy": 40.0},
#   "moves": {"Moonblast": 95.0, "Shadow Ball": 90.0},
#   "spreads": [{"nature": "Modest", "evs": {...}, "usage": 25.0}],
#   "tera_types": {"Fairy": 60.0, "Stellar": 20.0}
# }

# Get common competitive sets
sets = await smogon.get_common_sets("incineroar")

# Get teammate suggestions
teammates = await smogon.suggest_teammates("flutter-mane")
```

### Auto-Detection
- Automatically finds the latest available month
- Tries multiple VGC formats (Reg G, Reg F, etc.)
- Uses 1760 rating by default (high-level play)

## PokePasteClient

Fetches and parses teams from PokePaste URLs:

```python
from vgc_mcp.api.pokepaste import PokePasteClient

pokepaste = PokePasteClient(cache)

# Fetch and parse a team
team = await pokepaste.fetch_paste("https://pokepast.es/abc123")
```

## Error Handling

All clients raise specific exceptions:
- `PokeAPIError` - Pokemon/move not found
- `SmogonStatsError` - No usage data available
- `PokePasteError` - Invalid paste URL

```python
try:
    stats = await pokeapi.get_base_stats("not-a-pokemon")
except PokeAPIError as e:
    print(f"Not found: {e}")
```
