# ANIMEProMatcher Kernel

高性能动漫文件名识别与元数据联动核心服务。采用 **Pipeline 流水线架构**，提供从"原始文件名"到"标准化元数据"的一站式解析方案。

> 本项目是主项目 `recognition/` 模块的**独立微服务分支**，架构与接口完全对齐，去除了 PostgreSQL / ConfigManager / TmdbMateFull 等外部依赖，使用 SQLite 实现零配置启动。

## 🏗️ 架构概览

```
src/
├── recognition_engine/          # L1 识别内核 (Anitopy 深度定制)
│   ├── kernel.py                #   核心解析入口 core_recognize()
│   ├── title_cleaner.py         #   标题清洗器 (L1 预处理)
│   ├── tag_extractor.py         #   规格标签提取
│   ├── special_episode_handler.py  # 特权集数锁定
│   ├── bgm_matcher/             #   Bangumi 对撞算法
│   └── tmdb_matcher/            #   TMDB 评分算法
│
├── recognition_service/         # 微服务层 (FastAPI + Pipeline)
│   ├── main.py                  #   FastAPI 入口
│   ├── context.py               #   RecognitionContext 任务上下文
│   ├── recognizer.py            #   RecognitionWorkflow 编排器
│   ├── renderer.py              #   ResultRenderer 最终结论构建
│   ├── storage_manager.py       #   SQLite 存储 (指纹+元数据缓存)
│   ├── config.py                #   独立版配置
│   │
│   ├── pipeline/                #   Pipeline 流水线
│   │   ├── parser.py            #     L1 解析 + 指纹预匹配
│   │   ├── matcher.py           #     L2 云端搜索对撞
│   │   ├── enricher.py          #     L2.5 字段补全
│   │   └── maintenance.py       #     L3 记忆维护 (指纹+元数据写入)
│   │
│   ├── data_provider/           #   数据提供者
│   │   ├── tmdb/client.py       #     TMDB 统一数据中心
│   │   ├── bangumi/client.py    #     Bangumi 独立数据源
│   │   └── local_cache.py       #     本地缓存 DAO (指纹+元数据)
│   │
│   └── render/                  #   渲染引擎
│       ├── engine.py            #     专家级规则引擎
│       └── reporter.py          #     审计日志汇报
│
└── anitopy/                     # Anitopy C++ 绑定库

anime-matcher-pc/                # 桌面端客户端 (可选，非必需)
├── main.py                      #   PyQt6 启动入口
└── src/
    ├── core/                    #   识别处理器 + 重命名引擎
    ├── gui/                     #   PyQt6 界面 (主界面/规则管理/设置)
    └── utils/                   #   路径桥接/配置/规则数据库
```

### Pipeline 流程

```
请求 → ParserStage → MatcherStage → EnrichmentStage → MaintenanceStage → ResultRenderer → 响应
         │              │              │                  │                   │
         ▼              ▼              ▼                  ▼                   ▼
    指纹预匹配      云端搜索对撞     字段补全          指纹+元数据         规则渲染
    L1 内核解析     TMDB/Bangumi    缓存补全          写入存储            审计日志
```

## 🚀 核心特性

- **Pipeline 流水线架构**: 与主项目完全对齐的 5 阶段流水线设计
  - **ParserStage (L1)**: 内置深度定制 anitopy 语义解析 + 文件名指纹智能记忆
  - **MatcherStage (L2)**: TMDB & Bangumi 智能对撞与自动映射算法，支持网络重试
  - **EnrichmentStage (L2.5)**: 元数据字段补全，缓存优先
  - **MaintenanceStage (L3)**: 指纹与元数据自动写入，下次识别秒级命中
  - **ResultRenderer (L3)**: 专家级渲染引擎 + 审计日志汇报
- **智能记忆**: 文件名指纹匹配（数字替换为 `#`），带有效性校验，避免简单指纹误匹配
- **全量审计日志**: 与主项目对齐的 emoji 格式日志，完整回溯每一个判决细节
- **完全解耦**: 零配置启动，SQLite 存储，支持 Docker 容器化

## 📖 API 接口 (POST `/recognize`)

### 请求示例 (本地解析)

