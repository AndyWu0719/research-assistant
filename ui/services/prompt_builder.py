from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ui.services.config_store import (
    AGENTS_PATH,
    CONFIGS_DIR,
    DAILY_PROFILE_PATH,
    RANKING_PROFILES_PATH,
    ROOT,
    SOURCE_POLICIES_PATH,
    SKILLS_DIR,
    resolve_quality_profile,
)
from ui.services.file_naming import (
    constraint_output_path,
    feasibility_output_path,
    paper_summary_output_path,
    sidecar_json_path,
    top10_output_path,
    topic_map_output_path,
)
from ui.services.paper_sources import parse_reference


@dataclass(slots=True)
class PromptPackage:
    skill_name: str
    title: str
    prompt: str
    expected_output: Path
    manifest_output: Path | None
    metadata: dict[str, Any]


def format_time_range(value: dict[str, Any] | str) -> str:
    if isinstance(value, str):
        return value
    label = value.get("label")
    if label:
        return label
    days = value.get("days")
    if days:
        return f"最近 {days} 天"
    return "未指定"


def format_sources(sources: list[str]) -> str:
    return "、".join(sources) if sources else "未指定"


def format_constraints(value: Any) -> str:
    if isinstance(value, str):
        return value.strip() or "无额外约束"
    if isinstance(value, dict):
        ordered = []
        for key in ("compute", "data", "time", "budget", "notes"):
            raw = str(value.get(key, "")).strip()
            if raw:
                ordered.append(f"{key}: {raw}")
        return "；".join(ordered) if ordered else "无额外约束"
    return "无额外约束"


def skill_path(skill_name: str) -> Path:
    return SKILLS_DIR / skill_name / "SKILL.md"


def common_instructions(skill_name: str) -> str:
    return "\n".join(
        [
            f"- 项目根目录: {ROOT}",
            f"- 必须遵循全局规则: {AGENTS_PATH}",
            f"- 必须阅读并复用 skill: {skill_path(skill_name)}",
            f"- 排序时必须参考: {RANKING_PROFILES_PATH}",
            f"- 来源约束必须参考: {SOURCE_POLICIES_PATH}",
            "- 所有用户可见输出默认使用中文。",
            "- 如果信息缺失或来源不稳定，要显式标注不确定性。",
            "- 不要伪造检索、下载、代码仓库或实验结论。",
        ]
    )


def top10_manifest_schema() -> str:
    return """{
  "task": "literature-scout",
  "field": "...",
  "time_range": "...",
  "sources": ["arXiv", "OpenReview"],
  "ranking_profile": "...",
  "constraints": "...",
  "top_k": 10,
  "generated_at": "...",
  "papers": [
    {
      "rank": 1,
      "title": "...",
      "paper_url": "...",
      "year": 2026,
      "venue": "arXiv / ICLR / NeurIPS ...",
      "core_contribution": "...",
      "why_relevant": "...",
      "why_priority": "...",
      "priority": "高 / 中 / 低",
      "code_url": "...",
      "dataset_url": "...",
      "project_url": "...",
      "resource_cost": "低 / 中 / 高"
    }
  ]
}"""


def paper_reader_manifest_schema() -> str:
    return """{
  "task": "paper-reader",
  "paper": {
    "title": "...",
    "paper_url": "...",
    "pdf_path": "...",
    "code_url": "...",
    "project_url": "..."
  },
  "summary_depth": "标准 / 深入 / 超详细",
  "generated_at": "...",
  "sections": {
    "one_sentence": "...",
    "method": "...",
    "experiments": "...",
    "limitations": "...",
    "diagram_text": "..."
  }
}"""


def simple_manifest_schema(task_name: str) -> str:
    return f"""{{
  "task": "{task_name}",
  "generated_at": "...",
  "summary": {{
    "title": "...",
    "ranking_profile": "...",
    "key_conclusion": "..."
  }}
}}"""


def build_literature_scout_prompt(params: dict[str, Any]) -> PromptPackage:
    field = params["field"].strip()
    ranking_profile = params["ranking_profile"]
    expected_output = top10_output_path(field, ranking_profile)
    manifest_output = sidecar_json_path(expected_output)
    time_range_text = format_time_range(params["time_range"])
    constraints_text = format_constraints(params.get("constraints"))
    prompt = f"""请使用 `literature-scout` skill 完成一次文献巡检。

执行前必须完成：
{common_instructions("literature-scout")}
- 如果显式参数缺失，可读取默认配置: {DAILY_PROFILE_PATH}

任务理解
- 目标: 为指定研究方向生成结构化 Top {params["top_k"]} 文献巡检结果。
- 研究领域: {field}
- 时间范围: {time_range_text}
- 来源范围: {format_sources(params["sources"])}
- 排序 profile: {ranking_profile}
- 自定义约束: {constraints_text}
- 返回数量: {params["top_k"]}

输出要求
1. 按 `AGENTS.md` 中的结构化骨架输出。
2. 明确说明 ranking profile、关键维度、Top 项为什么靠前、同分如何打破。
3. 结果必须写入 Markdown 文件:
   - {expected_output}
4. 同时写一个 JSON sidecar，便于本地网页读取:
   - {manifest_output}
   - JSON 结构参考:
```json
{top10_manifest_schema()}
```
5. Markdown 中必须包含 Top K 表格，至少包含这些列：
   - 排名
   - 论文
   - 核心贡献
   - 相关性原因
   - 排名原因
   - 推荐优先级
   - 开源情况
   - 资源成本
6. 每个推荐项至少回答：
   - 为什么相关
   - 为什么值得优先看
7. 如果没有公开代码或数据，要明确写 `未发现公开代码` 或 `未发现公开数据`。
8. 不要输出空壳结果；如果检索不足，要说明原因和缺口。
"""
    metadata = {
        "field": field,
        "time_range": params["time_range"],
        "sources": params["sources"],
        "ranking_profile": ranking_profile,
        "constraints": constraints_text,
        "top_k": params["top_k"],
        "expected_output": str(expected_output),
        "manifest_output": str(manifest_output),
    }
    return PromptPackage(
        skill_name="literature-scout",
        title=f"top10-{field}",
        prompt=prompt,
        expected_output=expected_output,
        manifest_output=manifest_output,
        metadata=metadata,
    )


