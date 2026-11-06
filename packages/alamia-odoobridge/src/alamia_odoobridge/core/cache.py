"""
In-Memory Schema Cache for Alamia OdooBridge.
Caches introspection metadata (ir.model lists, fields_get) with configurable TTL
to eliminate redundant RPC latency while maintaining data freshness.
"""

import time
import logging
import threading
from typing import Any, Dict, Optional, NamedTuple

logger = logging.getLogger("alamia_odoobridge.cache")


class _CacheEntry(NamedTuple):
    value: Any
    expires_at: float


class SchemaCache:
    """Thread-safe TTL in-memory schema cache."""

    def __init__(self, default_ttl: float = 3600.0, enabled: bool = True):
        self.default_ttl = default_ttl
        self.enabled = enabled
        self._cache: Dict[str, _CacheEntry] = {}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """Retrieve a value from the cache if present and not expired."""
        if not self.enabled:
            return None

        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None

            now = time.time()
            if now > entry.expires_at:
                del self._cache[key]
                self._misses += 1
                return None

            self._hits += 1
            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Store a value in the cache with an expiration timestamp."""
        if not self.enabled:
            return

        expires_in = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + expires_in

        with self._lock:
            self._cache[key] = _CacheEntry(value=value, expires_at=expires_at)

    def invalidate(self, key_or_prefix: Optional[str] = None) -> int:
        """
        Invalidate a specific key, all keys starting with a prefix, or everything.
        Returns the number of invalidated entries.
        """
        with self._lock:
            if not key_or_prefix:
                count = len(self._cache)
                self._cache.clear()
                return count

            keys_to_delete = [
                k for k in self._cache.keys()
                if k == key_or_prefix or k.startswith(key_or_prefix)
            ]
            for k in keys_to_delete:
                del self._cache[k]
            return len(keys_to_delete)

    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        with self._lock:
            self._cache.clear()
            self._hits = 0
            self._misses = 0

    @property
    def stats(self) -> Dict[str, Any]:
        """Return cache metrics (hits, misses, entry count, hit ratio)."""
        with self._lock:
            total = self._hits + self._misses
            ratio = (self._hits / total) if total > 0 else 0.0
            return {
                "enabled": self.enabled,
                "hits": self._hits,
                "misses": self._misses,
                "entries": len(self._cache),
                "hit_ratio": round(ratio, 3),
            }
