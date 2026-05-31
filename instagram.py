import os
from urllib.parse import urlparse
from config import IG_USER, IG_PASS

INSTA_LOADER = None
try:
    import instaloader
    INSTA_LOADER = True
except:
    INSTA_LOADER = False

def ig_shortcode(url):
    p = urlparse(url).path.rstrip('/').split('/')
    for i, s in enumerate(p):
        if s in ('p', 'reel', 'tv') and i+1 < len(p):
            return p[i+1]
    return p[-1] if p else ''

def ig_via_instaloader(url, user='', pwd=''):
    if not INSTA_LOADER:
        return None
    sc = ig_shortcode(url)
    if not sc:
        return None
    try:
        L = instaloader.Instaloader(save_metadata=False, compress_json=False, 
                                     download_pictures=True, download_videos=True,
                                     max_connection_attempts=2, quiet=True)
        login_user = user or IG_USER
        login_pwd = pwd or IG_PASS
        if login_user and login_pwd:
            try:
                L.load_session_from_file(login_user)
            except:
                try:
                    L.login(login_user, login_pwd)
                    L.save_session_to_file()
                except:
                    pass
        post = instaloader.Post.from_shortcode(L.context, sc)
        fmts = []
        if post.is_video:
            fmts.append({
                'id': 'ig_v',
                'label': 'Video',
                'ext': 'mp4',
                'height': 0,
                'size': 0,
                'type': 'video',
                'direct_url': post.video_url
            })
        if hasattr(post, 'get_sidecar_nodes'):
            for i, n in enumerate(post.get_sidecar_nodes()):
                e = 'mp4' if n.is_video else 'jpg'
                u = n.video_url if n.is_video else n.display_url
                fmts.append({
                    'id': f'ig_{i}',
                    'label': f'{"Video" if n.is_video else "Photo"} {i+1}',
                    'ext': e,
                    'height': 0,
                    'size': 0,
                    'type': 'video' if n.is_video else 'image',
                    'direct_url': u
                })
        elif not post.is_video:
            fmts.append({
                'id': 'ig_p',
                'label': 'Photo',
                'ext': 'jpg',
                'height': 0,
                'size': 0,
                'type': 'image',
                'direct_url': post.url
            })
        if fmts:
            return {
                'title': post.title or f'IG: {post.owner_username}',
                'duration': post.video_duration or 0,
                'thumbnail': post.url,
                'formats': fmts,
                'audio': []
            }
        return {
            'title': post.title or 'Photo',
            'duration': 0,
            'thumbnail': post.url,
            'formats': [{
                'id': 'ig',
                'label': 'Photo',
                'ext': 'jpg',
                'height': 0,
                'size': 0,
                'type': 'image',
                'direct_url': post.url
            }],
            'audio': []
        }
    except Exception as e:
        return None
