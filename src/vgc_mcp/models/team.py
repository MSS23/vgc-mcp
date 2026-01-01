"""Team data models with VGC validation."""

from typing import Optional
from pydantic import BaseModel, Field, model_validator

from .pokemon import PokemonBuild


class TeamSlot(BaseModel):
    """A slot in the team containing a Pokemon build."""
    pokemon: PokemonBuild
    slot_index: int = Field(ge=0, le=5)


class Team(BaseModel):
    """VGC Team - Bring 6, Pick 4."""
    name: str = "My Team"
    slots: list[TeamSlot] = Field(default_factory=list, max_length=6)

    @model_validator(mode="after")
    def validate_species_clause(self) -> "Team":
        """Enforce species clause - no duplicate base species."""
        species_list = [slot.pokemon.species.lower() for slot in self.slots]
        if len(species_list) != len(set(species_list)):
            # Find the duplicate
            seen = set()
            for species in species_list:
                if species in seen:
                    raise ValueError(f"Species Clause violation: duplicate {species}")
                seen.add(species)
        return self

    @property
    def size(self) -> int:
        """Number of Pokemon on the team."""
        return len(self.slots)

    @property
    def is_full(self) -> bool:
        """Check if team has 6 Pokemon."""
        return self.size >= 6

    def can_add(self, pokemon: PokemonBuild) -> tuple[bool, str]:
        """Check if a Pokemon can be added to the team."""
        if self.is_full:
            return False, "Team is full (max 6 Pokemon)"

        # Check species clause
        species = pokemon.species.lower()
        for slot in self.slots:
            if slot.pokemon.species.lower() == species:
                return False, f"Species Clause: {pokemon.species} already on team as {slot.pokemon.name}"

        return True, "OK"

    def get_pokemon_names(self) -> list[str]:
        """Get list of Pokemon names on the team."""
        return [slot.pokemon.name for slot in self.slots]

    def get_by_name(self, name: str) -> Optional[PokemonBuild]:
        """Get Pokemon by name."""
        name_lower = name.lower()
        for slot in self.slots:
            if slot.pokemon.name.lower() == name_lower:
                return slot.pokemon
        return None

    def get_by_slot(self, slot_index: int) -> Optional[PokemonBuild]:
        """Get Pokemon by slot index (0-5)."""
        if 0 <= slot_index < self.size:
            return self.slots[slot_index].pokemon
        return None

    @property
    def pokemon(self) -> list[PokemonBuild]:
        """Get list of all Pokemon on the team."""
        return [slot.pokemon for slot in self.slots]

    def add_pokemon(self, pokemon: PokemonBuild) -> bool:
        """
        Add a Pokemon to the team.

        Args:
            pokemon: The Pokemon to add

        Returns:
            True if added successfully, False if team is full or species clause violated
        """
        can_add, reason = self.can_add(pokemon)
        if not can_add:
            return False

        slot_index = self.size
        self.slots.append(TeamSlot(pokemon=pokemon, slot_index=slot_index))
        return True

    def remove_pokemon(self, name: str) -> bool:
        """
        Remove a Pokemon from the team by name.

        Args:
            name: Name of the Pokemon to remove

        Returns:
            True if removed, False if not found
        """
        name_lower = name.lower()
        for i, slot in enumerate(self.slots):
            if slot.pokemon.name.lower() == name_lower:
                self.slots.pop(i)
                # Re-index remaining slots
                for j, s in enumerate(self.slots):
                    s.slot_index = j
                return True
        return False

    def clear(self) -> None:
        """Remove all Pokemon from the team."""
        self.slots.clear()
