import sqlite3
import json
import logging
import os
from datetime import datetime, timedelta
from .config import DATABASE_PATH, CACHE_EXPIRY_DAYS, MEMORY_EXPIRY_DAYS

logger = logging.getLogger("anime-matcher.storage")

class StorageManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(StorageManager, cls).__new__(cls)
            cls._instance.conn = None
            cls._instance.initialized = False
        return cls._instance

    def _ensure_connection(self):
        """延迟初始化：只有在真正使用时才创建数据库连接和表"""
        if self.initialized:
            return True
        
        try:
            # 确保数据库所在的目录存在
            db_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"创建存储目录: {db_dir}")

            # 只有调用此方法时才会创建 .db 文件
            self.conn = sqlite3.connect(DATABASE_PATH, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self._create_tables()
            self.initialized = True
            return True
        except Exception as e:
            logger.error(f"无法初始化本地存储: {e}")
            return False

    def _create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS metadata_cache (
                key TEXT PRIMARY KEY,
                source TEXT,
                data TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS recognition_memory (
                pattern_key TEXT PRIMARY KEY,
                tmdb_id TEXT,
                media_type TEXT,
                season INTEGER,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    def get_metadata(self, key: str, source: str):
        if not self._ensure_connection(): return None
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT data, updated_at FROM metadata_cache WHERE key = ? AND source = ?", (key, source))
            row = cursor.fetchone()
            if row:
                updated_at = datetime.strptime(row['updated_at'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - updated_at > timedelta(days=CACHE_EXPIRY_DAYS):
                    return None
                return json.loads(row['data'])
        except Exception:
            return None
        return None

    def set_metadata(self, key: str, source: str, data: dict):
        if not self._ensure_connection(): return
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO metadata_cache (key, source, data, updated_at) VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                (key, source, json.dumps(data, ensure_ascii=False))
            )
            self.conn.commit()
        except Exception:
            pass

    def get_memory(self, pattern_key: str):
        if not self._ensure_connection(): return None
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT tmdb_id, media_type, season, updated_at FROM recognition_memory WHERE pattern_key = ?", (pattern_key,))
            row = cursor.fetchone()
            if row:
                updated_at = datetime.strptime(row['updated_at'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - updated_at > timedelta(days=MEMORY_EXPIRY_DAYS):
                    return None
                return {"tmdb_id": row['tmdb_id'], "media_type": row['media_type'], "season": row['season']}
        except Exception:
            return None
        return None

    def set_memory(self, pattern_key: str, tmdb_id: str, media_type: str, season: int):
        if not self._ensure_connection(): return
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO recognition_memory (pattern_key, tmdb_id, media_type, season, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (pattern_key, tmdb_id, media_type, season)
            )
            self.conn.commit()
        except Exception:
            pass

storage = StorageManager()