import requests
import logging
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class OptimizedHTTPClient:
    """
    HTTP client with connection pooling and automatic retry logic.
    Reuses connections to reduce overhead and improve performance.
    """
    
    def __init__(self, pool_connections=10, pool_maxsize=20, max_retries=3):
        """
        Initialize HTTP client with connection pooling.
        
        Args:
            pool_connections: Number of connection pools to cache
            pool_maxsize: Maximum number of connections per pool
            max_retries: Maximum number of retry attempts for failed requests
        """
        self.session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,  # Wait 1, 2, 4 seconds between retries
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "POST", "PUT", "DELETE", "OPTIONS", "TRACE"]
        )
        
        # Configure HTTP adapter with pooling
        adapter = HTTPAdapter(
            pool_connections=pool_connections,
            pool_maxsize=pool_maxsize,
            max_retries=retry_strategy
        )
        
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)
        
        logger.info(f"Initialized HTTP client with connection pooling "
                   f"(pool_size={pool_maxsize}, max_retries={max_retries})")
    
    def post(self, url, **kwargs):
        """Make a POST request using the pooled session."""
        try:
            return self.session.post(url, **kwargs)
        except Exception as e:
            logger.error(f"HTTP POST error for {url}: {e}")
            raise
    
    def get(self, url, **kwargs):
        """Make a GET request using the pooled session."""
        try:
            return self.session.get(url, **kwargs)
        except Exception as e:
            logger.error(f"HTTP GET error for {url}: {e}")
            raise
    
    def put(self, url, **kwargs):
        """Make a PUT request using the pooled session."""
        try:
            return self.session.put(url, **kwargs)
        except Exception as e:
            logger.error(f"HTTP PUT error for {url}: {e}")
            raise
    
    def patch(self, url, **kwargs):
        """Make a PATCH request using the pooled session."""
        try:
            return self.session.patch(url, **kwargs)
        except Exception as e:
            logger.error(f"HTTP PATCH error for {url}: {e}")
            raise
    
    def delete(self, url, **kwargs):
        """Make a DELETE request using the pooled session."""
        try:
            return self.session.delete(url, **kwargs)
        except Exception as e:
            logger.error(f"HTTP DELETE error for {url}: {e}")
            raise
    
    def close(self):
        """Close the session and release connections."""
        self.session.close()
        logger.info("Closed HTTP client session")


# Global HTTP client instance
_http_client = None


def get_http_client():
    """Get the global HTTP client instance, creating it if necessary."""
    global _http_client
    if _http_client is None:
        _http_client = OptimizedHTTPClient()
    return _http_client


def close_http_client():
    """Close the global HTTP client."""
    global _http_client
    if _http_client is not None:
        _http_client.close()
        _http_client = None
