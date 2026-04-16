from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from research_assistant.codex_bridge import LiteratureScoutInput, PaperFetcherInput, run_literature_scout, run_paper_fetch
from research_assistant.config_store import (
    LEGACY_LITERATURE_SCAN_OUTPUT_DIR,
    LITERATURE_SCAN_OUTPUT_DIR,
    OUTPUTS_DIR,
    ROOT,
    automation_history_path,
    current_automation_config_path,
    ensure_project_layout,
    list_automation_config_paths,
    load_automation_config,
    load_automation_runtime_state,
    load_interesting_papers,
    load_json,
    now_iso,
    save_automation_runtime_state,
    save_json,
)
from research_assistant.ui_text import is_english


DEFAULT_POLL_INTERVAL_SECONDS = 60


def _normalize_token(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())


def _time_zone(name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(str(name or "Asia/Hong_Kong"))
    except Exception:
        return ZoneInfo("UTC")


def _parse_run_time(value: str | None) -> tuple[int, int]:
    raw = str(value or "09:00").strip()
    try:
        hour_str, minute_str = raw.split(":", 1)
        hour = min(max(int(hour_str), 0), 23)
        minute = min(max(int(minute_str), 0), 59)
        return hour, minute
    except ValueError:
        return 9, 0


def _config_key(config_path: Path) -> str:
    return config_path.name


def list_history_candidates(config: dict[str, Any]) -> list[dict[str, str]]:
    field_token = _normalize_token(config.get("field"))
    history_scope = str(config.get("history_scope") or "same-field").strip().lower()
    ranking_token = _normalize_token(config.get("ranking_profile"))
    seen: set[str] = set()
    items: list[dict[str, str]] = []

    sidecar_paths: list[Path] = []
    for directory in (LITERATURE_SCAN_OUTPUT_DIR, LEGACY_LITERATURE_SCAN_OUTPUT_DIR):
        if directory.exists():
            sidecar_paths.extend(directory.glob("*.json"))

    for sidecar_path in sorted(sidecar_paths, key=lambda item: item.stat().st_mtime, reverse=True):
        payload = load_json(sidecar_path, {})
        if not isinstance(payload, dict):
            continue
        papers = payload.get("papers")
        if not isinstance(papers, list):
            continue
        if history_scope == "same-field" and field_token and _normalize_token(payload.get("field")) != field_token:
            continue
        if history_scope == "same-field-and-ranking":
            if field_token and _normalize_token(payload.get("field")) != field_token:
                continue
            if ranking_token and _normalize_token(payload.get("ranking_profile")) != ranking_token:
                continue

        for paper in papers:
            if not isinstance(paper, dict):
                continue
            title = str(paper.get("title") or "").strip()
            paper_url = str(paper.get("paper_url") or "").strip()
            if not title and not paper_url:
                continue
            dedupe_key = f"{title.lower()}||{paper_url.lower()}"
            if dedupe_key in seen:
                continue
            seen.add(dedupe_key)
            items.append(
                {
                    "title": title,
                    "paper_url": paper_url,
                    "source_file": str(sidecar_path.with_suffix(".md")),
                }
            )
    return items


def refresh_history_index(config: dict[str, Any], config_path: Path | None = None) -> dict[str, Any]:
    ensure_project_layout()
    path = automation_history_path(config_path)
    if not config.get("exclude_previous_output_papers", True):
        payload = {
            "task_name": config.get("task_name"),
            "field": config.get("field"),
            "ranking_profile": config.get("ranking_profile"),
            "history_scope": config.get("history_scope"),
            "updated_at": now_iso(),
            "items": [],
        }
        save_json(path, payload)
        return payload

    items = list_history_candidates(config)
    payload = {
        "task_name": config.get("task_name"),
        "field": config.get("field"),
        "ranking_profile": config.get("ranking_profile"),
        "history_scope": config.get("history_scope"),
        "updated_at": now_iso(),
        "items": items,
    }
    save_json(path, payload)
    return payload


def download_interesting_papers(config: dict[str, Any]) -> dict[str, Any]:
    if not config.get("auto_download_interesting", False):
        return {"attempted": 0, "downloaded": 0, "errors": []}

    interesting = load_interesting_papers()
    attempted = 0
    downloaded = 0
    errors: list[str] = []
    for item in interesting.get("items", []):
        reference = str(item.get("paper_url") or "").strip()
        if not reference:
            continue
        attempted += 1
        response = run_paper_fetch(
            PaperFetcherInput(
                reference=reference,
                output_dir=OUTPUTS_DIR / "pdfs",
                quality_profile="economy",
                language=config.get("language"),
            )
        )
        if response.status == "success":
            downloaded += 1
        else:
            errors.append(response.error or response.message)
    return {
        "attempted": attempted,
        "downloaded": downloaded,
        "errors": errors[:5],
    }


def automation_schedule_snapshot(config_path: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    ensure_project_layout()
    resolved_path = config_path or current_automation_config_path()
    config = load_automation_config(resolved_path)
    runtime_state = load_automation_runtime_state()
    config_state = runtime_state.get("configs", {}).get(_config_key(resolved_path), {})
    zone = _time_zone(config.get("schedule", {}).get("timezone"))
    current = now.astimezone(zone) if now else datetime.now(zone)
    hour, minute = _parse_run_time(config.get("schedule", {}).get("time_of_day"))
    scheduled_today = current.replace(hour=hour, minute=minute, second=0, microsecond=0)
    last_attempt_local_date = str(config_state.get("last_attempt_local_date") or "")

    if current < scheduled_today:
        next_run = scheduled_today
    elif last_attempt_local_date != current.date().isoformat():
        next_run = current
    else:
        next_run = scheduled_today + timedelta(days=1)

    return {
        "config_path": str(resolved_path),
        "task_name": config.get("task_name"),
        "enabled": bool(config.get("enabled", True)),
        "runner": config.get("runner", "local-scheduler"),
        "timezone": str(zone),
        "scheduled_time": f"{hour:02d}:{minute:02d}",
        "last_attempt_at": config_state.get("last_attempt_at"),
        "last_attempt_local_date": config_state.get("last_attempt_local_date"),
        "last_status": config_state.get("last_status"),
        "last_output": config_state.get("last_output"),
        "next_run_at": next_run.isoformat(timespec="seconds"),
        "due": bool(config.get("enabled", True)) and next_run <= current,
    }


def daemon_snapshot(max_heartbeat_age_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS * 2) -> dict[str, Any]:
    ensure_project_layout()
    payload = load_automation_runtime_state().get("daemon", {})
    heartbeat_raw = payload.get("heartbeat_at")
    is_running = False
    if heartbeat_raw:
        try:
            heartbeat = datetime.fromisoformat(str(heartbeat_raw))
            if heartbeat.tzinfo is None:
                now = datetime.now()
            else:
                now = datetime.now(heartbeat.tzinfo)
            is_running = (now - heartbeat).total_seconds() <= max_heartbeat_age_seconds
        except ValueError:
            is_running = False
    return {
        "pid": payload.get("pid"),
        "started_at": payload.get("started_at"),
        "heartbeat_at": heartbeat_raw,
        "is_running": is_running,
    }


def run_local_automation(config_path: Path | None = None, force: bool = False) -> dict[str, Any]:
    ensure_project_layout()
    resolved_path = config_path or current_automation_config_path()
    config = load_automation_config(resolved_path)
    schedule = automation_schedule_snapshot(resolved_path)
    runtime_state = load_automation_runtime_state()
    config_states = runtime_state.setdefault("configs", {})
    config_state = dict(config_states.get(_config_key(resolved_path), {}))
    zone = _time_zone(config.get("schedule", {}).get("timezone"))
    current = datetime.now(zone)

    if not config.get("enabled", True) and not force:
        return {
            "status": "skipped",
            "message": "Automation is disabled." if is_english(config.get("language")) else "自动化已停用。",
            "config_path": str(resolved_path),
            "due": schedule["due"],
        }
    if not schedule["due"] and not force:
        return {
            "status": "skipped",
            "message": "Automation is not due yet." if is_english(config.get("language")) else "当前还未到自动化执行时间。",
            "config_path": str(resolved_path),
            "due": schedule["due"],
            "next_run_at": schedule["next_run_at"],
        }

    config_state.update(
        {
            "last_attempt_at": current.isoformat(timespec="seconds"),
            "last_attempt_local_date": current.date().isoformat(),
            "last_status": "running",
        }
    )
    config_states[_config_key(resolved_path)] = config_state
    save_automation_runtime_state(runtime_state)

    history_payload = refresh_history_index(config, resolved_path)
    history_path = automation_history_path(resolved_path)
    response = run_literature_scout(
        LiteratureScoutInput(
            field=str(config.get("field") or ""),
            time_range=config.get("time_range") or {},
            sources=list(config.get("sources") or []),
            ranking_profile=str(config.get("ranking_profile") or "balanced-default"),
            constraints=config.get("constraints") or "",
            top_k=int(config.get("top_k") or 10),
            quality_profile=config.get("quality_profile"),
            language=config.get("language"),
            history_exclusion_path=str(history_path),
            history_exclusion_count=len(history_payload.get("items", [])),
        )
    )
    downloads = download_interesting_papers(config)

    runtime_state = load_automation_runtime_state()
    config_states = runtime_state.setdefault("configs", {})
    config_states[_config_key(resolved_path)] = {
        **dict(config_states.get(_config_key(resolved_path), {})),
        "last_attempt_at": current.isoformat(timespec="seconds"),
        "last_attempt_local_date": current.date().isoformat(),
        "last_status": response.status,
        "last_output": str(response.expected_output_path) if response.expected_output_path else None,
        "last_error": response.error,
        "history_exclusion_count": len(history_payload.get("items", [])),
        "last_download_summary": downloads,
    }
    save_automation_runtime_state(runtime_state)

    message = response.message
    if downloads["attempted"]:
        if is_english(config.get("language")):
            message = f"{message} Interesting-paper downloads: {downloads['downloaded']}/{downloads['attempted']}."
        else:
            message = f"{message} 感兴趣论文自动下载：{downloads['downloaded']}/{downloads['attempted']}。"

    return {
        "status": response.status,
        "message": message,
        "config_path": str(resolved_path),
        "history_exclusion_count": len(history_payload.get("items", [])),
        "history_exclusion_path": str(history_path),
        "output_path": str(response.expected_output_path) if response.expected_output_path else None,
        "manifest_path": str(response.manifest_path) if response.manifest_path else None,
        "error": response.error,
        "downloads": downloads,
        "bridge": response.to_dict(),
    }


def run_enabled_automations(force: bool = False, active_only: bool = False) -> list[dict[str, Any]]:
    ensure_project_layout()
    paths = [current_automation_config_path()] if active_only else list_automation_config_paths(enabled_only=False)
    results: list[dict[str, Any]] = []
    for path in paths:
        results.append(run_local_automation(path, force=force))
    return results


def start_scheduler_daemon() -> dict[str, Any]:
    ensure_project_layout()
    snapshot = daemon_snapshot()
    if snapshot["is_running"]:
        return {
            "status": "already_running",
            "pid": snapshot.get("pid"),
            "message": "Local scheduler is already running.",
        }
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "run_automation.py"), "--daemon"],
        cwd=ROOT,
    )
    return {
        "status": "started",
        "pid": process.pid,
        "message": "Local scheduler started.",
    }


