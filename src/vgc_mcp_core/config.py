"""Configuration settings for the VGC MCP server."""

import bisect
import logging
import sys
from pathlib import Path


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """Configure logging for the application.

    Args:
        level: Logging level (default: INFO)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("vgc_mcp")

    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)

    logger.setLevel(level)
    return logger


# Initialize logger
logger = setup_logging()


class Settings:
    """Application settings."""

    # Cache settings
    CACHE_DIR: Path = Path(__file__).parent.parent.parent / "data" / "cache"
    CACHE_EXPIRE_DAYS: int = 7

    # API settings
    POKEAPI_BASE_URL: str = "https://pokeapi.co/api/v2"
    SMOGON_STATS_BASE_URL: str = "https://www.smogon.com/stats"
    POKEPASTE_BASE_URL: str = "https://pokepast.es"
    API_TIMEOUT_SECONDS: float = 30.0
    API_MAX_RETRIES: int = 3
    API_RETRY_DELAY: float = 1.0

    # Smogon rating cutoffs
    SMOGON_RATING_CUTOFFS: list[int] = [0, 1500, 1630, 1760]

    # VGC defaults
    DEFAULT_LEVEL: int = 50
    DEFAULT_FORMAT: str = "gen9vgc2026regfbo3"
    DEFAULT_RATING: int = 0  # 0 = all competitive data (broadest dataset)

    # Team settings
    MAX_TEAM_SIZE: int = 6
    MAX_TOTAL_EVS: int = 508
    MAX_STAT_EVS: int = 252

    # Damage calculation
    DAMAGE_ROLL_COUNT: int = 16


settings = Settings()


# Valid EV breakpoints at level 50: 0, 4, 12, 20, 28, 36, ... 244, 252
# Pattern: First point at 4 EVs, then +8 EVs for each additional stat point
# EVs like 8, 16, 24, 32 are wasteful (same stat as 4, 12, 20, 28)
EV_BREAKPOINTS_LV50: list[int] = [0, 4] + [4 + 8 * i for i in range(1, 32)]  # 0, 4, 12, 20, ... 252


def normalize_evs(evs: int) -> int:
    """
    Normalize EVs to a valid breakpoint at level 50.

    At level 50, EV breakpoints are: 0, 4, 12, 20, 28, 36, ... 244, 252
    - First stat point: 4 EVs
    - Each additional point: +8 EVs

    EVs between breakpoints (like 8, 16, 24) are wasteful and get
    rounded down to the previous breakpoint.

    Uses binary search for O(log n) lookup instead of O(n) linear search.

    Args:
        evs: Raw EV value

    Returns:
        EVs rounded down to nearest valid breakpoint, capped at 252

    Examples:
        normalize_evs(4) -> 4   (valid breakpoint)
        normalize_evs(8) -> 4   (wasteful, same stat as 4)
        normalize_evs(12) -> 12 (valid breakpoint)
        normalize_evs(16) -> 12 (wasteful, same stat as 12)
        normalize_evs(252) -> 252 (max valid)
        normalize_evs(256) -> 252 (capped)
    """
    # Cap at max stat EVs first
    evs = min(evs, settings.MAX_STAT_EVS)

    if evs <= 0:
        return 0

    # Use bisect to find insertion point, then get previous valid breakpoint
    # bisect_right gives index where evs would be inserted to keep sorted order
    idx = bisect.bisect_right(EV_BREAKPOINTS_LV50, evs) - 1

    if idx >= 0:
        return EV_BREAKPOINTS_LV50[idx]

    return 0


def distribute_remaining_evs(
    current_evs: dict[str, int],
    remaining: int,
    priority_stats: list[str] | None = None
) -> dict[str, int]:
    """
    Distribute remaining EVs across stats using valid breakpoints.

    At level 50, EVs must be at valid breakpoints (0, 4, 12, 20, 28...).
    This function distributes leftover EVs properly.

    Args:
        current_evs: Dict of stat_name -> current EV value
        remaining: Number of EVs left to distribute
        priority_stats: Stats to prioritize (in order). If None, uses default order.

    Returns:
        Updated EV dict with remaining EVs distributed at valid breakpoints

    Example:
        # Have 88 EVs remaining, want to put in Attack
        distribute_remaining_evs({'hp': 84, 'spd': 84, 'spe': 252}, 88, ['atk'])
        # Returns: {'hp': 84, 'spd': 84, 'spe': 252, 'atk': 84, 'def': 4}
        # Because 88 = 84 (valid) + 4 (valid), not 88 (invalid)
    """
    if remaining <= 0:
        return current_evs

    result = current_evs.copy()

    # Default priority: atk, spa, def, spd, hp (offense first, then bulk)
    if priority_stats is None:
        priority_stats = ['atk', 'attack', 'spa', 'special_attack', 'def', 'defense',
                         'spd', 'special_defense', 'hp']

    # Normalize stat names
    stat_mapping = {
        'hp': 'hp', 'health': 'hp',
        'atk': 'attack', 'attack': 'attack',
        'def': 'defense', 'defense': 'defense',
        'spa': 'special_attack', 'special_attack': 'special_attack', 'spatk': 'special_attack',
        'spd': 'special_defense', 'special_defense': 'special_defense', 'spdef': 'special_defense',
        'spe': 'speed', 'speed': 'speed',
    }

    # All stats in normalized form
    all_stats = ['hp', 'attack', 'defense', 'special_attack', 'special_defense', 'speed']

    # Convert priority list to normalized names
    normalized_priority = []
    for stat in priority_stats:
        normalized = stat_mapping.get(stat.lower(), stat.lower())
        if normalized in all_stats and normalized not in normalized_priority:
            normalized_priority.append(normalized)

    # Add remaining stats not in priority
    for stat in all_stats:
        if stat not in normalized_priority:
            normalized_priority.append(stat)

    # Distribute remaining EVs
    evs_left = remaining
    for stat in normalized_priority:
        if evs_left <= 0:
            break

        current = result.get(stat, 0)
        if current >= settings.MAX_STAT_EVS:
            continue

        # Find max we can add to this stat
        max_addable = settings.MAX_STAT_EVS - current

        # Find the largest valid breakpoint we can add
        for bp in reversed(EV_BREAKPOINTS_LV50):
            if bp <= min(evs_left, max_addable):
                if bp > 0:
                    # Only add if it results in a valid total for this stat
                    new_value = current + bp
                    if new_value in EV_BREAKPOINTS_LV50 or new_value == 0:
                        result[stat] = new_value
                        evs_left -= bp
                        break
                    else:
                        # Current + bp doesn't give valid breakpoint
                        # Try to find a bp that makes the total valid
                        for test_bp in reversed(EV_BREAKPOINTS_LV50):
                            if test_bp <= min(evs_left, max_addable):
                                test_total = current + test_bp
                                if test_total in EV_BREAKPOINTS_LV50:
                                    result[stat] = test_total
                                    evs_left -= test_bp
                                    break
                        break

    return result


def validate_ev_spread(evs: dict[str, int]) -> tuple[bool, str]:
    """
    Validate an EV spread for VGC legality.

    Args:
        evs: Dict of stat_name -> EV value

    Returns:
        Tuple of (is_valid, error_message)
    """
    total = sum(evs.values())

    if total > settings.MAX_TOTAL_EVS:
        return False, f"Total EVs ({total}) exceed maximum ({settings.MAX_TOTAL_EVS})"

    for stat, value in evs.items():
        if value > settings.MAX_STAT_EVS:
            return False, f"{stat} EVs ({value}) exceed maximum ({settings.MAX_STAT_EVS})"
        if value < 0:
            return False, f"{stat} EVs ({value}) cannot be negative"
        if value not in EV_BREAKPOINTS_LV50 and value != 0:
            normalized = normalize_evs(value)
            return False, f"{stat} EVs ({value}) is not a valid breakpoint. Use {normalized} instead."

    return True, ""
