# Anime-Matcher PC (桌面端剧集整理工具)

基于 `anime-matcher` 项目内置的 `recognition_service` Pipeline 架构，提供桌面端视频重命名与整理功能。

> **与旧版的区别**: 旧版 PC 客户端是独立项目，需要从 GitHub 下载算法内核。新版直接内置于 `anime-matcher` 项目中，通过 `sys.path` 自动加载 `recognition_service` Pipeline，无需下载、零配置启动。

---

## ✨ 核心特性

- **内置 Pipeline 引擎**: 直接调用 `RecognitionContext` + `RecognitionWorkflow` 五阶段流水线 (Parser → Matcher → Enricher → Maintenance → Renderer)
- **全量审计日志**: 与服务端 API 完全对齐的 emoji 格式日志，完整回溯每个判决细节
- **智能记忆与本地缓存**: 文件名指纹匹配，秒级二次识别
- **规则管理中心**: 支持本地规则与远程订阅一键同步 (Peewee + SQLite)
- **智能重命名引擎**: 电影/剧集双轨制独立格式，完美适配补零逻辑 (`season_02` / `episode_02`)
- **用户体验**: 拖拽支持、URL 编码自动还原、窗口布局永久记忆

---

## 🏗️ 架构概览

```
anime-matcher/                    # 主项目根目录
├── src/
│   ├── recognition_engine/       # L1 识别内核 (Anitopy)
│   ├── recognition_service/      # 微服务层 (Pipeline + FastAPI)
│   └── anitopy/                  # C++ 绑定库
├── data/                         # SQLite 数据库 (指纹 + 元数据缓存)
│   └── matcher_storage.db
├── anime-matcher-pc/             # ← 本 PC 客户端
│   ├── main.py                   # 程序启动入口
│   ├── requirements.txt          # PC 客户端专属依赖
│   ├── VideoRenamer_Qt6.ini      # 用户配置 (自动生成)
│   ├── VideoRenamer.db           # 规则数据库 (自动生成)
│   └── src/
│       ├── core/
│       │   ├── processor.py      # 识别处理器 (调用 Pipeline)
│       │   ├── renamer.py        # 重命名引擎 (字段占位符)
│       │   └── rules.py          # 规则同步与合并
│       ├── gui/
│       │   ├── main_window.py    # 主窗口 Shell
│       │   ├── worker.py         # 后台重命名线程
│       │   ├── rule_manager.py   # 规则管理 UI
│       │   └── tabs/
│       │       ├── main_tab.py   # 主界面 (文件列表 + 预览)
│       │       └── settings_tab.py # 设置页
│       └── utils/
│           ├── paths.py          # 路径管理 (自动桥接主项目 src/)
│           ├── config.py         # QSettings 配置管理
│           └── database.py       # Peewee 规则数据库
└── pyproject.toml                # 主项目依赖
```

### 工作原理

```
用户拖入文件
    ↓
MainTab → RenameWorker (QThread)
    ↓
RecognitionProcessor.recognize_file()
    ↓
RecognitionContext (构建上下文: 规则 + 云端凭据 + 覆盖参数)
    ↓
RecognitionWorkflow.run()
    ├── ParserStage      (L1 内核解析 + 指纹预匹配)
    ├── MatcherStage     (L2 TMDB/Bangumi 云端对撞)
    ├── EnrichmentStage  (L2.5 字段补全)
    ├── MaintenanceStage (L3 指纹 + 元数据写入)
    └── ResultRenderer   (L3 专家渲染 + 审计日志)
    ↓
RecognitionResult {success, final_result, raw_meta, tmdb_match, logs}
    ↓
RenameEngine.build_paths() (字段占位符 → 新路径)
    ↓
预览表格 / 执行重命名
```

---

## 🚀 快速上手

### 1. 环境准备

确保系统已安装 **Python 3.10+** 和主项目的依赖:

```bash
# 在主项目根目录安装核心依赖
cd anime-matcher
pip install -e .

# 安装 PC 客户端专属依赖
pip install -r anime-matcher-pc/requirements.txt
```

### 2. 配置云端联动 (推荐)

