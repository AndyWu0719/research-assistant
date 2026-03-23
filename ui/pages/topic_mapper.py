from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import TopicMapperInput, detect_codex_cli, run_topic_mapper
from ui.services.config_store import OUTPUTS_DIR, QUALITY_PROFILE_OPTIONS, RANKING_PROFILES, TIME_RANGE_OPTIONS, ensure_project_layout, load_user_preferences, update_user_preferences
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
    render_prompt_expander,
)
from ui.services.result_loader import list_recent_markdown, load_result
from ui.services.ui_text import expander_title, t, time_range_label


STATE_KEY = "topic_mapper_last_execution"

ensure_project_layout()
preferences = load_user_preferences()
language = preferences["language"]
task_defaults = preferences["task_defaults"]["topic_mapper"]
codex_status = detect_codex_cli(language=language)
quality_options = list(QUALITY_PROFILE_OPTIONS)

render_app_sidebar("topic_mapper")
render_page_header("topic_mapper")
render_codex_status_panel(codex_status, expanded=False)

with st.form("topic_mapper_form"):
    topic = st.text_area(t("topic_mapper.topic", language), height=120, placeholder=t("topic_mapper.topic_placeholder", language))
    time_range_key = st.selectbox(
        t("common.time_window", language),
        options=list(TIME_RANGE_OPTIONS.keys()),
        index=list(TIME_RANGE_OPTIONS.keys()).index(task_defaults.get("time_range_key", "30d")),
        format_func=lambda item: time_range_label(TIME_RANGE_OPTIONS[item], language),
    )
    quality_profile = st.selectbox(
        t("common.quality_profile", language),
        options=quality_options,
        index=quality_options.index(task_defaults.get("quality_profile", "balanced")),
        format_func=lambda item: format_quality_option(item, task_type="topic_mapper"),
        help=t("topic_mapper.quality_help", language),
    )
    with st.expander(expander_title("advanced_options", language), expanded=False):
        cross_domain = st.checkbox(t("topic_mapper.cross_domain", language), value=bool(task_defaults.get("cross_domain", False)))
        return_count = st.number_input(t("topic_mapper.return_count", language), min_value=5, max_value=60, value=int(task_defaults.get("return_count", 15)))
        ranking_mode = st.selectbox(t("topic_mapper.ranking_mode", language), options=RANKING_PROFILES, index=RANKING_PROFILES.index(task_defaults.get("ranking_mode", "balanced-default")))
    submitted = st.form_submit_button(t("topic_mapper.submit", language), use_container_width=True)

if submitted:
    update_user_preferences(
        {
            "task_defaults": {
                "topic_mapper": {
                    "quality_profile": quality_profile,
                    "time_range_key": time_range_key,
                    "cross_domain": cross_domain,
                    "return_count": int(return_count),
                    "ranking_mode": ranking_mode,
                }
            }
        }
    )
    response = run_topic_mapper(
        TopicMapperInput(
            topic=topic,
            time_range=TIME_RANGE_OPTIONS[time_range_key],
            cross_domain=cross_domain,
            return_count=int(return_count),
            ranking_mode=ranking_mode,
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
        render_loaded_result(load_result(Path(output_path)))

st.divider()
st.subheader(t("topic_mapper.recent_results_heading", language))
recent_results = list_recent_markdown(OUTPUTS_DIR / "topic_maps", limit=20)
if not recent_results:
    st.info(t("topic_mapper.no_results", language))
else:
    result_lookup = {path.name: path for path in recent_results}
    selected_result = st.selectbox(t("common.select_result_file", language), options=list(result_lookup.keys()))
    selected_path = result_lookup[selected_result]
    loaded = load_result(selected_path)
    render_path_expander(
        t("common.output_and_paths", language),
        {
            t("common.result_file", language): selected_path,
            t("common.json_sidecar", language): selected_path.with_suffix(".json"),
        },
    )
    render_loaded_result(loaded)
