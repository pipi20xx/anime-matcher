"""
ParserStage - L1 本地解析阶段
对齐主项目 recognition/pipeline/parser.py
"""
import re
import os
import time
from typing import Optional
from ..context import RecognitionContext
from recognition_engine.kernel import core_recognize
from recognition_engine.special_episode_handler import SpecialEpisodeHandler


def _is_chinese(text: str) -> bool:
    if not text: return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff': return True
    return False

def _clean_privileged_title(title: str) -> str:
    if not title: return title
    cleaned = re.sub(r'\.', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


class ParserStage:
    """L1 解析 + 指纹预匹配"""

    @staticmethod
    async def run(ctx: RecognitionContext):
        start = time.time()

        # --- 加载特权提取规则 ---
        if ctx.all_privilege:
            SpecialEpisodeHandler.load_external_rules(ctx.all_privilege)
            ctx.log(f"┣ [临时规则] 已加载 {len(ctx.all_privilege)} 条临时特权规则")

        # --- 配置审计 ---
        p_anime = "ON" if ctx.anime_priority else "OFF"
        p_batch = "ON" if ctx.batch_enhance else "OFF"
        p_fp = "ON" if ctx.use_fingerprint else "OFF"
        p_bgm = "ON" if ctx.bangumi_priority else "OFF"
        p_failover = "ON" if ctx.bangumi_failover else "OFF"
        p_force_file = "ON" if ctx.force_filename else "OFF"

        ctx.log(f"🚀 --- [ANIME 深度审计流水线启动] ---")
        ctx.log(f"┃ [待处理条目]: {ctx.filename}")
        ctx.log(f"┃ [配置] 策略状态: 动漫优化[{p_anime}] | 合集增强[{p_batch}] | 智能记忆[{p_fp}] | BGM数据源优先[{p_bgm}] | BGM故障转移[{p_failover}] | 强制单文件[{p_force_file}]")

        # --- 指纹预匹配 (智能记忆) ---
        if ctx.use_fingerprint and not ctx.tmdb_data:
            fp_match = await ctx.cache_dao.get_fingerprint_match(ctx.filename, ctx.logs)
            if fp_match:
                ctx.tmdb_data = {
                    "id": fp_match["id"],
                    "type": fp_match["type"],
                    "source": "fingerprint_match"
                }
                ctx.log(f"┃ [智能记忆] ⚡ 记忆加速启动，将跳过冗余内核解析步骤")

        # --- L1 内核解析 ---
        kernel_logs = []
        ctx.meta = core_recognize(
            input_name=ctx.filename,
            custom_words=ctx.all_noise,
            custom_groups=ctx.all_groups,
            original_input=ctx.original_filename,
            current_logs=kernel_logs,
            batch_enhancement=ctx.batch_enhance,
            force_filename=ctx.force_filename
        )

        # 同步内核日志
        for l in kernel_logs: ctx.log(l)

        # --- 处理参数覆盖 ---
        ParserStage._apply_forced_params(ctx)

        ctx.add_perf("本地解析", start)

    @staticmethod
    def _apply_forced_params(ctx: RecognitionContext):
        """处理强制参数覆盖 (对齐主项目 _apply_forced_params)"""
        meta = ctx.meta

        if ctx.forced_tmdb_id:
            meta.forced_tmdbid = str(ctx.forced_tmdb_id)
            ctx.log(f"┣ [强制参数] 🔧 强制 TMDB ID: {meta.forced_tmdbid}")

        if ctx.forced_type:
            ft = ctx.forced_type.lower()
            # 智能记忆已命中时，以记忆中的类型为准
            cached_type = ctx.tmdb_data.get("type") if ctx.tmdb_data else None
            if cached_type:
                from recognition_engine.data_models import MediaType
                meta.type = MediaType.MOVIE if cached_type == "movie" else MediaType.TV
                ctx.log(f"┣ [强制参数] ⚠️ 智能记忆已命中(type={cached_type})，忽略 forced_type={ft}，保持记忆类型")
            else:
                from recognition_engine.data_models import MediaType
                meta.type = MediaType.MOVIE if ft == "movie" else MediaType.TV
                ctx.log(f"┣ [强制参数] 🔧 强制类型: {ft}")
