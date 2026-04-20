from __future__ import annotations

from PySide6.QtCore import QUrl, Signal
from PySide6.QtWidgets import QDialog, QVBoxLayout
from PySide6.QtWebEngineCore import QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView


class SiteLoginDialog(QDialog):
    login_completed = Signal(dict)

    def __init__(self, login_url: str, profile_dir: str, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("站点登录")
        self.resize(980, 760)
        self.profile = QWebEngineProfile(self)
        self.profile.setPersistentStoragePath(profile_dir)
        self.page = QWebEnginePage(self.profile, self)
        self.view = QWebEngineView(self)
        self.view.setPage(self.page)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.view)
        self.view.load(QUrl(login_url))
