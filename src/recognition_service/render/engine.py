"""
RenderEngine - 专家级规则渲染引擎
对齐主项目 recognition/render/engine.py，适配独立版（用 tmdb_provider 代替 MetaCacheManager）。
"""
import regex as re
import httpx
from typing import Dict, Any, List, Optional

class RenderEngine:
    """
    核心规则引擎：负责执行各种复杂的自定义渲染逻辑。
    支持：标题翻译、集数偏移、强制 ID 重定向、元数据精修、链式规则。
    """
    @staticmethod
    def evaluate_includes(expression: str, filename: str) -> bool:
        try:
            expr = expression.replace('||', '|')
            tokens = re.split(r'([&\|\(\)])', expr)
            processed_tokens = []
            for token in tokens:
                t = token.strip()
                if not t: continue
                if t in ['&', '|', '(', ')']:
                    if t == '&': processed_tokens.append(' and ')
                    elif t == '|': processed_tokens.append(' or ')
                    else: processed_tokens.append(t)
                else:
                    is_contained = t.lower() in filename.lower()
                    processed_tokens.append('True' if is_contained else 'False')
            eval_str = "".join(processed_tokens)
            return eval(eval_str, {"__builtins__": {}}, {})
        except:
            return expression.lower() in filename.lower()

    @staticmethod
    def _eval_math(expression: str, context: Dict[str, Any]) -> Any:
        try:
            expr = str(expression).upper()
            for key, val in context.items():
                if val is not None:
                    expr = expr.replace(str(key).upper(), str(val))
            if not re.match(r'^[\d\s\+\-\*\/\%\(\)\.]+$', expr):
                return expression
            return int(eval(expr, {"__builtins__": {}}, {}))
        except:
            return expression

    @staticmethod
    async def apply_rules(
        final_result: Dict[str, Any],
        local_result: Dict[str, Any],
        raw_filename: str,
        rules: List[str],
        logs: List[str],
        tmdb_provider: Any = None
    ) -> Dict[str, Any]:
        """
        执行渲染规则。直接修改传入的 Dict 对象。
        """
        if not rules: return final_result

        skip_count = 0
        def get_meta_context():
            return {
                "EP": local_result.get("episode", 0),
                "S": local_result.get("season", 1),
                "YEAR": local_result.get("year", ""),
            }

        async def fetch_tmdb_update(new_id, new_type):
            if not tmdb_provider: return
            details = await tmdb_provider.get_details(str(new_id), new_type, logs=logs)
            if details:
                final_result["tmdb_id"] = str(details.get("id"))
                final_result["title"] = details.get("title") or details.get("name")
                final_result["year"] = str(details.get("year") or "")
                final_result["poster_path"] = details.get("poster_path")
                final_result["release_date"] = details.get("release_date")
                logs.append(f"┃  => [Mod] TMDB 强制重定向: {final_result['title']} (ID:{new_id})")

        for idx, rule in enumerate(rules):
            rule = rule.strip()
            if not rule or rule.startswith("#"): continue

            is_remote = rule.startswith("[REMOTE]")
            source_tag = "[社区]" if is_remote else "[私有]"
            actual_line = rule[8:] if is_remote else rule

            try:
                # 1. 偏移定位器 (A <> B >> Expr)
                if " <> " in actual_line and " >> " in actual_line:
                    parts = actual_line.split(" >> ", 1)
                    formula, locators = parts[1].strip(), parts[0].split(" <> ")
                    if len(locators) == 2:
                        p = f"(?i){re.escape(locators[0].strip())}\s*(\d+)\s*{re.escape(locators[1].strip())}"
                        match = re.search(p, raw_filename)
                        if match:
                            captured_num = int(match.group(1))
                            new_ep = RenderEngine._eval_math(formula, {"EP": captured_num})
                            if isinstance(new_ep, int):
                                local_result["episode"] = new_ep
                                final_result["episode"] = str(new_ep)
                                logs.append(f"┣ 🏷️  [Render]{source_tag} 偏移定位: {match.group(0)} -> E{new_ep}")
                        else: skip_count += 1
                    continue

                # 2. 专家条件规则 (@?{...})
                if actual_line.startswith("@?{"):
                    if " => " not in actual_line: continue
                    parts = actual_line.split(" => ", 1)
                    src_match = re.search(r"\{\[(.*?)\]\}", parts[0])
                    tgt_match = re.search(r"\{\[(.*?)\]\}", parts[1])
                    if not src_match or not tgt_match:
                        skip_count += 1; continue

                    src_conds, tgt_mods = src_match.group(1), tgt_match.group(1)
                    cond_dict = {item.split("=")[0].strip().lower(): item.split("=")[1].strip() for item in src_conds.split(";") if "=" in item}

                    tmdb_id = final_result.get("tmdb_id", "")
                    curr_s, curr_e = int(local_result.get("season") or 1), int(local_result.get("episode") or 0)
                    m_type = local_result.get("type", "tv")
                    curr_year = str(local_result.get("year") or "")

                    match_fail = None
                    if "tmdbid" in cond_dict and cond_dict["tmdbid"] != tmdb_id: match_fail = "ID不符"
                    elif "type" in cond_dict and cond_dict["type"] != m_type: match_fail = "类型不符"
                    elif "year" in cond_dict and cond_dict["year"] != curr_year: match_fail = "年份不符"
                    elif "s" in cond_dict and str(curr_s) != cond_dict["s"]: match_fail = "季号不符"
                    elif "e" in cond_dict:
                        if "-" in cond_dict["e"]:
                            try:
                                s_range, e_range = map(int, cond_dict["e"].split("-"))
                                if not (s_range <= curr_e <= e_range): match_fail = "集数不在范围"
                            except: match_fail = "格式错误"
                        elif str(curr_e) != cond_dict["e"]: match_fail = "集数不符"
                    elif "includes" in cond_dict:
                        if not RenderEngine.evaluate_includes(cond_dict["includes"], raw_filename): match_fail = "包含词不匹配"

                    if match_fail:
                        skip_count += 1; continue

                    logs.append(f"┣ 🎯 [Render]{source_tag} 命中专家规则: {actual_line}")
                    mod_dict = {item.split("=")[0].strip().lower(): item.split("=")[1].strip() for item in tgt_mods.split(";") if "=" in item}
                    if "tmdbid" in mod_dict:
                        await fetch_tmdb_update(mod_dict["tmdbid"], mod_dict.get("type", m_type))
                    if "year" in mod_dict:
                        local_result["year"] = mod_dict["year"]; final_result["year"] = mod_dict["year"]
                    if "s" in mod_dict:
                        local_result["season"] = int(mod_dict["s"]); final_result["season"] = int(mod_dict["s"])
                    if "e" in mod_dict:
                        e_formula, old_e = mod_dict["e"], local_result.get("episode")
                        new_e = RenderEngine._eval_math(e_formula, get_meta_context())
                        if isinstance(new_e, int):
                            local_result["episode"] = new_e
                            final_result["episode"] = str(new_e)
                            log_msg = f"┃  => [Mod] 集数: E{old_e} -> E{new_e}"
                            # 合集区间处理
                            if local_result.get("is_batch") and local_result.get("end_episode"):
                                old_end = local_result.get("end_episode")
                                new_end = RenderEngine._eval_math(e_formula, {"EP": old_end, "S": get_meta_context()["S"], "YEAR": get_meta_context()["YEAR"]})
                                if isinstance(new_end, int):
                                    local_result["end_episode"] = new_end
                                    final_result["episode"] = f"{new_e}-{new_end}"
                                    log_msg = f"┃  => [Mod] 集数区间: E{old_e}-E{old_end} -> E{new_e}-E{new_end}"
                            logs.append(log_msg)
                    continue

                # 3. 正则替换/提取/链式 (A => B)
                if " => " in actual_line:
                    pattern_str, replacement = actual_line.split(" => ", 1)
                    pattern_str, replacement = pattern_str.strip(), replacement.strip()
                    chain_rules = None
                    if replacement.startswith("&&"):
                        chain_rules, replacement = replacement[2:].strip(), ""

                    # 提取模式 {[key=value]}
                    if replacement.startswith("{[") and replacement.endswith("]}"):
                        match = re.search(pattern_str, raw_filename, flags=re.I)
                        if match:
                            logs.append(f"┣ 🏷️  [Render]{source_tag} 命中提取: {pattern_str}")
                            try: expanded_content = match.expand(replacement[2:-2])
                            except: expanded_content = replacement[2:-2]
                            mods = {item.split("=")[0].strip().lower(): item.split("=")[1].strip() for item in expanded_content.split(";") if "=" in item}
                            for k, v in mods.items():
                                if k == "e":
                                    val_to_set = RenderEngine._eval_math(v, get_meta_context())
                                    if isinstance(val_to_set, int):
                                        local_result["episode"] = val_to_set
                                        final_result["episode"] = str(val_to_set)
                                        logs.append(f"┃  => [Set] 集数: {val_to_set}")
                                elif k == "s":
                                    local_result["season"] = int(v)
                                    final_result["season"] = int(v)
                                    logs.append(f"┃  => [Set] 季数: {v}")
                                elif k == "tmdbid":
                                    await fetch_tmdb_update(v, "tv")
                        else: skip_count += 1
                        continue

                    # 正则翻译
                    if re.search(pattern_str, raw_filename, flags=re.I):
                        logs.append(f"┣ 🏷️  [Render]{source_tag} 命中翻译: {pattern_str} -> {replacement}")
                        for target in [local_result, final_result]:
                            for field in ["cn_name", "en_name", "title", "processed_name"]:
                                if target.get(field):
                                    target[field] = re.sub(pattern_str, replacement, target[field], flags=re.I)
                        # 非空替换结果自动添加为标签
                        if replacement and not chain_rules:
                            if "tags" not in local_result: local_result["tags"] = []
                            if replacement not in local_result["tags"]:
                                local_result["tags"].append(replacement)
                        # 链式规则
                        if chain_rules:
                            await RenderEngine.apply_rules(final_result, local_result, raw_filename, [chain_rules], logs, tmdb_provider)
                    else: skip_count += 1
            except Exception as e:
                logs.append(f"┣ ❌ [Error]{source_tag} 规则 #{idx+1} 异常: {str(e)}")

        if skip_count > 0: logs.append(f"┣ ⏩ 跳过 {skip_count} 条不匹配的自定义渲染词")
        return final_result
