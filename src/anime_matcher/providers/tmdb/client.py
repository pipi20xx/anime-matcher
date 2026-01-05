import httpx
import asyncio
import re
import os
from typing import List, Optional, Dict, Any, Tuple
from ...tmdb_matcher.logic import TMDBMatcher

class TMDBProvider:
    """
    TMDB 独立数据提供者 (L2)
    已解耦：不依赖外部 ConfigManager 或 MetaCacheManager
    """
    BASE_URL = "https://api.themoviedb.org/3"

    def __init__(self, api_key: str = None, proxy: str = None):
        # 优先级：构造函数参数 > 环境变量
        self.api_key = api_key or os.environ.get("TMDB_API_KEY")
        _proxy = proxy or os.environ.get("TMDB_PROXY")
        
        # 增加安全性检查：只有合法的 http 代理才会被采信
        if _proxy and isinstance(_proxy, str) and _proxy.startswith("http"):
            self.proxy = _proxy
        else:
            self.proxy = None

    async def _fetch(self, endpoint: str, params: dict = {}, logs: Any = None) -> Optional[Dict]:
        if not self.api_key: return None
        
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        params["api_key"] = self.api_key
        params["language"] = params.get("language", "zh-CN")
        
        full_url = f"{self.BASE_URL}{endpoint}"
        log_params = {k: ("****" if k == "api_key" else v) for k, v in params.items()}
        query_str = "&".join([f"{k}={v}" for k, v in log_params.items()])
        _log(f"┃ [TMDB] ☁️ GET {full_url}?{query_str}")
        
        if self.proxy:
            _log(f"┃ [Proxy] 🛡️ 启用代理加速: {self.proxy}")

        async with httpx.AsyncClient(timeout=15, proxy=self.proxy) as client:
            try:
                resp = await client.get(full_url, params=params)
                if resp.status_code == 200: return resp.json()
                _log(f"┃   ❌ TMDB HTTP {resp.status_code}")
                return None
            except Exception as e: 
                _log(f"┃   ❌ TMDB Network Error: {e}")
                return None

    async def get_details(self, tmdb_id: str, media_type: str, logs: Any = None) -> Optional[Dict]:
        data = await self._fetch(f"/{media_type}/{tmdb_id}", {"append_to_response": "credits"}, logs=logs)
        if not data: return None
        
        cast_list = []
        for c in data.get("credits", {}).get("cast", [])[:15]:
            cast_list.append({
                "character": c.get("character"),
                "actor": c.get("name"),
                "image": c.get("profile_path")
            })
        
        norm = TMDBMatcher.normalize(data, media_type_hint=media_type)
        norm["genres"] = [g.get("name") for g in data.get("genres", [])]
        norm["tagline"] = data.get("tagline")
        norm["cast"] = cast_list
        return norm

    async def search(self, query: str, year: Optional[str], media_type: str, logs: Any = None, lang: str = "zh-CN") -> List[Dict]:
        params = {"query": query, "include_adult": "false", "language": lang}
        if year: params["year" if media_type == "movie" else "first_air_date_year"] = year
        data = await self._fetch(f"/search/{media_type}", params, logs=logs)
        results = (data or {}).get("results", [])
        if not results and year:
            params.pop("year" if media_type == "movie" else "first_air_date_year")
            data_retry = await self._fetch(f"/search/{media_type}", params, logs=logs)
            if data_retry: results = data_retry.get("results", [])
        return results

    async def smart_search(self, cn_name: Optional[str], en_name: Optional[str], year: Optional[str], media_type: str, logs: Any, anime_priority: bool = True) -> Optional[Dict]:
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        cn_queries = TMDBMatcher.prepare_queries(cn_name)
        en_queries = TMDBMatcher.prepare_queries(en_name)

        _log(f"┃ [TMDB-Smart] 🚀 启动定向搜索策略...")
        
        merged_candidates = []
        seen_ids = set()

        all_query_groups = []
        if cn_queries: all_query_groups.append({"queries": cn_queries, "lang": "zh-CN"})
        if en_queries: all_query_groups.append({"queries": en_queries, "lang": "en-US"})

        for group in all_query_groups:
            lang = group["lang"]
            for idx, q in enumerate(group["queries"]):
                if len(merged_candidates) > 0:
                    targets = self._build_match_targets(cn_name, en_name, cn_queries)
                    temp_scored = []
                    for c_idx, item in enumerate(merged_candidates[:5]):
                        score, _, _, _ = TMDBMatcher.calculate_match_score(item, targets, cn_name or "", en_name or "", c_idx, anime_priority)
                        temp_scored.append(score)
                    
                    if temp_scored and max(temp_scored) >= 95:
                        _log(f"┃   ℹ️ 已命中高置信度候选 ({max(temp_scored):.0f}分)，跳过后续查询")
                        break

                res_list = await self.search(q, year, media_type, logs=logs, lang=lang)
                
                # 全名唯一命中保护
                if idx == 0 and len(res_list) == 1:
                    _log(f"┃   🪄 全名搜索唯一命中，确认为高置信度目标")
                    for item in res_list:
                        if item.get("id") not in seen_ids:
                            seen_ids.add(item.get("id"))
                            merged_candidates.append(item)
                    return await self._process_candidates(merged_candidates, seen_ids, cn_name, en_name, cn_queries, media_type, logs, anime_priority)

                for item in res_list:
                    if item.get("id") not in seen_ids:
                        seen_ids.add(item.get("id"))
                        merged_candidates.append(item)

        return await self._process_candidates(merged_candidates, seen_ids, cn_name, en_name, cn_queries, media_type, logs, anime_priority)

    async def _process_candidates(self, merged_candidates, seen_ids, cn_name, en_name, cn_queries, media_type, logs, anime_priority):
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        if not merged_candidates:
            _log(f"┃ ❌ TMDB 定向搜索均无结果")
            return None
        
        _log(f"┃ [TMDB-Match] ⚖️ 正在对合并后的 {len(merged_candidates[:10])} 个候选进行交叉对撞...")
        
        targets = self._build_match_targets(cn_name, en_name, cn_queries)
        scored_pool = []
        for idx, item in enumerate(merged_candidates[:10]):
            score, trace, best_match_info, summary = TMDBMatcher.calculate_match_score(
                item, targets, cn_name or "", en_name or "", idx, anime_priority
            )
            c_name = item.get("title") or item.get("name")
            c_year = (item.get("release_date") or item.get("first_air_date") or "")[:4]
            
            _log(f"┣ [#{idx+1}] ID:{item.get('id')} | {c_name} ({c_year})")
            for t_line in trace: _log(t_line)
            _log(f"┃   ├─ 最佳匹配: {best_match_info}")
            _log(f"┃   └─ {summary}")
            
            scored_pool.append({"item": item, "score": score})
        
        scored_pool.sort(key=lambda x: x["score"], reverse=True)
        best = scored_pool[0]
        
        _log(f"┃")
        if best["score"] >= 85 or len(seen_ids) == 1:
             if len(seen_ids) == 1 and best["score"] < 85:
                 _log(f"┃ 🪄 触发[孤独命中]策略 (唯一 ID)")
             _log(f"┗ ✅ 最终采信: {best['item'].get('title') or best['item'].get('name')} (ID: {best['item']['id']})")
             details = await self.get_details(str(best["item"]["id"]), media_type, logs=logs)
             if details:
                 details["_score"] = best["score"]
                 return details
        
        _log(f"┗ ❌ 置信度不足 ({best['score']:.1f} < 85)")
        return None

    def _build_match_targets(self, cn_name, en_name, cn_queries):
        targets = []
        if cn_name: targets.append(re.sub(r"[^\w]", "", cn_name).upper())
        if en_name: targets.append(re.sub(r"[^\w]", "", en_name).upper())
        if cn_queries and len(cn_queries) > 1: targets.append(re.sub(r"[^\w]", "", cn_queries[1]).upper())
        return targets