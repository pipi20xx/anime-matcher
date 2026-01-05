import httpx
import asyncio
import datetime
import os
from typing import List, Optional, Dict, Any, Tuple
from ...bgm_matcher.logic import BangumiMatcher
from ...tmdb_matcher.logic import TMDBMatcher
from ..tmdb.client import TMDBProvider as TMDBClient

class BangumiProvider:
    """
    Bangumi 独立数据提供者 (L2)
    已解耦：不依赖外部 ConfigManager 或 MetaCacheManager
    """
    BASE_URL = "https://api.bgm.tv"

    def __init__(self, token: str = None, proxy: str = None):
        self.token = token or os.environ.get("BANGUMI_TOKEN")
        self.proxy = proxy or os.environ.get("BANGUMI_PROXY")

    def _get_headers(self):
        h = {"User-Agent": "ANIME-Pro-Matcher/2.0"}
        if self.token: h["Authorization"] = f"Bearer {self.token}"
        return h

    async def _fetch(self, method: str, url: str, logs: Any = None, params: dict = None, json: dict = None) -> Optional[Any]:
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        # 日志参数拼接
        query_str = f"?{'&'.join([f'{k}={v}' for k, v in params.items()])}" if params else ""
        payload_str = f" | Body: {json}" if json else ""
        _log(f"┃ [BGM] ☁️ {method} {url}{query_str}{payload_str}")
        
        if self.proxy:
            _log(f"┃ [Proxy] 🛡️ 启用代理加速: {self.proxy}")

        async with httpx.AsyncClient(timeout=15, proxy=self.proxy) as client:
            try:
                if method == "GET":
                    resp = await client.get(url, headers=self._get_headers(), params=params)
                else:
                    resp = await client.post(url, headers=self._get_headers(), json=json)
                
                if resp.status_code == 200: return resp.json()
                _log(f"┃   ❌ BGM HTTP {resp.status_code}")
            except Exception as e:
                _log(f"┃   ❌ BGM Network Error: {e}")
        return None

    async def get_subject_details(self, subject_id: int, logs: Any = None, include_cast: bool = False) -> Optional[Dict]:
        data = await self._fetch("GET", f"{self.BASE_URL}/v0/subjects/{subject_id}", logs=logs)
        if not data: return None
        
        cast = []
        if include_cast:
            characters = await self._fetch("GET", f"{self.BASE_URL}/v0/subjects/{subject_id}/characters", logs=logs) or []
            for char in characters[:12]:
                actors = char.get("actors", [])
                cast.append({
                    "character": char.get("name"),
                    "actor": actors[0].get("name") if actors else "未知",
                    "image": char.get("images", {}).get("grid") or ""
                })

        meta_tags = []
        platform = data.get("platform")
        if platform: meta_tags.append(platform)
        infobox = data.get("infobox", [])
        for info in infobox:
            if info.get("key") in ["地区", "产地", "放送星期"]:
                val = info.get("value")
                if isinstance(val, str): meta_tags.append(val)
                elif isinstance(val, list): meta_tags.extend([v.get("v") for v in val if v.get("v")])

        user_tags = [t.get("name") for t in data.get("tags", [])]
        images = data.get("images", {})
        poster = images.get("large") or images.get("common") or ""
        
        return {
            "id": data.get("id"),
            "title": data.get("name_cn") or data.get("name"),
            "original_title": data.get("name"),
            "overview": data.get("summary"),
            "poster_path": poster,
            "backdrop_path": poster,
            "vote_average": data.get("rating", {}).get("score", 0),
            "release_date": data.get("date"),
            "total_episodes": data.get("total_episodes") or 0,
            "genres": meta_tags,
            "tags": user_tags,
            "cast": cast,
            "source": "bangumi",
            "platform": platform
        }

    async def search_subject(self, keyword: str, logs: Any, current_episode: Optional[int] = None, expected_type: str = "tv") -> Optional[dict]:
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        if not keyword: return None
        _log(f"┃ [BGM-Search] 🔍 正在检索 Bangumi 库: '{keyword}'")
        
        data = await self._fetch("POST", f"{self.BASE_URL}/v0/search/subjects", logs=logs, json={"keyword": keyword, "filter": {"type": [2]}})
        if not data: return None
        
        candidates = data.get("data", [])
        if not candidates: 
            _log(f"┃   ❌ 未发现匹配条目")
            return None

        _log(f"┃ [BGM-Filter] ⚖️ 正在核验 {len(candidates[:3])} 个潜在候选人...")
        best_candidate = None
        
        for idx, cand in enumerate(candidates[:3]):
            detail = await self.get_subject_details(cand['id'], logs)
            if not detail: continue

            platform = detail.get('platform', '')
            total_eps = detail.get('total_episodes', 0)
            c_name = detail['title']
            rank = idx + 1
            
            _log(f"┣ [Rank #{rank}] {c_name} (ID:{cand['id']})")
            _log(f"┃   ├─ 类型: {platform} | 总集数: {total_eps}")
            
            is_movie_type = platform in ["剧场版", "电影版", "Movie"]
            if expected_type == "tv" and (current_episode or 0) > 1:
                if is_movie_type or total_eps == 1:
                    _log(f"┃   └─ ❌ [排除] 模式冲突: 识别模式为 TV，但该条目为单集电影/OVA")
                    continue
            
            if total_eps > 0 and current_episode and current_episode > (total_eps + 5):
                if idx == 0 or len(candidates) == 1:
                    _log(f"┃   └─ ⚠️ [警告] 集数存疑: 提取到 E{current_episode} 但条目仅 {total_eps} 集，作为首选仍尝试采信")
                else: 
                    _log(f"┃   └─ ❌ [排除] 集数超限: 文件集数(E{current_episode}) 远超条目总量({total_eps})")
                    continue

            if not best_candidate:
                _log(f"┃   └─ ✅ [胜出] 该条目相关度最高且通过规格核验")
                best_candidate = detail
            else:
                _log(f"┃   └─ ⏩ [略过] 已有相关度更高的优选条目")

        if best_candidate:
            _log(f"┗ 🎯 最终锁定 Bangumi 目标: {best_candidate['title']}")
            return best_candidate
        
        _log(f"┗ ❌ 遗憾：本次搜索发现的候选人均未通过规格核验")
        return None

    async def map_to_tmdb(self, bgm_item: Dict, tmdb_api_key: str, logs: Any, tmdb_proxy: str = None) -> Optional[Dict]:
        def _log(msg):
            if hasattr(logs, "log"): logs.log(msg)
            elif isinstance(logs, list): logs.append(msg)

        bgm_platform = bgm_item.get('platform', '')
        name_cn = bgm_item.get('title', '')
        
        primary_strategy = 'tv' 
        if bgm_platform in ['Movie', '剧场版'] or '剧场版' in name_cn:
            primary_strategy = 'movie'

        _log(f"┃ [BGM-Link] 🔗 正在尝试将 Bangumi 条目映射至 TMDB ({primary_strategy} 模式)")
        strategies = BangumiMatcher.generate_search_strategies(bgm_item)
        search_phases = [('tv', 'tv'), ('movie', 'movie')] if primary_strategy == 'tv' else [('movie', 'movie'), ('tv', 'tv')]

        scored_pool = []
        seen_ids = set()
        tmdb = TMDBClient(tmdb_api_key, proxy=tmdb_proxy)

        for endpoint, scoring_strategy in search_phases:
            if any(x["score"] >= 85 for x in scored_pool): break
            
            for query, year, lang_hint in strategies:
                tmdb_lang = "ja-JP" if lang_hint == "ja" else "zh-CN"
                q_label = "日文原名" if lang_hint == "ja" else "中文标题"
                
                results = await tmdb.search(query, year, endpoint, logs=logs, lang=tmdb_lang)
                _log(f"┃   ├─ 🔍 [{q_label}] '{query}' -> 发现 {len(results)} 个候选人")
                
                for cand in results:
                    m_id = cand.get('id')
                    if m_id in seen_ids: continue
                    seen_ids.add(m_id)
                    
                    cand['media_type'] = endpoint
                    score, trace, reason = BangumiMatcher.score_candidate(cand, bgm_item, query, scoring_strategy, query_label=q_label)
                    scored_pool.append({"item": cand, "score": score, "query": query, "reason": reason, "trace": trace, "win_lang": q_label})
        
        if not scored_pool:
            _log(f"┃ ❌ TMDB 所有搜索维度均未发现任何候选结果")
            return None

        scored_pool.sort(key=lambda x: x["score"], reverse=True)
        for idx, entry in enumerate(scored_pool[:5]):
            item = entry["item"]
            c_name = item.get('title') or item.get('name')
            c_year = (item.get('release_date') or item.get('first_air_date') or '')[:4]
            _log(f"┣ [TMDB#{idx+1}] ID:{item['id']} | {c_name} ({c_year})")
            for t_line in entry["trace"]: _log(t_line)
            _log(f"┃   ├─ 最终分: {entry['score']:.1f} | 依据: {entry['win_lang']}")
            _log(f"┃   └─ 构成: {entry['reason']}")

        best = scored_pool[0]
        threshold = 70
        if best["score"] >= threshold:
            _log(f"┗ ✅ 建立映射: [BGM ID:{bgm_item['id']}] -> [TMDB ID:{best['item']['id']}] ({best['item'].get('title') or best['item'].get('name')})")
            details = await tmdb.get_details(str(best["item"]["id"]), best["item"]['media_type'], logs=logs)
            return details or TMDBMatcher.normalize(best["item"], media_type_hint=best["item"]['media_type'])
        
        _log(f"┃ ⚠️ BGM 映射最高分不足 ({best['score']:.1f} < {threshold})，执行回退策略...")
        return None
