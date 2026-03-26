from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
VENV_DIR = ROOT / ".venv"


def find_executable(name: str, extra_candidates: list[Path] | None = None) -> str | None:
    resolved = shutil.which(name)
    if resolved:
        return resolved
    for candidate in extra_candidates or []:
        if candidate.exists():
            return str(candidate)
    return None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="One-command bootstrap for Research Assistant.")
    parser.add_argument("--prepare-only", action="store_true", help="Install/check prerequisites but do not launch the app.")
    parser.add_argument("--without-scheduler", action="store_true", help="Start the app without the local automation scheduler.")
    return parser.parse_args()


def venv_python() -> Path:
    if os.name == "nt":
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(command: list[str], *, cwd: Path | None = None, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd or ROOT, text=True, check=check)


def ensure_venv() -> Path:
    python_path = venv_python()
    if python_path.exists():
        return python_path
    run([sys.executable, "-m", "venv", str(VENV_DIR)])
    return python_path


def ensure_python_requirements(python_path: Path) -> None:
    run([str(python_path), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(python_path), "-m", "pip", "install", "-r", str(ROOT / "requirements.txt")])


def ensure_node_runtime() -> str:
    npm_candidates = []
    if os.name == "nt":
        npm_candidates = [
            Path(os.environ.get("ProgramFiles", r"C:\Program Files")) / "nodejs" / "npm.cmd",
            Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "nodejs" / "npm.cmd",
        ]
    npm = find_executable("npm", npm_candidates)
    if npm:
        return npm

    if sys.platform == "darwin":
        brew = shutil.which("brew")
        if brew:
            run([brew, "install", "node"])
            npm = find_executable("npm", npm_candidates)
            if npm:
                return npm
        raise RuntimeError("未检测到 `npm`，且无法通过 Homebrew 自动安装 Node.js。")

    if os.name == "nt":
        winget = shutil.which("winget")
        if winget:
            run(
                [
                    winget,
                    "install",
                    "--id",
                    "OpenJS.NodeJS.LTS",
                    "-e",
                    "--silent",
                    "--accept-package-agreements",
                    "--accept-source-agreements",
                ]
            )
            npm = find_executable("npm", npm_candidates)
            if npm:
                return npm
        raise RuntimeError("未检测到 `npm`，且无法通过 winget 自动安装 Node.js。")

    raise RuntimeError("未检测到 `npm`，当前平台也没有配置自动安装 Node.js 的路径。")


def ensure_codex_cli() -> None:
    if shutil.which("codex"):
        return
    npm = ensure_node_runtime()
    run([npm, "install", "-g", "@openai/codex"])


def codex_logged_in() -> bool:
    executable = shutil.which("codex")
    if not executable:
        return False
    process = subprocess.run(
        [executable, "login", "status"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = (process.stdout or process.stderr).lower()
    return process.returncode == 0 and "logged in" in output


def ensure_codex_login() -> None:
    executable = shutil.which("codex")
    if not executable:
        raise RuntimeError("未检测到 `codex` 命令。")
    if codex_logged_in():
        return
    run([executable, "login"], check=True)


def launch_app(python_path: Path, without_scheduler: bool) -> int:
    command = [str(python_path), str(ROOT / "desktop" / "main.py")]
    if without_scheduler:
        command.append("--without-scheduler")
    process = subprocess.run(command, cwd=ROOT, check=False)
    return process.returncode


def main() -> int:
    args = parse_args()
    python_path = ensure_venv()
    ensure_python_requirements(python_path)
    ensure_codex_cli()
    ensure_codex_login()
    if args.prepare_only:
        print("环境准备完成。")
        return 0
    return launch_app(python_path, without_scheduler=args.without_scheduler)


if __name__ == "__main__":
    raise SystemExit(main())
