from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .kernel import core_recognize
from .data_models import MediaType
from .providers.tmdb.client import TMDBProvider
from .providers.bangumi.client import BangumiProvider
from .render_engine import RenderEngine
from .storage_manager import storage
from .special_episode_handler import SpecialEpisodeHandler
import uvicorn
import os
import time

app = FastAPI(title="ANIMEProMatcher Kernel Service")

def _is_chinese(text: str) -> bool:
    if not text:
        return False
    for char in text:
        if '\u4e00' <= char <= '\u9fff':
            return True
    return False

def _split_title(title: str) -> list:
    if not title or '/' not in title:
        return [title] if title else []
    
    parts = [p.strip() for p in title.split('/') if p.strip()]
    if len(parts) < 2:
        return parts
    
    cn_titles = [p for p in parts if _is_chinese(p)]
    en_titles = [p for p in parts if not _is_chinese(p)]
    
    result = []
    if cn_titles:
        result.append(cn_titles[0])
    if en_titles:
        result.append(en_titles[0])
    
    return result if result else parts

def _clean_privileged_title(title: str) -> str:
    if not title:
        return title
    
    import re
    
    cleaned = re.sub(r'\.', ' ', title)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    cleaned = cleaned.strip()
    
    return cleaned

class RecognitionRequest(BaseModel):
    filename: str = Field(..., description="待识别的文件名", json_schema_extra={"example": "[ANi] 花樣少年少女 - 02.mkv"})
    custom_words: List[str] = Field(default=[], description="L1 预处理规则")
    custom_groups: List[str] = Field(default=[], description="自定义制作组")
    custom_render: List[str] = Field(default=[], description="L3 专家渲染规则 (翻译/偏移/重定向)")
    special_rules: List[str] = Field(default=[], description="特权提取规则 (正则|||字幕组索引|||标题索引|||集数索引|||描述)")
    force_filename: bool = Field(default=False, description="强制单文件模式")
    batch_enhancement: bool = Field(default=False, description="合集增强模式")
    
    # 方案 B: 扩展参数
    with_cloud: bool = Field(default=False, description="是否开启云端联网元数据匹配")
    use_storage: bool = Field(default=False, description="是否启用本地持久化存储(如果全局开关开启)")
    anime_priority: bool = Field(default=True, description="动画优先级加权")
    bangumi_priority: bool = Field(default=False, description="是否优先从 Bangumi 检索")
    bangumi_failover: bool = Field(default=True, description="是否在 TMDB 失败时启用 Bangumi 故障转移")
    tmdb_api_key: Optional[str] = Field(default=None, description="TMDB API Key")
    tmdb_proxy: Optional[str] = Field(default=None, description="TMDB 代理地址")
    tmdb_id: Optional[str] = Field(default=None, description="【已知 ID 提示】如果后端已命中心指纹，可直接传入 ID 以触发专家规则")
    tmdb_type: Optional[str] = Field(default=None, description="【已知类型提示】movie 或 tv，配合 tmdb_id 使用")
    bangumi_token: Optional[str] = Field(default=None, description="Bangumi 令牌")
    bangumi_proxy: Optional[str] = Field(default=None, description="Bangumi 代理地址")

class LocalResult(BaseModel):
    """核心解析产生的原始数据 (L1)"""
    cn_name: Optional[str] = None
    en_name: Optional[str] = None
    team: Optional[str] = None
    season: int = 1
    episode: int = 1
    is_batch: bool = False
    end_episode: Optional[int] = None
    type: str = "tv"
    resolution: Optional[str] = None
    platform: Optional[str] = None
    source: Optional[str] = None
    video_encode: Optional[str] = None
    audio_encode: Optional[str] = None
    subtitle: Optional[str] = None
    year: Optional[str] = None

