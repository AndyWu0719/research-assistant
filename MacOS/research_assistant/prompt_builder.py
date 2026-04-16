from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from research_assistant.config_store import (
    AGENTS_PATH,
    CONFIGS_DIR,
    RANKING_PROFILES_PATH,
    ROOT,
    SCAN_DEFAULTS_PATH,
    SOURCE_POLICIES_PATH,
    SKILLS_DIR,
    current_automation_config_path,
    load_user_preferences,
    resolve_quality_profile,
)
from research_assistant.file_naming import (
    constraint_output_path,
    feasibility_output_path,
    literature_scan_output_path,
    paper_summary_output_path_for_language,
    sidecar_json_path,
    topic_map_output_path,
)
from research_assistant.language import language_display_name, normalize_language, prompt_language_instruction
from research_assistant.paper_sources import parse_reference
from research_assistant.ui_text import bool_label, is_english, risk_preference_label, summary_depth_label, time_range_label


@dataclass(slots=True)
class PromptPackage:
    skill_name: str
    title: str
    prompt: str
    expected_output: Path
    manifest_output: Path | None
    metadata: dict[str, Any]


def format_time_range(value: dict[str, Any] | str, language: str) -> str:
    return time_range_label(value, language)


def format_sources(sources: list[str], language: str) -> str:
    if not sources:
        return "Not specified" if is_english(language) else "未指定"
    return ", ".join(sources) if is_english(language) else "、".join(sources)


def format_constraints(value: Any, language: str) -> str:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or ("No additional constraints" if is_english(language) else "无额外约束")
    if isinstance(value, dict):
        key_labels = {
            "compute": "Compute" if is_english(language) else "compute",
            "data": "Data" if is_english(language) else "data",
            "time": "Time" if is_english(language) else "time",
            "budget": "Budget" if is_english(language) else "budget",
            "notes": "Notes" if is_english(language) else "notes",
        }
        ordered = []
        for key in ("compute", "data", "time", "budget", "notes"):
            raw = str(value.get(key, "")).strip()
            if raw:
                ordered.append(f"{key_labels[key]}: {raw}")
        if ordered:
            return "; ".join(ordered) if is_english(language) else "；".join(ordered)
    return "No additional constraints" if is_english(language) else "无额外约束"


def skill_path(skill_name: str) -> Path:
    return SKILLS_DIR / skill_name / "SKILL.md"


def resolve_task_language(params: dict[str, Any]) -> str:
    return normalize_language(params.get("language") or load_user_preferences().get("language"))


def common_instructions(skill_name: str, language: str) -> str:
    if is_english(language):
        return "\n".join(
            [
                f"- Project root: {ROOT}",
                f"- You must follow the global rules in: {AGENTS_PATH}",
                f"- You must read and reuse the skill: {skill_path(skill_name)}",
                f"- Ranking decisions must reference: {RANKING_PROFILES_PATH}",
                f"- Source restrictions must reference: {SOURCE_POLICIES_PATH}",
                f"- Output language: {language_display_name(language)}",
                f"- {prompt_language_instruction(language)}",
                "- If information is missing or the sources are unstable, explicitly mark the uncertainty.",
                "- Do not fabricate retrieval results, downloads, repositories, or experimental conclusions.",
            ]
        )
    return "\n".join(
        [
            f"- 项目根目录: {ROOT}",
            f"- 必须遵循全局规则: {AGENTS_PATH}",
            f"- 必须阅读并复用 skill: {skill_path(skill_name)}",
            f"- 排序时必须参考: {RANKING_PROFILES_PATH}",
            f"- 来源约束必须参考: {SOURCE_POLICIES_PATH}",
            f"- 输出语言: {language_display_name(language)}",
            f"- {prompt_language_instruction(language)}",
            "- 如果信息缺失或来源不稳定，要显式标注不确定性。",
            "- 不要伪造检索、下载、代码仓库或实验结论。",
        ]
    )


