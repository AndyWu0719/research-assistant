from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import IdeaFeasibilityInput, detect_codex_cli, run_idea_feasibility
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
from ui.services.ui_text import RISK_PREFERENCE_OPTIONS, expander_title, risk_preference_label, t


STATE_KEY = "idea_feasibility_last_execution"

ensure_project_layout()
preferences = load_user_preferences()
language = preferences["language"]
task_defaults = preferences["task_defaults"]["idea_feasibility"]
codex_status = detect_codex_cli(language=language)
quality_options = list(QUALITY_PROFILE_OPTIONS)

render_app_sidebar("idea_feasibility")
render_page_header("idea_feasibility")
render_codex_status_panel(codex_status, expanded=False)

with st.form("idea_feasibility_form"):
    idea = st.text_area(t("idea_feasibility.idea", language), height=150)
    target_field = st.text_input(t("idea_feasibility.target_field", language), placeholder=t("idea_feasibility.target_field_placeholder", language))
    quality_profile = st.selectbox(
        t("common.quality_profile", language),
        options=quality_options,
        index=quality_options.index(task_defaults.get("quality_profile", "balanced")),
        format_func=lambda item: format_quality_option(item, task_type="idea_feasibility"),
    )
    with st.expander(expander_title("advanced_options", language), expanded=False):
        compute_budget = st.text_input(t("idea_feasibility.compute_budget", language), value=task_defaults.get("compute_budget", "单卡 24G"))
        data_budget = st.text_input(t("idea_feasibility.data_budget", language), value=task_defaults.get("data_budget", "优先公开数据"))
        risk_preference = st.selectbox(
            t("idea_feasibility.risk_preference", language),
            options=RISK_PREFERENCE_OPTIONS,
            index=RISK_PREFERENCE_OPTIONS.index(task_defaults.get("risk_preference", "balanced")),
            format_func=lambda item: risk_preference_label(item, language),
        )
        prefer_low_cost_validation = st.checkbox(t("idea_feasibility.prefer_low_cost_validation", language), value=bool(task_defaults.get("prefer_low_cost_validation", True)))
    submitted = st.form_submit_button(t("idea_feasibility.submit", language), use_container_width=True)

if submitted:
    update_user_preferences(
        {
            "task_defaults": {
                "idea_feasibility": {
                    "quality_profile": quality_profile,
                    "compute_budget": compute_budget,
                    "data_budget": data_budget,
                    "risk_preference": risk_preference,
                    "prefer_low_cost_validation": prefer_low_cost_validation,
                }
            }
        }
    )
    response = run_idea_feasibility(
        IdeaFeasibilityInput(
            idea=idea,
            target_field=target_field,
            compute_budget=compute_budget,
            data_budget=data_budget,
            risk_preference=risk_preference,
            prefer_low_cost_validation=prefer_low_cost_validation,
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
st.subheader(t("idea_feasibility.recent_results_heading", language))
recent_results = list_recent_markdown(OUTPUTS_DIR / "feasibility_reports", limit=20)
if not recent_results:
    st.info(t("idea_feasibility.no_results", language))
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
