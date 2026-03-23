from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import PaperFetcherInput, detect_codex_cli, download_and_run_reader, run_paper_fetch
from ui.services.config_store import OUTPUTS_DIR, QUALITY_PROFILE_OPTIONS, ensure_project_layout, load_interesting_papers, load_user_preferences, remove_interesting_paper, update_user_preferences
from ui.services.page_helpers import (
    format_quality_option,
    render_app_sidebar,
    render_bridge_response,
    render_codex_status_panel,
    render_page_header,
    render_pdf_extraction_status,
)
from ui.services.paper_sources import split_references
from ui.services.result_loader import list_recent_markdown
from ui.services.ui_text import expander_title, t


ensure_project_layout()
preferences = load_user_preferences()
language = preferences["language"]
task_defaults = preferences["task_defaults"]["pdf_fetcher"]
codex_status = detect_codex_cli(language=language)
quality_options = list(QUALITY_PROFILE_OPTIONS)

render_app_sidebar("pdf_fetcher")
render_page_header("pdf_fetcher")
render_codex_status_panel(codex_status, expanded=False)

with st.form("pdf_fetch_form"):
    raw_references = st.text_area(
        t("pdf_fetcher.references", language),
        height=180,
        placeholder=t("pdf_fetcher.references_placeholder", language),
    )
    auto_read = st.checkbox(t("pdf_fetcher.auto_read", language), value=bool(task_defaults.get("auto_read", False)))
    with st.expander(expander_title("advanced_options", language), expanded=False):
        save_dir = st.text_input(t("pdf_fetcher.save_dir", language), value=str(task_defaults.get("save_dir", OUTPUTS_DIR / "pdfs")))
        reader_quality_profile = st.selectbox(
            t("pdf_fetcher.reader_quality_profile", language),
            options=quality_options,
            index=quality_options.index(task_defaults.get("reader_quality_profile", "balanced")),
            format_func=lambda item: format_quality_option(item, task_type="paper_reader"),
            disabled=not auto_read,
        )
        show_candidates = st.checkbox(t("pdf_fetcher.show_candidates", language), value=True)
    submitted = st.form_submit_button(t("pdf_fetcher.submit", language), use_container_width=True)

if submitted:
    update_user_preferences(
        {
            "task_defaults": {
                "pdf_fetcher": {
                    "save_dir": save_dir,
                    "auto_read": auto_read,
                    "reader_quality_profile": reader_quality_profile,
                }
            }
        }
    )
    references = split_references(raw_references)
    if not references:
        st.warning(t("pdf_fetcher.no_reference", language))
    else:
        for index, reference in enumerate(references, start=1):
            st.markdown(f"### {t('pdf_fetcher.task_heading', language, index=index)}")
            st.code(reference, language="text")
            if auto_read:
                results = download_and_run_reader(
                    reference=reference,
                    quality_profile="economy",
                    reader_quality_profile=reader_quality_profile,
                    output_dir=save_dir,
                    language=language,
                )
                download = results["download"]
                reader = results["reader"]
                if download:
                    st.markdown(f"**{t('common.download_status', language)}**")
                    render_bridge_response(download)
                    candidates = (download.payload or {}).get("candidates") or []
                    if show_candidates and download.status != "success" and candidates:
                        st.markdown("\n".join(f"- {item}" for item in candidates))
                if reader:
                    st.markdown(f"**{t('common.read_status', language)}**")
                    render_bridge_response(reader)
                    render_pdf_extraction_status(reader.payload or {})
            else:
                response = run_paper_fetch(
                    PaperFetcherInput(
                        reference=reference,
                        output_dir=save_dir,
                        quality_profile="economy",
                        language=language,
                    )
                )
                render_bridge_response(response)
                candidates = (response.payload or {}).get("candidates") or []
                if show_candidates and response.status != "success" and candidates:
                    st.markdown(t("pdf_fetcher.candidate_pages", language))
                    st.markdown("\n".join(f"- {item}" for item in candidates))

st.divider()
st.subheader(t("pdf_fetcher.interesting_heading", language))
interesting = load_interesting_papers()
if not interesting["items"]:
    st.info(t("pdf_fetcher.no_interesting", language))
else:
    for index, item in enumerate(interesting["items"], start=1):
        title = item.get("title") or f"Paper {index}"
        paper_url = item.get("paper_url", "")
        with st.expander(f"{index}. {title}", expanded=index <= 5):
            st.markdown(
                "\n".join(
                    [
                        f"- {t('common.paper_link', language)}: {paper_url or t('common.not_provided', language)}",
                        f"- {t('pdf_fetcher.source_result', language)}: {item.get('source_result', t('common.not_recorded', language))}",
                        f"- {t('pdf_fetcher.saved_at', language)}: {item.get('saved_at', t('common.not_recorded', language))}",
                    ]
                )
            )
            col1, col2, col3 = st.columns(3)
            if col1.button(t("pdf_fetcher.download_only", language), key=f"fetch-interesting-{index}", disabled=not bool(paper_url)):
                response = run_paper_fetch(
                    PaperFetcherInput(
                        reference=paper_url,
                        output_dir=OUTPUTS_DIR / "pdfs",
                        quality_profile="economy",
                        language=language,
                    )
                )
                render_bridge_response(response)
            if col2.button(t("pdf_fetcher.download_and_read", language), key=f"fetch-read-interesting-{index}", disabled=not bool(paper_url)):
                results = download_and_run_reader(
                    reference=paper_url,
                    quality_profile="economy",
                    reader_quality_profile=task_defaults.get("reader_quality_profile", "balanced"),
                    output_dir=OUTPUTS_DIR / "pdfs",
                    language=language,
                )
                if results["download"]:
                    render_bridge_response(results["download"])
                if results["reader"]:
                    render_bridge_response(results["reader"])
                    render_pdf_extraction_status((results["reader"].payload or {}) if results["reader"] else {})
            if col3.button(t("pdf_fetcher.remove_mark", language), key=f"remove-interesting-{index}"):
                removed = remove_interesting_paper(paper_url or title)
                if removed:
                    st.success(t("pdf_fetcher.removed", language))
                else:
                    st.info(t("pdf_fetcher.not_found", language))

st.divider()
st.subheader(t("pdf_fetcher.recent_read_results", language))
recent_summaries = list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=10)
if recent_summaries:
    st.markdown("\n".join(f"- `{path.name}`" for path in recent_summaries))
else:
    st.info(t("pdf_fetcher.no_reader_results", language))
