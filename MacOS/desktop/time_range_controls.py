from __future__ import annotations

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QHBoxLayout, QLabel, QWidget

from research_assistant.language import normalize_language
from research_assistant.site_catalog import compact_time_range_to_payload, payload_to_compact_time_range


def ui_text(zh_cn: str, en_us: str, language: str) -> str:
    return en_us if normalize_language(language) == "en-US" else zh_cn


def serialize_compact_range(value: int, unit: str) -> dict[str, object]:
    return compact_time_range_to_payload(int(value), str(unit))


class CompactTimeRangeRow(QWidget):
    changed = Signal()

    def __init__(self, language: str, parent=None) -> None:
        super().__init__(parent)
        self.language = normalize_language(language)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        self.prefix_label = QLabel(ui_text("最近", "Last", self.language))
        self.value_combo = QComboBox()
        for value in [7, 14, 30, 60, 90, 180, 365]:
            self.value_combo.addItem(str(value), value)
        self.unit_combo = QComboBox()
        self.unit_combo.addItem(ui_text("天", "day(s)", self.language), "day")
        self.unit_combo.addItem(ui_text("年", "year(s)", self.language), "year")

        layout.addWidget(self.prefix_label)
        layout.addWidget(self.value_combo, 1)
        layout.addWidget(self.unit_combo)
        layout.addStretch(1)

        self.value_combo.currentIndexChanged.connect(lambda *_args: self.changed.emit())
        self.unit_combo.currentIndexChanged.connect(lambda *_args: self.changed.emit())

    def payload(self) -> dict[str, object]:
        return serialize_compact_range(int(self.value_combo.currentData()), str(self.unit_combo.currentData()))

    def set_payload(self, payload: dict[str, object]) -> None:
        value, unit = payload_to_compact_time_range(payload)
        value_index = self.value_combo.findData(value)
        if value_index < 0:
            self.value_combo.addItem(str(value), value)
            value_index = self.value_combo.findData(value)
        self.value_combo.setCurrentIndex(max(0, value_index))
        self.unit_combo.setCurrentIndex(max(0, self.unit_combo.findData(unit)))
