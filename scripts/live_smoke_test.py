from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.config_store import OUTPUTS_DIR, TIME_RANGE_OPTIONS, ensure_project_layout, load_user_preferences, update_user_preferences
from ui.services.file_naming import smoke_report_path
from ui.services.result_loader import load_result
from ui.services.ui_text import risk_preference_label, summary_depth_label, t, time_range_label


PAGE_TIMEOUT_SECONDS = 900
TEST_LANGUAGE = "zh-CN"


def widget_by_label(sequence: list[Any], label: str) -> Any:
    for item in sequence:
        item_label = getattr(item, "label", None) or item.proto.label
        if item_label == label:
            return item
    raise KeyError(f"Widget not found: {label}")


def button_by_label(at: AppTest, label: str) -> Any:
    for item in at.button:
        item_label = getattr(item, "label", None) or item.proto.label
        if item_label == label:
            return item
    raise KeyError(f"Button not found: {label}")


def selectbox_choose(widget: Any, target: str) -> None:
    options = [str(item) for item in widget.options]
    if target in options:
        widget.select(target)
        return
    for option in options:
        if option.startswith(f"{target} |") or target in option:
            widget.select(option)
            return
    raise ValueError(f"Option not found for {widget.proto.label}: {target} / {options}")


def snapshot(directory: Path, pattern: str) -> dict[Path, float]:
    return {path: path.stat().st_mtime for path in directory.glob(pattern) if path.is_file()}


def changed_paths(directory: Path, pattern: str, before: dict[Path, float]) -> list[Path]:
    candidates = []
    for path in directory.glob(pattern):
        if not path.is_file():
            continue
        mtime = path.stat().st_mtime
        if mtime > before.get(path, 0.0) + 1e-6:
            candidates.append(path)
    return sorted(candidates, key=lambda item: item.stat().st_mtime, reverse=True)


def latest_changed(directory: Path, pattern: str, before: dict[Path, float]) -> Path | None:
    items = changed_paths(directory, pattern, before)
    return items[0] if items else None


def latest_existing(directory: Path, pattern: str) -> Path | None:
    items = [path for path in directory.glob(pattern) if path.is_file()]
    return sorted(items, key=lambda item: item.stat().st_mtime, reverse=True)[0] if items else None


def submit_page(page_path: str, prepare: Callable[[AppTest], None], submit_label: str) -> AppTest:
    at = AppTest.from_file(page_path)
    at.run(timeout=30)
    prepare(at)
    button_by_label(at, submit_label).click()
    at.run(timeout=PAGE_TIMEOUT_SECONDS)
    if at.exception:
        raise RuntimeError("; ".join(str(item.value) for item in at.exception))
    return at


def record_from_markdown(task_type: str, changed_markdown: Path | None, input_summary: dict[str, Any], page_name: str) -> dict[str, Any]:
    if not changed_markdown:
        return {
            "page": page_name,
            "task_type": task_type,
            "quality_profile": "economy",
            "model": None,
            "reasoning_effort": None,
            "input_summary": input_summary,
            "output_paths": [],
            "status": "error",
            "error": "No new Markdown output file was detected." if TEST_LANGUAGE == "en-US" else "未检测到新的 Markdown 输出文件。",
        }

    loaded = load_result(changed_markdown)
    metadata = loaded.metadata
    output_paths = metadata.get("output_paths") or {"markdown": str(changed_markdown), "json": str(changed_markdown.with_suffix('.json'))}
    return {
        "page": page_name,
        "task_type": task_type,
        "quality_profile": metadata.get("quality_profile", "economy"),
        "model": metadata.get("model"),
        "reasoning_effort": metadata.get("reasoning_effort"),
        "input_summary": input_summary,
        "output_paths": output_paths,
        "status": metadata.get("status", "success"),
        "error": metadata.get("error"),
    }


def run_pdf_pipeline_test() -> dict[str, Any]:
    pdf_before = snapshot(OUTPUTS_DIR / "pdfs", "*.pdf")
    summary_before = snapshot(OUTPUTS_DIR / "paper_summaries", "*.md")

    def prepare(at: AppTest) -> None:
        widget_by_label(at.text_area, t("pdf_fetcher.references", TEST_LANGUAGE)).input("1810.04805")
        widget_by_label(at.checkbox, t("pdf_fetcher.auto_read", TEST_LANGUAGE)).check()
        selectbox_choose(widget_by_label(at.selectbox, t("pdf_fetcher.reader_quality_profile", TEST_LANGUAGE)), "economy")

    submit_page("ui/pages/pdf_fetcher.py", prepare, t("pdf_fetcher.submit", TEST_LANGUAGE))
    changed_pdf = latest_changed(OUTPUTS_DIR / "pdfs", "*.pdf", pdf_before) or latest_existing(OUTPUTS_DIR / "pdfs", "*.pdf")
    changed_summary = latest_changed(OUTPUTS_DIR / "paper_summaries", "*.md", summary_before)
    summary_record = record_from_markdown(
        task_type="pdf_fetcher_pipeline",
        changed_markdown=changed_summary,
        input_summary={"reference": "1810.04805", "auto_read": True},
        page_name="PDF Downloads",
    )
    output_paths = dict(summary_record.get("output_paths") or {})
    if changed_pdf:
        output_paths["pdf"] = str(changed_pdf)
        output_paths["pdf_sidecar"] = str(changed_pdf.with_suffix(".source.json"))
    summary_record["output_paths"] = output_paths
    return summary_record


