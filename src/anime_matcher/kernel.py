import regex as re
from typing import List, Optional, Tuple, Any, Dict, Callable

from .constants import MediaType, PIX_RE, VIDEO_RE, AUDIO_RE, SOURCE_RE, DYNAMIC_RANGE_RE, PLATFORM_RE, NOISE_WORDS
from .data_models import MetaBase
from .title_cleaner import TitleCleaner
from .tag_extractor import TagExtractor
from .anitopy_wrapper import AnitopyWrapper
from .post_processor import PostProcessor

class LoggerStub:
    """
    A lightweight logger that writes to a list.
    Mimics RecognitionLogger interface for compatibility.
    """
    def __init__(self, logs: List[str]):
        self.logs = logs
    
    def log(self, message: str):
        self.logs.append(message)
        
    def debug_out(self, section: str, msgs: List[str]):
        self.logs.append(f"┃ [DEBUG][{section}]: 启动子流程审计")
        if not msgs:
            self.logs.append(f"┣ ⏩ 该步骤未产生关键动作")
        else:
            for m in msgs: self.logs.append(f"┣ {m}")
        self.logs.append(f"┗ ✅ 流程结束")

def core_recognize(
    input_name: str, 
    custom_words: List[str], 
    custom_groups: List[str], 
    original_input: str, 
    current_logs: List[str],
    batch_enhancement: bool = False, 
    fingerprint_data: Dict[str, Any] = None, 
    force_filename: bool = False
) -> MetaBase:
    """
    The Pure Recognition Kernel.
    Stateless, I/O-free (except via callbacks).
    """
    logger_stub = LoggerStub(current_logs)

    meta_obj = MetaBase(type=MediaType.UNKNOWN)
    # --- STEP 1: 预处理 ---
    processed_title, forced, debug1 = TitleCleaner.pre_clean(input_name, custom_words, force_filename=force_filename)
    meta_obj.processed_name = input_name 
    logger_stub.debug_out("STEP 1: 预处理与自定义规则", debug1)
    if forced:
        for k, v in forced.items(): current_logs.append(f"┣ [DEBUG][Forced] 应用强制元数据: {k} = {v}")
        if "tmdbid" in forced: meta_obj.forced_tmdbid = forced["tmdbid"]
        if "type" in forced: meta_obj.type = MediaType.TV if forced["type"] == "tv" else MediaType.MOVIE
        if "s" in forced: meta_obj.begin_season = int(forced["s"])
        if "e" in forced: meta_obj.begin_episode = int(forced["e"])

    # --- STEP 2: 独立挖掘 ---
    current_logs.append(f"┃")
    meta_obj.year, debug2_y = TagExtractor.extract_year(processed_title)
    
    # 只有在未指定强制季数时，才尝试提取季数
    debug2_s = []
    if meta_obj.begin_season is None:
        meta_obj.begin_season, debug2_s = TagExtractor.extract_season(processed_title)
    else:
        debug2_s = [f"保留强制季数 S{meta_obj.begin_season}"]

    meta_obj.resource_platform, debug2_p = TagExtractor.extract_platform(processed_title)
    logger_stub.debug_out("STEP 2: 元数据独立探测", debug2_y + debug2_s + debug2_p)

    # --- STEP 2.5: 技术规格预提取与标题屏蔽 (Noise Shielding) ---
    current_logs.append(f"┃")
    s_logs = []
    
    # 制作组先行锁定：如果首部有 [Group]，提前识别并屏蔽
    first_bracket = re.match(r"^\[([^\]]+)\]|^【([^】]+)】", processed_title)
    if first_bracket:
        candidate = first_bracket.group(1) or first_bracket.group(2)
        # 简单校验：不是纯数字，且不包含分辨率关键词
        if not candidate.isdigit() and not re.search(PIX_RE, candidate):
             # [Optimization] 如果该词本身就是噪音词（如 "搬運"），则跳过制作组识别
             is_noise = False
             for nw in NOISE_WORDS:
                 if re.search(nw, candidate, flags=re.I):
                     is_noise = True
                     break
             
             if not is_noise:
                 team, t_logs = TagExtractor.extract_release_group(processed_title)
                 if team:
                     meta_obj.resource_team = team
                     s_logs.extend(t_logs)
                     # 强力移除首部字幕组块，防止干扰
                     processed_title = re.sub(r"^\[[^\]]+\]|^【[^】]+】", "", processed_title, count=1).strip()
                     s_logs.append(f"┣ [Shield] 提前屏蔽首部制作组: {candidate}")
                 else:
                     s_logs.append(f"┣ [Shield] 忽略首部疑似制作组但非核心组的块: {candidate}")
             else:
                 s_logs.append(f"┣ [Shield] 发现首部块为已知噪音词，已忽略: {candidate}")

                 # [Optimization] 如果移除首部组名后，标题仍然以括号开头，
                 # 则将该括号“脱壳”，防止 Anitopy 再次将其误判为制作组
                 if processed_title.startswith("[") or processed_title.startswith("【"):
                     # 寻找对应的闭合括号
                     end_char = "]" if processed_title.startswith("[") else "】"
                     end_idx = processed_title.find(end_char)
                     if end_idx > 0:
                         # 提取括号内容并替换掉原括号
                         inner_content = processed_title[1:end_idx]
                         processed_title = inner_content + " " + processed_title[end_idx+1:]
                         processed_title = processed_title.strip()
                         s_logs.append(f"┣ [Optimization] 对次级括号执行脱壳处理，引导内核识别标题")

    # 提取并抹除的正则列表
    shield_patterns = [
        (PIX_RE, TagExtractor.extract_resolution, "resource_pix"),
        (VIDEO_RE, TagExtractor.extract_video_encode, "video_encode"),
        (AUDIO_RE, TagExtractor.extract_audio_encode, "audio_encode"),
        (SOURCE_RE, TagExtractor.extract_source, "resource_type"),
        (DYNAMIC_RANGE_RE, TagExtractor.extract_dynamic_range, "video_effect"),
        (PLATFORM_RE, TagExtractor.extract_platform, "resource_platform"),
    ]

    for pattern, extractor_func, attr_name in shield_patterns:
        matches = list(re.finditer(pattern, processed_title))
        if matches:
            if extractor_func:
                val, logs = extractor_func(processed_title)
                if val and attr_name:
                    setattr(meta_obj, attr_name, val)
                    s_logs.extend(logs)
            # 原地屏蔽：保持结构，避免产生大量碎片空格
            for m in matches:
                # 尽量只替换内容，不破坏前后的点
                raw_text = m.group(0)
                processed_title = processed_title.replace(raw_text, " ")
            
            # 合并连续空格
            processed_title = re.sub(r"\s+", " ", processed_title)
    
    # 强力噪音屏蔽 (包含容器后缀, 完结标志, 压制术语 and NOISE_WORDS)
    noise_shield = [
        r"(?i)\b(MKV|MP4|AVI|FLV|WMV|MOV|7z|ZIP|TS|7zip)\b", # 常见后缀
        r"(?i)\b(Fin|END|Complete|Final)\b", # 英文完结标志
        r"(?i)(完结|全集|合集)", # 中文完结标志
        r"(?i)(精校|修正|修复|重制|修正版|无修正|未删减)", # 质量术语
        *NOISE_WORDS # 库内所有噪音
    ]
    for np in noise_shield:
        try:
            if np and processed_title:
                processed_title = re.sub(np, " ", processed_title)
        except:
            continue
    
    # 最后统一清理一下空格，并执行“空壳括号”保险清理
    processed_title = re.sub(r"\s+", " ", processed_title)
    
    # 保险清理：移除被掏空后的空壳括号 (如 [ ], [ - ], ( ), 【 】)
    # 只有当括号内全为空格或常用分隔符时，才视为垃圾并清理
    shell_pattern = r"[\[\(\{【][\s\-\._/]*[\]\)\}】]"
    for _ in range(2): # 跑两遍以处理可能产生的嵌套壳
        processed_title = re.sub(shell_pattern, " ", processed_title)
        processed_title = re.sub(r"\s+", " ", processed_title)

    processed_title = processed_title.strip()

    # 独立处理字幕语言
    sub_val, sub_logs = TagExtractor.extract_subtitle_lang(processed_title)
    if sub_val:
        meta_obj.subtitle_lang = sub_val
        s_logs.extend(sub_logs)

    if s_logs:
        logger_stub.debug_out("STEP 2.5: 规格预处理与噪声屏蔽", s_logs)

    # --- STEP 3: 内核解析 ---
    current_logs.append(f"┃")
    safe_title = str(processed_title).strip()
    current_logs.append(f"┃ [DEBUG][STEP 3]: 调用 Anitopy 语义内核 (脱敏标题: {safe_title})")
    info_dict = {}
    try:
        info_dict = AnitopyWrapper.parse(processed_title)
        
        # 记录所有非空解析字段 (排除掉已知的冗余字段)
        ignore_keys = ["file_name", "file_extension", "file_type"]
        found_any = False
        for k, v in info_dict.items():
            if v is not None and k not in ignore_keys:
                val_str = ", ".join([str(i) for i in v]) if isinstance(v, list) else str(v)
                current_logs.append(f"┣ [RAW] {k}: {val_str}")
                found_any = True
        
        if not found_any:
            current_logs.append(f"┣ ⚠️ 内核未发现任何语义属性")
            
        current_logs.append(f"┗ ✅ 内核解析完成")
    except Exception as e:
        current_logs.append(f"┗ ❌ 内核解析异常: {str(e)}")

    # --- STEP 4-7: 后处理与精炼 ---
    PostProcessor.process(
        meta_obj, 
        info_dict, 
        input_name, 
        processed_title, 
        current_logs, 
        custom_groups, 
        logger_stub, 
        batch_enhancement=batch_enhancement, 
        fingerprint_data=fingerprint_data
    )
    
    return meta_obj
