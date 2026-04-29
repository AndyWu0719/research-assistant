from __future__ import annotations

import argparse
import importlib.util
import json
import os
import plistlib
import shutil
import subprocess
import sys
from pathlib import Path

if str(Path(__file__).resolve().parents[1]) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from research_assistant.windows_encoding import apply_utf8_child_env, configure_utf8_stdio, utf8_subprocess_text_kwargs


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Research Assistant"
PACKAGE_ID = "com.andywu.research-assistant"
WINDOWS_COMPANY_NAME = "Andy Wu"
DIST_ROOT = ROOT / "dist" / "installers"
IGNORE_TOP_LEVEL = {
    ".github",
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


def repo_default_version() -> str:
    for candidate in (ROOT.parent / "VERSION", ROOT / "VERSION"):
        if candidate.exists():
            value = candidate.read_text(encoding="utf-8").strip()
            if value:
                return value
    return "1.0.0"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build native installers for Research Assistant.")
    parser.add_argument("--platform", choices=["auto", "macos", "windows"], default="auto")
    parser.add_argument("--version", default=repo_default_version())
    parser.add_argument(
        "--keep-intermediates",
        action="store_true",
        help="Keep temporary PyInstaller and project-template files under dist/installers/<platform>/.",
    )
    return parser.parse_args()


def native_platform() -> str:
    if sys.platform == "darwin":
        return "macos"
    if os.name == "nt" or sys.platform.startswith("win"):
        return "windows"
    raise RuntimeError("当前仅支持在 macOS 或 Windows 上构建原生安装包。")


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd or ROOT, check=True, env=apply_utf8_child_env(), **utf8_subprocess_text_kwargs())


def clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def should_ignore(relative_path: Path) -> bool:
    if not relative_path.parts:
        return False
    if relative_path.parts[0] in IGNORE_TOP_LEVEL:
        return True
    if "__pycache__" in relative_path.parts:
        return True
    if relative_path.suffix in {".pyc", ".pyo"}:
        return True
    if relative_path.name == ".DS_Store":
        return True
    if relative_path.suffix == ".p8":
        return True
    if relative_path.name in {"signing.env", ".env", ".env.local"}:
        return True

    if relative_path == Path("configs/user_preferences.yaml"):
        return True
    if relative_path == Path("configs/update_state.json"):
        return True
    if relative_path == Path("configs/automations/index.yaml"):
        return True
    if relative_path == Path("configs/automations/runtime_state.json"):
        return True
    if relative_path.parts[:3] == ("configs", "automations", "history") and relative_path.name != ".gitkeep":
        return True
    if relative_path.parts[:2] == ("configs", "automations") and relative_path.suffix == ".yaml" and "--" in relative_path.stem:
        return True

    if relative_path.parts and relative_path.parts[0] == "outputs":
        allowed = {".gitkeep", "README.md"}
        return relative_path.name not in allowed
    return False


