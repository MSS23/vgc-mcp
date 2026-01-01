# rules/ - VGC Format Rules

VGC format rules, regulations, and legality checking.

## Files

| File | Purpose |
|------|---------|
| `regulation_loader.py` | Load regulation configs (Reg G, Reg H, etc.) |
| `vgc_rules.py` | Core VGC rules and validation |
| `restricted.py` | Restricted Pokemon lists by regulation |
| `item_clause.py` | Item clause validation |

---

## regulation_loader.py

Load and manage VGC regulation configurations:

```python
from vgc_mcp.rules.regulation_loader import get_regulation_config, RegulationConfig

config = get_regulation_config()

# Current regulation info
config.current_regulation  # "G"
config.restricted_count    # 2 (max restricted per team)
config.get_all_smogon_formats()  # ["gen9vgc2025regg", ...]
```

### Regulation Configs
- **Reg G**: 2 restricted, standard ruleset
- **Reg H**: Future regulation settings
- Configures Smogon format strings for usage data

---

## vgc_rules.py

Core VGC rules validation:

```python
from vgc_mcp.rules.vgc_rules import (
    is_pokemon_banned,
    is_pokemon_restricted,
    validate_team_legality
)

# Check if Pokemon is banned
is_pokemon_banned("Mewtwo")  # True for most regulations

# Check if Pokemon is restricted
is_pokemon_restricted("Koraidon")  # True

# Full team validation
result = validate_team_legality(team)
# Returns: {
#   "valid": True/False,
#   "issues": ["Too many restricted Pokemon", ...],
#   "warnings": [...]
# }
```

---

## restricted.py

Restricted Pokemon by regulation:

```python
from vgc_mcp.rules.restricted import (
    RESTRICTED_POKEMON,
    get_restricted_for_regulation
)

# All restricted Pokemon
RESTRICTED_POKEMON  # ["Koraidon", "Miraidon", "Calyrex-Ice", ...]

# Get restricted for specific regulation
restricted = get_restricted_for_regulation("G")
```

### Restricted Pokemon Include:
- Box legendaries (Koraidon, Miraidon)
- Paradox legendaries (Walking Wake, Iron Leaves)
- Calyrex forms
- Terapagos (in some regulations)

---

## item_clause.py

Item clause validation (no duplicate items):

```python
from vgc_mcp.rules.item_clause import validate_item_clause

result = validate_item_clause(team)
# Returns: {
#   "valid": True/False,
#   "duplicate_items": ["Choice Scarf"] if any
# }
```

---

## Usage in Tools

```python
# In legality_tools.py
from ..rules.vgc_rules import validate_team_legality
from ..rules.restricted import is_pokemon_restricted

@mcp.tool()
async def check_team_legality():
    result = validate_team_legality(team_manager.team)
    return result
```
