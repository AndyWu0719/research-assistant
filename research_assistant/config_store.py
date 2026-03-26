from __future__ import annotations

import hashlib
import json
import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from research_assistant.language import DEFAULT_LANGUAGE, normalize_language
from research_assistant.ui_text import normalize_risk_preference, normalize_summary_depth


PROJECT_ROOT_ENV = "RESEARCH_ASSISTANT_PROJECT_ROOT"
ROOT = Path(os.environ.get(PROJECT_ROOT_ENV, Path(__file__).resolve().parents[1])).expanduser().resolve()
AGENTS_PATH = ROOT / "AGENTS.md"
SKILLS_DIR = ROOT / "skills"
CONFIGS_DIR = ROOT / "configs"
OUTPUTS_DIR = ROOT / "outputs"
LITERATURE_SCAN_OUTPUT_DIR = OUTPUTS_DIR / "literature_scans"
LEGACY_LITERATURE_SCAN_OUTPUT_DIR = OUTPUTS_DIR / "daily_top10"
LITERATURE_SCAN_RESULT_DIRS = (
    LITERATURE_SCAN_OUTPUT_DIR,
    LEGACY_LITERATURE_SCAN_OUTPUT_DIR,
)

SCAN_DEFAULTS_PATH = CONFIGS_DIR / "scan_defaults.yaml"
LEGACY_DAILY_PROFILE_PATH = CONFIGS_DIR / "daily_profile.yaml"
AUTOMATIONS_DIR = CONFIGS_DIR / "automations"
LEGACY_AUTOMATION_CONFIG_PATH = AUTOMATIONS_DIR / "daily_top10.yaml"
AUTOMATION_INDEX_PATH = AUTOMATIONS_DIR / "index.yaml"
AUTOMATION_HISTORY_DIR = AUTOMATIONS_DIR / "history"
AUTOMATION_RUNTIME_STATE_PATH = AUTOMATIONS_DIR / "runtime_state.json"
INTERESTING_PAPERS_PATH = CONFIGS_DIR / "interesting_papers.json"
EXECUTION_PROFILES_PATH = CONFIGS_DIR / "execution_profiles.yaml"
RANKING_PROFILES_PATH = CONFIGS_DIR / "ranking_profiles.md"
SOURCE_POLICIES_PATH = CONFIGS_DIR / "source_policies.md"
USER_PREFERENCES_PATH = CONFIGS_DIR / "user_preferences.yaml"
APP_UPDATE_CONFIG_PATH = CONFIGS_DIR / "app_update.yaml"
DEFAULT_TOP_K = 10
DEFAULT_RANKING_PROFILE = "balanced-default"
DEFAULT_QUALITY_PROFILE = "balanced"
DEFAULT_OUTPUT_ROOT = "outputs"
DEFAULT_PDF_DIR = "outputs/pdfs"
DEFAULT_SOURCES = ["arXiv", "OpenReview"]
QUALITY_PROFILE_OPTIONS = [
    "economy",
    "balanced",
    "high-accuracy",
    "max-analysis",
]
SOURCE_OPTIONS = [
    "arXiv",
    "OpenReview",
    "ACL Anthology",
    "CVF Open Access",
    "PMLR",
    "Semantic Scholar",
    "Crossref",
    "Google Scholar",
]
RANKING_PROFILES = [
    "balanced-default",
    "trend-focused",
    "resource-constrained",
]
TIME_RANGE_OPTIONS = {
    "7d": {"mode": "rolling", "days": 7, "label": "最近 7 天"},
    "14d": {"mode": "rolling", "days": 14, "label": "最近 14 天"},
    "30d": {"mode": "rolling", "days": 30, "label": "最近 30 天"},
    "90d": {"mode": "rolling", "days": 90, "label": "最近 90 天"},
    "1y": {"mode": "rolling", "days": 365, "label": "最近 1 年"},
}

