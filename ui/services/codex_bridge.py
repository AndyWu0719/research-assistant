from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

from ui.services.config_store import OUTPUTS_DIR, ROOT, ensure_project_layout, load_user_preferences, now_iso, resolve_quality_profile
from ui.services.file_naming import prompt_request_path
from ui.services.language import normalize_language
from ui.services.pdf_extractor import extract_pdf_text
from ui.services.paper_sources import parse_reference
from ui.services.prompt_builder import (
    PromptPackage,
    build_constraint_explorer_prompt,
    build_idea_feasibility_prompt,
    build_literature_scout_prompt,
    build_paper_reader_prompt,
    build_topic_mapper_prompt,
)
from ui.services.ui_text import is_english


PAPER_FETCHER_SCRIPT = ROOT / "skills" / "paper-fetcher" / "scripts" / "download_paper.py"
CODEX_EXEC_RESULT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "status": {
            "type": "string",
            "enum": ["success", "partial", "error"],
        },
        "summary": {"type": "string"},
        "written_files": {
            "type": "array",
            "items": {"type": "string"},
        },
        "notes": {
            "type": "array",
            "items": {"type": "string"},
        },
        "error": {
            "type": ["string", "null"],
        },
    },
    "required": ["status", "summary", "written_files", "notes", "error"],
}
TASK_LABELS = {
    "paper_fetcher": {"zh-CN": "PDF 下载", "en-US": "PDF Download"},
    "literature_scout": {"zh-CN": "Top10 文献巡检", "en-US": "Top 10 Literature Scan"},
    "paper_reader": {"zh-CN": "单篇论文精读", "en-US": "Paper Deep Read"},
    "topic_mapper": {"zh-CN": "方向论文地图", "en-US": "Topic Map"},
    "idea_feasibility": {"zh-CN": "想法可行性分析", "en-US": "Idea Feasibility"},
    "constraint_explorer": {"zh-CN": "资源受限探索", "en-US": "Constraint Explorer"},
}
_CODEX_STATUS_CACHE: dict[str, CodexCLIStatus] = {}


@dataclass(slots=True)
class CodexCLIStatus:
    available: bool
    executable: str | None
    version: str | None
    login_ok: bool
    login_mode: str | None
    can_execute: bool
    message: str
    issues: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class QualityProfileSelection:
    name: str
    label: str
    description: str
    model: str
    reasoning_effort: str
    web_execution_control: str
    automation_control: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class BridgeResponse:
    task_type: str
    status: str
    mode: str
    message: str
    quality_profile: str
    model: str | None = None
    reasoning_effort: str | None = None
    control_level: str | None = None
    prompt_request_path: Path | None = None
    expected_output_path: Path | None = None
    manifest_path: Path | None = None
    output_paths: dict[str, str] = field(default_factory=dict)
    error: str | None = None
    payload: dict[str, Any] | None = None
    prompt_text: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        for key in ("prompt_request_path", "expected_output_path", "manifest_path"):
            value = payload.get(key)
            if value:
                payload[key] = str(value)
        payload["prompt_text"] = None
        return payload


@dataclass(slots=True)
class LiteratureScoutInput:
    field: str
    time_range: dict[str, Any]
    sources: list[str]
    ranking_profile: str
    constraints: Any
    top_k: int
    quality_profile: str | None = None
    language: str | None = None


@dataclass(slots=True)
class PaperReaderInput:
    paper_reference: str
    summary_depth: str
    diagram_summary: bool
    focus_experiments: bool
    auto_fetch_pdf: bool = False
    quality_profile: str | None = None
    reference_slug: str | None = None
    language: str | None = None


@dataclass(slots=True)
class TopicMapperInput:
    topic: str
    time_range: dict[str, Any]
    cross_domain: bool
    return_count: int
    ranking_mode: str
    quality_profile: str | None = None
    language: str | None = None


@dataclass(slots=True)
class IdeaFeasibilityInput:
    idea: str
    target_field: str
    compute_budget: str
    data_budget: str
    risk_preference: str
    prefer_low_cost_validation: bool
    quality_profile: str | None = None
    language: str | None = None


@dataclass(slots=True)
class ConstraintExplorerInput:
    field: str
    compute_limit: str
    data_limit: str
    prefer_reproduction: bool
    prefer_open_source: bool
    quality_profile: str | None = None
    language: str | None = None


@dataclass(slots=True)
class PaperFetcherInput:
    reference: str
    output_dir: str | Path | None = None
    filename: str | None = None
    force: bool = False
    resolve_only: bool = False
    quality_profile: str | None = None
    language: str | None = None


