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


class CompactTimeRangeWidgetTests(unittest.TestCase):
    def test_widget_serializes_to_existing_payload_shape(self) -> None:
        module = load_module(ROOT / "MacOS" / "desktop" / "time_range_controls.py", "mac_time_range_controls")
        payload = module.serialize_compact_range(14, "day")
        self.assertEqual(payload, {"mode": "rolling", "days": 14, "label": "最近 14 天"})


if __name__ == "__main__":
    unittest.main()
