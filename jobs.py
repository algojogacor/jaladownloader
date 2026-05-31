import os
import time
import threading
import logging
from config import DOWNLOADS
from cache import evict_stale_cache

logger = logging.getLogger(__name__)

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
        # Purge stale downloaded files and directories (>30 min)
        if os.path.exists(DOWNLOADS):
            for f in os.listdir(DOWNLOADS):
                fp = os.path.join(DOWNLOADS, f)
                try:
                    if os.path.isfile(fp) and now - os.path.getmtime(fp) > 1800:
                        os.remove(fp)
                    elif os.path.isdir(fp) and f.startswith('temp_') and now - os.path.getmtime(fp) > 1800:
                        import shutil
                        shutil.rmtree(fp)
                except Exception as e:
                    logger.debug(f"Cleaner failed to remove file/dir {fp}: {e}", exc_info=True)
        # Purge stale job entries (>30 min), including done/error jobs
        stale_jobs = [k for k, v in jobs.items() if (v.get('_created', 0) and now - v['_created'] > 1800)]
        for k in stale_jobs:
            jobs.pop(k, None)
        # Evict expired cache entries
        try:
            evict_stale_cache()
        except Exception as e:
            logger.debug(f"Cleaner failed to evict stale cache: {e}", exc_info=True)

def get_queue_position(jid):
    queued = [k for k, v in jobs.items() if v.get('status') == 'queued']
    queued.sort(key=lambda k: jobs[k].get('_created', 0))
    try:
        return queued.index(jid) + 1
    except ValueError:
        return 0

def start_cleaner():
    t = threading.Thread(target=cleaner, daemon=True)
    t.start()
