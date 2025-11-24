"""
Simple test script to verify the optimization modules work correctly.
This tests basic functionality without requiring the full app to run.
"""
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def test_token_cache():
    """Test token cache basic functionality."""
    print("Testing token cache...")
    from core.utils.token_cache import get_token_cache
    
    cache = get_token_cache()
    
    # Test set and get
    cache.set("test_account", "test_token_123", ttl_seconds=10)
    token = cache.get("test_account")
    assert token == "test_token_123", f"Expected 'test_token_123', got '{token}'"
    
    # Test stats
    stats = cache.get_stats()
    assert stats["total"] >= 1, "Cache should have at least 1 entry"
    
    print("✓ Token cache test passed")


def test_http_client():
    """Test HTTP client initialization."""
    print("Testing HTTP client...")
    from core.utils.http_client import get_http_client, close_http_client
    
    client = get_http_client()
    assert client is not None, "HTTP client should not be None"
    assert hasattr(client, 'session'), "HTTP client should have session attribute"
    
    close_http_client()
    print("✓ HTTP client test passed")


def test_adaptive_polling():
    """ Test adaptive poller functionality."""
    print("Testing adaptive poller...")
    stats = poller.get_stats()
    assert "current_interval" in stats, "Stats should include current_interval"
    
    print("✓ Adaptive poller test passed")


def test_response_cache():
    """Test response cache functionality."""
    print("Testing response cache...")
    from core.utils.response_cache import get_response_cache
    
    cache = get_response_cache()
    
    # Test set and get
    cache.set("test_endpoint", {"data": "test_value"}, ttl_seconds=10)
    data = cache.get("test_endpoint")
    assert data == {"data": "test_value"}, f"Expected test data, got {data}"
    
    # Test cache miss
    missing = cache.get("nonexistent_endpoint")
    assert missing is None, "Should return None for missing endpoint"
    
    # Test stats
    stats = cache.get_stats()
    assert "hits" in stats and "misses" in stats, "Stats should include hits and misses"
    
    print("✓ Response cache test passed")


def test_api_metrics():
    """Test API metrics tracking."""
    print("Testing API metrics...")
    from core.utils.api_metrics import get_api_metrics
    
    metrics = get_api_metrics()
    
    # Record some calls
    metrics.record_call("test_endpoint_1")
    metrics.record_call("test_endpoint_2")
    metrics.record_call("test_endpoint_1")
    
    # Get stats
    stats = metrics.get_stats()
    assert stats["total_calls"] >= 3, f"Expected at least 3 calls, got {stats['total_calls']}"
    assert "test_endpoint_1" in stats["by_endpoint"], "Should track test_endpoint_1"
    
    print("✓ API metrics test passed")


if __name__ == "__main__":
    try:
        test_token_cache()
        test_http_client()
        test_adaptive_polling()
        test_response_cache()
        test_api_metrics()
        
        print("\n✅ All optimization module tests passed!")
        sys.exit(0)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