def copy_project_template(destination_root: Path) -> None:
    for source in sorted(ROOT.rglob("*")):
        relative_path = source.relative_to(ROOT)
        if should_ignore(relative_path):
            continue
        target = destination_root / relative_path
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def write_build_metadata(destination_root: Path, platform: str, version: str) -> None:
    payload = {
        "app_name": APP_NAME,
        "version": version,
        "platform": platform,
        "built_from": str(ROOT),
    }
    (destination_root / ".app-build.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_pyinstaller() -> None:
    if importlib.util.find_spec("PyInstaller") is not None:
        return
    raise RuntimeError("未检测到 PyInstaller。请先执行 `python -m pip install -r packaging/requirements-build.txt`。")


def ensure_host_platform(target: str) -> None:
    current = native_platform()
    if current != target:
        raise RuntimeError(f"当前主机是 {current}，不能直接构建 {target} 安装包。请切换到原生 {target} 主机或对应 CI。")


def pyinstaller_add_data(source: Path, destination: str) -> str:
    separator = ";" if os.name == "nt" or sys.platform.startswith("win") else ":"
    return f"{source}{separator}{destination}"


def pyinstaller_extra_args(platform: str) -> list[str]:
    normalized = str(platform or "").strip().lower()
    extra = [
        "--hidden-import",
        "PySide6.QtWebEngineWidgets",
        "--hidden-import",
        "PySide6.QtWebEngineCore",
        "--collect-submodules",
        "PySide6.QtWebEngineWidgets",
        "--collect-submodules",
        "PySide6.QtWebEngineCore",
    ]
    if normalized == "windows":
        extra.extend(["--collect-all", "tzdata"])
    return extra


def resolve_makensis() -> str:
    executable = shutil.which("makensis")
    if executable:
        return executable

    candidates = [
        Path(os.environ.get("ProgramFiles", "")) / "NSIS" / "makensis.exe",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "NSIS" / "makensis.exe",
    ]
    for candidate in candidates:
        if str(candidate) and candidate.exists():
            return str(candidate)

    raise RuntimeError("未检测到 NSIS (`makensis`)。请先在 Windows 上安装 NSIS，例如 `winget install NSIS.NSIS`。")


def codesign_app(app_path: Path) -> None:
    if shutil.which("codesign") is None:
        return
    run(["codesign", "--force", "--deep", "--sign", "-", str(app_path)])


def write_bundle_version(app_path: Path, version: str) -> None:
    info_plist = app_path / "Contents" / "Info.plist"
    if not info_plist.exists():
        return
    with info_plist.open("rb") as handle:
        payload = plistlib.load(handle)
    payload["CFBundleShortVersionString"] = version
    payload["CFBundleVersion"] = version
    payload["CFBundleIdentifier"] = PACKAGE_ID
    with info_plist.open("wb") as handle:
        plistlib.dump(payload, handle, sort_keys=False)


def prepare_build_root(platform: str, version: str) -> tuple[Path, Path, Path, Path, Path]:
    build_root = DIST_ROOT / platform
    template_root = build_root / "project_template"
    pyinstaller_dist = build_root / "pyinstaller"
    pyinstaller_work = build_root / "pyinstaller-work"
    pyinstaller_spec = build_root / "pyinstaller-spec"

    clean_dir(build_root)
    template_root.mkdir(parents=True, exist_ok=True)
    copy_project_template(template_root)
    write_build_metadata(template_root, platform, version)

    pyinstaller_dist.mkdir(parents=True, exist_ok=True)
    pyinstaller_work.mkdir(parents=True, exist_ok=True)
    pyinstaller_spec.mkdir(parents=True, exist_ok=True)
    return build_root, template_root, pyinstaller_dist, pyinstaller_work, pyinstaller_spec


def cleanup_intermediates(template_root: Path, pyinstaller_work: Path, pyinstaller_spec: Path, keep_intermediates: bool) -> None:
    if keep_intermediates:
        return
    for path in [template_root, pyinstaller_work, pyinstaller_spec]:
        if path.exists():
            shutil.rmtree(path)


def build_macos(version: str, *, keep_intermediates: bool = False) -> dict[str, str]:
    ensure_host_platform("macos")
    ensure_pyinstaller()
    build_root, template_root, pyinstaller_dist, pyinstaller_work, pyinstaller_spec = prepare_build_root("macos", version)

    add_data_arg = pyinstaller_add_data(template_root, "project_template")
    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        str(pyinstaller_dist),
        "--workpath",
        str(pyinstaller_work),
        "--specpath",
        str(pyinstaller_spec),
        "--add-data",
        add_data_arg,
        *pyinstaller_extra_args("macos"),
        str(ROOT / "desktop" / "main.py"),
    ]
    run(command, cwd=ROOT)

    app_path = pyinstaller_dist / f"{APP_NAME}.app"
    if not app_path.exists():
        raise RuntimeError(f"PyInstaller 未生成应用包：{app_path}")

    write_bundle_version(app_path, version)
    codesign_app(app_path)

    pkg_path = build_root / f"ResearchAssistant-macos-{version}.pkg"
    if pkg_path.exists():
        pkg_path.unlink()
    run(
        [
            "pkgbuild",
            "--component",
            str(app_path),
            "--install-location",
            "/Applications",
            "--identifier",
            PACKAGE_ID,
            "--version",
            version,
            str(pkg_path),
        ],
        cwd=build_root,
    )

    cleanup_intermediates(template_root, pyinstaller_work, pyinstaller_spec, keep_intermediates)
    if not keep_intermediates:
        unpacked_dir = pyinstaller_dist / APP_NAME
        if unpacked_dir.exists() and unpacked_dir.is_dir():
            shutil.rmtree(unpacked_dir)

    return {
        "platform": "macos",
        "bundle_path": str(app_path),
        "installer_path": str(pkg_path),
    }


def build_windows(version: str, *, keep_intermediates: bool = False) -> dict[str, str]:
    ensure_host_platform("windows")
    ensure_pyinstaller()
    makensis = resolve_makensis()
    build_root, template_root, pyinstaller_dist, pyinstaller_work, pyinstaller_spec = prepare_build_root("windows", version)

    command = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--clean",
        "--windowed",
        "--name",
        APP_NAME,
        "--distpath",
        str(pyinstaller_dist),
        "--workpath",
        str(pyinstaller_work),
        "--specpath",
        str(pyinstaller_spec),
        "--add-data",
        pyinstaller_add_data(template_root, "project_template"),
        *pyinstaller_extra_args("windows"),
        str(ROOT / "desktop" / "main.py"),
    ]
    run(command, cwd=ROOT)

    app_dir = pyinstaller_dist / APP_NAME
    exe_path = app_dir / f"{APP_NAME}.exe"
    if not exe_path.exists():
        raise RuntimeError(f"PyInstaller 未生成 Windows 可执行文件：{exe_path}")

    installer_script = ROOT / "packaging" / "windows" / "installer.nsi"
    if not installer_script.exists():
        raise RuntimeError(f"缺少 Windows 安装器脚本：{installer_script}")

    output_path = build_root / f"ResearchAssistant-windows-{version}.exe"
    if output_path.exists():
        output_path.unlink()

    run(
        [
            makensis,
            f"/DAPP_NAME={APP_NAME}",
            f"/DAPP_EXE_NAME={APP_NAME}.exe",
            f"/DAPP_VERSION={version}",
            f"/DAPP_DIR={app_dir.resolve()}",
            f"/DOUTPUT_FILE={output_path.resolve()}",
            f"/DINSTALL_DIR=$LOCALAPPDATA\\Programs\\{APP_NAME}",
            f"/DCOMPANY_NAME={WINDOWS_COMPANY_NAME}",
            str(installer_script),
        ],
        cwd=ROOT,
    )

    cleanup_intermediates(template_root, pyinstaller_work, pyinstaller_spec, keep_intermediates)
    return {
        "platform": "windows",
        "app_dir": str(app_dir),
        "exe_path": str(exe_path),
        "installer_path": str(output_path),
    }


def main() -> int:
    configure_utf8_stdio()
    args = parse_args()
    current = native_platform()
    target = current if args.platform == "auto" else args.platform
    if target == "macos":
        summary = build_macos(args.version, keep_intermediates=args.keep_intermediates)
    elif target == "windows":
        summary = build_windows(args.version, keep_intermediates=args.keep_intermediates)
    else:
        raise RuntimeError(f"暂不支持的平台：{target}")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
