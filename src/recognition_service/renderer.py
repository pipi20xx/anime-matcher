"""
ResultRenderer - 最终结论构建 + L3 渲染调用
对齐主项目 recognition/renderer.py（简化版，无 Renamer / TmdbMateFull）
"""
import os
import time
from typing import Dict, Any
from .context import RecognitionContext
from .render.engine import RenderEngine
from .render.reporter import RenderReporter


class ResultRenderer:
    """
    渲染器主入口 (Layer 3 - Final Stage)
    方法签名与主项目对齐：apply_to_context(ctx) -> data_packet
    """

    @staticmethod
    async def apply_to_context(ctx: RecognitionContext) -> Dict[str, Any]:
        # 1. 初始化结论数据包 (Data Normalization)
        data_packet = ResultRenderer._prepare_data_packet(ctx)

        # 2. 执行专家渲染规则 (Expert Rules Engine)
        render_start = time.time()
        if ctx.all_render:
            ctx.log("┃ [DEBUG][Step 8: 自定义渲染词处理]: 启动子流程审计")
            r_logs = []
            data_packet = await RenderEngine.apply_rules(
                data_packet, ctx.filename, ctx.all_render, r_logs, ctx.api_key
            )
            for l in r_logs: ctx.log(l)
            ctx.log("┃ ✅ 渲染流程结束")

        ctx.add_perf("规则渲染", render_start)

        # 3. 同步并修正最终渲染名 (processed_name)
        f = data_packet["final_result"]
        if not f.get("processed_name"):
            f["processed_name"] = ctx.filename.split('/')[-1].rsplit('.', 1)[0]

        # 4. 汇总汇报与审计 (Reporting)
        return RenderReporter.report(ctx, data_packet)

    @staticmethod
    def _prepare_data_packet(ctx: RecognitionContext) -> Dict[str, Any]:
        """
        将上下文碎片化信息整合为初步的最终结论 (data_packet)。
        对齐主项目 _prepare_data_packet 方法。
        """
        meta = ctx.meta
        tmdb_data = ctx.tmdb_data or {}

        f_title = tmdb_data.get("title") or tmdb_data.get("name") or (meta.cn_name or meta.en_name)
        f_id = tmdb_data.get("id", "")
        f_year = tmdb_data.get("year") or meta.year or ""
        m_type_str = meta.type.value if hasattr(meta.type, 'value') else str(meta.type)
        f_category = tmdb_data.get("category") or ("电影" if m_type_str == "movie" else "剧集")
        f_season = meta.begin_season if meta.begin_season is not None else 1
        f_episode = f"{meta.begin_episode}-{meta.end_episode}" if meta.is_batch and meta.end_episode else (meta.begin_episode or "")

        processed_name = meta.processed_name or ctx.filename.split('/')[-1].rsplit('.', 1)[0]

        # 制片国家
        raw_c = tmdb_data.get("origin_country")
        c_code = raw_c[0] if isinstance(raw_c, list) and raw_c else str(raw_c or "")
        f_country = c_code  # 简化版不做映射翻译

        final_res = {
            "path": ctx.filename,
            "filename": ctx.filename.split('/')[-1],
            "title": f_title,
            "tmdb_id": f_id,
            "year": f_year,
            "category": f_category,
            "secondary_category": tmdb_data.get("secondary_category"),
            "origin_country": f_country,
            "season": f_season,
            "episode": f_episode,
            "resolution": meta.resource_pix,
            "team": meta.resource_team,
            "source": meta.resource_type,
            "video_encode": meta.video_encode,
            "audio_encode": meta.audio_encode,
            "video_effect": meta.video_effect,
            "subtitle": meta.subtitle_lang,
            "platform": meta.resource_platform,
            "processed_name": processed_name,
            "poster_path": tmdb_data.get("poster_path"),
            "release_date": tmdb_data.get("release_date") or tmdb_data.get("first_air_date"),
            "vote_average": tmdb_data.get("vote_average"),
            "duration": f"{ctx.duration:.1f}s",
        }

        # 构建元数据快照 (raw_meta)
        raw_meta_clean = vars(meta).copy()
        if 'type' in raw_meta_clean and hasattr(raw_meta_clean['type'], 'value'):
            raw_meta_clean['type'] = raw_meta_clean['type'].value

        return {
            "success": True,
            "final_result": final_res,
            "raw_meta": raw_meta_clean,
            "tmdb_match": tmdb_data
        }