class FinalResult(BaseModel):
    """对标原项目最终返回结构"""
    audio_encode: Optional[str] = None
    category: str = "未知"
    duration: str = "0s"
    episode: str = ""
    filename: str = ""
    origin_country: str = ""
    path: str = ""
    platform: Optional[str] = None
    poster_path: Optional[str] = None
    processed_name: str = ""
    release_date: Optional[str] = None
    resolution: Optional[str] = None
    season: int = 1
    secondary_category: Optional[str] = None
    source: Optional[str] = None
    subtitle: Optional[str] = None
    team: Optional[str] = None
    title: str = ""
    tmdb_id: str = ""
    video_effect: Optional[str] = None
    video_encode: Optional[str] = None
    vote_average: Optional[float] = None
    year: str = ""

class RecognitionResponse(BaseModel):
    _filename: str
    _task_id: int = 0
    local_result: LocalResult
    final_result: FinalResult
    cloud_result: Optional[Dict[str, Any]] = None
    summary: str
    logs: List[str]

@app.post("/recognize", response_model=RecognitionResponse, summary="核心识别接口")
async def recognize(req: RecognitionRequest):
    start_time = time.time()
    logs = []

    # --- 参数清洗 (防止 Swagger 默认值 "string" 干扰) ---
    def clean_param(v):
        if v == "string" or not v: return None
        return v
    
    req.tmdb_api_key = clean_param(req.tmdb_api_key)
    req.tmdb_proxy = clean_param(req.tmdb_proxy)
    req.bangumi_token = clean_param(req.bangumi_token)
    req.bangumi_proxy = clean_param(req.bangumi_proxy)
    req.tmdb_id = clean_param(req.tmdb_id)
    req.tmdb_type = clean_param(req.tmdb_type)
    
    # 存储控制位
    active_storage = req.use_storage

    # --- [STAGE 0] 任务控制台 (配置审计) ---
    logs.append(f"🚀 --- [ANIME 深度审计流启动] ---")
    
    def on_off(b): return "ON" if b else "OFF"
    
    logs.append(f"┃ [配置] 模式状态: 强制单文件[{on_off(req.force_filename)}] | 合集增强[{on_off(req.batch_enhancement)}] | 云端联动[{on_off(req.with_cloud)}] | 智能记忆[{on_off(req.use_storage)}]")
    logs.append(f"┃ [配置] 策略权重: 动漫优先[{on_off(req.anime_priority)}] | Bangumi 优先[{on_off(req.bangumi_priority)}] | TMDB 故障转移[{on_off(req.bangumi_failover)}]")
    
    # 规则数量统计
    logs.append(f"┃ [配置] 规则载入: 屏蔽词({len(req.custom_words)}) | 制作组({len(req.custom_groups)}) | 专家渲染({len(req.custom_render)})")
    
    # 云端参数摘要 (脱敏处理)
    if req.with_cloud:
        tmdb_key_mask = f"{req.tmdb_api_key[:4]}***{req.tmdb_api_key[-4:]}" if req.tmdb_api_key and len(req.tmdb_api_key) > 8 else ("Env-Key" if os.environ.get("TMDB_API_KEY") else "Missing")
        logs.append(f"┃ [配置] 云端凭据: TMDB密钥[{tmdb_key_mask}]")
        if req.tmdb_proxy: logs.append(f"┃ [配置] 网络代理: {req.tmdb_proxy}")
    
    if req.tmdb_id:
        type_hint = f" ({req.tmdb_type})" if req.tmdb_type else ""
        logs.append(f"┃ [配置] 锚点提示: 已知锁定 ID = {req.tmdb_id}{type_hint}")

    active_storage = req.use_storage

    try:
        # --- [STAGE 0.5] 加载特权提取规则 ---
        if req.special_rules:
            SpecialEpisodeHandler.load_external_rules(req.special_rules)
            logs.append(f"┃ [配置] 特权规则载入: {len(req.special_rules)} 条")
        
        # --- [STAGE 1] 本地解析 (L1 Kernel) ---
        meta = core_recognize(
            input_name=req.filename,
            custom_words=req.custom_words,
            custom_groups=req.custom_groups,
            original_input=req.filename,
            current_logs=logs,
            batch_enhancement=req.batch_enhancement,
            force_filename=req.force_filename
        )
        
        # 封装 L1 原始结果
        l1_dict = {
            "cn_name": meta.cn_name, "en_name": meta.en_name, "team": meta.resource_team,
            "season": meta.begin_season or 1, "episode": meta.begin_episode if isinstance(meta.begin_episode, int) else 1,
            "is_batch": meta.is_batch, "end_episode": meta.end_episode if isinstance(meta.end_episode, int) else None,
            "type": req.tmdb_type if req.tmdb_type else (meta.type.value if hasattr(meta.type, "value") else str(meta.type)),
            "resolution": meta.resource_pix, "platform": meta.resource_platform, "source": meta.resource_type,
            "video_encode": meta.video_encode, "audio_encode": meta.audio_encode,
            "subtitle": meta.subtitle_lang, "year": meta.year
        }

        # --- [STAGE 1.5] 查阅持久化记忆 ---
        current_tmdb_id = req.tmdb_id
        
        # 优先级：请求参数强制 ID > L1 识别结果中的强制 ID > 本地存储记忆
        if not current_tmdb_id and meta.forced_tmdbid:
            current_tmdb_id = meta.forced_tmdbid
            logs.append(f"┃ [STAGE 1.5] 🚀 发现规则锁定 ID: {current_tmdb_id}")

        if active_storage and not current_tmdb_id:
            pattern_key = f"{l1_dict['cn_name'] or l1_dict['en_name']}|{l1_dict['year']}"
            memory = storage.get_memory(pattern_key)
            if memory:
                current_tmdb_id = memory['tmdb_id']
                l1_dict['type'] = memory['media_type']
                logs.append(f"┃ [STORAGE] ⚡ 命中心特征记忆: 自动锁定 ID {current_tmdb_id}")

        # --- [STAGE 2] 云端对撞 (L2 Cloud) ---
        cloud_data = None
        tmdb_client = TMDBProvider(api_key=req.tmdb_api_key, proxy=req.tmdb_proxy)
        if req.with_cloud:
            logs.append("┃")
            logs.append("┃ [DEBUG][STEP 8: 云端元数据联动]: 启动搜索对撞")
            
            # 先尝试查缓存
            cache_key = current_tmdb_id if current_tmdb_id else (l1_dict["cn_name"] or l1_dict["en_name"])
            if active_storage:
                cloud_data = storage.get_metadata(cache_key, "tmdb")
                if cloud_data:
                    logs.append(f"┃ [STORAGE] ⚡ 命中元数据缓存: {cloud_data.get('title') or cloud_data.get('name')}")

            if not cloud_data:
                bgm_client = BangumiProvider(token=req.bangumi_token, proxy=req.bangumi_proxy)
                m_type_str = l1_dict["type"]
                
                if current_tmdb_id:
                    cloud_data = await tmdb_client.get_details(current_tmdb_id, m_type_str, logs)
                else:
                    privileged_title = getattr(meta, 'privileged_title', None)
                    privileged_titles = _split_title(privileged_title) if privileged_title else []
                    
                    if privileged_titles:
                        logs.append(f"┃ [匹配] 🎯 使用特权标题优先搜索: {' | '.join(privileged_titles)}")
                    
                    if req.bangumi_priority:
                        search_order = ["bangumi", "tmdb"]
                    else:
                        search_order = ["tmdb", "bangumi"] if req.bangumi_failover else ["tmdb"]
                    
                    is_auto_type = m_type_str == "auto"
                    if is_auto_type:
                        logs.append(f"┃ [匹配] 🔍 类型为 AUTO，将同时搜索 TV 和 Movie")
                    
                    async def search_cloud(use_privileged: bool = False, title_index: int = 0, clean_privileged: bool = False):
                        nonlocal cloud_data
                        if cloud_data: return
                        
                        if use_privileged and privileged_titles:
                            title = privileged_titles[title_index] if title_index < len(privileged_titles) else privileged_titles[0]
                            if clean_privileged:
                                title = _clean_privileged_title(title)
                                logs.append(f"┃ [匹配] 🧹 使用清洗后的特权标题: {title}")
                            cn = title if _is_chinese(title) else None
                            en = title if not _is_chinese(title) else None
                            original_cn = None
                        else:
                            cn = l1_dict["cn_name"]
                            en = l1_dict["en_name"]
                            original_cn = meta.original_cn_name
                        
                        for source in search_order:
                            if cloud_data: break
                            if source == "tmdb":
                                if is_auto_type:
                                    cloud_data = await tmdb_client.smart_search_multi(
                                        cn, en, l1_dict["year"], logs, 
                                        anime_priority=req.anime_priority,
                                        original_cn_name=original_cn
                                    )
                                else:
                                    cloud_data = await tmdb_client.smart_search(
                                        cn, en, l1_dict["year"], m_type_str, logs, 
                                        anime_priority=req.anime_priority,
                                        original_cn_name=original_cn
                                    )
                            elif source == "bangumi":
                                queries = [q for q in [en, cn] if q]
                                if not queries and meta.processed_name:
                                    queries = [meta.processed_name]
                                
                                for q in queries:
                                    if cloud_data: break
                                    bgm_subject = await bgm_client.search_subject(q, logs, current_episode=l1_dict["episode"], expected_type=m_type_str if not is_auto_type else None)
                                    if bgm_subject:
                                        logs.append(f"┃ [匹配] 🪄 Bangumi 命中，尝试映射...")
                                        cloud_data = await bgm_client.map_to_tmdb(bgm_subject, tmdb_api_key=req.tmdb_api_key or os.environ.get("TMDB_API_KEY", ""), logs=logs, tmdb_proxy=req.tmdb_proxy)
                                        if not cloud_data: 
                                            logs.append(f"┃ [匹配] ⚠️ Bangumi 映射 TMDB 失败，回退到原始元数据")
                                            cloud_data = bgm_subject
                    
                    for i in range(len(privileged_titles)):
                        if cloud_data: break
                        await search_cloud(use_privileged=True, title_index=i)
                    for i in range(len(privileged_titles)):
                        if cloud_data: break
                        await search_cloud(use_privileged=True, title_index=i, clean_privileged=True)
                    if not cloud_data:
                        if privileged_titles:
                            logs.append(f"┃ [匹配] 🔄 特权标题搜索失败，使用清洗后的标题继续搜索: {l1_dict['cn_name'] or l1_dict['en_name']}")
                        await search_cloud(use_privileged=False)
                
                # 存入缓存
                if active_storage and cloud_data:
                    storage.set_metadata(str(cloud_data.get('id')), "tmdb", cloud_data)
                    # 存入记忆
                    pattern_key = f"{l1_dict['cn_name'] or l1_dict['en_name']}|{l1_dict['year']}"
                    storage.set_memory(pattern_key, str(cloud_data.get('id')), l1_dict['type'], l1_dict['season'])

            if cloud_data:
                logs.append(f"┗ ✅ 识别成功: {cloud_data.get('title') or cloud_data.get('name')} (ID: {cloud_data.get('id')})")
            else:
                logs.append(f"┗ ❌ 云端检索未发现高置信度匹配")

        # --- [STAGE 3] 最终报告初步构建 ---
        m_type_zh = "电影" if l1_dict["type"] == "movie" else "剧集"
        final_dict = {
            "audio_encode": l1_dict["audio_encode"], "category": m_type_zh, "episode": str(l1_dict["episode"]),
            "filename": os.path.basename(req.filename), "path": req.filename, "platform": l1_dict["platform"],
            "processed_name": meta.processed_name or "", "resolution": l1_dict["resolution"],
            "season": l1_dict["season"], "source": l1_dict["source"], "subtitle": l1_dict["subtitle"],
            "team": l1_dict["team"], "title": l1_dict["cn_name"] or l1_dict["en_name"] or meta.processed_name,
            "video_effect": meta.video_effect, "video_encode": l1_dict["video_encode"], "year": l1_dict["year"] or "",
            "tmdb_id": current_tmdb_id or "" 
        }
        
        if cloud_data:
            final_dict.update({
                "title": cloud_data.get("title") or cloud_data.get("name") or final_dict["title"],
                "tmdb_id": str(cloud_data.get("id", "")),
                "poster_path": cloud_data.get("poster_path"),
                "release_date": cloud_data.get("release_date") or cloud_data.get("first_air_date"),
                "vote_average": cloud_data.get("vote_average"),
                "origin_country": ", ".join(cloud_data.get("origin_country", [])) if isinstance(cloud_data.get("origin_country"), list) else (cloud_data.get("origin_country") or "")
            })
            if not final_dict["year"] and final_dict.get("release_date"): final_dict["year"] = final_dict["release_date"][:4]

        # --- [STAGE 4] 执行规则渲染 (L3) ---
        if req.custom_render:
            logs.append("┃")
            logs.append("┃ [DEBUG][STEP 8.5: 自定义渲染词处理]: 启动微服务引擎渲染")
            await RenderEngine.apply_rules(
                final_result=final_dict,
                local_result=l1_dict,
                raw_filename=req.filename,
                rules=req.custom_render,
                logs=logs,
                tmdb_provider=tmdb_client
            )
            logs.append("┗ ✅ 渲染流程结束")

        # --- [STAGE 5] 日志输出与响应封装 ---
        logs.append("┃")
        logs.append("┃ [DEBUG][STEP 7: 本地解析属性审计]: 原始提取结论")
        label_map_l1 = {"cn_name": "中文搜索块", "en_name": "英文搜索块", "type": "媒体类型", "season": "季度", "episode": "集数", "team": "制作小组"}
        for k in ["cn_name", "en_name", "type", "season", "episode", "team"]:
            if l1_dict.get(k): logs.append(f"┣ 🏷️ {label_map_l1.get(k, k)}: {l1_dict[k]}")
        logs.append("┗ ✅ 本地解析完成")

        logs.append("┃")
        logs.append("┃ [DEBUG][STEP 9: 最终结果属性审计]: 融合结论 (final_result)")
        label_map_final = {
            "title": "最终标题", "tmdb_id": "TMDB 编号", "category": "媒体类型", "season": "季度", "episode": "集数", 
            "team": "制作小组", "resolution": "分辨率", "video_encode": "视频编码", "subtitle": "字幕语言", "processed_name": "渲染后标题"
        }
        for k in ["title", "tmdb_id", "category", "season", "episode", "team", "resolution", "video_encode", "subtitle", "processed_name"]:
            val = final_dict.get(k)
            logs.append(f"┣ 🔹 {label_map_final.get(k, k)}: {val if val else '-'}")
            
        duration = f"{time.time() - start_time:.1f}s"
        final_dict["duration"] = duration
        summary_text = f"{'['+final_dict.get('team','')+'] ' if final_dict.get('team') else ''}{final_dict.get('category')} S{final_dict.get('season')}E{final_dict.get('episode')}"
        logs.append(f"┗ 🏁 识别完成：{summary_text} (总耗时: {duration})")
        
        return RecognitionResponse(
            _filename=req.filename,
            _task_id=0,
            local_result=LocalResult(**l1_dict),
            final_result=FinalResult(**final_dict),
            cloud_result=cloud_data,
            summary=summary_text,
            logs=logs
        )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    return {"status": "healthy"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)