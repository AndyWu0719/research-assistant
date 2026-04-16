from __future__ import annotations

import os
import shlex
import stat
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from research_assistant.language import normalize_language


APP_NAME = "Research Assistant"


def _is_english(language: str | None) -> bool:
    return normalize_language(language) == "en-US"


def _message(zh_cn: str, en_us: str, language: str | None) -> str:
    return en_us if _is_english(language) else zh_cn


def _runtime_platform(platform_override: str | None = None) -> str:
    value = str(platform_override or "").strip().lower()
    if value in {"macos", "windows"}:
        return value
    if os.name == "nt" or sys.platform.startswith("win"):
        return "windows"
    if sys.platform == "darwin":
        return "macos"
    return "unsupported"


def _macos_bundle_path(executable: str | Path | None = None) -> Path | None:
    target = Path(executable or sys.executable).expanduser().resolve()
    try:
        if target.parents[0].name == "MacOS" and target.parents[1].name == "Contents" and target.parents[2].suffix == ".app":
            return target.parents[2]
    except IndexError:
        return None
    return None


def _default_windows_restart_exe() -> Path:
    local_app_data = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
    return local_app_data / "Programs" / APP_NAME / f"{APP_NAME}.exe"


def build_macos_update_script(pkg_path: Path, app_pid: int, relaunch_app: Path) -> str:
    install_cmd = f"/usr/sbin/installer -pkg {shlex.quote(str(pkg_path))} -target /"
    escaped_install_cmd = install_cmd.replace("\\", "\\\\").replace('"', '\\"')
    applescript = f'do shell script "{escaped_install_cmd}" with administrator privileges'
    return "\n".join(
        [
            "#!/bin/bash",
            "set -euo pipefail",
            f"APP_PID={app_pid}",
            f"APP_PATH={shlex.quote(str(relaunch_app))}",
            "",
            'while kill -0 "$APP_PID" 2>/dev/null; do',
            "  sleep 1",
            "done",
            "",
            f"/usr/bin/osascript -e {shlex.quote(applescript)}",
            "sleep 2",
            'if [ -d "$APP_PATH" ]; then',
            '  open -a "$APP_PATH" || true',
            "fi",
            "",
        ]
    )


def build_windows_update_script(installer_path: Path, app_pid: int, restart_exe: Path) -> str:
    return "\r\n".join(
        [
            "@echo off",
            "setlocal",
            f'set "APP_PID={app_pid}"',
            f'set "INSTALLER_PATH={installer_path}"',
            f'set "RESTART_EXE={restart_exe}"',
            "",
            ":wait_loop",
            'tasklist /FI "PID eq %APP_PID%" 2>NUL | find "%APP_PID%" >NUL',
            "if not errorlevel 1 (",
            "  timeout /t 1 /nobreak >NUL",
            "  goto wait_loop",
            ")",
            'start "" /wait "%INSTALLER_PATH%" /S',
            "if errorlevel 1 exit /b %errorlevel%",
            'if exist "%RESTART_EXE%" start "" "%RESTART_EXE%"',
            "endlocal",
            "",
        ]
    )


def _write_launcher(text: str, suffix: str, executable: bool) -> Path:
    temp_dir = Path(tempfile.mkdtemp(prefix="research-assistant-update-"))
    path = temp_dir / f"apply-update{suffix}"
    path.write_text(text, encoding="utf-8", newline="\n" if suffix == ".sh" else "\r\n")
    if executable:
        path.chmod(path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return path


def start_in_place_update(
    download_path: str | Path,
    *,
    app_pid: int | None = None,
    current_executable: str | Path | None = None,
    language: str | None = None,
    platform_override: str | None = None,
) -> dict[str, Any]:
    target = Path(download_path).expanduser().resolve()
    if not target.exists():
        return {
            "status": "error",
            "message": _message("更新包不存在。", "The downloaded update package does not exist.", language),
            "should_exit": False,
        }

    platform = _runtime_platform(platform_override)
    pid = int(app_pid or os.getpid())

    if platform == "macos":
        if target.suffix.lower() != ".pkg":
            return {
                "status": "unsupported",
                "message": _message("当前 macOS 更新仅支持 `.pkg` 安装包。", "macOS in-place updates currently support `.pkg` installers only.", language),
                "should_exit": False,
            }
        bundle_path = _macos_bundle_path(current_executable)
        if bundle_path is None:
            return {
                "status": "unsupported",
                "message": _message("只有打包后的 macOS 应用才支持原地更新。", "In-place macOS updates are only supported from the packaged app.", language),
                "should_exit": False,
            }
        launcher = _write_launcher(build_macos_update_script(target, pid, bundle_path), ".sh", executable=True)
        subprocess.Popen(["/bin/bash", str(launcher)], cwd=launcher.parent, start_new_session=True)
        return {
            "status": "started",
            "message": _message(
                "安装器已准备好。应用即将退出，并请求系统授权后自动覆盖安装。",
                "The installer is ready. The app will quit and request system authorization to replace the current installation.",
                language,
            ),
            "launcher_path": str(launcher),
            "should_exit": True,
        }

    if platform == "windows":
        if target.suffix.lower() != ".exe":
            return {
                "status": "unsupported",
                "message": _message("当前 Windows 更新仅支持 `.exe` 安装包。", "Windows in-place updates currently support `.exe` installers only.", language),
                "should_exit": False,
            }
        executable = Path(current_executable or sys.executable).expanduser().resolve()
        restart_exe = executable if executable.suffix.lower() == ".exe" else _default_windows_restart_exe()
        launcher = _write_launcher(build_windows_update_script(target, pid, restart_exe), ".cmd", executable=False)
        if hasattr(os, "startfile"):
            os.startfile(str(launcher))  # type: ignore[attr-defined]
        else:
            subprocess.Popen(["cmd", "/c", "start", "", str(launcher)], cwd=launcher.parent, start_new_session=True)
        return {
            "status": "started",
            "message": _message(
                "安装器已准备好。应用即将退出，并自动静默覆盖安装当前版本。",
                "The installer is ready. The app will quit and silently replace the current installation.",
                language,
            ),
            "launcher_path": str(launcher),
            "should_exit": True,
        }

    return {
        "status": "unsupported",
        "message": _message("当前平台暂不支持原地更新。", "In-place updates are not supported on this platform.", language),
        "should_exit": False,
    }
