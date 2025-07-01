"""
Unit tests for caching and rate limiting modules.
"""

import pytest
import asyncio
from datetime import datetime, timedelta
from cache import MCPCache, cache_mcp_result
from rate_limit import (
    TokenBucket,
    RateLimiter,
    RateLimitTracker,
    rate_limit,
    MCPRateLimitError
)

# Test data
test_data = {
    "tool_name": "test_tool",
    "args": ("arg1", "arg2"),
    "kwargs": {"key1": "value1", "key2": "value2"}
}

# Cache tests
def test_cache_key_generation():
    """Test cache key generation is consistent and unique"""
    cache = MCPCache()
    
    # Same inputs should generate same key
    key1 = cache._generate_key(
        test_data["tool_name"],
        test_data["args"],
        test_data["kwargs"]
    )
    key2 = cache._generate_key(
        test_data["tool_name"],
        test_data["args"],
        test_data["kwargs"]
    )
    assert key1 == key2
    
    # Different inputs should generate different keys
    key3 = cache._generate_key(
        "different_tool",
        test_data["args"],
        test_data["kwargs"]
    )
    assert key1 != key3

def test_cache_set_get():
    """Test basic cache set and get operations"""
    cache = MCPCache(ttl_seconds=1)
    key = "test_key"
    value = {"data": "test_value"}
    
    # Set and get
    cache.set(key, value)
    assert cache.get(key) == value
    
    # Wait for expiration
    asyncio.run(asyncio.sleep(1.1))
    assert cache.get(key) is None

def test_cache_clear():
    """Test cache clearing"""
    cache = MCPCache()
    
    # Add some items
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    
    # Clear cache
    cache.clear()
    assert cache.get("key1") is None
    assert cache.get("key2") is None

def test_cache_remove_expired():
    """Test removal of expired cache entries"""
    cache = MCPCache(ttl_seconds=1)
    
    # Add items
    cache.set("key1", "value1")
    cache.set("key2", "value2")
    
    # Wait for expiration
    asyncio.run(asyncio.sleep(1.1))
    
    # Remove expired
    cache.remove_expired()
    assert len(cache._cache) == 0

@pytest.mark.asyncio
async def test_cache_decorator():
    """Test cache decorator functionality"""
    # Define test function
    call_count = 0
    
    @cache_mcp_result(ttl_seconds=1)
    async def test_func(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        return {"result": "test"}
    
    # First call should execute function
    result1 = await test_func("arg1", key1="value1")
    assert call_count == 1
    
    # Second call should use cache
    result2 = await test_func("arg1", key1="value1")
    assert call_count == 1
    assert result1 == result2
    
    # Wait for cache expiration
    await asyncio.sleep(1.1)
    
    # Third call should execute function again
    result3 = await test_func("arg1", key1="value1")
    assert call_count == 2
    assert result1 == result3

# Rate limit tests
def test_token_bucket_initialization():
    """Test TokenBucket initialization"""
    bucket = TokenBucket(rate=1.0, capacity=5)
    assert bucket.rate == 1.0
    assert bucket.capacity == 5
    assert bucket.tokens == 5

@pytest.mark.asyncio
async def test_token_bucket_acquire():
    """Test TokenBucket token acquisition"""
    bucket = TokenBucket(rate=1.0, capacity=2)
    
    # Should be able to acquire initial tokens
    assert await bucket.acquire(1)
    assert await bucket.acquire(1)
    
    # Should not be able to acquire more tokens
    assert not await bucket.acquire(1)
    
    # Wait for token refill
    await asyncio.sleep(1.1)
    assert await bucket.acquire(1)

def test_rate_limiter_initialization():
    """Test RateLimiter initialization"""
    limiter = RateLimiter()
    
    # Check default limits
    assert "default" in limiter.tool_limits
    assert len(limiter.limiters) == len(limiter.tool_limits)
    
    # Check tool-specific limits
    assert "search_medication_price" in limiter.tool_limits
    assert "find_generic_alternatives" in limiter.tool_limits

@pytest.mark.asyncio
async def test_rate_limiter_check_rate_limit():
    """Test rate limit checking"""
    limiter = RateLimiter()
    tool_name = "test_tool"
    
    # Should use default limits for unknown tool
    assert await limiter.check_rate_limit(tool_name)
    
    # Add specific limit
    limiter.tool_limits[tool_name] = (1, 2)  # 1 req/sec, burst of 2
    limiter.limiters[tool_name] = TokenBucket(1, 2)
    
    # Test rate limiting
    assert await limiter.check_rate_limit(tool_name)
    assert await limiter.check_rate_limit(tool_name)
    assert not await limiter.check_rate_limit(tool_name)

@pytest.mark.asyncio
async def test_rate_limit_decorator():
    """Test rate limit decorator functionality"""
    # Define test function
    @rate_limit("test_tool", tokens=1)
    async def test_func():
        return "success"
    
    # First calls should succeed
    assert await test_func() == "success"
    assert await test_func() == "success"
    
    # Next call should raise rate limit error
    with pytest.raises(MCPRateLimitError):
        await test_func()
    
    # Wait for token refill
    await asyncio.sleep(1.1)
    assert await test_func() == "success"

def test_rate_limit_tracker():
    """Test rate limit usage tracking"""
    tracker = RateLimitTracker()
    tool_name = "test_tool"
    
    # Record some requests
    for _ in range(3):
        tracker.record_request(tool_name)
    
    # Check usage stats
    stats = tracker.get_usage_stats(tool_name, window_seconds=60)
    assert stats["requests"] == 3
    assert stats["rate"] > 0
    
    # Test cleanup
    tracker.cleanup_old_data(max_age_seconds=0)
    stats = tracker.get_usage_stats(tool_name)
    assert stats["requests"] == 0

@pytest.mark.asyncio
async def test_combined_cache_and_rate_limit():
    """Test cache and rate limit working together"""
    call_count = 0
    
    @rate_limit("test_tool", tokens=1)
    @cache_mcp_result(ttl_seconds=1)
    async def test_func():
        nonlocal call_count
        call_count += 1
        return "success"
    
    # First call should execute and cache
    assert await test_func() == "success"
    assert call_count == 1
    
    # Second call should use cache (not rate limited)
    assert await test_func() == "success"
    assert call_count == 1
    
    # Wait for cache expiration
    await asyncio.sleep(1.1)
    
    # Third call should hit rate limit
    with pytest.raises(MCPRateLimitError):
        await test_func()
    
    # Wait for rate limit reset
    await asyncio.sleep(1.1)
    
    # Fourth call should execute function
    assert await test_func() == "success"
    assert call_count == 2 