def literature_scout_manifest_schema(language: str) -> str:
    priority = "high / medium / low" if is_english(language) else "高 / 中 / 低"
    resource_cost = "low / medium / high" if is_english(language) else "低 / 中 / 高"
    return f"""{{
  "task": "literature-scout",
  "field": "...",
  "time_range": "...",
  "sources": ["arXiv", "OpenReview"],
  "ranking_profile": "...",
  "constraints": "...",
  "top_k": 10,
  "generated_at": "...",
  "papers": [
    {{
      "rank": 1,
      "title": "...",
      "paper_url": "...",
      "year": 2026,
      "venue": "arXiv / ICLR / NeurIPS ...",
      "core_contribution": "...",
      "why_relevant": "...",
      "why_priority": "...",
      "priority": "{priority}",
      "code_url": "...",
      "dataset_url": "...",
      "project_url": "...",
      "resource_cost": "{resource_cost}"
    }}
  ]
}}"""


def paper_reader_manifest_schema(language: str) -> str:
    summary_depth = "standard / deep / very_deep" if is_english(language) else "标准 / 深入 / 超详细"
    return f"""{{
  "task": "paper-reader",
  "paper": {{
    "title": "...",
    "paper_url": "...",
    "pdf_path": "...",
    "code_url": "...",
    "project_url": "..."
  }},
  "pdf_extraction": {{
    "status": "success / error",
    "quality": "good / mixed / poor",
    "text_path": "...",
    "warnings": ["..."]
  }},
  "summary_depth": "{summary_depth}",
  "generated_at": "...",
  "sections": {{
    "one_sentence": "...",
    "method": "...",
    "experiments": "...",
    "limitations": "...",
    "diagram_text": "..."
  }}
}}"""


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
    language = resolve_task_language(params)
    expected_output = literature_scan_output_path(field, ranking_profile)
    manifest_output = sidecar_json_path(expected_output)
    time_range_text = format_time_range(params["time_range"], language)
    constraints_text = format_constraints(params.get("constraints"), language)
    history_exclusion_path = str(params.get("history_exclusion_path") or "").strip()
    history_exclusion_count = int(params.get("history_exclusion_count") or 0)
    history_requirements = ""
    if history_exclusion_path and history_exclusion_count > 0:
        if is_english(language):
            history_requirements = f"""
History-Based Exclusions
- You must read the historical exclusion file: {history_exclusion_path}
- Historical paper count to exclude: {history_exclusion_count}
- Do not include any paper whose title or `paper_url` matches that history file.
- If the remaining candidate pool is too small after exclusion, explicitly say so instead of repeating old papers.
"""
        else:
            history_requirements = f"""
历史去重约束
- 必须读取历史排除文件：{history_exclusion_path}
- 需要排除的历史论文数：{history_exclusion_count}
- 标题或 `paper_url` 命中该历史文件的论文，不得再次进入本次 Top K。
- 如果排除后候选池明显不足，要明确写出缺口，不要用旧论文补位。
"""

    if is_english(language):
        prompt = f"""Use the `literature-scout` skill to complete a literature scan.

Before execution, you must finish the following:
{common_instructions("literature-scout", language)}
- If explicit parameters are missing, you may read the default config from: {SCAN_DEFAULTS_PATH}

Task Understanding
- Goal: generate a structured literature scan for the requested research area.
- Research area: {field}
- Time range: {time_range_text}
- Sources: {format_sources(params["sources"], language)}
- Ranking profile: {ranking_profile}
- Output language: {language_display_name(language)}
- Custom constraints: {constraints_text}
- Number of returned items: {params["top_k"]}
{history_requirements}

Output Requirements
1. Follow the structured skeleton described in `AGENTS.md`.
2. Explain the ranking profile, key dimensions, why the top items rank first, and how ties are broken.
3. Write the final Markdown file to:
   - {expected_output}
4. Also write a JSON sidecar for the local web app:
   - {manifest_output}
   - Use this JSON structure as a reference:
```json
{literature_scout_manifest_schema(language)}
```
5. The Markdown must include a Top K table with at least these columns:
   - Rank
   - Paper
   - Core contribution
   - Why relevant
   - Why prioritized
   - Priority
   - Open-source status
   - Resource cost
6. Every recommended item must answer:
   - Why it is relevant
   - Why it deserves priority
7. If no public code or data is available, explicitly write `No public code found` or `No public data found`.
8. Do not produce a hollow result. If retrieval is insufficient, explain the gap and failure mode.
"""
    else:
        prompt = f"""请使用 `literature-scout` skill 完成一次文献巡检。

执行前必须完成：
{common_instructions("literature-scout", language)}
- 如果显式参数缺失，可读取默认配置: {SCAN_DEFAULTS_PATH}

任务理解
- 目标: 为指定研究方向生成结构化 Top {params["top_k"]} 文献巡检结果。
- 研究领域: {field}
- 时间范围: {time_range_text}
- 来源范围: {format_sources(params["sources"], language)}
- 排序 profile: {ranking_profile}
- 输出语言: {language_display_name(language)}
- 自定义约束: {constraints_text}
- 返回数量: {params["top_k"]}
{history_requirements}

输出要求
1. 按 `AGENTS.md` 中的结构化骨架输出。
2. 明确说明 ranking profile、关键维度、Top 项为什么靠前、同分如何打破。
3. 结果必须写入 Markdown 文件:
   - {expected_output}
4. 同时写一个 JSON sidecar，便于本地网页读取:
   - {manifest_output}
   - JSON 结构参考:
```json
{literature_scout_manifest_schema(language)}
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
        "language": language,
        "history_exclusion_path": history_exclusion_path,
        "history_exclusion_count": history_exclusion_count,
        "expected_output": str(expected_output),
        "manifest_output": str(manifest_output),
    }
    return PromptPackage(
        skill_name="literature-scout",
        title=f"literature-scan-{field}",
        prompt=prompt,
        expected_output=expected_output,
        manifest_output=manifest_output,
        metadata=metadata,
    )


def build_paper_reader_prompt(params: dict[str, Any]) -> PromptPackage:
    reference = parse_reference(params["paper_reference"])
    reference_slug = params.get("reference_slug") or reference.identifier or "paper"
    language = resolve_task_language(params)
    expected_output = paper_summary_output_path_for_language(reference_slug, language)
    manifest_output = sidecar_json_path(expected_output)
    extraction = params.get("pdf_extraction") or {}
    extraction_lines = [
        f"- {'Extraction status' if is_english(language) else '抽取状态'}: {extraction.get('status', 'not-available')}",
        f"- {'Extraction quality' if is_english(language) else '抽取质量'}: {extraction.get('quality', 'unknown')}",
        f"- {'Cleaned text path' if is_english(language) else '清洗文本路径'}: {extraction.get('text_path', 'Not provided' if is_english(language) else '未提供')}",
        f"- {'Extraction sidecar' if is_english(language) else '抽取质量 sidecar'}: {extraction.get('sidecar_path', 'Not provided' if is_english(language) else '未提供')}",
    ]
    warnings = extraction.get("warnings") or []
    if warnings:
        extraction_lines.extend(f"  - {item}" for item in warnings[:4])

    if is_english(language):
        prompt = f"""Use the `paper-reader` skill to produce a structured deep read for a single paper.

