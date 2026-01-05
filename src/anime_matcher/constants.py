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

# 2. 流媒体平台 (Streaming Platforms) - 新增
# 包含用户指定的: Disney+, playWEB, Baha, B-Global, CrunchRoll, friDay, LINETV, KKTV, ATVP, DSNP, NF, IQ, CRAMZN, Netflix, Amazon, AppleTV+, iT
# 修改: 允许可选的连字符前缀 (?:-)? 以兼容用户自定义的 "-Baha" 格式
PLATFORM_RE = r"(?i)(?:-)?(?<![a-zA-Z0-9])(Baha|Bilibili|Netflix|NF|Amazon|AMZN|DSNP|Crunchyroll|CR|Hulu|HBO|YouTube|YT|playWEB|B-Global|friDay|LINETV|KKTV|ATVP|IQ|CRAMZN|iT)(?![a-zA-Z0-9])|(?:-)?(?<![a-zA-Z0-9])(Disney\+|AppleTV\+)"

# 3. 深度噪音
NOISE_WORDS = [
    r"(?i)PTS|JADE|AOD|CHC|[A-Z]{1,4}TV[-0-9UVHDK]*",
    r"(?i)[0-9]{1,2}th|[0-9]{1,2}bit|IMAX|BBC|XXX|DC$",
    r"(?i)Ma10p|Hi10p|Hi10|Ma10|10bit|8bit",
    r"连载|新番|合集|招募翻译|版本|出品|台版|港版|[a-zA-Z0-9]+字幕组|[a-zA-Z0-9]+字幕社|[★☆]*[0-9]{1,2}月新番[★☆]*",
    r"(?i)UNCUT|UNRATE|WITH EXTRAS|RERIP|SUBBED|PROPER|REPACK|Complete|Extended|Version|10bit",
    r"CD[ ]*[1-9]|DVD[ ]*[1-9]|DISK[ ]*[1-9]|DISC[ ]*[1-9]|[ ]+GB",
    r"[多中英葡法俄日韩德意西印泰台港粤双文语简繁体特效内封官译外挂]+字幕",
    r"(?i)YYeTs|人人影视|弯弯字幕组|Big5|GB|Dual-Audio|简体|繁体|双语|简中|繁中|日文|英文|内嵌|内封|特效|无修|外挂|简日|繁日|简繁|中日|中英|搬運",
    r"(?i)(?<![a-zA-Z0-9])(CHS|CHT|JAP|ENG|SUB)(?![a-zA-Z0-9])",
    r"(?i)(?<![a-zA-Z0-9])(PGS|ASS|SSA|SRT|VobSub)(?![a-zA-Z0-9])",
    r"(?i)(?<![a-zA-Z0-9])(CHS|CHT|JP|JPN|BIG5|GB|ENG|SC|TC)(_|-|&)*(CHS|CHT|JP|JPN|BIG5|GB|ENG|SC|TC)*(?![a-zA-Z0-9])",
    r"(?i)[简繁中日英双雙多]+[体文语語]*[ ]*(MP4|MKV|AVC|HEVC|AAC|ASS|SRT)*",
]

# 4. 发布组排除词
NOT_GROUPS = "1080P|720P|4K|2160P|H264|H265|X264|X265|AVC|HEVC|AAC|DTS|AC3|DDP|ATMOS|WEB-DL|WEBRIP|BLURAY|BD|HD|HDR|SDR|DV|TRUEHD|HIRES|10BIT|EAC3|UHD 4K|Ma10p|Hi10p|Hi10|Ma10|(?i)REMUX"

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
