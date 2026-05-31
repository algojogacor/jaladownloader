import os
import time
import subprocess
import threading
from config import BASE, YTDLP

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
        except:
            pass
    return 0.0

def run_update():
    try:
        print("Auto-updating yt-dlp...")
        r = subprocess.run([YTDLP, '-U'], capture_output=True, text=True, timeout=300)
        print(f"Update command output: {r.stdout} / {r.stderr}")
        with open(UPDATED_FILE, 'w') as f:
            f.write(str(time.time()))
        print(f"yt-dlp updated successfully. Version: {get_ytdlp_version()}")
    except Exception as e:
        print(f"Failed to update yt-dlp: {e}")

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
