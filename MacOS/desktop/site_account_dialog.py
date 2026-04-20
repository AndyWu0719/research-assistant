from __future__ import annotations

import shutil

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from research_assistant.config_store import load_site_account_preferences, save_site_account_preferences
from research_assistant.language import normalize_language
from research_assistant.site_access import SITE_SESSIONS_DIR, session_storage_dir
from research_assistant.site_catalog import PROTECTED_SITES
from research_assistant.site_credentials import SecretStore, delete_site_secret, load_site_secret, public_record, save_site_secret


def ui_text(zh_cn: str, en_us: str, language: str) -> str:
    return en_us if normalize_language(language) == "en-US" else zh_cn


def configured_site_account_count() -> int:
    records = load_site_account_preferences().get("records") or []
    return sum(1 for record in records if record.get("has_secret"))


def site_account_summary_text(language: str) -> str:
    count = configured_site_account_count()
    return ui_text(f"已配置 {count} 个授权站点账号", f"{count} protected site accounts configured", language)


class SiteAccountDialog(QDialog):
    def __init__(self, language: str, parent=None) -> None:
        super().__init__(parent)
        self.language = normalize_language(language)
        self.store = SecretStore()
        self.setWindowTitle(ui_text("站点账号", "Site Accounts", self.language))
        self.resize(980, 620)

        root = QHBoxLayout(self)
        self.site_list = QListWidget()
        root.addWidget(self.site_list, 1)

        detail = QWidget()
        detail_layout = QVBoxLayout(detail)
        self.status_label = QLabel(site_account_summary_text(self.language))
        self.status_label.setWordWrap(True)
        detail_layout.addWidget(self.status_label)

        form = QFormLayout()
        self.site_name_label = QLabel("-")
        form.addRow(ui_text("站点", "Site", self.language), self.site_name_label)

        self.account_label_input = QLineEdit()
        form.addRow(ui_text("账号标签", "Account Label", self.language), self.account_label_input)

        self.username_input = QLineEdit()
        form.addRow(ui_text("用户名 / 邮箱", "Username / Email", self.language), self.username_input)

        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.EchoMode.Password)
        form.addRow(ui_text("密码", "Password", self.language), self.password_input)

        self.login_mode_combo = QComboBox()
        self.login_mode_combo.addItem(ui_text("普通账号", "Direct Login", self.language), "direct")
        self.login_mode_combo.addItem(ui_text("机构 SSO", "Institution SSO", self.language), "institution-sso")
        form.addRow(ui_text("登录模式", "Login Mode", self.language), self.login_mode_combo)

        self.institution_input = QLineEdit()
        form.addRow(ui_text("机构提示", "Institution Hint", self.language), self.institution_input)

        self.auto_fill_checkbox = QCheckBox(ui_text("允许自动填充账号密码", "Allow Auto-Fill", self.language))
        form.addRow(self.auto_fill_checkbox)
        detail_layout.addLayout(form)

        buttons = QHBoxLayout()
        self.save_button = QPushButton(ui_text("保存凭据", "Save Credentials", self.language))
        self.test_button = QPushButton(ui_text("测试读取", "Test Secret", self.language))
        self.clear_session_button = QPushButton(ui_text("清除会话", "Clear Session", self.language))
        self.delete_button = QPushButton(ui_text("删除凭据", "Delete Credentials", self.language))
        buttons.addWidget(self.save_button)
        buttons.addWidget(self.test_button)
        buttons.addWidget(self.clear_session_button)
        buttons.addWidget(self.delete_button)
        detail_layout.addLayout(buttons)
        detail_layout.addStretch(1)
        root.addWidget(detail, 2)

        self.site_list.currentItemChanged.connect(self._load_current_record)
        self.save_button.clicked.connect(self.save_current_record)
        self.test_button.clicked.connect(self.test_current_secret)
        self.clear_session_button.clicked.connect(self.clear_current_session)
        self.delete_button.clicked.connect(self.delete_current_record)

        self._populate_sites()

    def _records(self) -> list[dict[str, object]]:
        return list(load_site_account_preferences().get("records") or [])

    def _current_site_key(self) -> str:
        item = self.site_list.currentItem()
        return str(item.data(32) or "").strip() if item else ""

    def _populate_sites(self) -> None:
        self.site_list.clear()
        for site_key, payload in PROTECTED_SITES.items():
            item = QListWidgetItem(str(payload["label"]))
            item.setData(32, site_key)
            self.site_list.addItem(item)
        if self.site_list.count():
            self.site_list.setCurrentRow(0)

    def _find_record(self, site_key: str) -> dict[str, object] | None:
        for record in self._records():
            if record.get("site_key") == site_key:
                return record
        return None

    def _load_current_record(self, *_args) -> None:
        site_key = self._current_site_key()
        payload = PROTECTED_SITES.get(site_key, {})
        self.site_name_label.setText(str(payload.get("label") or "-"))
        record = self._find_record(site_key) or {}
        self.account_label_input.setText(str(record.get("account_label") or ""))
        self.username_input.setText("")
        self.password_input.setText("")
        self.login_mode_combo.setCurrentIndex(max(0, self.login_mode_combo.findData(record.get("login_mode") or "direct")))
        self.institution_input.setText(str(record.get("institution_hint") or ""))
        self.auto_fill_checkbox.setChecked(bool(record.get("auto_fill_enabled", True)))
        self.status_label.setText(site_account_summary_text(self.language))

    def save_current_record(self) -> None:
        site_key = self._current_site_key()
        account_label = self.account_label_input.text().strip()
        username = self.username_input.text().strip()
        password = self.password_input.text()
        if not site_key or not account_label or not username or not password:
            QMessageBox.warning(self, self.windowTitle(), ui_text("请补全站点、账号标签、用户名和密码。", "Fill in site, account label, username, and password.", self.language))
            return
        save_site_secret(self.store, site_key, account_label, username, password)
        record = public_record(
            site_key=site_key,
            account_label=account_label,
            username=username,
            login_mode=self.login_mode_combo.currentData(),
            institution_hint=self.institution_input.text().strip(),
            auto_fill_enabled=self.auto_fill_checkbox.isChecked(),
            has_secret=True,
            last_login_success_at="",
            last_session_refresh_at="",
        )
        records = [item for item in self._records() if item.get("site_key") != site_key]
        records.append(record)
        save_site_account_preferences({"records": records, "active_site_filter": "all"})
        self.status_label.setText(site_account_summary_text(self.language))
        QMessageBox.information(self, self.windowTitle(), ui_text("站点凭据已保存到系统安全存储。", "Site credentials were saved to the system secure store.", self.language))

    def test_current_secret(self) -> None:
        site_key = self._current_site_key()
        account_label = self.account_label_input.text().strip()
        if not site_key or not account_label:
            QMessageBox.information(self, self.windowTitle(), ui_text("请先选择站点并填写账号标签。", "Choose a site and account label first.", self.language))
            return
        payload = load_site_secret(self.store, site_key, account_label)
        if payload:
            QMessageBox.information(self, self.windowTitle(), ui_text("已成功读取系统安全存储中的凭据。", "Successfully loaded credentials from the secure store.", self.language))
            return
        QMessageBox.warning(self, self.windowTitle(), ui_text("当前没有可读取的已保存凭据。", "No saved credential could be loaded for this site.", self.language))

    def clear_current_session(self) -> None:
        site_key = self._current_site_key()
        account_label = self.account_label_input.text().strip()
        if not site_key or not account_label:
            return
        session_dir = session_storage_dir(SITE_SESSIONS_DIR, site_key, account_label)
        if session_dir.exists():
            shutil.rmtree(session_dir)
        QMessageBox.information(self, self.windowTitle(), ui_text("站点会话已清除。", "Site session cleared.", self.language))

    def delete_current_record(self) -> None:
        site_key = self._current_site_key()
        account_label = self.account_label_input.text().strip()
        if not site_key or not account_label:
            return
        delete_site_secret(self.store, site_key, account_label)
        records = [
            item
            for item in self._records()
            if not (item.get("site_key") == site_key and item.get("account_label") == account_label)
        ]
        save_site_account_preferences({"records": records, "active_site_filter": "all"})
        self._load_current_record()
        QMessageBox.information(self, self.windowTitle(), ui_text("站点凭据已删除。", "Site credentials removed.", self.language))