```json
{
  "filename": "[ANi] 花樣少年少女 - 02.mkv",
  "custom_words": [],
  "custom_groups": [],
  "custom_render": [],
  "special_rules": [],
  "force_filename": false,
  "batch_enhancement": false,
  "with_cloud": false,
  "use_storage": false,
  "anime_priority": true,
  "bangumi_priority": false,
  "bangumi_failover": true,
  "tmdb_api_key": null,
  "tmdb_proxy": null,
  "tmdb_id": null,
  "tmdb_type": null,
  "bangumi_token": null,
  "bangumi_proxy": null
}
```

### 请求示例 (云端联动 + 专家规则)

```json
{
  "filename": "[MILKs&LoliHouse] Saioshi no Gikei - 08 [WebRip 1080p HEVC-10bit AAC ASS].mkv",
  "custom_words": ["Saioshi no Gikei => 宰相的义弟大人"],
  "custom_groups": ["MILKs", "LoliHouse", "MILKs&LoliHouse"],
  "custom_render": ["@?{[tmdbid=273134;type=tv;e=13-24]} => {[s=2;e=EP-12]}"],
  "special_rules": ["^\\[(MILKs&LoliHouse)\\]\\s+(.+?)\\s+-\\s+(\\d{1,4}) => {[group=\\1;title=\\2;e=\\3]} # MLH定向"],
  "force_filename": false,
  "batch_enhancement": false,
  "with_cloud": true,
  "use_storage": true,
  "anime_priority": true,
  "bangumi_priority": false,
  "bangumi_failover": true,
  "tmdb_api_key": "your_api_key_here",
  "tmdb_proxy": null,
  "tmdb_id": null,
  "tmdb_type": null,
  "bangumi_token": null,
  "bangumi_proxy": null
}
```

### 请求参数说明

| 字段名 | 默认值 | 类型 | 功能描述 |
| :--- | :--- | :--- | :--- |
| **filename** | (必填) | string | 待识别的文件名或完整文件路径 |
| **custom_words** | `[]` | list | L1 预处理规则 (A => B)，在解析前执行 |
| **custom_groups** | `[]` | list | 自定义制作组名单，辅助内核锁定小组字段 |
| **custom_render** | `[]` | list | L3 专家渲染规则: 支持条件修正与偏移计算 |
| **special_rules** | `[]` | list | 特权提取规则: `正则 => {[字段=值]}` |
| **force_filename** | `false` | bool | 强制单文件模式，屏蔽路径干扰词 |
| **batch_enhancement** | `false` | bool | 开启合集/批处理增强逻辑 |
| **with_cloud** | `false` | bool | 云端联动总开关，开启后执行网络匹配 |
| **use_storage** | `false` | bool | 智能记忆与本地缓存: 自动记忆识别历史并缓存元数据 |
| **anime_priority** | `true` | bool | 联网匹配时开启动画分类加权优化 |
| **bangumi_priority** | `false` | bool | 优先检索 Bangumi 库并映射至 TMDB |
| **bangumi_failover** | `true` | bool | Bangumi 故障转移: TMDB 检索失败时自动尝试 Bangumi |
| **tmdb_api_key** | `null` | string | TMDB 密钥 (也可通过环境变量 `TMDB_API_KEY` 配置) |
| **tmdb_proxy** | `null` | string | TMDB 网络请求代理 |
| **tmdb_id** | `null` | string | 已知 ID 提示: 传入后可直接触发专家规则，跳过云端检索 |
| **tmdb_type** | `null` | string | 已知类型提示: `movie` 或 `tv`，配合 `tmdb_id` 使用 |
| **bangumi_token** | `null` | string | Bangumi 个人授权令牌 (可选) |
| **bangumi_proxy** | `null` | string | Bangumi 网络请求代理 |

---

### 返回结果结构

返回结构与主项目完全对齐：

```json
{
  "success": true,
  "final_result": { ... },
  "raw_meta": { ... },
  "tmdb_match": { ... },
  "logs": [...]
}
```

