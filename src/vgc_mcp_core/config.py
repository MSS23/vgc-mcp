"""Configuration settings for the VGC MCP server."""

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
    DEFAULT_FORMAT: str = "gen9vgc2025regg"
    DEFAULT_RATING: int = 1760

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

    # Find the highest breakpoint <= evs
    for bp in reversed(EV_BREAKPOINTS_LV50):
        if bp <= evs:
            return bp

    return 0