启动程序后进入 **设置** 页签:
- **TMDB API Key**: 前往 [TMDB 官网](https://www.themoviedb.org/settings/api) 申请
- **TMDB 代理**: 中国大陆用户请填入代理地址 (如 `http://127.0.0.1:7890`)

### 3. 启动

```bash
cd anime-matcher-pc
python main.py
```

拖入视频文件或文件夹 → 点击 **预览重命名** → 确认后点击 **执行重命名**。

---

## 🧩 重命名支持字段

重命名格式支持以下字段，使用花括号包裹，如 `{title}`。字段名与主项目 API `final_result` 完全一致:

| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| **title** | string | 最终采信标题 (优先使用云端/专家规则修正) |
| **tmdb_id** | string | TMDB 唯一识别码 |
| **category** | string | 媒体分类 (`剧集` / `电影`) |
| **processed_name** | string | 渲染后标题 (按专家规则重命名后的文件名) |
| **season** | int | 最终决定的季度 |
| **season_02** | string | 季号补零 (如 `01`) |
| **episode** | string | 最终决定的集数或范围 (如 `13` 或 `01-12`) |
| **episode_02** | string | 集号补零 (如 `05`) |
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
| **release_date** | string | 正式上映日期 |
| **poster_path** | string | 云端海报图片路径 |
| **duration** | string | 识别耗时 |
| **filename** | string | 原始文件名 (无后缀) |
| **path** | string | 原始完整路径 |

---

## ⚙️ 设置项说明

### 联网匹配

设置项名称与主项目 API `RecognitionRequest` 字段完全对齐:

| UI 标签 | config key | API 字段 | 说明 |
| :--- | :--- | :--- | :--- |
| 云端联动 | `with_cloud` | `with_cloud` | 云端联动总开关，开启后执行网络匹配 |
| TMDB API Key | `tmdb_api_key` | `tmdb_api_key` | TMDB 密钥 (也可通过环境变量 `TMDB_API_KEY` 配置) |
| TMDB 代理 | `tmdb_proxy` | `tmdb_proxy` | TMDB 网络请求代理 |
| Bangumi Token | `bangumi_token` | `bangumi_token` | Bangumi 个人授权令牌 (可选) |
| Bangumi 代理 | `bangumi_proxy` | `bangumi_proxy` | Bangumi 网络请求代理 |
| 智能记忆与本地缓存 | `use_storage` | `use_storage` | 自动记忆识别历史并缓存元数据 |
| 动画优先级加权 | `anime_priority` | `anime_priority` | 联网匹配时开启动画分类加权优化 |
| Bangumi 优先 | `bangumi_priority` | `bangumi_priority` | 优先检索 Bangumi 库并映射至 TMDB |
| Bangumi 故障转移 | `bangumi_failover` | `bangumi_failover` | TMDB 检索失败时自动尝试 Bangumi |
| 合集增强 | `batch_enhancement` | `batch_enhancement` | 开启合集/批处理增强逻辑 |

### 数据库管理

| 按钮 | 清理表 | 说明 |
| :--- | :--- | :--- |
| 清理元数据缓存 | `metadata_cache` | TMDB 详情缓存 |
| 清理标题记忆 | `recognition_memory` | 旧版标题→ID 映射 |
| 清理指纹缓存 | `fingerprint_cache` | 文件名指纹→ID 映射 |

### 重命名后正则替换

在生成新文件名后，对文件名执行正则替换。每行一条规则，格式为 `pattern => replacement`。

示例:
```
(?i) unwanted => replacement
```

---

## 📁 规则管理

PC 客户端内置规则管理中心 (第二个页签)，支持四类规则。分类名称与主项目 API 对齐:

| UI 标题 | DB 分类 | API 字段 | 作用阶段 | 说明 |
| :--- | :--- | :--- | :--- | :--- |
| 自定义识别词 (L1 预处理) | `noise` | `custom_words` | L1 解析前 | 屏蔽词/替换/提取 (A => B) |
| 自定义制作组 (L1 辅助) | `group` | `custom_groups` | L1 识别 | 自定义制作组名单，辅助内核锁定小组字段 |
| 自定义渲染规则 (L3 专家渲染) | `render` | `custom_render` | L3 结论后 | 条件修正与偏移计算 (翻译/偏移/重定向) |
| 自定义特权规则 (L1 特权提取) | `privileged` | `special_rules` | L1 最早期 | 正则 => {[字段=值]}，集数直接锁定 |

每类规则支持:
- **本地规则**: 直接在文本框中编辑 (每行一条)
- **远程订阅**: 填入 URL，点击同步自动拉取并缓存

规则编写指南请参考主项目 `docs/` 目录下的文档。

---

## 🔧 与主项目的关系

| 组件 | 主项目 | PC 客户端 |
| :--- | :--- | :--- |
| 识别引擎 | `src/recognition_service/` | 直接通过 `sys.path` 导入 |
| 数据库 | `data/matcher_storage.db` | 共享 (通过 `AM_DATABASE_PATH` 环境变量) |
| 规则系统 | API 请求参数 | 本地 Peewee SQLite (`VideoRenamer.db`) |
| 配置管理 | 环境变量 / Docker | QSettings INI (`VideoRenamer_Qt6.ini`) |
| 用户界面 | FastAPI Swagger | PyQt6 桌面 GUI |
| 日志格式 | emoji + `┃`/`┣`/`┗` 前缀 | 完全一致 (操作日志也使用 emoji) |

PC 客户端通过 `src/utils/paths.py` 自动:
1. 将主项目 `src/` 加入 `sys.path`
2. 设置 `AM_DATABASE_PATH` 指向主项目 `data/matcher_storage.db`

因此无需任何手动配置即可直接运行。
