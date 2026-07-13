"""
EnrichmentStage - L2.5 元数据字段补全
对齐主项目 recognition/pipeline/enricher.py（简化版，无 TmdbMateFull）
"""
from ..context import RecognitionContext


class EnrichmentStage:
    """L2.5 字段补全：将云端数据融合到 local_result 和 final_result"""

    @staticmethod
    async def execute(ctx: RecognitionContext):
        if not ctx.cloud_match:
            return

        cloud = ctx.cloud_match
        l1 = ctx.local_result

        # 类型修正
        if cloud.get("media_type"):
            l1["type"] = cloud["media_type"]

        # 如果云端有季数信息，以云端为准（仅当本地未指定时）
        if cloud.get("number_of_seasons") and not ctx.raw_meta.begin_season:
            l1["season"] = 1
