"""
MatcherStage - L2 云端搜索对撞阶段
对齐主项目 recognition/pipeline/matcher.py
"""
import os
import time
from typing import Optional, Dict, Any
from ..context import RecognitionContext
from .parser import _is_chinese, _clean_privileged_title


def _split_title(title: str) -> list:
    """按 / 分割特权标题，返回所有有效部分用于逐个搜索"""
    if not title or '/' not in title:
        return [title] if title else []

    parts = [p.strip() for p in title.split('/') if p.strip()]
    return parts


class MatcherStage:
    """L2 云端元数据匹配"""

    @staticmethod
    async def run(ctx: RecognitionContext):
        start = time.time()
        meta = ctx.meta

        # 独立版特有：云端联动总开关
        if not ctx.with_cloud:
            return

        # 0. 确定搜索用的标题 (优先使用特权标题)
        privileged_title = getattr(meta, 'privileged_title', None)
        privileged_titles = _split_title(privileged_title) if privileged_title else []

        if privileged_titles:
            ctx.log(f"┃ [匹配] 🎯 使用特权标题优先搜索: {' | '.join(privileged_titles)}")

        # 1. 只有在指纹未命中且当前数据仍为空时，才进行深度搜索
        if not ctx.tmdb_data:
            # 2.1 强制 TMDB ID 锁定模式
            if meta.forced_tmdbid:
                ctx.log(f"┃ [匹配] 🚀 发现锁定 ID: {meta.forced_tmdbid}，正在联网获取...")
                m_type_str = "movie" if ctx.forced_type == "movie" else "tv"
                details = await ctx.tmdb_client.get_details(meta.forced_tmdbid, m_type_str, ctx.logs)
                if details:
                    ctx.tmdb_data = details
                else:
                    # 尝试另一种类型
                    alt_type = "tv" if m_type_str == "movie" else "movie"
                    details = await ctx.tmdb_client.get_details(meta.forced_tmdbid, alt_type, ctx.logs)
                    if details:
                        ctx.tmdb_data = details
                        ctx.log(f"┃ [匹配] ✅ 类型自动判定为: {alt_type.upper()}")

            # 2.2 定义搜索策略
            if not ctx.tmdb_data:
                async def search_cloud(use_privileged: bool = False, title_index: int = 0, clean_privileged: bool = False):
                    if ctx.tmdb_data: return
                    bgm_prio = ctx.bangumi_priority
                    bgm_failover = ctx.bangumi_failover

                    if bgm_prio:
                        search_order = ["bangumi", "tmdb"]
                    else:
                        search_order = ["tmdb", "bangumi"] if bgm_failover else ["tmdb"]

                    ctx.log(f"┃ [匹配] ☁️ 云端搜索顺序: {search_order} (优先级: {bgm_prio}, 故障转移: {bgm_failover})")

                    is_auto_type = hasattr(meta.type, 'value') and meta.type.value == "auto"
                    if is_auto_type:
                        ctx.log(f"┃ [匹配] 🔍 类型为 AUTO，将同时搜索 TV 和 Movie")
                        m_type_str = None
                    else:
                        m_type_str = "movie" if (hasattr(meta.type, 'value') and meta.type.value == "movie") else "tv"

                    if use_privileged and privileged_titles:
                        title = privileged_titles[title_index] if title_index < len(privileged_titles) else privileged_titles[0]
                        if clean_privileged:
                            title = _clean_privileged_title(title)
                            ctx.log(f"┃ [匹配] 🧹 使用清洗后的特权标题: {title}")
                        cn = title if _is_chinese(title) else None
                        en = title if not _is_chinese(title) else None
                        original_cn = None
                    else:
                        cn = meta.cn_name
                        en = meta.en_name
                        original_cn = getattr(meta, 'original_cn_name', None)

                    for source in search_order:
                        if ctx.tmdb_data: break
                        if source == "tmdb":
                            if is_auto_type:
                                ctx.tmdb_data = await ctx.tmdb_client.smart_search_multi(
                                    cn, en, meta.year, ctx.logs,
                                    anime_priority=ctx.anime_priority,
                                    original_cn_name=original_cn
                                )
                            else:
                                ctx.tmdb_data = await ctx.tmdb_client.smart_search(
                                    cn, en, meta.year, m_type_str, ctx.logs,
                                    anime_priority=ctx.anime_priority,
                                    original_cn_name=original_cn
                                )
                        elif source == "bangumi":
                            queries = [q for q in [en, cn] if q]
                            if not queries and getattr(meta, 'processed_name', None):
                                queries = [meta.processed_name]

                            for q in queries:
                                if ctx.tmdb_data: break
                                bgm_subject = await ctx.bangumi_client.search_subject(
                                    q, ctx.logs,
                                    current_episode=meta.begin_episode,
                                    expected_type=m_type_str
                                )
                                if bgm_subject:
                                    ctx.log(f"┃ [匹配] 🪄 Bangumi 命中，尝试映射...")
                                    ctx.tmdb_data = await ctx.bangumi_client.map_to_tmdb(
                                        bgm_subject,
                                        ctx.api_key or os.environ.get("TMDB_API_KEY", ""),
                                        ctx.logs,
                                        tmdb_proxy=ctx.tmdb_proxy
                                    )

                # 执行搜索 (优先特权标题，失败后用正常标题)
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i, clean_privileged=False)
                # 特权标题清洗后搜索
                for i in range(len(privileged_titles)):
                    if ctx.tmdb_data: break
                    await search_cloud(use_privileged=True, title_index=i, clean_privileged=True)
                # 最后用正常标题搜索
                if not ctx.tmdb_data:
                    if privileged_titles:
                        ctx.log(f"┃ [匹配] 🔄 特权标题搜索失败，使用清洗后的标题继续搜索: {meta.cn_name or meta.en_name}")
                    await search_cloud(use_privileged=False)

        # AUTO 类型自动判定
        if ctx.tmdb_data and hasattr(meta.type, 'value') and meta.type.value == "auto":
            matched_type = ctx.tmdb_data.get("type", "tv")
            from recognition_engine.data_models import MediaType
            if matched_type == "movie":
                meta.type = MediaType.MOVIE
                ctx.log(f"┃ [匹配] 🎬 AUTO 类型已自动判定为: MOVIE")
            else:
                meta.type = MediaType.TV
                ctx.log(f"┃ [匹配] 📺 AUTO 类型已自动判定为: TV")

        ctx.add_perf("元数据匹配", start)