DEFAULT_SCAN_DEFAULTS: dict[str, Any] = {
    "field": "multimodal large language models",
    "time_range": {"mode": "rolling", "days": 7, "label": "最近 7 天"},
    "sources": deepcopy(DEFAULT_SOURCES),
    "ranking_profile": DEFAULT_RANKING_PROFILE,
    "quality_profile": DEFAULT_QUALITY_PROFILE,
    "constraints": {
        "compute": "",
        "data": "优先公开数据、公开代码和可直接复用 benchmark",
        "time": "优先选择过去 7 天内值得跟进的新论文",
        "budget": "",
        "notes": "作为示例配置，可在网页中改成你自己的研究方向。",
    },
    "output": {
        "directory": "outputs/literature_scans",
        "filename_template": "YYYY-MM-DD-<field>-<ranking_profile>.md",
    },
    "language": DEFAULT_LANGUAGE,
    "top_k": DEFAULT_TOP_K,
}
DEFAULT_DAILY_PROFILE = DEFAULT_SCAN_DEFAULTS

DEFAULT_AUTOMATION_CONFIG: dict[str, Any] = {
    "task_name": "每日文献巡检",
    "field": DEFAULT_SCAN_DEFAULTS["field"],
    "time_range": DEFAULT_SCAN_DEFAULTS["time_range"],
    "sources": deepcopy(DEFAULT_SCAN_DEFAULTS["sources"]),
    "ranking_profile": DEFAULT_SCAN_DEFAULTS["ranking_profile"],
    "quality_profile": DEFAULT_QUALITY_PROFILE,
    "constraints": deepcopy(DEFAULT_SCAN_DEFAULTS["constraints"]),
    "top_k": DEFAULT_TOP_K,
    "schedule": {
        "timezone": "Asia/Hong_Kong",
        "time_of_day": "09:00",
        "cadence": "daily",
    },
    "enabled": True,
    "auto_download_interesting": False,
    "runner": "local-scheduler",
    "exclude_previous_output_papers": True,
    "history_scope": "same-field",
    "generated_prompt_target": "Local Scheduler + Codex CLI",
    "language": DEFAULT_LANGUAGE,
}

DEFAULT_INTERESTING_PAPERS: dict[str, Any] = {
    "updated_at": None,
    "items": [],
}

DEFAULT_EXECUTION_PROFILES: dict[str, Any] = {
    "profiles": {
        "economy": {
            "label": "economy",
            "description": "最低成本档，适合检索、整理、下载、轻量总结。",
            "model": "gpt-5.4-mini",
            "reasoning_effort": "low",
            "web_execution_control": "exact-cli-override",
            "automation_control": "recommended-only",
        },
        "balanced": {
            "label": "balanced",
            "description": "默认平衡档，适合常规文献巡检和常规论文总结。",
            "model": "gpt-5.4",
            "reasoning_effort": "medium",
            "web_execution_control": "exact-cli-override",
            "automation_control": "recommended-only",
        },
        "high-accuracy": {
            "label": "high-accuracy",
            "description": "高精度档，适合跨论文综合、方向地图与可行性分析。",
            "model": "gpt-5.4",
            "reasoning_effort": "high",
            "web_execution_control": "exact-cli-override",
            "automation_control": "recommended-only",
        },
        "max-analysis": {
            "label": "max-analysis",
            "description": "最高分析档，仅在明确要求时使用。",
            "model": "gpt-5.4",
            "reasoning_effort": "xhigh",
            "web_execution_control": "exact-cli-override",
            "automation_control": "recommended-only",
        },
    },
    "task_defaults": {
        "paper_fetcher": "economy",
        "prompt_builder": "economy",
        "automation": "balanced",
        "literature_scout": "balanced",
        "paper_reader": "balanced",
        "topic_mapper": "balanced",
        "idea_feasibility": "balanced",
        "constraint_explorer": "balanced",
    },
    "recommendations": {
        "daily_scan": "建议优先 balanced；若只做轻量巡检可改 economy。",
        "paper_reader": "常规精读建议 balanced；重要论文深读再切到 high-accuracy。",
        "deep_reports": "跨论文综合、方向地图、可行性分析优先 high-accuracy。",
        "automation": "每日自动化默认不要用 max-analysis，避免持续高成本运行。",
    },
}

