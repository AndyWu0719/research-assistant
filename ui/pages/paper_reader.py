from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import PaperReaderInput, detect_codex_cli, run_paper_reader
from ui.services.config_store import OUTPUTS_DIR, QUALITY_PROFILE_OPTIONS, ensure_project_layout, load_user_preferences, update_user_preferences
from ui.services.page_helpers import (
    format_quality_option,
    recall_prompt,
    remember_prompt,
    render_app_sidebar,
    render_bridge_response,
    render_codex_status_panel,
    render_named_sections,
    render_page_header,
    render_path_expander,
    render_pdf_extraction_status,
    render_prompt_expander,
)
from ui.services.result_loader import list_recent_markdown, load_result
from ui.services.ui_text import SUMMARY_DEPTH_OPTIONS, expander_title, summary_depth_label, t


STATE_KEY = "paper_reader_last_execution"
PAPER_READER_SECTION_KEYS = [
    "one_sentence",
    "paper_overview",
    "background",
    "goal",
    "core_problem_and_method",
    "core_method",
    "key_experiments_and_conclusions",
    "experiments",
    "results",
    "limitations",
    "open_resources",
    "diagram_plain",
    "diagram_explanation",
]

ensure_project_layout()
preferences = load_user_preferences()
language = preferences["language"]
task_defaults = preferences["task_defaults"]["paper_reader"]
codex_status = detect_codex_cli(language=language)
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = task_defaults.get("quality_profile", "balanced")

render_app_sidebar("paper_reader")
render_page_header("paper_reader")
render_codex_status_panel(codex_status, expanded=False)

with st.form("paper_reader_form"):
    paper_reference = st.text_input(
        t("paper_reader.paper_reference", language),
        placeholder=t("paper_reader.paper_reference_placeholder", language),
    )
    summary_depth = st.selectbox(
        t("paper_reader.summary_depth", language),
        options=SUMMARY_DEPTH_OPTIONS,
        index=SUMMARY_DEPTH_OPTIONS.index(task_defaults.get("summary_depth", "standard")),
        format_func=lambda item: summary_depth_label(item, language),
    )
    quality_profile = st.selectbox(
        t("common.quality_profile", language),
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="paper_reader"),
        help=t("paper_reader.quality_help", language),
    )
    with st.expander(expander_title("advanced_options", language), expanded=False):
        diagram_summary = st.checkbox(t("paper_reader.diagram_summary", language), value=bool(task_defaults.get("diagram_summary", True)))
        focus_experiments = st.checkbox(t("paper_reader.focus_experiments", language), value=bool(task_defaults.get("focus_experiments", True)))
        auto_fetch_pdf = st.checkbox(t("paper_reader.auto_fetch_pdf", language), value=bool(task_defaults.get("auto_fetch_pdf", True)))
    submitted = st.form_submit_button(t("paper_reader.submit", language), use_container_width=True)

if submitted:
    update_user_preferences(
        {
            "task_defaults": {
                "paper_reader": {
                    "quality_profile": quality_profile,
                    "summary_depth": summary_depth,
                    "diagram_summary": diagram_summary,
                    "focus_experiments": focus_experiments,
                    "auto_fetch_pdf": auto_fetch_pdf,
                }
            }
        }
    )
    response = run_paper_reader(
        PaperReaderInput(
            paper_reference=paper_reference,
            summary_depth=summary_depth,
            diagram_summary=diagram_summary,
            focus_experiments=focus_experiments,
            auto_fetch_pdf=auto_fetch_pdf,
            quality_profile=quality_profile,
            language=language,
        )
    )
    remember_prompt(
        STATE_KEY,
        {
            "response": response.to_dict(),
            "prompt": response.prompt_text,
        },
    )

stored = recall_prompt(STATE_KEY)
if stored:
    st.subheader(t("common.status_heading", language))
    render_bridge_response(stored["response"])
    fetch_payload = (stored["response"].get("payload") or {}).get("fetch")
    if fetch_payload:
        st.markdown(f"**{t('paper_reader.pdf_fetch_chain', language)}**")
        render_bridge_response(fetch_payload)
    render_prompt_expander(stored.get("prompt"))
    render_pdf_extraction_status(stored["response"].get("payload") or {})
    output_path = stored["response"].get("expected_output_path")
    if output_path and Path(output_path).exists():
        st.markdown(f"**{t('common.current_read_result', language)}**")
        render_named_sections(load_result(Path(output_path)), PAPER_READER_SECTION_KEYS)

st.divider()
st.subheader(t("paper_reader.recent_results_heading", language))
recent_results = list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=20)
if not recent_results:
    st.info(t("paper_reader.no_results", language))
else:
    result_lookup = {path.name: path for path in recent_results}
    selected_result = st.selectbox(
        t("paper_reader.select_result_file", language),
        options=list(result_lookup.keys()),
    )
    selected_path = result_lookup[selected_result]
    loaded = load_result(selected_path)
    render_path_expander(
        t("common.output_and_paths", language),
        {
            t("common.result_file", language): selected_path,
            t("common.json_sidecar", language): selected_path.with_suffix(".json"),
        },
    )
    render_pdf_extraction_status(loaded.metadata)
    render_named_sections(loaded, PAPER_READER_SECTION_KEYS)
