from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def requested_platform(argv: list[str]) -> str:
    for index, arg in enumerate(argv):
        if arg == "--platform" and index + 1 < len(argv):
            return argv[index + 1].strip().lower()
        if arg.startswith("--platform="):
            return arg.split("=", 1)[1].strip().lower()
    return "auto"


def target_subtree(argv: list[str]) -> str:
    selected = requested_platform(argv)
    if selected == "windows":
        return "Windows"
    if selected == "macos":
        return "MacOS"
    if os.name == "nt" or sys.platform.startswith("win"):
        return "Windows"
    return "MacOS"


def preferred_python() -> str:
    if os.name == "nt":
        candidate = ROOT / ".venv" / "Scripts" / "python.exe"
    else:
        candidate = ROOT / ".venv" / "bin" / "python"
    return str(candidate) if candidate.exists() else sys.executable


def main() -> int:
    args = sys.argv[1:]
    target = ROOT / target_subtree(args) / "scripts" / "build_installer.py"
    if not target.exists():
        raise RuntimeError(f"Missing compatibility target: {target}")
    process = subprocess.run(
        [preferred_python(), str(target), *args],
        cwd=ROOT,
        check=False,
    )
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
