"""
LocalCacheDAO - 指纹与元数据的数据访问对象 (DAO)
对齐主项目 recognition/data_provider/local_cache.py，底层使用 SQLite storage_manager。
"""
from typing import List, Optional, Dict, Any
from ..storage_manager import storage

class LocalCacheDAO:
    """
    Data Access Object for Local Metadata Cache and Series Fingerprints.
    底层使用 SQLite，不依赖 PostgreSQL / MetaCacheManager。
    """

    async def get_fingerprint_match(self, filename: str, logs: List[str] = None) -> Optional[Dict[str, Any]]:
        """根据文件名指纹查找系列匹配"""
        return storage.get_fingerprint_match(filename, logs)

    async def save_fingerprint(self, filename: str, tmdb_data: Dict[str, Any], logs: List[str] = None):
        """保存指纹"""
        storage.save_fingerprint(filename, tmdb_data, logs)

    async def get_metadata(self, tmdb_id: str, media_type: str, logs: List[str] = None) -> Optional[Dict[str, Any]]:
        """从本地存储获取完整元数据"""
        key = f"{media_type}:{tmdb_id}"
        cached = storage.get_metadata(key, "tmdb")
        if cached:
            if logs is not None:
                logs.append(f"┃ [数据中心] ⚡ 命中本地缓存: {cached.get('title')} (ID: {tmdb_id})")
            cached["source"] = "cache_hit"
            return cached
        return None

    async def save_metadata(self, tmdb_id: str, media_type: str, data: Dict[str, Any], logs: List[str] = None):
        """保存/更新元数据到本地存储"""
        key = f"{media_type}:{tmdb_id}"
        storage.set_metadata(key, "tmdb", data)
        if logs is not None:
            logs.append(f"┃ [数据中心] 💾 同步最新档案 (ID: {key})")
