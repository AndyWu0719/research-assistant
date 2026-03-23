from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import (
    LiteratureScoutInput,
    PaperFetcherInput,
    detect_codex_cli,
    download_and_run_reader,
    run_literature_scout,
    run_paper_fetch,
)
from ui.services.config_store import (
    OUTPUTS_DIR,
    QUALITY_PROFILE_OPTIONS,
    RANKING_PROFILES,
    SOURCE_OPTIONS,
    TIME_RANGE_OPTIONS,
    add_interesting_paper,
    default_quality_for_task,
    ensure_project_layout,
    load_daily_profile,
    load_interesting_papers,
    load_user_preferences,
    save_daily_profile,
    time_range_key,
    update_user_preferences,
)
from ui.services.page_helpers import (
    format_quality_option,
    recall_prompt,
    remember_prompt,
    render_app_sidebar,
    render_bridge_response,
    render_codex_status_panel,
    render_loaded_result,
    render_page_header,
    render_path_expander,
    render_pdf_extraction_status,
    render_prompt_expander,
)
from ui.services.result_loader import list_recent_markdown, load_result
from ui.services.ui_text import expander_title, t, time_range_label


STATE_KEY = "top10_last_execution"

ensure_project_layout()
daily_profile = load_daily_profile()
interesting_payload = load_interesting_papers()
preferences = load_user_preferences()
language = preferences["language"]
global_defaults = preferences["global_defaults"]
task_defaults = preferences["task_defaults"]["literature_scout"]
interesting_keys = {
    f"{(item.get('paper_url') or '').strip().lower()}||{(item.get('title') or '').strip().lower()}"
    for item in interesting_payload["items"]
}
codex_status = detect_codex_cli(language=language)


def is_interesting(title: str, paper_url: str) -> bool:
    key = f"{paper_url.strip().lower()}||{title.strip().lower()}"
    return key in interesting_keys


render_app_sidebar("top10")
render_page_header("top10")
render_codex_status_panel(codex_status, expanded=False)

time_options = list(TIME_RANGE_OPTIONS.keys())
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_time = global_defaults.get("time_range_key") or time_range_key(daily_profile["time_range"])
default_sources = global_defaults.get("sources") or daily_profile["sources"]
default_constraints = (global_defaults.get("constraints") or {}).get("notes") or daily_profile.get("constraints", {}).get("notes", "")
default_quality = task_defaults.get("quality_profile") or daily_profile.get("quality_profile") or default_quality_for_task("literature_scout")

with st.form("top10_form"):
    field = st.text_input(t("common.field", language), value=global_defaults.get("field") or daily_profile["field"])
    selected_time = st.selectbox(
        t("common.time_range", language),
        options=time_options,
        index=time_options.index(default_time if default_time in time_options else "7d"),
        format_func=lambda item: time_range_label(TIME_RANGE_OPTIONS[item], language),
    )
    sources = st.multiselect(t("common.sources", language), options=SOURCE_OPTIONS, default=default_sources)
    ranking_profile = st.selectbox(
        t("common.ranking_profile", language),
        options=RANKING_PROFILES,
        index=RANKING_PROFILES.index(global_defaults.get("ranking_profile") or daily_profile["ranking_profile"]),
    )
    quality_profile = st.selectbox(
        t("common.quality_profile", language),
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="literature_scout"),
        help=t("top10.quality_help", language),
    )
    top_k = st.number_input(t("common.top_k", language), min_value=1, max_value=50, value=int(global_defaults.get("top_k") or daily_profile["top_k"]))
    with st.expander(expander_title("advanced_options", language), expanded=False):
        constraints = st.text_area(
            t("common.constraints", language),
            value=default_constraints,
            height=100,
            placeholder=t("top10.constraints_placeholder", language),
        )
        save_as_daily = st.checkbox(t("top10.save_as_daily", language), value=False)
    submitted = st.form_submit_button(t("top10.submit", language), use_container_width=True)