Before execution, you must finish the following:
{common_instructions("paper-reader", language)}

Paper Input
- Input object: {params["paper_reference"]}
- Parsed type: {reference.kind}
- Normalized reference: {reference.normalized}
- Output language: {language_display_name(language)}
- Summary depth: {summary_depth_label(params["summary_depth"], language)}
- Need diagram-style explanation: {bool_label(params["diagram_summary"], language)}
- Prioritize experimental details: {bool_label(params["focus_experiments"], language)}
- If the input is a web link and the PDF has not been downloaded yet, you may first use `paper-fetcher` to download it into `outputs/pdfs/`.

PDF Extraction Context
{chr(10).join(extraction_lines)}

Output Requirements
1. Produce a structured summary in {language_display_name(language)} while keeping the original paper title.
2. Write the outputs to:
   - Markdown: {expected_output}
   - JSON sidecar: {manifest_output}
3. The Markdown must include at least:
   - One-sentence summary
   - Paper overview
   - Main method
   - Experimental details
   - Limitations
   - Open resources
   - Diagram-style explanation
4. JSON structure reference:
```json
{paper_reader_manifest_schema(language)}
```
5. If code, model weights, or data are not publicly available, say so explicitly.
6. If evidence is insufficient, clearly mark which parts cannot be confirmed.
7. If a cleaned local text file is provided, read that file first before summarizing. Tables, formulas, and experimental details must only be described from visible evidence.
8. If PDF extraction quality is `mixed` or `poor`, explicitly warn about uncertainty in the result and do not fill in missing tables, formulas, or experiment details.
"""
    else:
        prompt = f"""请使用 `paper-reader` skill 对单篇论文做结构化精读。

