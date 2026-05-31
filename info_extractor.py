import os
import json
import subprocess
import time
import logging
from config import YTDLP, COOKIES_FILE
from cache import get_info_with_cache, set_info_cache
from instagram import ig_via_instaloader
from platforms import detect_platform, parse_image_page

logger = logging.getLogger(__name__)

def validate_url(url):
    if not url:
        raise ValueError('URL tidak valid')
    if len(url) > 2048:
        raise ValueError('URL tidak valid')
    if not (url.startswith('http://') or url.startswith('https://')):
        raise ValueError('URL tidak valid')
    try:
        domain = url.split('//', 1)[1].split('/', 1)[0].split('?', 1)[0].split('#', 1)[0]
        if '.' not in domain or domain.startswith('.') or domain.endswith('.'):
            raise ValueError('URL tidak valid')
    except IndexError:
        raise ValueError('URL tidak valid')

def get_url_info(url, ig_user='', ig_pass=''):
    validate_url(url)
    platform = detect_platform(url)
    
    # Check cache first
    cached = get_info_with_cache(url)
    if cached:
        return cached
    
    # Instagram: try with provided credentials first, then anonymous
    if platform == 'instagram':
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
            return ig_result
            
    try:
        cmd = [YTDLP, '--dump-json', '--no-playlist', '--no-warnings', '--no-check-certificates', url]
        if os.path.exists(COOKIES_FILE):
            cmd.insert(-1, '--cookies')
            cmd.insert(-1, COOKIES_FILE)
            
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
                return result
            raise Exception(r.stderr[:300] or 'Gak bisa mengambil info video')
            
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
        return result_data
    except subprocess.TimeoutExpired:
        raise Exception('Timeout saat mengambil info video')
    except Exception as e:
        raise e
