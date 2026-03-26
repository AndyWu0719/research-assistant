from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from research_assistant.automation_runtime import (
    DEFAULT_POLL_INTERVAL_SECONDS,
    automation_schedule_snapshot,
    daemon_snapshot,
    run_enabled_automations,
    run_local_automation,
    run_scheduler_loop,
)
from research_assistant.config_store import current_automation_config_path, list_automation_config_paths, load_automation_config
from research_assistant.ui_text import is_english


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local daily automation without Codex app automations.")
    parser.add_argument("--daemon", action="store_true", help="Run the local scheduler loop.")
    parser.add_argument("--force", action="store_true", help="Run immediately even if the task is not due yet.")
    parser.add_argument("--active-only", action="store_true", help="Only operate on the current active automation config.")
    parser.add_argument("--poll-interval", type=int, default=DEFAULT_POLL_INTERVAL_SECONDS, help="Daemon polling interval in seconds.")
    parser.add_argument("--status", action="store_true", help="Print scheduler and automation status, then exit.")
    return parser.parse_args()


def print_status(active_only: bool) -> int:
    daemon = daemon_snapshot()
    paths = [current_automation_config_path()] if active_only else list_automation_config_paths(enabled_only=False)
    configs: list[dict[str, object]] = []
    for path in paths:
        config = load_automation_config(path)
        configs.append(
            {
                "config_path": str(path),
                "task_name": config.get("task_name"),
                "enabled": config.get("enabled"),
                "runner": config.get("runner"),
                "exclude_previous_output_papers": config.get("exclude_previous_output_papers"),
                "schedule": automation_schedule_snapshot(path),
            }
        )
    print(json.dumps({"daemon": daemon, "configs": configs}, ensure_ascii=False, indent=2))
    return 0


def main() -> int:
    args = parse_args()
    language = load_automation_config(current_automation_config_path()).get("language")

    if args.status:
        return print_status(active_only=args.active_only)

    if args.daemon:
        print(
            "Starting local automation scheduler." if is_english(language) else "正在启动本地自动化调度器。"
        )
        run_scheduler_loop(poll_interval_seconds=args.poll_interval, active_only=args.active_only)
        return 0

    if args.active_only:
        result = run_local_automation(current_automation_config_path(), force=args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {"success", "skipped"} else 1

    results = run_enabled_automations(force=args.force, active_only=False)
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return 0 if all(item.get("status") in {"success", "skipped"} for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
