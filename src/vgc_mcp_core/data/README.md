# data/ - Static Data

Static data files for Pokemon, moves, and VGC rules.

## Files

This folder contains JSON/Python data files for:

- Restricted Pokemon lists by regulation
- Common VGC Pokemon for fuzzy matching
- Move databases for coverage analysis
- Type chart data

## Usage

Data is loaded at module import time and cached in memory.

```python
from vgc_mcp.data.restricted import RESTRICTED_POKEMON
from vgc_mcp.data.common_pokemon import COMMON_VGC_POKEMON
```

## Note

The `data/cache/` folder at the project root (not this folder) contains the disk cache for API responses. That cache is managed by `api/cache.py`.
