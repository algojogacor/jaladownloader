import time
from config import CACHE_TTL

CACHE = {}

def get_info_with_cache(url):
    now = time.time()
    if url in CACHE and now - CACHE[url]['time'] < CACHE_TTL:
        return CACHE[url]['data']
    return None

def set_info_cache(url, data):
    CACHE[url] = {'data': data, 'time': time.time()}

def evict_stale_cache():
    now = time.time()
    stale_keys = [k for k in list(CACHE) if now - CACHE[k]['time'] > CACHE_TTL * 2]
    for k in stale_keys:
        CACHE.pop(k, None)
