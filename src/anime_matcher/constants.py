from enum import Enum

class MediaType(Enum):
    MOVIE = "movie"
    TV = "tv"
    UNKNOWN = "unknown"

# 1. 影音规格
# 修改: 使用 lookarounds 替代 \b，以支持下划线 _ 作为分隔符 (VCB-Studio 风格)
PIX_RE = r"(?i)(?<![a-zA-Z0-9])((\d{3,4}[Pp])|([248][Kk])|(\d{3,4}[xX]\d{3,4}))(?![a-zA-Z0-9])"
VIDEO_RE = r"(?i)(?<![a-zA-Z0-9])(H\.?26[45]|[Xx]26[45]|AVC|HEVC|VC[0-9]?|MPEG[0-9]?|Xvid|DivX|AV1)(?![a-zA-Z0-9])"
AUDIO_RE = r"(?i)(?<![a-zA-Z0-9])(DTS-?HD(?:\.MA|[-\s]MA)?|DTS(?:\.MA|[-\s]MA)?|Atmos|TrueHD|AC-?3|DDP|DD\+|DD|AAC|FLAC|Vorbis|Opus|E-?AC-?3|LPCM|PCM)(?:(?:(?:\s*|\.|_|-)(?=[0-9]))?([0-9]\.[0-9](?:\+[0-9]\.[0-9])?|[0-9]ch))?(?![a-zA-Z0-9])"
SOURCE_RE = r"(?i)(?<![a-zA-Z0-9])(WEB-DL|WEBRIP|WEB-RIP|BDRIP|DVDRIP|HDRip|BLURAY|UHDTV|HDTV|HDDVD|REMUX|UHD|Pdtv|Dvdscr|BLU|WEB|BD)(?![a-zA-Z0-9])"
# 拆分原 EFFECT_RE: 独立出动态范围
DYNAMIC_RANGE_RE = r"(?i)(?<![a-zA-Z0-9])(HDR10\+|HDR10|HDR|HLG|Dolby\s*Vision|DoVi|DV|SDR|IMAX)(?![a-zA-Z0-9])"
# 剩余的作为版本/其他特效标签
EFFECT_RE = r"(?i)(?<![a-zA-Z0-9])(3D|REPACK|HQ|Remastered|Extended|Uncut|Internal|Pro|Proper)(?![a-zA-Z0-9])"

# 2. 流媒体平台
PLATFORM_RE = r"(?i)(?:-)?(?<![a-zA-Z0-9])(Baha|Bilibili|Netflix|NF|Amazon|AMZN|DSNP|Crunchyroll|CR|Hulu|HBO|YouTube|YT|playWEB|B-Global|friDay|LINETV|KKTV|ATVP|IQ|CRAMZN|iT|ABEMA)(?![a-zA-Z0-9])|(?:-)?(?<![a-zA-Z0-9])(Disney\+|AppleTV\+)"

# 2.5 字幕标签正则 (用于标题屏蔽)
# [Optimize] 增加对空格和碎屑的容错，确保能切除 [简日 字幕] 或 [CHS_CHT]
SUBTITLE_RE = r"(?i)(?<![\u4e00-\u9fa5])([简繁中日英双雙多]{1,}[体文语語\s]*[内內外\s]*[嵌封挂掛\s]*字幕?|[简繁中日英双雙多]{1,}[体文语語\s]*[双雙]语|[简繁中日英双雙多]{1,}\s*字幕|CHS|CHT|JPSC|JP_SC|BIG5|GB)(?![\u4e00-\u9fa5])"

# 3. 深度噪音
NOISE_WORDS = [
    r"(?i)PTS|JADE|AOD|CHC|(?!LINETV)[A-Z]{1,4}TV[-0-9UVHDK]*",
    r"(?i)[0-9]{1,2}th|[0-9]{1,2}bit|IMAX|BBC|XXX|DC$",
    r"(?i)Ma10p|Hi10p|Hi10|Ma10|10bit|8bit",
    r"连载|新番|合集|招募翻译|版本|出品|台版|港版|搬运|搬運|[a-zA-Z0-9]+字幕组|[a-zA-Z0-9]+字幕社|[★☆]*[0-9]{1,2}月新番[★☆]*",
    r"(?i)UNCUT|UNRATE|WITH EXTRAS|RERIP|SUBBED|PROPER|REPACK|Complete|Extended|Version|10bit",
    r"CD[ ]*[1-9]|DVD[ ]*[1-9]|DISK[ ]*[1-9]|DISC[ ]*[1-9]|[ ]+GB",
    # [Optimize] 只保留固定的发布组/翻译组碎屑噪声
    r"(?i)YYeTs|人人影视|弯弯字幕组",
    # [Optimize] 约束语言标签：必须包含 体/文/语/字 等明确后缀
    r"(?i)\b[简繁中日英双雙多]+[体文语語]+[ ]*(MP4|MKV|AVC|HEVC|AAC|ASS|SRT)*\b",
]

# 4. 发布组排除词
NOT_GROUPS = "1080P|720P|4K|2160P|H264|H265|X264|X265|AVC|HEVC|AAC|DTS|AC3|DDP|ATMOS|WEB-DL|WEBRIP|BLURAY|BD|HD|HDR|SDR|DV|TRUEHD|HIRES|10BIT|EAC3|UHD 4K|Ma10p|Hi10p|Hi10|Ma10|(?i)REMUX"

# 4.5 发布组语义特征词 (用于提高首部制作组识别的置信度)
GROUP_KEYWORDS = r"组|組|社|制作|製作|字幕|工作|家族|学园|學園|压制|壓制|发布|發佈|协会|協會|联盟|聯盟|论坛|論壇|中心|屋|团|團|亭|园|園"

# 5. 季集匹配
EPISODE_PATTERNS = [
    r"(?i)EP?([0-9]{2,4})", 
    r"(?i)DR([0-9]{2,4})",
    r"第[ ]*([0-9]{1,4})[ ]*[集话話期幕]", 
    r"[[]([0-9]{1,4})[]]",
    r"[ ]+-[ ]+([0-9]{1,4})"
]

SEASON_PATTERNS = [
    r"(?i)S([0-9]{1,2})",
    r"第([一二三四五六七八九十0-9]+)季",
    r"Season[ ]*([0-9]+)",
    r"(?i)\b([0-9]{1,2})(?:st|nd|rd|th)\b(?:\s*Season)?"
]

CN_MAP = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9, '十': 10}
