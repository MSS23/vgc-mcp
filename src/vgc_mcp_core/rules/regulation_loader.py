"""Unified VGC regulation configuration loader.

This module provides a single source of truth for all VGC regulation data,
loading from an external JSON file that can be updated without code changes.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional


class RegulationConfig:
    """Loads and manages VGC regulation configuration from JSON."""

    def __init__(self, config_path: Optional[Path] = None):
        """
        Initialize the regulation configuration.

        Args:
            config_path: Path to regulations.json. If None, uses default location.
        """
        if config_path is None:
            config_path = Path(__file__).parent.parent / "data" / "regulations.json"
        self._config_path = config_path
        self._data: dict = {}
        self._session_override: Optional[str] = None
        self._load_config()

    def _load_config(self) -> None:
        """Load configuration from JSON file."""
        try:
            with open(self._config_path, "r", encoding="utf-8") as f:
                self._data = json.load(f)
        except FileNotFoundError:
            # Fallback to minimal default if file not found
            self._data = {
                "current_regulation": "reg_f",
                "regulations": {
                    "reg_f": {
                        "name": "Regulation F",
                        "smogon_formats": ["gen9vgc2026regfbo3", "gen9vgc2026regf"],
                        "restricted_limit": 2,
                        "item_clause": True,
                        "species_clause": True,
                        "level": 50,
                        "pokemon_limit": 6,
                        "bring_limit": 4,
                        "restricted_pokemon": [],
                        "banned_pokemon": [],
                    }
                }
            }

    def reload(self) -> None:
        """Reload configuration from file (useful for testing or hot-reloading)."""
        self._load_config()

    @property
    def current_regulation(self) -> str:
        """
        Get current regulation code.

        Priority:
        1. Session override (set via set_session_regulation)
        2. Explicit current_regulation in JSON
        3. Auto-detect based on date ranges
        4. First regulation in list
        """
        # Session override takes priority
        if self._session_override:
            return self._session_override

        # Check for explicit current_regulation in JSON
        if self._data.get("current_regulation"):
            return self._data["current_regulation"]

        # Auto-detect based on date ranges
        today = datetime.now().date()
        for reg_code, reg_data in self._data.get("regulations", {}).items():
            start_str = reg_data.get("start_date")
            end_str = reg_data.get("end_date")

            if start_str and end_str:
                try:
                    start = datetime.strptime(start_str, "%Y-%m-%d").date()
                    end = datetime.strptime(end_str, "%Y-%m-%d").date()
                    if start <= today <= end:
                        return reg_code
                except ValueError:
                    continue

        # Default to first regulation
        regulations = list(self._data.get("regulations", {}).keys())
        return regulations[0] if regulations else "reg_f"

    def set_session_regulation(self, regulation: str) -> bool:
        """
        Override current regulation for this session.

        Args:
            regulation: Regulation code (e.g., "reg_f", "reg_g")

        Returns:
            True if valid regulation, False otherwise
        """
        if regulation in self._data.get("regulations", {}):
            self._session_override = regulation
            return True
        return False

    def clear_session_override(self) -> None:
        """Clear session regulation override, reverting to default detection."""
        self._session_override = None

    def get_regulation(self, regulation: Optional[str] = None) -> dict:
        """
        Get full regulation data.

        Args:
            regulation: Regulation code. Uses current if None.

        Returns:
            Full regulation dictionary with all fields
        """
        reg = regulation or self.current_regulation
        return self._data.get("regulations", {}).get(reg, {})

    def get_smogon_formats(self, regulation: Optional[str] = None) -> list[str]:
        """
        Get Smogon format strings for a regulation.

        Args:
            regulation: Regulation code. Uses current if None.

        Returns:
            List of Smogon format strings (e.g., ["gen9vgc2026regfbo3"])
        """
        reg_data = self.get_regulation(regulation)
        return reg_data.get("smogon_formats", [])

    def get_all_smogon_formats(self) -> list[str]:
        """
        Get all Smogon format strings from all regulations.

        Returns:
            Deduplicated list of all format strings, current regulation first
        """
        formats = []
        seen = set()

        # Add current regulation formats first
        for fmt in self.get_smogon_formats():
            if fmt not in seen:
                formats.append(fmt)
                seen.add(fmt)

        # Add formats from other regulations
        for reg_code in self._data.get("regulations", {}):
            for fmt in self.get_smogon_formats(reg_code):
                if fmt not in seen:
                    formats.append(fmt)
                    seen.add(fmt)

        return formats

    def get_restricted_pokemon(self, regulation: Optional[str] = None) -> set[str]:
        """
        Get restricted Pokemon for a regulation.

        Args:
            regulation: Regulation code. Uses current if None.

        Returns:
            Set of restricted Pokemon names (lowercase, hyphenated)
        """
        reg_data = self.get_regulation(regulation)
        return set(reg_data.get("restricted_pokemon", []))

    def get_banned_pokemon(self, regulation: Optional[str] = None) -> set[str]:
        """
        Get banned (mythical) Pokemon for a regulation.

        Args:
            regulation: Regulation code. Uses current if None.

        Returns:
            Set of banned Pokemon names (lowercase, hyphenated)
        """
        reg_data = self.get_regulation(regulation)
        return set(reg_data.get("banned_pokemon", []))

    def get_restricted_limit(self, regulation: Optional[str] = None) -> int:
        """
        Get maximum number of restricted Pokemon allowed.

        Args:
            regulation: Regulation code. Uses current if None.

        Returns:
            Number of restricted Pokemon allowed (0, 1, or 2)
        """
        reg_data = self.get_regulation(regulation)
        return reg_data.get("restricted_limit", 2)

    def is_item_clause_active(self, regulation: Optional[str] = None) -> bool:
        """Check if item clause is active for a regulation."""
        reg_data = self.get_regulation(regulation)
        return reg_data.get("item_clause", True)

    def is_species_clause_active(self, regulation: Optional[str] = None) -> bool:
        """Check if species clause is active for a regulation."""
        reg_data = self.get_regulation(regulation)
        return reg_data.get("species_clause", True)

    def get_level(self, regulation: Optional[str] = None) -> int:
        """Get battle level for a regulation (usually 50)."""
        reg_data = self.get_regulation(regulation)
        return reg_data.get("level", 50)

    def get_pokemon_limit(self, regulation: Optional[str] = None) -> int:
        """Get team size limit (usually 6)."""
        reg_data = self.get_regulation(regulation)
        return reg_data.get("pokemon_limit", 6)

    def get_bring_limit(self, regulation: Optional[str] = None) -> int:
        """Get number of Pokemon you can bring to battle (usually 4)."""
        reg_data = self.get_regulation(regulation)
        return reg_data.get("bring_limit", 4)

    def list_regulation_codes(self) -> list[str]:
        """
        List all available regulation codes.

        Returns:
            List of regulation codes (e.g., ["reg_f", "reg_g", "reg_h"])
        """
        return list(self._data.get("regulations", {}).keys())

    def list_regulations(self) -> list[dict]:
        """
        List all available regulations with summary info.

        Returns:
            List of regulation summaries
        """
        result = []
        for reg_code, reg_data in self._data.get("regulations", {}).items():
            result.append({
                "code": reg_code,
                "name": reg_data.get("name", reg_code),
                "description": reg_data.get("description", ""),
                "restricted_limit": reg_data.get("restricted_limit", 2),
                "start_date": reg_data.get("start_date"),
                "end_date": reg_data.get("end_date"),
                "is_current": reg_code == self.current_regulation
            })
        return result

    def is_pokemon_restricted(
        self,
        pokemon_name: str,
        regulation: Optional[str] = None
    ) -> bool:
        """
        Check if a Pokemon is restricted.

        Args:
            pokemon_name: Pokemon name (case-insensitive)
            regulation: Regulation code. Uses current if None.

        Returns:
            True if the Pokemon is restricted
        """
        name_normalized = pokemon_name.lower().replace(" ", "-")
        restricted = self.get_restricted_pokemon(regulation)
        return name_normalized in restricted

    def is_pokemon_banned(
        self,
        pokemon_name: str,
        regulation: Optional[str] = None
    ) -> bool:
        """
        Check if a Pokemon is banned (mythical).

        Args:
            pokemon_name: Pokemon name (case-insensitive)
            regulation: Regulation code. Uses current if None.

        Returns:
            True if the Pokemon is banned
        """
        name_normalized = pokemon_name.lower().replace(" ", "-")
        banned = self.get_banned_pokemon(regulation)
        return name_normalized in banned


# Global singleton for easy access
_regulation_config: Optional[RegulationConfig] = None


def get_regulation_config() -> RegulationConfig:
    """Get or create the global regulation config singleton."""
    global _regulation_config
    if _regulation_config is None:
        _regulation_config = RegulationConfig()
    return _regulation_config


def reset_regulation_config() -> None:
    """Reset the global config (useful for testing)."""
    global _regulation_config
    _regulation_config = None