### `final_result` 字段说明

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| **title** | string | 最终采信标题 (优先使用云端/专家规则修正) |
| **tmdb_id** | string | TMDB 唯一识别码 |
| **category** | string | 媒体分类 (`剧集` / `电影`) |
| **secondary_category** | string | 二级分类 (独立版暂不支持，返回 null) |
| **processed_name** | string | 渲染后标题: 按照专家规则重命名后的文件名 |
| **poster_path** | string | 云端海报图片路径 |
| **release_date** | string | 正式上映日期 |
| **season** | int | 最终决定的季度 |
| **episode** | string | 最终决定的集数或范围 (如 `13` 或 `01-12`) |
| **team** | string | 最终确定的制作小组 |
| **resolution** | string | 最终分辨率 |
| **video_encode** | string | 最终视频编码 |
| **video_effect** | string | 视频特效 (如 `HDR`, `Dolby Vision`) |
| **audio_encode** | string | 最终音频编码 |
| **subtitle** | string | 最终字幕语言 |
| **source** | string | 最终资源来源 |
| **platform** | string | 最终发布平台 |
| **origin_country** | string | 制片国家 |
| **vote_average** | float | 媒体评分 |
| **year** | string | 最终年份 |
| **duration** | string | 识别耗时 |
| **filename** | string | 原始文件名 |
| **path** | string | 原始完整路径 |

### `raw_meta` 字段说明

L1 内核原始提取结果（`vars(meta)` 快照），包含但不限于：

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `cn_name` | string | 提取到的中文剧名搜索块 |
| `en_name` | string | 提取到的英文/特征搜索块 |
| `team` | string | 识别到的制作组/字幕组 |
| `begin_season` | int | 识别到的季度编号 |
| `begin_episode` | int | 识别到的集数编号 |
| `is_batch` | bool | 是否判定为合集/批处理 |
| `end_episode` | int | 合集时的结束集数 |
| `type` | string | 媒体类型 (`tv` / `movie` / `auto`) |
| `resource_pix` | string | 分辨率规格 |
| `resource_platform` | string | 发布平台 |
| `resource_type` | string | 资源来源 |
| `video_encode` | string | 视频编码格式 |
| `audio_encode` | string | 音频编码格式 |
| `subtitle_lang` | string | 识别到的字幕语言 |
| `year` | string | 识别到的发布年份 |
| `processed_name` | string | 内核处理后的标题 |
| `forced_tmdbid` | string | 规则锁定的 TMDB ID |

### `tmdb_match` 字段说明

L2 云端匹配结果（TMDB 标准化数据），包含：

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `id` | int | TMDB ID |
| `title` / `name` | string | 标题 |
| `original_title` | string | 原始标题 |
| `overview` | string | 简介 |
| `poster_path` | string | 海报路径 |
| `backdrop_path` | string | 背景图路径 |
| `vote_average` | float | 评分 |
| `release_date` | string | 上映/首播日期 |
| `year` | string | 年份 |
| `origin_country` | list | 制片国家列表 |
| `genres` | list | 类型列表 |
| `cast` | list | 演员列表 |
| `tagline` | string | 标语 |
| `type` | string | 媒体类型 (`tv` / `movie`) |

### `logs` 字段说明

全链路审计日志列表，与主项目格式完全对齐，包含 emoji 标签：

```
🚀 --- [ANIME 深度审计流水线启动] ---
┃ [待处理条目]: [ANi] Spy x Family - 02.mkv
┃ [配置] 策略状态: 动漫优化[ON] | 合集增强[OFF] | 智能记忆[OFF] ...
┣ [TMDB] ☁️ GET https://api.themoviedb.org/3/search/tv?...
┣ [TMDB-Match] ⚖️ 正在对合并后的 3 个候选进行交叉对撞...
┗ ✅ 最终采信: Spy x Family (ID: 120089)
📢 [最终结论汇报 (标准化元数据)]
┣ 🎬 标题: Spy x Family
┣ 📆 年份: 2022
┣ 🆔 TMDB ID: 120089
┣ 🎦 类型: 剧集
┣ 📅 季号: 1 | 集号: 2
┗ 📄 渲染后名: [ANi] Spy x Family - 02
⏱️ [性能审计]: 全链路耗时 1234ms (本地解析: 45ms | 元数据匹配: 1100ms | ...)
```

---

## 📦 快速启动

### Docker 部署 (推荐)

```bash
cd anime-matcher && docker-compose up -d
```

访问 `http://localhost:8081/docs` 查看 Swagger 交互式文档。

### 本地运行

```bash
pip install -e .
PYTHONPATH=src python -m recognition_service.main
```

### 桌面端客户端 (可选)