def run_paper_reader_test(pdf_path: str) -> dict[str, Any]:
    before = snapshot(OUTPUTS_DIR / "paper_summaries", "*.md")

    def prepare(at: AppTest) -> None:
        widget_by_label(at.text_input, t("paper_reader.paper_reference", TEST_LANGUAGE)).input(pdf_path)
        selectbox_choose(widget_by_label(at.selectbox, t("paper_reader.summary_depth", TEST_LANGUAGE)), summary_depth_label("standard", TEST_LANGUAGE))
        selectbox_choose(widget_by_label(at.selectbox, t("common.quality_profile", TEST_LANGUAGE)), "economy")
        widget_by_label(at.checkbox, t("paper_reader.diagram_summary", TEST_LANGUAGE)).check()
        widget_by_label(at.checkbox, t("paper_reader.focus_experiments", TEST_LANGUAGE)).uncheck()
        widget_by_label(at.checkbox, t("paper_reader.auto_fetch_pdf", TEST_LANGUAGE)).uncheck()

    submit_page("ui/pages/paper_reader.py", prepare, t("paper_reader.submit", TEST_LANGUAGE))
    changed = latest_changed(OUTPUTS_DIR / "paper_summaries", "*.md", before)
    return record_from_markdown(
        task_type="paper_reader",
        changed_markdown=changed,
        input_summary={"paper_reference": pdf_path, "quality_profile": "economy"},
        page_name="Paper Deep Read",
    )


def run_top10_test() -> dict[str, Any]:
    before = snapshot(OUTPUTS_DIR / "daily_top10", "*.md")

    def prepare(at: AppTest) -> None:
        widget_by_label(at.text_input, t("common.field", TEST_LANGUAGE)).input("speech representation learning for low-resource ASR")
        selectbox_choose(widget_by_label(at.selectbox, t("common.time_range", TEST_LANGUAGE)), time_range_label(TIME_RANGE_OPTIONS["30d"], TEST_LANGUAGE))
        widget_by_label(at.multiselect, t("common.sources", TEST_LANGUAGE)).set_value(["arXiv", "OpenReview"])
        selectbox_choose(widget_by_label(at.selectbox, t("common.ranking_profile", TEST_LANGUAGE)), "resource-constrained")
        selectbox_choose(widget_by_label(at.selectbox, t("common.quality_profile", TEST_LANGUAGE)), "economy")
        widget_by_label(at.number_input, t("common.top_k", TEST_LANGUAGE)).set_value(3)
        widget_by_label(at.text_area, t("common.constraints", TEST_LANGUAGE)).input("单卡 24G，优先公开代码和可快速复现的工作")

    submit_page("ui/pages/top10.py", prepare, t("top10.submit", TEST_LANGUAGE))
    changed = latest_changed(OUTPUTS_DIR / "daily_top10", "*.md", before)
    return record_from_markdown(
        task_type="literature_scout",
        changed_markdown=changed,
        input_summary={
            "field": "speech representation learning for low-resource ASR",
            "time_range": time_range_label(TIME_RANGE_OPTIONS["30d"], TEST_LANGUAGE),
            "sources": ["arXiv", "OpenReview"],
            "ranking_profile": "resource-constrained",
            "top_k": 3,
        },
        page_name="Top 10 Literature Scan",
    )


def run_topic_mapper_test() -> dict[str, Any]:
    before = snapshot(OUTPUTS_DIR / "topic_maps", "*.md")

    def prepare(at: AppTest) -> None:
        widget_by_label(at.text_area, t("topic_mapper.topic", TEST_LANGUAGE)).input("multimodal evidence retrieval for long-video reasoning")
        selectbox_choose(widget_by_label(at.selectbox, t("common.time_window", TEST_LANGUAGE)), time_range_label(TIME_RANGE_OPTIONS["30d"], TEST_LANGUAGE))
        selectbox_choose(widget_by_label(at.selectbox, t("common.quality_profile", TEST_LANGUAGE)), "economy")
        widget_by_label(at.checkbox, t("topic_mapper.cross_domain", TEST_LANGUAGE)).uncheck()
        widget_by_label(at.number_input, t("topic_mapper.return_count", TEST_LANGUAGE)).set_value(6)
        selectbox_choose(widget_by_label(at.selectbox, t("topic_mapper.ranking_mode", TEST_LANGUAGE)), "resource-constrained")

    submit_page("ui/pages/topic_mapper.py", prepare, t("topic_mapper.submit", TEST_LANGUAGE))
    changed = latest_changed(OUTPUTS_DIR / "topic_maps", "*.md", before)
    return record_from_markdown(
        task_type="topic_mapper",
        changed_markdown=changed,
        input_summary={
            "topic": "multimodal evidence retrieval for long-video reasoning",
            "time_range": time_range_label(TIME_RANGE_OPTIONS["30d"], TEST_LANGUAGE),
            "return_count": 6,
            "ranking_mode": "resource-constrained",
        },
        page_name="Topic Map",
    )


