"""Team state management with VGC rules and Pokemon context persistence."""

from typing import Optional

from ..models.pokemon import PokemonBuild
from ..models.team import Team, TeamSlot


class TeamManager:
    """Manages team state with VGC rule validation and context persistence.

    The context system allows storing Pokemon builds for reference in
    subsequent calculations. For example, after setting "my Entei" with
    a specific spread, future queries can reference "my Entei" to use
    that stored build.
    """

    def __init__(self):
        """Initialize with an empty team and context storage."""
        self._team = Team()
        # Context storage for "my Pokemon" references
        self._pokemon_context: dict[str, PokemonBuild] = {}
        # Track the most recently referenced Pokemon
        self._active_pokemon: Optional[str] = None

    def get_current_team(self) -> Optional[Team]:
        """Get the current team (for tool access)."""
        return self._team if self._team.size > 0 else None

    @property
    def team(self) -> Team:
        """Get the current team."""
        return self._team

    @property
    def size(self) -> int:
        """Get number of Pokemon on team."""
        return self._team.size

    @property
    def is_full(self) -> bool:
        """Check if team has 6 Pokemon."""
        return self._team.is_full

    def add_pokemon(self, pokemon: PokemonBuild) -> tuple[bool, str, dict]:
        """
        Add a Pokemon to the team.

        Args:
            pokemon: The Pokemon build to add

        Returns:
            Tuple of (success, message, data)
        """
        can_add, reason = self._team.can_add(pokemon)

        if not can_add:
            if self.is_full:
                return False, reason, {
                    "error": "team_full",
                    "current_team": self._team.get_pokemon_names(),
                    "suggestion": "Use swap_pokemon to replace one, or remove_pokemon first"
                }
            else:
                return False, reason, {
                    "error": "species_clause",
                    "current_team": self._team.get_pokemon_names()
                }

        # Add to team
        slot = TeamSlot(pokemon=pokemon, slot_index=self.size)
        self._team.slots.append(slot)

        return True, f"Added {pokemon.name} to slot {slot.slot_index + 1}", {
            "slot": slot.slot_index + 1,
            "team_size": self.size,
            "team": self._team.get_pokemon_names()
        }

    def remove_pokemon(self, slot_index: int) -> tuple[bool, str, dict]:
        """
        Remove a Pokemon by slot index (0-based internally, 1-based for users).

        Args:
            slot_index: Slot index (0-5)

        Returns:
            Tuple of (success, message, data)
        """
        if slot_index < 0 or slot_index >= self.size:
            return False, f"Invalid slot index: {slot_index + 1}", {
                "error": "invalid_slot",
                "valid_slots": list(range(1, self.size + 1))
            }

        removed = self._team.slots.pop(slot_index)

        # Re-index remaining slots
        for i, slot in enumerate(self._team.slots):
            slot.slot_index = i

        return True, f"Removed {removed.pokemon.name} from team", {
            "removed": removed.pokemon.name,
            "team_size": self.size,
            "team": self._team.get_pokemon_names()
        }

    def remove_by_name(self, name: str) -> tuple[bool, str, dict]:
        """
        Remove a Pokemon by name.

        Args:
            name: Pokemon name to remove

        Returns:
            Tuple of (success, message, data)
        """
        name_lower = name.lower()
        for i, slot in enumerate(self._team.slots):
            if slot.pokemon.name.lower() == name_lower:
                return self.remove_pokemon(i)

        return False, f"{name} not found on team", {
            "error": "not_found",
            "team": self._team.get_pokemon_names()
        }

    def swap_pokemon(
        self,
        slot_index: int,
        new_pokemon: PokemonBuild
    ) -> tuple[bool, str, dict]:
        """
        Replace a Pokemon in a slot with a new one.

        Args:
            slot_index: Slot to replace (0-5)
            new_pokemon: New Pokemon to add

        Returns:
            Tuple of (success, message, data)
        """
        if slot_index < 0 or slot_index >= self.size:
            return False, f"Invalid slot index: {slot_index + 1}", {
                "error": "invalid_slot"
            }

        # Check species clause (excluding the slot we're replacing)
        new_species = new_pokemon.species.lower()
        for i, slot in enumerate(self._team.slots):
            if i != slot_index and slot.pokemon.species.lower() == new_species:
                return False, f"Species Clause: {new_pokemon.species} already on team", {
                    "error": "species_clause"
                }

        old_pokemon = self._team.slots[slot_index].pokemon
        self._team.slots[slot_index].pokemon = new_pokemon

        return True, f"Replaced {old_pokemon.name} with {new_pokemon.name}", {
            "removed": old_pokemon.name,
            "added": new_pokemon.name,
            "slot": slot_index + 1,
            "team": self._team.get_pokemon_names()
        }

    def update_pokemon(
        self,
        slot_index: int,
        **updates
    ) -> tuple[bool, str, dict]:
        """
        Update a Pokemon's configuration.

        Args:
            slot_index: Slot to update (0-5)
            **updates: Fields to update (nature, evs, item, moves, etc.)

        Returns:
            Tuple of (success, message, data)
        """
        if slot_index < 0 or slot_index >= self.size:
            return False, f"Invalid slot index: {slot_index + 1}", {
                "error": "invalid_slot"
            }

        pokemon = self._team.slots[slot_index].pokemon
        updated_fields = []

        for key, value in updates.items():
            if hasattr(pokemon, key) and value is not None:
                setattr(pokemon, key, value)
                updated_fields.append(key)

        if updated_fields:
            return True, f"Updated {pokemon.name}: {', '.join(updated_fields)}", {
                "pokemon": pokemon.name,
                "updated": updated_fields
            }
        else:
            return False, "No valid fields to update", {
                "error": "no_updates"
            }

    def reorder(self, slot1: int, slot2: int) -> tuple[bool, str, dict]:
        """
        Swap positions of two Pokemon.

        Args:
            slot1: First slot index (0-5)
            slot2: Second slot index (0-5)

        Returns:
            Tuple of (success, message, data)
        """
        if not (0 <= slot1 < self.size and 0 <= slot2 < self.size):
            return False, "Invalid slot indices", {
                "error": "invalid_slots",
                "valid_slots": list(range(1, self.size + 1))
            }

        if slot1 == slot2:
            return False, "Cannot swap a slot with itself", {
                "error": "same_slot"
            }

        # Swap
        self._team.slots[slot1], self._team.slots[slot2] = \
            self._team.slots[slot2], self._team.slots[slot1]

        # Update indices
        self._team.slots[slot1].slot_index = slot1
        self._team.slots[slot2].slot_index = slot2

        return True, f"Swapped slots {slot1 + 1} and {slot2 + 1}", {
            "team": self._team.get_pokemon_names()
        }

    def clear(self) -> tuple[bool, str, dict]:
        """
        Clear all Pokemon from the team.

        Returns:
            Tuple of (success, message, data)
        """
        count = self.size
        self._team = Team()
        return True, f"Cleared {count} Pokemon from team", {
            "removed_count": count
        }

    def get_pokemon(self, slot_index: int) -> Optional[PokemonBuild]:
        """Get Pokemon at a slot."""
        return self._team.get_by_slot(slot_index)

    def get_pokemon_by_name(self, name: str) -> Optional[PokemonBuild]:
        """Get Pokemon by name."""
        return self._team.get_by_name(name)

    def get_team_summary(self) -> dict:
        """Get a summary of the current team."""
        pokemon_list = []
        for slot in self._team.slots:
            p = slot.pokemon
            pokemon_list.append({
                "slot": slot.slot_index + 1,
                "name": p.name,
                "types": p.types,
                "ability": p.ability,
                "item": p.item,
                "tera_type": p.tera_type,
                "nature": p.nature.value,
                "evs": {
                    "hp": p.evs.hp,
                    "attack": p.evs.attack,
                    "defense": p.evs.defense,
                    "special_attack": p.evs.special_attack,
                    "special_defense": p.evs.special_defense,
                    "speed": p.evs.speed,
                },
                "moves": p.moves
            })

        return {
            "name": self._team.name,
            "size": self.size,
            "slots_remaining": 6 - self.size,
            "pokemon": pokemon_list
        }

    # ==========================================================================
    # Pokemon Context Management (for "my Pokemon" references)
    # ==========================================================================

    def set_pokemon_context(
        self,
        reference: str,
        pokemon: PokemonBuild
    ) -> tuple[bool, str]:
        """
        Store a Pokemon build for future reference.

        Allows users to say "my Entei" and have it refer to a specific
        build with predetermined stats, nature, EVs, etc.

        Args:
            reference: Reference name (e.g., "entei", "my entei")
            pokemon: The Pokemon build to store

        Returns:
            Tuple of (success, message)
        """
        # Normalize the reference name
        key = self._normalize_context_key(reference)

        self._pokemon_context[key] = pokemon
        self._active_pokemon = key

        return True, f"Stored {pokemon.name} as '{reference}'"

    def get_pokemon_context(
        self,
        reference: Optional[str] = None
    ) -> Optional[PokemonBuild]:
        """
        Get a stored Pokemon by reference.

        Handles various input formats:
        - "my entei", "my Entei" -> looks up "entei"
        - "the entei" -> looks up "entei"
        - "entei" -> looks up "entei"
        - None or empty -> returns most recently used Pokemon

        Args:
            reference: Reference name, or None for most recent

        Returns:
            The stored PokemonBuild or None if not found
        """
        if not reference:
            # Return most recently used Pokemon
            if self._active_pokemon:
                return self._pokemon_context.get(self._active_pokemon)
            return None

        key = self._normalize_context_key(reference)

        if key in self._pokemon_context:
            self._active_pokemon = key
            return self._pokemon_context[key]

        return None

    def _normalize_context_key(self, reference: str) -> str:
        """
        Normalize a reference string to a context key.

        Handles prefixes like "my", "the", "that", etc.
        """
        reference = reference.lower().strip()

        # Remove common prefixes
        prefixes = ["my ", "the ", "that ", "this "]
        for prefix in prefixes:
            if reference.startswith(prefix):
                reference = reference[len(prefix):]
                break

        # Normalize Pokemon name format
        reference = reference.replace(" ", "-")

        return reference

    def list_pokemon_context(self) -> list[dict]:
        """
        List all stored Pokemon contexts.

        Returns:
            List of stored Pokemon with their reference names and key stats
        """
        result = []
        for key, pokemon in self._pokemon_context.items():
            result.append({
                "reference": key,
                "name": pokemon.name,
                "nature": pokemon.nature.value,
                "evs": {
                    "hp": pokemon.evs.hp,
                    "attack": pokemon.evs.attack,
                    "defense": pokemon.evs.defense,
                    "special_attack": pokemon.evs.special_attack,
                    "special_defense": pokemon.evs.special_defense,
                    "speed": pokemon.evs.speed,
                },
                "is_active": key == self._active_pokemon
            })
        return result

    def clear_pokemon_context(self, reference: Optional[str] = None) -> tuple[bool, str]:
        """
        Clear stored Pokemon context(s).

        Args:
            reference: Specific reference to clear, or None to clear all

        Returns:
            Tuple of (success, message)
        """
        if reference:
            key = self._normalize_context_key(reference)
            if key in self._pokemon_context:
                del self._pokemon_context[key]
                if self._active_pokemon == key:
                    self._active_pokemon = None
                return True, f"Cleared context for '{reference}'"
            return False, f"No context found for '{reference}'"
        else:
            count = len(self._pokemon_context)
            self._pokemon_context.clear()
            self._active_pokemon = None
            return True, f"Cleared {count} stored Pokemon"

    def get_active_pokemon(self) -> Optional[PokemonBuild]:
        """Get the most recently referenced Pokemon."""
        if self._active_pokemon:
            return self._pokemon_context.get(self._active_pokemon)
        return None

    @property
    def active_pokemon_name(self) -> Optional[str]:
        """Get the name of the most recently referenced Pokemon."""
        return self._active_pokemon
