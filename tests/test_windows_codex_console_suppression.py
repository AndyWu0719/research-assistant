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


class WindowsCodexConsoleSuppressionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.windows_setup = load_module(ROOT / "Windows" / "research_assistant" / "codex_setup.py", "windows_codex_setup")
        self.windows_bridge = load_module(ROOT / "Windows" / "research_assistant" / "codex_bridge.py", "windows_codex_bridge")

    def test_setup_background_subprocess_kwargs_hide_windows_console(self) -> None:
        kwargs = self.windows_setup.background_subprocess_kwargs(platform_override="windows")
        self.assertIn("creationflags", kwargs)
        self.assertNotEqual(kwargs["creationflags"], 0)

    def test_bridge_background_subprocess_kwargs_hide_windows_console(self) -> None:
        kwargs = self.windows_bridge.background_subprocess_kwargs(platform_override="windows")
        self.assertIn("creationflags", kwargs)
        self.assertNotEqual(kwargs["creationflags"], 0)

    def test_background_subprocess_kwargs_are_empty_on_non_windows(self) -> None:
        self.assertEqual(self.windows_setup.background_subprocess_kwargs(platform_override="macos"), {})
        self.assertEqual(self.windows_bridge.background_subprocess_kwargs(platform_override="macos"), {})


if __name__ == "__main__":
    unittest.main()
