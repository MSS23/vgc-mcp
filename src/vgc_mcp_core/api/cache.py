"""Disk-based caching layer for API responses."""

import hashlib
from pathlib import Path
from typing import Any, Optional

import diskcache


class APICache:
    """Disk-based cache with 7-day expiration."""

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

    def _make_key(self, prefix: str, *args: str) -> str:
        """Create a cache key from prefix and arguments."""
        key_data = f"{prefix}:{':'.join(str(a) for a in args)}"
        return hashlib.sha256(key_data.encode()).hexdigest()[:32]

    def get(self, prefix: str, *args: str) -> Optional[Any]:
        """Retrieve from cache if not expired."""
        key = self._make_key(prefix, *args)
        return self.cache.get(key)

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

    def close(self) -> None:
        """Close the cache."""
        self.cache.close()

    def __enter__(self) -> "APICache":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.close()
