"""Disk-based caching layer for API responses."""

import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

import diskcache

logger = logging.getLogger(__name__)


class APICache:
    """Disk-based cache with 7-day expiration and hit/miss tracking."""

    DEFAULT_EXPIRE = 7 * 24 * 60 * 60  # 7 days in seconds

    def __init__(self, cache_dir: Optional[str] = None):
        """Initialize cache with optional custom directory."""
        if cache_dir is None:
            # Default to data/cache in the project root
            cache_dir = Path(__file__).parent.parent.parent.parent / "data" / "cache"
        else:
            cache_dir = Path(cache_dir)

        cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache = diskcache.Cache(str(cache_dir))
        self._hits = 0
        self._misses = 0

    def _make_key(self, prefix: str, *args: str) -> str:
        """Create a cache key from prefix and arguments."""
        key_data = f"{prefix}:{':'.join(str(a) for a in args)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get(self, prefix: str, *args: str) -> Optional[Any]:
        """Retrieve from cache if not expired. Tracks hit/miss stats."""
        key = self._make_key(prefix, *args)
        result = self.cache.get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def set(
        self,
        prefix: str,
        *args: str,
        value: Any,
        expire: Optional[int] = None
    ) -> None:
        """Store in cache with expiration."""
        key = self._make_key(prefix, *args)
        self.cache.set(key, value, expire=expire or self.DEFAULT_EXPIRE)

    def delete(self, prefix: str, *args: str) -> None:
        """Remove specific cache entry."""
        key = self._make_key(prefix, *args)
        self.cache.delete(key)

    def clear_all(self) -> None:
        """Clear entire cache."""
        self.cache.clear()

    @property
    def stats(self) -> dict:
        """Return cache hit/miss statistics."""
        total = self._hits + self._misses
        return {
            "hits": self._hits,
            "misses": self._misses,
            "total": total,
            "hit_rate": f"{(self._hits / total * 100):.1f}%" if total > 0 else "0.0%",
        }

    def reset_stats(self) -> None:
        """Reset hit/miss counters."""
        self._hits = 0
        self._misses = 0

    def close(self) -> None:
        """Close the cache. Logs final stats if any lookups occurred."""
        total = self._hits + self._misses
        if total > 0:
            logger.debug(
                "Cache closing — hits: %d, misses: %d, hit rate: %s",
                self._hits, self._misses, self.stats["hit_rate"]
            )
        self.cache.close()

    def __enter__(self) -> "APICache":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
