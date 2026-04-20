from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from research_assistant.config_store import CONFIGS_DIR, load_site_account_preferences
from research_assistant.site_catalog import detect_protected_site


SITE_SESSIONS_DIR = CONFIGS_DIR / "site_sessions"


@dataclass(slots=True)
class AccessInspection:
    reference: str
    site_key: str | None
    requires_auth: bool


def inspect_reference(reference: str) -> AccessInspection:
    site_key = detect_protected_site(reference)
    return AccessInspection(reference=reference, site_key=site_key, requires_auth=site_key is not None)


def session_storage_dir(root: Path, site_key: str, account_label: str) -> Path:
    return root / site_key / account_label


def session_cookie_store(root: Path, site_key: str, account_label: str) -> Path:
    return session_storage_dir(root, site_key, account_label) / "profile"


def session_cookie_file(root: Path, site_key: str, account_label: str) -> Path:
    return session_storage_dir(root, site_key, account_label) / "cookies.json"


def resolve_site_account(site_key: str | None) -> dict[str, object] | None:
    if not site_key:
        return None
    records = load_site_account_preferences().get("records") or []
    for record in records:
        if record.get("site_key") == site_key and record.get("has_secret"):
            return record
    return None


def load_session_cookies(site_key: str, account_label: str, root: Path | None = None) -> list[dict[str, str]]:
    path = session_cookie_file(root or SITE_SESSIONS_DIR, site_key, account_label)
    if not path.exists():
        return []
    payload = json.loads(path.read_text(encoding="utf-8"))
    return [item for item in payload if isinstance(item, dict) and item.get("name") and item.get("value")]


def authenticated_cookie_header(site_key: str, account_label: str, root: Path | None = None) -> str:
    cookies = load_session_cookies(site_key, account_label, root=root)
    return "; ".join(f"{item['name']}={item['value']}" for item in cookies)


def session_is_valid(site_key: str, account_label: str, root: Path | None = None) -> bool:
    return bool(load_session_cookies(site_key, account_label, root=root))


def maybe_handle_protected_site(
    reference: str,
    output_dir: Path,
    filename: str | None,
    force: bool,
    resolve_only: bool,
) -> dict[str, object]:
    inspection = inspect_reference(reference)
    if not inspection.requires_auth:
        return {"status": "not_protected", "reference": reference}
    account = resolve_site_account(inspection.site_key)
    if not account:
        return {"status": "auth_required", "site_key": inspection.site_key, "resume_reference": reference}
    account_label = str(account.get("account_label") or "").strip()
    if not session_is_valid(str(inspection.site_key), account_label):
        return {"status": "auth_required", "site_key": inspection.site_key, "resume_reference": reference}
    return {
        "status": "ok",
        "mode": "protected-session",
        "site_key": inspection.site_key,
        "reference": reference,
        "output_dir": str(output_dir),
        "filename": filename or "",
        "force": force,
        "resolve_only": resolve_only,
    }
