"""Data models for team diff functionality."""

from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class ChangeType(str, Enum):
    """Type of change detected for a Pokemon."""
    ADDED = "added"       # Pokemon in v2 not in v1
    REMOVED = "removed"   # Pokemon in v1 not in v2
    MODIFIED = "modified" # Pokemon in both, but with differences


class FieldType(str, Enum):
    """What field changed on a Pokemon."""
    EVS = "evs"
    IVS = "ivs"
    NATURE = "nature"
    ITEM = "item"
    ABILITY = "ability"
    TERA_TYPE = "tera_type"
    MOVES = "moves"
    LEVEL = "level"


@dataclass
class StatChange:
    """A single stat change (for EVs/IVs)."""
    stat: str       # "hp", "atk", "def", "spa", "spd", "spe"
    before: int
    after: int

    @property
    def delta(self) -> int:
        """Difference between after and before values."""
        return self.after - self.before


@dataclass
class MoveChange:
    """Changes to moveset."""
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    @property
    def has_changes(self) -> bool:
        return bool(self.added or self.removed)


@dataclass
class FieldChange:
    """A single field change on a Pokemon."""
    field: FieldType
    before: Any
    after: Any
    reason: str = ""  # Pattern-based explanation

    # Optional detailed changes for complex fields
    stat_changes: Optional[list[StatChange]] = None  # For EV/IV changes
    move_changes: Optional[MoveChange] = None        # For move changes

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "field": self.field.value,
            "before": self.before,
            "after": self.after,
            "reason": self.reason,
        }
        if self.stat_changes:
            result["stat_changes"] = [
                {"stat": sc.stat, "before": sc.before, "after": sc.after, "delta": sc.delta}
                for sc in self.stat_changes
            ]
        if self.move_changes:
            result["move_changes"] = {
                "added": self.move_changes.added,
                "removed": self.move_changes.removed,
            }
        return result


@dataclass
class PokemonDiff:
    """Diff result for a single Pokemon."""
    species: str
    change_type: ChangeType
    changes: list[FieldChange] = field(default_factory=list)

    # Store full pokemon data for added/removed display
    pokemon_data: Optional[dict] = None

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        result = {
            "species": self.species,
            "change_type": self.change_type.value,
            "changes": [c.to_dict() for c in self.changes],
        }
        if self.pokemon_data:
            result["pokemon_data"] = self.pokemon_data
        return result


@dataclass
class TeamDiff:
    """Complete diff between two team versions."""
    version1_name: str
    version2_name: str
    pokemon_diffs: list[PokemonDiff] = field(default_factory=list)

    # Unchanged Pokemon (for display)
    unchanged: list[str] = field(default_factory=list)

    @property
    def summary(self) -> dict:
        """Generate summary statistics."""
        added = [d for d in self.pokemon_diffs if d.change_type == ChangeType.ADDED]
        removed = [d for d in self.pokemon_diffs if d.change_type == ChangeType.REMOVED]
        modified = [d for d in self.pokemon_diffs if d.change_type == ChangeType.MODIFIED]

        # Count field changes
        field_counts: dict[str, int] = {}
        for diff in modified:
            for change in diff.changes:
                field_counts[change.field.value] = field_counts.get(change.field.value, 0) + 1

        return {
            "total_pokemon_changed": len(self.pokemon_diffs),
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
            "unchanged": len(self.unchanged),
            "field_changes": field_counts,
            "total_field_changes": sum(len(d.changes) for d in modified),
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "version1_name": self.version1_name,
            "version2_name": self.version2_name,
            "summary": self.summary,
            "added": [d.to_dict() for d in self.pokemon_diffs if d.change_type == ChangeType.ADDED],
            "removed": [d.to_dict() for d in self.pokemon_diffs if d.change_type == ChangeType.REMOVED],
            "modified": [d.to_dict() for d in self.pokemon_diffs if d.change_type == ChangeType.MODIFIED],
            "unchanged": self.unchanged,
        }