def _resolve_language(language: str | None = None) -> str:
    return normalize_language(language or load_user_preferences().get("language"))


def _task_label(task_type: str, language: str | None = None) -> str:
    lang = _resolve_language(language)
    return TASK_LABELS.get(task_type, {}).get(lang, task_type)


def _join_items(items: list[str], language: str) -> str:
    return "; ".join(items) if is_english(language) else "；".join(items)


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def _save_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _trim_text(value: str, limit: int = 4000) -> str:
    if len(value) <= limit:
        return value
    return f"{value[:limit]}...(truncated)"


def _parse_process_output(process: subprocess.CompletedProcess[str]) -> dict[str, Any]:
    stdout = process.stdout.strip()
    if not stdout:
        return {}
    try:
        return json.loads(stdout)
    except json.JSONDecodeError:
        return {"raw_stdout": stdout}


def _quality_selection(task_type: str, requested: str | None) -> QualityProfileSelection:
    raw = resolve_quality_profile(requested, task_type=task_type)
    return QualityProfileSelection(
        name=raw["name"],
        label=raw.get("label", raw["name"]),
        description=raw.get("description", ""),
        model=raw["model"],
        reasoning_effort=raw["reasoning_effort"],
        web_execution_control=raw.get("web_execution_control", "exact-cli-override"),
        automation_control=raw.get("automation_control", "recommended-only"),
    )


