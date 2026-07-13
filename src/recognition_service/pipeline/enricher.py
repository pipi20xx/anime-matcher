"""
EnrichmentStage - L2.5 元数据字段补全
对齐主项目 recognition/pipeline/enricher.py（简化版，无 TmdbMateFull / OfflineDAO）
"""
import time
from ..context import RecognitionContext


class EnrichmentStage:
    """L2.5 字段补全：将云端数据融合到 meta 和 tmdb_data"""

    @staticmethod
    async def run(ctx: RecognitionContext):
        if not ctx.tmdb_data: return
        start = time.time()

        m_id = str(ctx.tmdb_data.get("id", ""))
        m_type = ctx.tmdb_data.get("type", "tv")

        if not m_id: return

        # 检查本地缓存是否有更完整的数据
        if ctx.use_fingerprint:
            cached = await ctx.cache_dao.get_metadata(m_id, m_type, ctx.logs)
            if cached:
                # 用缓存数据补全缺失字段
                for f in ["poster_path", "backdrop_path", "overview", "release_date", "year",
                           "genres", "original_language", "vote_average", "origin_country"]:
                    if not ctx.tmdb_data.get(f) and cached.get(f):
                        ctx.tmdb_data[f] = cached[f]

        # 联网补全展示资料 (如果缓存也没有)
        if not ctx.tmdb_data.get("poster_path") or not ctx.tmdb_data.get("overview"):
            try:
                online_details = await ctx.tmdb_client.get_details(m_id, m_type, [])
                if online_details:
                    for f in ["poster_path", "backdrop_path", "overview", "vote_average",
                               "genres", "tagline", "cast"]:
                        if not ctx.tmdb_data.get(f) and online_details.get(f):
                            ctx.tmdb_data[f] = online_details.get(f)
            except: pass

        ctx.add_perf("深度补全", start)
