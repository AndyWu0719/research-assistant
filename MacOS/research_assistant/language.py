from __future__ import annotations

from typing import Any


DEFAULT_LANGUAGE = "zh-CN"
LANGUAGE_OPTIONS: dict[str, dict[str, str]] = {
    "zh-CN": {
        "label": "中文",
        "display": "中文",
        "prompt_label": "中文",
        "english_label": "Chinese",
    },
    "en-US": {
        "label": "English",
        "display": "English",
        "prompt_label": "英文",
        "english_label": "English",
    },
}


def normalize_language(value: str | None) -> str:
    if value in LANGUAGE_OPTIONS:
        return str(value)
    lowered = (value or "").strip().lower()
    if lowered in {"zh", "zh-cn", "zh_hans", "chinese"}:
        return "zh-CN"
    if lowered in {"en", "en-us", "english"}:
        return "en-US"
    return DEFAULT_LANGUAGE


def language_label(value: str | None, ui_language: str | None = None) -> str:
    normalized = normalize_language(value)
    if normalize_language(ui_language) == "en-US":
        return LANGUAGE_OPTIONS[normalized]["english_label"]
    return LANGUAGE_OPTIONS[normalized]["label"]


def language_display_name(value: str | None) -> str:
    normalized = normalize_language(value)
    return LANGUAGE_OPTIONS[normalized]["display"]


def prompt_language_instruction(value: str | None) -> str:
    normalized = normalize_language(value)
    if normalized == "en-US":
        return (
            "All user-visible output for this task must be in English. Keep paper titles, model names, repository names, and dataset names in their original form. "
            "If the evidence is insufficient, explicitly write uncertainty / not enough evidence."
        )
    return "所有用户可见输出默认使用中文；论文标题、模型名、仓库名、数据集名保留原文。"


def language_suffix(value: str | None) -> str:
    normalized = normalize_language(value)
    return "en" if normalized == "en-US" else "zh"


def merge_language(payload: dict[str, Any], language: str | None) -> dict[str, Any]:
    merged = dict(payload)
    merged["language"] = normalize_language(language)
    return merged
