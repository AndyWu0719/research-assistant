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


class SiteCredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.mac_credentials = load_module(ROOT / "MacOS" / "research_assistant" / "site_credentials.py", "mac_site_credentials")
        self.windows_credentials = load_module(ROOT / "Windows" / "research_assistant" / "site_credentials.py", "windows_site_credentials")
        self.mac_config = load_module(ROOT / "MacOS" / "research_assistant" / "config_store.py", "mac_config_store_for_site_accounts")

    def test_public_metadata_never_contains_plaintext_password(self) -> None:
        record = self.mac_credentials.public_record(
            site_key="jstor",
            account_label="HKU",
            username="reader@example.com",
            password="secret-value",
            login_mode="institution-sso",
            institution_hint="HKU",
            auto_fill_enabled=True,
            has_secret=True,
            last_login_success_at="2026-04-20T10:00:00",
            last_session_refresh_at="2026-04-20T10:05:00",
        )
        self.assertNotIn("password", record)
        self.assertNotIn("username", record)
        self.assertEqual(record["username_hint"], "r***@example.com")

    def test_secret_service_name_is_stable_by_site_and_account(self) -> None:
        service = self.mac_credentials.secret_service_name("jstor", "HKU")
        self.assertEqual(service, "research-assistant.site-account.jstor.HKU")

    def test_delete_missing_secret_is_safe(self) -> None:
        class FakeStore(self.mac_credentials.SecretStore):
            def save_secret(self, *_args, **_kwargs):
                raise NotImplementedError

            def load_secret(self, *_args, **_kwargs):
                return None

            def delete_secret(self, *_args, **_kwargs):
                return False

        self.assertFalse(self.mac_credentials.delete_site_secret(FakeStore(), "jstor", "HKU"))

    def test_windows_module_loads_and_shares_same_service_naming(self) -> None:
        service = self.windows_credentials.secret_service_name("jstor", "HKU")
        self.assertEqual(service, "research-assistant.site-account.jstor.HKU")

    def test_config_store_defaults_include_site_account_metadata_bucket(self) -> None:
        site_accounts = self.mac_config.DEFAULT_USER_PREFERENCES["site_accounts"]
        self.assertEqual(site_accounts["records"], [])
        self.assertEqual(site_accounts["active_site_filter"], "all")

    def test_normalize_site_account_record_keeps_only_public_metadata(self) -> None:
        record = self.mac_config.normalize_site_account_record(
            {
                "site_key": "jstor",
                "account_label": "HKU",
                "username_hint": "r***@example.com",
                "login_mode": "institution-sso",
                "institution_hint": "HKU",
                "auto_fill_enabled": True,
                "has_secret": True,
                "last_login_success_at": "2026-04-20T10:00:00",
                "last_session_refresh_at": "2026-04-20T10:05:00",
                "password": "should-not-survive",
            }
        )
        self.assertNotIn("password", record)
        self.assertEqual(record["site_key"], "jstor")
        self.assertTrue(record["has_secret"])


if __name__ == "__main__":
    unittest.main()
