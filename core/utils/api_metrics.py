import logging
import json
import os
from datetime import datetime
from collections import defaultdict
import threading

logger = logging.getLogger(__name__)


class APIMetrics:
    """Track API calls and provide usage statistics."""
    
    def __init__(self):
        self._metrics = defaultdict(int)  # {endpoint: count}
        self._lock = threading.Lock()
        self.start_time = datetime.now()
    
    def record_call(self, endpoint):
        """Record an API call to the specified endpoint."""
        with self._lock:
            self._metrics[endpoint] += 1
    
    def get_stats(self):
        """Get current API call statistics."""
        with self._lock:
            total_calls = sum(self._metrics.values())
            uptime = (datetime.now() - self.start_time).total_seconds()
            calls_per_hour = (total_calls / uptime * 3600) if uptime > 0 else 0
            
            return {
                "total_calls": total_calls,
                "calls_per_hour": round(calls_per_hour, 2),
                "uptime_seconds": round(uptime),
                "by_endpoint":  dict(self._metrics),
                "timestamp": datetime.now().isoformat()
            }
    
    def save_to_file(self, filepath):
        """Save metrics to a JSON file."""
        try:
            stats = self.get_stats()
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=4)
            
            logger.info(f"API metrics saved to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save API metrics: {e}")
    
    def log_summary(self):
        """Log a summary of API metrics."""
        stats = self.get_stats()
        logger.info(f"=== API Metrics Summary ===")
        logger.info(f"Total API calls: {stats['total_calls']}")
        logger.info(f"Calls per hour: {stats['calls_per_hour']}")
        logger.info(f"Uptime: {stats['uptime_seconds']}s")
        logger.info(f"Top endpoints:")
        
        # Sort by call count
        sorted_endpoints = sorted(
            stats['by_endpoint'].items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        
        for endpoint, count in sorted_endpoints:
            logger.info(f"  {endpoint}: {count}")


# Global metrics instance
_api_metrics = APIMetrics()


def get_api_metrics():
    """Get the global API metrics instance."""
    return _api_metrics
