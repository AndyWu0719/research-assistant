from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from desktop.runtime import configure_runtime_environment


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Launch the native Research Assistant desktop app.")
    parser.add_argument("--version", action="store_true", help="Print the desktop app version, then exit.")
    parser.add_argument("--daemon", action="store_true", help="Run the local automation scheduler loop.")
    parser.add_argument("--force", action="store_true", help="Run automation immediately even if it is not due yet.")
    parser.add_argument("--active-only", action="store_true", help="Only operate on the active automation config.")
    parser.add_argument("--status", action="store_true", help="Print scheduler and automation status, then exit.")
    parser.add_argument("--without-scheduler", action="store_true", help="Reserved for compatibility with the legacy launcher.")
    return parser.parse_args()


def print_status(active_only: bool) -> int:
    from research_assistant.automation_runtime import automation_schedule_snapshot, daemon_snapshot
    from research_assistant.config_store import current_automation_config_path, list_automation_config_paths, load_automation_config

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


def run_headless(args: argparse.Namespace) -> int:
    from research_assistant.automation_runtime import DEFAULT_POLL_INTERVAL_SECONDS, run_enabled_automations, run_local_automation, run_scheduler_loop
    from research_assistant.app_update import current_build_info
    from research_assistant.config_store import current_automation_config_path

    if args.version:
        print(json.dumps(current_build_info(), ensure_ascii=False, indent=2))
        return 0

    if args.status:
        return print_status(active_only=args.active_only)

    if args.daemon:
        run_scheduler_loop(poll_interval_seconds=DEFAULT_POLL_INTERVAL_SECONDS, active_only=args.active_only)
        return 0

    if args.active_only:
        result = run_local_automation(current_automation_config_path(), force=args.force)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("status") in {"success", "skipped"} else 1

    results = run_enabled_automations(force=args.force, active_only=False)
    print(json.dumps({"results": results}, ensure_ascii=False, indent=2))
    return 0 if all(item.get("status") in {"success", "skipped"} for item in results) else 1


def launch_gui() -> int:
    from PySide6.QtWidgets import QApplication

    from desktop.app import ResearchAssistantWindow

    app = QApplication(sys.argv)
    app.setApplicationName("Research Assistant")
    app.setOrganizationName("Andy Wu")
    window = ResearchAssistantWindow()
    window.show()
    return app.exec()


def main() -> int:
    configure_runtime_environment()
    args = parse_args()
    if args.version or args.daemon or args.status or args.force or args.active_only:
        return run_headless(args)
    return launch_gui()


if __name__ == "__main__":
    raise SystemExit(main())
