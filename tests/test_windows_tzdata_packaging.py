from __future__ import annotations

import importlib.util
import sys
import unittest
from datetime import timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    project_root = path.parents[1]
    original_path = list(sys.path)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
    return module


class WindowsTzdataPackagingTests(unittest.TestCase):
    def test_windows_runtime_requirements_include_tzdata(self) -> None:
        content = (ROOT / "Windows" / "packaging" / "runtime-requirements.txt").read_text(encoding="utf-8")
        self.assertIn("tzdata", content)

    def test_windows_build_installer_collects_tzdata(self) -> None:
        module = load_module(ROOT / "Windows" / "scripts" / "build_installer.py", "windows_build_installer")
        extra_args = module.pyinstaller_extra_args("windows")
        self.assertIn("--collect-all", extra_args)
        self.assertIn("tzdata", extra_args)

    def test_windows_timezone_falls_back_to_timezone_utc(self) -> None:
        module = load_module(ROOT / "Windows" / "research_assistant" / "automation_runtime.py", "windows_automation_runtime")

        class BrokenZoneInfo:
            def __init__(self, _name: str) -> None:
                raise RuntimeError("tzdata missing")

        original = module.ZoneInfo
        module.ZoneInfo = BrokenZoneInfo
        try:
            zone = module._time_zone("UTC")
        finally:
            module.ZoneInfo = original
        self.assertIs(zone, timezone.utc)


if __name__ == "__main__":
    unittest.main()