def detect_codex_cli(refresh: bool = False, language: str | None = None) -> CodexCLIStatus:
    lang = _resolve_language(language)
    if lang in _CODEX_STATUS_CACHE and not refresh:
        return _CODEX_STATUS_CACHE[lang]

    executable = shutil.which("codex")
    if not executable:
        _CODEX_STATUS_CACHE[lang] = CodexCLIStatus(
            available=False,
            executable=None,
            version=None,
            login_ok=False,
            login_mode=None,
            can_execute=False,
            message="`codex` command was not found." if is_english(lang) else "未检测到 `codex` 命令。",
            issues=["Codex CLI is not installed."] if is_english(lang) else ["未安装 Codex CLI。"],
            notes=[
                "The web app can still handle PDF downloads and config management, but research pages will fall back to manual bridging."
                if is_english(lang)
                else "网页仍可使用 PDF 下载和配置管理，但研究类页面会退回手动桥接。"
            ],
        )
        return _CODEX_STATUS_CACHE[lang]

    version = None
    issues: list[str] = []
    notes = [
        "Codex CLI does not need a long-running background service. The web app will call `codex exec` on demand."
        if is_english(lang)
        else "Codex CLI 不需要常驻后台进程；网页会按需调用 `codex exec`。"
    ]
    try:
        version_process = subprocess.run(
            ["codex", "--version"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        version = (version_process.stdout or version_process.stderr).strip() or None
    except OSError as exc:
        issues.append(
            f"Failed to run `codex --version`: {exc}"
            if is_english(lang)
            else f"无法执行 `codex --version`：{exc}"
        )

    login_ok = False
    login_mode = None
    try:
        login_process = subprocess.run(
            ["codex", "login", "status"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        output = (login_process.stdout or login_process.stderr).strip()
        lowered = output.lower()
        if login_process.returncode == 0 and "logged in" in lowered:
            login_ok = True
            if "chatgpt" in lowered:
                login_mode = "ChatGPT"
            elif "api key" in lowered:
                login_mode = "API Key"
            else:
                login_mode = "Unknown"
        else:
            issues.append(output or ("`codex login status` returned an unexpected response." if is_english(lang) else "`codex login status` 返回异常。"))
    except OSError as exc:
        issues.append(
            f"Failed to run `codex login status`: {exc}"
            if is_english(lang)
            else f"无法执行 `codex login status`：{exc}"
        )

    if login_ok:
        message = (
            f"Detected a usable Codex CLI. Login mode: {login_mode or 'Unknown'}."
            if is_english(lang)
            else f"已检测到可用的 Codex CLI，登录方式：{login_mode or 'Unknown'}。"
        )
    elif issues:
        message = "Codex CLI was found, but usable login has not been completed." if is_english(lang) else "检测到 Codex CLI，但当前未完成可用登录。"
    else:
        message = "Codex CLI status is unknown." if is_english(lang) else "Codex CLI 状态未知。"

    _CODEX_STATUS_CACHE[lang] = CodexCLIStatus(
        available=True,
        executable=executable,
        version=version,
        login_ok=login_ok,
        login_mode=login_mode,
        can_execute=login_ok,
        message=message,
        issues=issues,
        notes=notes,
    )
    return _CODEX_STATUS_CACHE[lang]


def capability_matrix(language: str | None = None) -> list[dict[str, str]]:
    lang = _resolve_language(language)
    codex_status = detect_codex_cli(language=lang)
    codex_cli_state = "Ready" if codex_status.can_execute and is_english(lang) else "已打通" if codex_status.can_execute else "Login Or Install Required" if is_english(lang) else "需登录或安装"
    codex_cli_note = codex_status.message
    if codex_status.issues:
        codex_cli_note = f"{codex_cli_note} {_join_items(codex_status.issues[:2], lang)}"

    return [
        {
            "label": "Local Codex CLI Execution" if is_english(lang) else "本地 Codex CLI 执行链路",
            "status": codex_cli_state,
            "description": codex_cli_note,
        },
        {
            "label": "PDF Downloads" if is_english(lang) else "PDF 下载",
            "status": "Ready" if is_english(lang) else "已打通",
            "description": (
                "Downloads PDFs through the local paper-fetcher script and writes a source sidecar."
                if is_english(lang)
                else "通过 paper-fetcher 本地脚本真实下载 PDF，并写入来源 sidecar。"
            ),
        },
        {
            "label": "In-App Research Execution" if is_english(lang) else "网页内研究执行",
            "status": "Ready" if is_english(lang) else "已打通",
            "description": (
                "Top 10, deep read, topic map, feasibility, and constraint exploration all use the local Codex CLI first, and report real failure reasons when they fail."
                if is_english(lang)
                else "Top10 / 精读 / 方向地图 / 可行性 / 资源探索现在优先走本地 Codex CLI，失败时会明确返回真实原因。"
            ),
        },
        {
            "label": "Automation Configuration" if is_english(lang) else "自动化配置",
            "status": "Ready" if is_english(lang) else "已打通",
            "description": (
                "The web app writes the daily profile and automation YAML, and recommends a quality profile. The actual model and reasoning settings for Codex app automations still need to be chosen manually."
                if is_english(lang)
                else "网页会写 daily profile 与 automation YAML，并给出质量档位推荐；Codex app automation 的模型与 reasoning 仍需手动选择。"
            ),
        },
    ]


def save_prompt_request(
    package: PromptPackage,
    bridge_mode: str = "prompt-shell-manual",
    note: str | None = None,
) -> BridgeResponse:
    language = _resolve_language(package.metadata.get("language"))
    request_path = prompt_request_path(package.skill_name, package.title)
    request_path.parent.mkdir(parents=True, exist_ok=True)
    request_text = "\n".join(
        [
            f"# Prompt Request: {package.title}",
            "",
            "```yaml",
            yaml.safe_dump(package.metadata, allow_unicode=True, sort_keys=False).strip(),
            "```",
            "",
            "## Prompt",
            "",
            package.prompt.strip(),
            "",
            "## Bridge Status" if is_english(language) else "## Bridge Status",
            "",
            f"- mode: {bridge_mode}",
            f"- note: {note or ('This request file was generated by the local web app and can be used for manual replay or auditing.' if is_english(language) else '该请求文件由本地网页生成，可用于手动回放或审计。')}",
        ]
    )
    request_path.write_text(request_text, encoding="utf-8")
    request_meta_path = request_path.with_suffix(".json")
    _save_json(request_meta_path, package.metadata)
    return BridgeResponse(
        task_type=str(package.metadata.get("task_type", package.skill_name)),
        status="saved",
        mode=bridge_mode,
        message="Prompt request file generated." if is_english(language) else "已生成 prompt 请求文件。",
        quality_profile=str(package.metadata.get("quality_profile", "balanced")),
        model=package.metadata.get("model"),
        reasoning_effort=package.metadata.get("reasoning_effort"),
        control_level=package.metadata.get("control_level"),
        prompt_request_path=request_path,
        expected_output_path=package.expected_output,
        manifest_path=package.manifest_output,
        output_paths={
            "prompt_request": str(request_path),
            "markdown": str(package.expected_output),
            "json": str(package.manifest_output) if package.manifest_output else "",
        },
        payload=package.metadata,
        prompt_text=package.prompt,
    )


def _compose_codex_prompt(
    package: PromptPackage,
    task_type: str,
    input_summary: dict[str, Any],
    quality: QualityProfileSelection,
) -> str:
    language = _resolve_language(package.metadata.get("language"))
    manifest_path = str(package.manifest_output) if package.manifest_output else ("Not provided" if is_english(language) else "未提供")
    sidecar_skeleton = json.dumps(
        {
            "task_type": task_type,
            "created_at": "...",
            "input_summary": input_summary,
            "quality_profile": quality.name,
            "model": quality.model,
            "reasoning_effort": quality.reasoning_effort,
            "execution_mode": "local-codex-cli",
            "status": "success",
            "output_paths": {
                "markdown": str(package.expected_output),
                "json": manifest_path,
            },
            "error": None,
        },
        ensure_ascii=False,
        indent=2,
    )
    execution_context = {
        "task_type": task_type,
        "quality_profile": quality.name,
        "model": quality.model,
        "reasoning_effort": quality.reasoning_effort,
        "control_level": quality.web_execution_control,
        "expected_output": str(package.expected_output),
        "manifest_output": manifest_path,
    }
    if is_english(language):
        return "\n".join(
            [
                package.prompt.strip(),
                "",
                "Additional Execution Context",
                "",
                "```yaml",
                yaml.safe_dump(execution_context, allow_unicode=True, sort_keys=False).strip(),
                "```",
                "",
                "Enforced Execution Requirements",
                "1. This is a real execution task launched from the local web app through Codex CLI. Do not return analysis only. You must write the result to the required output files.",
                f"2. The main Markdown file must be written to: {package.expected_output}",
                f"3. The JSON sidecar must be written to: {manifest_path}",
                "4. The top level of the JSON sidecar must keep at least the following fields. You may append task-specific fields beyond them:",
                "```json",
                sidecar_skeleton,
                "```",
                "5. If you need live web research, use the currently available real-time browsing capabilities instead of treating static knowledge as current fact.",
                "6. If the task is only partially completed, still write the sidecar with `status=partial` or `status=error`, and explain the real failure reason.",
                "7. If the output mentions local file paths, they must be real project paths. Do not invent paths.",
                "",
                "Final Reply Requirement",
                "- After all files are written, return only one JSON object.",
                "- That JSON object must match the schema provided by the bridge layer so the web app can read the execution state.",
            ]
        )
    return "\n".join(
        [
            package.prompt.strip(),
            "",
            "补充执行上下文",
            "",
            "```yaml",
            yaml.safe_dump(execution_context, allow_unicode=True, sort_keys=False).strip(),
            "```",
            "",
            "强制执行要求",
            "1. 这是本地网页通过 Codex CLI 发起的真实执行任务，不要只返回分析文本，必须把结果真实写入指定输出文件。",
            f"2. Markdown 主文件必须写到：{package.expected_output}",
            f"3. JSON sidecar 必须写到：{manifest_path}",
            "4. JSON sidecar 顶层至少保留以下字段；可以在此基础上追加任务特有字段：",
            "```json",
            sidecar_skeleton,
            "```",
            "5. 如果你需要联网检索，请使用当前可用的实时检索能力，不要把静态知识当成最新事实。",
            "6. 如果任务未完全完成，也要把 sidecar 写成 `status=partial` 或 `status=error`，并写清失败原因。",
            "7. 若输出中涉及本地文件路径，必须使用项目内真实路径，不要虚构。",
            "",
            "最终回复要求",
            "- 所有文件写入完成后，最终只返回一个 JSON 对象。",
            "- 该 JSON 对象必须符合桥接层给你的 schema，用于网页回读状态。",
        ]
    )


def _wrap_prompt_package(
    package: PromptPackage,
    task_type: str,
    input_summary: dict[str, Any],
    quality: QualityProfileSelection,
) -> PromptPackage:
    metadata = dict(package.metadata)
    metadata.update(
        {
            "task_type": task_type,
            "input_summary": input_summary,
            "quality_profile": quality.name,
            "model": quality.model,
            "reasoning_effort": quality.reasoning_effort,
            "control_level": quality.web_execution_control,
            "execution_mode": "local-codex-cli",
        }
    )
    return PromptPackage(
        skill_name=package.skill_name,
        title=package.title,
        prompt=_compose_codex_prompt(package, task_type, input_summary, quality),
        expected_output=package.expected_output,
        manifest_output=package.manifest_output,
        metadata=metadata,
    )


def _write_standard_sidecar(
    task_type: str,
    manifest_path: Path | None,
    input_summary: dict[str, Any],
    quality: QualityProfileSelection,
    expected_output: Path,
    prompt_request_path: Path | None,
    status: str,
    error: str | None = None,
    existing: dict[str, Any] | None = None,
    extra_paths: dict[str, str] | None = None,
    execution_mode: str = "local-codex-cli",
) -> dict[str, Any]:
    payload = dict(existing or {})
    canonical = {
        "task_type": task_type,
        "created_at": payload.get("created_at") or now_iso(),
        "input_summary": input_summary,
        "quality_profile": quality.name,
        "model": quality.model,
        "reasoning_effort": quality.reasoning_effort,
        "execution_mode": execution_mode,
        "status": status,
        "output_paths": {
            "markdown": str(expected_output),
            "json": str(manifest_path) if manifest_path else "",
            "prompt_request": str(prompt_request_path) if prompt_request_path else "",
        },
        "error": error,
    }
    if extra_paths:
        canonical["output_paths"].update(extra_paths)
    payload.update(canonical)
    if manifest_path:
        _save_json(manifest_path, payload)
    return payload


def _augment_manifest(manifest_path: Path | None, updates: dict[str, Any]) -> dict[str, Any]:
    payload = _load_json(manifest_path) if manifest_path else {}
    payload.update(updates)
    if manifest_path:
        _save_json(manifest_path, payload)
    return payload


def _invoke_codex_exec(prompt: str, quality: QualityProfileSelection) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="research-assistant-codex-") as temp_dir:
        schema_path = Path(temp_dir) / "result-schema.json"
        last_message_path = Path(temp_dir) / "last-message.json"
        _save_json(schema_path, CODEX_EXEC_RESULT_SCHEMA)
        command = [
            "codex",
            "exec",
            "-m",
            quality.model,
            "-c",
            f'model_reasoning_effort="{quality.reasoning_effort}"',
            "-C",
            str(ROOT),
            "--skip-git-repo-check",
            "-s",
            "workspace-write",
            "--color",
            "never",
            "--output-schema",
            str(schema_path),
            "--output-last-message",
            str(last_message_path),
            "-",
        ]
        process = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            input=prompt,
            check=False,
        )
        last_message = last_message_path.read_text(encoding="utf-8").strip() if last_message_path.exists() else ""
        try:
            final_json = json.loads(last_message) if last_message else {}
        except json.JSONDecodeError:
            final_json = {}
        return {
            "returncode": process.returncode,
            "stdout": process.stdout.strip(),
            "stderr": process.stderr.strip(),
            "final_json": final_json,
            "last_message": last_message,
        }


def _bridge_unavailable_response(
    task_type: str,
    wrapped_package: PromptPackage,
    input_summary: dict[str, Any],
    quality: QualityProfileSelection,
    codex_status: CodexCLIStatus,
) -> BridgeResponse:
    language = _resolve_language(wrapped_package.metadata.get("language"))
    prompt_record = save_prompt_request(
        wrapped_package,
        bridge_mode="manual-bridge-fallback",
        note=(
            "No usable local Codex CLI environment was detected, or login has not been completed. The prompt request file has been kept for manual replay."
            if is_english(language)
            else "未检测到可用的本地 Codex CLI 或未完成登录；已保留 prompt 请求文件以便手动回放。"
        ),
    )
    manifest = _write_standard_sidecar(
        task_type=task_type,
        manifest_path=wrapped_package.manifest_output,
        input_summary=input_summary,
        quality=quality,
        expected_output=wrapped_package.expected_output,
        prompt_request_path=prompt_record.prompt_request_path,
        status="unavailable",
        error=codex_status.message if not codex_status.issues else _join_items(codex_status.issues, language),
        execution_mode="manual-bridge-fallback",
    )
    return BridgeResponse(
        task_type=task_type,
        status="unavailable",
        mode="manual-bridge-fallback",
        message=(
            "No usable local Codex CLI execution environment was detected. Falling back to manual bridging."
            if is_english(language)
            else "未检测到可用的本地 Codex CLI 执行环境，已回退为手动桥接。"
        ),
        quality_profile=quality.name,
        model=quality.model,
        reasoning_effort=quality.reasoning_effort,
        control_level=quality.web_execution_control,
        prompt_request_path=prompt_record.prompt_request_path,
        expected_output_path=wrapped_package.expected_output,
        manifest_path=wrapped_package.manifest_output,
        output_paths=manifest.get("output_paths", {}),
        error=manifest.get("error"),
        payload=manifest,
        prompt_text=wrapped_package.prompt,
    )


def _run_codex_task(
    task_type: str,
    package: PromptPackage,
    input_summary: dict[str, Any],
    requested_quality: str | None,
) -> BridgeResponse:
    ensure_project_layout()
    language = _resolve_language(package.metadata.get("language"))
    quality = _quality_selection(task_type, requested_quality)
    wrapped_package = _wrap_prompt_package(package, task_type, input_summary, quality)
    codex_status = detect_codex_cli(language=language)
    if not codex_status.can_execute:
        return _bridge_unavailable_response(task_type, wrapped_package, input_summary, quality, codex_status)

    prompt_record = save_prompt_request(
        wrapped_package,
        bridge_mode="local-codex-cli",
        note=(
            "The web app has triggered local Codex CLI execution. This prompt request file is retained for auditing and manual replay."
            if is_english(language)
            else "网页已触发本地 Codex CLI 执行。该 prompt 请求文件保留用于审计与手动回放。"
        ),
    )
    result = _invoke_codex_exec(wrapped_package.prompt, quality)
    final_json = result.get("final_json") or {}
    manifest_existing = _load_json(wrapped_package.manifest_output) if wrapped_package.manifest_output else {}

    status = str(final_json.get("status") or ("success" if result["returncode"] == 0 else "error"))
    error = final_json.get("error")
    if result["returncode"] != 0 and not error:
        error = result["stderr"] or result["stdout"] or ("Codex CLI execution failed." if is_english(language) else "Codex CLI 执行失败。")

    markdown_exists = wrapped_package.expected_output.exists()
    if status == "success" and not markdown_exists:
        status = "partial" if manifest_existing else "error"
        error = error or ("Expected Markdown output file was not found." if is_english(language) else "未找到预期的 Markdown 输出文件。")
    if not manifest_existing and status == "success":
        manifest_existing = {}

    sidecar = _write_standard_sidecar(
        task_type=task_type,
        manifest_path=wrapped_package.manifest_output,
        input_summary=input_summary,
        quality=quality,
        expected_output=wrapped_package.expected_output,
        prompt_request_path=prompt_record.prompt_request_path,
        status=status,
        error=error,
        existing=manifest_existing,
    )

    summary = str(final_json.get("summary") or "")
    notes = final_json.get("notes") or []
    if status == "success":
        message = summary or (f"{_task_label(task_type, language)} completed successfully." if is_english(language) else f"{_task_label(task_type, language)}执行成功。")
    elif status == "partial":
        message = summary or (f"{_task_label(task_type, language)} completed partially." if is_english(language) else f"{_task_label(task_type, language)}部分完成。")
    else:
        message = summary or error or (f"{_task_label(task_type, language)} failed." if is_english(language) else f"{_task_label(task_type, language)}执行失败。")
    if notes:
        message = f"{message} {_join_items([str(item) for item in notes[:2]], language)}"

    output_paths = dict(sidecar.get("output_paths", {}))
    if final_json.get("written_files"):
        output_paths["reported_written_files"] = ", ".join(str(item) for item in final_json["written_files"])

    return BridgeResponse(
        task_type=task_type,
        status=status,
        mode="local-codex-cli",
        message=message,
        quality_profile=quality.name,
        model=quality.model,
        reasoning_effort=quality.reasoning_effort,
        control_level=quality.web_execution_control,
        prompt_request_path=prompt_record.prompt_request_path,
        expected_output_path=wrapped_package.expected_output,
        manifest_path=wrapped_package.manifest_output,
        output_paths=output_paths,
        error=error,
        payload={
            **sidecar,
            "exec_result": final_json,
            "stdout": _trim_text(result["stdout"]),
            "stderr": _trim_text(result["stderr"]),
        },
        prompt_text=wrapped_package.prompt,
    )


def run_literature_scout(task_input: LiteratureScoutInput) -> BridgeResponse:
    package = build_literature_scout_prompt(asdict(task_input))
    return _run_codex_task(
        task_type="literature_scout",
        package=package,
        input_summary={
            "field": task_input.field,
            "time_range": task_input.time_range,
            "sources": task_input.sources,
            "ranking_profile": task_input.ranking_profile,
            "constraints": task_input.constraints,
            "top_k": task_input.top_k,
            "language": task_input.language,
        },
        requested_quality=task_input.quality_profile,
    )


def run_topic_mapper(task_input: TopicMapperInput) -> BridgeResponse:
    package = build_topic_mapper_prompt(asdict(task_input))
    return _run_codex_task(
        task_type="topic_mapper",
        package=package,
        input_summary={
            "topic": task_input.topic,
            "time_range": task_input.time_range,
            "cross_domain": task_input.cross_domain,
            "return_count": task_input.return_count,
            "ranking_mode": task_input.ranking_mode,
            "language": task_input.language,
        },
        requested_quality=task_input.quality_profile,
    )


def run_idea_feasibility(task_input: IdeaFeasibilityInput) -> BridgeResponse:
    package = build_idea_feasibility_prompt(asdict(task_input))
    return _run_codex_task(
        task_type="idea_feasibility",
        package=package,
        input_summary={
            "idea": task_input.idea,
            "target_field": task_input.target_field,
            "compute_budget": task_input.compute_budget,
            "data_budget": task_input.data_budget,
            "risk_preference": task_input.risk_preference,
            "prefer_low_cost_validation": task_input.prefer_low_cost_validation,
            "language": task_input.language,
        },
        requested_quality=task_input.quality_profile,
    )


def run_constraint_explorer(task_input: ConstraintExplorerInput) -> BridgeResponse:
    package = build_constraint_explorer_prompt(asdict(task_input))
    return _run_codex_task(
        task_type="constraint_explorer",
        package=package,
        input_summary={
            "field": task_input.field,
            "compute_limit": task_input.compute_limit,
            "data_limit": task_input.data_limit,
            "prefer_reproduction": task_input.prefer_reproduction,
            "prefer_open_source": task_input.prefer_open_source,
            "language": task_input.language,
        },
        requested_quality=task_input.quality_profile,
    )


def run_paper_reader(task_input: PaperReaderInput) -> BridgeResponse:
    language = _resolve_language(task_input.language)
    resolved_reference = task_input.paper_reference
    fetch_payload: dict[str, Any] | None = None
    if task_input.auto_fetch_pdf and parse_reference(task_input.paper_reference).kind != "local_pdf":
        reader_quality = _quality_selection("paper_reader", task_input.quality_profile)
        download_response = run_paper_fetch(
            PaperFetcherInput(
                reference=task_input.paper_reference,
                output_dir=OUTPUTS_DIR / "pdfs",
                quality_profile="economy",
                language=language,
            )
        )
        if download_response.status not in {"success", "ok"}:
            return BridgeResponse(
                task_type="paper_reader",
                status="error",
                mode=download_response.mode,
                message="Paper download failed, so the deep read could not continue." if is_english(language) else "论文下载失败，无法继续精读。",
                quality_profile=reader_quality.name,
                model=reader_quality.model,
                reasoning_effort=reader_quality.reasoning_effort,
                control_level="not-started",
                error=download_response.error or download_response.message,
                payload={"fetch": download_response.to_dict()},
            )
        fetch_payload = download_response.to_dict()
        resolved_reference = str((download_response.payload or {}).get("saved_path", task_input.paper_reference))

    extraction_payload: dict[str, Any] | None = None
    resolved_parsed = parse_reference(resolved_reference)
    if resolved_parsed.kind == "local_pdf":
        extraction = extract_pdf_text(resolved_parsed.normalized, language=language)
        extraction_payload = extraction.to_dict()

    package = build_paper_reader_prompt(
        {
            "paper_reference": resolved_reference,
            "summary_depth": task_input.summary_depth,
            "diagram_summary": task_input.diagram_summary,
            "focus_experiments": task_input.focus_experiments,
            "reference_slug": task_input.reference_slug,
            "language": task_input.language,
            "pdf_extraction": extraction_payload,
        }
    )
    response = _run_codex_task(
        task_type="paper_reader",
        package=package,
        input_summary={
            "original_reference": task_input.paper_reference,
            "resolved_reference": resolved_reference,
            "summary_depth": task_input.summary_depth,
            "diagram_summary": task_input.diagram_summary,
            "focus_experiments": task_input.focus_experiments,
            "auto_fetch_pdf": task_input.auto_fetch_pdf,
            "pdf_extraction": extraction_payload,
            "language": task_input.language,
        },
        requested_quality=task_input.quality_profile,
    )
    if extraction_payload:
        manifest_payload = _augment_manifest(
            response.manifest_path,
            {
                "pdf_extraction": extraction_payload,
                "uncertainty": extraction_payload.get("warnings", []),
                "output_paths": {
                    **((response.payload or {}).get("output_paths") or {}),
                    "pdf_text": extraction_payload.get("text_path", ""),
                    "pdf_extraction_sidecar": extraction_payload.get("sidecar_path", ""),
                },
            },
        )
        response.output_paths.update(
            {
                "pdf_text": str(extraction_payload.get("text_path", "")),
                "pdf_extraction_sidecar": str(extraction_payload.get("sidecar_path", "")),
            }
        )
        payload = dict(response.payload or {})
        payload.update(
            {
                "pdf_extraction": extraction_payload,
                "uncertainty": extraction_payload.get("warnings", []),
                "output_paths": manifest_payload.get("output_paths", response.output_paths),
            }
        )
        response.payload = payload
        if extraction_payload.get("quality") in {"mixed", "poor"}:
            response.message = (
                (
                    f"{response.message} PDF extraction quality is {extraction_payload['quality']}. Tables, formulas, and experimental details were treated as uncertain evidence."
                    if is_english(language)
                    else f"{response.message} PDF 文本抽取质量为 {extraction_payload['quality']}，表格、公式和实验细节已按不确定信息处理。"
                )
            )
    if fetch_payload:
        payload = dict(response.payload or {})
        payload["fetch"] = fetch_payload
        response.payload = payload
    return response


def _normalize_source_record(
    source_record_path: Path,
    task_input: PaperFetcherInput,
    quality_profile: str,
    status: str,
    error: str | None = None,
) -> dict[str, Any]:
    payload = _load_json(source_record_path)
    payload.update(
        {
            "task_type": "paper_fetcher",
            "created_at": payload.get("updated_at") or now_iso(),
            "input_summary": {
                "reference": task_input.reference,
                "output_dir": str(task_input.output_dir or OUTPUTS_DIR / "pdfs"),
                "filename": task_input.filename,
                "force": task_input.force,
                "resolve_only": task_input.resolve_only,
            },
            "quality_profile": quality_profile,
            "model": None,
            "reasoning_effort": None,
            "execution_mode": "local-script",
            "status": status,
            "output_paths": {
                "pdf": payload.get("saved_path", ""),
                "source_record": str(source_record_path),
            },
            "error": error,
        }
    )
    _save_json(source_record_path, payload)
    return payload


def run_paper_fetch(task_input: PaperFetcherInput) -> BridgeResponse:
    ensure_project_layout()
    language = _resolve_language(task_input.language)
    quality = _quality_selection("paper_fetcher", task_input.quality_profile)
    target_dir = str(task_input.output_dir or (OUTPUTS_DIR / "pdfs"))
    command = [
        sys.executable,
        str(PAPER_FETCHER_SCRIPT),
        task_input.reference,
        "--output-dir",
        target_dir,
        "--json",
    ]
    if task_input.filename:
        command.extend(["--filename", task_input.filename])
    if task_input.force:
        command.append("--force")
    if task_input.resolve_only:
        command.append("--resolve-only")

    process = subprocess.run(
        command,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = _parse_process_output(process)
    raw_message = payload.get("message") or payload.get("error") or process.stderr.strip()
    source_record = payload.get("source_record")

    if process.returncode != 0:
        return BridgeResponse(
            task_type="paper_fetcher",
            status="error",
            mode="local-script",
            message="PDF download failed." if is_english(language) else "PDF 下载失败。",
            quality_profile=quality.name,
            model=None,
            reasoning_effort=None,
            control_level="local-script",
            output_paths={},
            error=payload.get("error") or process.stderr.strip() or raw_message or ("Download failed." if is_english(language) else "下载失败。"),
            payload={**(payload or {"stderr": process.stderr.strip()}), "raw_message": raw_message},
        )

    if source_record:
        source_payload = _normalize_source_record(
            Path(source_record),
            task_input=task_input,
            quality_profile=quality.name,
            status="success",
        )
    else:
        source_payload = payload

    return BridgeResponse(
        task_type="paper_fetcher",
        status="success",
        mode="local-script",
        message="PDF downloaded successfully." if is_english(language) else "PDF 下载成功。",
        quality_profile=quality.name,
        model=None,
        reasoning_effort=None,
        control_level="local-script",
        output_paths={
            "pdf": str(payload.get("saved_path", "")),
            "source_record": str(source_record or ""),
        },
        payload={**source_payload, "raw_message": raw_message},
    )


def download_and_run_reader(
    reference: str,
    quality_profile: str | None = None,
    reader_quality_profile: str | None = None,
    output_dir: str | Path | None = None,
    summary_depth: str = "standard",
    diagram_summary: bool = True,
    focus_experiments: bool = True,
    language: str | None = None,
) -> dict[str, BridgeResponse | None]:
    download_response = run_paper_fetch(
        PaperFetcherInput(
            reference=reference,
            output_dir=output_dir or (OUTPUTS_DIR / "pdfs"),
            quality_profile=quality_profile or "economy",
            language=language,
        )
    )
    reader_response: BridgeResponse | None = None
    if download_response.status == "success":
        pdf_path = str((download_response.payload or {}).get("saved_path", ""))
        if pdf_path:
            reader_response = run_paper_reader(
                PaperReaderInput(
                    paper_reference=pdf_path,
                    summary_depth=summary_depth,
                    diagram_summary=diagram_summary,
                    focus_experiments=focus_experiments,
                    auto_fetch_pdf=False,
                    quality_profile=reader_quality_profile or "balanced",
                    reference_slug=Path(pdf_path).stem,
                    language=language,
                )
            )
    return {
        "download": download_response,
        "reader": reader_response,
    }
