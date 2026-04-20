from __future__ import annotations

import importlib.util
import sys
import tempfile
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


class SiteAccessTests(unittest.TestCase):
    def setUp(self) -> None:
        self.module = load_module(ROOT / "MacOS" / "research_assistant" / "site_access.py", "mac_site_access")

    def test_detects_sciencedirect_as_protected(self) -> None:
        state = self.module.inspect_reference("https://www.sciencedirect.com/science/article/pii/S000000000")
        self.assertTrue(state.requires_auth)
        self.assertEqual(state.site_key, "sciencedirect")

    def test_public_arxiv_reference_stays_public(self) -> None:
        state = self.module.inspect_reference("https://arxiv.org/abs/2401.00001")
        self.assertFalse(state.requires_auth)
        self.assertIsNone(state.site_key)

    def test_session_storage_is_isolated_by_site_and_account(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            path = self.module.session_storage_dir(root, "jstor", "HKU")
            self.assertEqual(path, root / "jstor" / "HKU")

    def test_missing_account_returns_auth_required(self) -> None:
        response = self.module.maybe_handle_protected_site(
            reference="https://www.sciencedirect.com/science/article/pii/S000000000",
            output_dir=Path("/tmp"),
            filename=None,
            force=False,
            resolve_only=False,
        )
        self.assertEqual(response["status"], "auth_required")
        self.assertEqual(response["site_key"], "sciencedirect")


if __name__ == "__main__":
    unittest.main()
