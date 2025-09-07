import subprocess
import sys
import logging

logger = logging.getLogger(__name__)
trading_process = None

def start_trading():
    """Starts the trading bot as a separate process."""
    global trading_process
    if trading_process and trading_process.poll() is None:
        return {"success": False, "message": "Trading app is already running."}
    try:
        python_executable = sys.executable
        trading_process = subprocess.Popen([python_executable, "-u", "main.py"])
        logger.info(f"Started trading process with PID: {trading_process.pid}")
        return {"success": True, "message": "Trading app started."}
    except Exception as e:
        logger.error(f"Failed to start trading process: {e}")
        return {"success": False, "message": str(e)}

def stop_trading():
    """Stops the trading bot process."""
    global trading_process
    if trading_process and trading_process.poll() is None:
        try:
            pid = trading_process.pid
            trading_process.terminate()
            trading_process.wait(timeout=5)
            if trading_process.poll() is None:
                trading_process.kill()
            trading_process = None
            logger.info(f"Stopped trading process with PID: {pid}")
            return {"success": True, "message": "Trading app stopped."}
        except Exception as e:
            logger.error(f"Error stopping trading process: {e}")
            return {"success": False, "message": "Could not stop the process cleanly."}
    else:
        return {"success": False, "message": "Trading app is not running."}

def get_trading_status():
    """Checks if the trading bot process is running."""
    global trading_process
    if trading_process and trading_process.poll() is None:
        return {"status": "Running"}
    else:
        return {"status": "Stopped"}