def run_idea_feasibility_test() -> dict[str, Any]:
    before = snapshot(OUTPUTS_DIR / "feasibility_reports", "*.md")

    def prepare(at: AppTest) -> None:
        widget_by_label(at.text_area, t("idea_feasibility.idea", TEST_LANGUAGE)).input("Use retrieval supervision to improve long-video reasoning under single-GPU constraints")
        widget_by_label(at.text_input, t("idea_feasibility.target_field", TEST_LANGUAGE)).input("multimodal long-video reasoning")
        selectbox_choose(widget_by_label(at.selectbox, t("common.quality_profile", TEST_LANGUAGE)), "economy")
        widget_by_label(at.text_input, t("idea_feasibility.compute_budget", TEST_LANGUAGE)).input("单卡 24G")
        widget_by_label(at.text_input, t("idea_feasibility.data_budget", TEST_LANGUAGE)).input("优先公开 benchmark 与公开视频数据")
        selectbox_choose(widget_by_label(at.selectbox, t("idea_feasibility.risk_preference", TEST_LANGUAGE)), risk_preference_label("balanced", TEST_LANGUAGE))
        widget_by_label(at.checkbox, t("idea_feasibility.prefer_low_cost_validation", TEST_LANGUAGE)).check()

    submit_page("ui/pages/idea_feasibility.py", prepare, t("idea_feasibility.submit", TEST_LANGUAGE))
    changed = latest_changed(OUTPUTS_DIR / "feasibility_reports", "*.md", before)
    return record_from_markdown(
        task_type="idea_feasibility",
        changed_markdown=changed,
        input_summary={
            "idea": "Use retrieval supervision to improve long-video reasoning under single-GPU constraints",
            "target_field": "multimodal long-video reasoning",
            "compute_budget": "单卡 24G",
            "data_budget": "优先公开 benchmark 与公开视频数据",
        },
        page_name="Idea Feasibility",
    )


def run_constraint_explorer_test() -> dict[str, Any]:
    before = snapshot(OUTPUTS_DIR / "constraint_reports", "*.md")

    def prepare(at: AppTest) -> None:
        widget_by_label(at.text_input, t("common.field", TEST_LANGUAGE)).input("speech representation learning for low-resource ASR")
        widget_by_label(at.text_input, t("constraint_explorer.compute_limit", TEST_LANGUAGE)).input("单卡 24G")
        widget_by_label(at.text_input, t("constraint_explorer.data_limit", TEST_LANGUAGE)).input("优先公开数据或可替代小规模数据")
        selectbox_choose(widget_by_label(at.selectbox, t("common.quality_profile", TEST_LANGUAGE)), "economy")
        widget_by_label(at.checkbox, t("constraint_explorer.prefer_reproduction", TEST_LANGUAGE)).check()
        widget_by_label(at.checkbox, t("constraint_explorer.prefer_open_source", TEST_LANGUAGE)).check()

    submit_page("ui/pages/constraint_explorer.py", prepare, t("constraint_explorer.submit", TEST_LANGUAGE))
    changed = latest_changed(OUTPUTS_DIR / "constraint_reports", "*.md", before)
    return record_from_markdown(
        task_type="constraint_explorer",
        changed_markdown=changed,
        input_summary={
            "field": "speech representation learning for low-resource ASR",
            "compute_limit": "单卡 24G",
            "data_limit": "优先公开数据或可替代小规模数据",
        },
        page_name="Constraint Explorer",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--language", default="zh-CN", choices=["zh-CN", "en-US"])
    return parser.parse_args()


def main() -> int:
    global TEST_LANGUAGE
    args = parse_args()
    TEST_LANGUAGE = args.language
    ensure_project_layout()
    original_language = load_user_preferences()["language"]
    report: list[dict[str, Any]] = []

    try:
        update_user_preferences({"language": TEST_LANGUAGE})
        pdf_record = run_pdf_pipeline_test()
        report.append(pdf_record)

        pdf_output = (pdf_record.get("output_paths") or {}).get("pdf")
        if not pdf_output:
            raise RuntimeError(
                "The PDF downloads page did not produce a PDF, so the paper deep-read smoke test cannot continue."
                if TEST_LANGUAGE == "en-US"
                else "PDF 下载页未产出 PDF，无法继续单篇论文精读 smoke test。"
            )

        report.append(run_paper_reader_test(str(pdf_output)))
        report.append(run_top10_test())
        report.append(run_topic_mapper_test())
        report.append(run_idea_feasibility_test())
        report.append(run_constraint_explorer_test())
    finally:
        update_user_preferences({"language": original_language})

    report_path = smoke_report_path("live-smoke-test")
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(report_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
