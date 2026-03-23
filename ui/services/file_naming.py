from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from ui.services.config_store import OUTPUTS_DIR


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


def top10_output_path(field: str, ranking_profile: str) -> Path:
    filename = f"{today_str()}-{slugify(field)}-{slugify(ranking_profile)}.md"
    return OUTPUTS_DIR / "daily_top10" / filename


def paper_summary_output_path(reference_slug: str) -> Path:
    filename = f"{slugify(reference_slug)}-zh.md"
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
