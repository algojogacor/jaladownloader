import os
import asyncio
import threading
import uuid
import html
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes

from info_extractor import get_url_info
from download_queue import enqueue_job
from jobs import get_job, get_queue_position, pop_job
from history import add_entry

BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')
sessions = {} # session_id -> metadata cache

def get_size_str(size):
    if not size or size <= 0:
        return ""
    u = ['B', 'KB', 'MB', 'GB']
    i = 0
    s = float(size)
    while s >= 1024 and i < len(u) - 1:
        s /= 1024
        i += 1
    return f" • {s:.1f} {u[i]}"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Selamat datang di JalaDownloader Bot! 📥\n\n"
        "Kirim link video/audio dari platform apa saja (YouTube, TikTok, Instagram, dll) "
        "dan bot akan membantu mengunduhnya."
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Platform yang didukung:\n"
        "- YouTube (Video & Audio)\n"
        "- TikTok (No Watermark)\n"
        "- Instagram (Reels, Posts, Carousel)\n"
        "- Twitter / X\n"
        "- Facebook\n"
        "- Pinterest\n"
        "- Reddit\n"
        "- SoundCloud\n"
        "- Capcut, Bilibili, dll."
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text.strip()
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("Silakan kirim link URL yang valid (dimulai dengan http:// atau https://).")
        return
        
    status_msg = await update.message.reply_text("🔍 Fetching info...")
    
    # Run the blocking get_url_info inside executor to keep the event loop responsive
    loop = asyncio.get_running_loop()
    try:
        result = await loop.run_in_executor(None, lambda: get_url_info(url))
        
        # Save search metadata in temporary session cache
        jid = str(uuid.uuid4())[:8]
        sessions[jid] = {
            'url': url,
            'title': result.get('title', 'Unknown'),
            'platform': result.get('platform', 'unknown'),
            'formats': result.get('formats', []) + result.get('audio', []),
            'duration': result.get('duration', 0)
        }
        
        # Build keyboard layout
        keyboard = []
        
        # Instagram Carousel support
        is_carousel = result.get('platform') == 'instagram' and len([f for f in sessions[jid]['formats'] if f.get('id', '').startswith('ig_')]) > 1
        if is_carousel:
            keyboard.append([InlineKeyboardButton("📦 Download All as ZIP", callback_data=f"zip:{jid}")])
            
        row = []
        for f in sessions[jid]['formats']:
            size_str = get_size_str(f.get('size', 0))
            label = f"{f.get('label', '')} {f.get('ext', '')}{size_str}"
            btn = InlineKeyboardButton(label, callback_data=f"dl:{jid}:{f['id']}")
            row.append(btn)
            if len(row) == 2:
                keyboard.append(row)
                row = []
        if row:
            keyboard.append(row)
            
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        duration_str = ""
        if result.get('duration'):
            m = result['duration'] // 60
            s = result['duration'] % 60
            duration_str = f" • ⏱️ {m}m {s}s"
            
        text = f"📹 <b>{html.escape(result.get('title', 'Unknown'))}</b>\n🌐 Platform: {result.get('platform', 'unknown').upper()}{duration_str}\n\nPilih format unduhan di bawah ini:"
        await status_msg.edit_text(text, reply_markup=reply_markup, parse_mode="HTML")
        
    except Exception as e:
        await status_msg.edit_text(f"❌ Gagal mengambil info: {str(e)[:300]}")

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if not data:
        return
        
    if data.startswith("dl:") or data.startswith("zip:"):
        parts = data.split(":")
        action = parts[0]
        session_id = parts[1]
        
        session = sessions.get(session_id)
        if not session:
            await query.edit_message_text("❌ Sesi pencarian ini telah kedaluwarsa. Silakan kirim ulang link Anda.")
            return
            
        url = session['url']
        title = session['title']
        platform = session['platform']
        download_jid = str(uuid.uuid4())[:8]
        
        if action == "zip":
            ftype = "zip"
            fmt_id = "zip"
            direct_url = ""
            items = [{'direct_url': f['direct_url'], 'ext': f['ext']} for f in session['formats'] if f.get('id', '').startswith('ig_')]
        else:
            fmt_id = parts[2]
            selected_fmt = None
            for f in session['formats']:
                if f.get('id') == fmt_id:
                    selected_fmt = f
                    break
                    
            if not selected_fmt:
                await query.edit_message_text("❌ Format tidak valid.")
                return
                
            ftype = selected_fmt.get('type', 'video')
            direct_url = selected_fmt.get('direct_url', '')
            items = []
            
        await query.edit_message_text("⬇️ Menghubungi server...")
        
        # Enqueue downloading task
        res = enqueue_job(
            jid=download_jid,
            url=url,
            fmt_id=fmt_id,
            ftype=ftype,
            direct_url=direct_url,
            title=title,
            platform=platform,
            items=items
        )
        
        # Status polling
        last_status_text = ""
        done = False
        while not done:
            await asyncio.sleep(1.5)
            job = get_job(download_jid)
            if not job:
                await query.edit_message_text("❌ Unduhan tidak ditemukan.")
                return
                
            status = job.get('status')
            if status == 'queued':
                pos = get_queue_position(download_jid)
                status_text = f"⏳ Antrian posisi #{pos}, sabar ya..."
                if status_text != last_status_text:
                    await query.edit_message_text(status_text)
                    last_status_text = status_text
            elif status == 'processing':
                prog = job.get('progress', 0)
                speed = job.get('speed', '--')
                status_text = f"⬇️ Downloading... {prog}% ({speed})"
                if status_text != last_status_text:
                    await query.edit_message_text(status_text)
                    last_status_text = status_text
            elif status == 'done':
                done = True
                file_path = job.get('path')
                file_name = job.get('file')
                filesize = job.get('filesize', 0)
                
                if not file_path or not os.path.exists(file_path):
                    await query.edit_message_text("❌ File hasil unduhan tidak ditemukan di server.")
                    return
                    
                await query.edit_message_text("📤 Mengirim file ke Telegram...")
                
                try:
                    if filesize > 50 * 1024 * 1024:
                        base_url = os.environ.get('BASE_URL', 'http://localhost:5000')
                        download_url = f"{base_url.rstrip('/')}/file/{download_jid}"
                        size_str = get_size_str(filesize).strip(' •')
                        await query.edit_message_text(
                            f"📦 <b>File terlalu besar (> 50MB)</b>\n\n"
                            f"File tidak bisa dikirim langsung melalui Telegram karena batas ukuran file 50MB.\n"
                            f"Silakan unduh file Anda melalui link berikut:\n\n"
                            f"🔗 <a href='{download_url}'>Unduh File ({size_str})</a>\n\n"
                            f"<i>Link ini valid selama 30 menit.</i>",
                            parse_mode="HTML"
                        )
                    else:
                        is_video = file_name.lower().endswith(('.mp4', '.mov', '.avi'))
                        is_audio = file_name.lower().endswith(('.mp3', '.m4a'))
                        
                        with open(file_path, 'rb') as f:
                            if is_video:
                                await context.bot.send_video(
                                    chat_id=query.message.chat_id,
                                    video=f,
                                    filename=file_name,
                                    caption=title
                                )
                            elif is_audio:
                                await context.bot.send_audio(
                                    chat_id=query.message.chat_id,
                                    audio=f,
                                    filename=file_name,
                                    title=title
                                )
                            else:
                                await context.bot.send_document(
                                    chat_id=query.message.chat_id,
                                    document=f,
                                    filename=file_name,
                                    caption=title
                                )
                        await query.edit_message_text("✅ Selesai! File berhasil dikirim.")
                        
                        # Cleanup since it was successfully sent
                        try:
                            add_entry(
                                title=job.get('title', 'Unknown'),
                                platform=job.get('platform', 'unknown'),
                                url=job.get('url', ''),
                                filename=job.get('file', ''),
                                filesize=job.get('filesize', 0)
                            )
                        except Exception as de:
                            print(f"Error logging history: {de}")
                        try:
                            os.remove(file_path)
                        except:
                            pass
                        pop_job(download_jid)
                except Exception as e:
                    await query.edit_message_text(f"❌ Gagal mengirim file: {e}")
                    try:
                        os.remove(file_path)
                    except:
                        pass
                    pop_job(download_jid)
            elif status == 'error':
                done = True
                err = job.get('error', 'Gagal memproses file')
                await query.edit_message_text(f"❌ Gagal mengunduh: {err}")
                pop_job(download_jid)

def run_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Add handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("help", help_cmd))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    application.add_handler(CallbackQueryHandler(handle_callback))
    
    # Start bot polling
    application.run_polling(close_loop=False)

def start_bot():
    if not BOT_TOKEN:
        print("Telegram bot token not found. Skipping bot startup.")
        return
    t = threading.Thread(target=run_bot_loop, daemon=True)
    t.start()
    print("Telegram bot started successfully in background thread.")
