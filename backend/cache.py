"""
Caching utilities for MCP tools.
"""

from typing import Any, Optional, Dict, Callable
import json
import asyncio
from datetime import datetime, timedelta
import hashlib
from functools import wraps

class MCPCache:
    """Simple in-memory cache with TTL for MCP tool results"""
    
    def __init__(self, ttl_seconds: int = 3600):
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ttl_seconds = ttl_seconds
    
    def _generate_key(self, tool_name: str, args: tuple, kwargs: Dict[str, Any]) -> str:
        """Generate a unique cache key based on tool name and arguments"""
        # Convert args and kwargs to a stable string representation
        args_str = json.dumps(args, sort_keys=True)
        kwargs_str = json.dumps(kwargs, sort_keys=True)
        key_str = f"{tool_name}:{args_str}:{kwargs_str}"
        return hashlib.sha256(key_str.encode()).hexdigest()
    
    def get(self, key: str) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired"""
        if key not in self._cache:
            return None
        
        entry = self._cache[key]
        if datetime.now() > entry["expires_at"]:
            del self._cache[key]
            return None
        
        return entry["value"]
    
    def set(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> None:
        """Set a value in cache with TTL"""
        expires_at = datetime.now() + timedelta(seconds=ttl_seconds or self._ttl_seconds)
        self._cache[key] = {
            "value": value,
            "expires_at": expires_at
        }
    
    def clear(self) -> None:
        """Clear all cached values"""
        self._cache.clear()
    
    def remove_expired(self) -> None:
        """Remove all expired cache entries"""
        now = datetime.now()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry["expires_at"]
        ]
        for key in expired_keys:
            del self._cache[key]

# Global cache instance
mcp_cache = MCPCache()

def cache_mcp_result(ttl_seconds: Optional[int] = None):
    """Decorator to cache MCP tool results"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Generate cache key
            cache_key = mcp_cache._generate_key(func.__name__, args, kwargs)
            
            # Try to get from cache
            cached_result = mcp_cache.get(cache_key)
            if cached_result is not None:
                return cached_result
            
            # Execute function and cache result
            result = await func(*args, **kwargs)
            mcp_cache.set(cache_key, result, ttl_seconds)
            return result
        
        return wrapper
    return decorator

# Start background task to periodically clean expired cache entries
async def clean_expired_cache():
    """Background task to clean expired cache entries"""
    while True:
        mcp_cache.remove_expired()
        await asyncio.sleep(300)  # Clean every 5 minutes 