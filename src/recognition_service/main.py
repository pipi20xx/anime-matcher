from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .context import RecognitionContext
from .recognizer import RecognitionWorkflow
import uvicorn

app = FastAPI(title="ANIMEProMatcher Kernel Service")


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
    try:
        # 构建上下文
        ctx = RecognitionContext.from_request(req)

        # 执行 Pipeline
        await RecognitionWorkflow.recognize(ctx)

        # 构建响应
        return RecognitionResponse(
            _filename=req.filename,
            _task_id=0,
            local_result=LocalResult(**ctx.local_result),
            final_result=FinalResult(**ctx.final_result),
            cloud_result=ctx.cloud_match,
            summary=getattr(ctx, 'summary', ''),
            logs=ctx.logs
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
