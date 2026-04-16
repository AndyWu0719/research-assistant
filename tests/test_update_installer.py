from __future__ import annotations

import importlib.util
import sys
import unittest
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


class UpdateInstallerContract(unittest.TestCase):
    def setUp(self) -> None:
        self.macos_module_path = ROOT / "MacOS" / "research_assistant" / "update_installer.py"
        self.windows_module_path = ROOT / "Windows" / "research_assistant" / "update_installer.py"

    def test_update_installer_modules_exist(self) -> None:
        self.assertTrue(self.macos_module_path.exists(), self.macos_module_path)
        self.assertTrue(self.windows_module_path.exists(), self.windows_module_path)

    def test_macos_update_script_contains_pkg_install_and_relaunch(self) -> None:
        module = load_module(self.macos_module_path, "macos_update_installer")
        script = module.build_macos_update_script(
            Path("/tmp/ResearchAssistant-macos-1.1.2.pkg"),
            app_pid=4321,
            relaunch_app=Path("/Applications/Research Assistant.app"),
        )
        self.assertIn("APP_PID=4321", script)
        self.assertIn("installer -pkg /tmp/ResearchAssistant-macos-1.1.2.pkg -target /", script)
        self.assertIn('open -a "$APP_PATH"', script)

    def test_windows_update_script_contains_silent_install_and_restart(self) -> None:
        module = load_module(self.windows_module_path, "windows_update_installer")
        script = module.build_windows_update_script(
            Path(r"C:\Temp\ResearchAssistant-windows-1.1.2.exe"),
            app_pid=9876,
            restart_exe=Path(r"C:\Users\andy\AppData\Local\Programs\Research Assistant\Research Assistant.exe"),
        )
        self.assertIn('set "APP_PID=9876"', script)
        self.assertIn('tasklist /FI "PID eq %APP_PID%"', script)
        self.assertIn('start "" /wait "%INSTALLER_PATH%" /S', script)
        self.assertIn('start "" "%RESTART_EXE%"', script)


if __name__ == "__main__":
    unittest.main()
