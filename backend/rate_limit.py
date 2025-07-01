"""
Rate limiting utilities for MCP tools.
"""

from typing import Dict, Optional, Callable
import time
import asyncio
from datetime import datetime, timedelta
from functools import wraps
from errors import MCPRateLimitError

class TokenBucket:
    """Token bucket rate limiter implementation"""
    
    def __init__(self, rate: float, capacity: int):
        self.rate = rate  # tokens per second
        self.capacity = capacity
        self.tokens = capacity
        self.last_update = time.time()
    
    def _add_tokens(self) -> None:
        """Add tokens based on time elapsed"""
        now = time.time()
        elapsed = now - self.last_update
        new_tokens = elapsed * self.rate
        
        self.tokens = min(self.capacity, self.tokens + new_tokens)
        self.last_update = now
    
    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens"""
        self._add_tokens()
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        
        return False

class RateLimiter:
    """Rate limiter for MCP tools"""
    
    def __init__(self):
        # Default limits per tool
        self.tool_limits = {
            "search_medication_price": (5, 10),  # 5 requests/sec, burst of 10
            "find_generic_alternatives": (2, 5),  # 2 requests/sec, burst of 5
            "find_pharmacies": (2, 5),          # 2 requests/sec, burst of 5
            "compare_prices": (1, 3),           # 1 request/sec, burst of 3
            "default": (10, 20)                 # Default: 10 requests/sec, burst of 20
        }
        
        # Create token buckets for each tool
        self.limiters: Dict[str, TokenBucket] = {}
        for tool, (rate, capacity) in self.tool_limits.items():
            self.limiters[tool] = TokenBucket(rate, capacity)
    
    async def check_rate_limit(self, tool_name: str, tokens: int = 1) -> bool:
        """Check if the tool has exceeded its rate limit"""
        limiter = self.limiters.get(tool_name, self.limiters["default"])
        return await limiter.acquire(tokens)

# Global rate limiter instance
rate_limiter = RateLimiter()

def rate_limit(tool_name: Optional[str] = None, tokens: int = 1):
    """Decorator to apply rate limiting to MCP tools"""
    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Use function name if tool_name not provided
            actual_tool = tool_name or func.__name__
            
            # Check rate limit
            if not await rate_limiter.check_rate_limit(actual_tool, tokens):
                retry_after = 1.0 / rate_limiter.tool_limits.get(actual_tool, (1, 1))[0]
                raise MCPRateLimitError(
                    f"Rate limit exceeded for {actual_tool}. "
                    f"Please retry after {retry_after:.1f} seconds."
                )
            
            return await func(*args, **kwargs)
        return wrapper
    return decorator

class RateLimitTracker:
    """Track rate limit usage and provide analytics"""
    
    def __init__(self):
        self.usage: Dict[str, list] = {}
    
    def record_request(self, tool_name: str):
        """Record a request for a tool"""
        now = datetime.now()
        if tool_name not in self.usage:
            self.usage[tool_name] = []
        self.usage[tool_name].append(now)
    
    def get_usage_stats(self, tool_name: str, window_seconds: int = 3600) -> Dict:
        """Get usage statistics for a tool"""
        if tool_name not in self.usage:
            return {"requests": 0, "rate": 0.0}
        
        now = datetime.now()
        window_start = now - timedelta(seconds=window_seconds)
        
        # Filter requests within window
        recent_requests = [
            ts for ts in self.usage[tool_name]
            if ts > window_start
        ]
        
        # Calculate stats
        num_requests = len(recent_requests)
        rate = num_requests / window_seconds if window_seconds > 0 else 0
        
        return {
            "requests": num_requests,
            "rate": rate,
            "window_seconds": window_seconds
        }
    
    def cleanup_old_data(self, max_age_seconds: int = 86400):
        """Remove old usage data"""
        now = datetime.now()
        cutoff = now - timedelta(seconds=max_age_seconds)
        
        for tool_name in self.usage:
            self.usage[tool_name] = [
                ts for ts in self.usage[tool_name]
                if ts > cutoff
            ]

# Global rate limit tracker instance
rate_tracker = RateLimitTracker()

# Start background task to clean old usage data
async def clean_old_usage_data():
    """Background task to clean old usage data"""
    while True:
        rate_tracker.cleanup_old_data()
        await asyncio.sleep(3600)  # Clean every hour 