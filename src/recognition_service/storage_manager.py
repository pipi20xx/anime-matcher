import sqlite3
import json
import logging
import os
import re
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from .config import DATABASE_PATH, CACHE_EXPIRY_DAYS, MEMORY_EXPIRY_DAYS

logger = logging.getLogger("recognition_service.storage")

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
            db_dir = os.path.dirname(os.path.abspath(DATABASE_PATH))
            if not os.path.exists(db_dir):
                os.makedirs(db_dir, exist_ok=True)
                logger.info(f"创建存储目录: {db_dir}")

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
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS fingerprint_cache (
                fingerprint TEXT PRIMARY KEY,
                tmdb_id TEXT,
                media_type TEXT,
                title TEXT,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        self.conn.commit()

    # ========== 元数据缓存 ==========

    def get_metadata(self, key: str, source: str) -> Optional[Dict]:
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

    # ========== 旧版标题记忆 (向后兼容) ==========

    def get_memory(self, pattern_key: str) -> Optional[Dict]:
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

    # ========== 文件名指纹记忆 (对齐主项目) ==========

    @staticmethod
    def make_fingerprint(filename: str) -> str:
        """将文件名中的数字替换为 #，生成指纹"""
        return re.sub(r'\d+', '#', filename)

    @staticmethod
    def is_fingerprint_valid(fingerprint: str, original_filename: str) -> bool:
        """
        检查指纹是否足够有效，避免过于简单的指纹导致误匹配。

        无效指纹示例：S#E#.mkv (只有季集模式)、#.mkv (只有集数)
        有效指纹示例：[LoliHouse] Spy x Family - # [####].mkv (包含标题和制作组)
        """
        # 1. 移除所有数字占位符 # 后，检查是否有实质内容
        stripped = fingerprint.replace('#', '')

        # 2. 移除常见的季集模式标记
        season_ep_patterns = [
            r'[Ss]#?',
            r'[Ee][Pp]?#?',
            r'第\s*#?\s*[集话回話]?',
            r'[Vv][Oo][Ll]\.?\s*#?',
        ]
        clean_fingerprint = stripped
        for pattern in season_ep_patterns:
            clean_fingerprint = re.sub(pattern, '', clean_fingerprint, flags=re.IGNORECASE)

        # 3. 移除文件扩展名和技术规格标记
        clean_fingerprint = re.sub(r'\.\w{2,4}$', '', clean_fingerprint)
        clean_fingerprint = re.sub(r'[\[\]【】()]', '', clean_fingerprint)
        clean_fingerprint = clean_fingerprint.strip()

        # 4. 移除纯技术规格词
        tech_words = ['mkv', 'mp4', 'avi', 'ts', 'flv', 'mov', 'webm']
        for word in tech_words:
            clean_fingerprint = clean_fingerprint.replace(word, '')

        # 5. 最终检查：剩余内容是否包含标题相关信息
        has_title_content = bool(re.search(r'[a-zA-Z\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff]{2,}', clean_fingerprint))

        # 6. 文件名过短也不值得记录
        is_filename_short = len(original_filename.strip()) < 10

        return has_title_content and not is_filename_short

    def get_fingerprint_match(self, filename: str, logs: List[str] = None) -> Optional[Dict[str, Any]]:
        """根据文件名指纹查找系列匹配"""
        if not self._ensure_connection(): return None
        try:
            fingerprint = self.make_fingerprint(filename)
            cursor = self.conn.cursor()
            cursor.execute("SELECT tmdb_id, media_type, title, updated_at FROM fingerprint_cache WHERE fingerprint = ?", (fingerprint,))
            row = cursor.fetchone()
            if row:
                updated_at = datetime.strptime(row['updated_at'], '%Y-%m-%d %H:%M:%S')
                if datetime.now() - updated_at > timedelta(days=MEMORY_EXPIRY_DAYS):
                    return None
                if logs is not None:
                    logs.append(f"┃ [智能记忆] ⚡ 命中加速: {row['title']} (ID: {row['tmdb_id']})")
                return {"id": row['tmdb_id'], "type": row['media_type'], "title": row['title'], "source": "fingerprint_match"}
        except Exception:
            return None
        return None

    def save_fingerprint(self, filename: str, tmdb_data: Dict[str, Any], logs: List[str] = None):
        """保存指纹"""
        if not self._ensure_connection(): return
        try:
            fingerprint = self.make_fingerprint(filename)

            if not self.is_fingerprint_valid(fingerprint, filename):
                if logs is not None:
                    logs.append(f"┃ [智能记忆] ⏭️ 跳过记录: 指纹 '{fingerprint}' 过于简单，缺乏区分度")
                return

            tmdb_id = str(tmdb_data.get('id', ''))
            media_type = tmdb_data.get('type', 'tv')
            title = tmdb_data.get('title') or tmdb_data.get('name') or ''

            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO fingerprint_cache (fingerprint, tmdb_id, media_type, title, updated_at) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)",
                (fingerprint, tmdb_id, media_type, title)
            )
            self.conn.commit()
            if logs is not None:
                logs.append(f"┃ [智能记忆] 💾 更新记忆特征: ID:{tmdb_id} | 标题:{title}")
        except Exception as e:
            if logs is not None:
                logs.append(f"┃ [智能记忆] ❌ 更新失败: {e}")

storage = StorageManager()
