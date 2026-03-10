# ANIMEProMatcher Kernel

高性能动漫文件名识别与元数据联动核心 (Layer 1 + 2 + 3)。采用全解耦微服务架构，提供从“原始文件名”到“标准化元数据”的一站式解析方案。

## 🚀 核心特性

- **三层架构设计**:
  - **Layer 1 (Core)**: 基于内置深度定制 anitopy 的语义解析内核。
  - **Layer 2 (Cloud)**: 集成 TMDB & Bangumi 智能对撞与自动映射算法。
  - **Layer 3 (Render)**: 内置专家级渲染引擎，支持复杂的集数偏移计算 (@formula) 与标题翻译。
- **全量审计日志**: 独创 9 步深度审计流，完整回溯解析、匹配、对撞、渲染的每一个判决细节。
- **完全解耦**: 零配置启动，支持 Docker 容器化，不依赖外部数据库。

## 📖 API 请求规范 (POST `/recognize`)

### 完整请求示例 (JSON Body)

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
  
  "tmdb_api_key": "string",
  "tmdb_proxy": "string",
  "tmdb_id": "string",
  "tmdb_type": "tv",
  "bangumi_token": "string",
  "bangumi_proxy": "string"
}
```

### 完整请求示例 (云端联动)

```json
{
  "filename": "[MILKs&LoliHouse] Saioshi no Gikei o Mederu Tame, Nagaikishimasu! - 08 [WebRip 1080p HEVC-10bit AAC ASS].mkv",
  "custom_words": ["Saioshi no Gikei o Mederu Tame, Nagaikishimasu! => 宰相的义弟大人"],
  "custom_groups": ["MILKs", "LoliHouse", "MILKs&LoliHouse"],
  "custom_render": ["@?{[tmdbid=273134;type=tv;e=13-24]} => {[s=2;e=EP-12]}"],
  "special_rules": ["^\\[(MILKs&LoliHouse)\\]\\s+(.+?)\\s+-\\s+(\\d{1,4}) => {[group=\\1;title=\\2;e=\\3]} # MLH定向"],
  "force_filename": false,
  "batch_enhancement": false,
  "with_cloud": true,
  "use_storage": false,
  "anime_priority": true,
  "bangumi_priority": false,
  "bangumi_failover": true
}
```

**示例说明：**
- `custom_words`: 将日文标题替换为中文，便于云端搜索
- `custom_groups`: 预定义制作组名单，确保正确识别 `MILKs&LoliHouse`
- `custom_render`: 专家渲染规则 - 当 TMDB ID 为 273134 且集数在 13-24 时，修正为第二季并偏移集数
- `special_rules`: 特权提取规则 - 针对特定字幕组格式，优先提取标题和集数
- `with_cloud: true`: 开启云端联动，自动从 TMDB/Bangumi 获取元数据

### 请求参数详细说明

| 字段名 | 默认值 | 类型 | 功能描述 |
| :--- | :--- | :--- | :--- |
| **filename** | (必填) | string | 待识别的文件名或完整文件路径 |
| **custom_words** | `[]` | list | L1 预处理规则 (A => B)，在解析前执行 |
| **custom_groups** | `[]` | list | 自定义制作组名单，辅助内核锁定小组字段 |
| **custom_render** | `[]` | list | **L3 专家渲染规则**: 支持条件修改与偏移计算 |
| **special_rules** | `[]` | list | **特权提取规则**: 格式 `正则表达式 => {[字段=值;字段=值]} # 描述`，支持字段: group/title/e/s/tmdbid/type/year |
| **force_filename**| `false` | bool | 强制单文件模式，屏蔽路径干扰词 |
| **batch_enhancement** | `false`| bool | 开启合集/批处理增强逻辑 |
| **with_cloud** | `false` | bool | **云端联动总开关**，开启后执行网络匹配 |
| **use_storage** | `false` | bool | **智能记忆与本地缓存**: 启用后可自动记忆识别历史并缓存元数据 |
| **anime_priority**| `true` | bool | 联网匹配时开开启动画分类加权优化 |
| **bangumi_priority**| `false` | bool | 优先检索 Bangumi 库并映射至 TMDB |
| **bangumi_failover**| `true` | bool | **Bangumi 故障转移**: 当 TMDB 检索失败时，自动尝试 Bangumi 检索并映射 |
| **tmdb_api_key** | `null` | string | TMDB 密钥 (也可通过环境变量配置) |
| **tmdb_proxy** | `null` | string | 指定 TMDB 网络请求代理 |
| **tmdb_id** | `null` | string | **已知 ID 提示**: 传入后可直接触发专家规则，跳过云端检索 |
| **tmdb_type** | `null` | string | **已知类型提示**: 取值 `movie` 或 `tv`，配合 `tmdb_id` 使用以消除歧义 |
| **bangumi_token** | `null` | string | Bangumi 个人授权令牌 (可选) |
| **bangumi_proxy** | `null` | string | 指定 Bangumi 网络请求代理 |

