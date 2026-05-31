#!/data/data/com.termux/files/usr/bin/python3
"""Web Video Downloader — Flask Entrypoint"""
import os
import time
import uuid
import threading
import logging
from flask import Flask, request, render_template, send_file, jsonify

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()  # also print to console
    ]
)
logger = logging.getLogger(__name__)
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_limiter.errors import RateLimitExceeded

from config import DOWNLOADS
from jobs import jobs, get_job, pop_job, start_cleaner
from info_extractor import get_url_info
from download_queue import enqueue_job, start_task_thread
from history import init_db, add_entry, get_history
from updater import start_updater

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# Initialize Flask-Limiter
limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=["60 per minute"]
)

@app.errorhandler(RateLimitExceeded)
def ratelimit_handler(e):
    return jsonify({"error": "Terlalu banyak request, coba lagi sebentar"}), 429

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/status-page')
def status_page():
    return render_template('status.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

# Cache downloads folder size
_downloads_size_cache = None
_downloads_size_last_checked = 0

@app.route('/ping')
def ping():
    from config import APP_VERSION, START_TIME
    active_jobs = sum(1 for j in jobs.values() if j.get('status') == 'processing')
    queued_jobs = sum(1 for j in jobs.values() if j.get('status') == 'queued')
    
    from cache import CACHE
    cache_size = len(CACHE)
    
    global _downloads_size_cache, _downloads_size_last_checked
    current_time = time.time()
    if _downloads_size_cache is None or current_time - _downloads_size_last_checked > 30:
        total_size = 0
        if os.path.exists(DOWNLOADS):
            for dirpath, dirnames, filenames in os.walk(DOWNLOADS):
                for f in filenames:
                    fp = os.path.join(dirpath, f)
                    try:
                        total_size += os.path.getsize(fp)
                    except:
                        pass
        _downloads_size_cache = round(total_size / (1024 * 1024), 2)
        _downloads_size_last_checked = current_time
        
    downloads_dir_size = _downloads_size_cache
    
    return jsonify({
        'status': 'ok',
        'version': APP_VERSION,
        'uptime': int(time.time() - START_TIME),
        'active_jobs': active_jobs,
        'queued_jobs': queued_jobs,
        'cache_size': cache_size,
        'downloads_dir_size': downloads_dir_size
    })

@app.route('/history')
def history_route():
    return jsonify(get_history())

@app.route('/admin/yt-dlp-version')
def admin_ytdlp_version():
    from updater import get_ytdlp_version, get_last_update_time
    last_update = get_last_update_time()
    last_updated_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_update)) if last_update > 0 else 'Never'
    return jsonify({
        'version': get_ytdlp_version(),
        'last_updated': last_updated_str
    })

@app.route('/info', methods=['POST'])
@limiter.limit("20 per minute")
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Isi linknya'}), 400
    
    try:
        ig_user = data.get('ig_user', '') or ''
        ig_pass = data.get('ig_pass', '') or ''
        result_data = get_url_info(url, ig_user, ig_pass)
        
        # Smart pick best formats for each context
        from smart_pick import pick_best_format
        all_formats = result_data.get('formats', []) + result_data.get('audio', [])
        recommended_format_id = pick_best_format(all_formats, data.get('context', 'save'))
        recommendations = {
            'save': pick_best_format(all_formats, 'save'),
            'share': pick_best_format(all_formats, 'share'),
            'audio': pick_best_format(all_formats, 'audio')
        }
        
        res = dict(result_data)
        res['recommended_format_id'] = recommended_format_id
        res['recommendations'] = recommendations
        return jsonify(res)
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download', methods=['POST'])
@limiter.limit("10 per minute")
def start():
    data = request.get_json()
    url = data.get('url', '').strip()
    fmt_id = data.get('format_id', 'best')
    ftype = data.get('type', 'video')
    direct_url = data.get('direct_url', '')
    title = data.get('title', 'Unknown')
    platform = data.get('platform', 'unknown')
    items = data.get('items', [])
    
    if not url:
        return jsonify({'error': 'Isi linknya'}), 400
    try:
        from info_extractor import validate_url
        validate_url(url)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
        
    jid = str(uuid.uuid4())[:8]
    res = enqueue_job(jid, url, fmt_id, ftype, direct_url, title, platform, items)
    return jsonify(res)

