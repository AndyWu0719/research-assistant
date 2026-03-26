from __future__ import annotations

import json
import os
import signal
import subprocess
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QThread, Qt, QTimer, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QListView,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QTextBrowser,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from desktop.runtime import runtime_project_root, scheduler_command, workspace_root
from research_assistant.app_update import (
    check_for_updates,
    current_version,
    download_update_package,
    mark_update_prompted,
    should_auto_check_updates,
)
from research_assistant.automation_runtime import automation_schedule_snapshot, daemon_snapshot, run_local_automation
from research_assistant.codex_bridge import (
    BridgeResponse,
    ConstraintExplorerInput,
    IdeaFeasibilityInput,
    LiteratureScoutInput,
    PaperFetcherInput,
    PaperReaderInput,
    TopicMapperInput,
    capability_matrix,
    detect_codex_cli,
    download_and_run_reader,
    run_constraint_explorer,
    run_idea_feasibility,
    run_literature_scout,
    run_paper_fetch,
    run_paper_reader,
    run_topic_mapper,
)
from research_assistant.config_store import (
    APP_UPDATE_CONFIG_PATH,
    LITERATURE_SCAN_OUTPUT_DIR,
    LITERATURE_SCAN_RESULT_DIRS,
    OUTPUTS_DIR,
    QUALITY_PROFILE_OPTIONS,
    RANKING_PROFILES,
    SOURCE_OPTIONS,
    TIME_RANGE_OPTIONS,
    add_interesting_paper,
    current_automation_config_path,
    default_quality_for_task,
    describe_automation_storage,
    ensure_project_layout,
    load_automation_config,
    load_interesting_papers,
    load_scan_defaults,
    load_user_preferences,
    resolve_quality_profile,
    save_automation_config,
    save_scan_defaults,
    time_range_key,
    update_user_preferences,
)
from research_assistant.language import normalize_language
from research_assistant.prompt_builder import build_daily_automation_prompt
from research_assistant.result_loader import LoadedResult, list_recent_markdown, load_result
from research_assistant.ui_text import (
    home_feature_overview,
    home_parameter_glossary,
    language_option_label,
    page_copy,
    risk_preference_label,
    summary_depth_label,
    t,
    time_range_label,
)


def ui_text(zh_cn: str, en_us: str, language: str) -> str:
    return en_us if normalize_language(language) == "en-US" else zh_cn


def json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2) if payload is not None else ""


def format_timestamp(value: float | int | None) -> str:
    if value is None:
        return "-"
    try:
        return datetime.fromtimestamp(float(value)).strftime("%Y-%m-%d %H:%M:%S")
    except (TypeError, ValueError, OSError):
        return str(value)


def open_local_path(path: Path | str | None) -> None:
    if not path:
        return
    target = Path(path).expanduser().resolve()
    QDesktopServices.openUrl(QUrl.fromLocalFile(str(target)))


def open_external_url(url: str | None) -> None:
    if not url:
        return
    QDesktopServices.openUrl(QUrl(str(url).strip()))


def open_download_target(target: str | None) -> None:
    if not target:
        return
    value = str(target).strip()
    if value.startswith(("https://", "http://", "file://")):
        open_external_url(value)
        return
    open_local_path(value)


def version_label(value: str | None = None) -> str:
    return f"Version {value or current_version()}"


def set_secondary(button: QPushButton) -> QPushButton:
    button.setProperty("secondary", True)
    button.style().unpolish(button)
    button.style().polish(button)
    return button


def markdown_browser(min_height: int = 0) -> QTextBrowser:
    browser = QTextBrowser()
    browser.setOpenExternalLinks(True)
    browser.setMinimumHeight(min_height)
    browser.setFrameShape(QFrame.Shape.NoFrame)
    browser.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
    return browser


def readonly_plaintext(min_height: int = 0) -> QPlainTextEdit:
    editor = QPlainTextEdit()
    editor.setReadOnly(True)
    if min_height:
        editor.setMinimumHeight(min_height)
    return editor


def styled_combo_box() -> QComboBox:
    combo = QComboBox()
    popup = QListView()
    popup.setObjectName("ComboPopup")
    popup.setMouseTracking(True)
    popup.setStyleSheet(
        """
        QListView#ComboPopup {
            background: #fffaf2;
            color: #223126;
            border: 1px solid #d9ceb9;
            border-radius: 12px;
            padding: 6px;
            outline: 0;
        }
        QListView#ComboPopup::item {
            min-height: 30px;
            padding: 7px 10px;
            border-radius: 8px;
            margin: 1px 0;
            color: #223126;
            background: transparent;
        }
        QListView#ComboPopup::item:hover {
            background: #f1e3be;
            color: #17392d;
            font-weight: 700;
        }
        QListView#ComboPopup::item:selected,
        QListView#ComboPopup::item:selected:active,
        QListView#ComboPopup::item:selected:!active {
            background: #ead8ad;
            color: #17392d;
            font-weight: 700;
        }
        """
    )
    combo.setView(popup)
    combo.setMaxVisibleItems(18)
    return combo


def create_topbar_field(label_text: str, field: QWidget, *, min_width: int = 120) -> QWidget:
    shell = QWidget()
    shell.setObjectName("TopBarField")
    layout = QVBoxLayout(shell)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)

    label = QLabel(label_text)
    label.setObjectName("TopBarFieldLabel")
    layout.addWidget(label)

    field.setMinimumWidth(min_width)
    field.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
    layout.addWidget(field)
    return shell


def create_card(title: str, description: str | None = None, *, name: str = "PanelCard") -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName(name)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(18, 18, 18, 18)
    layout.setSpacing(12)

    title_label = QLabel(title)
    title_label.setObjectName("CardTitle")
    layout.addWidget(title_label)

    if description:
        subtitle = QLabel(description)
        subtitle.setWordWrap(True)
        subtitle.setObjectName("CardSubtitle")
        layout.addWidget(subtitle)

    return frame, layout


