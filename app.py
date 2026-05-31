#!/data/data/com.termux/files/usr/bin/python3
"""Web Video Downloader — Flask + yt-dlp + Instaloader"""
import os, threading, time, uuid, subprocess, json, re
import urllib.request
from urllib.parse import urlparse
from html import unescape as html_unescape

# ── Instaloader (Instagram, no cookies needed) ──
IG_USER = os.environ.get('IG_USER', '')
IG_PASS = os.environ.get('IG_PASS', '')
INSTA_LOADER = None
try:
    import instaloader
    INSTA_LOADER = True
except:
    INSTA_LOADER = False

def ig_shortcode(url):
    p = urlparse(url).path.rstrip('/').split('/')
    for i, s in enumerate(p):
        if s in ('p','reel','tv') and i+1 < len(p): return p[i+1]
    return p[-1] if p else ''

def ig_via_instaloader(url, user='', pwd=''):
    if not INSTA_LOADER: return None
    sc = ig_shortcode(url)
    if not sc: return None
    try:
        L = instaloader.Instaloader(save_metadata=False, compress_json=False, 
                                     download_pictures=True, download_videos=True,
                                     max_connection_attempts=2, quiet=True)
        # Try provided credentials first, then env vars
        login_user = user or IG_USER
        login_pwd = pwd or IG_PASS
        if login_user and login_pwd:
            try: L.load_session_from_file(login_user)
            except:
                try: L.login(login_user, login_pwd); L.save_session_to_file()
                except: pass
        post = instaloader.Post.from_shortcode(L.context, sc)
        fmts = []
        if post.is_video:
            fmts.append({'id':'ig_v','label':'Video','ext':'mp4','height':0,'size':0,'type':'video','direct_url':post.video_url})
        if hasattr(post, 'get_sidecar_nodes'):
            for i, n in enumerate(post.get_sidecar_nodes()):
                e = 'mp4' if n.is_video else 'jpg'
                u = n.video_url if n.is_video else n.display_url
                fmts.append({'id':f'ig_{i}','label':f'{"Video"if n.is_video else"Photo"}{i+1}','ext':e,'height':0,'size':0,'type':'video'if n.is_video else'image','direct_url':u})
        elif not post.is_video:
            fmts.append({'id':'ig_p','label':'Photo','ext':'jpg','height':0,'size':0,'type':'image','direct_url':post.url})
        if fmts:
            return {'title':post.title or f'IG: {post.owner_username}','duration':post.video_duration or 0,'thumbnail':post.url,'formats':fmts,'audio':[]}
        return {'title':post.title or 'Photo','duration':0,'thumbnail':post.url,'formats':[{'id':'ig','label':'Photo','ext':'jpg','height':0,'size':0,'type':'image','direct_url':post.url}],'audio':[]}
    except: return None

