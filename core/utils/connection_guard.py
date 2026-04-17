# core/utils/connection_guard.py

import socket
import time
import logging

logger = logging.getLogger(__name__)

# A reliable, low-latency host to test connectivity against.
# Using Google's DNS — it's available worldwide and doesn't throttle pings.
_CHECK_HOST = "8.8.8.8"
_CHECK_PORT = 53
_CHECK_TIMEOUT = 5  # seconds per attempt


def is_internet_available() -> bool:
    """Returns True if we can reach the internet right now."""
    try:
        socket.setdefaulttimeout(_CHECK_TIMEOUT)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(
            (_CHECK_HOST, _CHECK_PORT)
        )
        return True
    except OSError:
        return False


def wait_for_internet(retry_interval: int = 30, label: str = "") -> None:
    """
    Blocks the calling thread until internet connectivity is restored.

    Logs a message every `retry_interval` seconds while waiting so you can
    see progress in the logs without flooding them.

    Args:
        retry_interval: How often (seconds) to re-check and log.
        label: Optional prefix for log messages (e.g., the caller's name).
    """
    prefix = f"[{label}] " if label else ""

    if is_internet_available():
        return  # Already connected — fast path

    logger.warning(
        f"{prefix}No internet connection detected. "
        f"Will retry every {retry_interval}s until connectivity is restored..."
    )

    attempts = 0
    while not is_internet_available():
        attempts += 1
        logger.warning(
            f"{prefix}Waiting for internet... (attempt {attempts}, "
            f"elapsed ~{attempts * retry_interval}s)"
        )
        time.sleep(retry_interval)

    elapsed = attempts * retry_interval
    logger.info(
        f"{prefix}Internet connection restored after ~{elapsed}s "
        f"({attempts} {'attempt' if attempts == 1 else 'attempts'})."
    )
