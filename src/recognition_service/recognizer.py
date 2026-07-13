"""
RecognitionWorkflow - Pipeline 编排器
对齐主项目 recognition/recognizer.py
"""
import logging
from .context import RecognitionContext
from .pipeline import ParserStage, MatcherStage, EnrichmentStage, MaintenanceStage
from .renderer import ResultRenderer

logger = logging.getLogger("recognition_service.recognizer")


class RecognitionWorkflow:
    """
    识别工作流编排器：按顺序执行 Pipeline 各阶段。
    """

    @staticmethod
    async def recognize(ctx: RecognitionContext):
        """执行完整识别流程"""
        try:
            # === 配置审计 ===
            ctx.report_config()

            # === STAGE 1: L1 本地解析 ===
            await ParserStage.execute(ctx)

            # === STAGE 2: L2 云端对撞 ===
            await MatcherStage.execute(ctx)

            # === STAGE 2.5: L2.5 字段补全 ===
            await EnrichmentStage.execute(ctx)

            # === STAGE 3: 最终报告构建 + L3 渲染 ===
            await ResultRenderer.execute(ctx)

            # === STAGE 4: L3 记忆维护 ===
            await MaintenanceStage.execute(ctx)

        except Exception as e:
            import traceback
            traceback.print_exc()
            ctx.log(f"┗ ❌ 识别流程异常: {e}")
            raise
