import os
import re
import time
import subprocess
import urllib.request
import zipfile
import shutil
import logging
from config import YTDLP, COOKIES_FILE, DOWNLOADS
from jobs import jobs

logger = logging.getLogger(__name__)

def build_ytdlp_cmd(base, url):
    """Build yt-dlp command with optimizations for Termux"""
    cmd = base + [
        '--no-playlist', '--no-warnings',
        '--js-runtimes', 'deno', '--remote-components', 'ejs:github',
        '-N', '4',  # 4 parallel fragment downloads
    ]
    if shutil.which('aria2c'):
        cmd += [
            '--downloader', 'aria2c',
            '--downloader', 'dash,m3u8:native',
            '--downloader-args', 'aria2c:-x 8 -s 8 -k 1M --file-allocation=none',
        ]
    else:
        cmd += [
            '--downloader', 'dash,m3u8:native',
        ]
        
    if os.path.exists(COOKIES_FILE):
        cmd += ['--cookies', COOKIES_FILE]
    if 'instagram.com' in url:
        cmd += ['--extractor-args', 'instagram:api=graphql']
    cmd.append(url)
    return cmd

def dl_direct(jid, url, out):
    try:
        ext = url.split('.')[-1].split('?')[0][:4].lower() or 'jpg'
        if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'mov', 'avi'):
            ext = 'jpg'
        fp = f'{out}.{ext}'
        urllib.request.urlretrieve(url, fp)
        job = jobs.get(jid)
        if job:
            job['status'] = 'done'
            job['file'] = f'file_{jid}.{ext}'
            job['path'] = fp
            job['progress'] = 100
            try:
                job['filesize'] = os.path.getsize(fp)
            except Exception as ex:
                logger.debug(f"Failed to get filesize for {fp}: {ex}", exc_info=True)
                job['filesize'] = 0
    except Exception as e:
        job = jobs.get(jid)
        if job:
            job['status'] = 'error'
            job['error'] = str(e)

def dl_zip(jid, items, out):
    temp_dir = os.path.join(DOWNLOADS, f"temp_{jid}")
    try:
        os.makedirs(temp_dir, exist_ok=True)
        filepaths = []
        for idx, item in enumerate(items):
            direct_url = item.get('direct_url')
            ext = item.get('ext', 'jpg')
            if not direct_url:
                continue
            ext = ext.split('?')[0][:4].lower()
            if ext not in ('jpg', 'jpeg', 'png', 'webp', 'gif', 'mp4', 'mov', 'avi'):
                ext = 'jpg'
            filename = f"item_{idx + 1}.{ext}"
            fp = os.path.join(temp_dir, filename)
            urllib.request.urlretrieve(direct_url, fp)
            filepaths.append((fp, filename))
            
            job = jobs.get(jid)
            if job:
                job['progress'] = int(((idx + 1) / len(items)) * 80)
        
        zip_path = f"{out}.zip"
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for fp, filename in filepaths:
                zipf.write(fp, filename)
            
        job = jobs.get(jid)
        if job:
            job['status'] = 'done'
            job['file'] = f'instagram_{jid}.zip'
            job['path'] = zip_path
            job['progress'] = 100
            try:
                job['filesize'] = os.path.getsize(zip_path)
            except Exception as ex:
                logger.debug(f"Failed to get filesize for {zip_path}: {ex}", exc_info=True)
                job['filesize'] = 0
    except Exception as e:
        job = jobs.get(jid)
        if job:
            job['status'] = 'error'
            job['error'] = str(e)
    finally:
        try:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir)
        except Exception as ex:
            logger.debug(f"Failed to cleanup temp dir {temp_dir}: {ex}", exc_info=True)

def run(jid, cmd, out):
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        import threading
        stderr_lines = []
        def read_stderr():
            try:
                for line in proc.stderr:
                    stderr_lines.append(line)
            except Exception as ex:
                logger.debug(f"Error reading process stderr: {ex}", exc_info=True)
                
        t = threading.Thread(target=read_stderr, daemon=True)
        t.start()
        
        if proc.stdout:
            for line in proc.stdout:
                m = re.search(r'(\d+\.?\d*)%', line)
                if m:
                    jobs[jid]['progress'] = float(m.group(1))
                m = re.search(r'(\d+\.?\d*[KMG]iB/s)', line)
                if m:
                    jobs[jid]['speed'] = m.group(1)
                m = re.search(r'ETA\s+(\d+:\d+)', line)
                if m:
                    jobs[jid]['eta'] = m.group(1)
                    
        proc.wait(timeout=600)
        t.join(timeout=5)
        
        if proc.returncode:
            jobs[jid]['status'] = 'error'
            err_msg = "".join(stderr_lines)[:500]
            jobs[jid]['error'] = err_msg or 'yt-dlp returned error code'
            return
        for f in os.listdir(DOWNLOADS):
            if f.startswith(os.path.basename(out)):
                fp = os.path.join(DOWNLOADS, f)
                jobs[jid]['status'] = 'done'
                jobs[jid]['file'] = f
                jobs[jid]['path'] = fp
                jobs[jid]['progress'] = 100
                try:
                    jobs[jid]['filesize'] = os.path.getsize(fp)
                except Exception as ex:
                    logger.debug(f"Failed to get filesize for {fp}: {ex}", exc_info=True)
                    jobs[jid]['filesize'] = 0
                return
        jobs[jid]['status'] = 'error'
        jobs[jid]['error'] = 'File gak ketemu'
    except Exception as e:
        jobs[jid]['status'] = 'error'
        jobs[jid]['error'] = str(e)