def create_page_header(title: str, caption: str, extra_widget: QWidget | None = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("PageHeader")
    layout = QHBoxLayout(frame)
    layout.setContentsMargins(4, 4, 4, 6)
    layout.setSpacing(16)

    info = QWidget()
    info.setObjectName("PageHeaderInfo")
    info_layout = QVBoxLayout(info)
    info_layout.setContentsMargins(0, 0, 0, 0)
    info_layout.setSpacing(6)

    title_label = QLabel(title)
    title_label.setObjectName("PageTitle")
    caption_label = QLabel(caption)
    caption_label.setObjectName("PageCaption")
    caption_label.setWordWrap(True)
    info_layout.addWidget(title_label)
    info_layout.addWidget(caption_label)

    layout.addWidget(info, 1)
    if extra_widget is not None:
        extra_widget.setObjectName("PageHeaderExtra")
        layout.addWidget(extra_widget, 0, Qt.AlignmentFlag.AlignTop)
    return frame


def create_metric_card(label: str) -> tuple[QFrame, QLabel]:
    frame = QFrame()
    frame.setObjectName("MetricCard")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    label_widget = QLabel(label)
    label_widget.setObjectName("MetricLabel")
    value_widget = QLabel("-")
    value_widget.setObjectName("MetricValue")
    value_widget.setWordWrap(True)

    layout.addWidget(label_widget)
    layout.addWidget(value_widget)
    return frame, value_widget


def create_action_tile(
    title: str,
    description: str,
    button_text: str,
    callback: Callable[[], None],
) -> QFrame:
    frame = QFrame()
    frame.setObjectName("ActionTile")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(16, 16, 16, 16)
    layout.setSpacing(10)

    title_label = QLabel(title)
    title_label.setObjectName("ActionTitle")
    title_label.setWordWrap(True)

    description_label = QLabel(description)
    description_label.setObjectName("ActionSubtitle")
    description_label.setWordWrap(True)

    button = set_secondary(QPushButton(button_text))
    button.clicked.connect(callback)

    layout.addWidget(title_label)
    layout.addWidget(description_label)
    layout.addStretch(1)
    layout.addWidget(button, 0, Qt.AlignmentFlag.AlignLeft)
    return frame


def create_field_label(text: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName("FieldLabel")
    label.setWordWrap(True)
    return label


def configure_field_form(layout: QFormLayout) -> QFormLayout:
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setLabelAlignment(Qt.AlignmentFlag.AlignLeft)
    layout.setFormAlignment(Qt.AlignmentFlag.AlignTop)
    layout.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
    layout.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    layout.setHorizontalSpacing(0)
    layout.setVerticalSpacing(10)
    return layout


def add_form_row(layout: QFormLayout, label: str, field: QWidget) -> None:
    layout.addRow(create_field_label(label), field)


def create_section_bar(title: str, description: str | None = None) -> QFrame:
    frame = QFrame()
    frame.setObjectName("SectionBar")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    layout.setSpacing(4)

    title_label = QLabel(title)
    title_label.setObjectName("SectionBarTitle")
    title_label.setWordWrap(True)
    layout.addWidget(title_label)

    if description:
        description_label = QLabel(description)
        description_label.setObjectName("SectionBarDescription")
        description_label.setWordWrap(True)
        layout.addWidget(description_label)

    return frame


def create_field_section(title: str, description: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    frame = QFrame()
    frame.setObjectName("FieldSection")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(10)
    layout.addWidget(create_section_bar(title, description))

    body_layout = QVBoxLayout()
    body_layout.setContentsMargins(0, 0, 0, 0)
    body_layout.setSpacing(10)
    layout.addLayout(body_layout)
    return frame, body_layout


def create_field_form_section(title: str, description: str | None = None) -> tuple[QFrame, QFormLayout]:
    frame, body_layout = create_field_section(title, description)
    form_layout = configure_field_form(QFormLayout())
    body_layout.addLayout(form_layout)
    return frame, form_layout


def bullet_markdown(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


class WorkerThread(QThread):
    result_ready = Signal(object)
    error_ready = Signal(str)

    def __init__(self, callback: Callable[[], Any]) -> None:
        super().__init__()
        self._callback = callback

    def run(self) -> None:
        try:
            self.result_ready.emit(self._callback())
        except Exception:
            self.error_ready.emit(traceback.format_exc())


class MultiSelectList(QListWidget):
    def __init__(self, options: list[str], selected: list[str] | None = None) -> None:
        super().__init__()
        self.setObjectName("MultiSelectList")
        self.setSelectionMode(QListWidget.SelectionMode.MultiSelection)
        self.setMinimumHeight(118)
        self.setAlternatingRowColors(False)
        self.setSpacing(4)
        for option in options:
            self.addItem(option)
        self.set_selected_values(selected or [])

    def selected_values(self) -> list[str]:
        return [item.text() for item in self.selectedItems()]

    def set_selected_values(self, values: list[str]) -> None:
        wanted = {value.strip() for value in values}
        for index in range(self.count()):
            item = self.item(index)
            item.setSelected(item.text() in wanted)


class ResultPanel(QWidget):
    def __init__(self, language: str) -> None:
        super().__init__()
        self.language = normalize_language(language)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.summary_box = readonly_plaintext(116)
        self.summary_box.setMaximumHeight(180)

        self.tabs = QTabWidget()
        self.tabs.setObjectName("ResultTabs")
        self.tabs.setDocumentMode(False)

        self.markdown_view = markdown_browser()
        self.metadata_view = readonly_plaintext()
        self.prompt_view = readonly_plaintext()
        self.payload_view = readonly_plaintext()

        self.tabs.addTab(self.markdown_view, ui_text("结果预览", "Preview", self.language))
        self.tabs.addTab(self.metadata_view, ui_text("Metadata", "Metadata", self.language))
        self.tabs.addTab(self.prompt_view, ui_text("Prompt", "Prompt", self.language))
        self.tabs.addTab(self.payload_view, ui_text("执行载荷", "Bridge Payload", self.language))

        layout.addWidget(self.summary_box)
        layout.addWidget(self.tabs, 1)
        self.clear()

    def clear(self) -> None:
        self.summary_box.setPlainText(ui_text("暂无结果。", "No result yet.", self.language))
        self.markdown_view.setMarkdown("")
        self.metadata_view.setPlainText("")
        self.prompt_view.setPlainText("")
        self.payload_view.setPlainText("")

    def show_message(
        self,
        summary: str,
        *,
        markdown: str = "",
        metadata: Any = None,
        prompt: str = "",
        payload: Any = None,
    ) -> None:
        self.summary_box.setPlainText(summary.strip() or ui_text("暂无结果。", "No result yet.", self.language))
        self.markdown_view.setMarkdown(markdown)
        self.metadata_view.setPlainText(json_text(metadata))
        self.prompt_view.setPlainText(prompt or "")
        self.payload_view.setPlainText(json_text(payload))

    def show_loaded_result(self, result: LoadedResult) -> None:
        summary_lines = [
            f"{ui_text('结果文件', 'Result File', self.language)}: {result.path}",
            f"{ui_text('更新时间', 'Updated At', self.language)}: {format_timestamp(result.path.stat().st_mtime)}",
        ]
        if result.metadata:
            summary_lines.append(
                f"{ui_text('状态', 'Status', self.language)}: {result.metadata.get('status', result.metadata.get('summary', '-'))}"
            )
            summary_lines.append(
                f"{ui_text('质量档位', 'Quality Profile', self.language)}: {result.metadata.get('quality_profile', '-')}"
            )
        if result.table_rows:
            summary_lines.append(f"{ui_text('条目数', 'Item Count', self.language)}: {len(result.table_rows)}")
        self.show_message(
            "\n".join(summary_lines),
            markdown=result.content,
            metadata=result.metadata,
        )

    def show_bridge_response(self, response: BridgeResponse) -> None:
        loaded: LoadedResult | None = None
        output_path = response.expected_output_path
        if output_path and Path(output_path).exists():
            loaded = load_result(Path(output_path))

        lines = [
            f"{ui_text('状态', 'Status', self.language)}: {response.status}",
            f"{ui_text('说明', 'Message', self.language)}: {response.message}",
            f"{ui_text('执行模式', 'Execution Mode', self.language)}: {response.mode}",
            f"{ui_text('质量档位', 'Quality Profile', self.language)}: {response.quality_profile}",
        ]
        if response.model:
            lines.append(f"{ui_text('模型', 'Model', self.language)}: {response.model}")
        if response.reasoning_effort:
            lines.append(f"{ui_text('推理强度', 'Reasoning Effort', self.language)}: {response.reasoning_effort}")
        if response.error:
            lines.append(f"{ui_text('错误', 'Error', self.language)}: {response.error}")
        if response.output_paths:
            lines.append("")
            lines.append(ui_text("输出路径", "Output Paths", self.language))
            for key, value in response.output_paths.items():
                if value:
                    lines.append(f"- {key}: {value}")

        self.show_message(
            "\n".join(lines),
            markdown=loaded.content if loaded else "",
            metadata=loaded.metadata if loaded else response.payload,
            prompt=response.prompt_text or "",
            payload=response.payload or response.to_dict(),
        )


class ScrollPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self.canvas = QWidget()
        self.canvas.setObjectName("PageCanvas")
        self.content_layout = QVBoxLayout(self.canvas)
        self.content_layout.setContentsMargins(12, 12, 12, 24)
        self.content_layout.setSpacing(18)

        self.scroll.setWidget(self.canvas)
        outer.addWidget(self.scroll)

    def add_page_header(self, title: str, caption: str, extra_widget: QWidget | None = None) -> None:
        self.content_layout.addWidget(create_page_header(title, caption, extra_widget))

    def add_two_column_section(self, left_stretch: int = 11, right_stretch: int = 10) -> tuple[QVBoxLayout, QVBoxLayout]:
        wrapper = QWidget()
        wrapper.setObjectName("SectionColumns")
        row = QHBoxLayout(wrapper)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(18)

        left = QWidget()
        left.setObjectName("SectionColumn")
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(18)

        right = QWidget()
        right.setObjectName("SectionColumn")
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(18)

        row.addWidget(left, left_stretch)
        row.addWidget(right, right_stretch)
        self.content_layout.addWidget(wrapper)
        return left_layout, right_layout


class HomePage(ScrollPage):
    def __init__(self, language: str) -> None:
        self.language = normalize_language(language)
        self.defaults_browser = markdown_browser(180)
        self.playbook_browser = markdown_browser(180)
        self.activity_browser = markdown_browser(220)
        self.parameters_browser = markdown_browser(280)
        self.capability_browser = markdown_browser(180)
        self.status_box = readonly_plaintext(220)
        self.metric_values: dict[str, QLabel] = {}
        self._page_navigator: Callable[[str], None] | None = None
        super().__init__()
        self._build_ui()
        self.refresh()

    def set_page_navigator(self, navigator: Callable[[str], None]) -> None:
        self._page_navigator = navigator

    def open_page(self, page_key: str) -> None:
        if self._page_navigator:
            self._page_navigator(page_key)

    def _build_ui(self) -> None:
        copy = page_copy("home", self.language)

        hero_actions = QWidget()
        hero_actions.setObjectName("HeaderActions")
        hero_actions_layout = QVBoxLayout(hero_actions)
        hero_actions_layout.setContentsMargins(0, 0, 0, 0)
        hero_actions_layout.setSpacing(10)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 0, 0, 0)
        button_row.setSpacing(10)
        refresh_button = QPushButton(ui_text("刷新状态", "Refresh", self.language))
        refresh_button.clicked.connect(self.refresh)
        open_workspace_button = set_secondary(QPushButton(ui_text("打开工作区", "Open Workspace", self.language)))
        open_workspace_button.clicked.connect(lambda: open_local_path(runtime_project_root()))
        open_outputs_button = set_secondary(QPushButton(ui_text("打开 outputs", "Open Outputs", self.language)))
        open_outputs_button.clicked.connect(lambda: open_local_path(OUTPUTS_DIR))
        button_row.addWidget(refresh_button)
        button_row.addWidget(open_workspace_button)
        button_row.addWidget(open_outputs_button)
        button_row.addStretch(1)

        metrics_row = QWidget()
        metrics_row.setObjectName("HeaderMetricRow")
        metrics_layout = QHBoxLayout(metrics_row)
        metrics_layout.setContentsMargins(0, 0, 0, 0)
        metrics_layout.setSpacing(10)
        for key, label in [
            ("language", ui_text("界面语言", "Interface Language", self.language)),
            ("field", ui_text("默认研究方向", "Default Field", self.language)),
            ("top_k", ui_text("默认返回数量", "Default Top K", self.language)),
            ("run_time", ui_text("自动化时间", "Automation Time", self.language)),
            ("interesting", ui_text("感兴趣论文", "Interesting Papers", self.language)),
        ]:
            card, value_label = create_metric_card(label)
            self.metric_values[key] = value_label
            metrics_layout.addWidget(card, 2 if key == "field" else 1)

        hero_actions_layout.addLayout(button_row)
        self.add_page_header(copy["title"], copy["caption"], hero_actions)
        self.content_layout.addWidget(metrics_row)

        left_layout, right_layout = self.add_two_column_section(12, 8)

        actions_card, actions_layout = create_card(
            ui_text("快捷入口", "Quick Actions", self.language),
        )
        actions_grid = QGridLayout()
        actions_grid.setContentsMargins(0, 0, 0, 0)
        actions_grid.setHorizontalSpacing(12)
        actions_grid.setVerticalSpacing(12)
        action_specs = [
            ("literature_scout", ui_text("文献巡检", "Literature Scan", self.language), ui_text("快速收敛最近值得跟进的论文。", "Narrow down the latest papers worth following.", self.language)),
            ("paper_reader", ui_text("单篇论文精读", "Paper Deep Read", self.language), ui_text("围绕一篇论文做结构化拆解。", "Produce a structured breakdown of one paper.", self.language)),
            ("topic_mapper", ui_text("方向地图", "Topic Map", self.language), ui_text("搭建新方向的阅读地图和主题簇。", "Build a reading map and topic clusters for a new area.", self.language)),
            ("idea_feasibility", ui_text("想法可行性", "Idea Feasibility", self.language), ui_text("先判断一个想法值不值得做。", "Check whether an idea is worth pursuing.", self.language)),
            ("constraint_explorer", ui_text("约束探索", "Constraint Explorer", self.language), ui_text("在有限算力和时间下找切入口。", "Find viable entry points under limited resources.", self.language)),
            ("automation_config", ui_text("自动化配置", "Automation Setup", self.language), ui_text("把高频任务整理成可持续运行的自动化。", "Turn repeated workflows into reusable automation.", self.language)),
        ]
        for index, (page_key, title, subtitle) in enumerate(action_specs):
            tile = create_action_tile(
                title,
                subtitle,
                ui_text("打开", "Open", self.language),
                lambda checked=False, key=page_key: self.open_page(key),
            )
            actions_grid.addWidget(tile, index // 3, index % 3)
        actions_layout.addLayout(actions_grid)
        left_layout.addWidget(actions_card)

        activity_card, activity_layout = create_card(
            ui_text("最近动态", "Recent Activity", self.language),
        )
        activity_layout.addWidget(self.activity_browser)
        left_layout.addWidget(activity_card, 1)

        playbook_card, playbook_layout = create_card(
            ui_text("使用路径", "Playbooks", self.language),
        )
        playbook_layout.addWidget(self.playbook_browser)
        left_layout.addWidget(playbook_card)

        status_card, status_layout = create_card(
            ui_text("本地执行环境", "Local Runtime", self.language),
        )
        status_layout.addWidget(self.status_box)
        right_layout.addWidget(status_card)

        capability_card, capability_layout = create_card(
            ui_text("能力状态", "Capability Status", self.language),
        )
        capability_layout.addWidget(self.capability_browser)
        right_layout.addWidget(capability_card)

        defaults_card, defaults_layout = create_card(
            ui_text("研究默认项", "Research Defaults", self.language),
        )
        defaults_layout.addWidget(self.defaults_browser)
        right_layout.addWidget(defaults_card)

        parameters_card, parameters_layout = create_card(
            ui_text("参数解释", "Parameter Guide", self.language),
        )
        parameters_layout.addWidget(self.parameters_browser)
        self.content_layout.addWidget(parameters_card)

    def refresh(self) -> None:
        ensure_project_layout()
        preferences = load_user_preferences()
        daily = load_scan_defaults()
        automation = load_automation_config()
        interesting = load_interesting_papers()
        codex = detect_codex_cli(refresh=True, language=self.language)
        daemon = daemon_snapshot()
        schedule = automation_schedule_snapshot(current_automation_config_path())
        daily_quality = resolve_quality_profile(daily.get("quality_profile"), task_type="literature_scout")

        self.metric_values["language"].setText(language_option_label(preferences["language"], self.language))
        field_value = daily["field"]
        if len(field_value) > 52:
            field_value = field_value[:49] + "..."
        self.metric_values["field"].setText(field_value)
        self.metric_values["top_k"].setText(str(daily["top_k"]))
        self.metric_values["run_time"].setText(automation["schedule"]["time_of_day"])
        self.metric_values["interesting"].setText(str(len(interesting["items"])))

        if normalize_language(self.language) == "en-US":
            path_block = (
                "Beginner Path\n"
                "  Home -> PDF Downloads -> Paper Deep Read -> Literature Scan\n\n"
                "Advanced Path\n"
                "  Literature Scan -> Topic Map -> Idea Feasibility -> Constraint Explorer -> Automation Setup"
            )
        else:
            path_block = (
                "新手路径\n"
                "  首页 -> PDF 下载 -> 单篇论文精读 -> 文献巡检\n\n"
                "进阶路径\n"
                "  文献巡检 -> 方向地图 -> 想法可行性 -> 约束探索 -> 自动化配置"
            )

        self.playbook_browser.setMarkdown(
            "\n".join(
                [
                    "### " + ui_text("推荐使用路径", "Recommended Paths", self.language),
                    "```text",
                    path_block,
                    "```",
                    "",
                    "### " + ui_text("功能概览", "Feature Overview", self.language),
                    *[f"- **{title}**: {summary}" for title, summary in home_feature_overview(self.language)],
                ]
            )
        )

        parameter_rows = home_parameter_glossary(self.language)
        parameter_table = "\n".join(
            [
                f"| {t('home.parameter_field', self.language)} | {t('home.parameter_description', self.language)} |",
                "| --- | --- |",
                *[f"| {name} | {description} |" for name, description in parameter_rows],
            ]
        )
        self.parameters_browser.setMarkdown(parameter_table)

        self.defaults_browser.setMarkdown(
            "\n".join(
                [
                    f"- {t('common.field', self.language)}: `{daily['field']}`",
                    f"- {t('common.time_range', self.language)}: `{time_range_label(daily['time_range'], self.language)}`",
                    f"- {t('common.sources', self.language)}: `{', '.join(daily['sources'])}`",
                    f"- {t('common.ranking_profile', self.language)}: `{daily['ranking_profile']}`",
                    f"- {t('common.quality_profile', self.language)}: `{daily['quality_profile']}`",
                    f"- {t('common.recommended_model', self.language)}: `{daily_quality['model']}`",
                    f"- {t('common.recommended_reasoning', self.language)}: `{daily_quality['reasoning_effort']}`",
                    f"- {t('common.top_k', self.language)}: `{daily['top_k']}`",
                    f"- {ui_text('自动化时间', 'Automation Time', self.language)}: `{automation['schedule']['time_of_day']}`",
                ]
            )
        )

        status_lines = [
            f"{ui_text('工作区', 'Workspace', self.language)}: {runtime_project_root()}",
            f"{ui_text('应用版本', 'App Version', self.language)}: {version_label(current_version())}",
            f"{ui_text('界面语言', 'Interface Language', self.language)}: {preferences['language']}",
            "",
            f"{ui_text('默认排序画像', 'Default Ranking Profile', self.language)}: {daily['ranking_profile']}",
            f"{ui_text('推荐模型', 'Recommended Model', self.language)}: {daily_quality['model']}",
            f"{ui_text('推荐推理强度', 'Recommended Reasoning', self.language)}: {daily_quality['reasoning_effort']}",
            "",
            "Codex CLI",
            f"- {ui_text('可执行', 'Available', self.language)}: {codex.available}",
            f"- {ui_text('路径', 'Path', self.language)}: {codex.executable or '-'}",
            f"- {ui_text('版本', 'Version', self.language)}: {codex.version or '-'}",
            f"- {ui_text('登录可执行', 'Can Execute', self.language)}: {codex.can_execute}",
            f"- {ui_text('状态', 'Status', self.language)}: {codex.message}",
        ]
        if codex.issues:
            status_lines.append(f"- {ui_text('问题', 'Issues', self.language)}:")
            status_lines.extend(f"  - {item}" for item in codex.issues)
        status_lines.extend(
            [
                "",
                ui_text("自动化调度", "Automation Scheduler", self.language),
                f"- {ui_text('调度器运行中', 'Daemon Running', self.language)}: {daemon['is_running']}",
                f"- PID: {daemon.get('pid') or '-'}",
                f"- {ui_text('下次运行', 'Next Run', self.language)}: {schedule.get('next_run_at') or '-'}",
                f"- {ui_text('最近状态', 'Last Status', self.language)}: {schedule.get('last_status') or '-'}",
            ]
        )
        self.status_box.setPlainText("\n".join(status_lines))

        capability_lines: list[str] = []
        for item in capability_matrix(self.language):
            capability_lines.extend(
                [
                    f"### {item['label']} · {item['status']}",
                    item["description"],
                    "",
                ]
            )
        self.capability_browser.setMarkdown("\n".join(capability_lines).strip())

        recent_sections = [
            (t("home.scan_card", self.language), list_recent_markdown(LITERATURE_SCAN_RESULT_DIRS, limit=5)),
            (t("home.summary_card", self.language), list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=5)),
            (t("home.map_card", self.language), list_recent_markdown(OUTPUTS_DIR / "topic_maps", limit=5)),
            (t("home.feasibility_card", self.language), list_recent_markdown(OUTPUTS_DIR / "feasibility_reports", limit=5)),
        ]
        recent_lines: list[str] = []
        for title, items in recent_sections:
            recent_lines.append(f"### {title}")
            if items:
                recent_lines.extend(f"- `{item.name}`" for item in items)
            else:
                empty_key = {
                    t("home.scan_card", self.language): t("home.no_scan", self.language),
                    t("home.summary_card", self.language): t("home.no_summary", self.language),
                    t("home.map_card", self.language): t("home.no_map", self.language),
                    t("home.feasibility_card", self.language): t("home.no_feasibility", self.language),
                }[title]
                recent_lines.append(f"- {empty_key}")
            recent_lines.append("")
        self.activity_browser.setMarkdown("\n".join(recent_lines).strip())


class BaseTaskPage(ScrollPage):
    page_key = ""
    recent_dirs: Path | list[Path] | tuple[Path, ...] = OUTPUTS_DIR
    primary_output_dir = OUTPUTS_DIR

    def __init__(self, language: str) -> None:
        self.language = normalize_language(language)
        self._worker: WorkerThread | None = None
        self._focus_order: list[QWidget] = []
        self._shortcuts: list[QShortcut] = []
        self.current_output_path: Path | None = None
        self.current_loaded_result: LoadedResult | None = None
        self.result_panel = ResultPanel(self.language)
        self.status_box = readonly_plaintext(140)
        self.recent_combo = styled_combo_box()
        self.recent_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.load_recent_button = set_secondary(QPushButton(ui_text("加载历史结果", "Load Result", self.language)))
        self.refresh_recent_button = set_secondary(QPushButton(ui_text("刷新列表", "Refresh", self.language)))
        self.open_dir_button = set_secondary(QPushButton(ui_text("打开目录", "Open Folder", self.language)))
        self.run_button = QPushButton(self.run_button_label())
        self.run_button.setMinimumHeight(46)
        super().__init__()
        self._build_page()
        self.refresh_recent_results()

    def run_button_label(self) -> str:
        return ui_text("执行", "Run", self.language)

    def task_tips_markdown(self) -> str:
        return ""

    def build_right_column_extras(self, layout: QVBoxLayout) -> None:
        return

    def build_form(self, layout: QVBoxLayout) -> None:
        raise NotImplementedError

    def execute_task(self) -> Any:
        raise NotImplementedError

    def register_focus_widgets(self, *widgets: QWidget) -> None:
        for widget in widgets:
            if widget is None or widget in self._focus_order:
                continue
            self._focus_order.append(widget)

    def focus_primary_field(self) -> None:
        if not self._focus_order:
            return
        widget = self._focus_order[0]
        widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if isinstance(widget, QLineEdit):
            widget.selectAll()

    def _apply_tab_order(self) -> None:
        ordered = [widget for widget in self._focus_order if widget is not None]
        for first, second in zip(ordered, ordered[1:]):
            QWidget.setTabOrder(first, second)

    def _add_shortcut(self, sequence: str, callback: Callable[[], None]) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _install_keyboard_flow(self) -> None:
        for sequence in ("Meta+Return", "Ctrl+Return"):
            self._add_shortcut(sequence, self.start_task)
        for sequence in ("Meta+L", "Ctrl+L"):
            self._add_shortcut(sequence, self.focus_primary_field)
        for sequence in ("Meta+Shift+R", "Ctrl+Shift+R"):
            self._add_shortcut(sequence, self.refresh_recent_results)

    def _build_page(self) -> None:
        copy = page_copy(self.page_key, self.language)
        self.add_page_header(copy["title"], copy["caption"])

        left_layout, right_layout = self.add_two_column_section(6, 9)

        form_card, form_layout_wrapper = create_card(
            ui_text("任务字段", "Task Fields", self.language),
        )
        form_layout_wrapper.setSpacing(14)
        self.build_form(form_layout_wrapper)

        button_row = QHBoxLayout()
        button_row.setContentsMargins(0, 2, 0, 0)
        button_row.setSpacing(12)
        keyboard_hint = QLabel(
            ui_text(
                "⌘/Ctrl + Enter 运行 · ⌘/Ctrl + L 聚焦首个字段 · ⌘/Ctrl + Shift + R 刷新历史",
                "Cmd/Ctrl+Enter to run · Cmd/Ctrl+L focus first field · Cmd/Ctrl+Shift+R refresh history",
                self.language,
            )
        )
        keyboard_hint.setObjectName("KeyboardHint")
        button_row.addWidget(keyboard_hint, 1)
        button_row.addWidget(self.run_button, 0, Qt.AlignmentFlag.AlignRight)
        form_layout_wrapper.addLayout(button_row)

        status_heading = QLabel(ui_text("执行状态", "Execution Status", self.language))
        status_heading.setObjectName("SubsectionLabel")
        form_layout_wrapper.addWidget(status_heading)
        form_layout_wrapper.addWidget(self.status_box)

        tips = self.task_tips_markdown().strip()
        if tips:
            tips_browser = markdown_browser(140)
            tips_browser.setMarkdown(tips)
            form_layout_wrapper.addWidget(tips_browser)
        left_layout.addWidget(form_card)

        workbench_card, workbench_layout = create_card(
            ui_text("工作台", "Workbench", self.language),
        )
        toolbar = QHBoxLayout()
        toolbar.setContentsMargins(0, 0, 0, 0)
        toolbar.setSpacing(10)
        toolbar.addWidget(QLabel(t("common.recent_results", self.language)))
        toolbar.addWidget(self.recent_combo, 1)
        toolbar.addWidget(self.load_recent_button)
        toolbar.addWidget(self.refresh_recent_button)
        toolbar.addWidget(self.open_dir_button)
        workbench_layout.addLayout(toolbar)

        self.result_panel.setMinimumHeight(520)
        workbench_layout.addWidget(self.result_panel, 1)
        self.workbench_extra_layout = QVBoxLayout()
        self.workbench_extra_layout.setContentsMargins(0, 0, 0, 0)
        self.workbench_extra_layout.setSpacing(12)
        workbench_layout.addLayout(self.workbench_extra_layout)
        right_layout.addWidget(workbench_card, 1)

        self.build_right_column_extras(self.workbench_extra_layout)

        self.run_button.clicked.connect(self.start_task)
        self.open_dir_button.clicked.connect(self.open_output_directory)
        self.refresh_recent_button.clicked.connect(self.refresh_recent_results)
        self.load_recent_button.clicked.connect(self.load_selected_recent)
        self._apply_tab_order()
        self._install_keyboard_flow()

    def output_directory(self) -> Path:
        return self.current_output_path.parent if self.current_output_path else Path(self.primary_output_dir)

    def open_output_directory(self) -> None:
        open_local_path(self.output_directory())

    def handle_task_success(self, result: Any) -> None:
        if isinstance(result, BridgeResponse):
            self.current_output_path = Path(result.expected_output_path) if result.expected_output_path else None
            self.status_box.setPlainText(result.message)
            self.result_panel.show_bridge_response(result)
            loaded = load_result(self.current_output_path) if self.current_output_path and self.current_output_path.exists() else None
            self.current_loaded_result = loaded
            self.after_result_changed(loaded)
            self.refresh_recent_results()
            return
        self.current_loaded_result = None
        self.after_result_changed(None)
        self.status_box.setPlainText(ui_text("任务已完成。", "Task completed.", self.language))
        self.result_panel.show_message(ui_text("任务已完成。", "Task completed.", self.language), payload=result)

    def after_result_changed(self, result: LoadedResult | None) -> None:
        return

    def start_task(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        self.run_button.setEnabled(False)
        self.status_box.setPlainText(ui_text("正在执行，请稍候...", "Running, please wait...", self.language))
        self._worker = WorkerThread(self.execute_task)
        self._worker.result_ready.connect(self._on_task_success)
        self._worker.error_ready.connect(self._on_task_error)
        self._worker.finished.connect(lambda: self.run_button.setEnabled(True))
        self._worker.start()

    def _on_task_success(self, result: Any) -> None:
        self.handle_task_success(result)

    def _on_task_error(self, trace: str) -> None:
        self.status_box.setPlainText(ui_text("执行失败。", "Execution failed.", self.language) + "\n\n" + trace)
        self.result_panel.show_message(ui_text("执行失败。", "Execution failed.", self.language), payload={"traceback": trace})
        QMessageBox.critical(self, ui_text("执行失败", "Execution Failed", self.language), trace)

    def refresh_recent_results(self) -> None:
        current = self.recent_combo.currentData()
        self.recent_combo.blockSignals(True)
        self.recent_combo.clear()
        for path in list_recent_markdown(self.recent_dirs, limit=30):
            self.recent_combo.addItem(path.name, path)
        self.recent_combo.blockSignals(False)

        if self.recent_combo.count() == 0:
            self.recent_combo.addItem(ui_text("暂无历史结果", "No saved results", self.language), None)
            self.recent_combo.setEnabled(False)
            self.load_recent_button.setEnabled(False)
            return

        self.recent_combo.setEnabled(True)
        self.load_recent_button.setEnabled(True)
        for index in range(self.recent_combo.count()):
            if self.recent_combo.itemData(index) == current:
                self.recent_combo.setCurrentIndex(index)
                break

    def load_selected_recent(self) -> None:
        path = self.recent_combo.currentData()
        if not path:
            return
        loaded = load_result(Path(path))
        self.current_output_path = Path(path)
        self.current_loaded_result = loaded
        self.status_box.setPlainText(f"{ui_text('已加载历史结果', 'Loaded Result', self.language)}: {Path(path).name}")
        self.result_panel.show_loaded_result(loaded)
        self.after_result_changed(loaded)


class LiteratureScoutPage(BaseTaskPage):
    page_key = "literature_scout"
    recent_dirs = LITERATURE_SCAN_RESULT_DIRS
    primary_output_dir = LITERATURE_SCAN_OUTPUT_DIR

    def __init__(self, language: str) -> None:
        self.paper_rows: list[dict[str, str]] = []
        self.paper_selector = styled_combo_box()
        self.paper_selector.setEnabled(False)
        self.paper_browser = markdown_browser(220)
        self.mark_interesting_button = QPushButton()
        self.open_paper_button = set_secondary(QPushButton())
        self.open_code_button = set_secondary(QPushButton())
        super().__init__(language)

    def run_button_label(self) -> str:
        return t("literature_scout.submit", self.language)

    def task_tips_markdown(self) -> str:
        return "\n".join(
            [
                f"- {t('literature_scout.quality_help', self.language)}",
                f"- {ui_text('`Top K` 现在只代表返回数量，不会再固化到目录名或任务名里。', '`Top K` now controls only the return count. It is no longer baked into folder names or task names.', self.language)}",
                f"- {ui_text('如果你给了明确算力、数据或时间约束，建议同步填写“补充约束”，避免结果华而不实。', 'If you have concrete compute, data, or timeline limits, fill the constraints box so the result stays practical.', self.language)}",
            ]
        )

    def build_form(self, layout: QVBoxLayout) -> None:
        preferences = load_user_preferences()
        scan_defaults = load_scan_defaults()
        global_defaults = preferences["global_defaults"]
        task_defaults = preferences["task_defaults"]["literature_scout"]

        scope_section, scope_form = create_field_form_section(
            ui_text("研究范围", "Research Scope", self.language),
            ui_text("先定义研究主题、时间窗和来源范围。", "Start with the research topic, time window, and source scope.", self.language),
        )
        self.field_input = QLineEdit(global_defaults.get("field") or scan_defaults["field"])
        add_form_row(scope_form, t("common.field", self.language), self.field_input)

        self.time_combo = styled_combo_box()
        default_time = global_defaults.get("time_range_key") or time_range_key(scan_defaults["time_range"])
        for key, value in TIME_RANGE_OPTIONS.items():
            self.time_combo.addItem(time_range_label(value, self.language), key)
        self.time_combo.setCurrentIndex(max(0, self.time_combo.findData(default_time)))
        add_form_row(scope_form, t("common.time_range", self.language), self.time_combo)

        default_sources = global_defaults.get("sources") or scan_defaults["sources"]
        self.sources_list = MultiSelectList(SOURCE_OPTIONS, default_sources)
        add_form_row(scope_form, t("common.sources", self.language), self.sources_list)
        layout.addWidget(scope_section)

        strategy_section, strategy_form = create_field_form_section(
            ui_text("排序与执行", "Ranking And Execution", self.language),
            ui_text("统一控制排序策略、执行质量和返回规模。", "Control ranking mode, execution quality, and return volume from one block.", self.language),
        )
        self.ranking_combo = styled_combo_box()
        for item in RANKING_PROFILES:
            self.ranking_combo.addItem(item, item)
        self.ranking_combo.setCurrentIndex(
            max(0, self.ranking_combo.findData(global_defaults.get("ranking_profile") or scan_defaults["ranking_profile"]))
        )
        add_form_row(strategy_form, t("common.ranking_profile", self.language), self.ranking_combo)

        self.quality_combo = styled_combo_box()
        default_quality = task_defaults.get("quality_profile") or default_quality_for_task("literature_scout")
        for item in QUALITY_PROFILE_OPTIONS:
            self.quality_combo.addItem(item, item)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(default_quality)))
        add_form_row(strategy_form, t("common.quality_profile", self.language), self.quality_combo)

        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 50)
        self.topk_spin.setValue(int(global_defaults.get("top_k") or scan_defaults["top_k"]))
        add_form_row(strategy_form, t("common.top_k", self.language), self.topk_spin)
        layout.addWidget(strategy_section)

        context_section, context_form = create_field_form_section(
            ui_text("约束与记忆", "Constraints And Memory", self.language),
            ui_text("把现实约束补进去，并决定是否更新每日默认项。", "Add practical constraints here and decide whether to update the daily default.", self.language),
        )
        default_constraints = (global_defaults.get("constraints") or {}).get("notes") or scan_defaults.get("constraints", {}).get("notes", "")
        self.constraints_edit = QTextEdit()
        self.constraints_edit.setMinimumHeight(130)
        self.constraints_edit.setPlaceholderText(t("literature_scout.constraints_placeholder", self.language))
        self.constraints_edit.setPlainText(default_constraints)
        add_form_row(context_form, t("common.constraints", self.language), self.constraints_edit)

        self.save_daily_checkbox = QCheckBox(t("literature_scout.save_as_daily", self.language))
        context_form.addRow(self.save_daily_checkbox)
        layout.addWidget(context_section)

        self.register_focus_widgets(
            self.field_input,
            self.time_combo,
            self.sources_list,
            self.ranking_combo,
            self.quality_combo,
            self.topk_spin,
            self.constraints_edit,
            self.save_daily_checkbox,
        )

    def build_right_column_extras(self, layout: QVBoxLayout) -> None:
        paper_card, paper_layout = create_card(
            ui_text("Top K 速览", "Top K Focus", self.language),
            ui_text("选择一篇论文后，可直接查看链接并标记感兴趣。", "Pick a paper to inspect links and mark it as interesting.", self.language),
        )

        self.paper_selector.currentIndexChanged.connect(self._update_selected_paper)
        paper_layout.addWidget(self.paper_selector)
        paper_layout.addWidget(self.paper_browser)

        actions = QHBoxLayout()
        self.mark_interesting_button.setText(t("literature_scout.mark_interesting", self.language))
        self.mark_interesting_button.clicked.connect(self.mark_current_paper_interesting)
        self.open_paper_button.setText(ui_text("打开论文", "Open Paper", self.language))
        self.open_paper_button.clicked.connect(lambda: self._open_selected_link("paper_url"))
        self.open_code_button.setText(ui_text("打开代码", "Open Code", self.language))
        self.open_code_button.clicked.connect(lambda: self._open_selected_link("code_url"))
        actions.addWidget(self.mark_interesting_button)
        actions.addWidget(self.open_paper_button)
        actions.addWidget(self.open_code_button)
        paper_layout.addLayout(actions)
        layout.addWidget(paper_card)
        self._update_selected_paper()

    def execute_task(self) -> BridgeResponse:
        preferences = load_user_preferences()
        scan_defaults = load_scan_defaults()
        language = preferences["language"]
        field = self.field_input.text().strip()
        if not field:
            raise ValueError(ui_text("请先填写研究方向。", "Please enter a research area first.", self.language))
        selected_time = self.time_combo.currentData()
        sources = self.sources_list.selected_values() or scan_defaults["sources"]
        constraints = self.constraints_edit.toPlainText().strip()

        update_user_preferences(
            {
                "global_defaults": {
                    "field": field,
                    "time_range_key": selected_time,
                    "sources": sources,
                    "ranking_profile": self.ranking_combo.currentData(),
                    "constraints": {
                        "compute": "",
                        "data": "",
                        "time": "",
                        "budget": "",
                        "notes": constraints,
                    },
                    "top_k": int(self.topk_spin.value()),
                },
                "task_defaults": {
                    "literature_scout": {
                        "quality_profile": self.quality_combo.currentData(),
                    }
                },
            }
        )

        if self.save_daily_checkbox.isChecked():
            save_scan_defaults(
                {
                    "field": field,
                    "time_range": TIME_RANGE_OPTIONS[selected_time],
                    "sources": sources,
                    "ranking_profile": self.ranking_combo.currentData(),
                    "quality_profile": self.quality_combo.currentData(),
                    "constraints": {
                        "compute": "",
                        "data": "",
                        "time": "",
                        "budget": "",
                        "notes": constraints,
                    },
                    "top_k": int(self.topk_spin.value()),
                    "language": language,
                }
            )

        return run_literature_scout(
            LiteratureScoutInput(
                field=field,
                time_range=TIME_RANGE_OPTIONS[selected_time],
                sources=sources,
                ranking_profile=self.ranking_combo.currentData(),
                constraints=constraints,
                top_k=int(self.topk_spin.value()),
                quality_profile=self.quality_combo.currentData(),
                language=language,
            )
        )

    def after_result_changed(self, result: LoadedResult | None) -> None:
        self.paper_rows = result.table_rows if result else []
        self.paper_selector.blockSignals(True)
        self.paper_selector.clear()
        if not self.paper_rows:
            self.paper_selector.addItem(ui_text("暂无可用论文条目", "No parsed paper rows", self.language), None)
            self.paper_selector.setEnabled(False)
        else:
            for index, row in enumerate(self.paper_rows, start=1):
                rank = row.get("rank") or row.get("排名") or str(index)
                title = row.get("title") or row.get("论文") or f"Paper {index}"
                self.paper_selector.addItem(f"#{rank} {title}", row)
            self.paper_selector.setEnabled(True)
        self.paper_selector.blockSignals(False)
        self._update_selected_paper()

    def current_paper_row(self) -> dict[str, str] | None:
        data = self.paper_selector.currentData()
        return data if isinstance(data, dict) else None

    def _update_selected_paper(self, *_: Any) -> None:
        row = self.current_paper_row()
        enabled = row is not None
        self.mark_interesting_button.setEnabled(enabled)
        self.open_paper_button.setEnabled(bool(row and row.get("paper_url")))
        self.open_code_button.setEnabled(bool(row and row.get("code_url")))
        if not row:
            self.paper_browser.setMarkdown(ui_text("还没有加载可解析的 Top K 论文条目。", "No parsed Top K paper rows have been loaded yet.", self.language))
            return

        title = row.get("title") or row.get("论文") or "-"
        rank = row.get("rank") or row.get("排名") or "-"
        core = row.get("core_contribution") or row.get("核心贡献") or t("common.not_provided", self.language)
        why_relevant = row.get("why_relevant") or row.get("相关性原因") or t("common.not_provided", self.language)
        why_priority = row.get("why_priority") or row.get("排名原因") or t("common.not_provided", self.language)
        priority = row.get("priority") or row.get("推荐优先级") or t("common.not_provided", self.language)
        paper_url = row.get("paper_url") or ""
        code_url = row.get("code_url") or ""
        project_url = row.get("project_url") or ""
        dataset_url = row.get("dataset_url") or ""
        self.paper_browser.setMarkdown(
            "\n".join(
                [
                    f"### #{rank} {title}",
                    f"- **{ui_text('核心贡献', 'Core Contribution', self.language)}**: {core}",
                    f"- **{t('common.why_relevant', self.language)}**: {why_relevant}",
                    f"- **{t('common.why_priority', self.language)}**: {why_priority}",
                    f"- **{t('common.priority', self.language)}**: {priority}",
                    f"- **{t('common.paper_link', self.language)}**: {paper_url or t('common.not_found', self.language)}",
                    f"- **{t('common.code_link', self.language)}**: {code_url or t('common.not_found', self.language)}",
                    f"- **{ui_text('项目页', 'Project Page', self.language)}**: {project_url or t('common.not_found', self.language)}",
                    f"- **{ui_text('数据集', 'Dataset', self.language)}**: {dataset_url or t('common.not_found', self.language)}",
                ]
            )
        )

    def mark_current_paper_interesting(self) -> None:
        row = self.current_paper_row()
        if not row:
            return
        item = {
            "title": row.get("title") or row.get("论文") or "",
            "paper_url": row.get("paper_url") or "",
            "code_url": row.get("code_url") or "",
            "source_result": str(self.current_output_path) if self.current_output_path else "",
            "rank": row.get("rank") or row.get("排名") or "",
        }
        saved = add_interesting_paper(item)
        if saved:
            QMessageBox.information(self, ui_text("已保存", "Saved", self.language), t("literature_scout.interesting_saved", self.language))
        else:
            QMessageBox.information(self, ui_text("已存在", "Already Exists", self.language), t("literature_scout.already_interesting", self.language))

    def _open_selected_link(self, key: str) -> None:
        row = self.current_paper_row()
        if not row:
            return
        open_external_url(row.get(key))


class PaperReaderPage(BaseTaskPage):
    page_key = "paper_reader"
    recent_dirs = OUTPUTS_DIR / "paper_summaries"
    primary_output_dir = OUTPUTS_DIR / "paper_summaries"

    def run_button_label(self) -> str:
        return t("paper_reader.submit", self.language)

    def task_tips_markdown(self) -> str:
        return f"- {t('paper_reader.quality_help', self.language)}"

    def build_form(self, layout: QVBoxLayout) -> None:
        preferences = load_user_preferences()
        task_defaults = preferences["task_defaults"]["paper_reader"]

        input_section, input_form = create_field_form_section(
            ui_text("论文输入", "Paper Input", self.language),
            ui_text("支持链接、标识符或本地 PDF。", "Supports URLs, identifiers, or a local PDF.", self.language),
        )
        path_row = QWidget()
        path_layout = QHBoxLayout(path_row)
        path_layout.setContentsMargins(0, 0, 0, 0)
        path_layout.setSpacing(10)
        self.reference_input = QLineEdit()
        self.reference_input.setPlaceholderText(t("paper_reader.paper_reference_placeholder", self.language))
        self.browse_pdf_button = set_secondary(QPushButton(ui_text("选择 PDF", "Choose PDF", self.language)))
        self.browse_pdf_button.clicked.connect(self.choose_pdf)
        path_layout.addWidget(self.reference_input, 1)
        path_layout.addWidget(self.browse_pdf_button)
        add_form_row(input_form, t("paper_reader.paper_reference", self.language), path_row)
        layout.addWidget(input_section)

        strategy_section, strategy_form = create_field_form_section(
            ui_text("阅读策略", "Reading Strategy", self.language),
            ui_text("这里统一控制摘要深度、质量档位和精读偏好。", "Use one compact block for summary depth, quality, and reading preferences.", self.language),
        )
        self.summary_depth_combo = styled_combo_box()
        for key in ["standard", "deep", "very_deep"]:
            self.summary_depth_combo.addItem(summary_depth_label(key, self.language), key)
        self.summary_depth_combo.setCurrentIndex(max(0, self.summary_depth_combo.findData(task_defaults.get("summary_depth", "standard"))))
        add_form_row(strategy_form, t("paper_reader.summary_depth", self.language), self.summary_depth_combo)

        self.quality_combo = styled_combo_box()
        for item in QUALITY_PROFILE_OPTIONS:
            self.quality_combo.addItem(item, item)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(task_defaults.get("quality_profile", "balanced"))))
        add_form_row(strategy_form, t("common.quality_profile", self.language), self.quality_combo)

        self.diagram_checkbox = QCheckBox(t("paper_reader.diagram_summary", self.language))
        self.diagram_checkbox.setChecked(bool(task_defaults.get("diagram_summary", True)))
        strategy_form.addRow(self.diagram_checkbox)

        self.experiment_checkbox = QCheckBox(t("paper_reader.focus_experiments", self.language))
        self.experiment_checkbox.setChecked(bool(task_defaults.get("focus_experiments", True)))
        strategy_form.addRow(self.experiment_checkbox)

        self.auto_fetch_checkbox = QCheckBox(t("paper_reader.auto_fetch_pdf", self.language))
        self.auto_fetch_checkbox.setChecked(bool(task_defaults.get("auto_fetch_pdf", True)))
        strategy_form.addRow(self.auto_fetch_checkbox)
        layout.addWidget(strategy_section)

        self.register_focus_widgets(
            self.reference_input,
            self.browse_pdf_button,
            self.summary_depth_combo,
            self.quality_combo,
            self.diagram_checkbox,
            self.experiment_checkbox,
            self.auto_fetch_checkbox,
        )

    def choose_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, ui_text("选择 PDF", "Choose PDF", self.language), str(Path.home()), "PDF Files (*.pdf)")
        if path:
            self.reference_input.setText(path)

    def execute_task(self) -> BridgeResponse:
        preferences = load_user_preferences()
        reference = self.reference_input.text().strip()
        if not reference:
            raise ValueError(ui_text("请先填写论文引用或选择本地 PDF。", "Please enter a paper reference or choose a local PDF.", self.language))
        update_user_preferences(
            {
                "task_defaults": {
                    "paper_reader": {
                        "quality_profile": self.quality_combo.currentData(),
                        "summary_depth": self.summary_depth_combo.currentData(),
                        "diagram_summary": self.diagram_checkbox.isChecked(),
                        "focus_experiments": self.experiment_checkbox.isChecked(),
                        "auto_fetch_pdf": self.auto_fetch_checkbox.isChecked(),
                    }
                }
            }
        )
        return run_paper_reader(
            PaperReaderInput(
                paper_reference=reference,
                summary_depth=self.summary_depth_combo.currentData(),
                diagram_summary=self.diagram_checkbox.isChecked(),
                focus_experiments=self.experiment_checkbox.isChecked(),
                auto_fetch_pdf=self.auto_fetch_checkbox.isChecked(),
                quality_profile=self.quality_combo.currentData(),
                language=preferences["language"],
            )
        )


