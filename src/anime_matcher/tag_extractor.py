import regex as re
import cn2an
from typing import Optional, Any, List, Tuple
from .constants import SEASON_PATTERNS, EPISODE_PATTERNS, CN_MAP, NOT_GROUPS, VIDEO_RE, PIX_RE, PLATFORM_RE, DYNAMIC_RANGE_RE, AUDIO_RE, SOURCE_RE

class TagExtractor:
    @staticmethod
    def roman_to_int(s: str) -> Optional[int]:
        s = s.upper().strip()
        if not re.match(r'^[IVX]+$', s): return None
        roman = {'I': 1, 'V': 5, 'X': 10}
        num = 0
        try:
            for i in range(len(s)):
                if i > 0 and roman[s[i]] > roman[s[i - 1]]:
                    num += roman[s[i]] - 2 * roman[s[i - 1]]
                else:
                    num += roman[s[i]]
            return num
        except: return None

    @staticmethod
    def chinese_to_number(text: str) -> Optional[int]:
        try:
            if text in CN_MAP: return CN_MAP[text]
            # 尝试罗马数字
            roman = TagExtractor.roman_to_int(text)
            if roman: return roman
            return int(cn2an.cn2an(text, mode='smart'))
        except: return None

    @staticmethod
    def extract_source(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别介质来源 (如 UHD.Blu-ray.Remux)"""
        matches = re.findall(SOURCE_RE, filename)
        if not matches: return None, []

        res = []
        seen = set()
        mapping = {
            "WEBRIP": "WebRip", "WEB-RIP": "WebRip", "WEBDL": "WEB-DL", "WEB-DL": "WEB-DL",
            "BLURAY": "Blu-ray", "BD": "Blu-ray", "BLU": "Blu-ray",
            "HDTV": "HDTV", "UHDTV": "UHDTV", "DVDRIP": "DVD-Rip", "BDRIP": "BD-Rip",
            "REMUX": "Remux", "UHD": "UHD", "Pdtv": "PDTV", "Dvdscr": "DVD-SCR", "WEB": "WEB"
        }

        for m in matches:
            upper_m = m.upper().replace("-", "")
            final_val = mapping.get(upper_m, m)
            if final_val not in seen:
                res.append(final_val)
                seen.add(final_val)
        
        def sort_source(x):
            order = ["UHD", "Blu-ray", "WEB-DL", "WebRip", "HDTV", "Remux"]
            return order.index(x) if x in order else 99
        
        res.sort(key=sort_source)
        final_str = ".".join(res)
        return final_str, [f"[规则][内置] 介质来源: {'.'.join(matches)} -> {final_str}"]

    @staticmethod
    def extract_year(text: str) -> Tuple[Optional[str], List[str]]:
        match = re.search(r"\b((19|20)\d{2})\b", text)
        if match: return match.group(1), [f"[规则][内置] 上映年份: {match.group(1)}"]
        return None, []

    @staticmethod
    def extract_season(text: str) -> Tuple[Optional[int], List[str]]:
        for p in SEASON_PATTERNS:
            match = re.search(p, text, re.I)
            if match:
                val = TagExtractor.chinese_to_number(match.group(1))
                if val: return val, [f"[规则][内置] 季号: S{val}"]
        
        # [New] 罗马数字季号支持 (Season III, S IV)
        roman_explicit = re.search(r"(?i)(?:Season|S|第)\s*([IVX]+)(?:\s*季)?\b", text)
        if roman_explicit:
            val = TagExtractor.roman_to_int(roman_explicit.group(1))
            if val: return val, [f"[规则][内置] 罗马季号: S{val}"]

        # [New] 罗马数字后缀支持 (Title III [01]...)
        # 匹配位于空格之后，且后面紧跟 [ ( 或 结束符 的罗马数字
        roman_suffix = re.search(r"\s([IVX]+)(?=\s|\[|\(|【|（|$)", text)
        if roman_suffix:
            val = TagExtractor.roman_to_int(roman_suffix.group(1))
            # 限制范围 1-10 防止误伤 I (1) 或过大的词
            if val and 1 < val <= 10:
                return val, [f"[规则][内置] 罗马后缀季号: S{val}"]

        return None, []

    @staticmethod
    def validate_episode(ep_val: Any, filename: str) -> Tuple[Optional[int], List[str]]:
        if ep_val is None: return None, []
        try:
            val_str = str(ep_val[0] if isinstance(ep_val, list) else ep_val)
            if re.search(rf"(?i)[Hx]\.?{val_str}\b", filename) or re.search(rf"(?i)\b{val_str}[Pp]\b", filename):
                if not re.search(rf"(?i)(EP|第|E|episode|#)\s*0*{val_str}", filename):
                    return None, [f"[规则][内置] 集数误报拦截: {val_str}"]
            return int(val_str), [f"[规则][内置] 集数校验通过: E{val_str}"]
        except: return None, []

    @staticmethod
    def extract_episode(text: str, filename_context: str = "") -> Tuple[Optional[int], List[str]]:
        for p in EPISODE_PATTERNS:
            match = re.search(p, text, re.I)
            if match:
                val = match.group(1)
                return TagExtractor.validate_episode(val, filename_context)
        return None, []

    @staticmethod
    def extract_release_group(filename: str, info_group: Optional[str] = None) -> Tuple[Optional[str], List[str]]:
        """强化版制作组提取"""
        logs = []
        def is_valid_group(g: str) -> bool:
            if not g: return False
            g = g.strip()
            if len(g) < 2: return False
            if re.match(r"^\d+$", g): return False
            if "@" in g:
                parts = g.split("@")
                if len(parts[-1].strip()) < 2: return False
            digit_count = sum(c.isdigit() for c in g)
            if digit_count / len(g) > 0.8: return False
            return True

        if info_group and re.search(PLATFORM_RE, info_group):
            logs.append(f"[规则][内置] 平台词纠偏: {info_group}")
            info_group = None

        if info_group and info_group.upper() not in NOT_GROUPS and is_valid_group(info_group):
            return info_group, [f"[规则][内置] 制作组: {info_group}"]
        
        gm = re.match(r"^\[([^\]]+)\]", filename)
        if gm:
            g_candidate = gm.group(1)
            if not re.search(PLATFORM_RE, g_candidate) and is_valid_group(g_candidate):
                return g_candidate, [f"[规则][内置] 首部制作组: {g_candidate}"]
            
        base_name = re.sub(r"\.[a-zA-Z0-9]+$", "", filename)
        tm = re.search(r"-([a-zA-Z0-9\.@[_\-]+)$", base_name) 
        if tm:
            raw = tm.group(1)
            g_candidate = raw
            # 不再一刀切拆分 @，保留完整的 A@B 结构，这在 PT 站点中代表了“来源@发布组”

            if g_candidate.upper() not in NOT_GROUPS and is_valid_group(g_candidate):
                 msg = f"[规则][内置] 尾部制作组: {g_candidate}"

                 return g_candidate, [msg]
        return None, []

    @staticmethod
    def extract_platform(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别发布平台"""
        match = re.search(PLATFORM_RE, filename)
        if match:
            raw = match.group(0).lstrip('-')
            mapping = {"CR": "Crunchyroll", "NF": "Netflix", "AMZN": "Amazon", "ATVP": "AppleTV+", "DSNP": "Disney+", "iT": "iTunes"}
            upper_raw = raw.upper()
            final_val = mapping.get(upper_raw, "iTunes" if raw == "iT" else ("Amazon" if upper_raw == "CRAMZN" else raw))
            log_msg = f"[规则][内置] 发布平台: {raw}"
            if final_val != raw: log_msg += f" -> {final_val}"
            return final_val, [log_msg]
        return None, []

    @staticmethod
    def extract_dynamic_range(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别动态范围指标"""
        matches = re.findall(DYNAMIC_RANGE_RE, filename)
        if not matches: return None, []
        found_tags = set(m.upper().replace(" ", "") for m in matches)
        res = []
        if any(x in found_tags for x in ["DOVI", "DV", "DOLBYVISION"]): res.append("Dolby Vision")
        if "HDR10+" in found_tags: res.append("HDR10+")
        elif "HDR10" in found_tags: res.append("HDR10")
        elif "HDR" in found_tags: res.append("HDR")
        if "HLG" in found_tags: res.append("HLG")
        if "IMAX" in found_tags: res.append("IMAX")
        if "SDR" in found_tags: res.append("SDR")
        final_val = ".".join(res) if res else None
        if final_val: return final_val, [f"[规则][内置] 动态范围: {final_val}"]
        return None, []

    @staticmethod
    def extract_resolution(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别分辨率标准化"""
        match = re.search(PIX_RE, filename)
        if match:
            raw = match.group(0).lower()
            if "4k" in raw or "2160p" in raw: return "4K", [f"[规则][内置] 分辨率标准化: {match.group(0)} -> 4K"]
            if "1080p" in raw: return "1080P", [f"[规则][内置] 分辨率标准化: {match.group(0)} -> 1080P"]
            if "720p" in raw: return "720P", [f"[规则][内置] 分辨率标准化: {match.group(0)} -> 720P"]
            if "x" in raw:
                try:
                    dims = [int(x) for x in re.findall(r"\d+", raw)]
                    if dims:
                        max_d, min_d = max(dims), min(dims)
                        if max_d >= 3840 or min_d >= 2160: final_val = "4K"
                        elif max_d >= 1920 or min_d >= 1080: final_val = "1080P"
                        elif max_d >= 1280 or min_d >= 720: final_val = "720P"
                        else: final_val = f"{min_d}P"
                        return final_val, [f"[规则][内置] 分辨率标准化 ({match.group(0)}): {final_val}"]
                except: pass
            return raw.upper(), []
        return None, []

    @staticmethod
    def extract_audio_encode(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别音频规格"""
        matches = list(re.finditer(AUDIO_RE, filename))
        if matches:
            final_tags, raw_log_parts, seen_combos = [], [], set()
            for m in matches:
                codec_raw = m.group(1).upper().replace(".", "").replace("-", "").replace("_", "")
                codec = codec_raw
                if "ATMOS" in codec_raw: codec = "Dolby Atmos"
                elif "DTSHDMA" in codec_raw or "DTSMA" in codec_raw: codec = "DTS-HD MA"
                elif "DTSHD" in codec_raw: codec = "DTS-HD"
                elif "EAC3" in codec_raw or "DDP" in codec_raw or "DD+" in codec_raw: codec = "E-AC-3"
                elif "AC3" in codec_raw or "DD" == codec_raw: codec = "AC-3"
                elif "TRUEHD" in codec_raw: codec = "TrueHD"
                elif "LPCM" in codec_raw or "PCM" in codec_raw: codec = "LPCM"
                elif "DTS" == codec_raw: codec = "DTS"
                elif "AAC" in codec_raw: codec = "AAC"
                elif "FLAC" in codec_raw: codec = "FLAC"
                elif "OPUS" in codec_raw: codec = "Opus"
                elif "VORBIS" in codec_raw: codec = "Vorbis"
                channel_raw = m.group(2).lower().replace("_", "") if m.group(2) else ""
                channel = "2.0" if "2ch" in channel_raw else ("5.1" if "6ch" in channel_raw else ("7.1" if "8ch" in channel_raw else channel_raw))
                full_tag = f"{codec} {channel}".strip() if channel else codec
                if full_tag not in seen_combos:
                    final_tags.append(full_tag); seen_combos.add(full_tag); raw_log_parts.append(m.group(0))
            def sort_key(x):
                base = x.split()[0] 
                order = ["Dolby", "DTS-HD", "TrueHD", "LPCM", "E-AC-3", "AC-3", "DTS", "FLAC", "Opus", "AAC", "Vorbis"]
                for i, o in enumerate(order):
                    if base.startswith(o): return i
                return 99
            final_tags.sort(key=sort_key)
            final_str = " ".join(final_tags)
            return final_str, [f"[规则][内置] 音频规格: {' '.join(raw_log_parts)} -> {final_str}"]
        return None, []

    @staticmethod
    def extract_video_encode(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别视频规格"""
        match = re.search(VIDEO_RE, filename)
        if match:
            raw = match.group(0).upper().replace(".", "").replace("-", "")
            final_val = "H.265" if ("265" in raw or "HEVC" in raw) else ("H.264" if ("264" in raw or "AVC" in raw) else ("AV1" if "AV1" in raw else match.group(0).upper() if "MPEG" in raw else match.group(0)))
            return final_val, [f"[规则][内置] 视频规格: {match.group(0)} -> {final_val}"]
        return None, []

    @staticmethod
    def extract_subtitle_lang(filename: str) -> Tuple[Optional[str], List[str]]:
        """[内置] 识别字幕语言"""
        logs = []
        rules = [
            (r"\[BIG5\]|\[BIG5_MP4\]|\[CHT\]", "繁体内嵌"), (r"\[GB\]|\[GB_MP4\]|\[GB_CN\]|\[CHS\]", "简体内嵌"),
            (r"简体双语|简日特效字幕", "简日双语"), (r"\[CHI_JPN\]|JPSC&JPTC|SUBx3|\[jap_chs_cht\]", "简繁日内封"),
            (r"ASSx1|SRTx1", "简体内封"), (r"\bASSx2|\bASS|\bSRTx2|\bSRT", "简繁内封"),
            (r"(?i)(CHS|GB|SC)(&|_|＆|\x20)(CHT|BIG5|TC)(&|_|＆|\x20)JA?PN?", "简繁日内封"),
            (r"(?i)(CHS|GB|SC)_JA?PN?(&|＆|\x20)(CHT|BIG5|TC)_JA?PN?", "简繁日内封"),
            (r"(?i)(CHS|GB|SC)(_|&|＆|\x20)(CHT|BIG5|TC)", "简繁内封"),
            (r"(?i)(CHS|GB|SC)_?(CHT|BIG5|TC)", "简繁内封"),
            (r"(?i)(CHS|GB|SC)(_|&|＆|\x20)(-)JA?PN?", "简日双语"),
            (r"(?i)(CHT|BIG5|TC)(_|&|＆|\x20)(-)JA?PN?", "繁日双语"),
            (r"(?i)\[JA?PN?(_|&|＆|\x20)?(SC|CHS|GB)\]", "简日双语"),
            (r"(?i)\[JA?PN?(_|&|＆|\x20)?(TC|CHT|BIG5)\]", "繁日双语"),
            (r"简日内嵌|簡日內嵌", "简日内嵌"), (r"繁日内嵌|繁日內嵌", "繁日内嵌"), (r"简繁内嵌|簡繁內嵌", "简繁内嵌"), 
            (r"简体内嵌|簡體內嵌", "简体内嵌"), (r"繁体内嵌|繁體內嵌", "繁体内嵌"),
            (r"简繁日内封|簡繁日內封", "简繁日内封"), (r"简日内封|簡日內封", "简日内封"), (r"繁日内封|繁日內封", "繁日内封"), 
            (r"简体内封|簡體內封", "简体内封"), (r"繁体内封|繁體內封", "繁体内封"),
        ]
        for pattern, label in rules:
            if re.search(pattern, filename, re.I):
                logs.append(f"[规则][内置] 字幕语言: {label}")
                return label, logs
        f_norm = filename.upper().replace("_", " ").replace("&", " ").replace("+", " ")
        langs = set()
        if re.search(r"(简日|CHS\s*JAP|SC\s*JP)", f_norm): langs.add("简日双语")
        elif re.search(r"(繁日|CHT\s*JAP|TC\s*JP)", f_norm): langs.add("繁日双语")
        elif re.search(r"(简繁|CHS\s*CHT|SC\s*TC)", f_norm): langs.add("简繁双语")
        if not langs:
            has_chs = re.search(r"(CHS|GB|SC|简体|简中)", f_norm)
            has_cht = re.search(r"(CHT|BIG5|TC|繁体|繁中)", f_norm)
            has_jp = re.search(r"(JAP|JP|日文|日语)", f_norm)
            if has_chs and has_jp: langs.add("简日双语")
            elif has_cht and has_jp: langs.add("繁日双语")
            elif has_chs and has_cht: langs.add("简繁双语")
            elif has_chs: langs.add("简体中文")
            elif has_cht: langs.add("繁体中文")
            elif has_jp: langs.add("日文")
        if re.search(r"(ENG|EN|英文|英语)", f_norm):
            if not langs: langs.add("英文")
        final_lang = " & ".join(sorted(list(langs))) if langs else None
        if final_lang: logs.append(f"[规则][内置] 字幕语言: {final_lang}")
        return final_lang, logs
