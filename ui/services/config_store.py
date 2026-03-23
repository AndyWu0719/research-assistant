from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml


ROOT = Path(__file__).resolve().parents[2]
AGENTS_PATH = ROOT / "AGENTS.md"
SKILLS_DIR = ROOT / "skills"
CONFIGS_DIR = ROOT / "configs"
OUTPUTS_DIR = ROOT / "outputs"
UI_DIR = ROOT / "ui"

DAILY_PROFILE_PATH = CONFIGS_DIR / "daily_profile.yaml"
AUTOMATIONS_DIR = CONFIGS_DIR / "automations"
AUTOMATION_CONFIG_PATH = AUTOMATIONS_DIR / "daily_top10.yaml"
INTERESTING_PAPERS_PATH = CONFIGS_DIR / "interesting_papers.json"
EXECUTION_PROFILES_PATH = CONFIGS_DIR / "execution_profiles.yaml"
RANKING_PROFILES_PATH = CONFIGS_DIR / "ranking_profiles.md"
SOURCE_POLICIES_PATH = CONFIGS_DIR / "source_policies.md"

DEFAULT_LANGUAGE = "zh-CN"
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

DEFAULT_DAILY_PROFILE: dict[str, Any] = {
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
        "directory": "outputs/daily_top10",
        "filename_template": "YYYY-MM-DD-<field>-<ranking_profile>.md",
    },
    "language": DEFAULT_LANGUAGE,
    "top_k": DEFAULT_TOP_K,
}

DEFAULT_AUTOMATION_CONFIG: dict[str, Any] = {
    "task_name": "每日 Top10 文献巡检",
    "field": DEFAULT_DAILY_PROFILE["field"],
    "time_range": DEFAULT_DAILY_PROFILE["time_range"],
    "sources": deepcopy(DEFAULT_DAILY_PROFILE["sources"]),
    "ranking_profile": DEFAULT_DAILY_PROFILE["ranking_profile"],
    "quality_profile": DEFAULT_QUALITY_PROFILE,
    "constraints": deepcopy(DEFAULT_DAILY_PROFILE["constraints"]),
    "top_k": DEFAULT_TOP_K,
    "schedule": {
        "timezone": "Asia/Hong_Kong",
        "time_of_day": "09:00",
        "cadence": "daily",
    },
    "enabled": True,
    "auto_download_interesting": False,
    "generated_prompt_target": "Codex app Automations",
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
            "description": "默认平衡档，适合常规 Top10 巡检和常规论文总结。",
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
        "topic_mapper": "high-accuracy",
        "idea_feasibility": "high-accuracy",
        "constraint_explorer": "high-accuracy",
    },
    "recommendations": {
        "daily_top10": "建议优先 balanced；若只做轻量巡检可改 economy。",
        "paper_reader": "常规精读建议 balanced；重要论文深读再切到 high-accuracy。",
        "deep_reports": "跨论文综合、方向地图、可行性分析优先 high-accuracy。",
        "automation": "每日自动化默认不要用 max-analysis，避免持续高成本运行。",
    },
}


def ensure_project_layout() -> None:
    directories = [
        CONFIGS_DIR,
        AUTOMATIONS_DIR,
        OUTPUTS_DIR / "daily_top10",
        OUTPUTS_DIR / "paper_summaries",
        OUTPUTS_DIR / "topic_maps",
        OUTPUTS_DIR / "feasibility_reports",
        OUTPUTS_DIR / "constraint_reports",
        OUTPUTS_DIR / "pdfs",
        OUTPUTS_DIR / "prompt_requests" / "literature_scout",
        OUTPUTS_DIR / "prompt_requests" / "paper_reader",
        OUTPUTS_DIR / "prompt_requests" / "topic_mapper",
        OUTPUTS_DIR / "prompt_requests" / "idea_feasibility",
        OUTPUTS_DIR / "prompt_requests" / "constraint_explorer",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)

    if not DAILY_PROFILE_PATH.exists():
        save_yaml(DAILY_PROFILE_PATH, DEFAULT_DAILY_PROFILE)
    if not AUTOMATION_CONFIG_PATH.exists():
        save_yaml(AUTOMATION_CONFIG_PATH, DEFAULT_AUTOMATION_CONFIG)
    if not INTERESTING_PAPERS_PATH.exists():
        save_json(INTERESTING_PAPERS_PATH, DEFAULT_INTERESTING_PAPERS)
    if not EXECUTION_PROFILES_PATH.exists():
        save_yaml(EXECUTION_PROFILES_PATH, DEFAULT_EXECUTION_PROFILES)


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


def load_daily_profile() -> dict[str, Any]:
    profile = load_yaml(DAILY_PROFILE_PATH, DEFAULT_DAILY_PROFILE)
    profile["time_range"] = normalize_time_range(profile.get("time_range", "7d"))
    profile.setdefault("sources", deepcopy(DEFAULT_SOURCES))
    profile.setdefault("ranking_profile", DEFAULT_RANKING_PROFILE)
    profile["quality_profile"] = normalize_quality_profile(profile.get("quality_profile"))
    profile.setdefault("language", DEFAULT_LANGUAGE)
    profile.setdefault("top_k", DEFAULT_TOP_K)
    return profile


def save_daily_profile(profile: dict[str, Any]) -> None:
    payload = deep_merge(DEFAULT_DAILY_PROFILE, profile)
    payload["time_range"] = normalize_time_range(payload.get("time_range", "7d"))
    payload["quality_profile"] = normalize_quality_profile(payload.get("quality_profile"))
    save_yaml(DAILY_PROFILE_PATH, payload)


def load_automation_config() -> dict[str, Any]:
    config = load_yaml(AUTOMATION_CONFIG_PATH, DEFAULT_AUTOMATION_CONFIG)
    config["time_range"] = normalize_time_range(config.get("time_range", "7d"))
    config["quality_profile"] = normalize_quality_profile(config.get("quality_profile"))
    return config


def save_automation_config(config: dict[str, Any]) -> None:
    payload = deep_merge(DEFAULT_AUTOMATION_CONFIG, config)
    payload["time_range"] = normalize_time_range(payload.get("time_range", "7d"))
    payload["quality_profile"] = normalize_quality_profile(payload.get("quality_profile"))
    save_yaml(AUTOMATION_CONFIG_PATH, payload)


def load_execution_profiles() -> dict[str, Any]:
    payload = load_yaml(EXECUTION_PROFILES_PATH, DEFAULT_EXECUTION_PROFILES)
    payload = deep_merge(DEFAULT_EXECUTION_PROFILES, payload)
    profiles = payload.setdefault("profiles", {})
    for name in QUALITY_PROFILE_OPTIONS:
        profiles.setdefault(name, deepcopy(DEFAULT_EXECUTION_PROFILES["profiles"][name]))
    payload.setdefault("task_defaults", deepcopy(DEFAULT_EXECUTION_PROFILES["task_defaults"]))
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
