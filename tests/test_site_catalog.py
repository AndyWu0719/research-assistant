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


class SiteCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mac_catalog = load_module(ROOT / "MacOS" / "research_assistant" / "site_catalog.py", "mac_site_catalog")
        self.windows_catalog = load_module(ROOT / "Windows" / "research_assistant" / "site_catalog.py", "windows_site_catalog")

    def test_discovery_sources_cover_social_science_and_humanities(self) -> None:
        discovery = self.mac_catalog.discovery_source_options()
        for expected in ["SSRN", "PubMed", "ERIC", "JSTOR", "Project MUSE", "PhilPapers"]:
            self.assertIn(expected, discovery)

    def test_protected_site_keys_include_expected_platforms(self) -> None:
        protected = self.mac_catalog.protected_site_keys()
        for expected in [
            "jstor",
            "project_muse",
            "proquest",
            "ebscohost",
            "sciencedirect",
            "springerlink",
            "wiley",
            "taylor_and_francis",
            "sage",
        ]:
            self.assertIn(expected, protected)

    def test_compact_time_range_round_trips_between_ui_and_payload(self) -> None:
        payload = self.mac_catalog.compact_time_range_to_payload(30, "day")
        self.assertEqual(payload, {"mode": "rolling", "days": 30, "label": "最近 30 天"})
        value, unit = self.mac_catalog.payload_to_compact_time_range({"mode": "rolling", "days": 365, "label": "最近 1 年"})
        self.assertEqual((value, unit), (1, "year"))

    def test_detect_protected_site_matches_known_domain(self) -> None:
        self.assertEqual(
            self.mac_catalog.detect_protected_site("https://www.sciencedirect.com/science/article/pii/S000000000"),
            "sciencedirect",
        )
        self.assertIsNone(self.mac_catalog.detect_protected_site("https://arxiv.org/abs/2401.00001"))

    def test_windows_catalog_mirrors_macos(self) -> None:
        self.assertEqual(self.windows_catalog.discovery_source_options(), self.mac_catalog.discovery_source_options())
        self.assertEqual(self.windows_catalog.protected_site_keys(), self.mac_catalog.protected_site_keys())


if __name__ == "__main__":
    unittest.main()
