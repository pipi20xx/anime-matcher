"""
RecognitionContext - 识别任务上下文
对齐主项目 recognition/context.py，适配独立版（无 ConfigManager，用请求参数直接构建）。
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
import os
import time
import logging

logger = logging.getLogger("recognition_service.context")

@dataclass
class RecognitionContext:
    """
    贯穿整个识别 Pipeline 的上下文对象。
    每个阶段都可以读取和修改其中的数据。

    字段命名与主项目 recognition/context.py 保持一致：
    - meta: L1 内核返回的 MetaBase 对象
    - tmdb_data: L2 云端匹配结果
    - cache_dao / local_store: 本地缓存 DAO
    - all_noise / all_groups / all_render / all_privilege: 规则列表
    - use_fingerprint: 智能指纹开关
    - batch_enhance: 合集增强
    """
    # === 输入 ===
    filename: str = ""
    original_filename: str = ""

    # L1 预处理规则 (主项目字段名: all_noise / all_groups)
    all_noise: List[str] = field(default_factory=list)
    all_groups: List[str] = field(default_factory=list)
    # L3 渲染规则 (主项目字段名: all_render)
    all_render: List[str] = field(default_factory=list)
    # 特权提取规则 (主项目字段名: all_privilege)
    all_privilege: List[str] = field(default_factory=list)

    # 模式控制
    force_filename: bool = False
    batch_enhance: bool = False
    use_fingerprint: bool = True

    # 方案 B: 扩展参数
    anime_priority: bool = True
    bangumi_priority: bool = False
    bangumi_failover: bool = True

    # 云端凭据
    api_key: Optional[str] = None
    tmdb_proxy: Optional[str] = None
    forced_tmdb_id: Optional[str] = None
    forced_type: Optional[str] = None
    bangumi_token: Optional[str] = None
    bangumi_proxy: Optional[str] = None

    # === 中间状态 ===
    meta: Optional[Any] = None              # L1 内核返回的 MetaBase 对象 (主项目: ctx.meta)
    tmdb_data: Optional[Dict[str, Any]] = None  # L2 云端匹配结果 (主项目: ctx.tmdb_data)

    # === 运行时 ===
    logs: List[str] = field(default_factory=list)
    perf_stats: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)

    # === 数据提供者 (延迟初始化) ===
    _tmdb_client: Any = None
    _bangumi_client: Any = None
    _cache_dao: Any = None

    # === 向后兼容字段 (旧 API 请求参数名) ===
    # custom_words → all_noise, custom_groups → all_groups
    # custom_render → all_render, special_rules → all_privilege
    # use_storage → use_fingerprint, batch_enhancement → batch_enhance
    # tmdb_id → forced_tmdb_id, tmdb_type → forced_type
    # with_cloud 控制是否执行云端匹配
    with_cloud: bool = False

    @property
    def tmdb_client(self):
        if self._tmdb_client is None:
            from .data_provider.tmdb.client import TMDBProvider
            self._tmdb_client = TMDBProvider(api_key=self.api_key, proxy=self.tmdb_proxy)
        return self._tmdb_client

    @property
    def bangumi_client(self):
        if self._bangumi_client is None:
            from .data_provider.bangumi.client import BangumiProvider
            self._bangumi_client = BangumiProvider(token=self.bangumi_token, proxy=self.bangumi_proxy)
        return self._bangumi_client

    @property
    def cache_dao(self):
        """本地缓存 DAO (主项目: ctx.cache_dao / ctx.local_store)"""
        if self._cache_dao is None:
            from .data_provider.local_cache import LocalCacheDAO
            self._cache_dao = LocalCacheDAO()
        return self._cache_dao

    @property
    def local_store(self):
        """别名，与主项目 ctx.local_store 一致"""
        return self.cache_dao

    @property
    def duration(self) -> float:
        """已耗时（秒）"""
        return time.time() - self.start_time

    def log(self, message: str, level: str = "INFO"):
        """添加日志"""
        self.logs.append(message)

    def add_perf(self, stage: str, start_ts: float):
        """添加性能统计"""
        duration_ms = int((time.time() - start_ts) * 1000)
        self.perf_stats.append(f"{stage}: {duration_ms}ms")

    @classmethod
    def from_request(cls, req) -> "RecognitionContext":
        """从 FastAPI 请求模型构建上下文"""
        def clean_param(v):
            if v == "string" or not v: return None
            return v

        ctx = cls(
            filename=req.filename,
            original_filename=req.filename,
            all_noise=req.custom_words,
            all_groups=req.custom_groups,
            all_render=req.custom_render,
            all_privilege=req.special_rules,
            force_filename=req.force_filename,
            batch_enhance=req.batch_enhancement,
            with_cloud=req.with_cloud,
            use_fingerprint=req.use_storage,
            anime_priority=req.anime_priority,
            bangumi_priority=req.bangumi_priority,
            bangumi_failover=req.bangumi_failover,
            api_key=clean_param(req.tmdb_api_key),
            tmdb_proxy=clean_param(req.tmdb_proxy),
            forced_tmdb_id=clean_param(req.tmdb_id),
            forced_type=clean_param(req.tmdb_type),
            bangumi_token=clean_param(req.bangumi_token),
            bangumi_proxy=clean_param(req.bangumi_proxy),
        )
        return ctx
