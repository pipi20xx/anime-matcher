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

    # [Fix] 优先从原始输入提取发布平台，防止被预处理噪声逻辑误删
    meta_obj.resource_platform, debug2_p = TagExtractor.extract_platform(input_name)
    logger_stub.debug_out("STEP 2: 元数据独立探测", debug2_y + debug2_s + debug2_p)

    # --- STEP 2.5: 技术规格预提取与标题屏蔽 (Noise Shielding) ---
    current_logs.append(f"┃")
    s_logs = []
    
    # [Strategy] 顶级优先级：全局自定义制作组扫描
    if custom_groups:
        import zhconv
        sorted_groups = sorted([g for g in custom_groups if g and len(g.strip()) >= 2], key=len, reverse=True)
        for g in sorted_groups:
            g_clean = re.sub(r"^\[(?:REMOTE|私有|社区|内置)\]", "", g).strip()
            if not g_clean: continue
            
            # [Crucial] 平台词与技术规格排他性检查
            from .constants import NOT_GROUPS
            if re.search(PLATFORM_RE, g_clean) or re.search(rf"(?i)^({NOT_GROUPS})$", g_clean):
                continue
            
            g_simp, g_trad = zhconv.convert(g_clean, "zh-hans"), zhconv.convert(g_clean, "zh-hant")
            p_esc, s_esc, t_esc = re.escape(g_clean), re.escape(g_simp), re.escape(g_trad)
            boundary_chars = r"a-zA-Z0-9\u4e00-\u9fa5\u3040-\u309f\u30a0-\u30ff"
            pattern = rf"(?i)(?<![{boundary_chars}])({p_esc}|{s_esc}|{t_esc})(?![{boundary_chars}])"
            
            match = re.search(pattern, processed_title)
            if match:
                # [Strategy] 发现锚点后进行智能扩张，以捕获联合发布块 (GroupA & GroupB)
                start, end = match.start(), match.end()
                l_pos, r_pos = start, end
                while l_pos > 0:
                    prev = processed_title[l_pos-1]
                    if prev in "★☆[]【】(){}": break
                    if prev == " ":
                        if l_pos > 1 and processed_title[l_pos-2] in "&+x":
                            l_pos -= 1; continue
                        else: break
                    if prev in "&+x": l_pos -= 1; continue
                    l_pos -= 1
                while r_pos < len(processed_title):
                    nxt = processed_title[r_pos]
                    if nxt in "★☆[]【】(){}": break
                    if nxt == " ":
                        if r_pos < len(processed_title)-1 and nxt in "&+x":
                            r_pos += 1; continue
                        else: break
                    if nxt in "&+x": r_pos += 1; continue
                    r_pos += 1
                
                full_block = processed_title[l_pos:r_pos].strip(" &+x")
                meta_obj.resource_team = full_block
                s_logs.append(f"┣ [Shield] 全局匹配命中制作组(含联合扩张): {full_block}")
                processed_title = (processed_title[:l_pos] + " " + processed_title[r_pos:]).strip()
                processed_title = re.sub(r"\s+", " ", processed_title)
                break

    # [New] 非括号首部制作组检测 (支持 Group★Title 或 Group Title 这种风格)
    if not meta_obj.resource_team:
        # 提取第一个空格或特殊装饰符之前的块
        # 由于星号已经在 pre_clean 被换成了空格，这里匹配首个空格前的文本
        first_block_match = re.search(r"^([^\s★☆\[【]+)", processed_title)
        if first_block_match:
            candidate = first_block_match.group(1).strip()
            from .constants import GROUP_KEYWORDS
            # 语义校验：块内必须包含制作组特征词 (如 字幕组, 制作, 社)
            if re.search(GROUP_KEYWORDS, candidate):
                # 排除明显的剧名特征 (如 [第01话])
                if not re.search(r"第?\d+[集话話回季]|[上下]卷", candidate):
                    meta_obj.resource_team = candidate
                    s_logs.append(f"┣ [Shield] 探测到首部特征制作组: {candidate}")
                    # 从标题中切除该块
                    processed_title = processed_title[first_block_match.end():].strip()
                    # 清理可能残留在开头的空格或星号碎屑
                    processed_title = re.sub(r"^[★☆■□◆◇●○•\s\-_/]+", "", processed_title).strip()

    # 预清洗：剥离掉开头的纯噪声中括号块
    for _ in range(2):
        leading_noise = re.match(r"^\[(?:搬运|搬運|新番|连载|連載|合集)\]|^【(?:搬运|搬運|新番|连载|連載|合集)】", processed_title)
        if leading_noise:
            noise_text = leading_noise.group(0)
            processed_title = processed_title[len(noise_text):].strip()
            s_logs.append(f"┣ [Shield] 自动剔除首部噪声块: {noise_text}")

    # 制作组先行锁定：探测通用括号
    if not meta_obj.resource_team:
        for _ in range(3):
            first_bracket = re.match(r"^\[([^\]]+)\]|^【([^】]+)】", processed_title)
            if not first_bracket: break
            candidate = first_bracket.group(1) or first_bracket.group(2)
            if candidate.strip() and not candidate.isdigit() and not re.search(PIX_RE, candidate):
                 is_noise = False
                 for nw in NOISE_WORDS:
                     if re.search(nw, candidate, flags=re.I):
                         is_noise = True; break
                 if not is_noise:
                     team, t_logs = TagExtractor.extract_release_group(processed_title)
                     if team:
                         meta_obj.resource_team = team
                         s_logs.extend(t_logs)
                         processed_title = re.sub(r"^\[[^\]]+\]|^【[^】]+】", "", processed_title, count=1).strip()
                         s_logs.append(f"┣ [Shield] 提前屏蔽首部制作组: {team}")
                         break
                     else: break
            raw_bracket = first_bracket.group(0)
            processed_title = processed_title[len(raw_bracket):].strip()
            s_logs.append(f"┣ [Shield] 自动剔除首部噪声块: {raw_bracket}")

    # 提取并抹除技术规格
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
            for m in matches: processed_title = processed_title.replace(m.group(0), " ")
            processed_title = re.sub(r"\s+", " ", processed_title)
    
    noise_shield = [
        r"(?i)\b(MKV|MP4|AVI|FLV|WMV|MOV|7z|ZIP|TS|7zip)\b",
        r"(?i)\b(Fin|END|Complete|Final)\b",
        r"(?i)(完结|全集|合集)",
        r"(?i)(精校|修正|修复|重制|修正版|无修正|未删减)",
        *NOISE_WORDS
    ]
    for np in noise_shield:
        try: processed_title = re.sub(np, " ", processed_title)
        except: continue
    processed_title = re.sub(r"\s+", " ", processed_title)
    shell_pattern = r"[\[\(\{【][\s\-\._/]*[\]\)\}】]"
    for _ in range(2): 
        processed_title = re.sub(shell_pattern, " ", processed_title)
        processed_title = re.sub(r"\s+", " ", processed_title)

    processed_title = processed_title.strip()
    sub_val, sub_logs = TagExtractor.extract_subtitle_lang(input_name)
    if sub_val: meta_obj.subtitle_lang = sub_val
    s_logs.extend(sub_logs)
    if s_logs: logger_stub.debug_out("STEP 2.5: 规格预处理与噪声屏蔽", s_logs)

    # --- STEP 3: 内核解析 ---
    current_logs.append(f"┃")
    safe_title = str(processed_title).strip()
    current_logs.append(f"┃ [DEBUG][STEP 3]: 调用 Anitopy 语义内核 (脱敏标题: {safe_title})")
    info_dict = {}
    try:
        if safe_title: info_dict = AnitopyWrapper.parse(processed_title) or {}
        else:
            current_logs.append(f"┣ ⚠️ 标题经预处理后为空，跳过内核解析")
            info_dict = {}
        ignore_keys = ["file_name", "file_extension", "file_type"]
        found_any = False
        for k, v in info_dict.items():
            if v is not None and k not in ignore_keys:
                val_str = ", ".join([str(i) for i in v]) if isinstance(v, list) else str(v)
                current_logs.append(f"┣ [RAW] {k}: {val_str}")
                found_any = True
        if not found_any: current_logs.append(f"┣ ⚠️ 内核未发现任何语义属性")
        current_logs.append(f"┗ ✅ 内核解析完成")
    except Exception as e: current_logs.append(f"┗ ❌ 内核解析异常: {str(e)}")

    # --- STEP 4-7: 后处理与精炼 ---
    PostProcessor.process(meta_obj, info_dict, input_name, processed_title, current_logs, custom_groups, logger_stub, batch_enhancement=batch_enhancement, fingerprint_data=fingerprint_data)
    return meta_obj
