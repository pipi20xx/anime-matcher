"""
MaintenanceStage - L3 指纹与元数据写入
对齐主项目 recognition/pipeline/maintenance.py
"""
import time
from ..context import RecognitionContext


class MaintenanceStage:
    """L3 记忆维护：保存指纹和元数据到本地存储"""

    @staticmethod
    async def run(ctx: RecognitionContext):
        if not ctx.tmdb_data: return
        start = time.time()

        m_id = str(ctx.tmdb_data.get("id", ""))
        m_type = ctx.tmdb_data.get("type", "tv")

        # 1. 自动维护指纹库
        if ctx.use_fingerprint:
            existing_fp = await ctx.cache_dao.get_fingerprint_match(ctx.filename, [])
            if not existing_fp or str(existing_fp.get("id")) != m_id:
                await ctx.cache_dao.save_fingerprint(ctx.filename, ctx.tmdb_data, ctx.logs)

        # 2. 自动同步元数据到本地缓存
        if ctx.tmdb_data.get("source") not in ["archive_hit", "cache_hit_verified"]:
            existing = await ctx.cache_dao.get_metadata(m_id, m_type, [])
            if not existing:
                await ctx.cache_dao.save_metadata(m_id, m_type, ctx.tmdb_data, ctx.logs)

        ctx.add_perf("维护同步", start)
