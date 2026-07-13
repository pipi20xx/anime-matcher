"""
MaintenanceStage - L3 指纹与元数据写入
对齐主项目 recognition/pipeline/maintenance.py
"""
from ..context import RecognitionContext


class MaintenanceStage:
    """L3 记忆维护：保存指纹和元数据到本地存储"""

    @staticmethod
    async def execute(ctx: RecognitionContext):
        if not ctx.active_storage:
            return

        if not ctx.cloud_match:
            return

        # 保存文件名指纹
        await ctx.local_cache.save_fingerprint(ctx.filename, ctx.cloud_match, ctx.logs)

        # 保存元数据
        tmdb_id = str(ctx.cloud_match.get("id", ""))
        media_type = ctx.cloud_match.get("media_type") or ctx.local_result.get("type", "tv")
        if tmdb_id:
            await ctx.local_cache.save_metadata(tmdb_id, media_type, ctx.cloud_match, ctx.logs)
