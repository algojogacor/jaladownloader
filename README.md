# JalaDownloader

Web video & audio downloader. Paste a link, choose format, download.

Part of the JalaJO ecosystem.

## Stack

- **Backend:** Flask + yt-dlp
- **Frontend:** HTML/CSS (JalaJO design system)
- **Platform support:** YouTube, TikTok, Instagram, Twitter, and more

## Run

```bash
pip install -r requirements.txt
python app.py
```

## Auto-Deploy

This app auto-deploys on an Android phone via Termux:
- Push to `main` → within 60 seconds, phone pulls + restarts Flask
- Uses cron + git polling (no webhook needed)

## Legal

This tool is for downloading content you own or have permission to download.