@app.route('/download-zip', methods=['POST'])
@limiter.limit("5 per minute")
def start_zip():
    data = request.get_json()
    url = data.get('url', '').strip()
    fmt_id = data.get('format_id', 'best')
    ftype = data.get('type', 'video')
    direct_url = data.get('direct_url', '')
    title = data.get('title', 'Unknown')
    platform = data.get('platform', 'unknown')
    items = data.get('items', [])
    
    if not url:
        return jsonify({'error': 'Isi linknya'}), 400
    try:
        from info_extractor import validate_url
        validate_url(url)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
        
    jid = str(uuid.uuid4())[:8]
    res = enqueue_job(jid, url, fmt_id, ftype, direct_url, title, platform, items)
    return jsonify(res)

@app.route('/status/<jid>')
def status(jid):
    j = get_job(jid)
    if not j:
        return jsonify({'status': 'not_found'})
    resp = {
        'status': j['status'],
        'file': j.get('file'),
        'progress': j.get('progress', 0),
        'speed': j.get('speed', ''),
        'eta': j.get('eta', ''),
        'error': j.get('error')
    }
    if j['status'] == 'queued':
        from jobs import get_queue_position
        resp['position'] = get_queue_position(jid)
    return jsonify(resp)

@app.route('/file/<jid>')
def send_file_route(jid):
    j = get_job(jid)
    if not j or not j.get('path'):
        return 'File gak ada', 404
        
    resp = send_file(j['path'], download_name=j['file'])
    @resp.call_on_close
    def clean():
        try:
            add_entry(
                title=j.get('title', 'Unknown'),
                platform=j.get('platform', 'unknown'),
                url=j.get('url', ''),
                filename=j.get('file', ''),
                filesize=j.get('filesize', 0)
            )
        except Exception as e:
            logger.error(f"Error recording history: {e}")
        try:
            os.remove(j['path'])
            fn = j['file']
            logger.info(f'CLEANUP: {fn}')
        except Exception as ex:
            logger.debug(f"Cleanup remove failed: {ex}", exc_info=True)
        pop_job(jid)
    return resp

def scheduler_loop():
    while True:
        time.sleep(3)
        # Skip job check if there are no queued jobs
        if not any(j.get('status') == 'queued' for j in jobs.values()):
            continue
            
        # Count active jobs where status == 'processing'
        active_count = sum(1 for j in jobs.values() if j.get('status') == 'processing')
        if active_count < 2: # MAX_CONCURRENT = 2
            # Promote oldest queued job
            queued_jids = [k for k, v in jobs.items() if v.get('status') == 'queued']
            if queued_jids:
                queued_jids.sort(key=lambda k: jobs[k].get('_created', 0))
                next_jid = queued_jids[0]
                next_job = jobs[next_jid]
                task = next_job.get('task')
                if task:
                    next_job['status'] = 'processing'
                    start_task_thread(
                        jid=next_jid,
                        ftype=task.get('ftype'),
                        out=task.get('out'),
                        items=task.get('items'),
                        direct_url=task.get('direct_url'),
                        cmd=task.get('cmd')
                    )

if __name__ == '__main__':
    init_db()
    start_cleaner()
    start_updater()
    
    # Start download queue scheduler
    threading.Thread(target=scheduler_loop, daemon=True).start()
    
    # Start Telegram Bot if token is available
    try:
        from bot import start_bot
        start_bot()
    except Exception as e:
        logger.error(f"Failed to load Telegram bot: {e}")
        
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
