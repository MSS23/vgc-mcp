# ui/ - MCP-UI Support

Interactive UI components for MCP clients that support MCP-UI (SEP-1865).

## Files

| File | Purpose |
|------|---------|
| `resources.py` | UI resource creation and metadata |
| `components.py` | Reusable UI component builders |
| `__init__.py` | Registration helper |

## Folder

| Folder | Purpose |
|--------|---------|
| `templates/` | HTML templates for UI components |

---

## Overview

MCP-UI enables rich interactive displays in supported clients (Goose Desktop, Claude Desktop extensions). Tools can return UI metadata that clients render as interactive widgets.

### How It Works

1. Tool returns normal response data
2. UI metadata is added pointing to a resource URI
3. Client fetches the resource and renders it
4. User can interact with the UI

---

## resources.py - UI Resource Creation

Create UI resources for different visualizations:

```python
from vgc_mcp.ui.resources import (
    create_damage_calc_resource,
    create_team_roster_resource,
    create_speed_tier_resource,
    create_coverage_resource,
    add_ui_metadata
)

# Create a damage calc UI
ui_resource = create_damage_calc_resource(
    attacker="Flutter Mane",
    defender="Incineroar",
    move="Moonblast",
    damage_range="85-101%",
    ko_chance="Guaranteed OHKO"
)

# Add to tool response
response = add_ui_metadata(response_dict, ui_resource)
```

### Available Resources

| Resource | Purpose |
|----------|---------|
| `damage_calc` | Damage calculation results |
| `team_roster` | 6-slot team display |
| `speed_tiers` | Speed tier visualization |
| `coverage` | Type coverage grid |

---

## components.py - Reusable Components

Build common UI elements:

```python
from vgc_mcp.ui.components import (
    pokemon_card,
    damage_bar,
    type_badge,
    stat_display
)

# Pokemon card HTML
card = pokemon_card(
    name="Flutter Mane",
    item="Choice Specs",
    ability="Protosynthesis",
    moves=["Moonblast", "Shadow Ball"]
)

# Damage bar with range
bar = damage_bar(min_percent=45, max_percent=55)
```

---

## templates/ - HTML Templates

Pre-built HTML/CSS templates:

```
templates/
├── damage_calc.html     # Damage calculator display
├── team_roster.html     # 6-slot team grid
├── speed_tiers.html     # Vertical speed chart
└── shared/
    ├── styles.css       # Common styles
    └── pokemon_card.html # Reusable card component
```

---

## Usage in Tools

```python
# In team_tools.py
from ..ui.resources import create_team_roster_resource, add_ui_metadata

@mcp.tool()
async def view_team():
    result = team_manager.get_team_summary()

    # Add UI for clients that support it
    try:
        if team_manager.size > 0:
            team_data = [pokemon_to_ui_dict(p) for p in team_manager.team]
            ui_resource = create_team_roster_resource(team=team_data)
            result = add_ui_metadata(result, ui_resource)
    except Exception:
        pass  # UI is optional enhancement

    return result
```

---

## Client Compatibility

| Client | MCP-UI Support |
|--------|----------------|
| Goose Desktop | Full support |
| Claude Desktop | Limited (extensions) |
| Other MCP clients | Text fallback |

Tools always return text responses. UI is an optional enhancement for supported clients.

---

## Registration

```python
# In server.py
from .ui import register_ui_resources

register_ui_resources(mcp)
```

This registers the `ui://` resource handlers with the MCP server.
