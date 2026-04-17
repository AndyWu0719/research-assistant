from __future__ import annotations

import json
import os
import platform
import shlex
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from research_assistant.language import normalize_language
from research_assistant.ui_text import is_english


APP_NAME = "Research Assistant"
NODE_INDEX_URL = "https://nodejs.org/dist/index.json"
NODE_DIST_BASE_URL = "https://nodejs.org/dist"


@dataclass(slots=True)
class CodexSetupResult:
    status: str
    message: str
    codex_executable: str | None = None
    codex_version: str | None = None
    npm_executable: str | None = None
    managed_install: bool = False
    notes: list[str] = field(default_factory=list)
    error: str | None = None
    login_script_path: str | None = None
    opened_terminal: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def support_root() -> Path:
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME
    if os.name == "nt":
        local_app_data_raw = os.environ.get("LOCALAPPDATA")
        local_app_data = Path(local_app_data_raw) if local_app_data_raw else Path.home() / "AppData" / "Local"
        return local_app_data / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME.lower().replace(" ", "-")


def codex_runtime_root() -> Path:
    return support_root() / "runtime" / "codex"


def codex_setup_state_path() -> Path:
    return codex_runtime_root() / "setup-state.json"


def managed_node_runtime_dir() -> Path:
    return codex_runtime_root() / "node-runtime"


def managed_npm_prefix() -> Path:
    return codex_runtime_root() / "npm-global"


def managed_npm_cache_dir() -> Path:
    return codex_runtime_root() / "npm-cache"


def managed_codex_executable() -> Path:
    if os.name == "nt":
        return managed_npm_prefix() / "codex.cmd"
    return managed_npm_prefix() / "bin" / "codex"


def managed_npm_executable() -> Path:
    if os.name == "nt":
        return managed_node_runtime_dir() / "npm.cmd"
    return managed_node_runtime_dir() / "bin" / "npm"


def managed_node_executable() -> Path:
    if os.name == "nt":
        return managed_node_runtime_dir() / "node.exe"
    return managed_node_runtime_dir() / "bin" / "node"


def managed_node_bin_dir() -> Path:
    if os.name == "nt":
        return managed_node_runtime_dir()
    return managed_node_runtime_dir() / "bin"


def managed_codex_bin_dir() -> Path:
    if os.name == "nt":
        return managed_npm_prefix()
    return managed_npm_prefix() / "bin"


def managed_login_script_path() -> Path:
    if os.name == "nt":
        return codex_runtime_root() / "Launch Codex Login.bat"
    return codex_runtime_root() / "Launch Codex Login.command"


def load_codex_setup_state() -> dict[str, Any]:
    path = codex_setup_state_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_codex_setup_state(payload: dict[str, Any]) -> None:
    path = codex_setup_state_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def mark_auto_prepare_attempt(app_version: str) -> None:
    payload = load_codex_setup_state()
    payload["last_auto_prepare_version"] = str(app_version or "").strip()
    save_codex_setup_state(payload)


def should_auto_prepare(app_version: str) -> bool:
    payload = load_codex_setup_state()
    return str(payload.get("last_auto_prepare_version") or "").strip() != str(app_version or "").strip()


def _localized(zh_cn: str, en_us: str, language: str) -> str:
    return en_us if is_english(language) else zh_cn


def _detect_language(language: str | None = None) -> str:
    return normalize_language(language or "zh-CN")


def _candidate_paths() -> list[Path]:
    if os.name == "nt":
        app_data_raw = os.environ.get("APPDATA")
        local_app_data_raw = os.environ.get("LOCALAPPDATA")
        app_data = Path(app_data_raw) if app_data_raw else Path.home() / "AppData" / "Roaming"
        local_app_data = Path(local_app_data_raw) if local_app_data_raw else Path.home() / "AppData" / "Local"
        candidates = [
            managed_codex_executable(),
            app_data / "npm" / "codex.cmd",
            app_data / "npm" / "codex",
            local_app_data / "npm" / "codex.cmd",
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "codex.cmd",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs" / "codex.cmd",
            local_app_data / "Programs" / "nodejs" / "codex.cmd",
        ]
    else:
        candidates = [
            managed_codex_executable(),
            Path("/opt/homebrew/bin/codex"),
            Path("/usr/local/bin/codex"),
            Path.home() / ".local/bin/codex",
            Path.home() / ".npm-global/bin/codex",
            Path.home() / ".nvm/versions/node/current/bin/codex",
        ]
    return [candidate for candidate in candidates if candidate.exists() and candidate.is_file()]


