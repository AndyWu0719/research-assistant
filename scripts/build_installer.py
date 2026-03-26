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


ROOT = Path(__file__).resolve().parents[1]
APP_NAME = "Research Assistant"
PACKAGE_ID = "com.andywu.research-assistant"
DIST_ROOT = ROOT / "dist" / "installers"
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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build macOS installers for Research Assistant.")
    parser.add_argument("--platform", choices=["auto", "macos"], default="auto")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--keep-intermediates", action="store_true", help="Keep temporary PyInstaller and project-template files under dist/installers/macos/.")
    return parser.parse_args()


def native_platform() -> str:
    if sys.platform != "darwin":
        raise RuntimeError("当前仅支持在 macOS 上构建 macOS 安装包。")
    return "macos"


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd or ROOT, check=True, text=True)


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


def build_macos(version: str, *, keep_intermediates: bool = False) -> dict[str, str]:
    ensure_pyinstaller()
    build_root = DIST_ROOT / "macos"
    legacy_windows_root = DIST_ROOT / "windows"
    template_root = build_root / "project_template"
    pyinstaller_dist = build_root / "pyinstaller"
    pyinstaller_work = build_root / "pyinstaller-work"
    pyinstaller_spec = build_root / "pyinstaller-spec"

    if legacy_windows_root.exists():
        shutil.rmtree(legacy_windows_root)
    clean_dir(build_root)
    template_root.mkdir(parents=True, exist_ok=True)
    copy_project_template(template_root)
    write_build_metadata(template_root, "macos", version)

    pyinstaller_dist.mkdir(parents=True, exist_ok=True)
    pyinstaller_work.mkdir(parents=True, exist_ok=True)
    pyinstaller_spec.mkdir(parents=True, exist_ok=True)

    add_data_arg = f"{template_root}:project_template"
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

    if not keep_intermediates:
        for path in [template_root, pyinstaller_work, pyinstaller_spec]:
            if path.exists():
                shutil.rmtree(path)
        unpacked_dir = pyinstaller_dist / APP_NAME
        if unpacked_dir.exists() and unpacked_dir.is_dir():
            shutil.rmtree(unpacked_dir)

    return {
        "platform": "macos",
        "app_path": str(app_path),
        "pkg_path": str(pkg_path),
    }


def main() -> int:
    args = parse_args()
    current = native_platform()
    target = current if args.platform == "auto" else args.platform
    if target != "macos":
        raise RuntimeError("当前脚本仅实现 macOS 安装包构建。")

    summary = build_macos(args.version, keep_intermediates=args.keep_intermediates)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
