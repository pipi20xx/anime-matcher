"""
RenderReporter - 审计日志汇报
对齐主项目 recognition/render/reporter.py
"""
from typing import Dict, Any, List

class RenderReporter:
    """
    负责最终结论的汇报、日志打印及审计写入。
    """
    @staticmethod
    def report_l1_audit(logs: List[str], l1_dict: Dict[str, Any]):
        """L1 本地解析属性审计"""
        logs.append("┃")
        logs.append("┃ [DEBUG][STEP 7: 本地解析属性审计]: 原始提取结论")
        label_map = {
            "cn_name": "中文搜索块", "en_name": "英文搜索块", "type": "媒体类型",
            "season": "季度", "episode": "集数", "team": "制作小组"
        }
        for k in ["cn_name", "en_name", "type", "season", "episode", "team"]:
            if l1_dict.get(k): logs.append(f"┣ 🏷️ {label_map.get(k, k)}: {l1_dict[k]}")
        logs.append("┗ ✅ 本地解析完成")

    @staticmethod
    def report_final_audit(logs: List[str], final_dict: Dict[str, Any]):
        """最终结果属性审计"""
        logs.append("┃")
        logs.append("┃ [DEBUG][STEP 9: 最终结果属性审计]: 融合结论 (final_result)")
        label_map = {
            "title": "最终标题", "tmdb_id": "TMDB 编号", "category": "媒体类型",
            "season": "季度", "episode": "集数", "team": "制作小组",
            "resolution": "分辨率", "video_encode": "视频编码",
            "subtitle": "字幕语言", "processed_name": "渲染后标题"
        }
        for k in ["title", "tmdb_id", "category", "season", "episode", "team", "resolution", "video_encode", "subtitle", "processed_name"]:
            val = final_dict.get(k)
            logs.append(f"┣ 🔹 {label_map.get(k, k)}: {val if val else '-'}")

    @staticmethod
    def report_summary(logs: List[str], final_dict: Dict[str, Any], duration: str):
        """最终摘要"""
        summary_text = f"{'['+final_dict.get('team','')+'] ' if final_dict.get('team') else ''}{final_dict.get('category')} S{final_dict.get('season')}E{final_dict.get('episode')}"
        logs.append(f"┗ 🏁 识别完成：{summary_text} (总耗时: {duration})")
        return summary_text