def resolve_codex_executable() -> str | None:
    executable = shutil.which("codex")
    if executable:
        return executable
    for candidate in _candidate_paths():
        return str(candidate)
    return None


def resolve_npm_executable() -> str | None:
    executable = shutil.which("npm")
    if executable:
        return executable
    candidate = managed_npm_executable()
    if candidate.exists() and candidate.is_file():
        return str(candidate)
    if os.name == "nt":
        local_app_data_raw = os.environ.get("LOCALAPPDATA")
        local_app_data = Path(local_app_data_raw) if local_app_data_raw else Path.home() / "AppData" / "Local"
        npm_candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "npm.cmd",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs" / "npm.cmd",
            local_app_data / "Programs" / "nodejs" / "npm.cmd",
        ]
        for item in npm_candidates:
            if item.exists() and item.is_file():
                return str(item)
    return None


def is_managed_codex_executable(executable: str | Path | None) -> bool:
    if not executable:
        return False
    try:
        return Path(executable).expanduser().resolve() == managed_codex_executable().resolve()
    except FileNotFoundError:
        return False


def codex_command_env(executable: str | Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    target = str(executable or "").strip()
    if not is_managed_codex_executable(target):
        return env

    path_entries: list[str] = [
        str(managed_node_bin_dir()),
        str(managed_codex_bin_dir()),
    ]
    current_path = env.get("PATH", "")
    if current_path:
        path_entries.append(current_path)
    env["PATH"] = os.pathsep.join(path_entries)
    return env


def background_subprocess_kwargs(platform_override: str | None = None) -> dict[str, Any]:
    platform_name = str(platform_override or "").strip().lower()
    is_windows = platform_name == "windows" or (not platform_name and os.name == "nt")
    if not is_windows:
        return {}
    kwargs: dict[str, Any] = {
        "creationflags": int(getattr(subprocess, "CREATE_NO_WINDOW", 0x08000000)),
    }
    startupinfo_cls = getattr(subprocess, "STARTUPINFO", None)
    use_show_window = getattr(subprocess, "STARTF_USESHOWWINDOW", None)
    if startupinfo_cls is not None and use_show_window is not None:
        startupinfo = startupinfo_cls()
        startupinfo.dwFlags |= use_show_window
        kwargs["startupinfo"] = startupinfo
    return kwargs


def _command_output(command: list[str]) -> str:
    process = subprocess.run(
        command,
        capture_output=True,
        text=True,
        check=False,
        env=codex_command_env(command[0] if command else None),
        **background_subprocess_kwargs(),
    )
    output = (process.stdout or process.stderr or "").strip()
    if process.returncode != 0:
        return ""
    return output


def codex_version(executable: str | None = None) -> str | None:
    target = executable or resolve_codex_executable()
    if not target:
        return None
    return _command_output([target, "--version"]) or None


def _macos_node_archive_metadata() -> tuple[str, str]:
    machine = platform.machine().lower()
    if machine in {"arm64", "aarch64"}:
        return "osx-arm64-tar", "darwin-arm64"
    if machine in {"x86_64", "amd64"}:
        return "osx-x64-tar", "darwin-x64"
    raise RuntimeError(f"暂不支持当前 macOS 架构：{machine}")


def _windows_node_archive_metadata() -> tuple[str, str]:
    machine = platform.machine().lower()
    if machine in {"amd64", "x86_64"}:
        return "win-x64-zip", "win-x64"
    if machine in {"arm64", "aarch64"}:
        return "win-arm64-zip", "win-arm64"
    raise RuntimeError(f"暂不支持当前 Windows 架构：{machine}")


def _safe_extract_tar(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with tarfile.open(archive_path, "r:xz") as archive:
        for member in archive.getmembers():
            target_path = (destination / member.name).resolve()
            if target_path != destination_root and destination_root not in target_path.parents:
                raise RuntimeError(f"Node.js 安装包包含非法路径：{member.name}")
        archive.extractall(destination)


def _safe_extract_zip(archive_path: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    destination_root = destination.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            target_path = (destination / member.filename).resolve()
            if target_path != destination_root and destination_root not in target_path.parents:
                raise RuntimeError(f"Node.js 安装包包含非法路径：{member.filename}")
        archive.extractall(destination)


def _download_file(url: str, destination: Path) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": f"{APP_NAME} Codex Bootstrap"})
    with urllib.request.urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)


def _latest_node_lts_release() -> tuple[dict[str, Any], str]:
    if sys.platform == "darwin":
        files_key, archive_suffix = _macos_node_archive_metadata()
        archive_name_builder = lambda version: f"node-{version}-{archive_suffix}.tar.xz"
    elif os.name == "nt":
        files_key, archive_suffix = _windows_node_archive_metadata()
        archive_name_builder = lambda version: f"node-{version}-{archive_suffix}.zip"
    else:
        raise RuntimeError("当前自动准备流程仅覆盖 macOS 和 Windows。")
    request = urllib.request.Request(NODE_INDEX_URL, headers={"User-Agent": f"{APP_NAME} Codex Bootstrap"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.load(response)

    for item in payload:
        if item.get("lts") and files_key in item.get("files", []):
            archive_name = archive_name_builder(item["version"])
            return item, archive_name
    raise RuntimeError("未找到适用于当前平台架构的 Node.js LTS 发行版。")


def _install_managed_node_runtime(language: str) -> tuple[str, list[str]]:
    if sys.platform != "darwin" and os.name != "nt":
        raise RuntimeError(_localized("当前自动准备流程仅覆盖 macOS 和 Windows。", "The managed bootstrap flow currently only supports macOS and Windows.", language))

    release, archive_name = _latest_node_lts_release()
    runtime_root = codex_runtime_root()
    runtime_root.mkdir(parents=True, exist_ok=True)
    download_url = f"{NODE_DIST_BASE_URL}/{release['version']}/{archive_name}"
    notes = [
        _localized(
            f"未检测到系统 npm，已转为下载 Node.js LTS {release['version']} 并放入应用托管目录。",
            f"No system npm was found. Downloaded Node.js LTS {release['version']} into the app-managed runtime.",
            language,
        )
    ]

    with tempfile.TemporaryDirectory(prefix="research-assistant-node-") as temp_dir:
        temp_root = Path(temp_dir)
        archive_path = temp_root / archive_name
        extract_root = temp_root / "extract"
        _download_file(download_url, archive_path)
        if archive_name.endswith(".zip"):
            _safe_extract_zip(archive_path, extract_root)
        else:
            _safe_extract_tar(archive_path, extract_root)

        if archive_name.endswith(".zip"):
            extracted_dir = extract_root / archive_name.removesuffix(".zip")
        else:
            extracted_dir = extract_root / archive_name.removesuffix(".tar.xz")
        if not extracted_dir.exists():
            children = [path for path in extract_root.iterdir() if path.is_dir()]
            if len(children) != 1:
                raise RuntimeError("无法识别 Node.js 解压目录。")
            extracted_dir = children[0]

        target_dir = managed_node_runtime_dir()
        if target_dir.exists():
            shutil.rmtree(target_dir)
        shutil.move(str(extracted_dir), str(target_dir))

    payload = load_codex_setup_state()
    payload.update(
        {
            "managed_node_version": release["version"],
            "managed_node_download_url": download_url,
        }
    )
    save_codex_setup_state(payload)
    return str(managed_npm_executable()), notes


def _install_codex_with_npm(npm_executable: str, language: str) -> tuple[str, list[str]]:
    runtime_root = codex_runtime_root()
    runtime_root.mkdir(parents=True, exist_ok=True)
    managed_npm_prefix().mkdir(parents=True, exist_ok=True)
    managed_npm_cache_dir().mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    npm_bin_dir = str(Path(npm_executable).expanduser().resolve().parent)
    path_entries = [npm_bin_dir]
    managed_node_dir = str(managed_node_bin_dir())
    if Path(managed_node_dir).exists():
        path_entries.append(managed_node_dir)
    if env.get("PATH"):
        path_entries.append(env["PATH"])
    env["PATH"] = os.pathsep.join(path_entries)
    env["NPM_CONFIG_CACHE"] = str(managed_npm_cache_dir())
    env["NPM_CONFIG_UPDATE_NOTIFIER"] = "false"

    process = subprocess.run(
        [
            npm_executable,
            "install",
            "--global",
            "--prefix",
            str(managed_npm_prefix()),
            "--no-audit",
            "--no-fund",
            "@openai/codex",
        ],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        **background_subprocess_kwargs(),
    )
    if process.returncode != 0:
        output = (process.stdout or process.stderr or "").strip()
        if len(output) > 1800:
            output = output[:1800] + "...(truncated)"
        raise RuntimeError(
            _localized(
                f"安装 Codex CLI 失败：{output or '未知错误'}",
                f"Failed to install Codex CLI: {output or 'unknown error'}",
                language,
            )
        )

    executable = managed_codex_executable()
    if not executable.exists():
        raise RuntimeError(_localized("Codex CLI 安装完成，但未找到可执行文件。", "Codex CLI installation finished, but the executable was not found.", language))

    notes = [
        _localized(
            f"Codex CLI 已安装到应用托管目录：{executable}",
            f"Codex CLI was installed into the app-managed runtime: {executable}",
            language,
        )
    ]
    return str(executable), notes


def prepare_codex_cli(language: str | None = None, *, force_managed_install: bool = False) -> dict[str, Any]:
    lang = _detect_language(language)
    notes: list[str] = []
    existing = resolve_codex_executable()
    if existing and not force_managed_install:
        version = codex_version(existing)
        if version:
            notes.append(
                _localized(
                    "已检测到可用的本地 Codex CLI，应用不会重复安装。",
                    "A usable local Codex CLI was found. The app will not install another copy.",
                    lang,
                )
            )
            if is_managed_codex_executable(existing):
                notes.append(
                    _localized(
                        "当前 Codex CLI 由 Research Assistant 托管，无需手工安装。",
                        "The current Codex CLI is managed by Research Assistant, so no manual installation is needed.",
                        lang,
                    )
                )
            return CodexSetupResult(
                status="ready",
                message=_localized("Codex CLI 已就绪。", "Codex CLI is ready.", lang),
                codex_executable=existing,
                codex_version=version,
                npm_executable=resolve_npm_executable(),
                managed_install=is_managed_codex_executable(existing),
                notes=notes,
            ).to_dict()

    npm_executable = resolve_npm_executable()
    if npm_executable:
        notes.append(
            _localized(
                "已检测到可用 npm，将在应用托管目录安装 Codex CLI。",
                "Found a usable npm executable. Codex CLI will be installed into the app-managed runtime.",
                lang,
            )
        )
    else:
        npm_executable, node_notes = _install_managed_node_runtime(lang)
        notes.extend(node_notes)

    executable, install_notes = _install_codex_with_npm(npm_executable, lang)
    notes.extend(install_notes)
    version = codex_version(executable)

    payload = load_codex_setup_state()
    payload.update(
        {
            "last_prepare_status": "success",
            "last_prepare_codex_path": executable,
            "last_prepare_codex_version": version,
        }
    )
    save_codex_setup_state(payload)

    return CodexSetupResult(
        status="installed",
        message=_localized("Codex CLI 已准备完成。", "Codex CLI is ready.", lang),
        codex_executable=executable,
        codex_version=version,
        npm_executable=npm_executable,
        managed_install=True,
        notes=notes,
    ).to_dict()


def open_codex_login_terminal(language: str | None = None, executable: str | None = None) -> dict[str, Any]:
    lang = _detect_language(language)
    target = executable or resolve_codex_executable()
    if not target:
        return CodexSetupResult(
            status="error",
            message=_localized("未检测到 Codex CLI，请先完成准备流程。", "Codex CLI was not found. Prepare it first.", lang),
            error=_localized("未检测到 Codex CLI。", "Codex CLI was not found.", lang),
        ).to_dict()

    script_path = managed_login_script_path()
    script_path.parent.mkdir(parents=True, exist_ok=True)
    if os.name == "nt":
        path_prefix = os.pathsep.join([str(managed_node_bin_dir()), str(managed_codex_bin_dir())]) if is_managed_codex_executable(target) else ""
        lines = [
            "@echo off",
            "title Research Assistant - Codex Login",
            f'echo {_localized("Research Assistant 已为你准备好 Codex 登录。", "Research Assistant has prepared Codex login for you.", lang)}',
            f'echo {_localized("窗口会执行 codex login；完成授权后直接回到桌面端即可。", "This window will run codex login. Return to the desktop app after authorization.", lang)}',
            "echo.",
        ]
        if path_prefix:
            lines.append(f'set "PATH={path_prefix};%PATH%"')
        lines.extend(
            [
                f'"{target}" login',
                "set STATUS=%ERRORLEVEL%",
                "echo.",
                "if \"%STATUS%\"==\"0\" (",
                f'  echo {_localized("Codex 登录命令已结束。若浏览器授权成功，桌面端会在后续刷新中变为可执行。", "The Codex login command finished. If browser authorization succeeded, the desktop app will detect it on refresh.", lang)}',
                ") else (",
                f'  echo {_localized("Codex 登录命令退出状态：", "Codex login exited with status:", lang)} %STATUS%',
                ")",
                "echo.",
                f'echo {_localized("这个窗口可以直接关闭。", "You can close this window now.", lang)}',
                "pause",
                "",
            ]
        )
        script_path.write_text("\r\n".join(lines), encoding="utf-8")
    else:
        path_prefix = os.pathsep.join([str(managed_node_bin_dir()), str(managed_codex_bin_dir())]) if is_managed_codex_executable(target) else ""
        lines = [
            "#!/bin/bash",
            "set -u",
            "",
            "clear",
            f'echo "{_localized("Research Assistant 已为你准备好 Codex 登录。", "Research Assistant has prepared Codex login for you.", lang)}"',
            f'echo "{_localized("终端会执行 codex login；完成授权后直接回到桌面端即可。", "The terminal will run codex login. Return to the desktop app after authorization.", lang)}"',
            'echo ""',
        ]
        if path_prefix:
            lines.append(f'export PATH="{path_prefix}:$PATH"')
        lines.extend(
            [
                f"{shlex.quote(target)} login",
                "status=$?",
                'echo ""',
                'if [ "$status" -eq 0 ]; then',
                f'  echo "{_localized("Codex 登录命令已结束。若浏览器授权成功，桌面端会在后续刷新中变为可执行。", "The Codex login command finished. If browser authorization succeeded, the desktop app will detect it on refresh.", lang)}"',
                "else",
                f'  echo "{_localized("Codex 登录命令退出状态：", "Codex login exited with status:", lang)} $status"',
                "fi",
                'echo ""',
                f'echo "{_localized("这个终端窗口可以直接关闭。", "You can close this terminal window now.", lang)}"',
                'exec "${SHELL:-/bin/zsh}" -l',
                "",
            ]
        )
        script_path.write_text("\n".join(lines), encoding="utf-8")
        script_path.chmod(script_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    if sys.platform == "darwin":
        subprocess.run(["open", str(script_path)], check=True)
    elif os.name == "nt":
        os.startfile(str(script_path))  # type: ignore[attr-defined]
    else:
        subprocess.Popen([target, "login"], env=codex_command_env(target))

    return CodexSetupResult(
        status="started",
        message=_localized("已打开 Codex 登录终端。", "Opened the Codex login terminal.", lang),
        codex_executable=target,
        codex_version=codex_version(target),
        managed_install=is_managed_codex_executable(target),
        login_script_path=str(script_path),
        opened_terminal=True,
    ).to_dict()
