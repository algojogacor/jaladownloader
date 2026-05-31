import os
import time
import subprocess
import threading
import logging
from config import BASE, YTDLP

logger = logging.getLogger(__name__)

UPDATED_FILE = os.path.join(BASE, 'yt-dlp-updated.txt')

def get_ytdlp_version():
    try:
        r = subprocess.run([YTDLP, '--version'], capture_output=True, text=True, timeout=10)
        return r.stdout.strip()
    except Exception as e:
        return f"Unknown ({e})"

def get_last_update_time():
    if os.path.exists(UPDATED_FILE):
        try:
            with open(UPDATED_FILE, 'r') as f:
                return float(f.read().strip())
        except Exception as e:
            logger.debug(f"Failed to read yt-dlp-updated.txt: {e}", exc_info=True)
    return 0.0

def run_update():
    try:
        logger.info("Auto-updating yt-dlp...")
        r = subprocess.run([YTDLP, '-U'], capture_output=True, text=True, timeout=300)
        logger.info(f"Update command output: {r.stdout} / {r.stderr}")
        with open(UPDATED_FILE, 'w') as f:
            f.write(str(time.time()))
        logger.info(f"yt-dlp updated successfully. Version: {get_ytdlp_version()}")
    except Exception as e:
        logger.error(f"Failed to update yt-dlp: {e}", exc_info=True)

def updater_loop():
    # Wait a bit after startup to not block initial app startup
    time.sleep(10)
    while True:
        last_update = get_last_update_time()
        if time.time() - last_update > 7 * 86400:
            run_update()
        time.sleep(86400) # Check every 24 hours

def start_updater():
    t = threading.Thread(target=updater_loop, daemon=True)
    t.start()
