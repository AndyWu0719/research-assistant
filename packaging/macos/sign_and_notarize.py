from __future__ import annotations

import argparse
import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
BUILD_SCRIPT = ROOT / "scripts" / "build_installer.py"
APP_NAME = "Research Assistant"
PACKAGE_ID = "com.andywu.research-assistant"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build, sign, and notarize the macOS Research Assistant installer.")
    parser.add_argument("--version", default="1.0.0")
    parser.add_argument("--skip-build", action="store_true", help="Reuse an existing built app instead of rebuilding.")
    parser.add_argument("--app-path", help="Path to an existing .app bundle when --skip-build is used.")
    parser.add_argument("--skip-notarize", action="store_true", help="Only sign the app/pkg, do not submit for notarization.")
    return parser.parse_args()


def env_required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"缺少环境变量 `{name}`。请参考 packaging/macos/signing.env.example。")
    return value


def run(command: list[str], *, cwd: Path | None = None, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd or ROOT,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def load_build_module() -> Any:
    spec = importlib.util.spec_from_file_location("research_assistant_build_installer", BUILD_SCRIPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载构建脚本：{BUILD_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def ensure_tool(name: str) -> str:
    resolved = shutil.which(name)
    if not resolved:
        raise RuntimeError(f"缺少系统工具 `{name}`。请先安装 Xcode Command Line Tools。")
    return resolved


def build_or_resolve_app(args: argparse.Namespace) -> tuple[Path, Path]:
    if args.skip_build:
        if not args.app_path:
            raise RuntimeError("使用 --skip-build 时必须同时提供 --app-path。")
        app_path = Path(args.app_path).expanduser().resolve()
        if not app_path.exists():
            raise RuntimeError(f"找不到 app 包：{app_path}")
        build_root = app_path.parents[1]
        return app_path, build_root

    module = load_build_module()
    summary = module.build_macos(args.version)
    return Path(summary["app_path"]).resolve(), Path(summary["app_path"]).resolve().parents[1]


def sign_app(app_path: Path, identity: str) -> None:
    run(
        [
            "codesign",
            "--force",
            "--deep",
            "--strict",
            "--timestamp",
            "--options",
            "runtime",
            "--sign",
            identity,
            str(app_path),
        ]
    )
    run(["codesign", "--verify", "--deep", "--strict", "--verbose=2", str(app_path)])
    run(["spctl", "--assess", "--type", "exec", "--verbose=2", str(app_path)])


def build_unsigned_pkg(app_path: Path, version: str, build_root: Path) -> Path:
    unsigned_pkg = build_root / f"ResearchAssistant-macos-{version}-unsigned.pkg"
    if unsigned_pkg.exists():
        unsigned_pkg.unlink()
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
            str(unsigned_pkg),
        ],
        cwd=build_root,
    )
    return unsigned_pkg


def sign_pkg(unsigned_pkg: Path, identity: str) -> Path:
    signed_pkg = unsigned_pkg.with_name(unsigned_pkg.name.replace("-unsigned", ""))
    if signed_pkg.exists():
        signed_pkg.unlink()
    run(["productsign", "--sign", identity, str(unsigned_pkg), str(signed_pkg)])
    run(["pkgutil", "--check-signature", str(signed_pkg)])
    run(["spctl", "--assess", "--type", "install", "--verbose=2", str(signed_pkg)])
    return signed_pkg


def notary_auth_args() -> list[str]:
    keychain_profile = os.environ.get("APPLE_KEYCHAIN_PROFILE", "").strip()
    if keychain_profile:
        return ["--keychain-profile", keychain_profile]
    return [
        "--apple-id",
        env_required("APPLE_ID"),
        "--team-id",
        env_required("APPLE_TEAM_ID"),
        "--password",
        env_required("APPLE_APP_SPECIFIC_PASSWORD"),
    ]


def notarize_pkg(pkg_path: Path) -> dict[str, Any]:
    command = ["xcrun", "notarytool", "submit", str(pkg_path), "--wait", "--output-format", "json", *notary_auth_args()]
    process = run(command, capture_output=True)
    try:
        payload = json.loads(process.stdout)
    except json.JSONDecodeError:
        payload = {"raw_stdout": process.stdout}
    run(["xcrun", "stapler", "staple", str(pkg_path)])
    return payload


def main() -> int:
    args = parse_args()
    ensure_tool("codesign")
    ensure_tool("pkgbuild")
    ensure_tool("productsign")
    ensure_tool("pkgutil")
    ensure_tool("spctl")
    if not args.skip_notarize:
        ensure_tool("xcrun")

    app_sign_identity = env_required("APPLE_DEVELOPER_ID_APPLICATION")
    installer_sign_identity = env_required("APPLE_DEVELOPER_ID_INSTALLER")

    app_path, build_root = build_or_resolve_app(args)
    sign_app(app_path, app_sign_identity)
    unsigned_pkg = build_unsigned_pkg(app_path, args.version, build_root)
    signed_pkg = sign_pkg(unsigned_pkg, installer_sign_identity)

    notarization_payload: dict[str, Any] | None = None
    if not args.skip_notarize:
        notarization_payload = notarize_pkg(signed_pkg)

    summary = {
        "app_path": str(app_path),
        "unsigned_pkg_path": str(unsigned_pkg),
        "signed_pkg_path": str(signed_pkg),
        "notarized": not args.skip_notarize,
        "notary_result": notarization_payload,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
