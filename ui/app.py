from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import capability_matrix, detect_codex_cli
from ui.services.config_store import (
    DAILY_PROFILE_PATH,
    EXECUTION_PROFILES_PATH,
    INTERESTING_PAPERS_PATH,
    OUTPUTS_DIR,
    USER_PREFERENCES_PATH,
    current_automation_config_path,
    ensure_project_layout,
    load_automation_config,
    load_daily_profile,
    load_interesting_papers,
    load_user_preferences,
    resolve_quality_profile,
)
from ui.services.page_helpers import render_app_sidebar, render_codex_status, render_page_header, render_path_expander
from ui.services.result_loader import list_recent_markdown
from ui.services.ui_text import (
    home_feature_overview,
    home_parameter_glossary,
    language_option_label,
    page_copy,
    t,
    time_range_label,
)


ensure_project_layout()
user_preferences = load_user_preferences()
app_language = user_preferences["language"]

st.set_page_config(
    page_title=page_copy("home", app_language)["title"],
    layout="wide",
    initial_sidebar_state="expanded",
)

daily_profile = load_daily_profile()
automation_config = load_automation_config()
interesting_papers = load_interesting_papers()
codex_status = detect_codex_cli(language=app_language)
daily_quality = resolve_quality_profile(daily_profile.get("quality_profile"), task_type="literature_scout")
automation_path = current_automation_config_path()

render_app_sidebar("home")
render_page_header("home")

st.markdown(f"**{t('home.project_heading', app_language)}**")
st.markdown("\n".join(f"- {item}" for item in t("home.project_points", app_language)))

left, right = st.columns([1.2, 1])
with left:
    st.subheader(t("home.feature_heading", app_language))
    for title, summary in home_feature_overview(app_language):
        st.markdown(f"- **{title}**: {summary}")

    st.subheader(t("home.recommended_paths_heading", app_language))
    if app_language == "en-US":
        path_text = (
            "Beginner Path\n"
            "  Home -> PDF Downloads -> Paper Deep Read -> Top 10 Literature Scan\n\n"
            "Advanced User Path\n"
            "  Top 10 Literature Scan -> Topic Map -> Idea Feasibility -> Constraint Explorer -> Automation Setup"
        )
    else:
        path_text = (
            "新手路径\n"
            "  Home -> PDF Downloads -> Paper Deep Read -> Top 10 Literature Scan\n\n"
            "高级用户路径\n"
            "  Top 10 Literature Scan -> Topic Map -> Idea Feasibility -> Constraint Explorer -> Automation Setup"
        )
    st.code(path_text, language="text")

with right:
    st.subheader(t("home.defaults_heading", app_language))
    st.markdown(
        "\n".join(
            [
                f"- {t('common.field', app_language)}: `{daily_profile['field']}`",
                f"- {t('common.time_range', app_language)}: `{time_range_label(daily_profile['time_range'], app_language)}`",
                f"- {t('common.sources', app_language)}: `{', '.join(daily_profile['sources'])}`",
                f"- {t('common.ranking_profile', app_language)}: `{daily_profile['ranking_profile']}`",
                f"- {t('common.quality_profile', app_language)}: `{daily_profile['quality_profile']}`",
                f"- {t('common.recommended_model', app_language)}: `{daily_quality['model']}`",
                f"- {t('common.recommended_reasoning', app_language)}: `{daily_quality['reasoning_effort']}`",
                f"- {t('common.top_k', app_language)}: `{daily_profile['top_k']}`",
                f"- {t('common.language_display', app_language)}: `{language_option_label(user_preferences['language'], app_language)}`",
                f"- {'Daily Runtime' if app_language == 'en-US' else '自动化时间'}: `{automation_config['schedule']['time_of_day']}`",
                f"- {'Interesting Papers Marked' if app_language == 'en-US' else '已标记感兴趣论文数'}: `{len(interesting_papers['items'])}`",
            ]
        )
    )

st.subheader(t("home.parameters_heading", app_language))
field_key = t("home.parameter_field", app_language)
desc_key = t("home.parameter_description", app_language)
st.table([{field_key: name, desc_key: description} for name, description in home_parameter_glossary(app_language)])

st.subheader(t("home.automation_pdf_heading", app_language))
st.markdown("\n".join(f"- {item}" for item in t("home.automation_pdf_points", app_language)))

st.subheader(t("home.environment_heading", app_language))
render_codex_status(codex_status)

st.subheader(t("home.capability_heading", app_language))
for item in capability_matrix(app_language):
    with st.expander(f"{item['label']} | {item['status']}", expanded=item["status"] in {"已打通", "Ready"}):
        st.write(item["description"])

st.subheader(t("home.recent_outputs_heading", app_language))
recent_top10 = list_recent_markdown(OUTPUTS_DIR / "daily_top10", limit=5)
recent_summaries = list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=5)
recent_maps = list_recent_markdown(OUTPUTS_DIR / "topic_maps", limit=5)
recent_feasibility = list_recent_markdown(OUTPUTS_DIR / "feasibility_reports", limit=5)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown(f"**{t('home.top10_card', app_language)}**")
    if recent_top10:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_top10))
    else:
        st.info(t("home.no_top10", app_language))
with col2:
    st.markdown(f"**{t('home.summary_card', app_language)}**")
    if recent_summaries:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_summaries))
    else:
        st.info(t("home.no_summary", app_language))
with col3:
    st.markdown(f"**{t('home.map_card', app_language)}**")
    if recent_maps:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_maps))
    else:
        st.info(t("home.no_map", app_language))
with col4:
    st.markdown(f"**{t('home.feasibility_card', app_language)}**")
    if recent_feasibility:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_feasibility))
    else:
        st.info(t("home.no_feasibility", app_language))

render_path_expander(
    t("home.paths_heading", app_language),
    {
        "daily profile": DAILY_PROFILE_PATH,
        "active automation config": automation_path,
        "execution profiles": EXECUTION_PROFILES_PATH,
        "interesting papers": INTERESTING_PAPERS_PATH,
        "user preferences": USER_PREFERENCES_PATH,
    },
)