---

## 📖 返回结果全字段说明

### 1. `local_result` (本地解析原始结论)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| `cn_name` | string | 提取到的中文剧名搜索块 |
| `en_name` | string | 提取到的英文/特征搜索块 |
| `team` | string | 识别到的制作组/字幕组 |
| `season` | int | 识别到的季度编号 |
| `episode` | int | 识别到的集数编号 |
| `is_batch` | bool | 是否判定为合集/批处理 |
| `end_episode` | int | 合集时的结束集数 |
| `type` | string | 媒体类型 (`tv` / `movie`) |
| `resolution` | string | 分辨率规格 |
| `platform` | string | 发布平台 |
| `source` | string | 资源来源 |
| `video_encode` | string | 视频编码格式 |
| `audio_encode` | string | 音频编码格式 |
| `subtitle` | string | 识别到的字幕语言 |
| `year` | string | 识别到的发布年份 |

### 2. `final_result` (全信托最终结论 - 与主项目对齐)
| 字段名 | 类型 | 说明 |
| :--- | :--- | :--- |
| **`title`** | string | **最终采信标题** (优先使用云端/专家规则修正) |
| **`tmdb_id`** | string | **TMDB 唯一识别码** |
| `category` | string | 媒体分类 (`剧集` / `电影`) |
| `processed_name`| string | **渲染后标题**: 按照专家规则重命名后的文件名 |
| `poster_path` | string | 云端海报图片路径 |
| `release_date` | string | 正式上映日期 |
| `season` | int | 最终决定的季度 |
| `episode` | string | 最终决定的集数或范围 (如 `13` 或 `01-12`) |
| `team` | string | 最终确定的制作小组 |
| `resolution` | string | 最终分辨率 |
| `video_encode` | string | 最终视频编码 |
| `video_effect` | string | 视频特效 (如 `HDR`, `Dolby Vision`) |
| `audio_encode` | string | 最终音频编码 |
| `subtitle` | string | 最终字幕语言 |
| `source` | string | 最终资源来源 |
| `platform` | string | 最终发布平台 |
| `origin_country` | string | **制片国家** (如 `日本`, `美国`) |
| `vote_average` | float | 媒体评分 |
| `year` | string | 最终年份 |
| `duration` | string | 识别耗时 |
| `filename` | string | 原始文件名 |
| `path` | string | 原始完整路径 |

## 📦 快速启动

```bash
cd anime-matcher && docker-compose up -d
```
访问 `http://localhost:8081/docs` 查看 Swagger 交互式文档。

---

## 📖 规则编写指南 (Rules Guide)

为了实现精准的识别与个性化的重命名，本项目支持三套强大的规则系统：

- [**自定义特权规则 (最高优先级)**](./docs/privileged-rules.md): 作用于识别流程最早期。命中后集数直接锁定，标题作为优先搜索候选。
- [**自定义识别词 (预处理)**](./docs/recognition-rules.md): 作用于"文件名"解析前。用于屏蔽干扰字符、纠正标题误匹配、或强制锁定特定 TMDB ID。
- [**自定义渲染词 (后处理)**](./docs/render-rules.md): 作用于"匹配结论"生成后。支持专家级的条件修正（基于 ID/季/集）、集数偏移计算、自动打标签等。

---

## 鸣谢参考项目

- [anitopy](https://github.com/igorcmoura/anitopy)
- [Symedia](https://github.com/shenxianmq/Symedia)
- [MoviePilot](https://github.com/jxxghp/MoviePilot)