`anime-matcher-pc/` 是一个基于 PyQt6 的桌面端重命名工具，直接调用本项目的 Pipeline 引擎，适合不想部署 API 服务的个人用户。

> 该客户端是**独立的可选组件**，不影响核心识别服务的运行。仅需要 API 服务的用户无需安装。

```bash
# 安装桌面端额外依赖
pip install -r anime-matcher-pc/requirements.txt

# 启动 GUI
cd anime-matcher-pc && python main.py
```

详见 [anime-matcher-pc/README.md](./anime-matcher-pc/README.md)。

### 环境变量

| 变量名 | 默认值 | 说明 |
| :--- | :--- | :--- |
| `TMDB_API_KEY` | - | TMDB API 密钥 |
| `TMDB_PROXY` | - | TMDB 代理地址 |
| `BANGUMI_TOKEN` | - | Bangumi 授权令牌 |
| `BANGUMI_PROXY` | - | Bangumi 代理地址 |
| `AM_DATABASE_PATH` | `data/matcher_storage.db` | SQLite 数据库路径 |

---

## 📖 规则编写指南

本项目支持三套强大的规则系统：

- [**自定义特权规则 (最高优先级)**](./docs/privileged-rules.md): 作用于识别流程最早期。命中后集数直接锁定，标题作为优先搜索候选。
- [**自定义识别词 (预处理)**](./docs/recognition-rules.md): 作用于"文件名"解析前。用于屏蔽干扰字符、纠正标题误匹配、或强制锁定特定 TMDB ID。
- [**自定义渲染词 (后处理)**](./docs/render-rules.md): 作用于"匹配结论"生成后。支持专家级的条件修正（基于 ID/季/集）、集数偏移计算、自动打标签等。

---

## 🔄 与主项目对齐情况

| 主项目 `recognition/` | 独立版 `recognition_service/` | 对齐状态 |
| :--- | :--- | :--- |
| `context.py` (RecognitionContext) | `context.py` | ✅ 字段名一致 (meta/tmdb_data/cache_dao/all_noise/all_groups/all_render/all_privilege) |
| `recognizer.py` (RecognitionWorkflow) | `recognizer.py` | ✅ 方法名一致 (run)，返回 data_packet |
| `renderer.py` (ResultRenderer) | `renderer.py` | ✅ apply_to_context + _prepare_data_packet |
| `pipeline/parser.py` | `pipeline/parser.py` | ✅ run() + _apply_forced_params |
| `pipeline/matcher.py` | `pipeline/matcher.py` | ✅ search_cloud 策略一致 |
| `pipeline/enricher.py` | `pipeline/enricher.py` | ✅ 简化版 (无 TmdbMateFull) |
| `pipeline/maintenance.py` | `pipeline/maintenance.py` | ✅ 指纹+元数据写入 |
| `render/engine.py` | `render/engine.py` | ✅ data_packet 结构 + 链式规则 |
| `render/reporter.py` | `render/reporter.py` | ✅ emoji 日志格式一致 |
| `data_provider/tmdb/client.py` | `data_provider/tmdb/client.py` | ✅ + 网络重试 (Tuple 返回) |
| `data_provider/bangumi/client.py` | `data_provider/bangumi/client.py` | ✅ |
| `data_provider/local_cache.py` | `data_provider/local_cache.py` | ✅ 指纹+有效性校验 (SQLite 替代 PostgreSQL) |
| API 返回格式 | ✅ 一致 | `success` / `final_result` / `raw_meta` / `tmdb_match` / `logs` |
| 日志格式 | ✅ 一致 | emoji 标签 + `┃`/`┣`/`┗` 前缀 |

### 独立版特有差异

- **存储后端**: SQLite (`storage_manager.py`) 替代 PostgreSQL (`MetaCacheManager`)
- **配置管理**: 请求参数直传，无 `ConfigManager` 依赖
- **`with_cloud` 开关**: 独立版新增云端联动总开关，主项目始终联网
- **简化模块**: 无 `OfflineDAO` / `TmdbMateFull` / `AIHelper` / `Renamer`

---

## 鸣谢参考项目

- [anitopy](https://github.com/igorcmoura/anitopy)
- [Symedia](https://github.com/shenxianmq/Symedia)
- [MoviePilot](https://github.com/jxxghp/MoviePilot)
