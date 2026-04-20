from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtCore import QUrl, Signal
from PySide6.QtNetwork import QNetworkCookie
from PySide6.QtWidgets import QDialog, QHBoxLayout, QLabel, QMessageBox, QPushButton, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView

from research_assistant.language import normalize_language
from research_assistant.site_access import (
    SITE_SESSIONS_DIR,
    inspect_reference,
    resolve_site_account,
    session_cookie_file,
    session_cookie_store,
    session_is_valid,
    session_storage_dir,
)
from research_assistant.site_credentials import SecretStore, load_site_secret


def ui_text(zh_cn: str, en_us: str, language: str) -> str:
    return en_us if normalize_language(language) == "en-US" else zh_cn


class SiteLoginDialog(QDialog):
    login_completed = Signal(dict)

    def __init__(
        self,
        *,
        site_key: str,
        account_label: str,
        login_url: str,
        profile_dir: Path,
        cookies_path: Path,
        username: str,
        password: str,
        language: str,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.language = normalize_language(language)
        self.site_key = site_key
        self.account_label = account_label
        self.cookies_path = cookies_path
        self.username = username
        self.password = password
        self.cookies: dict[str, dict[str, object]] = {}

        self.setWindowTitle(ui_text("站点登录", "Site Login", self.language))
        self.resize(980, 760)

        self.profile = QWebEngineProfile(self)
        self.profile.setPersistentStoragePath(str(profile_dir))
        self.profile.setPersistentCookiesPolicy(QWebEngineProfile.PersistentCookiesPolicy.ForcePersistentCookies)
        self.profile.cookieStore().cookieAdded.connect(self._on_cookie_added)

        self.page = QWebEnginePage(self.profile, self)
        self.view = QWebEngineView(self)
        self.view.setPage(self.page)
        self.view.loadFinished.connect(self._auto_fill_credentials)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        hint = QLabel(
            ui_text(
                "应用会尝试自动填入用户名和密码；若进入学校 SSO 或 MFA，请在此窗口手动完成，完成后点击“继续下载”。",
                "The app will try to auto-fill username and password. If your institution SSO or MFA takes over, finish it in this window and click Continue Download.",
                self.language,
            )
        )
        hint.setWordWrap(True)
        hint.setContentsMargins(12, 12, 12, 12)
        layout.addWidget(hint)
        layout.addWidget(self.view, 1)

        buttons = QHBoxLayout()
        buttons.setContentsMargins(12, 12, 12, 12)
        buttons.addWidget(QLabel(ui_text("完成网页登录后再继续。", "Finish the web login before continuing.", self.language)))
        buttons.addStretch(1)
        continue_button = QPushButton(ui_text("继续下载", "Continue Download", self.language))
        cancel_button = QPushButton(ui_text("取消", "Cancel", self.language))
        continue_button.clicked.connect(self._complete_login)
        cancel_button.clicked.connect(self.reject)
        buttons.addWidget(cancel_button)
        buttons.addWidget(continue_button)
        layout.addLayout(buttons)

        self.view.load(QUrl(login_url))

    def _cookie_to_payload(self, cookie: QNetworkCookie) -> dict[str, object]:
        return {
            "name": bytes(cookie.name()).decode("utf-8", errors="ignore"),
            "value": bytes(cookie.value()).decode("utf-8", errors="ignore"),
            "domain": cookie.domain(),
            "path": cookie.path(),
            "secure": cookie.isSecure(),
            "http_only": cookie.isHttpOnly(),
        }

    def _persist_cookies(self) -> None:
        self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
        payload = [value for value in self.cookies.values() if value.get("name") and value.get("value")]
        self.cookies_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    def _on_cookie_added(self, cookie: QNetworkCookie) -> None:
        payload = self._cookie_to_payload(cookie)
        key = f"{payload['domain']}|{payload['path']}|{payload['name']}"
        self.cookies[key] = payload
        self._persist_cookies()

    def _auto_fill_credentials(self, ok: bool) -> None:
        if not ok:
            return
        script = f"""
(() => {{
  const username = {json.dumps(self.username)};
  const password = {json.dumps(self.password)};
  const userSelectors = [
    'input[type=email]',
    'input[name=email]',
    'input[name=username]',
    'input[name=user]',
    'input[id*=email]',
    'input[id*=user]',
    'input[type=text]'
  ];
  const passSelectors = [
    'input[type=password]',
    'input[name=password]',
    'input[id*=password]'
  ];
  const userField = userSelectors.map((selector) => document.querySelector(selector)).find(Boolean);
  const passField = passSelectors.map((selector) => document.querySelector(selector)).find(Boolean);
  if (userField && !userField.value) {{
    userField.focus();
    userField.value = username;
    userField.dispatchEvent(new Event('input', {{bubbles: true}}));
    userField.dispatchEvent(new Event('change', {{bubbles: true}}));
  }}
  if (passField && !passField.value) {{
    passField.focus();
    passField.value = password;
    passField.dispatchEvent(new Event('input', {{bubbles: true}}));
    passField.dispatchEvent(new Event('change', {{bubbles: true}}));
  }}
  return {{filledUser: Boolean(userField), filledPassword: Boolean(passField)}};
}})();
"""
        self.page.runJavaScript(script)

    def _complete_login(self) -> None:
        self._persist_cookies()
        self.login_completed.emit({"site_key": self.site_key, "account_label": self.account_label, "cookies_path": str(self.cookies_path)})
        self.accept()


def ensure_site_login(reference: str, language: str, parent=None) -> dict[str, object]:
    resolved_language = normalize_language(language)
    inspection = inspect_reference(reference)
    if not inspection.requires_auth:
        return {"status": "not_protected", "reference": reference}

    record = resolve_site_account(inspection.site_key)
    if not record:
        return {
            "status": "auth_required",
            "site_key": inspection.site_key,
            "message": ui_text("该站点需要先在“站点账号”中配置凭据。", "Configure credentials in Site Accounts before accessing this site.", resolved_language),
        }

    account_label = str(record.get("account_label") or "").strip()
    if session_is_valid(str(inspection.site_key), account_label):
        return {"status": "ready", "site_key": inspection.site_key}

    secret = load_site_secret(SecretStore(), str(inspection.site_key), account_label)
    if not secret:
        return {
            "status": "auth_required",
            "site_key": inspection.site_key,
            "message": ui_text("当前站点还没有可读取的安全凭据。", "No readable secure credential is stored for this site.", resolved_language),
        }

    session_dir = session_storage_dir(SITE_SESSIONS_DIR, str(inspection.site_key), account_label)
    profile_dir = session_cookie_store(SITE_SESSIONS_DIR, str(inspection.site_key), account_label)
    cookies_path = session_cookie_file(SITE_SESSIONS_DIR, str(inspection.site_key), account_label)
    session_dir.mkdir(parents=True, exist_ok=True)
    profile_dir.mkdir(parents=True, exist_ok=True)

    dialog = SiteLoginDialog(
        site_key=str(inspection.site_key),
        account_label=account_label,
        login_url=reference,
        profile_dir=profile_dir,
        cookies_path=cookies_path,
        username=str(secret["username"]),
        password=str(secret["password"]),
        language=resolved_language,
        parent=parent,
    )
    dialog.exec()
    if session_is_valid(str(inspection.site_key), account_label):
        return {"status": "ready", "site_key": inspection.site_key}

    QMessageBox.information(
        parent,
        ui_text("站点登录未完成", "Site Login Incomplete", resolved_language),
        ui_text("未检测到可复用的登录会话，请完成网页登录后再继续。", "No reusable login session was detected. Finish the web login before continuing.", resolved_language),
    )
    return {"status": "canceled", "site_key": inspection.site_key}
