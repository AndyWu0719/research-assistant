from __future__ import annotations

import hashlib
import os
import re
import shutil
import sys
from pathlib import Path

import yaml


APP_NAME = "Research Assistant"
PROJECT_ROOT_ENV = "RESEARCH_ASSISTANT_PROJECT_ROOT"
BUILD_METADATA_NAME = ".app-build.json"
PRESERVED_PATHS = [
    Path("outputs"),
    Path("configs/app_update.yaml"),
    Path("configs/scan_defaults.yaml"),
    Path("configs/interesting_papers.json"),
    Path("configs/user_preferences.yaml"),
    Path("configs/automations"),
]
IGNORE_TOP_LEVEL = {
    ".git",
    ".venv",
    "venv",
    "env",
    "dist",
    "build",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
}
LEGACY_WORKSPACE_ARTIFACTS = [
    Path("Launch Research Assistant.bat"),
    Path("Launch Research Assistant.command"),
    Path("scripts/install_windows.ps1"),
    Path("packaging/windows"),
    Path("ui"),
    Path(".streamlit"),
]


def source_root() -> Path:
    return Path(__file__).resolve().parents[1]


def is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def bundle_template_root() -> Path:
    if not is_frozen_app():
        return source_root()
    meipass = getattr(sys, "_MEIPASS", None)
    if not meipass:
        raise RuntimeError("打包应用缺少 PyInstaller 运行时资源目录。")
    return Path(meipass).resolve() / "project_template"


def workspace_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME / "workspace"
    if os.name == "nt":
        local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return local_app_data / APP_NAME / "workspace"
    return Path.home() / ".local" / "share" / APP_NAME.lower().replace(" ", "-") / "workspace"


def runtime_project_root() -> Path:
    configured = os.environ.get(PROJECT_ROOT_ENV)
    if configured:
        return Path(configured).expanduser().resolve()
    return source_root()


def load_build_metadata(path: Path) -> str:
    marker = path / BUILD_METADATA_NAME
    if not marker.exists():
        return ""
    return marker.read_text(encoding="utf-8")


def is_preserved(relative_path: Path) -> bool:
    for preserved in PRESERVED_PATHS:
        if relative_path == preserved or preserved in relative_path.parents:
            return True
    return False


def should_ignore(relative_path: Path) -> bool:
    if not relative_path.parts:
        return False
    if relative_path.parts[0] in IGNORE_TOP_LEVEL:
        return True
    if "__pycache__" in relative_path.parts:
        return True
    if relative_path.suffix in {".pyc", ".pyo"}:
        return True
    return relative_path.name == ".DS_Store"


def copy_path(source: Path, destination: Path) -> None:
    if source.is_dir():
        destination.mkdir(parents=True, exist_ok=True)
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, destination)


def _sanitize_filename_fragment(value: str, max_length: int = 56) -> str:
    lowered = (value or "").strip().lower()
    lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff._-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-._")
    if not lowered:
        lowered = "automation-task"
    return lowered[:max_length].rstrip("-._")


def _automation_config_filename(task_name: str) -> str:
    cleaned = _sanitize_filename_fragment(task_name)
    digest = hashlib.sha1((task_name or "").strip().encode("utf-8")).hexdigest()[:8]
    return f"{cleaned}--{digest}.yaml"


def _load_yaml(path: Path) -> dict[str, object]:
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload if isinstance(payload, dict) else {}


def _save_yaml(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(payload, allow_unicode=True, sort_keys=False, width=88),
        encoding="utf-8",
    )


def _replace_text(path: Path, replacements: dict[str, str]) -> None:
    if not path.exists() or not path.is_file():
        return
    try:
        original = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return
    updated = original
    for source, target in replacements.items():
        updated = updated.replace(source, target)
    if updated != original:
        path.write_text(updated, encoding="utf-8")


def _remove_legacy_artifacts(target_root: Path) -> None:
    for relative_path in LEGACY_WORKSPACE_ARTIFACTS:
        candidate = target_root / relative_path
        if candidate.is_dir():
            shutil.rmtree(candidate, ignore_errors=True)
            continue
        candidate.unlink(missing_ok=True)


