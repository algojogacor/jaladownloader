import re
import urllib.request
from html import unescape as html_unescape

def detect_platform(url):
    url_lower = url.lower()
    if 'youtube.com' in url_lower or 'youtu.be' in url_lower:
        return 'youtube'
    if 'tiktok.com' in url_lower:
        return 'tiktok'
    if 'instagram.com' in url_lower:
        return 'instagram'
    if 'pinterest.com' in url_lower or 'pin.it' in url_lower:
        return 'pinterest'
    if 'reddit.com' in url_lower or 'v.redd.it' in url_lower:
        return 'reddit'
    if 'soundcloud.com' in url_lower:
        return 'soundcloud'
    if 'capcut.com' in url_lower:
        return 'capcut'
    if 'bilibili.com' in url_lower or 'b23.tv' in url_lower:
        return 'bilibili'
    if 'twitter.com' in url_lower or 'x.com' in url_lower:
        return 'twitter'
    if 'facebook.com' in url_lower or 'fb.watch' in url_lower:
        return 'facebook'
    return 'unknown'

def parse_image_page(url):
    try:
        req = urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'})
        html = urllib.request.urlopen(req, timeout=15).read().decode('utf-8', errors='ignore')
        img_urls = []
        for p in [r'og:image[^c]*content="([^"]+)"', r'twitter:image[^c]*content="([^"]+)"']:
            m = re.search(p, html)
            if m:
                img_urls.append(('Photo', html_unescape(m.group(1))))
                break
        fmts = []
        for i, (l, u) in enumerate(img_urls):
            s = 0
            if 's640x640' in u:
                hu = u.replace('s640x640','s1080x1080')
                try:
                    hr = urllib.request.Request(hu, method='HEAD')
                    hs = urllib.request.urlopen(hr, timeout=5)
                    if hs.status == 200:
                        u = hu
                        s = int(hs.headers.get('Content-Length',0))
                except:
                    pass
            if not s:
                try:
                    hr = urllib.request.Request(u, method='HEAD')
                    hs = urllib.request.urlopen(hr, timeout=5)
                    s = int(hs.headers.get('Content-Length',0))
                except:
                    pass
            fmts.append({
                'id': f'img_{i}',
                'label': l,
                'ext': 'jpg',
                'height': 0,
                'size': s,
                'type': 'image',
                'direct_url': u
            })
        return fmts
    except:
        return []
