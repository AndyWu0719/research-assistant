from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from desktop.runtime import configure_runtime_environment
from research_assistant.app_update import check_for_updates
from research_assistant.automation_runtime import automation_schedule_snapshot, daemon_snapshot
from research_assistant.codex_bridge import PaperFetcherInput, detect_codex_cli, run_paper_fetch
from research_assistant.file_naming import smoke_report_path
from research_assistant.config_store import ensure_project_layout
from desktop.app import ResearchAssistantWindow


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a basic smoke test for the native desktop app.")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--reference", default="2401.00001", help="Paper reference used for resolve-only PDF smoke check.")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero when network-based PDF resolve fails.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = configure_runtime_environment()
    ensure_project_layout()

    app = QApplication.instance() or QApplication([])
    window = ResearchAssistantWindow()
    window.close()
    app.quit()

    codex_status = detect_codex_cli(refresh=True, language=args.language).to_dict()
    daemon_status = daemon_snapshot()
    schedule_status = automation_schedule_snapshot()
    update_status = check_for_updates()
    fetch_response = run_paper_fetch(
        PaperFetcherInput(
            reference=args.reference,
            resolve_only=True,
            quality_profile="economy",
            language=args.language,
        )
    )

    report = {
        "project_root": str(project_root),
        "status": "success",
        "window_title": window.windowTitle(),
        "checks": {
            "desktop_window": {
                "status": "success",
                "message": "Native desktop window instantiated successfully.",
            },
            "codex_cli": codex_status,
            "scheduler": {
                "daemon": daemon_status,
                "schedule": schedule_status,
            },
            "app_update": update_status,
            "pdf_fetch_resolve_only": fetch_response.to_dict(),
        },
    }

    if fetch_response.status != "success":
        report["status"] = "partial"

    report_path = smoke_report_path()
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"status": report["status"], "report_path": str(report_path)}, ensure_ascii=False, indent=2))

    if args.strict and fetch_response.status != "success":
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
