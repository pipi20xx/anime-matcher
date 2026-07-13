"""
MatcherStage - L2 云端搜索对撞阶段
对齐主项目 recognition/pipeline/matcher.py
"""
import os
from typing import Optional, Dict, Any
from ..context import RecognitionContext
from .parser import _is_chinese, _split_title, _clean_privileged_title


class MatcherStage:
    """L2 云端元数据匹配"""

    @staticmethod
    async def execute(ctx: RecognitionContext):
        if not ctx.with_cloud:
            return

        # 如果指纹已命中，直接获取详情
        if ctx.tmdb_match and ctx.tmdb_match.get("source") == "fingerprint_match":
            ctx.log("┃")
            ctx.log("┃ [DEBUG][STEP 8: 云端元数据联动]: 指纹命中，直接获取详情")
            details = await ctx.tmdb_provider.get_details(
                str(ctx.tmdb_match["id"]), ctx.tmdb_match.get("type", "tv"), logs=ctx.logs
            )
            if details:
                ctx.cloud_match = details
                ctx.log(f"┗ ✅ 指纹命中详情获取成功: {details.get('title') or details.get('name')}")
                return
            else:
                ctx.log("┃   ⚠️ 指纹命中但详情获取失败，回退到正常搜索流程")
                ctx.tmdb_match = None

        # 已知 ID 直接获取详情
        if ctx.tmdb_id and not ctx.tmdb_match:
            ctx.log("┃")
            ctx.log("┃ [DEBUG][STEP 8: 云端元数据联动]: 已知ID，直接获取详情")
            cache_key = ctx.tmdb_id
            if ctx.active_storage:
                from ..storage_manager import storage
                cloud_data = storage.get_metadata(cache_key, "tmdb")
                if cloud_data:
                    ctx.log(f"┃ [STORAGE] ⚡ 命中元数据缓存: {cloud_data.get('title') or cloud_data.get('name')}")
                    ctx.cloud_match = cloud_data
                    return

            details = await ctx.tmdb_provider.get_details(
                ctx.tmdb_id, ctx.local_result["type"], logs=ctx.logs
            )
            if details:
                ctx.cloud_match = details
                if ctx.active_storage:
                    from ..storage_manager import storage
                    storage.set_metadata(str(details.get('id')), "tmdb", details)
                ctx.log(f"┗ ✅ 识别成功: {details.get('title') or details.get('name')} (ID: {details.get('id')})")
                return
            else:
                ctx.log("┗ ❌ 已知ID详情获取失败")

        # 正常搜索流程
        ctx.log("┃")
        ctx.log("┃ [DEBUG][STEP 8: 云端元数据联动]: 启动搜索对撞")

        # 先查缓存
        cache_key = ctx.tmdb_id if ctx.tmdb_id else (ctx.local_result["cn_name"] or ctx.local_result["en_name"])
        if ctx.active_storage:
            from ..storage_manager import storage
            cached = storage.get_metadata(cache_key, "tmdb")
            if cached:
                ctx.log(f"┃ [STORAGE] ⚡ 命中元数据缓存: {cached.get('title') or cached.get('name')}")
                ctx.cloud_match = cached
                return

        cloud_data = await MatcherStage._search_cloud(ctx)

        if cloud_data:
            ctx.cloud_match = cloud_data
            ctx.log(f"┗ ✅ 识别成功: {cloud_data.get('title') or cloud_data.get('name')} (ID: {cloud_data.get('id')})")
            # 存入缓存
            if ctx.active_storage:
                from ..storage_manager import storage
                storage.set_metadata(str(cloud_data.get('id')), "tmdb", cloud_data)
                pattern_key = f"{ctx.local_result['cn_name'] or ctx.local_result['en_name']}|{ctx.local_result['year']}"
                storage.set_memory(pattern_key, str(cloud_data.get('id')), ctx.local_result['type'], ctx.local_result['season'])
        else:
            ctx.log("┗ ❌ 云端检索未发现高置信度匹配")

    @staticmethod
    async def _search_cloud(ctx: RecognitionContext) -> Optional[Dict]:
        tmdb_client = ctx.tmdb_provider
        bgm_client = ctx.bgm_provider
        l1 = ctx.local_result
        meta = ctx.raw_meta
        m_type_str = l1["type"]

        privileged_title = getattr(meta, 'privileged_title', None)
        privileged_titles = _split_title(privileged_title) if privileged_title else []

        if privileged_titles:
            ctx.log(f"┃ [匹配] 🎯 使用特权标题优先搜索: {' | '.join(privileged_titles)}")

        if ctx.bangumi_priority:
            search_order = ["bangumi", "tmdb"]
        else:
            search_order = ["tmdb", "bangumi"] if ctx.bangumi_failover else ["tmdb"]

        is_auto_type = m_type_str == "auto"
        if is_auto_type:
            ctx.log("┃ [匹配] 🔍 类型为 AUTO，将同时搜索 TV 和 Movie")

        cloud_data = None

        async def search_cloud(use_privileged: bool = False, title_index: int = 0, clean_privileged: bool = False):
            nonlocal cloud_data
            if cloud_data: return

            if use_privileged and privileged_titles:
                title = privileged_titles[title_index] if title_index < len(privileged_titles) else privileged_titles[0]
                if clean_privileged:
                    title = _clean_privileged_title(title)
                    ctx.log(f"┃ [匹配] 🧹 使用清洗后的特权标题: {title}")
                cn = title if _is_chinese(title) else None
                en = title if not _is_chinese(title) else None
                original_cn = None
            else:
                cn = l1["cn_name"]
                en = l1["en_name"]
                original_cn = getattr(meta, 'original_cn_name', None)

            for source in search_order:
                if cloud_data: break
                if source == "tmdb":
                    if is_auto_type:
                        cloud_data = await tmdb_client.smart_search_multi(
                            cn, en, l1["year"], ctx.logs,
                            anime_priority=ctx.anime_priority,
                            original_cn_name=original_cn
                        )
                    else:
                        cloud_data = await tmdb_client.smart_search(
                            cn, en, l1["year"], m_type_str, ctx.logs,
                            anime_priority=ctx.anime_priority,
                            original_cn_name=original_cn
                        )
                elif source == "bangumi":
                    queries = [q for q in [en, cn] if q]
                    if not queries and getattr(meta, 'processed_name', None):
                        queries = [meta.processed_name]

                    for q in queries:
                        if cloud_data: break
                        bgm_subject = await bgm_client.search_subject(
                            q, ctx.logs,
                            current_episode=l1["episode"],
                            expected_type=m_type_str if not is_auto_type else None
                        )
                        if bgm_subject:
                            ctx.log("┃ [匹配] 🪄 Bangumi 命中，尝试映射...")
                            cloud_data = await bgm_client.map_to_tmdb(
                                bgm_subject,
                                tmdb_api_key=ctx.tmdb_api_key or os.environ.get("TMDB_API_KEY", ""),
                                logs=ctx.logs,
                                tmdb_proxy=ctx.tmdb_proxy
                            )
                            if not cloud_data:
                                ctx.log("┃ [匹配] ⚠️ Bangumi 映射 TMDB 失败，回退到原始元数据")
                                cloud_data = bgm_subject

        # 特权标题搜索
        for i in range(len(privileged_titles)):
            if cloud_data: break
            await search_cloud(use_privileged=True, title_index=i)
        for i in range(len(privileged_titles)):
            if cloud_data: break
            await search_cloud(use_privileged=True, title_index=i, clean_privileged=True)

        # 常规搜索
        if not cloud_data:
            if privileged_titles:
                ctx.log(f"┃ [匹配] 🔄 特权标题搜索失败，使用原始标题继续搜索: {l1['cn_name'] or l1['en_name']}")
            await search_cloud(use_privileged=False)

        return cloud_data
