"""
RecognitionProcessor - 识别处理器
直接调用主项目 recognition_service 的 Pipeline 架构，无需下载或手动加载内核。
"""
import os
import asyncio
import json
# paths.py 会自动设置 AM_DATABASE_PATH 并将主项目 src/ 加入 sys.path
from src.utils.paths import PROJECT_ROOT  # noqa: F401


class RecognitionResult:
    """识别结果包装器，适配 RenameEngine 的接口"""

    def __init__(self, pipeline_result: dict):
        self._pipeline_result = pipeline_result
        self.logs = pipeline_result.get("logs", [])
        self._data = pipeline_result.get("final_result", {})
        # 将 final_result 的字段挂载为属性
        for k, v in self._data.items():
            setattr(self, k, v)

    def to_dict(self) -> dict:
        return self._data


class RecognitionProcessor:
    """
    识别处理器 - 直接调用 recognition_service Pipeline。
    替代旧版手动拼装 core_recognize / TMDBProvider / BangumiProvider 的方式。
    """

    def __init__(self, config_data=None):
        self.config = config_data or {}

    def recognize_file(self, filename_path: str) -> RecognitionResult:
        """同步入口：在独立事件循环中运行异步 Pipeline"""
        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(self._async_recognize(filename_path))
            loop.close()
            return result
        except Exception as e:
            return RecognitionResult({
                "success": False,
                "final_result": {
                    "title": "异常",
                    "filename": os.path.basename(filename_path),
                    "path": filename_path,
                },
                "logs": [f"[CRITICAL] {e}"],
            })

    async def _async_recognize(self, filename_path: str) -> RecognitionResult:
        from recognition_service.context import RecognitionContext
        from recognition_service.recognizer import RecognitionWorkflow

        original_filename = os.path.basename(filename_path)

        # --- 从规则数据库加载规则 ---
        from src.core.rules import RuleManager
        db_noise = RuleManager.get_merged_rules('noise')
        db_group = RuleManager.get_merged_rules('group')
        db_privileged = RuleManager.get_merged_rules('privileged')
        db_render = RuleManager.get_merged_rules('render')

        # --- 获取自定义覆盖参数 ---
        custom_settings = self.config.get('custom_settings', {})
        ui_tmdb_id = custom_settings.get('tmdb_id_override')
        ui_media_type = custom_settings.get('media_type_override', 'tv')

        # --- 构建 Pipeline 上下文 ---
        ctx = RecognitionContext(
            filename=original_filename,
            original_filename=original_filename,
            all_noise=list(set(self.config.get('custom_words', []) + db_noise)),
            all_groups=list(set(self.config.get('custom_groups', []) + db_group)),
            all_render=db_render,
            all_privilege=db_privileged,
            force_filename=True,
            batch_enhance=self.config.get('batch_enhancement', False),
            with_cloud=self.config.get('with_cloud', False),
            use_fingerprint=self.config.get('use_storage', False),
            anime_priority=self.config.get('anime_priority', True),
            bangumi_priority=self.config.get('bangumi_priority', False),
            bangumi_failover=self.config.get('bangumi_failover', True),
            api_key=self.config.get('tmdb_api_key') or None,
            tmdb_proxy=self.config.get('tmdb_proxy') or None,
            forced_tmdb_id=ui_tmdb_id or None,
            forced_type=ui_media_type if ui_media_type != 'tv' else None,
            bangumi_token=self.config.get('bangumi_token') or None,
            bangumi_proxy=self.config.get('bangumi_proxy') or None,
        )

        # --- 运行完整 Pipeline ---
        workflow = RecognitionWorkflow(ctx)
        result = await workflow.run()

        # --- 补充 path 字段 (Pipeline 用 filename 存的是纯文件名) ---
        if result.get("final_result"):
            result["final_result"]["path"] = filename_path

        return RecognitionResult(result)
