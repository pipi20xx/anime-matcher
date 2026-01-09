import regex as re
from typing import Optional, Tuple, List

class SpecialEpisodeHandler:
    """
    针对特定字幕组或特殊命名格式的集数提取处理器。
    这些规则优先级极高，一旦匹配成功将直接锁定集数。
    """
    
    # 规则配置列表: (正则表达式, 捕获组索引, 描述)
    # 建议使用原始字符串 r"" 以避免转义问题
    RULES = [
        # 1. LoliHouse 标准格式: [LoliHouse] ... - 01
        (r"^\[LoliHouse\].* - (\d+)", 1, "LoliHouse 定向提取"),
        
        # 2. LoliHouse 合作组格式: [NC-Raws & LoliHouse] ... - 01
        (r"^\[.*?LoliHouse.*?\].* - (\d+)", 1, "LoliHouse 合作组提取"),

        # 3. SweetSub 标准格式: [SweetSub] ... - 01
        (r"^\[SweetSub\].* - (\d+)", 1, "SweetSub 标准提取"),

        # 4. SweetSub 括号格式: [SweetSub][...][01][...]
        (r"^\[SweetSub\].*?\[(\d{1,3})\]", 1, "SweetSub 括号提取"),

        # 5. 晚街与灯 标准格式: [晚街与灯][Title][01_SubTitle] 或 [01 - 总第11]
        (r"\[晚街[與与]燈\].*?\[(\d{1,3})(?:\s*[-_][^\]]*)?\]", 1, "晚街与灯 定向提取"),
    ]

    @staticmethod
    def extract(filename: str) -> Tuple[Optional[int], Optional[str], List[str]]:
        """
        尝试使用特权规则提取集数
        :param filename: 原始文件名
        :return: (集数, 集数原文, 日志列表)
        """
        logs = []
        for pattern, group_idx, desc in SpecialEpisodeHandler.RULES:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                try:
                    val_str = match.group(group_idx)
                    val = int(val_str)
                    logs.append(f"[规则][特权] {desc}命中: {val_str} (来自 {match.group(0)[:30]}...)")
                    return val, val_str, logs
                except (ValueError, IndexError):
                    continue
        return None, None, []
