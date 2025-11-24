import time
import threading
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class TokenCache:
    """Thread-safe token cache with automatic expiration management."""
    
    def __init__(self):
        self._cache = {}  # {account_name: {"token": str, "expires_at": float}}
        self._lock = threading.Lock()
        # Default token expiration is 55 minutes (tokens typically last 60 min)
        self.default_ttl_seconds = 55 * 60
    
    def get(self, account_name):
        """
        Get a cached token for the account if it exists and hasn't expired.
        
        Args:
            account_name: Name of the account
            
        Returns:
            Token string if valid cached token exists, None otherwise
        """
        with self._lock:
            if account_name not in self._cache:
                logger.debug(f"No cached token for {account_name}")
                return None
            
            cached_entry = self._cache[account_name]
            expires_at = cached_entry["expires_at"]
            
            # Check if token is still valid (with 5 minute buffer)
            if time.time() >= expires_at:
                logger.info(f"Cached token for {account_name} has expired")
                del self._cache[account_name]
                return None
            
            logger.debug(f"Using cached token for {account_name} (expires in {int(expires_at - time.time())}s)")
            return cached_entry["token"]
    
    def set(self, account_name, token, ttl_seconds=None):
        """
        Store a token in the cache with expiration time.
        
        Args:
            account_name: Name of the account
            token: Authentication token
            ttl_seconds: Time to live in seconds (default: 55 minutes)
        """
        if ttl_seconds is None:
            ttl_seconds = self.default_ttl_seconds
        
        expires_at = time.time() + ttl_seconds
        
        with self._lock:
            self._cache[account_name] = {
                "token": token,
                "expires_at": expires_at
            }
            logger.info(f"Cached token for {account_name} (TTL: {ttl_seconds}s)")
    
    def invalidate(self, account_name):
        """Remove a token from the cache."""
        with self._lock:
            if account_name in self._cache:
                del self._cache[account_name]
                logger.info(f"Invalidated cached token for {account_name}")
    
    def clear(self):
        """Clear all cached tokens."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.info(f"Cleared {count} cached tokens")
    
    def get_stats(self):
        """Get cache statistics."""
        with self._lock:
            total = len(self._cache)
            valid = sum(1 for entry in self._cache.values() 
                       if time.time() < entry["expires_at"])
            return {"total": total, "valid": valid, "expired": total - valid}


# Global token cache instance
_token_cache = TokenCache()


def get_token_cache():
    """Get the global token cache instance."""
    return _token_cache
