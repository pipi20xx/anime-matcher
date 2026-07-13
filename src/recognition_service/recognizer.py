"""
RecognitionWorkflow - Pipeline 编排器
对齐主项目 recognition/recognizer.py
"""
import logging
from typing import Tuple, Dict, Any, List
from .context import RecognitionContext
from .pipeline import ParserStage, MatcherStage, EnrichmentStage, MaintenanceStage
from .renderer import ResultRenderer

logger = logging.getLogger("recognition_service.recognizer")


class RecognitionWorkflow:
    """
    Recognition Orchestrator (Layer 3)
    High-level pipeline management.
    """
    def __init__(self, ctx: RecognitionContext):
        self.ctx = ctx

    async def run(self) -> Dict[str, Any]:
        # 1. 基础解析阶段 (Kernel + Rules)
        await ParserStage.run(self.ctx)

        # 2. 元数据匹配阶段 (Fingerprint + Cloud)
        await MatcherStage.run(self.ctx)

        # 3. 深度字段补全阶段 (Enrichment)
        await EnrichmentStage.run(self.ctx)

        # 4. 后处理与维护阶段 (Fingerprint Sync + Cache Update)
        await MaintenanceStage.run(self.ctx)

        # 5. 渲染与汇报阶段
        return await ResultRenderer.apply_to_context(self.ctx)


class MovieRecognizer:
    """
    识别入口 (对齐主项目 MovieRecognizer)
    """
    @staticmethod
    async def recognize_full(filename: str, **kwargs) -> Tuple[Dict[str, Any], List[str]]:
        """
        全链路识别接口。
        返回: (result_data, logs)
        result_data 结构: { success, final_result, raw_meta, tmdb_match, logs }
        """
        ctx = RecognitionContext(filename, **kwargs)
        workflow = RecognitionWorkflow(ctx)
        result = await workflow.run()
        return result, ctx.logs
