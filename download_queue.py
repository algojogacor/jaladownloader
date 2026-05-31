import os
import threading
import logging
from config import YTDLP, DOWNLOADS

logger = logging.getLogger(__name__)
from jobs import jobs, create_job, get_queue_position
from downloader import build_ytdlp_cmd, run, dl_direct, dl_zip

MAX_CONCURRENT = 2
queue_lock = threading.Lock()

def enqueue_job(jid, url, fmt_id, ftype, direct_url, title, platform, items):
    with queue_lock:
        job = create_job(jid)
        job['title'] = title
        job['platform'] = platform
        job['url'] = url
        
        out = os.path.join(DOWNLOADS, f'dl_{jid}')
        
        cmd = []
        if ftype != 'zip' and not (direct_url and ftype in ('image', 'video')):
            cmd = build_ytdlp_cmd([YTDLP, '-o', f'{out}.%(ext)s', '--newline'], url)
            if ftype == 'audio' or fmt_id == 'mp3':
                cmd += ['-x', '--audio-format', 'mp3', '--audio-quality', '0']
            elif fmt_id == 'best':
                cmd += ['-f', 'best[ext=mp4]/best']
            else:
                cmd += ['-f', f'{fmt_id}+bestaudio/best']
                
        active_count = sum(1 for j in jobs.values() if j.get('status') == 'processing')
        
        if active_count >= MAX_CONCURRENT:
            job['status'] = 'queued'
            job['task'] = {
                'ftype': ftype,
                'out': out,
                'items': items,
                'direct_url': direct_url,
                'cmd': cmd
            }
            return {'queued': True, 'position': get_queue_position(jid), 'job_id': jid}
        else:
            job['status'] = 'processing'
            start_task_thread(jid, ftype, out, items, direct_url, cmd)
            return {'queued': False, 'job_id': jid}

def start_task_thread(jid, ftype, out, items, direct_url, cmd):
    # Set status to processing before thread execution
    job = jobs.get(jid)
    if job:
        job['status'] = 'processing'
        
    if ftype == 'zip' and items:
        threading.Thread(target=lambda: dl_zip(jid, items, out), daemon=True).start()
    elif direct_url and ftype in ('image', 'video'):
        threading.Thread(target=lambda: dl_direct(jid, direct_url, out), daemon=True).start()
    else:
        threading.Thread(target=lambda: run(jid, cmd, out), daemon=True).start()
