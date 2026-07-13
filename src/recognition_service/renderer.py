"""
ResultRenderer - 最终结论构建 + L3 渲染调用
对齐主项目 recognition/renderer.py（简化版，无 Renamer/TmdbMateFull）
"""
import os
from .context import RecognitionContext
from .render.engine import RenderEngine
from .render.reporter import RenderReporter


class ResultRenderer:
    """L3 最终报告构建 + 渲染规则执行"""

    @staticmethod
    async def execute(ctx: RecognitionContext):
        l1 = ctx.local_result
        meta = ctx.raw_meta
        cloud = ctx.cloud_match

        # --- 构建最终结论 ---
        m_type_zh = "电影" if l1["type"] == "movie" else "剧集"
        ctx.final_result = {
            "audio_encode": l1["audio_encode"],
            "category": m_type_zh,
            "episode": str(l1["episode"]),
            "filename": os.path.basename(ctx.filename),
            "path": ctx.filename,
            "platform": l1["platform"],
            "processed_name": getattr(meta, 'processed_name', '') or "",
            "resolution": l1["resolution"],
            "season": l1["season"],
            "source": l1["source"],
            "subtitle": l1["subtitle"],
            "team": l1["team"],
            "title": l1["cn_name"] or l1["en_name"] or getattr(meta, 'processed_name', ''),
            "video_effect": getattr(meta, 'video_effect', None),
            "video_encode": l1["video_encode"],
            "year": l1["year"] or "",
            "tmdb_id": ctx.tmdb_id or "",
            "duration": "0s",
            "origin_country": "",
            "poster_path": None,
            "release_date": None,
            "vote_average": None,
            "secondary_category": None,
        }

        # 融合云端数据
        if cloud:
            ctx.final_result.update({
                "title": cloud.get("title") or cloud.get("name") or ctx.final_result["title"],
                "tmdb_id": str(cloud.get("id", "")),
                "poster_path": cloud.get("poster_path"),
                "release_date": cloud.get("release_date") or cloud.get("first_air_date"),
                "vote_average": cloud.get("vote_average"),
                "origin_country": ", ".join(cloud.get("origin_country", [])) if isinstance(cloud.get("origin_country"), list) else (cloud.get("origin_country") or ""),
            })
            if not ctx.final_result["year"] and ctx.final_result.get("release_date"):
                ctx.final_result["year"] = ctx.final_result["release_date"][:4]

        # --- 执行渲染规则 ---
        if ctx.custom_render:
            ctx.log("┃")
            ctx.log("┃ [DEBUG][STEP 8.5: 自定义渲染词处理]: 启动微服务引擎渲染")
            await RenderEngine.apply_rules(
                final_result=ctx.final_result,
                local_result=ctx.local_result,
                raw_filename=ctx.filename,
                rules=ctx.custom_render,
                logs=ctx.logs,
                tmdb_provider=ctx.tmdb_provider
            )
            ctx.log("┗ ✅ 渲染流程结束")

        # --- 审计日志 ---
        RenderReporter.report_l1_audit(ctx.logs, ctx.local_result)
        RenderReporter.report_final_audit(ctx.logs, ctx.final_result)

        duration = ctx.get_duration()
        ctx.final_result["duration"] = duration
        summary_text = RenderReporter.report_summary(ctx.logs, ctx.final_result, duration)

        ctx.summary = summary_text