def stop_scheduler_daemon() -> dict[str, Any]:
    ensure_project_layout()
    runtime_state = load_automation_runtime_state()
    daemon_state = runtime_state.get("daemon", {})
    pid = daemon_state.get("pid")
    if not pid:
        return {
            "status": "not_running",
            "pid": None,
            "message": "Local scheduler is not running.",
        }
    try:
        os.kill(int(pid), signal.SIGTERM)
    except ProcessLookupError:
        result = {
            "status": "not_running",
            "pid": pid,
            "message": "Local scheduler process was not found.",
        }
    except PermissionError as exc:
        return {
            "status": "error",
            "pid": pid,
            "message": f"Failed to stop local scheduler: {exc}",
        }
    else:
        result = {
            "status": "stopped",
            "pid": pid,
            "message": "Local scheduler stopped.",
        }

    runtime_state["daemon"] = {
        "pid": None,
        "started_at": daemon_state.get("started_at"),
        "heartbeat_at": now_iso(),
    }
    save_automation_runtime_state(runtime_state)
    return result


def run_scheduler_loop(poll_interval_seconds: int = DEFAULT_POLL_INTERVAL_SECONDS, active_only: bool = False) -> None:
    ensure_project_layout()
    interval = max(int(poll_interval_seconds), 15)
    runtime_state = load_automation_runtime_state()
    runtime_state["daemon"] = {
        "pid": os.getpid(),
        "started_at": runtime_state.get("daemon", {}).get("started_at") or now_iso(),
        "heartbeat_at": now_iso(),
    }
    save_automation_runtime_state(runtime_state)

    try:
        while True:
            runtime_state = load_automation_runtime_state()
            runtime_state["daemon"] = {
                "pid": os.getpid(),
                "started_at": runtime_state.get("daemon", {}).get("started_at") or now_iso(),
                "heartbeat_at": now_iso(),
            }
            save_automation_runtime_state(runtime_state)
            run_enabled_automations(force=False, active_only=active_only)
            time.sleep(interval)
    finally:
        runtime_state = load_automation_runtime_state()
        runtime_state["daemon"] = {
            "pid": None,
            "started_at": runtime_state.get("daemon", {}).get("started_at"),
            "heartbeat_at": now_iso(),
        }
        save_automation_runtime_state(runtime_state)
