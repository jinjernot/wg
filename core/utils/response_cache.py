import time
import threading
import logging
import hashlib
import json

logger = logging.getLogger(__name__)


class ResponseCache:
    """
    Simple response cache for API responses with TTL support.
    Prevents redundant API calls when data hasn't changed.
    """
    
    def __init__(self):
        self._cache = {}  # {cache_key: {"data": any, "expires_at": float}}
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0
    
    def _generate_key(self, endpoint, params=None):
        """Generate a cache key from endpoint and parameters."""
        if params is None:
            return endpoint
        
        # Create deterministic key from params
        param_str = json.dumps(params, sort_keys=True)
        param_hash = hashlib.md5(param_str.encode()).hexdigest()[:8]
        return f"{endpoint}:{param_hash}"
    
    def get(self, endpoint, params=None):
        """
        Get cached response if it exists and hasn't expired.
        
        Args:
            endpoint: API endpoint identifier
            params: Optional parameters dict for cache key generation
            
        Returns:
            Cached data if valid, None otherwise
        """
        cache_key = self._generate_key(endpoint, params)
        
        with self._lock:
            if cache_key not in self._cache:
                self._misses += 1
                logger.debug(f"Cache miss for {endpoint}")
                return None
            
            cached_entry = self._cache[cache_key]
            expires_at = cached_entry["expires_at"]
            
            if time.time() >= expires_at:
                logger.debug(f"Cache expired for {endpoint}")
                del self._cache[cache_key]
                self._misses += 1
                return None
            
            self._hits += 1
            ttl_remaining = int(expires_at - time.time())
            logger.debug(f"Cache hit for {endpoint} (TTL: {ttl_remaining}s)")
            return cached_entry["data"]
    
    def set(self, endpoint, data, ttl_seconds, params=None):
        """
        Store data in cache with expiration time.
        
        Args:
            endpoint: API endpoint identifier
            data: Data to cache
            ttl_seconds: Time to live in seconds
            params: Optional parameters dict for cache key generation
        """
        cache_key = self._generate_key(endpoint, params)
        expires_at = time.time() + ttl_seconds
        
        with self._lock:
            self._cache[cache_key] = {
                "data": data,
                "expires_at": expires_at
            }
            logger.debug(f"Cached response for {endpoint} (TTL: {ttl_seconds}s)")
    
    def invalidate(self, endpoint, params=None):
        """Remove an entry from the cache."""
        cache_key = self._generate_key(endpoint, params)
        
        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                logger.debug(f"Invalidated cache for {endpoint}")
    
    def clear(self):
        """Clear all cached entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cached responses")
    
    def get_stats(self):
        """Get cache statistics."""
        with self._lock:
            total_requests = self._hits + self._misses
            hit_rate = (self._hits / total_requests * 100) if total_requests > 0 else 0
            
            return {
                "total_entries": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "hit_rate": f"{hit_rate:.1f}%"
            }


# Global response cache instance
_response_cache = ResponseCache()


def get_response_cache():
    """Get the global response cache instance."""
    return _response_cache