DEFAULT_AUTOMATION_INDEX: dict[str, Any] = {
    "active_config": None,
    "updated_at": None,
}

DEFAULT_AUTOMATION_RUNTIME_STATE: dict[str, Any] = {
    "daemon": {
        "pid": None,
        "started_at": None,
        "heartbeat_at": None,
    },
    "configs": {},
}

DEFAULT_USER_PREFERENCES: dict[str, Any] = {
    "version": 1,
    "language": DEFAULT_LANGUAGE,
    "global_defaults": {
        "field": DEFAULT_SCAN_DEFAULTS["field"],
        "time_range_key": "7d",
        "sources": deepcopy(DEFAULT_SOURCES),
        "ranking_profile": DEFAULT_RANKING_PROFILE,
        "constraints": deepcopy(DEFAULT_SCAN_DEFAULTS["constraints"]),
        "top_k": DEFAULT_TOP_K,
    },
    "task_defaults": {
        "literature_scout": {
            "quality_profile": "balanced",
        },
        "paper_reader": {
            "quality_profile": "balanced",
            "summary_depth": "standard",
            "diagram_summary": True,
            "focus_experiments": True,
            "auto_fetch_pdf": True,
        },
        "topic_mapper": {
            "quality_profile": "balanced",
            "time_range_key": "30d",
            "cross_domain": False,
            "return_count": 15,
            "ranking_mode": DEFAULT_RANKING_PROFILE,
        },
        "idea_feasibility": {
            "quality_profile": "balanced",
            "compute_budget": "单卡 24G",
            "data_budget": "优先公开数据",
            "risk_preference": "balanced",
            "prefer_low_cost_validation": True,
        },
        "constraint_explorer": {
            "quality_profile": "balanced",
            "compute_limit": "单卡 24G",
            "data_limit": "优先公开数据或可替代小规模数据",
            "prefer_reproduction": True,
            "prefer_open_source": True,
        },
        "pdf_fetcher": {
            "save_dir": DEFAULT_PDF_DIR,
            "auto_read": False,
            "reader_quality_profile": "balanced",
        },
        "automation": {
            "quality_profile": "balanced",
            "run_time": "09:00",
            "auto_download_interesting": False,
        },
    },
    "active_automation": {
        "task_name": DEFAULT_AUTOMATION_CONFIG["task_name"],
        "filename": None,
    },
}

DEFAULT_APP_UPDATE_CONFIG: dict[str, Any] = {
    "provider": "github_release",
    "github_repo": "AndyWu0719/research-assistant",
    "github_asset_pattern": "ResearchAssistant-macos-*.pkg",
    "github_token_env": "",
    "manifest_url": "",
    "channel": "stable",
    "check_on_launch": True,
    "check_interval_hours": 24,
    "download_in_app": True,
    "open_download_in_browser": False,
}


def _sanitize_filename_fragment(value: str, max_length: int = 56) -> str:
    lowered = (value or "").strip().lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff._-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-._")
    if not lowered:
        lowered = "automation-task"
    return lowered[:max_length].rstrip("-._")


def automation_config_filename_for_task(task_name: str) -> str:
    cleaned = _sanitize_filename_fragment(task_name)
    digest = hashlib.sha1((task_name or "").strip().encode("utf-8")).hexdigest()[:8]
    return f"{cleaned}--{digest}.yaml"


def automation_config_path_for_task(task_name: str) -> Path:
    return AUTOMATIONS_DIR / automation_config_filename_for_task(task_name)


def _default_automation_config_path() -> Path:
    return automation_config_path_for_task(DEFAULT_AUTOMATION_CONFIG["task_name"])