class TopicMapperPage(BaseTaskPage):
    page_key = "topic_mapper"
    recent_dirs = OUTPUTS_DIR / "topic_maps"
    primary_output_dir = OUTPUTS_DIR / "topic_maps"

    def run_button_label(self) -> str:
        return t("topic_mapper.submit", self.language)

    def build_form(self, layout: QVBoxLayout) -> None:
        preferences = load_user_preferences()
        task_defaults = preferences["task_defaults"]["topic_mapper"]

        topic_section, topic_form = create_field_form_section(
            ui_text("主题输入", "Topic Input", self.language),
            ui_text("先描述你要建立地图的方向或问题。", "Describe the direction or problem you want to map first.", self.language),
        )
        self.topic_edit = QTextEdit()
        self.topic_edit.setMinimumHeight(130)
        self.topic_edit.setPlaceholderText(t("topic_mapper.topic_placeholder", self.language))
        add_form_row(topic_form, t("topic_mapper.topic", self.language), self.topic_edit)

        self.time_combo = styled_combo_box()
        for key, value in TIME_RANGE_OPTIONS.items():
            self.time_combo.addItem(time_range_label(value, self.language), key)
        self.time_combo.setCurrentIndex(max(0, self.time_combo.findData(task_defaults.get("time_range_key", "30d"))))
        add_form_row(topic_form, t("common.time_range", self.language), self.time_combo)
        layout.addWidget(topic_section)

        strategy_section, strategy_form = create_field_form_section(
            ui_text("映射策略", "Mapping Strategy", self.language),
            ui_text("统一设置质量档位、返回规模和排序偏好。", "Keep quality, output size, and ranking preference in one strategy block.", self.language),
        )
        self.quality_combo = styled_combo_box()
        for item in QUALITY_PROFILE_OPTIONS:
            self.quality_combo.addItem(item, item)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(task_defaults.get("quality_profile", "balanced"))))
        add_form_row(strategy_form, t("common.quality_profile", self.language), self.quality_combo)

        self.cross_domain_checkbox = QCheckBox(t("topic_mapper.cross_domain", self.language))
        self.cross_domain_checkbox.setChecked(bool(task_defaults.get("cross_domain", False)))
        strategy_form.addRow(self.cross_domain_checkbox)

        self.return_count_spin = QSpinBox()
        self.return_count_spin.setRange(5, 60)
        self.return_count_spin.setValue(int(task_defaults.get("return_count", 15)))
        add_form_row(strategy_form, t("topic_mapper.return_count", self.language), self.return_count_spin)

        self.ranking_combo = styled_combo_box()
        for item in RANKING_PROFILES:
            self.ranking_combo.addItem(item, item)
        self.ranking_combo.setCurrentIndex(max(0, self.ranking_combo.findData(task_defaults.get("ranking_mode", "balanced-default"))))
        add_form_row(strategy_form, t("topic_mapper.ranking_mode", self.language), self.ranking_combo)
        layout.addWidget(strategy_section)

        self.register_focus_widgets(
            self.topic_edit,
            self.time_combo,
            self.quality_combo,
            self.cross_domain_checkbox,
            self.return_count_spin,
            self.ranking_combo,
        )

    def execute_task(self) -> BridgeResponse:
        preferences = load_user_preferences()
        topic = self.topic_edit.toPlainText().strip()
        if not topic:
            raise ValueError(ui_text("请先填写主题。", "Please enter a topic first.", self.language))
        update_user_preferences(
            {
                "task_defaults": {
                    "topic_mapper": {
                        "quality_profile": self.quality_combo.currentData(),
                        "time_range_key": self.time_combo.currentData(),
                        "cross_domain": self.cross_domain_checkbox.isChecked(),
                        "return_count": int(self.return_count_spin.value()),
                        "ranking_mode": self.ranking_combo.currentData(),
                    }
                }
            }
        )
        return run_topic_mapper(
            TopicMapperInput(
                topic=topic,
                time_range=TIME_RANGE_OPTIONS[self.time_combo.currentData()],
                cross_domain=self.cross_domain_checkbox.isChecked(),
                return_count=int(self.return_count_spin.value()),
                ranking_mode=self.ranking_combo.currentData(),
                quality_profile=self.quality_combo.currentData(),
                language=preferences["language"],
            )
        )


