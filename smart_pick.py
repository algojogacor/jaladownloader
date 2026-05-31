def pick_best_format(formats, context):
    if not formats:
        return None

    # Context: Audio
    if context == 'audio':
        # Prefer 'mp3' ID
        for f in formats:
            if f.get('id') == 'mp3':
                return f.get('id')
        # Fallback to any audio type format
        for f in formats:
            if f.get('type') == 'audio':
                return f.get('id')
        # General fallback
        return formats[-1].get('id')

    # Context: Share (prefer mp4, max height 720p, filesize < 50MB)
    elif context == 'share':
        limit_50mb = 50 * 1024 * 1024
        
        # 1. Filter video formats that are mp4, <= 720p, and size < 50MB (if size is known)
        valid_shareable = []
        for f in formats:
            if f.get('type') == 'video' and f.get('id') != 'best':
                ext = f.get('ext', '').lower()
                height = f.get('height') or 0
                size = f.get('size') or 0
                if size >= limit_50mb:
                    continue
                if ext == 'mp4' and height <= 720:
                    valid_shareable.append(f)
                    
        if valid_shareable:
            valid_shareable.sort(key=lambda x: x.get('height') or 0, reverse=True)
            return valid_shareable[0].get('id')
            
        # 2. Fallback to any video under 50MB
        valid_any_video = []
        for f in formats:
            if f.get('type') == 'video' and f.get('id') != 'best':
                size = f.get('size') or 0
                if size < limit_50mb:
                    valid_any_video.append(f)
        if valid_any_video:
            valid_any_video.sort(key=lambda x: x.get('height') or 0, reverse=True)
            return valid_any_video[0].get('id')
            
        # 3. Fallback to any video at all (except 'best' helper if others exist)
        video_fmts = [f for f in formats if f.get('type') == 'video' and f.get('id') != 'best']
        if video_fmts:
            video_fmts.sort(key=lambda x: x.get('height') or 0, reverse=True)
            return video_fmts[0].get('id')
            
        return formats[0].get('id')

    # Context: Save (best quality available)
    elif context == 'save':
        # Prefer the 'best' ID helper if available
        for f in formats:
            if f.get('id') == 'best':
                return f.get('id')
        # Otherwise find the highest resolution video format
        video_fmts = [f for f in formats if f.get('type') == 'video']
        if video_fmts:
            video_fmts.sort(key=lambda x: x.get('height') or 0, reverse=True)
            return video_fmts[0].get('id')
        return formats[0].get('id')

    # Default / Fallback: Prefer 720p mp4 if available, otherwise 'best'
    else:
        for f in formats:
            if f.get('type') == 'video' and f.get('ext') == 'mp4' and f.get('height') == 720:
                return f.get('id')
        for f in formats:
            if f.get('id') == 'best':
                return f.get('id')
        return formats[0].get('id')
