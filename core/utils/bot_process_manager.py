import subprocess
import sys
import logging
import os
import psutil

logger = logging.getLogger(__name__)
PID_FILE = "trading_bot.pid"

def is_running():
    """Checks if a process with the PID from the PID_FILE is running."""
    if not os.path.exists(PID_FILE):
        return False
    with open(PID_FILE, "r") as f:
        try:
            pid = int(f.read().strip())
        except ValueError:
            return False
    try:
        p = psutil.Process(pid)
        # Check if the process name contains python and the command line includes main.py
        return "python" in p.name().lower() and any("main.py" in s for s in p.cmdline())
    except psutil.NoSuchProcess:
        return False

def start_trading():
    """Starts the trading bot as a separate process and saves its PID."""
    if is_running():
        return {"success": False, "message": "Trading app is already running."}
    try:
        python_executable = sys.executable
        process = subprocess.Popen([python_executable, "-u", "main.py"])
        with open(PID_FILE, "w") as f:
            f.write(str(process.pid))
        logger.info(f"Started trading process with PID: {process.pid}")
        return {"success": True, "message": "Trading app started."}
    except Exception as e:
        logger.error(f"Failed to start trading process: {e}")
        return {"success": False, "message": str(e)}

def stop_trading():
    """Stops the trading bot process using the saved PID."""
    if not os.path.exists(PID_FILE):
        return {"success": False, "message": "Trading app is not running (no PID file)."}
    try:
        with open(PID_FILE, "r") as f:
            pid = int(f.read().strip())
        p = psutil.Process(pid)
        p.terminate()
        p.wait(timeout=5)
        if p.is_running():
            p.kill() # Force kill if it doesn't terminate gracefully
        os.remove(PID_FILE)
        logger.info(f"Stopped trading process with PID: {pid}")
        return {"success": True, "message": "Trading app stopped."}
    except psutil.NoSuchProcess:
        os.remove(PID_FILE) # Clean up the stale PID file
        return {"success": False, "message": "Trading app is not running (process not found)."}
    except Exception as e:
        logger.error(f"Error stopping trading process: {e}")
        return {"success": False, "message": "Could not stop the process cleanly."}

def get_trading_status():
    """Checks if the trading bot process is running."""
    if is_running():
        return {"status": "Running"}
    return {"status": "Stopped"}