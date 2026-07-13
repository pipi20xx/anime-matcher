"""
ParserStage - L1 本地解析阶段
对齐主项目 recognition/pipeline/parser.py
"""
import re
import os
from typing import Optional
from ..context import RecognitionContext
from recognition_engine.kernel import core_recognize
from recognition_engine.special_episode_handler import SpecialEpisodeHandler


def _is_chinese(text: str) -> bool:
    if not text: return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff': return True
    return False

def _split_title(title: str) -> list:
    if not title or '/' not in title: return [title] if title else []
    parts = [p.strip() for p in title.split('/') if p.strip()]
    if len(parts) < 2: return parts
    cn_titles = [p for p in parts if _is_chinese(p)]
    en_titles = [p for p in parts if not _is_chinese(p)]
    result = []
    if cn_titles: result.append(cn_titles[0])
    if en_titles: result.append(en_titles[0])
    return result if result else parts

def _clean_privileged_title(title: str) -> str:
    if not title: return title
    cleaned = re.sub(r'\.', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()


class ParserStage:
    """L1 解析 + 指纹预匹配"""

    @staticmethod
    async def execute(ctx: RecognitionContext):
        # --- 加载特权提取规则 ---
        if ctx.special_rules:
            SpecialEpisodeHandler.load_external_rules(ctx.special_rules)
            ctx.log(f"┃ [配置] 特权规则载入: {len(ctx.special_rules)} 条")

        # --- L1 内核解析 ---
        meta = core_recognize(
            input_name=ctx.filename,
            custom_words=ctx.custom_words,
            custom_groups=ctx.custom_groups,
            original_input=ctx.original_filename,
            current_logs=ctx.logs,
            batch_enhancement=ctx.batch_enhancement,
            force_filename=ctx.force_filename
        )
        ctx.raw_meta = meta

        # 封装 L1 原始结果
        ctx.local_result = {
            "cn_name": meta.cn_name, "en_name": meta.en_name, "team": meta.resource_team,
            "season": meta.begin_season or 1,
            "episode": meta.begin_episode if isinstance(meta.begin_episode, int) else 1,
            "is_batch": meta.is_batch,
            "end_episode": meta.end_episode if isinstance(meta.end_episode, int) else None,
            "type": ctx.tmdb_type if ctx.tmdb_type else (meta.type.value if hasattr(meta.type, "value") else str(meta.type)),
            "resolution": meta.resource_pix, "platform": meta.resource_platform,
            "source": meta.resource_type, "video_encode": meta.video_encode,
            "audio_encode": meta.audio_encode, "subtitle": meta.subtitle_lang, "year": meta.year
        }

        # --- 指纹预匹配 (智能记忆) ---
        current_tmdb_id = ctx.tmdb_id

        # 优先级1: L1 识别结果中的强制 ID
        if not current_tmdb_id and meta.forced_tmdbid:
            current_tmdb_id = meta.forced_tmdbid
            ctx.log(f"┃ [STAGE 1.5] 🚀 发现规则锁定 ID: {current_tmdb_id}")

        # 优先级2: 文件名指纹记忆
        if ctx.active_storage and not current_tmdb_id:
            fp_match = await ctx.local_cache.get_fingerprint_match(ctx.filename, ctx.logs)
            if fp_match:
                current_tmdb_id = fp_match.get("id")
                ctx.local_result["type"] = fp_match.get("type", ctx.local_result["type"])
                ctx.tmdb_match = fp_match  # 标记为指纹命中

        # 优先级3: 旧版标题记忆 (向后兼容)
        if ctx.active_storage and not current_tmdb_id:
            from ..storage_manager import storage
            pattern_key = f"{ctx.local_result['cn_name'] or ctx.local_result['en_name']}|{ctx.local_result['year']}"
            memory = storage.get_memory(pattern_key)
            if memory:
                current_tmdb_id = memory['tmdb_id']
                ctx.local_result['type'] = memory['media_type']
                ctx.log(f"┃ [STORAGE] ⚡ 命中标题特征记忆: 自动锁定 ID {current_tmdb_id}")

        ctx.tmdb_id = current_tmdb_id
