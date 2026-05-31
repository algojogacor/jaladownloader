import os
import time

import shutil

APP_VERSION = "2.0.0"
START_TIME = time.time()

BASE = os.path.dirname(os.path.abspath(__file__))
DOWNLOADS = os.path.join(BASE, 'downloads')
os.makedirs(DOWNLOADS, exist_ok=True)

termux_path = '/data/data/com.termux/files/usr/bin/yt-dlp'
if os.path.exists(termux_path):
    YTDLP = termux_path
else:
    YTDLP = shutil.which('yt-dlp') or 'yt-dlp'

COOKIES_FILE = os.path.join(BASE, 'instagram_cookies.txt')

# Cache configuration (5 minutes)
CACHE_TTL = 300

# Instaloader credentials
IG_USER = os.environ.get('IG_USER', '')
IG_PASS = os.environ.get('IG_PASS', '')
