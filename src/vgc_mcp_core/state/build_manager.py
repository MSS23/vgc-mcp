# -*- coding: utf-8 -*-
"""Build state manager for bidirectional UI sync.

Manages active Pokemon builds so that:
1. UI changes can be tracked via auto-save
2. Chat commands can modify builds by Pokemon name
3. State persists across tool calls within a session
"""

from typing import Any, Optional
from difflib import SequenceMatcher


class BuildStateManager:
    """Manages active Pokemon builds for bidirectional UI sync.

    Builds are stored by unique ID but can be looked up by Pokemon name.
    The most recently created/modified build is tracked as "active".
    """

    def __init__(self):
        self._builds: dict[str, dict] = {}  # build_id -> full state
        self._name_to_id: dict[str, str] = {}  # lowercase pokemon name -> build_id
        self._active_build_id: Optional[str] = None
        self._counter = 0

    def create_build(self, pokemon_data: dict) -> str:
        """Create a new build and return its unique ID.

        Args:
            pokemon_data: Dict with pokemon name, base_stats, types, evs, etc.

        Returns:
            Unique build ID (e.g., "build_0", "build_1")
        """
        pokemon_name = pokemon_data.get("name", "Unknown")
        build_id = f"build_{self._counter}"
        self._counter += 1

        self._builds[build_id] = {
            "build_id": build_id,
            "pokemon": pokemon_name,
            "base_stats": pokemon_data.get("base_stats", {}),
            "types": pokemon_data.get("types", []),
            "evs": pokemon_data.get("evs", {
                "hp": 0, "attack": 0, "defense": 0,
                "special_attack": 0, "special_defense": 0, "speed": 0
            }),
            "ivs": pokemon_data.get("ivs", {
                "hp": 31, "attack": 31, "defense": 31,
                "special_attack": 31, "special_defense": 31, "speed": 31
            }),
            "nature": pokemon_data.get("nature", "Serious"),
            "ability": pokemon_data.get("ability"),
            "item": pokemon_data.get("item"),
            "tera_type": pokemon_data.get("tera_type"),
            "moves": pokemon_data.get("moves", []),
            "abilities": pokemon_data.get("abilities", []),  # Available abilities
            "all_moves": pokemon_data.get("all_moves", []),  # Available moves
        }

        # Track name -> id mapping (lowercase for fuzzy matching)
        self._name_to_id[pokemon_name.lower()] = build_id
        self._active_build_id = build_id

        return build_id

    def get_build(self, build_id: str) -> Optional[dict]:
        """Get a build by its ID.

        Args:
            build_id: The unique build identifier

        Returns:
            Build dict or None if not found
        """
        return self._builds.get(build_id)

    def get_build_by_name(self, pokemon_name: str) -> Optional[dict]:
        """Get a build by Pokemon name (fuzzy matching).

        Args:
            pokemon_name: Pokemon name to search for (case-insensitive)

        Returns:
            Build dict or None if not found
        """
        name_lower = pokemon_name.lower()

        # Exact match first
        if name_lower in self._name_to_id:
            return self._builds.get(self._name_to_id[name_lower])

        # Fuzzy match - find best match above 0.6 threshold
        best_match = None
        best_ratio = 0.6

        for stored_name, build_id in self._name_to_id.items():
            ratio = SequenceMatcher(None, name_lower, stored_name).ratio()
            if ratio > best_ratio:
                best_ratio = ratio
                best_match = build_id

        if best_match:
            return self._builds.get(best_match)

        return None

    def get_active_build(self) -> Optional[dict]:
        """Get the most recently created/modified build.

        Returns:
            Active build dict or None if no builds exist
        """
        if self._active_build_id:
            return self._builds.get(self._active_build_id)
        return None

    def update_build(self, build_id: str, changes: dict) -> tuple[bool, str]:
        """Update a build with the given changes.

        Args:
            build_id: The build to update
            changes: Dict of field -> value changes

        Returns:
            Tuple of (success, message)
        """
        if build_id not in self._builds:
            return False, f"Build {build_id} not found"

        build = self._builds[build_id]

        for field, value in changes.items():
            if field in ["evs", "ivs"] and isinstance(value, dict):
                # Merge nested dict updates
                build[field].update(value)
            elif field == "moves" and isinstance(value, list):
                # Replace moves list entirely
                build["moves"] = value[:4]  # Max 4 moves
            else:
                build[field] = value

        self._active_build_id = build_id
        return True, f"Updated {', '.join(changes.keys())}"

    def update_build_by_name(self, pokemon_name: str, changes: dict) -> tuple[bool, str, Optional[str]]:
        """Update a build by Pokemon name.

        Args:
            pokemon_name: Pokemon name to find
            changes: Dict of changes to apply

        Returns:
            Tuple of (success, message, build_id)
        """
        build = self.get_build_by_name(pokemon_name)
        if not build:
            return False, f"No build found for '{pokemon_name}'", None

        build_id = build["build_id"]
        success, message = self.update_build(build_id, changes)
        return success, message, build_id

    def sync_from_ui(self, build_id: str, ui_state: dict) -> tuple[bool, str]:
        """Sync UI state back to server.

        Called when user makes changes via UI sliders/dropdowns and then
        sends a chat message. The UI state is captured and merged.

        Args:
            build_id: The build to sync
            ui_state: Serialized state from UI (evs, nature, moves, etc.)

        Returns:
            Tuple of (success, message)
        """
        if build_id not in self._builds:
            return False, f"Build {build_id} not found"

        build = self._builds[build_id]

        # Merge UI state - UI takes precedence for these fields
        if "evs" in ui_state:
            build["evs"].update(ui_state["evs"])
        if "nature" in ui_state:
            build["nature"] = ui_state["nature"]
        if "ability" in ui_state:
            build["ability"] = ui_state["ability"]
        if "item" in ui_state:
            build["item"] = ui_state["item"]
        if "tera_type" in ui_state:
            build["tera_type"] = ui_state["tera_type"]
        if "moves" in ui_state:
            build["moves"] = ui_state["moves"][:4]

        self._active_build_id = build_id
        return True, "Synced UI state"

    def change_move(self, build_id: str, old_move: str, new_move: str) -> tuple[bool, str]:
        """Change a specific move on a build.

        Args:
            build_id: The build to modify
            old_move: Move to replace (case-insensitive)
            new_move: New move to use

        Returns:
            Tuple of (success, message)
        """
        if build_id not in self._builds:
            return False, f"Build {build_id} not found"

        moves = self._builds[build_id]["moves"]
        old_lower = old_move.lower()

        for i, move in enumerate(moves):
            if move.lower() == old_lower:
                moves[i] = new_move
                self._active_build_id = build_id
                return True, f"Changed {old_move} to {new_move}"

        return False, f"Move '{old_move}' not found in moveset"

    def list_builds(self) -> list[dict]:
        """List all active builds.

        Returns:
            List of build summaries (id, pokemon name, item)
        """
        return [
            {
                "build_id": b["build_id"],
                "pokemon": b["pokemon"],
                "item": b.get("item", "None"),
                "nature": b.get("nature", "Serious"),
            }
            for b in self._builds.values()
        ]

    def delete_build(self, build_id: str) -> bool:
        """Delete a build by ID.

        Args:
            build_id: The build to delete

        Returns:
            True if deleted, False if not found
        """
        if build_id not in self._builds:
            return False

        build = self._builds[build_id]
        pokemon_name = build["pokemon"].lower()

        # Remove from name mapping
        if self._name_to_id.get(pokemon_name) == build_id:
            del self._name_to_id[pokemon_name]

        # Remove build
        del self._builds[build_id]

        # Update active if needed
        if self._active_build_id == build_id:
            self._active_build_id = next(iter(self._builds), None)

        return True

    @property
    def active_pokemon_name(self) -> Optional[str]:
        """Get the name of the active Pokemon build."""
        build = self.get_active_build()
        return build["pokemon"] if build else None

    @property
    def active_build_id(self) -> Optional[str]:
        """Get the ID of the active build."""
        return self._active_build_id

    def __len__(self) -> int:
        """Number of active builds."""
        return len(self._builds)