def build_paper_reader_prompt(params: dict[str, Any]) -> PromptPackage:
    reference = parse_reference(params["paper_reference"])
    reference_slug = params.get("reference_slug") or reference.identifier or "paper"
    expected_output = paper_summary_output_path(reference_slug)
    manifest_output = sidecar_json_path(expected_output)
    prompt = f"""请使用 `paper-reader` skill 对单篇论文做结构化精读。

执行前必须完成：
{common_instructions("paper-reader")}

输入论文
- 输入对象: {params["paper_reference"]}
- 解析类型: {reference.kind}
- 规范化引用: {reference.normalized}
- 摘要深度: {params["summary_depth"]}
- 是否需要图示化总结: {"是" if params["diagram_summary"] else "否"}
- 是否优先解释实验细节: {"是" if params["focus_experiments"] else "否"}
- 若输入是网页链接且还未下载 PDF，可先使用 `paper-fetcher` skill 下载到 `outputs/pdfs/`。

输出要求
1. 用中文输出结构化总结，保留论文标题原文。
2. 结果写入:
   - Markdown: {expected_output}
   - JSON sidecar: {manifest_output}
3. Markdown 至少包含：
   - 一句话总结
   - 论文速览
   - 主要方法
   - 实验细节
   - 局限性
   - 开源地址
   - 图示化解释
4. JSON 结构参考：
```json
{paper_reader_manifest_schema()}
```
5. 如果没有公开代码、模型或数据，要明确写出来。
6. 如果证据不足，明确标注哪部分无法确认。
"""
    metadata = {
        "paper_reference": params["paper_reference"],
        "summary_depth": params["summary_depth"],
        "diagram_summary": params["diagram_summary"],
        "focus_experiments": params["focus_experiments"],
        "expected_output": str(expected_output),
        "manifest_output": str(manifest_output),
    }
    return PromptPackage(
        skill_name="paper-reader",
        title=f"paper-reader-{reference_slug}",
        prompt=prompt,
        expected_output=expected_output,
        manifest_output=manifest_output,
        metadata=metadata,
    )


def build_topic_mapper_prompt(params: dict[str, Any]) -> PromptPackage:
    expected_output = topic_map_output_path(params["topic"], params["ranking_mode"])
    manifest_output = sidecar_json_path(expected_output)
    prompt = f"""请使用 `topic-mapper` skill 生成方向论文地图。

执行前必须完成：
{common_instructions("topic-mapper")}

任务参数
- 方向描述: {params["topic"]}
- 时间窗口: {format_time_range(params["time_range"])}
- 是否跨领域扩展: {"是" if params["cross_domain"] else "否"}
- 返回数量: {params["return_count"]}
- 排序方式: {params["ranking_mode"]}

输出要求
1. 必须给出 `Tier 1 / Tier 2 / Tier 3` 三层结果。
2. 必须解释每层排序依据，以及为什么属于该层。
3. Markdown 输出路径: {expected_output}
4. JSON sidecar 输出路径: {manifest_output}
5. JSON 结构参考：
```json
{simple_manifest_schema("topic-mapper")}
```
"""
    metadata = {
        "topic": params["topic"],
        "time_range": params["time_range"],
        "cross_domain": params["cross_domain"],
        "return_count": params["return_count"],
        "ranking_mode": params["ranking_mode"],
        "expected_output": str(expected_output),
        "manifest_output": str(manifest_output),
    }
    return PromptPackage(
        skill_name="topic-mapper",
        title=f"topic-map-{params['topic']}",
        prompt=prompt,
        expected_output=expected_output,
        manifest_output=manifest_output,
        metadata=metadata,
    )