class IdeaFeasibilityPage(BaseTaskPage):
    page_key = "idea_feasibility"
    recent_dirs = OUTPUTS_DIR / "feasibility_reports"
    primary_output_dir = OUTPUTS_DIR / "feasibility_reports"

    def run_button_label(self) -> str:
        return t("idea_feasibility.submit", self.language)

    def build_form(self, layout: QVBoxLayout) -> None:
        preferences = load_user_preferences()
        task_defaults = preferences["task_defaults"]["idea_feasibility"]

        idea_section, idea_form = create_field_form_section(
            ui_text("想法与目标", "Idea And Target", self.language),
            ui_text("先写清楚研究想法，再说明它要落在哪个领域。", "State the research idea first, then the target field it should land in.", self.language),
        )
        self.idea_edit = QTextEdit()
        self.idea_edit.setMinimumHeight(150)
        add_form_row(idea_form, t("idea_feasibility.idea", self.language), self.idea_edit)

        self.target_field_input = QLineEdit()
        self.target_field_input.setPlaceholderText(t("idea_feasibility.target_field_placeholder", self.language))
        add_form_row(idea_form, t("idea_feasibility.target_field", self.language), self.target_field_input)
        layout.addWidget(idea_section)

        resource_section, resource_form = create_field_form_section(
            ui_text("资源与风险", "Resources And Risk", self.language),
            ui_text("把执行质量、算力、数据与风险偏好放在同一层判断。", "Keep quality, compute, data, and risk preference within one decision block.", self.language),
        )
        self.quality_combo = styled_combo_box()
        for item in QUALITY_PROFILE_OPTIONS:
            self.quality_combo.addItem(item, item)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(task_defaults.get("quality_profile", "balanced"))))
        add_form_row(resource_form, t("common.quality_profile", self.language), self.quality_combo)

        self.compute_input = QLineEdit(task_defaults.get("compute_budget", "单卡 24G"))
        add_form_row(resource_form, t("idea_feasibility.compute_budget", self.language), self.compute_input)

        self.data_input = QLineEdit(task_defaults.get("data_budget", "优先公开数据"))
        add_form_row(resource_form, t("idea_feasibility.data_budget", self.language), self.data_input)

        self.risk_combo = styled_combo_box()
        for key in ["conservative", "balanced", "aggressive"]:
            self.risk_combo.addItem(risk_preference_label(key, self.language), key)
        self.risk_combo.setCurrentIndex(max(0, self.risk_combo.findData(task_defaults.get("risk_preference", "balanced"))))
        add_form_row(resource_form, t("idea_feasibility.risk_preference", self.language), self.risk_combo)

        self.low_cost_checkbox = QCheckBox(t("idea_feasibility.prefer_low_cost_validation", self.language))
        self.low_cost_checkbox.setChecked(bool(task_defaults.get("prefer_low_cost_validation", True)))
        resource_form.addRow(self.low_cost_checkbox)
        layout.addWidget(resource_section)

        self.register_focus_widgets(
            self.idea_edit,
            self.target_field_input,
            self.quality_combo,
            self.compute_input,
            self.data_input,
            self.risk_combo,
            self.low_cost_checkbox,
        )

    def execute_task(self) -> BridgeResponse:
        preferences = load_user_preferences()
        idea = self.idea_edit.toPlainText().strip()
        target_field = self.target_field_input.text().strip()
        if not idea:
            raise ValueError(ui_text("请先填写研究想法。", "Please enter a research idea first.", self.language))
        if not target_field:
            raise ValueError(ui_text("请先填写目标领域。", "Please enter a target field first.", self.language))
        update_user_preferences(
            {
                "task_defaults": {
                    "idea_feasibility": {
                        "quality_profile": self.quality_combo.currentData(),
                        "compute_budget": self.compute_input.text().strip(),
                        "data_budget": self.data_input.text().strip(),
                        "risk_preference": self.risk_combo.currentData(),
                        "prefer_low_cost_validation": self.low_cost_checkbox.isChecked(),
                    }
                }
            }
        )
        return run_idea_feasibility(
            IdeaFeasibilityInput(
                idea=idea,
                target_field=target_field,
                compute_budget=self.compute_input.text().strip(),
                data_budget=self.data_input.text().strip(),
                risk_preference=self.risk_combo.currentData(),
                prefer_low_cost_validation=self.low_cost_checkbox.isChecked(),
                quality_profile=self.quality_combo.currentData(),
                language=preferences["language"],
            )
        )