if submitted:
    source_values = sources or daily_profile["sources"]
    update_user_preferences(
        {
            "global_defaults": {
                "field": field,
                "time_range_key": selected_time,
                "sources": source_values,
                "ranking_profile": ranking_profile,
                "constraints": {
                    "compute": "",
                    "data": "",
                    "time": "",
                    "budget": "",
                    "notes": constraints,
                },
                "top_k": int(top_k),
            },
            "task_defaults": {
                "literature_scout": {
                    "quality_profile": quality_profile,
                }
            },
        }
    )
    if save_as_daily:
        save_daily_profile(
            {
                "field": field,
                "time_range": TIME_RANGE_OPTIONS[selected_time],
                "sources": source_values,
                "ranking_profile": ranking_profile,
                "quality_profile": quality_profile,
                "constraints": {
                    "compute": "",
                    "data": "",
                    "time": "",
                    "budget": "",
                    "notes": constraints,
                },
                "top_k": int(top_k),
                "language": language,
            }
        )
        st.success(t("top10.daily_saved", language))

    response = run_literature_scout(
        LiteratureScoutInput(
            field=field,
            time_range=TIME_RANGE_OPTIONS[selected_time],
            sources=source_values,
            ranking_profile=ranking_profile,
            constraints=constraints,
            top_k=int(top_k),
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
    render_prompt_expander(stored.get("prompt"))
    output_path = stored["response"].get("expected_output_path")
    if output_path and Path(output_path).exists():
        st.markdown(f"**{t('common.current_result', language)}**")
        render_loaded_result(load_result(Path(output_path)))

st.divider()
st.subheader(t("top10.recent_results_heading", language))
recent_results = list_recent_markdown(OUTPUTS_DIR / "daily_top10", limit=20)
if not recent_results:
    st.info(t("top10.no_results", language))
else:
    result_lookup = {path.name: path for path in recent_results}
    selected_result = st.selectbox(
        t("common.select_result_file", language),
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
    if loaded.metadata:
        st.markdown(f"**{t('common.execution_summary', language)}**")
        render_bridge_response(
            {
                "status": loaded.metadata.get("status", "success"),
                "message": t("common.history_loaded", language),
                "quality_profile": loaded.metadata.get("quality_profile"),
                "model": loaded.metadata.get("model"),
                "reasoning_effort": loaded.metadata.get("reasoning_effort"),
                "control_level": loaded.metadata.get("execution_mode"),
                "output_paths": loaded.metadata.get("output_paths") or {},
                "error": loaded.metadata.get("error"),
                "mode": loaded.metadata.get("execution_mode"),
            }
        )

    if loaded.table_rows:
        st.markdown(f"**{t('top10.top_k_list', language)}**")
        for index, row in enumerate(loaded.table_rows, start=1):
            rank = row.get("rank") or row.get("排名") or str(index)
            title = row.get("title") or row.get("论文") or f"Paper {index}"
            paper_url = row.get("paper_url", "")
            code_url = row.get("code_url", "")
            flagged = is_interesting(title, paper_url)
            expander_title_text = f"#{rank} {title}"
            if flagged:
                expander_title_text = f"{expander_title_text} | {t('top10.interest_suffix', language)}"
            with st.expander(expander_title_text, expanded=index <= 3):
                st.markdown(
                    "\n".join(
                        [
                            f"- {t('common.interesting_status', language)}: {t('common.marked', language) if flagged else t('common.unmarked', language)}",
                            f"- {t('common.paper_link', language)}: {paper_url or t('top10.not_parsed', language)}",
                            f"- {t('common.code_link', language)}: {code_url or t('top10.not_parsed', language)}",
                            f"- {t('common.why_relevant', language)}: {row.get('why_relevant') or row.get('相关性原因') or t('common.not_provided', language)}",
                            f"- {t('common.why_priority', language)}: {row.get('why_priority') or row.get('排名原因') or t('common.not_provided', language)}",
                            f"- {t('common.priority', language)}: {row.get('priority') or row.get('推荐优先级') or t('common.not_provided', language)}",
                        ]
                    )
                )
                interest_item = {
                    "title": title,
                    "paper_url": paper_url,
                    "code_url": code_url,
                    "source_result": str(selected_path),
                    "rank": rank,
                }
                col1, col2, col3 = st.columns(3)
                if col1.button(t("top10.mark_interesting", language), key=f"interest-{selected_path.name}-{index}", disabled=flagged):
                    added = add_interesting_paper(interest_item)
                    if added:
                        st.success(t("top10.interesting_saved", language))
                    else:
                        st.info(t("top10.already_interesting", language))
                if col2.button(t("top10.download_pdf", language), key=f"download-{selected_path.name}-{index}", disabled=not bool(paper_url)):
                    fetch_response = run_paper_fetch(
                        PaperFetcherInput(
                            reference=paper_url,
                            output_dir=OUTPUTS_DIR / "pdfs",
                            quality_profile="economy",
                            language=language,
                        )
                    )
                    render_bridge_response(fetch_response)
                    candidates = (fetch_response.payload or {}).get("candidates") or []
                    if fetch_response.status != "success" and candidates:
                        st.markdown(t("common.candidate_links", language))
                        st.markdown("\n".join(f"- {item}" for item in candidates))
                if col3.button(t("top10.download_and_read", language), key=f"download-read-{selected_path.name}-{index}", disabled=not bool(paper_url)):
                    pipeline = download_and_run_reader(
                        reference=paper_url,
                        quality_profile="economy",
                        reader_quality_profile="balanced",
                        output_dir=OUTPUTS_DIR / "pdfs",
                        language=language,
                    )
                    download_response = pipeline["download"]
                    reader_response = pipeline["reader"]
                    if download_response:
                        st.markdown(f"**{t('common.download_status', language)}**")
                        render_bridge_response(download_response)
                        candidates = (download_response.payload or {}).get("candidates") or []
                        if download_response.status != "success" and candidates:
                            st.markdown(t("common.candidate_links", language))
                            st.markdown("\n".join(f"- {item}" for item in candidates))
                    if reader_response:
                        st.markdown(f"**{t('common.read_status', language)}**")
                        render_bridge_response(reader_response)
                        render_pdf_extraction_status(reader_response.payload or {})
                        output_path = reader_response.expected_output_path
                        if output_path and output_path.exists():
                            st.markdown(f"**{t('top10.read_preview', language)}**")
                            render_loaded_result(load_result(output_path))
    render_loaded_result(loaded)
