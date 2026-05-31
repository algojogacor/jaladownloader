# JalaDownloader 📥

JalaDownloader is a fast, lightweight, and modern video and audio downloader web application and Telegram bot. It features automatic media format extraction, parallel fragment downloading, sequential batch processing, and an automated background update scheduler.

Part of the **JalaJO** ecosystem.

---

## 🛠️ Technology Stack

- **Web Framework:** Flask
- **Extraction Engine:** yt-dlp & Instaloader
- **Telegram Bot:** python-telegram-bot
- **Rate Limiting:** Flask-Limiter
- **Database:** SQLite (local history logging)
- **Design System:** JalaJO Dark/Light CSS design token system

---

## 📁 Module Structure

- **[app.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/app.py)** — Flask application entrypoint serving web pages, REST API endpoints, and starting background processes.
- **[bot.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/bot.py)** — Telegram Bot controller enforcing per-user rate limits, cancel options, and inline download format keyboards.
- **[cache.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/cache.py)** — In-memory query cache layer with time-to-live (TTL) expiration.
- **[config.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/config.py)** — Application environment, global configuration values, paths, and metadata constants.
- **[download_queue.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/download_queue.py)** — Threaded job coordinator managing active/queued downloads concurrently.
- **[downloader.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/downloader.py)** — Direct file downloader, ZIP carousel assembler, and subprocess wrapper parsing yt-dlp output streams in real-time.
- **[history.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/history.py)** — SQLite wrapper storing and fetching the most recent 100 successful download history entries.
- **[info_extractor.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/info_extractor.py)** — Metadata retriever executing yt-dlp json-dumps with inline input URL syntax validation.
- **[instagram.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/instagram.py)** — Instaloader scraper fetching Reels, Posts, and Carousel items using user-session files.
- **[jobs.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/jobs.py)** — Thread-safe jobs catalog and background garbage collector purging temp files and old jobs.
- **[platforms.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/platforms.py)** — Utility functions matching URL regular expressions and scraping direct image headers.
- **[smart_pick.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/smart_pick.py)** — Optimization logic choosing the best recommended format depending on download intent (save, share, or audio).
- **[updater.py](file:///wsl.localhost/Ubuntu/home/arya_rizky/projects/jaladownloader/updater.py)** — Daemon loop checking and upgrading the local yt-dlp executable once a week.

---

## 🌐 Supported Platforms

Supports extracting and downloading files from almost any site including:
- **YouTube** (with full 4K resolutions and MP3 audio converting options)
- **TikTok** (without watermarks)
- **Instagram** (Reels, image posts, and multiple carousel items zipped dynamically)
- **Twitter / X**
- **Facebook**
- **Pinterest**
- **Reddit**
- **SoundCloud**
- **Capcut, Bilibili**, and more.

---

## 🚀 How to Run

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
2. Launch the application:
   ```bash
   python app.py
   ```

---

## 🔑 Environment Variables

- `TELEGRAM_BOT_TOKEN` — Unique token provided by BotFather to authenticate and run the Telegram bot.
- `BASE_URL` — The public-facing HTTP address of the Flask web server (used by the Telegram bot to build direct links for files over 50MB).
- `IG_USER` — Default Instagram username used by Instaloader to pull carousel / private media post data.
- `IG_PASS` — Password corresponding to the `IG_USER` login.

---

## 📱 Auto-Deploy Setup (Termux + Git Polling)

This application is optimized to run continuously on an Android phone inside Termux:
1. A cron job regularly runs a synchronization bash script every 60 seconds.
2. The script polls the remote repository using `git pull`.
3. If new changes are detected, it updates the repository and automatically restarts the local Flask process.

---

## 🔌 API Endpoints

- **`GET /`** — Main web interface (JalaDownloader Search).
- **`GET /status-page`** — Monitoring dashboard displaying server status, uptime, active/queued downloads, and engine details.
- **`GET /ping`** — Health check endpoint returning system version, uptime, queue sizes, and cached download folder sizes.
- **`GET /history`** — Returns the recent download logs.
- **`GET /status/<jid>`** — Queries real-time download status, speeds, ETAs, and completion info for a job ID.
- **`GET /file/<jid>`** — Serves the completed video/audio file and schedules temporary file cleanup.
- **`GET /admin/yt-dlp-version`** — Queries the installed yt-dlp engine version and date of last update.
- **`POST /info`** — Returns metadata (title, thumbnails, platforms, and available formats) for a given video URL.
- **`POST /download`** — Submits a single URL download job to the queue.
- **`POST /download-zip`** — Submits an Instagram Carousel ZIP download job to the queue.
