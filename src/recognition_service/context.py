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
    """
    # === 输入 ===
    filename: str = ""
    original_filename: str = ""

    # L1 预处理规则
    custom_words: List[str] = field(default_factory=list)
    custom_groups: List[str] = field(default_factory=list)
    # L3 渲染规则
    custom_render: List[str] = field(default_factory=list)
    # 特权提取规则
    special_rules: List[str] = field(default_factory=list)

    # 模式控制
    force_filename: bool = False
    batch_enhancement: bool = False

    # 方案 B: 扩展参数
    with_cloud: bool = False
    use_storage: bool = False
    anime_priority: bool = True
    bangumi_priority: bool = False
    bangumi_failover: bool = True

    # 云端凭据
    tmdb_api_key: Optional[str] = None
    tmdb_proxy: Optional[str] = None
    tmdb_id: Optional[str] = None       # 已知 ID 提示
    tmdb_type: Optional[str] = None     # 已知类型提示
    bangumi_token: Optional[str] = None
    bangumi_proxy: Optional[str] = None

    # === 中间状态 ===
    raw_meta: Optional[Any] = None       # L1 内核返回的 MetaData 对象
    local_result: Dict[str, Any] = field(default_factory=dict)  # L1 封装结果
    cloud_match: Optional[Dict[str, Any]] = None  # L2 云端匹配结果
    tmdb_match: Optional[Dict[str, Any]] = None   # L2 最终采信的 TMDB 数据
    final_result: Dict[str, Any] = field(default_factory=dict)  # 最终结论

    # === 运行时 ===
    logs: List[str] = field(default_factory=list)
    start_time: float = field(default_factory=time.time)
    active_storage: bool = False

    # === 数据提供者 (延迟初始化) ===
    _tmdb_provider: Any = None
    _bgm_provider: Any = None
    _local_cache: Any = None

    @property
    def tmdb_provider(self):
        if self._tmdb_provider is None:
            from .data_provider.tmdb.client import TMDBProvider
            self._tmdb_provider = TMDBProvider(api_key=self.tmdb_api_key, proxy=self.tmdb_proxy)
        return self._tmdb_provider

    @property
    def bgm_provider(self):
        if self._bgm_provider is None:
            from .data_provider.bangumi.client import BangumiProvider
            self._bgm_provider = BangumiProvider(token=self.bangumi_token, proxy=self.bangumi_proxy)
        return self._bgm_provider

    @property
    def local_cache(self):
        if self._local_cache is None:
            from .data_provider.local_cache import LocalCacheDAO
            self._local_cache = LocalCacheDAO()
        return self._local_cache

    def log(self, msg: str):
        """添加日志"""
        self.logs.append(msg)

    def get_duration(self) -> str:
        """获取已耗时"""
        return f"{time.time() - self.start_time:.1f}s"

    def report_config(self):
        """配置审计日志"""
        def on_off(b): return "ON" if b else "OFF"
        self.log("🚀 --- [ANIME 深度审计流启动] ---")
        self.log(f"┃ [配置] 模式状态: 强制单文件[{on_off(self.force_filename)}] | 合集增强[{on_off(self.batch_enhancement)}] | 云端联动[{on_off(self.with_cloud)}] | 智能记忆[{on_off(self.use_storage)}]")
        self.log(f"┃ [配置] 策略权重: 动漫优先[{on_off(self.anime_priority)}] | Bangumi 优先[{on_off(self.bangumi_priority)}] | TMDB 故障转移[{on_off(self.bangumi_failover)}]")
        self.log(f"┃ [配置] 规则载入: 屏蔽词({len(self.custom_words)}) | 制作组({len(self.custom_groups)}) | 专家渲染({len(self.custom_render)})")

        if self.with_cloud:
            tmdb_key_mask = f"{self.tmdb_api_key[:4]}***{self.tmdb_api_key[-4:]}" if self.tmdb_api_key and len(self.tmdb_api_key) > 8 else ("Env-Key" if os.environ.get("TMDB_API_KEY") else "Missing")
            self.log(f"┃ [配置] 云端凭据: TMDB密钥[{tmdb_key_mask}]")
            if self.tmdb_proxy: self.log(f"┃ [配置] 网络代理: {self.tmdb_proxy}")

        if self.tmdb_id:
            type_hint = f" ({self.tmdb_type})" if self.tmdb_type else ""
            self.log(f"┃ [配置] 锚点提示: 已知锁定 ID = {self.tmdb_id}{type_hint}")

    @classmethod
    def from_request(cls, req) -> "RecognitionContext":
        """从 FastAPI 请求模型构建上下文"""
        def clean_param(v):
            if v == "string" or not v: return None
            return v

        ctx = cls(
            filename=req.filename,
            original_filename=req.filename,
            custom_words=req.custom_words,
            custom_groups=req.custom_groups,
            custom_render=req.custom_render,
            special_rules=req.special_rules,
            force_filename=req.force_filename,
            batch_enhancement=req.batch_enhancement,
            with_cloud=req.with_cloud,
            use_storage=req.use_storage,
            anime_priority=req.anime_priority,
            bangumi_priority=req.bangumi_priority,
            bangumi_failover=req.bangumi_failover,
            tmdb_api_key=clean_param(req.tmdb_api_key),
            tmdb_proxy=clean_param(req.tmdb_proxy),
            tmdb_id=clean_param(req.tmdb_id),
            tmdb_type=clean_param(req.tmdb_type),
            bangumi_token=clean_param(req.bangumi_token),
            bangumi_proxy=clean_param(req.bangumi_proxy),
        )
        ctx.active_storage = ctx.use_storage
        return ctx