def ensure_project_layout() -> None:
    directories = [
        CONFIGS_DIR,
        AUTOMATIONS_DIR,
        AUTOMATION_HISTORY_DIR,
        LITERATURE_SCAN_OUTPUT_DIR,
        OUTPUTS_DIR / "paper_summaries",
        OUTPUTS_DIR / "topic_maps",
        OUTPUTS_DIR / "feasibility_reports",
        OUTPUTS_DIR / "constraint_reports",
        OUTPUTS_DIR / "pdfs",
        OUTPUTS_DIR / "pdf_text",
        OUTPUTS_DIR / "smoke_tests",
        OUTPUTS_DIR / "prompt_requests" / "literature_scout",
        OUTPUTS_DIR / "prompt_requests" / "paper_reader",
        OUTPUTS_DIR / "prompt_requests" / "topic_mapper",
        OUTPUTS_DIR / "prompt_requests" / "idea_feasibility",
        OUTPUTS_DIR / "prompt_requests" / "constraint_explorer",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    if not SCAN_DEFAULTS_PATH.exists():
        if LEGACY_DAILY_PROFILE_PATH.exists():
            save_yaml(SCAN_DEFAULTS_PATH, load_yaml(LEGACY_DAILY_PROFILE_PATH, DEFAULT_SCAN_DEFAULTS))
            LEGACY_DAILY_PROFILE_PATH.unlink(missing_ok=True)
        else:
            save_yaml(SCAN_DEFAULTS_PATH, DEFAULT_SCAN_DEFAULTS)
    if not INTERESTING_PAPERS_PATH.exists():
        save_json(INTERESTING_PAPERS_PATH, DEFAULT_INTERESTING_PAPERS)
    if not EXECUTION_PROFILES_PATH.exists():
        save_yaml(EXECUTION_PROFILES_PATH, DEFAULT_EXECUTION_PROFILES)
    if not USER_PREFERENCES_PATH.exists():
        save_yaml(USER_PREFERENCES_PATH, DEFAULT_USER_PREFERENCES)
    if not APP_UPDATE_CONFIG_PATH.exists():
        save_yaml(APP_UPDATE_CONFIG_PATH, DEFAULT_APP_UPDATE_CONFIG)

    if not AUTOMATION_INDEX_PATH.exists():
        active_path = LEGACY_AUTOMATION_CONFIG_PATH if LEGACY_AUTOMATION_CONFIG_PATH.exists() else _default_automation_config_path()
        save_yaml(
            AUTOMATION_INDEX_PATH,
            {
                "active_config": active_path.name,
                "updated_at": now_iso(),
            },
        )
    if not AUTOMATION_RUNTIME_STATE_PATH.exists():
        save_json(AUTOMATION_RUNTIME_STATE_PATH, DEFAULT_AUTOMATION_RUNTIME_STATE)

    active_automation_path = current_automation_config_path()
    if not active_automation_path.exists():
        save_yaml(active_automation_path, DEFAULT_AUTOMATION_CONFIG)
    if active_automation_path == LEGACY_AUTOMATION_CONFIG_PATH and LEGACY_AUTOMATION_CONFIG_PATH.exists():
        migrate_legacy_automation_config_if_needed()


def deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = deepcopy(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_yaml(path: Path, default: dict[str, Any] | None = None) -> dict[str, Any]:
    if not path.exists():
        return deepcopy(default or {})
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if default is None:
        return data
    return deep_merge(default, data)


def save_yaml(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = yaml.safe_dump(
        data,
        allow_unicode=True,
        sort_keys=False,
        width=88,
    )
    path.write_text(text, encoding="utf-8")


def load_json(path: Path, default: dict[str, Any] | list[Any] | None = None) -> Any:
    if not path.exists():
        return deepcopy(default if default is not None else {})
    return json.loads(path.read_text(encoding="utf-8"))


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def normalize_time_range(value: str | dict[str, Any]) -> dict[str, Any]:
    if isinstance(value, dict):
        merged = deepcopy(value)
        if "label" not in merged:
            days = merged.get("days")
            if days:
                merged["label"] = f"最近 {days} 天"
        return merged
    return deepcopy(TIME_RANGE_OPTIONS.get(value, TIME_RANGE_OPTIONS["7d"]))


def time_range_key(value: str | dict[str, Any]) -> str:
    normalized = normalize_time_range(value)
    days = normalized.get("days")
    for key, option in TIME_RANGE_OPTIONS.items():
        if option.get("days") == days:
            return key
    return "7d"


def load_scan_defaults() -> dict[str, Any]:
    profile_path = SCAN_DEFAULTS_PATH if SCAN_DEFAULTS_PATH.exists() else LEGACY_DAILY_PROFILE_PATH
    profile = load_yaml(profile_path, DEFAULT_SCAN_DEFAULTS)
    profile["time_range"] = normalize_time_range(profile.get("time_range", "7d"))
    profile.setdefault("sources", deepcopy(DEFAULT_SOURCES))
    profile.setdefault("ranking_profile", DEFAULT_RANKING_PROFILE)
    profile["quality_profile"] = normalize_quality_profile(profile.get("quality_profile"))
    profile.setdefault("language", DEFAULT_LANGUAGE)
    profile.setdefault("top_k", DEFAULT_TOP_K)
    output = profile.setdefault("output", deepcopy(DEFAULT_SCAN_DEFAULTS["output"]))
    if str(output.get("directory") or "").strip() == "outputs/daily_top10":
        output["directory"] = DEFAULT_SCAN_DEFAULTS["output"]["directory"]
    output.setdefault("filename_template", DEFAULT_SCAN_DEFAULTS["output"]["filename_template"])
    return profile


def save_scan_defaults(profile: dict[str, Any]) -> None:
    payload = deep_merge(DEFAULT_SCAN_DEFAULTS, profile)
    payload["time_range"] = normalize_time_range(payload.get("time_range", "7d"))
    payload["quality_profile"] = normalize_quality_profile(payload.get("quality_profile"))
    payload["language"] = normalize_language(payload.get("language"))
    output = payload.setdefault("output", deepcopy(DEFAULT_SCAN_DEFAULTS["output"]))
    if str(output.get("directory") or "").strip() == "outputs/daily_top10":
        output["directory"] = DEFAULT_SCAN_DEFAULTS["output"]["directory"]
    output.setdefault("filename_template", DEFAULT_SCAN_DEFAULTS["output"]["filename_template"])
    save_yaml(SCAN_DEFAULTS_PATH, payload)
    LEGACY_DAILY_PROFILE_PATH.unlink(missing_ok=True)


def load_daily_profile() -> dict[str, Any]:
    return load_scan_defaults()


def save_daily_profile(profile: dict[str, Any]) -> None:
    save_scan_defaults(profile)


def load_automation_index() -> dict[str, Any]:
    index = load_yaml(AUTOMATION_INDEX_PATH, DEFAULT_AUTOMATION_INDEX)
    active_name = str(index.get("active_config") or "").strip()
    if active_name:
        index["active_config"] = Path(active_name).name
    else:
        index["active_config"] = None
    index.setdefault("updated_at", None)
    return index


def save_automation_index(index: dict[str, Any]) -> None:
    payload = deep_merge(DEFAULT_AUTOMATION_INDEX, index)
    active_name = str(payload.get("active_config") or "").strip()
    payload["active_config"] = Path(active_name).name if active_name else None
    payload["updated_at"] = now_iso()
    save_yaml(AUTOMATION_INDEX_PATH, payload)


def automation_history_path(path: Path | None = None) -> Path:
    config_path = path or current_automation_config_path()
    return AUTOMATION_HISTORY_DIR / f"{config_path.stem}.history.json"


def load_automation_runtime_state() -> dict[str, Any]:
    payload = load_json(AUTOMATION_RUNTIME_STATE_PATH, DEFAULT_AUTOMATION_RUNTIME_STATE)
    if not isinstance(payload, dict):
        return deepcopy(DEFAULT_AUTOMATION_RUNTIME_STATE)
    return deep_merge(DEFAULT_AUTOMATION_RUNTIME_STATE, payload)


def save_automation_runtime_state(state: dict[str, Any]) -> None:
    payload = deep_merge(DEFAULT_AUTOMATION_RUNTIME_STATE, state)
    save_json(AUTOMATION_RUNTIME_STATE_PATH, payload)


def current_automation_config_path() -> Path:
    index = load_yaml(AUTOMATION_INDEX_PATH, DEFAULT_AUTOMATION_INDEX) if AUTOMATION_INDEX_PATH.exists() else DEFAULT_AUTOMATION_INDEX
    active_name = str(index.get("active_config") or "").strip()
    if active_name:
        return AUTOMATIONS_DIR / Path(active_name).name
    if LEGACY_AUTOMATION_CONFIG_PATH.exists():
        return LEGACY_AUTOMATION_CONFIG_PATH
    return _default_automation_config_path()


def describe_automation_storage(task_name: str, path: Path | None = None) -> dict[str, str]:
    target = path or automation_config_path_for_task(task_name)
    return {
        "directory": str(target.parent),
        "filename": target.name,
        "path": str(target),
    }


def migrate_legacy_automation_config_if_needed() -> Path:
    if not LEGACY_AUTOMATION_CONFIG_PATH.exists():
        return current_automation_config_path()

    legacy_payload = load_yaml(LEGACY_AUTOMATION_CONFIG_PATH, DEFAULT_AUTOMATION_CONFIG)
    target_path = automation_config_path_for_task(str(legacy_payload.get("task_name") or DEFAULT_AUTOMATION_CONFIG["task_name"]))
    if target_path != LEGACY_AUTOMATION_CONFIG_PATH and not target_path.exists():
        save_yaml(target_path, legacy_payload)

    save_automation_index({"active_config": target_path.name})
    if USER_PREFERENCES_PATH.exists():
        preferences = load_yaml(USER_PREFERENCES_PATH, DEFAULT_USER_PREFERENCES)
        preferences["active_automation"] = {
            "task_name": legacy_payload.get("task_name", DEFAULT_AUTOMATION_CONFIG["task_name"]),
            "filename": target_path.name,
        }
        save_user_preferences(preferences)
    return target_path


def load_automation_config(path: Path | None = None) -> dict[str, Any]:
    config_path = path or current_automation_config_path()
    config = load_yaml(config_path, DEFAULT_AUTOMATION_CONFIG)
    config["time_range"] = normalize_time_range(config.get("time_range", "7d"))
    config["quality_profile"] = normalize_quality_profile(config.get("quality_profile"))
    config["language"] = normalize_language(config.get("language"))
    config.setdefault("runner", DEFAULT_AUTOMATION_CONFIG["runner"])
    config.setdefault("exclude_previous_output_papers", DEFAULT_AUTOMATION_CONFIG["exclude_previous_output_papers"])
    config.setdefault("history_scope", DEFAULT_AUTOMATION_CONFIG["history_scope"])
    return config


def save_automation_config(config: dict[str, Any], path: Path | None = None) -> Path:
    payload = deep_merge(DEFAULT_AUTOMATION_CONFIG, config)
    payload["time_range"] = normalize_time_range(payload.get("time_range", "7d"))
    payload["quality_profile"] = normalize_quality_profile(payload.get("quality_profile"))
    payload["language"] = normalize_language(payload.get("language"))
    target_path = path or automation_config_path_for_task(str(payload.get("task_name") or DEFAULT_AUTOMATION_CONFIG["task_name"]))
    save_yaml(target_path, payload)
    save_automation_index({"active_config": target_path.name})
    return target_path


def list_automation_config_paths(enabled_only: bool = False) -> list[Path]:
    ensure_project_layout()
    paths = sorted(
        path
        for path in AUTOMATIONS_DIR.glob("*.yaml")
        if path.is_file() and path.name != AUTOMATION_INDEX_PATH.name
    )
    if not enabled_only:
        return paths
    enabled_paths: list[Path] = []
    for path in paths:
        config = load_automation_config(path)
        if config.get("enabled", True):
            enabled_paths.append(path)
    return enabled_paths


def load_execution_profiles() -> dict[str, Any]:
    payload = load_yaml(EXECUTION_PROFILES_PATH, DEFAULT_EXECUTION_PROFILES)
    payload = deep_merge(DEFAULT_EXECUTION_PROFILES, payload)
    profiles = payload.setdefault("profiles", {})
    for name in QUALITY_PROFILE_OPTIONS:
        profiles.setdefault(name, deepcopy(DEFAULT_EXECUTION_PROFILES["profiles"][name]))
    payload.setdefault("task_defaults", deepcopy(DEFAULT_EXECUTION_PROFILES["task_defaults"]))
    recommendations = payload.setdefault("recommendations", {})
    if "daily_scan" not in recommendations and "daily_top10" in recommendations:
        recommendations["daily_scan"] = recommendations["daily_top10"]
    return payload


def normalize_quality_profile(value: str | None, task_type: str | None = None) -> str:
    if value in QUALITY_PROFILE_OPTIONS:
        return str(value)
    execution_profiles = load_execution_profiles()
    defaults = execution_profiles.get("task_defaults", {})
    if task_type and defaults.get(task_type) in QUALITY_PROFILE_OPTIONS:
        return defaults[task_type]
    return DEFAULT_QUALITY_PROFILE


def default_quality_for_task(task_type: str) -> str:
    execution_profiles = load_execution_profiles()
    defaults = execution_profiles.get("task_defaults", {})
    return normalize_quality_profile(defaults.get(task_type), task_type=task_type)


def resolve_quality_profile(value: str | None, task_type: str | None = None) -> dict[str, Any]:
    normalized = normalize_quality_profile(value, task_type=task_type)
    execution_profiles = load_execution_profiles()
    profile = deepcopy(execution_profiles["profiles"][normalized])
    profile["name"] = normalized
    return profile


def load_user_preferences() -> dict[str, Any]:
    payload = load_yaml(USER_PREFERENCES_PATH, DEFAULT_USER_PREFERENCES)
    payload = deep_merge(DEFAULT_USER_PREFERENCES, payload)
    payload["language"] = normalize_language(payload.get("language"))
    global_defaults = payload.setdefault("global_defaults", {})
    global_defaults.setdefault("field", DEFAULT_DAILY_PROFILE["field"])
    global_defaults.setdefault("time_range_key", "7d")
    global_defaults.setdefault("sources", deepcopy(DEFAULT_SOURCES))
    global_defaults.setdefault("ranking_profile", DEFAULT_RANKING_PROFILE)
    global_defaults.setdefault("constraints", deepcopy(DEFAULT_DAILY_PROFILE["constraints"]))
    global_defaults.setdefault("top_k", DEFAULT_TOP_K)
    task_defaults = payload.setdefault("task_defaults", {})
    for task_name, task_default in DEFAULT_USER_PREFERENCES["task_defaults"].items():
        task_defaults[task_name] = deep_merge(task_default, task_defaults.get(task_name, {}))
        if "quality_profile" in task_defaults[task_name]:
            task_defaults[task_name]["quality_profile"] = normalize_quality_profile(
                task_defaults[task_name].get("quality_profile"),
                task_type=task_name if task_name != "automation" else "automation",
            )
    task_defaults["paper_reader"]["summary_depth"] = normalize_summary_depth(task_defaults["paper_reader"].get("summary_depth"))
    task_defaults["idea_feasibility"]["risk_preference"] = normalize_risk_preference(
        task_defaults["idea_feasibility"].get("risk_preference")
    )
    active_automation = payload.setdefault("active_automation", {})
    current_path = current_automation_config_path()
    current_config = load_yaml(current_path, DEFAULT_AUTOMATION_CONFIG)
    active_automation["task_name"] = current_config.get("task_name", active_automation.get("task_name") or DEFAULT_AUTOMATION_CONFIG["task_name"])
    active_automation["filename"] = current_path.name
    return payload


def save_user_preferences(preferences: dict[str, Any]) -> None:
    payload = deep_merge(DEFAULT_USER_PREFERENCES, preferences)
    payload["language"] = normalize_language(payload.get("language"))
    global_defaults = payload.setdefault("global_defaults", {})
    global_defaults.setdefault("constraints", deepcopy(DEFAULT_DAILY_PROFILE["constraints"]))
    task_defaults = payload.setdefault("task_defaults", {})
    for task_name, task_default in DEFAULT_USER_PREFERENCES["task_defaults"].items():
        task_defaults[task_name] = deep_merge(task_default, task_defaults.get(task_name, {}))
        if "quality_profile" in task_defaults[task_name]:
            task_defaults[task_name]["quality_profile"] = normalize_quality_profile(
                task_defaults[task_name].get("quality_profile"),
                task_type=task_name if task_name != "automation" else "automation",
            )
    task_defaults["paper_reader"]["summary_depth"] = normalize_summary_depth(task_defaults["paper_reader"].get("summary_depth"))
    task_defaults["idea_feasibility"]["risk_preference"] = normalize_risk_preference(
        task_defaults["idea_feasibility"].get("risk_preference")
    )
    save_yaml(USER_PREFERENCES_PATH, payload)


def update_user_preferences(updates: dict[str, Any]) -> dict[str, Any]:
    payload = deep_merge(load_user_preferences(), updates)
    save_user_preferences(payload)
    return load_user_preferences()


def load_app_update_config() -> dict[str, Any]:
    payload = load_yaml(APP_UPDATE_CONFIG_PATH, DEFAULT_APP_UPDATE_CONFIG)
    payload = deep_merge(DEFAULT_APP_UPDATE_CONFIG, payload)
    payload["provider"] = str(payload.get("provider") or "github_release").strip() or "github_release"
    payload["github_repo"] = str(payload.get("github_repo") or "").strip().strip("/")
    payload["github_asset_pattern"] = str(payload.get("github_asset_pattern") or "").strip() or "ResearchAssistant-macos-*.pkg"
    payload["github_token_env"] = str(payload.get("github_token_env") or "").strip()
    payload["manifest_url"] = str(payload.get("manifest_url") or "").strip()
    payload["channel"] = str(payload.get("channel") or "stable").strip() or "stable"
    payload["check_on_launch"] = bool(payload.get("check_on_launch", True))
    payload["check_interval_hours"] = max(1, int(payload.get("check_interval_hours") or 24))
    payload["download_in_app"] = bool(payload.get("download_in_app", True))
    payload["open_download_in_browser"] = bool(payload.get("open_download_in_browser", False))
    return payload


def load_interesting_papers() -> dict[str, Any]:
    payload = load_json(INTERESTING_PAPERS_PATH, DEFAULT_INTERESTING_PAPERS)
    if isinstance(payload, list):
        payload = {"updated_at": None, "items": payload}
    payload.setdefault("updated_at", None)
    payload.setdefault("items", [])
    return payload


def save_interesting_papers(payload: dict[str, Any]) -> None:
    payload = deepcopy(payload)
    payload["updated_at"] = now_iso()
    payload.setdefault("items", [])
    save_json(INTERESTING_PAPERS_PATH, payload)


def add_interesting_paper(item: dict[str, Any]) -> bool:
    payload = load_interesting_papers()
    items = payload["items"]
    dedupe_key = f"{item.get('paper_url', '').strip().lower()}||{item.get('title', '').strip().lower()}"
    for existing in items:
        existing_key = (
            f"{existing.get('paper_url', '').strip().lower()}||"
            f"{existing.get('title', '').strip().lower()}"
        )
        if existing_key == dedupe_key:
            return False
    new_item = deepcopy(item)
    new_item.setdefault("saved_at", now_iso())
    items.append(new_item)
    save_interesting_papers(payload)
    return True


def remove_interesting_paper(identifier: str) -> bool:
    payload = load_interesting_papers()
    before = len(payload["items"])
    lowered = identifier.strip().lower()
    payload["items"] = [
        item
        for item in payload["items"]
        if lowered
        not in {
            (item.get("paper_url") or "").strip().lower(),
            (item.get("title") or "").strip().lower(),
            (item.get("id") or "").strip().lower(),
        }
    ]
    if len(payload["items"]) == before:
        return False
    save_interesting_papers(payload)
    return True
