from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import ConstraintExplorerInput, detect_codex_cli, run_constraint_explorer
from ui.services.config_store import OUTPUTS_DIR, QUALITY_PROFILE_OPTIONS, ensure_project_layout, load_user_preferences, update_user_preferences
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
from ui.services.ui_text import expander_title, t


STATE_KEY = "constraint_explorer_last_execution"

ensure_project_layout()
preferences = load_user_preferences()
language = preferences["language"]
task_defaults = preferences["task_defaults"]["constraint_explorer"]
codex_status = detect_codex_cli(language=language)
quality_options = list(QUALITY_PROFILE_OPTIONS)

render_app_sidebar("constraint_explorer")
render_page_header("constraint_explorer")
render_codex_status_panel(codex_status, expanded=False)

with st.form("constraint_explorer_form"):
    field = st.text_input(t("common.field", language), placeholder=t("constraint_explorer.field_placeholder", language))
    compute_limit = st.text_input(t("constraint_explorer.compute_limit", language), value=task_defaults.get("compute_limit", "单卡 24G"))
    data_limit = st.text_input(t("constraint_explorer.data_limit", language), value=task_defaults.get("data_limit", "优先公开数据或可替代小规模数据"))
    quality_profile = st.selectbox(
        t("common.quality_profile", language),
        options=quality_options,
        index=quality_options.index(task_defaults.get("quality_profile", "balanced")),
        format_func=lambda item: format_quality_option(item, task_type="constraint_explorer"),
    )
    with st.expander(expander_title("advanced_options", language), expanded=False):
        prefer_reproduction = st.checkbox(t("constraint_explorer.prefer_reproduction", language), value=bool(task_defaults.get("prefer_reproduction", True)))
        prefer_open_source = st.checkbox(t("constraint_explorer.prefer_open_source", language), value=bool(task_defaults.get("prefer_open_source", True)))
    submitted = st.form_submit_button(t("constraint_explorer.submit", language), use_container_width=True)

if submitted:
    update_user_preferences(
        {
            "task_defaults": {
                "constraint_explorer": {
                    "quality_profile": quality_profile,
                    "compute_limit": compute_limit,
                    "data_limit": data_limit,
                    "prefer_reproduction": prefer_reproduction,
                    "prefer_open_source": prefer_open_source,
                }
            }
        }
    )
    response = run_constraint_explorer(
        ConstraintExplorerInput(
            field=field,
            compute_limit=compute_limit,
            data_limit=data_limit,
            prefer_reproduction=prefer_reproduction,
            prefer_open_source=prefer_open_source,
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
st.subheader(t("constraint_explorer.recent_results_heading", language))
recent_results = list_recent_markdown(OUTPUTS_DIR / "constraint_reports", limit=20)
if not recent_results:
    st.info(t("constraint_explorer.no_results", language))
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
