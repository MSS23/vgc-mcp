# formats/ - Import/Export Formats

Parsing and generating Pokemon team formats.

## Files

| File | Purpose |
|------|---------|
| `showdown.py` | Pokemon Showdown paste format |

---

## showdown.py - Showdown Paste Format

Parse and generate Pokemon Showdown paste format:

### Parsing

```python
from vgc_mcp.formats.showdown import parse_showdown_pokemon, parse_showdown_team

# Parse single Pokemon
pokemon = parse_showdown_pokemon("""
Flutter Mane @ Choice Specs
Ability: Protosynthesis
Level: 50
Tera Type: Fairy
EVs: 252 SpA / 4 SpD / 252 Spe
Timid Nature
- Moonblast
- Shadow Ball
- Dazzling Gleam
- Protect
""")

# Returns dict with:
# {
#   "name": "Flutter Mane",
#   "item": "Choice Specs",
#   "ability": "Protosynthesis",
#   "level": 50,
#   "tera_type": "Fairy",
#   "evs": {"special_attack": 252, "special_defense": 4, "speed": 252},
#   "nature": "Timid",
#   "moves": ["Moonblast", "Shadow Ball", "Dazzling Gleam", "Protect"]
# }

# Parse full team (6 Pokemon separated by blank lines)
team = parse_showdown_team(paste_text)
# Returns list of parsed Pokemon dicts
```

### Generating

```python
from vgc_mcp.formats.showdown import export_pokemon, export_team

# Export single Pokemon to paste
paste = export_pokemon(pokemon_build)

# Export full team
team_paste = export_team(team_list)
```

### Paste Format

```
Pokemon Name (Nickname) @ Item
Ability: Ability Name
Level: 50
Shiny: Yes
Tera Type: Type
EVs: HP / Atk / Def / SpA / SpD / Spe
Nature Nature
IVs: 0 Atk
- Move 1
- Move 2
- Move 3
- Move 4

```

### Supported Features
- Nicknames: `Flutter Mane (Fluffy)`
- Gender: `Incineroar (M)` or `(F)`
- Shiny status
- Custom IVs: `IVs: 0 Atk` (for Foul Play protection)
- Tera Type
- All 25 natures

### Error Handling

```python
from vgc_mcp.formats.showdown import ShowdownParseError

try:
    pokemon = parse_showdown_pokemon(invalid_paste)
except ShowdownParseError as e:
    print(f"Parse error: {e}")
```