class ConstraintExplorerPage(BaseTaskPage):
    page_key = "constraint_explorer"
    recent_dirs = OUTPUTS_DIR / "constraint_reports"
    primary_output_dir = OUTPUTS_DIR / "constraint_reports"

    def run_button_label(self) -> str:
        return t("constraint_explorer.submit", self.language)

    def build_form(self, layout: QVBoxLayout) -> None:
        preferences = load_user_preferences()
        task_defaults = preferences["task_defaults"]["constraint_explorer"]

        field_section, field_form = create_field_form_section(
            ui_text("研究边界", "Research Boundary", self.language),
            ui_text("先定义方向，再把核心资源限制压进去。", "Define the direction first, then state the practical limits.", self.language),
        )
        self.field_input = QLineEdit()
        self.field_input.setPlaceholderText(t("constraint_explorer.field_placeholder", self.language))
        add_form_row(field_form, t("common.field", self.language), self.field_input)

        self.compute_input = QLineEdit(task_defaults.get("compute_limit", "单卡 24G"))
        add_form_row(field_form, t("constraint_explorer.compute_limit", self.language), self.compute_input)

        self.data_input = QLineEdit(task_defaults.get("data_limit", "优先公开数据或可替代小规模数据"))
        add_form_row(field_form, t("constraint_explorer.data_limit", self.language), self.data_input)
        layout.addWidget(field_section)

        preference_section, preference_form = create_field_form_section(
            ui_text("执行偏好", "Execution Preference", self.language),
            ui_text("这里统一控制质量档位、复现优先级和开源偏好。", "Use this block for quality level, reproduction priority, and open-source preference.", self.language),
        )
        self.quality_combo = styled_combo_box()
        for item in QUALITY_PROFILE_OPTIONS:
            self.quality_combo.addItem(item, item)
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(task_defaults.get("quality_profile", "balanced"))))
        add_form_row(preference_form, t("common.quality_profile", self.language), self.quality_combo)

        self.repro_checkbox = QCheckBox(t("constraint_explorer.prefer_reproduction", self.language))
        self.repro_checkbox.setChecked(bool(task_defaults.get("prefer_reproduction", True)))
        preference_form.addRow(self.repro_checkbox)

        self.opensource_checkbox = QCheckBox(t("constraint_explorer.prefer_open_source", self.language))
        self.opensource_checkbox.setChecked(bool(task_defaults.get("prefer_open_source", True)))
        preference_form.addRow(self.opensource_checkbox)
        layout.addWidget(preference_section)

        self.register_focus_widgets(
            self.field_input,
            self.compute_input,
            self.data_input,
            self.quality_combo,
            self.repro_checkbox,
            self.opensource_checkbox,
        )

    def execute_task(self) -> BridgeResponse:
        preferences = load_user_preferences()
        field = self.field_input.text().strip()
        if not field:
            raise ValueError(ui_text("请先填写研究方向。", "Please enter a research area first.", self.language))
        update_user_preferences(
            {
                "task_defaults": {
                    "constraint_explorer": {
                        "quality_profile": self.quality_combo.currentData(),
                        "compute_limit": self.compute_input.text().strip(),
                        "data_limit": self.data_input.text().strip(),
                        "prefer_reproduction": self.repro_checkbox.isChecked(),
                        "prefer_open_source": self.opensource_checkbox.isChecked(),
                    }
                }
            }
        )
        return run_constraint_explorer(
            ConstraintExplorerInput(
                field=field,
                compute_limit=self.compute_input.text().strip(),
                data_limit=self.data_input.text().strip(),
                prefer_reproduction=self.repro_checkbox.isChecked(),
                prefer_open_source=self.opensource_checkbox.isChecked(),
                quality_profile=self.quality_combo.currentData(),
                language=preferences["language"],
            )
        )


class PDFDownloaderPage(BaseTaskPage):
    page_key = "pdf_fetcher"
    recent_dirs = OUTPUTS_DIR / "paper_summaries"
    primary_output_dir = OUTPUTS_DIR / "pdfs"

    def run_button_label(self) -> str:
        return t("pdf_fetcher.submit", self.language)

    def build_form(self, layout: QVBoxLayout) -> None:
        preferences = load_user_preferences()
        task_defaults = preferences["task_defaults"]["pdf_fetcher"]

        input_section, input_form = create_field_form_section(
            ui_text("下载输入", "Download Input", self.language),
            ui_text("把待下载的引用和输出目录集中在一起。", "Keep references and the output directory together in one input block.", self.language),
        )
        self.references_edit = QTextEdit()
        self.references_edit.setMinimumHeight(160)
        self.references_edit.setPlaceholderText(t("pdf_fetcher.references_placeholder", self.language))
        add_form_row(input_form, t("pdf_fetcher.references", self.language), self.references_edit)

        output_row = QWidget()
        output_layout = QHBoxLayout(output_row)
        output_layout.setContentsMargins(0, 0, 0, 0)
        output_layout.setSpacing(10)
        self.output_dir_input = QLineEdit(task_defaults.get("save_dir") or str(OUTPUTS_DIR / "pdfs"))
        self.choose_dir_button = set_secondary(QPushButton(ui_text("选择目录", "Choose Folder", self.language)))
        self.choose_dir_button.clicked.connect(self.choose_output_dir)
        output_layout.addWidget(self.output_dir_input, 1)
        output_layout.addWidget(self.choose_dir_button)
        add_form_row(input_form, t("pdf_fetcher.save_dir", self.language), output_row)
        layout.addWidget(input_section)

        post_section, post_form = create_field_form_section(
            ui_text("后处理", "Post Processing", self.language),
            ui_text("决定是否自动串到论文精读，以及精读时使用的质量档位。", "Decide whether to chain directly into deep reading and which quality profile to use.", self.language),
        )
        self.auto_read_checkbox = QCheckBox(t("pdf_fetcher.auto_read", self.language))
        self.auto_read_checkbox.setChecked(bool(task_defaults.get("auto_read", False)))
        post_form.addRow(self.auto_read_checkbox)

        self.reader_quality_combo = styled_combo_box()
        for item in QUALITY_PROFILE_OPTIONS:
            self.reader_quality_combo.addItem(item, item)
        self.reader_quality_combo.setCurrentIndex(max(0, self.reader_quality_combo.findData(task_defaults.get("reader_quality_profile", "balanced"))))
        add_form_row(post_form, t("pdf_fetcher.reader_quality_profile", self.language), self.reader_quality_combo)
        layout.addWidget(post_section)

        self.register_focus_widgets(
            self.references_edit,
            self.output_dir_input,
            self.choose_dir_button,
            self.auto_read_checkbox,
            self.reader_quality_combo,
        )

    def choose_output_dir(self) -> None:
        path = QFileDialog.getExistingDirectory(
            self,
            ui_text("选择输出目录", "Choose Output Directory", self.language),
            self.output_dir_input.text().strip() or str(OUTPUTS_DIR / "pdfs"),
        )
        if path:
            self.output_dir_input.setText(path)

    def output_directory(self) -> Path:
        return Path(self.output_dir_input.text().strip() or str(OUTPUTS_DIR / "pdfs"))

    def execute_task(self) -> dict[str, Any]:
        preferences = load_user_preferences()
        references = [line.strip() for line in self.references_edit.toPlainText().splitlines() if line.strip()]
        if not references:
            raise ValueError(t("pdf_fetcher.no_reference", self.language))
        output_dir = self.output_dir_input.text().strip() or str(OUTPUTS_DIR / "pdfs")
        update_user_preferences(
            {
                "task_defaults": {
                    "pdf_fetcher": {
                        "save_dir": output_dir,
                        "auto_read": self.auto_read_checkbox.isChecked(),
                        "reader_quality_profile": self.reader_quality_combo.currentData(),
                    }
                }
            }
        )

        logs: list[dict[str, Any]] = []
        latest_reader: BridgeResponse | None = None
        for reference in references:
            if self.auto_read_checkbox.isChecked():
                chain = download_and_run_reader(
                    reference,
                    quality_profile="economy",
                    reader_quality_profile=self.reader_quality_combo.currentData(),
                    output_dir=output_dir,
                    language=preferences["language"],
                )
                download_response = chain["download"]
                reader_response = chain["reader"]
                logs.append(
                    {
                        "reference": reference,
                        "download": download_response.to_dict(),
                        "reader": reader_response.to_dict() if reader_response else None,
                    }
                )
                if reader_response:
                    latest_reader = reader_response
            else:
                response = run_paper_fetch(
                    PaperFetcherInput(
                        reference=reference,
                        output_dir=output_dir,
                        filename=None,
                        force=False,
                        resolve_only=False,
                        quality_profile="economy",
                        language=preferences["language"],
                    )
                )
                logs.append({"reference": reference, "download": response.to_dict()})

        return {
            "references": references,
            "logs": logs,
            "latest_reader": latest_reader,
            "output_dir": output_dir,
        }

    def handle_task_success(self, payload: Any) -> None:
        if not isinstance(payload, dict):
            super().handle_task_success(payload)
            return
        references = payload.get("references") or []
        latest_reader = payload.get("latest_reader")
        lines = [ui_text(f"本次共处理 {len(references)} 条引用。", f"Processed {len(references)} references.", self.language), ""]
        for item in payload.get("logs", []):
            download = item.get("download") or {}
            lines.append(f"- {item.get('reference')}: {download.get('status')} | {download.get('message')}")
            reader = item.get("reader")
            if reader:
                lines.append(f"  {ui_text('精读', 'Reader', self.language)}: {reader.get('status')} | {reader.get('message')}")
        self.status_box.setPlainText("\n".join(lines).strip())

        if isinstance(latest_reader, BridgeResponse):
            self.current_output_path = Path(latest_reader.expected_output_path) if latest_reader.expected_output_path else None
            self.result_panel.show_bridge_response(latest_reader)
            self.current_loaded_result = load_result(self.current_output_path) if self.current_output_path and self.current_output_path.exists() else None
        else:
            self.current_output_path = None
            self.current_loaded_result = None
            self.result_panel.show_message("\n".join(lines).strip(), payload=payload)

        self.refresh_recent_results()