def migrate_workspace_layout(target_root: Path) -> None:
    _remove_legacy_artifacts(target_root)
    outputs_dir = target_root / "outputs"
    legacy_scan_dir = outputs_dir / "daily_top10"
    scan_dir = outputs_dir / "literature_scans"
    scan_dir.mkdir(parents=True, exist_ok=True)
    (scan_dir / ".gitkeep").touch(exist_ok=True)

    if legacy_scan_dir.exists():
        legacy_gitkeep = legacy_scan_dir / ".gitkeep"
        if legacy_gitkeep.exists():
            legacy_gitkeep.unlink()
        for source in sorted(legacy_scan_dir.iterdir()):
            target = scan_dir / source.name
            if target.exists():
                continue
            shutil.move(str(source), str(target))
        try:
            legacy_scan_dir.rmdir()
        except OSError:
            pass

    prompt_dir = outputs_dir / "prompt_requests" / "literature_scout"
    if prompt_dir.exists():
        for source in sorted(prompt_dir.iterdir()):
            if "top10" not in source.name:
                continue
            target = prompt_dir / source.name.replace("top10", "literature-scan")
            if not target.exists():
                source.rename(target)
        for path in sorted(prompt_dir.iterdir()):
            _replace_text(
                path,
                {
                    "outputs/daily_top10/": "outputs/literature_scans/",
                    "top10-": "literature-scan-",
                },
            )

    for sidecar in scan_dir.glob("*.json"):
        _replace_text(
            sidecar,
            {
                "outputs/daily_top10/": "outputs/literature_scans/",
                "top10-": "literature-scan-",
            },
        )

    legacy_scan_defaults = target_root / "configs" / "daily_profile.yaml"
    scan_defaults = target_root / "configs" / "scan_defaults.yaml"
    if legacy_scan_defaults.exists() and not scan_defaults.exists():
        shutil.move(str(legacy_scan_defaults), str(scan_defaults))
    _replace_text(scan_defaults, {"outputs/daily_top10": "outputs/literature_scans"})

    automations_dir = target_root / "configs" / "automations"
    legacy_automation = automations_dir / "daily_top10.yaml"
    index_path = automations_dir / "index.yaml"
    if legacy_automation.exists():
        payload = _load_yaml(legacy_automation)
        task_name = str(payload.get("task_name") or "每日文献巡检").strip()
        target_path = automations_dir / _automation_config_filename(task_name)
        if target_path != legacy_automation and not target_path.exists():
            shutil.copy2(legacy_automation, target_path)
        index_payload = _load_yaml(index_path)
        active_name = str(index_payload.get("active_config") or "").strip()
        if not active_name or active_name == legacy_automation.name:
            index_payload["active_config"] = target_path.name
            _save_yaml(index_path, index_payload)
        if target_path.exists():
            legacy_automation.unlink(missing_ok=True)


def sync_bundle_to_workspace() -> Path:
    template_root = bundle_template_root()
    if not is_frozen_app():
        return template_root

    target_root = workspace_root()
    target_root.mkdir(parents=True, exist_ok=True)
    if (
        load_build_metadata(target_root) == load_build_metadata(template_root)
        and (target_root / "AGENTS.md").exists()
        and (target_root / "skills").exists()
        and (target_root / "configs").exists()
    ):
        migrate_workspace_layout(target_root)
        return target_root

    for source in sorted(template_root.rglob("*")):
        relative_path = source.relative_to(template_root)
        if should_ignore(relative_path):
            continue
        target_path = target_root / relative_path
        if is_preserved(relative_path) and target_path.exists():
            continue
        copy_path(source, target_path)
    migrate_workspace_layout(target_root)
    return target_root


def configure_runtime_environment() -> Path:
    project_root = sync_bundle_to_workspace()
    os.environ[PROJECT_ROOT_ENV] = str(project_root)
    return project_root


def scheduler_command() -> list[str]:
    if is_frozen_app():
        return [sys.executable, "--daemon"]
    return [sys.executable, str(source_root() / "desktop" / "main.py"), "--daemon"]
