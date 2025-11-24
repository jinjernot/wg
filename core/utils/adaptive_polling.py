import time
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class AdaptivePoller:
    """
    Manages adaptive polling intervals based on activity and time of day.
    Reduces API calls during quiet periods while maintaining responsiveness.
    """
    
    def __init__(self, base_interval=60, quiet_interval=120, off_hours_interval=300):
        """
        Initialize adaptive poller.
        
        Args:
            base_interval: Interval when trades are active (default: 60s)
            quiet_interval: Interval when no trades found (default: 120s)
            off_hours_interval: Interval during off-hours (default: 300s)
        """
        self.base_interval = base_interval
        self.quiet_interval = quiet_interval
        self.off_hours_interval = off_hours_interval
        
        self.current_interval = base_interval
        self.consecutive_empty_polls = 0
        self.last_activity_time = time.time()
        
        # Off-hours: 2 AM - 7 AM (Mexico City time)
        self.off_hours_start = 2
        self.off_hours_end = 7
        
        logger.info(f"Initialized adaptive poller (base={base_interval}s, "
                   f"quiet={quiet_interval}s, off-hours={off_hours_interval}s)")
    
    def record_activity(self, found_trades=False):
        """
        Record polling activity and adjust interval accordingly.
        
        Args:
            found_trades: Whether trades were found in this poll
        """
        if found_trades:
            # Reset to base interval when trades are found
            if self.current_interval != self.base_interval:
                logger.info(f"Trades detected, resetting interval to {self.base_interval}s")
            self.current_interval = self.base_interval
            self.consecutive_empty_polls = 0
            self.last_activity_time = time.time()
        else:
            # Increase interval if no trades found
            self.consecutive_empty_polls += 1
            
            # After 5 consecutive empty polls, switch to quiet interval
            if self.consecutive_empty_polls >= 5 and self.current_interval == self.base_interval:
                self.current_interval = self.quiet_interval
                logger.info(f"No activity detected, increasing interval to {self.quiet_interval}s")
    
    def get_interval(self):
        """
        Get the current polling interval, adjusted for time of day.
        
        Returns:
            Interval in seconds to wait before next poll
        """
        # Check if we're in off-hours (2 AM - 7 AM Mexico City time)
        current_hour = datetime.now().hour
        
        if self.off_hours_start <= current_hour < self.off_hours_end:
            if self.current_interval != self.off_hours_interval:
                logger.info(f"Off-hours detected, using {self.off_hours_interval}s interval")
            return self.off_hours_interval
        
        return self.current_interval
    
    def get_stats(self):
        """Get polling statistics."""
        time_since_activity = int(time.time() - self.last_activity_time)
        return {
            "current_interval": self.current_interval,
            "consecutive_empty_polls": self.consecutive_empty_polls,
            "seconds_since_activity": time_since_activity
        }
