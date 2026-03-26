from __future__ import annotations

import hashlib
import re
from datetime import datetime
from pathlib import Path

from research_assistant.config_store import LITERATURE_SCAN_OUTPUT_DIR, OUTPUTS_DIR
from research_assistant.language import language_suffix


def slugify(value: str, max_length: int = 64) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"\.pdf$", "", lowered)
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff._-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-._")
    if not lowered:
        lowered = "untitled"
    return lowered[:max_length].rstrip("-._")


def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def timestamp_str() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def sidecar_json_path(output_path: Path) -> Path:
    return output_path.with_suffix(".json")


def literature_scan_output_path(field: str, ranking_profile: str) -> Path:
    filename = f"{today_str()}-{slugify(field)}-{slugify(ranking_profile)}.md"
    return LITERATURE_SCAN_OUTPUT_DIR / filename


def paper_summary_output_path(reference_slug: str) -> Path:
    filename = f"{slugify(reference_slug)}-zh.md"
    return OUTPUTS_DIR / "paper_summaries" / filename


def paper_summary_output_path_for_language(reference_slug: str, language: str | None) -> Path:
    filename = f"{slugify(reference_slug)}-{language_suffix(language)}.md"
    return OUTPUTS_DIR / "paper_summaries" / filename


def topic_map_output_path(topic: str, ranking: str) -> Path:
    filename = f"{today_str()}-{slugify(topic)}-{slugify(ranking)}.md"
    return OUTPUTS_DIR / "topic_maps" / filename


def feasibility_output_path(field: str, idea: str) -> Path:
    filename = f"{today_str()}-{slugify(field)}-{slugify(idea, max_length=40)}.md"
    return OUTPUTS_DIR / "feasibility_reports" / filename


def constraint_output_path(field: str) -> Path:
    filename = f"{today_str()}-{slugify(field)}-resource-constrained.md"
    return OUTPUTS_DIR / "constraint_reports" / filename


def prompt_request_path(skill_name: str, subject: str) -> Path:
    filename = f"{timestamp_str()}-{slugify(subject, max_length=48)}.md"
    safe_skill = slugify(skill_name).replace("-", "_")
    return OUTPUTS_DIR / "prompt_requests" / safe_skill / filename


def pdf_text_output_path(reference_slug: str) -> Path:
    filename = f"{slugify(reference_slug, max_length=80)}-cleaned.txt"
    return OUTPUTS_DIR / "pdf_text" / filename


def smoke_report_path(name: str = "desktop-smoke-test") -> Path:
    filename = f"{timestamp_str()}-{slugify(name, max_length=48)}.json"
    return OUTPUTS_DIR / "smoke_tests" / filename


def automation_config_filename(task_name: str) -> str:
    cleaned = slugify(task_name, max_length=56)
    digest = hashlib.sha1(task_name.strip().encode("utf-8")).hexdigest()[:8]
    return f"{cleaned}--{digest}.yaml"
