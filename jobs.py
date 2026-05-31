import os
import time
import threading
from config import DOWNLOADS
from cache import evict_stale_cache

jobs = {}

def create_job(jid):
    jobs[jid] = {
        'status': 'processing',
        'file': None,
        'path': None,
        'progress': 0,
        'speed': '',
        'eta': '',
        '_created': time.time()
    }
    return jobs[jid]

def get_job(jid):
    return jobs.get(jid)

def pop_job(jid):
    return jobs.pop(jid, None)

def cleaner():
    while True:
        time.sleep(300)
        now = time.time()
        # Purge stale downloaded files (>30 min)
        if os.path.exists(DOWNLOADS):
            for f in os.listdir(DOWNLOADS):
                fp = os.path.join(DOWNLOADS, f)
                if os.path.isfile(fp) and now - os.path.getmtime(fp) > 1800:
                    try:
                        os.remove(fp)
                    except:
                        pass
        # Purge stale job entries (>30 min), including done/error jobs
        stale_jobs = [k for k, v in jobs.items() if (v.get('_created', 0) and now - v['_created'] > 1800)]
        for k in stale_jobs:
            jobs.pop(k, None)
        # Evict expired cache entries
        try:
            evict_stale_cache()
        except:
            pass

def start_cleaner():
    t = threading.Thread(target=cleaner, daemon=True)
    t.start()