# ── Image parse fallback ──
def parse_image_page(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        img_urls = []
        for p in [r'og:image[^c]*content="([^"]+)"', r'twitter:image[^c]*content="([^"]+)"']:
            m = re.search(p, html)
            if m: img_urls.append(('Photo', html_unescape(m.group(1)))); break
        fmts = []
        for i, (l, u) in enumerate(img_urls):
            s = 0
            if 's640x640' in u:
                hu = u.replace('s640x640','s1080x1080')
                try:
                    hr = urllib.request.Request(hu, method='HEAD')
                    hs = urllib.request.urlopen(hr, timeout=5)
                    if hs.status == 200: u = hu; s = int(hs.headers.get('Content-Length',0))
                except: pass
            if not s:
                try:
                    hr = urllib.request.Request(u, method='HEAD')
                    hs = urllib.request.urlopen(hr, timeout=5)
                    s = int(hs.headers.get('Content-Length',0))
                except: pass
            fmts.append({'id':f'img_{i}','label':l,'ext':'jpg','height':0,'size':s,'type':'image','direct_url':u})
        return fmts
    except: return []

from flask import Flask, request, render_template, send_file, jsonify

app = Flask(__name__)
BASE = os.path.dirname(__file__)
DOWNLOADS = os.path.join(BASE, 'downloads')
os.makedirs(DOWNLOADS, exist_ok=True)
jobs = {}
YTDLP = '/data/data/com.termux/files/usr/bin/yt-dlp'
COOKIES_FILE = os.path.join(BASE, 'instagram_cookies.txt')

# Cache for info endpoint (5 menit)
CACHE = {}
CACHE_TTL = 300

def get_info_with_cache(url):
    now = time.time()
    if url in CACHE and now - CACHE[url]['time'] < CACHE_TTL:
        return CACHE[url]['data']
    return None

def set_info_cache(url, data):
    CACHE[url] = {'data': data, 'time': time.time()}

def build_ytdlp_cmd(base, url):
    """Build yt-dlp command with optimizations for Termux"""
    cmd = base + [
        '--no-playlist', '--no-warnings',
        '--js-runtimes', 'deno', '--remote-components', 'ejs:github',
        '-N', '4',  # 4 parallel fragment downloads
        '--downloader', 'aria2c',
        '--downloader', 'dash,m3u8:native',
        '--downloader-args', 'aria2c:-x 8 -s 8 -k 1M --file-allocation=none',
    ]
    if os.path.exists(COOKIES_FILE):
        cmd += ['--cookies', COOKIES_FILE]
    if 'instagram.com' in url:
        cmd += ['--extractor-args', 'instagram:api=graphql']
    cmd.append(url)
    return cmd

@app.route('/')
def index(): return render_template('index.html')
@app.route('/privacy')
def privacy(): return render_template('privacy.html')
@app.route('/terms')
def terms(): return render_template('terms.html')
@app.route('/contact')
def contact(): return render_template('contact.html')

# ── Info endpoint ──
@app.route('/info', methods=['POST'])
def get_info():
    data = request.get_json()
    url = data.get('url', '').strip()
    if not url: return jsonify({'error':'Isi linknya'}), 400
    
    # Instagram: try with provided credentials first, then anonymous
    if 'instagram.com' in url:
        ig_user = data.get('ig_user', '') or ''
        ig_pass = data.get('ig_pass', '') or ''
        ig_result = ig_via_instaloader(url, ig_user, ig_pass)
        if ig_result: return jsonify(ig_result)
    
    # Check cache first
    cached = get_info_with_cache(url)
    if cached:
        return jsonify(cached)
    
    try:
        cmd = [YTDLP, '--dump-json', '--no-playlist', '--no-warnings', '--no-check-certificates', url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(-1, '--cookies'); cmd.insert(-1, COOKIES_FILE)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=45)
        if r.returncode or not r.stdout:
            ext = parse_image_page(url)
            if ext:
                result = {'title':'Image','duration':0,'thumbnail':'','formats':ext,'audio':[]}
                set_info_cache(url, result)
                return jsonify(result)
            return jsonify({'error':r.stderr[:300] or 'Gak bisa'}), 400
        info = json.loads(r.stdout.split('\n')[0])
        if r.returncode or not r.stdout:
            # Fallback
            ext = parse_image_page(url)
            if ext: return jsonify({'title':'Image','duration':0,'thumbnail':'','formats':ext,'audio':[]})
            return jsonify({'error':r.stderr[:300] or 'Gak bisa'}), 400
        info = json.loads(r.stdout.split('\n')[0])
        formats, seen, audio_formats = [], set(), []
        for f in info.get('formats',[]):
            vc, ac, h, fs = f.get('vcodec','n'), f.get('acodec','n'), f.get('height',0), f.get('filesize') or f.get('filesize_approx') or 0
            lbl = f"{h}p" if h else f.get('format_note','?')
            if vc != 'n' and lbl not in seen:
                seen.add(lbl)
                formats.append({'id':f['format_id'],'label':lbl,'ext':f.get('ext','mp4'),'height':h,'size':fs,'type':'video'})
        for f in info.get('formats',[]):
            if f.get('acodec','n')!='n' and f.get('vcodec')=='n':
                fs, ab = f.get('filesize') or f.get('filesize_approx') or 0, f.get('abr',0)
                audio_formats.append({'id':f['format_id'],'label':f"{int(ab)}kbps" if ab else 'Audio','ext':'m4a','size':fs,'type':'audio'}); break
        formats.sort(key=lambda x: x['height'] or 0, reverse=True)
        formats.insert(0,{'id':'best','label':'Best','ext':'mp4','height':info.get('height',0),'size':0,'type':'video'})
        audio_formats.append({'id':'mp3','label':'MP3 128kbps','ext':'mp3','size':0,'type':'audio'})
        result_data = {'title':info.get('title','?'),'duration':info.get('duration',0),'thumbnail':info.get('thumbnail',''),'formats':formats,'audio':audio_formats}
        set_info_cache(url, result_data)
        return jsonify(result_data)
    except subprocess.TimeoutExpired: return jsonify({'error':'Timeout'}), 408
    except Exception as e: return jsonify({'error':str(e)[:300]}), 400

# ── Download ──
@app.route('/download', methods=['POST'])
def start():
    data = request.get_json()
    url = data.get('url', '').strip()
    fmt_id = data.get('format_id', 'best')
    ftype = data.get('type', 'video')
    direct_url = data.get('direct_url', '')
    if not url: return jsonify({'error':'Isi linknya'}), 400
    jid = str(uuid.uuid4())[:8]
    out = os.path.join(DOWNLOADS, f'dl_{jid}')
    jobs[jid] = {'status':'processing','file':None,'path':None,'progress':0}
    
    # Instagram direct URL: try instaloader first if credentials provided
    if 'instagram.com' in url:
        ig_user = data.get('ig_user', '') or ''
        ig_pass = data.get('ig_pass', '') or ''
        ig_result = ig_via_instaloader(url, ig_user, ig_pass)
        if ig_result and ig_result.get('formats'):
            fmt = ig_result['formats'][0]
            if fmt.get('direct_url'):
                threading.Thread(target=lambda: dl_direct(jid, fmt['direct_url'], out), daemon=True).start()
                return jsonify({'job_id':jid})
    
    if direct_url and ftype in ('image','video'):
        threading.Thread(target=lambda: dl_direct(jid, direct_url, out), daemon=True).start()
        return jsonify({'job_id':jid})
    
    cmd = build_ytdlp_cmd([YTDLP, '-o', f'{out}.%(ext)s', '--newline'], url)
    # Remove --dump-json from build_ytdlp_cmd for download mode
    # And add format seletion
    if ftype == 'audio' or fmt_id == 'mp3': cmd += ['-x', '--audio-format', 'mp3', '--audio-quality', '0']
    elif fmt_id == 'best': cmd += ['-f', 'best[ext=mp4]/best']
    else: cmd += ['-f', f'{fmt_id}+bestaudio/best']
    threading.Thread(target=lambda: run(jid, cmd, out), daemon=True).start()
    return jsonify({'job_id':jid})

def dl_direct(jid, url, out):
    try:
        ext = url.split('.')[-1].split('?')[0][:4].lower() or 'jpg'
        if ext not in ('jpg','jpeg','png','webp','gif','mp4','mov','avi'): ext = 'jpg'
        fp = f'{out}.{ext}'
        urllib.request.urlretrieve(url, fp)
        jobs[jid]['status']='done'; jobs[jid]['file']=f'file_{jid}.{ext}'; jobs[jid]['path']=fp; jobs[jid]['progress']=100
    except Exception as e: jobs[jid]['status']='error'; jobs[jid]['error']=str(e)

def run(jid, cmd, out):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
        if r.returncode: jobs[jid]['status']='error'; jobs[jid]['error']=r.stderr[:500]; return
        for f in os.listdir(DOWNLOADS):
            if f.startswith(os.path.basename(out)):
                jobs[jid]['status']='done'; jobs[jid]['file']=f; jobs[jid]['path']=os.path.join(DOWNLOADS,f); jobs[jid]['progress']=100
                return
        jobs[jid]['status']='error'; jobs[jid]['error']='File gak ketemu'
    except Exception as e: jobs[jid]['status']='error'; jobs[jid]['error']=str(e)

@app.route('/status/<jid>')
def status(jid):
    j = jobs.get(jid)
    if not j: return jsonify({'status':'not_found'})
    return jsonify({'status':j['status'],'file':j.get('file'),'progress':j.get('progress',0),'error':j.get('error')})

@app.route('/file/<jid>')
def send_file_route(jid):
    j = jobs.get(jid)
    if not j or not j.get('path'): return 'File gak ada', 404
    resp = send_file(j['path'], download_name=j['file'])
    @resp.call_on_close
    def clean():
        try:
            os.remove(j['path'])
            fn=j['file']
            print(f'CLEANUP: {fn}')
        except:
            pass
    return resp

def cleaner():
    while True:
        time.sleep(300)
        now = time.time()
        for f in os.listdir(DOWNLOADS):
            fp = os.path.join(DOWNLOADS,f)
            if os.path.isfile(fp) and now - os.path.getmtime(fp) > 1800:
                try: os.remove(fp)
                except: pass
threading.Thread(target=cleaner, daemon=True).start()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
app.config['TEMPLATES_AUTO_RELOAD'] = True

# auto-deploy test
