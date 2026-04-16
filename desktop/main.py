from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def target_subtree() -> str:
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
    target = ROOT / target_subtree() / "desktop" / "main.py"
    if not target.exists():
        raise RuntimeError(f"Missing compatibility target: {target}")
    process = subprocess.run(
        [preferred_python(), str(target), *sys.argv[1:]],
        cwd=ROOT,
        check=False,
    )
    return process.returncode


if __name__ == "__main__":
    raise SystemExit(main())
