from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from .context import RecognitionContext
from .recognizer import RecognitionWorkflow
import uvicorn

app = FastAPI(title="ANIMEProMatcher Kernel Service")


class RecognitionRequest(BaseModel):
    filename: str = Field(..., description="待识别的文件名", json_schema_extra={"example": "[ANi] 花樣少年少女 - 02.mkv"})
    custom_words: List[str] = Field(default=[], description="L1 预处理规则 (屏蔽词/替换/提取)")
    custom_groups: List[str] = Field(default=[], description="自定义制作组名单")
    custom_render: List[str] = Field(default=[], description="L3 专家渲染规则 (翻译/偏移/重定向)")
    special_rules: List[str] = Field(default=[], description="特权提取规则 (正则 => {[字段=值]})")
    force_filename: bool = Field(default=False, description="强制单文件模式")
    batch_enhancement: bool = Field(default=False, description="合集增强模式")

    # 方案 B: 扩展参数
    with_cloud: bool = Field(default=False, description="是否开启云端联网元数据匹配")
    use_storage: bool = Field(default=False, description="是否启用智能记忆与本地缓存")
    anime_priority: bool = Field(default=True, description="动画优先级加权")
    bangumi_priority: bool = Field(default=False, description="是否优先从 Bangumi 检索")
    bangumi_failover: bool = Field(default=True, description="是否在 TMDB 失败时启用 Bangumi 故障转移")
    tmdb_api_key: Optional[str] = Field(default=None, description="TMDB API Key (也可通过环境变量 TMDB_API_KEY 配置)")
    tmdb_proxy: Optional[str] = Field(default=None, description="TMDB 代理地址")
    tmdb_id: Optional[str] = Field(default=None, description="【已知 ID 提示】传入后可直接触发专家规则，跳过云端检索")
    tmdb_type: Optional[str] = Field(default=None, description="【已知类型提示】movie 或 tv，配合 tmdb_id 使用")
    bangumi_token: Optional[str] = Field(default=None, description="Bangumi 个人授权令牌")
    bangumi_proxy: Optional[str] = Field(default=None, description="Bangumi 代理地址")


@app.post("/recognize", summary="核心识别接口")
async def recognize(req: RecognitionRequest):
    """
    执行全链路识别流程：
    1. 指纹判定 (智能记忆)
    2. 内核解析 (L1)
    3. 数据对撞 (L2 云端匹配)
    4. 字段补全 (L2.5)
    5. 规则渲染 (L3)
    6. 记忆维护 (指纹+元数据写入)

    返回结构与主项目对齐：
    - success: 是否成功
    - final_result: 最终标准化元数据
    - raw_meta: L1 内核原始提取结果
    - tmdb_match: L2 云端匹配数据
    - logs: 全链路审计日志
    """
    try:
        ctx = RecognitionContext.from_request(req)
        workflow = RecognitionWorkflow(ctx)
        result = await workflow.run()
        return result
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
async def health():
    return {"status": "healthy"}


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
