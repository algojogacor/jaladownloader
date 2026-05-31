import sqlite3
import os
import time
from config import BASE

DB_PATH = os.path.join(BASE, 'history.db')

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT,
            platform TEXT,
            url TEXT,
            filename TEXT,
            filesize INTEGER,
            downloaded_at INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def add_entry(title, platform, url, filename, filesize):
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO downloads (title, platform, url, filename, filesize, downloaded_at)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (title, platform, url, filename, filesize or 0, int(time.time())))
        # limit to 100 entries
        cursor.execute('''
            DELETE FROM downloads WHERE id NOT IN (
                SELECT id FROM downloads ORDER BY downloaded_at DESC LIMIT 100
            )
        ''')
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"DB Error: {e}")

def get_history():
    try:
        init_db()
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute('SELECT title, platform, url, filename, filesize, downloaded_at FROM downloads ORDER BY downloaded_at DESC LIMIT 50')
        rows = cursor.fetchall()
        conn.close()
        return [{
            'title': r[0],
            'platform': r[1],
            'url': r[2],
            'filename': r[3],
            'filesize': r[4],
            'downloaded_at': r[5]
        } for r in rows]
    except Exception as e:
        print(f"DB Error: {e}")
        return []