执行前必须完成：
{common_instructions("paper-reader", language)}

输入论文
- 输入对象: {params["paper_reference"]}
- 解析类型: {reference.kind}
- 规范化引用: {reference.normalized}
- 输出语言: {language_display_name(language)}
- 摘要深度: {summary_depth_label(params["summary_depth"], language)}
- 是否需要图示化总结: {bool_label(params["diagram_summary"], language)}
- 是否优先解释实验细节: {bool_label(params["focus_experiments"], language)}
- 若输入是网页链接且还未下载 PDF，可先使用 `paper-fetcher` skill 下载到 `outputs/pdfs/`。

PDF 文本抽取上下文
{chr(10).join(extraction_lines)}

输出要求
1. 使用 {language_display_name(language)} 输出结构化总结，保留论文标题原文。
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
{paper_reader_manifest_schema(language)}
```
5. 如果没有公开代码、模型或数据，要明确写出来。
6. 如果证据不足，明确标注哪部分无法确认。
7. 若已提供本地清洗文本，先读取该文本再总结；表格、公式、实验细节只能基于可见证据描述。
8. 若 PDF 抽取质量为 `mixed` 或 `poor`，必须在结果中显式提醒不确定性，且不要补全缺失表格、公式或实验细节。
"""

    metadata = {
        "paper_reference": params["paper_reference"],
        "summary_depth": summary_depth_label(params["summary_depth"], language),
        "diagram_summary": params["diagram_summary"],
        "focus_experiments": params["focus_experiments"],
        "language": language,
        "pdf_extraction": extraction,
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
    language = resolve_task_language(params)
    expected_output = topic_map_output_path(params["topic"], params["ranking_mode"])
    manifest_output = sidecar_json_path(expected_output)

    if is_english(language):
        prompt = f"""Use the `topic-mapper` skill to generate a paper map for the target direction.

Before execution, you must finish the following:
{common_instructions("topic-mapper", language)}

Task Parameters
- Topic description: {params["topic"]}
- Time window: {format_time_range(params["time_range"], language)}
- Expand across neighboring domains: {bool_label(params["cross_domain"], language)}
- Number of returned items: {params["return_count"]}
- Ranking mode: {params["ranking_mode"]}
- Output language: {language_display_name(language)}

Output Requirements
1. You must provide a three-tier result: `Tier 1 / Tier 2 / Tier 3`.
2. Explain the ranking rationale for each tier and why each item belongs there.
3. Markdown output path: {expected_output}
4. JSON sidecar output path: {manifest_output}
5. JSON structure reference:
```json
{simple_manifest_schema("topic-mapper")}
```
"""
    else:
        prompt = f"""请使用 `topic-mapper` skill 生成方向论文地图。

执行前必须完成：
{common_instructions("topic-mapper", language)}

任务参数
- 方向描述: {params["topic"]}
- 时间窗口: {format_time_range(params["time_range"], language)}
- 是否跨领域扩展: {bool_label(params["cross_domain"], language)}
- 返回数量: {params["return_count"]}
- 排序方式: {params["ranking_mode"]}
- 输出语言: {language_display_name(language)}

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
        "language": language,
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
    language = resolve_task_language(params)
    expected_output = feasibility_output_path(params["target_field"], params["idea"])
    manifest_output = sidecar_json_path(expected_output)

    if is_english(language):
        prompt = f"""Use the `idea-feasibility` skill to evaluate the following research idea.

Before execution, you must finish the following:
{common_instructions("idea-feasibility", language)}

Task Parameters
- Research idea: {params["idea"]}
- Target field: {params["target_field"]}
- Compute budget: {params["compute_budget"]}
- Data budget: {params["data_budget"]}
- Risk preference: {risk_preference_label(params["risk_preference"], language)}
- Prefer low-cost validation: {bool_label(params["prefer_low_cost_validation"], language)}
- Output language: {language_display_name(language)}

Output Requirements
1. You must include: related work, potential novelty, collision risk, technical risk, and a minimum viable validation path.
2. Distinguish clearly among: worth doing, worth doing but should be narrowed, mostly an engineering validation, and not recommended as a priority right now.
3. Markdown output path: {expected_output}
4. JSON sidecar output path: {manifest_output}
5. JSON structure reference:
```json
{simple_manifest_schema("idea-feasibility")}
```
"""
    else:
        prompt = f"""请使用 `idea-feasibility` skill 评估下面这个研究想法。

执行前必须完成：
{common_instructions("idea-feasibility", language)}

任务参数
- 研究想法: {params["idea"]}
- 目标领域: {params["target_field"]}
- 算力预算: {params["compute_budget"]}
- 数据预算: {params["data_budget"]}
- 风险偏好: {risk_preference_label(params["risk_preference"], language)}
- 是否优先低成本验证: {bool_label(params["prefer_low_cost_validation"], language)}
- 输出语言: {language_display_name(language)}

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
        "risk_preference": risk_preference_label(params["risk_preference"], language),
        "prefer_low_cost_validation": params["prefer_low_cost_validation"],
        "language": language,
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
    language = resolve_task_language(params)
    expected_output = constraint_output_path(params["field"])
    manifest_output = sidecar_json_path(expected_output)

    if is_english(language):
        prompt = f"""Use the `constraint-aware-explorer` skill for a resource-constrained exploration.

Before execution, you must finish the following:
{common_instructions("constraint-aware-explorer", language)}

Task Parameters
- Research field: {params["field"]}
- Compute limit: {params["compute_limit"]}
- Data limit: {params["data_limit"]}
- Prefer reproducible work: {bool_label(params["prefer_reproduction"], language)}
- Prefer open-source work: {bool_label(params["prefer_open_source"], language)}
- Output language: {language_display_name(language)}

Output Requirements
1. Start with a constraint summary and feasible-boundary judgment before making recommendations.
2. You must include: promising directions, reference papers, low-cost paths, and risk-vs-return analysis.
3. Markdown output path: {expected_output}
4. JSON sidecar output path: {manifest_output}
5. JSON structure reference:
```json
{simple_manifest_schema("constraint-aware-explorer")}
```
"""
    else:
        prompt = f"""请使用 `constraint-aware-explorer` skill 做资源受限探索。

执行前必须完成：
{common_instructions("constraint-aware-explorer", language)}

任务参数
- 研究领域: {params["field"]}
- 算力限制: {params["compute_limit"]}
- 数据限制: {params["data_limit"]}
- 是否优先复现: {bool_label(params["prefer_reproduction"], language)}
- 是否优先开源: {bool_label(params["prefer_open_source"], language)}
- 输出语言: {language_display_name(language)}

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
        "language": language,
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
    language = resolve_task_language(config)
    automation_path = current_automation_config_path()
    exclude_previous = bool(config.get("exclude_previous_output_papers", True))
    if is_english(language):
        return f"""Execute a local daily literature scan in the project directory `{ROOT}`.

Requirements:
1. Read `{AGENTS_PATH}`.
2. Read `{SCAN_DEFAULTS_PATH}` as the default parameter source.
3. Use the `literature-scout` skill.
4. Also reference:
   - `{RANKING_PROFILES_PATH}`
   - `{SOURCE_POLICIES_PATH}`
5. Write the result to `outputs/literature_scans/`, with filenames following `YYYY-MM-DD-<field>-<ranking_profile>.md`.
6. Also write a same-name `.json` sidecar for the local web app.
7. If `{CONFIGS_DIR / "interesting_papers.json"}` contains marked papers and `auto_download_interesting=true` in `{automation_path}`, use `paper-fetcher` to download missing PDFs into `outputs/pdfs/`.
8. If `exclude_previous_output_papers=true` in `{automation_path}`, read the generated history file under `{CONFIGS_DIR / "automations" / "history"}` and do not repeat previously output papers in the new Top K.
9. {prompt_language_instruction(language)}
10. This automation is intended for the local scheduler and `codex exec`, not for Codex app automation setup.

Current Automation Summary
- Task name: {config.get("task_name", "Daily Literature Scan")}
- Config file: {automation_path}
- Research field: {field}
- Time range: {format_time_range(config["time_range"], language)}
- Sources: {format_sources(config["sources"], language)}
- Ranking profile: {config["ranking_profile"]}
- Output language: {language_display_name(language)}
- Quality profile: {quality_profile}
- Recommended model: {quality_mapping["model"]}
- Recommended reasoning effort: {quality_mapping["reasoning_effort"]}
- Top K: {config["top_k"]}
- Daily runtime: {time_of_day}
- History dedup enabled: {exclude_previous}
"""

    return f"""请在项目目录 `{ROOT}` 中执行一次本地每日文献巡检。

要求：
1. 读取 `{AGENTS_PATH}`。
2. 读取 `{SCAN_DEFAULTS_PATH}`，将其作为默认参数源。
3. 使用 `literature-scout` skill。
4. 同时参考：
   - `{RANKING_PROFILES_PATH}`
   - `{SOURCE_POLICIES_PATH}`
5. 结果写入 `outputs/literature_scans/`，文件名遵循 `YYYY-MM-DD-<field>-<ranking_profile>.md`。
6. 结果同时写一个同名 `.json` sidecar，便于本地网页读取。
7. 如果 `{CONFIGS_DIR / "interesting_papers.json"}` 中存在已标记论文，且 `{automation_path}` 中 `auto_download_interesting=true`，再用 `paper-fetcher` 为未下载项补抓 PDF 到 `outputs/pdfs/`。
8. 如果 `{automation_path}` 中 `exclude_previous_output_papers=true`，则要读取 `{CONFIGS_DIR / "automations" / "history"}` 下生成的历史文件，避免把之前每日输出过的论文再次放入新的 Top K。
9. {prompt_language_instruction(language)}
10. 该自动化默认面向本地调度器和 `codex exec`，不依赖 Codex app Automation。

当前自动化摘要
- 任务名称: {config.get("task_name", "每日文献巡检")}
- 配置文件: {automation_path}
- 研究领域: {field}
- 时间范围: {format_time_range(config["time_range"], language)}
- 来源范围: {format_sources(config["sources"], language)}
- 排序 profile: {config["ranking_profile"]}
- 输出语言: {language_display_name(language)}
- 质量档位: {quality_profile}
- 推荐模型: {quality_mapping["model"]}
- 推荐 reasoning effort: {quality_mapping["reasoning_effort"]}
- Top K: {config["top_k"]}
- 每日运行时间: {time_of_day}
- 历史去重: {exclude_previous}
"""