class AutomationPage(ScrollPage):
    def __init__(self, language: str) -> None:
        self.language = normalize_language(language)
        self._worker: WorkerThread | None = None
        self._focus_order: list[QWidget] = []
        self._shortcuts: list[QShortcut] = []
        self.result_panel = ResultPanel(self.language)
        self.status_box = readonly_plaintext(180)
        self.preview_browser = markdown_browser(180)
        self.prompt_browser = readonly_plaintext(220)
        super().__init__()
        self._build_ui()
        self.load_from_config()
        self.refresh_status()

    def _build_ui(self) -> None:
        copy = page_copy("automation_config", self.language)
        self.add_page_header(copy["title"], copy["caption"])
        left_layout, right_layout = self.add_two_column_section(6, 9)

        form_card, form_layout_wrapper = create_card(
            ui_text("自动化字段", "Automation Fields", self.language),
        )
        form_layout_wrapper.setSpacing(14)

        identity_section, identity_form = create_field_form_section(
            ui_text("任务身份", "Task Identity", self.language),
            ui_text("先确定任务名、研究方向和输出语言。", "Start with the task name, research field, and output language.", self.language),
        )
        self.task_name_input = QLineEdit()
        add_form_row(identity_form, t("automation_config.task_name", self.language), self.task_name_input)

        self.field_input = QLineEdit()
        add_form_row(identity_form, t("common.field", self.language), self.field_input)

        self.output_language_combo = styled_combo_box()
        self.output_language_combo.addItem(language_option_label("zh-CN", self.language), "zh-CN")
        self.output_language_combo.addItem(language_option_label("en-US", self.language), "en-US")
        add_form_row(identity_form, t("automation_config.language", self.language), self.output_language_combo)
        form_layout_wrapper.addWidget(identity_section)

        scope_section, scope_form = create_field_form_section(
            ui_text("研究范围", "Research Scope", self.language),
            ui_text("统一设置时间窗、来源范围、排序方式和输出规模。", "Keep time range, sources, ranking mode, and output volume in one scope block.", self.language),
        )
        self.time_combo = styled_combo_box()
        for key, value in TIME_RANGE_OPTIONS.items():
            self.time_combo.addItem(time_range_label(value, self.language), key)
        add_form_row(scope_form, t("common.time_range", self.language), self.time_combo)

        self.sources_list = MultiSelectList(SOURCE_OPTIONS)
        add_form_row(scope_form, t("common.sources", self.language), self.sources_list)

        self.ranking_combo = styled_combo_box()
        for item in RANKING_PROFILES:
            self.ranking_combo.addItem(item, item)
        add_form_row(scope_form, t("common.ranking_profile", self.language), self.ranking_combo)

        self.quality_combo = styled_combo_box()
        for item in QUALITY_PROFILE_OPTIONS:
            self.quality_combo.addItem(item, item)
        add_form_row(scope_form, t("common.quality_profile", self.language), self.quality_combo)

        self.topk_spin = QSpinBox()
        self.topk_spin.setRange(1, 50)
        add_form_row(scope_form, t("common.top_k", self.language), self.topk_spin)
        form_layout_wrapper.addWidget(scope_section)

        delivery_section, delivery_form = create_field_form_section(
            ui_text("调度与交付", "Schedule And Delivery", self.language),
            ui_text("在这里定义每日运行时间、额外约束和自动化行为。", "Define run time, extra constraints, and automation behavior here.", self.language),
        )
        self.run_time_input = QLineEdit()
        self.run_time_input.setPlaceholderText("09:00")
        add_form_row(delivery_form, t("automation_config.run_time", self.language), self.run_time_input)

        self.constraints_edit = QTextEdit()
        self.constraints_edit.setMinimumHeight(130)
        add_form_row(delivery_form, t("common.constraints", self.language), self.constraints_edit)

        self.auto_download_checkbox = QCheckBox(t("automation_config.auto_download_interesting", self.language))
        delivery_form.addRow(self.auto_download_checkbox)

        self.exclude_history_checkbox = QCheckBox(ui_text("自动排除历史输出中的论文", "Exclude Previously Output Papers", self.language))
        delivery_form.addRow(self.exclude_history_checkbox)

        self.enabled_checkbox = QCheckBox(t("automation_config.enabled", self.language))
        delivery_form.addRow(self.enabled_checkbox)
        form_layout_wrapper.addWidget(delivery_section)

        actions = QHBoxLayout()
        actions.setContentsMargins(0, 2, 0, 0)
        actions.setSpacing(12)
        keyboard_hint = QLabel(
            ui_text(
                "⌘/Ctrl + S 保存 · ⌘/Ctrl + Enter 立即执行 · ⌘/Ctrl + L 聚焦首个字段",
                "Cmd/Ctrl+S save · Cmd/Ctrl+Enter run now · Cmd/Ctrl+L focus first field",
                self.language,
            )
        )
        keyboard_hint.setObjectName("KeyboardHint")
        self.save_button = QPushButton(t("automation_config.submit", self.language))
        self.save_button.clicked.connect(self.save_config)
        self.run_now_button = set_secondary(QPushButton(ui_text("立即执行", "Run Now", self.language)))
        self.run_now_button.clicked.connect(self.run_now)
        actions.addWidget(keyboard_hint, 1)
        actions.addWidget(self.save_button)
        actions.addWidget(self.run_now_button)
        form_layout_wrapper.addLayout(actions)
        left_layout.addWidget(form_card)

        scheduler_card, scheduler_layout = create_card(
            ui_text("调度器控制", "Scheduler Control", self.language),
            ui_text("启动、停止或刷新本地自动调度。", "Start, stop, or refresh the local scheduler.", self.language),
        )
        buttons = QHBoxLayout()
        self.refresh_button = set_secondary(QPushButton(ui_text("刷新状态", "Refresh Status", self.language)))
        self.refresh_button.clicked.connect(self.refresh_status)
        self.start_button = QPushButton(ui_text("启动调度器", "Start Scheduler", self.language))
        self.start_button.clicked.connect(self.start_scheduler)
        self.stop_button = set_secondary(QPushButton(ui_text("停止调度器", "Stop Scheduler", self.language)))
        self.stop_button.clicked.connect(self.stop_scheduler)
        buttons.addWidget(self.refresh_button)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.stop_button)
        buttons.addStretch(1)
        scheduler_layout.addLayout(buttons)
        left_layout.addWidget(scheduler_card)

        status_card, status_layout = create_card(
            ui_text("自动化状态", "Automation Status", self.language),
        )
        status_layout.addWidget(self.status_box)
        right_layout.addWidget(status_card)

        preview_card, preview_layout = create_card(
            ui_text("配置预览", "Config Preview", self.language),
            ui_text("保存前先确认任务名、文件名和执行时间。", "Confirm the task name, filename, and run time before saving.", self.language),
        )
        preview_layout.addWidget(self.preview_browser)
        right_layout.addWidget(preview_card)

        prompt_card, prompt_layout = create_card(
            ui_text("Automation Prompt", "Automation Prompt", self.language),
            ui_text("这里显示当前自动化会实际执行的 prompt。", "This shows the prompt the automation will actually run.", self.language),
        )
        prompt_layout.addWidget(self.prompt_browser)
        right_layout.addWidget(prompt_card)

        result_card, result_layout = create_card(
            ui_text("执行结果", "Execution Result", self.language),
        )
        result_layout.addWidget(self.result_panel, 1)
        right_layout.addWidget(result_card, 1)

        self.register_focus_widgets(
            self.task_name_input,
            self.field_input,
            self.output_language_combo,
            self.time_combo,
            self.sources_list,
            self.ranking_combo,
            self.quality_combo,
            self.topk_spin,
            self.run_time_input,
            self.constraints_edit,
            self.auto_download_checkbox,
            self.exclude_history_checkbox,
            self.enabled_checkbox,
        )
        for widget in [
            self.task_name_input,
            self.field_input,
            self.run_time_input,
            self.constraints_edit,
            self.time_combo,
            self.ranking_combo,
            self.quality_combo,
            self.output_language_combo,
            self.topk_spin,
            self.auto_download_checkbox,
            self.exclude_history_checkbox,
            self.enabled_checkbox,
        ]:
            if isinstance(widget, QLineEdit):
                widget.textChanged.connect(self.refresh_preview)
            elif isinstance(widget, QTextEdit):
                widget.textChanged.connect(self.refresh_preview)
            elif isinstance(widget, QComboBox):
                widget.currentIndexChanged.connect(self.refresh_preview)
            elif isinstance(widget, QSpinBox):
                widget.valueChanged.connect(self.refresh_preview)
            elif isinstance(widget, QCheckBox):
                widget.stateChanged.connect(self.refresh_preview)
        self.sources_list.itemSelectionChanged.connect(self.refresh_preview)

        self._apply_tab_order()
        self._install_keyboard_flow()

    def register_focus_widgets(self, *widgets: QWidget) -> None:
        for widget in widgets:
            if widget is None or widget in self._focus_order:
                continue
            self._focus_order.append(widget)

    def focus_primary_field(self) -> None:
        if not self._focus_order:
            return
        widget = self._focus_order[0]
        widget.setFocus(Qt.FocusReason.ShortcutFocusReason)
        if isinstance(widget, QLineEdit):
            widget.selectAll()

    def _apply_tab_order(self) -> None:
        ordered = [widget for widget in self._focus_order if widget is not None]
        for first, second in zip(ordered, ordered[1:]):
            QWidget.setTabOrder(first, second)

    def _add_shortcut(self, sequence: str, callback: Callable[[], None]) -> None:
        shortcut = QShortcut(QKeySequence(sequence), self)
        shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        shortcut.activated.connect(callback)
        self._shortcuts.append(shortcut)

    def _install_keyboard_flow(self) -> None:
        for sequence in ("Meta+S", "Ctrl+S"):
            self._add_shortcut(sequence, self.save_config)
        for sequence in ("Meta+Return", "Ctrl+Return"):
            self._add_shortcut(sequence, self.run_now)
        for sequence in ("Meta+L", "Ctrl+L"):
            self._add_shortcut(sequence, self.focus_primary_field)
        for sequence in ("Meta+Shift+R", "Ctrl+Shift+R"):
            self._add_shortcut(sequence, self.refresh_status)

    def load_from_config(self) -> None:
        config = load_automation_config()
        self.task_name_input.setText(config["task_name"])
        self.field_input.setText(config["field"])
        self.time_combo.setCurrentIndex(max(0, self.time_combo.findData(time_range_key(config["time_range"]))))
        self.sources_list.set_selected_values(config["sources"])
        self.ranking_combo.setCurrentIndex(max(0, self.ranking_combo.findData(config["ranking_profile"])))
        self.quality_combo.setCurrentIndex(max(0, self.quality_combo.findData(config["quality_profile"])))
        self.output_language_combo.setCurrentIndex(max(0, self.output_language_combo.findData(config["language"])))
        self.topk_spin.setValue(int(config["top_k"]))
        self.run_time_input.setText(config["schedule"]["time_of_day"])
        self.constraints_edit.setPlainText((config.get("constraints") or {}).get("notes", ""))
        self.auto_download_checkbox.setChecked(bool(config.get("auto_download_interesting", False)))
        self.exclude_history_checkbox.setChecked(bool(config.get("exclude_previous_output_papers", True)))
        self.enabled_checkbox.setChecked(bool(config.get("enabled", True)))
        self.refresh_preview()

    def build_automation_payload(self) -> dict[str, Any]:
        task_name = self.task_name_input.text().strip()
        field = self.field_input.text().strip()
        if not task_name:
            raise ValueError(ui_text("请先填写自动化任务名称。", "Please enter an automation task name first.", self.language))
        if not field:
            raise ValueError(ui_text("请先填写研究方向。", "Please enter a research area first.", self.language))
        return {
            "task_name": task_name,
            "field": field,
            "time_range": TIME_RANGE_OPTIONS[self.time_combo.currentData()],
            "sources": self.sources_list.selected_values() or ["arXiv", "OpenReview"],
            "ranking_profile": self.ranking_combo.currentData(),
            "quality_profile": self.quality_combo.currentData(),
            "constraints": {
                "compute": "",
                "data": "",
                "time": "",
                "budget": "",
                "notes": self.constraints_edit.toPlainText().strip(),
            },
            "top_k": int(self.topk_spin.value()),
            "schedule": {
                "timezone": "Asia/Hong_Kong",
                "time_of_day": self.run_time_input.text().strip() or "09:00",
                "cadence": "daily",
            },
            "enabled": self.enabled_checkbox.isChecked(),
            "auto_download_interesting": self.auto_download_checkbox.isChecked(),
            "exclude_previous_output_papers": self.exclude_history_checkbox.isChecked(),
            "runner": "local-scheduler",
            "history_scope": "same-field",
            "generated_prompt_target": "Native Desktop + Local Scheduler",
            "language": self.output_language_combo.currentData(),
        }

    def refresh_preview(self, *_: Any) -> None:
        try:
            payload = self.build_automation_payload()
        except ValueError:
            self.preview_browser.setMarkdown(ui_text("请先补全任务名和研究方向，预览才会显示。", "Fill in the task name and research field to render the preview.", self.language))
            self.prompt_browser.setPlainText("")
            return

        storage = describe_automation_storage(payload["task_name"])
        self.preview_browser.setMarkdown(
            "\n".join(
                [
                    f"- **{t('automation_config.preview_task_name', self.language)}**: `{payload['task_name']}`",
                    f"- **{t('automation_config.preview_filename', self.language)}**: `{storage['filename']}`",
                    f"- **{t('automation_config.preview_directory', self.language)}**: `{storage['directory']}`",
                    f"- **{t('automation_config.language', self.language)}**: `{language_option_label(payload['language'], self.language)}`",
                    f"- **{t('common.top_k', self.language)}**: `{payload['top_k']}`",
                    f"- **{t('automation_config.run_time', self.language)}**: `{payload['schedule']['time_of_day']}`",
                ]
            )
        )
        self.prompt_browser.setPlainText(build_daily_automation_prompt(payload))

    def save_config(self) -> None:
        try:
            payload = self.build_automation_payload()
        except ValueError as exc:
            QMessageBox.warning(self, ui_text("参数不完整", "Missing Parameters", self.language), str(exc))
            return
        path = save_automation_config(payload)
        storage = describe_automation_storage(payload["task_name"], path)
        self.status_box.setPlainText(f"{ui_text('已保存自动化配置', 'Automation config saved', self.language)}.\n{ui_text('路径', 'Path', self.language)}: {storage['path']}")
        self.refresh_status()

    def run_now(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        try:
            payload = self.build_automation_payload()
        except ValueError as exc:
            QMessageBox.warning(self, ui_text("参数不完整", "Missing Parameters", self.language), str(exc))
            return
        path = save_automation_config(payload)
        storage = describe_automation_storage(payload["task_name"], path)
        self.run_now_button.setEnabled(False)
        self.status_box.setPlainText(f"{ui_text('正在执行自动化任务', 'Running automation task', self.language)}...\n{ui_text('配置路径', 'Config Path', self.language)}: {storage['path']}")
        self._worker = WorkerThread(lambda: run_local_automation(current_automation_config_path(), force=True))
        self._worker.result_ready.connect(self._on_run_now_success)
        self._worker.error_ready.connect(self._on_run_now_error)
        self._worker.finished.connect(lambda: self.run_now_button.setEnabled(True))
        self._worker.start()

    def _on_run_now_success(self, payload: dict[str, Any]) -> None:
        self.status_box.setPlainText(json_text(payload))
        self.result_panel.show_message(ui_text("自动化执行结果", "Automation Run Result", self.language), payload=payload, metadata=payload)
        self.refresh_status()

    def _on_run_now_error(self, trace: str) -> None:
        self.status_box.setPlainText(ui_text("自动化执行失败。", "Automation execution failed.", self.language) + "\n\n" + trace)
        self.result_panel.show_message(ui_text("自动化执行失败。", "Automation execution failed.", self.language), payload={"traceback": trace})

    def refresh_status(self) -> None:
        daemon = daemon_snapshot()
        schedule = automation_schedule_snapshot(current_automation_config_path())
        config = load_automation_config()
        storage = describe_automation_storage(config["task_name"], current_automation_config_path())
        lines = [
            f"{ui_text('当前配置', 'Active Config', self.language)}: {storage['path']}",
            f"{ui_text('调度器运行中', 'Daemon Running', self.language)}: {daemon['is_running']}",
            f"{ui_text('调度器 PID', 'Daemon PID', self.language)}: {daemon.get('pid') or '-'}",
            f"{ui_text('计划执行时间', 'Scheduled Time', self.language)}: {schedule.get('scheduled_time') or '-'}",
            f"{ui_text('下次运行', 'Next Run', self.language)}: {schedule.get('next_run_at') or '-'}",
            f"{ui_text('最近一次尝试', 'Last Attempt', self.language)}: {schedule.get('last_attempt_at') or '-'}",
            f"{ui_text('最近状态', 'Last Status', self.language)}: {schedule.get('last_status') or '-'}",
            f"{ui_text('最近输出', 'Last Output', self.language)}: {schedule.get('last_output') or '-'}",
        ]
        self.status_box.setPlainText("\n".join(lines))
        self.refresh_preview()

    def start_scheduler(self) -> None:
        snapshot = daemon_snapshot()
        if snapshot["is_running"]:
            self.status_box.setPlainText(ui_text("本地调度器已经在运行。", "The local scheduler is already running.", self.language))
            return
        process = subprocess.Popen(
            scheduler_command(),
            cwd=runtime_project_root(),
            env=os.environ.copy(),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )
        self.status_box.setPlainText(f"{ui_text('已尝试启动调度器，进程号', 'Attempted to start the scheduler, PID', self.language)}: {process.pid}")

    def stop_scheduler(self) -> None:
        snapshot = daemon_snapshot()
        pid = snapshot.get("pid")
        if not pid:
            self.status_box.setPlainText(ui_text("当前没有记录到运行中的调度器。", "No running scheduler is currently recorded.", self.language))
            return
        try:
            os.kill(int(pid), signal.SIGTERM)
            self.status_box.setPlainText(f"{ui_text('已发送停止信号到 PID', 'Sent a stop signal to PID', self.language)} {pid}.")
        except OSError as exc:
            self.status_box.setPlainText(f"{ui_text('停止调度器失败', 'Failed to stop scheduler', self.language)}: {exc}")


class ResearchAssistantWindow(QMainWindow):
    PAGE_SPECS: list[tuple[str, type[QWidget]]] = [
        ("home", HomePage),
        ("literature_scout", LiteratureScoutPage),
        ("paper_reader", PaperReaderPage),
        ("pdf_fetcher", PDFDownloaderPage),
        ("topic_mapper", TopicMapperPage),
        ("idea_feasibility", IdeaFeasibilityPage),
        ("constraint_explorer", ConstraintExplorerPage),
        ("automation_config", AutomationPage),
    ]

    def __init__(self) -> None:
        super().__init__()
        ensure_project_layout()
        self._update_worker: WorkerThread | None = None
        self._update_download_worker: WorkerThread | None = None
        self._silent_update_check = False
        self.setWindowTitle("Research Assistant")
        self.resize(1560, 1024)
        self._build_ui()
        self._apply_style()
        if should_auto_check_updates():
            QTimer.singleShot(1200, self.check_app_update_silently)

    def _build_ui(self, current_row: int = 0) -> None:
        preferences = load_user_preferences()
        self.language = normalize_language(preferences["language"])

        central = QWidget()
        central.setObjectName("WindowShell")
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(20)

        sidebar = QFrame()
        sidebar.setObjectName("Sidebar")
        sidebar.setFixedWidth(256)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 16, 16, 16)
        sidebar_layout.setSpacing(16)

        brand_shell = QFrame()
        brand_shell.setObjectName("SidebarBrand")
        brand_layout = QVBoxLayout(brand_shell)
        brand_layout.setContentsMargins(14, 14, 14, 14)
        brand_layout.setSpacing(6)

        brand = QLabel("Research Assistant")
        brand.setObjectName("BrandLabel")
        brand.setWordWrap(True)
        brand_layout.addWidget(brand)

        subtitle = QLabel(ui_text("原生桌面研究工作台", "Native Desktop Research Workstation", self.language))
        subtitle.setObjectName("SidebarSubtitle")
        subtitle.setWordWrap(True)
        brand_layout.addWidget(subtitle)
        sidebar_layout.addWidget(brand_shell)

        nav_label = QLabel(t("sidebar.navigation", self.language))
        nav_label.setObjectName("SectionLabel")
        sidebar_layout.addWidget(nav_label)

        self.nav_list = QListWidget()
        self.nav_list.setObjectName("NavList")
        sidebar_layout.addWidget(self.nav_list, 1)

        sidebar_buttons = QHBoxLayout()
        open_workspace_button = set_secondary(QPushButton(ui_text("工作区", "Workspace", self.language)))
        open_workspace_button.clicked.connect(lambda: open_local_path(runtime_project_root()))
        open_outputs_button = set_secondary(QPushButton(ui_text("产物", "Outputs", self.language)))
        open_outputs_button.clicked.connect(lambda: open_local_path(OUTPUTS_DIR))
        sidebar_buttons.addWidget(open_workspace_button)
        sidebar_buttons.addWidget(open_outputs_button)
        sidebar_layout.addLayout(sidebar_buttons)

        layout.addWidget(sidebar, 0)

        main_shell = QWidget()
        main_shell.setObjectName("MainShell")
        main_layout = QVBoxLayout(main_shell)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(14)

        topbar = QFrame()
        topbar.setObjectName("TopBar")
        topbar_layout = QHBoxLayout(topbar)
        topbar_layout.setContentsMargins(18, 14, 18, 14)
        topbar_layout.setSpacing(14)

        topbar_text = QVBoxLayout()
        topbar_text.setContentsMargins(0, 0, 0, 0)
        topbar_text.setSpacing(4)
        topbar_title = QLabel(ui_text("桌面端研究工作台", "Desktop Research Workstation", self.language))
        topbar_title.setObjectName("TopBarTitle")
        topbar_subtitle = QLabel(str(workspace_root()))
        topbar_subtitle.setObjectName("TopBarSubtitle")
        topbar_subtitle.setWordWrap(True)
        topbar_text.addWidget(topbar_title)
        topbar_text.addWidget(topbar_subtitle)
        topbar_layout.addLayout(topbar_text, 1)

        self.language_combo = styled_combo_box()
        self.language_combo.setObjectName("TopBarCombo")
        self.language_combo.addItem(language_option_label("zh-CN", self.language), "zh-CN")
        self.language_combo.addItem(language_option_label("en-US", self.language), "en-US")
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(self.language)))
        self.language_combo.currentIndexChanged.connect(self.change_language)
        topbar_layout.addWidget(create_topbar_field(t("sidebar.language", self.language), self.language_combo, min_width=128))

        self.version_badge = QPushButton()
        self.version_badge.setObjectName("VersionBadge")
        self.version_badge.setText(version_label(current_version()))
        self.version_badge.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.version_badge.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.version_badge.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        topbar_layout.addWidget(self.version_badge)

        self.check_updates_button = set_secondary(QPushButton(ui_text("检查更新", "Check Updates", self.language)))
        self.check_updates_button.clicked.connect(self.check_app_update)
        topbar_layout.addWidget(self.check_updates_button)

        open_runtime_button = set_secondary(QPushButton(ui_text("打开运行目录", "Open Runtime", self.language)))
        open_runtime_button.clicked.connect(lambda: open_local_path(runtime_project_root()))
        topbar_layout.addWidget(open_runtime_button)
        main_layout.addWidget(topbar)

        self.pages = QStackedWidget()
        main_layout.addWidget(self.pages, 1)
        layout.addWidget(main_shell, 1)

        self.page_keys: list[str] = []
        for page_key, page_cls in self.PAGE_SPECS:
            self.page_keys.append(page_key)
            item = QListWidgetItem(page_copy(page_key, self.language)["nav_label"])
            self.nav_list.addItem(item)
            page = page_cls(self.language)
            if hasattr(page, "set_page_navigator"):
                getattr(page, "set_page_navigator")(self.navigate_to_page)
            self.pages.addWidget(page)

        self.nav_list.currentRowChanged.connect(self._on_page_changed)
        self.nav_list.setCurrentRow(max(0, min(current_row, self.nav_list.count() - 1)))
        self.statusBar().showMessage(f"{ui_text('工作区', 'Workspace', self.language)}: {workspace_root()}")

    def change_language(self, *_: Any) -> None:
        selected = self.language_combo.currentData()
        if not selected:
            return
        selected = normalize_language(selected)
        if selected == self.language:
            return
        current_row = self.nav_list.currentRow()
        update_user_preferences({"language": selected})
        self._build_ui(current_row)
        self._apply_style()

    def _on_page_changed(self, row: int) -> None:
        if row < 0:
            return
        self.pages.setCurrentIndex(row)
        label = page_copy(self.page_keys[row], self.language)["nav_label"]
        self.statusBar().showMessage(f"{label} | {ui_text('工作区', 'Workspace', self.language)}: {workspace_root()}")

    def navigate_to_page(self, page_key: str) -> None:
        if page_key not in self.page_keys:
            return
        self.nav_list.setCurrentRow(self.page_keys.index(page_key))

    def check_app_update(self) -> None:
        self._start_update_check(silent=False)

    def check_app_update_silently(self) -> None:
        if not should_auto_check_updates():
            return
        self._start_update_check(silent=True)

    def _start_update_check(self, *, silent: bool) -> None:
        if self._update_worker and self._update_worker.isRunning():
            return
        self._silent_update_check = silent
        self.check_updates_button.setEnabled(False)
        self.check_updates_button.setText(ui_text("检查中...", "Checking...", self.language))
        if not silent:
            self.statusBar().showMessage(ui_text("正在检查更新...", "Checking for updates...", self.language))
        self._update_worker = WorkerThread(check_for_updates)
        self._update_worker.result_ready.connect(self._on_update_check_result)
        self._update_worker.error_ready.connect(self._on_update_check_error)
        self._update_worker.finished.connect(self._reset_update_button)
        self._update_worker.start()

    def _reset_update_button(self) -> None:
        if hasattr(self, "check_updates_button"):
            self.check_updates_button.setEnabled(True)
            self.check_updates_button.setText(ui_text("检查更新", "Check Updates", self.language))

    def _on_update_check_result(self, payload: Any) -> None:
        status = str(payload.get("status") or "")
        current = version_label(str(payload.get("current_version") or current_version()))
        latest = version_label(str(payload.get("latest_version") or current_version()))
        download_url = str(payload.get("download_url") or "").strip()
        release_page_url = str(payload.get("release_page_url") or "").strip()
        asset_name = str(payload.get("asset_name") or "").strip()
        config_path = str(payload.get("config_path") or APP_UPDATE_CONFIG_PATH)
        download_in_app = bool(payload.get("download_in_app", True))
        open_in_browser = bool(payload.get("open_download_in_browser", False))

        if status == "update_available":
            if self._silent_update_check and bool(payload.get("already_prompted")):
                return
            lines = [
                f"{ui_text('当前版本', 'Current Version', self.language)}: {current}",
                f"{ui_text('最新版本', 'Latest Version', self.language)}: {latest}",
            ]
            published_at = str(payload.get("published_at") or "").strip()
            notes = str(payload.get("notes") or "").strip()
            if published_at:
                lines.append(f"{ui_text('发布时间', 'Published At', self.language)}: {published_at}")
            if notes:
                lines.extend(["", notes])
            mark_update_prompted(str(payload.get("latest_version") or ""))
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information)
            box.setWindowTitle(ui_text("发现新版本", "Update Available", self.language))
            box.setText("\n".join(lines))
            primary_button = None
            if download_url:
                primary_button = box.addButton(
                    ui_text("下载并安装", "Download And Install", self.language),
                    QMessageBox.ButtonRole.AcceptRole,
                )
            page_button = None
            if release_page_url:
                page_button = box.addButton(
                    ui_text("查看发布页", "Open Release Page", self.language),
                    QMessageBox.ButtonRole.ActionRole,
                )
            box.addButton(ui_text("稍后", "Later", self.language), QMessageBox.ButtonRole.RejectRole)
            box.exec()
            clicked = box.clickedButton()
            if clicked == primary_button and download_url:
                if download_in_app and not open_in_browser:
                    self._download_and_open_update(download_url, str(payload.get("latest_version") or ""), asset_name)
                else:
                    open_download_target(download_url)
            elif clicked == page_button and release_page_url:
                open_external_url(release_page_url)
            self.statusBar().showMessage(ui_text(f"发现新版本 {latest}", f"Update {latest} is available", self.language))
            return

        if status == "up_to_date":
            if self._silent_update_check:
                return
            message = ui_text(
                f"{current} 已是最新版本。",
                f"{current} is up to date.",
                self.language,
            )
            QMessageBox.information(self, ui_text("检查更新", "Check Updates", self.language), message)
            self.statusBar().showMessage(message)
            return

        if status == "unconfigured":
            if self._silent_update_check:
                return
            message = ui_text(
                f"当前版本：{current}\n尚未配置更新清单。\n请先填写：{config_path}",
                f"Current version: {current}\nNo update feed is configured yet.\nConfigure: {config_path}",
                self.language,
            )
            QMessageBox.information(self, ui_text("检查更新", "Check Updates", self.language), message)
            self.statusBar().showMessage(ui_text("未配置更新清单。", "No update feed configured.", self.language))
            return

        if status == "no_release":
            if self._silent_update_check:
                return
            message = str(payload.get("message") or ui_text("GitHub Releases 暂无已发布版本。", "No GitHub release has been published yet.", self.language))
            QMessageBox.information(self, ui_text("检查更新", "Check Updates", self.language), message)
            self.statusBar().showMessage(message)
            return

        message = str(payload.get("message") or ui_text("检查更新失败。", "Failed to check for updates.", self.language))
        if self._silent_update_check:
            self.statusBar().showMessage(message)
            return
        QMessageBox.warning(self, ui_text("检查更新", "Check Updates", self.language), message)
        self.statusBar().showMessage(message)

    def _on_update_check_error(self, trace: str) -> None:
        message = ui_text("检查更新失败。", "Failed to check for updates.", self.language)
        if self._silent_update_check:
            self.statusBar().showMessage(message)
            return
        QMessageBox.warning(self, ui_text("检查更新", "Check Updates", self.language), f"{message}\n\n{trace}")
        self.statusBar().showMessage(message)

    def _download_and_open_update(self, download_url: str, version: str, asset_name: str = "") -> None:
        if self._update_download_worker and self._update_download_worker.isRunning():
            return
        self.check_updates_button.setEnabled(False)
        self.check_updates_button.setText(ui_text("下载中...", "Downloading...", self.language))
        self.statusBar().showMessage(ui_text("正在下载更新安装包...", "Downloading the update installer...", self.language))
        self._update_download_worker = WorkerThread(lambda: download_update_package(download_url, version, asset_name or None))
        self._update_download_worker.result_ready.connect(self._on_update_download_result)
        self._update_download_worker.error_ready.connect(self._on_update_download_error)
        self._update_download_worker.finished.connect(self._reset_update_button)
        self._update_download_worker.start()

    def _on_update_download_result(self, payload: Any) -> None:
        download_path = str(payload.get("download_path") or "").strip()
        if not download_path:
            self._on_update_download_error(ui_text("未拿到更新包路径。", "Missing update package path.", self.language))
            return
        open_download_target(download_path)
        message = ui_text(
            f"已准备更新安装包：\n{download_path}\n\n安装器已打开，按提示完成覆盖安装即可。",
            f"The update package is ready:\n{download_path}\n\nThe installer has been opened. Follow it to replace the current app.",
            self.language,
        )
        QMessageBox.information(self, ui_text("开始更新", "Start Update", self.language), message)
        self.statusBar().showMessage(ui_text("更新安装包已就绪。", "The update installer is ready.", self.language))

    def _on_update_download_error(self, trace: str) -> None:
        message = ui_text("下载更新失败。", "Failed to download the update.", self.language)
        QMessageBox.warning(self, ui_text("开始更新", "Start Update", self.language), f"{message}\n\n{trace}")
        self.statusBar().showMessage(message)

    def _apply_style(self) -> None:
        QApplication.instance().setStyleSheet(
            """
            QMainWindow {
                background: #f4eee4;
            }
            QDialog, QMessageBox {
                background: #fffaf2;
            }
            QWidget {
                color: #223126;
                font-size: 13px;
                font-family: "PingFang SC", "SF Pro Text", "Iowan Old Style", "Helvetica Neue";
            }
            QMessageBox QWidget, QDialog QWidget {
                background: #fffaf2;
                color: #223126;
            }
            QLabel {
                background: transparent;
            }
            QMessageBox QLabel {
                color: #223126;
                background: transparent;
            }
            QWidget#WindowShell, QWidget#MainShell, QWidget#PageCanvas,
            QWidget#SectionColumns, QWidget#SectionColumn, QWidget#HeaderActions,
            QWidget#HeaderMetricRow, QWidget#PageHeaderInfo, QWidget#PageHeaderExtra,
            QWidget#TopStatusRow {
                background: transparent;
            }
            QWidget#TopBarField {
                background: transparent;
            }
            QFrame#Sidebar {
                background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 #173f33, stop:0.56 #14382e, stop:1 #102c24);
                border: 1px solid rgba(232, 240, 233, 0.18);
                border-radius: 22px;
            }
            QFrame#SidebarBrand {
                background: rgba(255, 248, 236, 0.14);
                border: 1px solid rgba(255, 248, 236, 0.22);
                border-radius: 16px;
            }
            QFrame#TopBar {
                background: rgba(255, 251, 245, 0.9);
                border: 1px solid #ddcfba;
                border-radius: 18px;
            }
            QFrame#PageHeader {
                background: transparent;
                border: none;
            }
            QFrame#PanelCard {
                background: rgba(255, 252, 247, 0.96);
                border: 1px solid #dfd3c0;
                border-radius: 18px;
            }
            QFrame#MetricCard {
                background: rgba(255, 249, 241, 0.98);
                border: 1px solid #ddd0bb;
                border-radius: 14px;
            }
            QFrame#ActionTile {
                background: rgba(255, 252, 247, 0.98);
                border: 1px solid #ddd1bc;
                border-radius: 16px;
            }
            QLabel#BrandLabel {
                color: #fff8ee;
                font-size: 22px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QLabel#SidebarSubtitle {
                color: rgba(247, 240, 228, 0.82);
            }
            QLabel#SectionLabel {
                color: rgba(244, 237, 223, 0.72);
                font-weight: 600;
                font-size: 12px;
            }
            QLabel#PageTitle {
                color: #1c3026;
                font-size: 30px;
                font-weight: 700;
            }
            QLabel#PageCaption {
                color: #5b675f;
                font-size: 13px;
            }
            QLabel#FieldLabel {
                color: #49594e;
                font-size: 12px;
                font-weight: 700;
                padding-left: 2px;
            }
            QLabel#SectionEyebrow {
                color: #897d68;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.1px;
            }
            QLabel#SectionBarTitle {
                color: #1c3026;
                font-size: 14px;
                font-weight: 700;
            }
            QLabel#SectionBarDescription {
                color: #5c685f;
                font-size: 12px;
            }
            QLabel#MetricLabel {
                color: #6c746d;
                font-size: 11px;
                font-weight: 600;
            }
            QLabel#MetricValue {
                color: #223126;
                font-size: 13px;
                font-weight: 700;
            }
            QLabel#ActionTitle {
                color: #1e3026;
                font-size: 15px;
                font-weight: 700;
            }
            QLabel#ActionSubtitle {
                color: #5e6a62;
                font-size: 12px;
            }
            QLabel#TopBarLabel {
                color: #59675d;
                font-weight: 600;
            }
            QLabel#TopBarFieldLabel {
                color: #59675d;
                font-size: 11px;
                font-weight: 700;
                padding-left: 2px;
            }
            QLabel#TopBarTitle {
                color: #223126;
                font-size: 18px;
                font-weight: 700;
            }
            QLabel#TopBarSubtitle {
                color: #58665c;
            }
            QPushButton#VersionBadge {
                background: #17392d;
                color: #fff8ec;
                border-radius: 11px;
                border: none;
                padding: 9px 12px;
                font-size: 12px;
                font-weight: 700;
            }
            QLabel#CardTitle {
                color: #1d2e22;
                font-size: 17px;
                font-weight: 700;
            }
            QLabel#CardSubtitle {
                color: #5b675f;
            }
            QLabel#SubsectionLabel {
                color: #4f5e54;
                font-weight: 700;
                padding-top: 4px;
            }
            QLabel#KeyboardHint {
                color: #6a766d;
                font-size: 11px;
            }
            QListWidget#NavList {
                background: rgba(255, 248, 236, 0.06);
                border: 1px solid rgba(237, 242, 237, 0.12);
                border-radius: 16px;
                padding: 8px;
                color: #f7f1e3;
            }
            QListWidget#NavList::item {
                background: rgba(255, 255, 255, 0.05);
                color: #f7f1e3;
                border: 1px solid rgba(245, 238, 226, 0.03);
                border-radius: 11px;
                padding: 11px 12px;
                margin: 4px 0;
                font-weight: 600;
            }
            QListWidget#NavList::item:hover {
                background: rgba(255, 248, 236, 0.12);
                color: #fffaf0;
                border: 1px solid rgba(255, 248, 236, 0.18);
            }
            QListWidget#NavList::item:selected {
                background: #f0e2c4;
                color: #163128;
                border: 1px solid #e1cfab;
                font-weight: 700;
            }
            QListWidget#MultiSelectList {
                background: rgba(255, 255, 255, 0.98);
                border: 1px solid #d9ceb9;
                border-radius: 12px;
                padding: 6px;
            }
            QListWidget#MultiSelectList::item {
                background: #f6efe5;
                border: 1px solid transparent;
                border-radius: 8px;
                padding: 8px 10px;
                margin: 2px 0;
            }
            QListWidget#MultiSelectList::item:selected {
                background: #17392d;
                color: #fff8ec;
            }
            QPushButton {
                background: #17392d;
                color: #fff8ec;
                border: none;
                border-radius: 10px;
                padding: 9px 14px;
                font-weight: 700;
                min-height: 18px;
            }
            QPushButton:hover {
                background: #1d4838;
            }
            QPushButton:disabled {
                background: #9aa89f;
                color: #eff2ec;
            }
            QPushButton[secondary="true"] {
                background: #efe4d1;
                color: #24352a;
                border: 1px solid #d4c3a6;
            }
            QPushButton[secondary="true"]:hover {
                background: #e2d5bd;
            }
            QFrame#FieldSection {
                background: transparent;
                border: none;
            }
            QFrame#SectionBar {
                background: rgba(244, 236, 223, 0.72);
                border: 1px solid #e3d4be;
                border-radius: 14px;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QTextBrowser, QListWidget {
                border-radius: 12px;
            }
            QLineEdit, QTextEdit, QPlainTextEdit, QComboBox, QSpinBox, QTextBrowser {
                background: rgba(255, 255, 255, 0.98);
                border: 1px solid #d9ceb9;
                padding: 8px 10px;
                selection-background-color: #d9ebd4;
            }
            QLineEdit, QComboBox, QSpinBox {
                min-height: 34px;
            }
            QComboBox#TopBarCombo {
                min-width: 128px;
                padding-right: 28px;
            }
            QComboBox::drop-down {
                border: none;
                width: 28px;
            }
            QComboBox QAbstractItemView, QListView#ComboPopup, QAbstractItemView {
                background: #fffaf2;
                color: #223126;
                border: 1px solid #d9ceb9;
                border-radius: 12px;
                padding: 6px;
                selection-background-color: #ead8ad;
                selection-color: #17392d;
                outline: 0;
            }
            QComboBox QAbstractItemView::item, QListView#ComboPopup::item, QAbstractItemView::item {
                min-height: 30px;
                padding: 7px 10px;
                border-radius: 8px;
                margin: 1px 0;
                color: #223126;
                background: transparent;
            }
            QComboBox QAbstractItemView::item:hover, QListView#ComboPopup::item:hover, QAbstractItemView::item:hover {
                background: #f1e3be;
                color: #17392d;
                font-weight: 700;
            }
            QComboBox QAbstractItemView::item:selected, QListView#ComboPopup::item:selected, QAbstractItemView::item:selected {
                background: #ead8ad;
                color: #17392d;
                font-weight: 700;
            }
            QScrollArea {
                border: none;
                background: transparent;
            }
            QTabWidget#ResultTabs::pane {
                background: rgba(255, 255, 255, 0.98);
                border: 1px solid #ddd1bc;
                border-radius: 14px;
                margin-top: 10px;
            }
            QTabWidget#ResultTabs::tab-bar {
                left: 10px;
            }
            QTabBar::tab {
                background: #eee3d2;
                color: #314338;
                border: 1px solid #d8cab1;
                border-bottom: none;
                border-top-left-radius: 10px;
                border-top-right-radius: 10px;
                padding: 8px 14px;
                margin-right: 6px;
                margin-top: 3px;
            }
            QTabBar::tab:selected {
                background: #17392d;
                color: #fff8ec;
                margin-top: 0;
            }
            QStatusBar {
                background: #f4eee4;
                color: #5d685f;
            }
            QCheckBox {
                spacing: 8px;
            }
            QCheckBox::indicator {
                width: 18px;
                height: 18px;
            }
            """
        )
        self._sync_topbar_control_heights()

    def _sync_topbar_control_heights(self) -> None:
        if not hasattr(self, "version_badge") or not hasattr(self, "check_updates_button"):
            return
        target_height = self.check_updates_button.sizeHint().height()
        if target_height <= 0:
            return
        self.version_badge.setFixedHeight(target_height)
