from __future__ import annotations

import importlib.util
import io
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


class _FakeStream(io.StringIO):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[tuple[str | None, str | None]] = []

    def reconfigure(self, *, encoding=None, errors=None) -> None:  # type: ignore[override]
        self.calls.append((encoding, errors))


class WindowsUnicodeEncodingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(ROOT / "Windows" / "research_assistant" / "windows_encoding.py", "windows_encoding_helper")

    def test_utf8_subprocess_kwargs_force_utf8_on_windows(self) -> None:
        kwargs = self.module.utf8_subprocess_text_kwargs(platform_override="windows")
        self.assertEqual(kwargs["text"], True)
        self.assertEqual(kwargs["encoding"], "utf-8")
        self.assertEqual(kwargs["errors"], "replace")

    def test_apply_utf8_child_env_sets_python_utf8_flags(self) -> None:
        payload = self.module.apply_utf8_child_env({}, platform_override="windows")
        self.assertEqual(payload["PYTHONUTF8"], "1")
        self.assertEqual(payload["PYTHONIOENCODING"], "utf-8")

    def test_configure_utf8_stdio_reconfigures_streams_on_windows(self) -> None:
        fake_out = _FakeStream()
        fake_err = _FakeStream()
        fake_in = _FakeStream()
        original_out, original_err, original_in = sys.stdout, sys.stderr, sys.stdin
        sys.stdout, sys.stderr, sys.stdin = fake_out, fake_err, fake_in
        try:
            self.module.configure_utf8_stdio(platform_override="windows")
        finally:
            sys.stdout, sys.stderr, sys.stdin = original_out, original_err, original_in
        self.assertEqual(fake_out.calls[-1], ("utf-8", "backslashreplace"))
        self.assertEqual(fake_err.calls[-1], ("utf-8", "backslashreplace"))
        self.assertEqual(fake_in.calls[-1], ("utf-8", "replace"))


if __name__ == "__main__":
    unittest.main()
