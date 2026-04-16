---
name: literature-scout
description: 当用户要按领域、时间范围、排序偏好生成一份可执行的文献巡检列表，或要快速完成某个方向的论文初筛与综述式摸底时使用；输出结构化论文清单、排序依据、图示和尽可能完整的论文/代码链接。
---

# Literature Scout

## 何时使用

- 用户要“某方向必读论文”“最近几年 Top papers”“这个子领域先看哪些论文”。
- 用户已经给出领域、任务边界、时间范围或排序偏好。
- 用户需要的是可执行的 Top K 清单，而不是长篇散乱罗列。
- 用户希望把结果自动落盘为每日榜单。

## 显式输入参数

- `field`：领域、任务或子方向定义
- `time_range`：时间范围，例如最近 7 天、最近 30 天、近 3 年
- `sources`：检索来源，例如 `arXiv`、`OpenReview`
- `ranking_profile`：`balanced-default`、`trend-focused`、`resource-constrained` 或用户自定义混合
- `constraints`：算力、数据、时间、预算、团队能力等现实约束

## 默认配置读取

- 如果用户没有显式传入上述参数，则读取 [configs/scan_defaults.yaml](/Users/andywu/Documents/codex_workplace/projects/research-assistant/configs/scan_defaults.yaml)。
- 默认配置文件现为 [configs/scan_defaults.yaml](/Users/andywu/Documents/codex_workplace/projects/research-assistant/configs/scan_defaults.yaml)。
- 参数优先级：
  1. 用户显式传入
  2. `configs/scan_defaults.yaml`
  3. 内部兜底逻辑
- 如果 `ranking_profile` 缺失：
  - 有明显约束时优先 `resource-constrained`
  - 关注每日新趋势时优先 `trend-focused`
  - 否则使用 `balanced-default`

## 工作流

1. 合并参数，形成最终执行配置：
   - `field`
   - `time_range`
   - `sources`
   - `ranking_profile`
   - `constraints`
2. 先把用户问题缩成一个明确的检索目标，并补全必要同义词。
3. 如果用户给了约束，先总结约束并判断哪些论文“看起来强但实际上不适合”。
4. 构造候选论文池：
   - 默认覆盖近 3-5 年
   - 如需研究脉络，补入少量奠基或转折论文
5. 读取 [configs/ranking_profiles.md](/Users/andywu/Documents/codex_workplace/projects/research-assistant/configs/ranking_profiles.md)，选择合适的排序画像。
6. 压缩为 Top K，每篇只保留高价值信息：
   - 做了什么
   - 为什么相关
   - 为什么排在这个位置
7. 尽量补齐论文链接、官方代码、复现仓库、数据集或项目主页。
8. 能图示就图示，优先给主题树、时间线或“先读后读”阅读路径图。
9. 将输出写入 `outputs/literature_scans/YYYY-MM-DD-<field>-<ranking_profile>.md`。
10. 如果调用来自本地网页，且 prompt 明确要求写 JSON sidecar，则同步写入同名 `.json` 文件。

## 输出要求

输出至少包含以下部分：

1. `任务定义`
2. `检索范围`
3. `排序依据`
4. `Top K 论文表`
5. `图示`
6. `先读哪几篇`

建议表格列：

| 列名 | 含义 |
| --- | --- |
| 排名 | 1-10 |
| 论文 | 标题、年份、会议/期刊 |
| 核心贡献 | 一句话概括 |
| 相关性原因 | 为什么和用户问题匹配 |
| 排名原因 | 为什么比上下项更靠前或更靠后 |
| 开源情况 | 论文、代码、数据、项目页 |
| 资源成本 | 低 / 中 / 高，必要时给出原因 |

## 输出落盘规则

- 输出文件必须写入：
  - `outputs/literature_scans/YYYY-MM-DD-<field>-<ranking_profile>.md`
- 如果 prompt 明确要求结构化 sidecar，则同步写：
  - `outputs/literature_scans/YYYY-MM-DD-<field>-<ranking_profile>.json`
- `YYYY-MM-DD` 使用执行当天日期。
- `<field>` 应转换为适合文件名的短 slug，例如：
  - `multimodal large language models` -> `multimodal-large-language-models`
- `ranking_profile` 直接使用配置名，例如：
  - `trend-focused`
  - `resource-constrained`
- 文件开头建议包含一段元信息摘要：
  - `field`
  - `time_range`
  - `sources`
  - `ranking_profile`
  - `constraints`
  - `generated_at`

## 排序规则

- 当用户和 `configs/scan_defaults.yaml` 都未指定偏好时，默认使用 `balanced-default`。
- 用户强调“最新热点”“最近风向”时，优先 `trend-focused`。
- 用户给出显存、算力、数据、时间等约束时，优先 `resource-constrained`。
- 不得只写“综合排序”，必须解释关键维度和 Top 项靠前原因。

## 质量要求

- 避免把同一论文的会议版、期刊版、arXiv 版重复列入同一份巡检结果。
- 避免只因为热度高就推荐和用户问题弱相关的论文。
- 范围过宽时，先按子方向切块，再给总榜。
- 没找到公开代码时，明确写 `未发现公开代码`。
- `sources` 里没有的来源，不应混入主榜单，除非单独注明为补充项。
- 每日自动运行时，优先保证榜单稳定可读，而不是盲目追求覆盖极宽。

## 通用要求

- 默认使用中文输出。
- 解释尽量结构化、清晰、易理解。
- 能图示就图示。
- 能给开源地址就给开源地址。
- 用户给出约束时，优先做约束感知分析。