def build_idea_feasibility_prompt(params: dict[str, Any]) -> PromptPackage:
    expected_output = feasibility_output_path(params["target_field"], params["idea"])
    manifest_output = sidecar_json_path(expected_output)
    prompt = f"""请使用 `idea-feasibility` skill 评估下面这个研究想法。

执行前必须完成：
{common_instructions("idea-feasibility")}

任务参数
- 研究想法: {params["idea"]}
- 目标领域: {params["target_field"]}
- 算力预算: {params["compute_budget"]}
- 数据预算: {params["data_budget"]}
- 风险偏好: {params["risk_preference"]}
- 是否优先低成本验证: {"是" if params["prefer_low_cost_validation"] else "否"}

输出要求
1. 必须包含：相关工作、潜在创新点、撞车风险、技术风险、最小可行验证路径。
2. 要区分“值得做”“值得做但要收缩”“更像工程验证”“当前不建议优先做”。
3. Markdown 输出路径: {expected_output}
4. JSON sidecar 输出路径: {manifest_output}
5. JSON 结构参考：
```json
{simple_manifest_schema("idea-feasibility")}
```
"""
    metadata = {
        "idea": params["idea"],
        "target_field": params["target_field"],
        "compute_budget": params["compute_budget"],
        "data_budget": params["data_budget"],
        "risk_preference": params["risk_preference"],
        "prefer_low_cost_validation": params["prefer_low_cost_validation"],
        "expected_output": str(expected_output),
        "manifest_output": str(manifest_output),
    }
    return PromptPackage(
        skill_name="idea-feasibility",
        title=f"idea-feasibility-{params['target_field']}",
        prompt=prompt,
        expected_output=expected_output,
        manifest_output=manifest_output,
        metadata=metadata,
    )


def build_constraint_explorer_prompt(params: dict[str, Any]) -> PromptPackage:
    expected_output = constraint_output_path(params["field"])
    manifest_output = sidecar_json_path(expected_output)
    prompt = f"""请使用 `constraint-aware-explorer` skill 做资源受限探索。

执行前必须完成：
{common_instructions("constraint-aware-explorer")}

任务参数
- 研究领域: {params["field"]}
- 算力限制: {params["compute_limit"]}
- 数据限制: {params["data_limit"]}
- 是否优先复现: {"是" if params["prefer_reproduction"] else "否"}
- 是否优先开源: {"是" if params["prefer_open_source"] else "否"}

输出要求
1. 先做约束摘要和可行性边界判断，再给推荐方向。
2. 必须包含：适合切入的方向、参考论文、低成本路径、风险收益分析。
3. Markdown 输出路径: {expected_output}
4. JSON sidecar 输出路径: {manifest_output}
5. JSON 结构参考：
```json
{simple_manifest_schema("constraint-aware-explorer")}
```
"""
    metadata = {
        "field": params["field"],
        "compute_limit": params["compute_limit"],
        "data_limit": params["data_limit"],
        "prefer_reproduction": params["prefer_reproduction"],
        "prefer_open_source": params["prefer_open_source"],
        "expected_output": str(expected_output),
        "manifest_output": str(manifest_output),
    }
    return PromptPackage(
        skill_name="constraint-aware-explorer",
        title=f"constraint-{params['field']}",
        prompt=prompt,
        expected_output=expected_output,
        manifest_output=manifest_output,
        metadata=metadata,
    )


def build_daily_automation_prompt(config: dict[str, Any]) -> str:
    field = config["field"]
    time_of_day = config.get("schedule", {}).get("time_of_day", "09:00")
    quality_profile = config.get("quality_profile", "balanced")
    quality_mapping = resolve_quality_profile(quality_profile, task_type="automation")
    return f"""请在项目目录 `{ROOT}` 中执行一次每日文献巡检。

要求：
1. 读取 `{AGENTS_PATH}`。
2. 读取 `{DAILY_PROFILE_PATH}`，将其作为默认参数源。
3. 使用 `literature-scout` skill。
4. 同时参考：
   - `{RANKING_PROFILES_PATH}`
   - `{SOURCE_POLICIES_PATH}`
5. 结果写入 `outputs/daily_top10/`，文件名遵循 `YYYY-MM-DD-<field>-<ranking_profile>.md`。
6. 结果同时写一个同名 `.json` sidecar，便于本地网页读取。
7. 如果 `{CONFIGS_DIR / "interesting_papers.json"}` 中存在已标记论文，且 `configs/automations/daily_top10.yaml` 中 `auto_download_interesting=true`，再用 `paper-fetcher` 为未下载项补抓 PDF 到 `outputs/pdfs/`。
8. 所有用户可见输出默认中文，不要伪造检索结果。
9. 自动化配置中的质量档位是推荐值；Codex app automation 的实际 model / reasoning effort 仍需在创建 automation 时手动选择，或由本地默认配置决定。

当前自动化摘要
- 任务名称: {config.get("task_name", "每日 Top10 文献巡检")}
- 研究领域: {field}
- 时间范围: {format_time_range(config["time_range"])}
- 来源范围: {format_sources(config["sources"])}
- 排序 profile: {config["ranking_profile"]}
- 质量档位: {quality_profile}
- 推荐模型: {quality_mapping["model"]}
- 推荐 reasoning effort: {quality_mapping["reasoning_effort"]}
- Top K: {config["top_k"]}
- 每日运行时间: {time_of_day}
"""
