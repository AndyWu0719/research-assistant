from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def load_module(path: Path, name: str):
    project_root = path.parents[1]
    original_path = list(sys.path)
    original_module = sys.modules.get(name)
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path[:] = original_path
        if original_module is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = original_module
    return module


class WebEnginePackagingTests(unittest.TestCase):
    def test_macos_build_collects_qtwebengine(self) -> None:
        module = load_module(ROOT / "MacOS" / "scripts" / "build_installer.py", "mac_build_installer")
        extra_args = module.pyinstaller_extra_args("macos")
        joined = " ".join(extra_args)
        self.assertIn("PySide6.QtWebEngineWidgets", joined)
        self.assertIn("PySide6.QtWebEngineCore", joined)

    def test_windows_build_collects_qtwebengine_and_tzdata(self) -> None:
        module = load_module(ROOT / "Windows" / "scripts" / "build_installer.py", "windows_build_installer_with_webengine")
        extra_args = module.pyinstaller_extra_args("windows")
        joined = " ".join(extra_args)
        self.assertIn("PySide6.QtWebEngineWidgets", joined)
        self.assertIn("PySide6.QtWebEngineCore", joined)
        self.assertIn("tzdata", joined)


if __name__ == "__main__":
    unittest.main()
