#!/data/data/com.termux/files/usr/bin/python3
"""Web Video Downloader — Flask Entrypoint"""
import os
import time
import uuid
import threading
from flask import Flask, request, render_template, send_file, jsonify

from config import YTDLP, COOKIES_FILE, DOWNLOADS
from cache import get_info_with_cache, set_info_cache
from jobs import jobs, create_job, get_job, pop_job, start_cleaner
from downloader import build_ytdlp_cmd, run, dl_direct, dl_zip
from instagram import ig_via_instaloader
from platforms import detect_platform, parse_image_page
from history import init_db, add_entry, get_history
from updater import start_updater

app = Flask(__name__)
app.config['TEMPLATES_AUTO_RELOAD'] = True

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/privacy')
def privacy():
    return render_template('privacy.html')

@app.route('/terms')
def terms():
    return render_template('terms.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

@app.route('/ping')
def ping():
    from config import APP_VERSION, START_TIME
    return jsonify({
        'status': 'ok',
        'version': APP_VERSION,
        'uptime': int(time.time() - START_TIME)
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
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url:
        return jsonify({'error': 'Isi linknya'}), 400
    
    platform = detect_platform(url)
    
    # Check cache first
    cached = get_info_with_cache(url)
    if cached:
        return jsonify(cached)
    
    # Instagram: try with provided credentials first, then anonymous
    if platform == 'instagram':
        ig_user = data.get('ig_user', '') or ''
        ig_pass = data.get('ig_pass', '') or ''
        ig_result = ig_via_instaloader(url, ig_user, ig_pass)
        if ig_result:
            ig_result['platform'] = 'instagram'
            ig_result['audio_only'] = False
            if 'audio' not in ig_result:
                ig_result['audio'] = []
            has_mp3 = any(f.get('id') == 'mp3' for f in ig_result['audio'])
            if not has_mp3:
                ig_result['audio'].append({'id': 'mp3', 'label': 'MP3 128kbps', 'ext': 'mp3', 'size': 0, 'type': 'audio'})
            set_info_cache(url, ig_result)
            return jsonify(ig_result)
            
    try:
        cmd = [YTDLP, '--dump-json', '--no-playlist', '--no-warnings', '--no-check-certificates', url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(-1, '--cookies')
            cmd.insert(-1, COOKIES_FILE)
        import subprocess
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if r.returncode or not r.stdout:
            ext = parse_image_page(url)
            if ext:
                result = {
                    'title': 'Image',
                    'duration': 0,
                    'thumbnail': '',
                    'formats': ext,
                    'audio': [{'id': 'mp3', 'label': 'MP3 128kbps', 'ext': 'mp3', 'size': 0, 'type': 'audio'}],
                    'platform': platform,
                    'audio_only': False
                }
                set_info_cache(url, result)
                return jsonify(result)
            return jsonify({'error': r.stderr[:300] or 'Gak bisa'}), 400
            
        import json
        info = json.loads(r.stdout.split('\n')[0])
        formats, seen, audio_formats = [], set(), []
        
        is_audio_only = True
        for f in info.get('formats', []):
            vcodec = f.get('vcodec', 'n')
            if vcodec != 'n' and vcodec != 'none':
                is_audio_only = False
                break
                
        for f in info.get('formats', []):
            vc, ac, h, fs = f.get('vcodec', 'n'), f.get('acodec', 'n'), f.get('height', 0), f.get('filesize') or f.get('filesize_approx') or 0
            lbl = f"{h}p" if h else f.get('format_note', '?')
            if vc != 'n' and vc != 'none' and lbl not in seen:
                seen.add(lbl)
                formats.append({
                    'id': f['format_id'],
                    'label': lbl,
                    'ext': f.get('ext', 'mp4'),
                    'height': h,
                    'size': fs,
                    'type': 'video'
                })
                
        seen_audio = set()
        for f in info.get('formats', []):
            acodec = f.get('acodec', 'n')
            if acodec != 'n' and acodec != 'none' and f.get('vcodec', 'n') in ('n', 'none'):
                fs, ab = f.get('filesize') or f.get('filesize_approx') or 0, f.get('abr', 0)
                label = f"{int(ab)}kbps" if ab else 'Audio'
                if label not in seen_audio:
                    seen_audio.add(label)
                    audio_formats.append({
                        'id': f['format_id'],
                        'label': label,
                        'ext': f.get('ext', 'm4a') if f.get('ext') != 'webm' else 'm4a',
                        'size': fs,
                        'type': 'audio'
                    })
                    
        formats.sort(key=lambda x: x['height'] or 0, reverse=True)
        if formats:
            formats.insert(0, {'id': 'best', 'label': 'Best', 'ext': 'mp4', 'height': info.get('height', 0), 'size': 0, 'type': 'video'})
            
        audio_formats.append({'id': 'mp3', 'label': 'MP3 128kbps', 'ext': 'mp3', 'size': 0, 'type': 'audio'})
        
        result_data = {
            'title': info.get('title', '?'),
            'duration': info.get('duration', 0),
            'thumbnail': info.get('thumbnail', ''),
            'formats': formats,
            'audio': audio_formats,
            'platform': platform,
            'audio_only': is_audio_only
        }
        set_info_cache(url, result_data)
        return jsonify(result_data)
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Timeout'}), 408
    except Exception as e:
        return jsonify({'error': str(e)[:300]}), 400

@app.route('/download', methods=['POST'])
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
        
    jid = str(uuid.uuid4())[:8]
    out = os.path.join(DOWNLOADS, f'dl_{jid}')
    
    job = create_job(jid)
    job['title'] = title
    job['platform'] = platform
    job['url'] = url
    
    if ftype == 'zip' and items:
        threading.Thread(target=lambda: dl_zip(jid, items, out), daemon=True).start()
        return jsonify({'job_id': jid})
        
    if direct_url and ftype in ('image', 'video'):
        threading.Thread(target=lambda: dl_direct(jid, direct_url, out), daemon=True).start()
        return jsonify({'job_id': jid})
        
    cmd = build_ytdlp_cmd([YTDLP, '-o', f'{out}.%(ext)s', '--newline'], url)
    if ftype == 'audio' or fmt_id == 'mp3':
        cmd += ['-x', '--audio-format', 'mp3', '--audio-quality', '0']
    elif fmt_id == 'best':
        cmd += ['-f', 'best[ext=mp4]/best']
    else:
        cmd += ['-f', f'{fmt_id}+bestaudio/best']
        
    threading.Thread(target=lambda: run(jid, cmd, out), daemon=True).start()
    return jsonify({'job_id': jid})

@app.route('/status/<jid>')
def status(jid):
    j = get_job(jid)
    if not j:
        return jsonify({'status': 'not_found'})
    return jsonify({
        'status': j['status'],
        'file': j.get('file'),
        'progress': j.get('progress', 0),
        'speed': j.get('speed', ''),
        'eta': j.get('eta', ''),
        'error': j.get('error')
    })

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
            print(f"Error recording history: {e}")
        try:
            os.remove(j['path'])
            fn = j['file']
            print(f'CLEANUP: {fn}')
        except:
            pass
        pop_job(jid)
    return resp

if __name__ == '__main__':
    init_db()
    start_cleaner()
    start_updater()
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
