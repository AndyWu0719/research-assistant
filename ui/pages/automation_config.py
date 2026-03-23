from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.config_store import (
    DAILY_PROFILE_PATH,
    QUALITY_PROFILE_OPTIONS,
    RANKING_PROFILES,
    SOURCE_OPTIONS,
    TIME_RANGE_OPTIONS,
    current_automation_config_path,
    describe_automation_storage,
    ensure_project_layout,
    load_automation_config,
    load_daily_profile,
    load_user_preferences,
    resolve_quality_profile,
    save_automation_config,
    save_daily_profile,
    time_range_key,
    update_user_preferences,
)
from ui.services.language import LANGUAGE_OPTIONS
from ui.services.page_helpers import format_quality_option, render_app_sidebar, render_page_header, render_path_expander
from ui.services.prompt_builder import build_daily_automation_prompt
from ui.services.ui_text import expander_title, language_option_label, t, time_range_label


ensure_project_layout()
daily_profile = load_daily_profile()
automation_config = load_automation_config()
preferences = load_user_preferences()
language = preferences["language"]
active_path = current_automation_config_path()

render_app_sidebar("automation_config")
render_page_header("automation_config")

quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = automation_config.get("quality_profile", preferences["task_defaults"]["automation"]["quality_profile"])
default_language = preferences.get("language")
language_display_to_code = {language_option_label(code, language): code for code in LANGUAGE_OPTIONS.keys()}
language_display_options = list(language_display_to_code.keys())
default_language_display = language_option_label(default_language, language)

with st.form("automation_form"):
    task_name = st.text_input(t("automation_config.task_name", language), value=automation_config["task_name"])
    field = st.text_input(t("common.field", language), value=automation_config["field"])
    time_key = st.selectbox(
        t("common.time_range", language),
        options=list(TIME_RANGE_OPTIONS.keys()),
        index=list(TIME_RANGE_OPTIONS.keys()).index(time_range_key(automation_config["time_range"])),
        format_func=lambda item: time_range_label(TIME_RANGE_OPTIONS[item], language),
    )
    sources = st.multiselect(t("common.sources", language), options=SOURCE_OPTIONS, default=automation_config["sources"])
    ranking_profile = st.selectbox(
        t("common.ranking_profile", language),
        options=RANKING_PROFILES,
        index=RANKING_PROFILES.index(automation_config["ranking_profile"]),
    )
    quality_profile = st.selectbox(
        t("common.quality_profile", language),
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="automation"),
        help=t("automation_config.quality_help", language),
    )
    selected_output_language_display = st.selectbox(
        t("automation_config.language", language),
        options=language_display_options,
        index=language_display_options.index(default_language_display),
    )
    output_language = language_display_to_code[selected_output_language_display]
    top_k = st.number_input(t("common.top_k", language), min_value=1, max_value=50, value=int(automation_config["top_k"]))
    run_time = st.text_input(t("automation_config.run_time", language), value=automation_config["schedule"]["time_of_day"])
    auto_download_interesting = st.checkbox(
        t("automation_config.auto_download_interesting", language),
        value=bool(automation_config["auto_download_interesting"]),
    )
    with st.expander(expander_title("advanced_options", language), expanded=False):
        constraints = st.text_area(
            t("common.constraints", language),
            value=automation_config.get("constraints", {}).get("notes", ""),
            height=100,
        )
        enabled = st.checkbox(t("automation_config.enabled", language), value=bool(automation_config["enabled"]))
    preview_storage = describe_automation_storage(task_name)
    st.markdown(
        "\n".join(
            [
                f"- {t('automation_config.preview_task_name', language)}: `{task_name}`",
                f"- {t('automation_config.preview_filename', language)}: `{preview_storage['filename']}`",
                f"- {t('automation_config.preview_directory', language)}: `{preview_storage['directory']}`",
            ]
        )
    )
    submitted = st.form_submit_button(t("automation_config.submit", language), use_container_width=True)

time_range = TIME_RANGE_OPTIONS[time_key]
source_values = sources or ["arXiv", "OpenReview"]
daily_payload = {
    "field": field,
    "time_range": time_range,
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
    "language": output_language,
}
preview_automation_payload = {
    "task_name": task_name,
    "field": field,
    "time_range": time_range,
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
    "schedule": {
        "timezone": "Asia/Hong_Kong",
        "time_of_day": run_time,
        "cadence": "daily",
    },
    "enabled": enabled,
    "auto_download_interesting": auto_download_interesting,
    "generated_prompt_target": "Codex app Automations",
    "language": output_language,
}

if submitted:
    save_daily_profile(daily_payload)
    saved_path = save_automation_config(preview_automation_payload)
    update_user_preferences(
        {
            "language": output_language,
            "global_defaults": {
                "field": field,
                "time_range_key": time_key,
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
                "automation": {
                    "quality_profile": quality_profile,
                    "run_time": run_time,
                    "auto_download_interesting": auto_download_interesting,
                }
            },
            "active_automation": {
                "task_name": task_name,
                "filename": saved_path.name,
            },
        }
    )
    daily_profile = load_daily_profile()
    automation_config = load_automation_config()
    preferences = load_user_preferences()
    language = preferences["language"]
    active_path = current_automation_config_path()
    preview_storage = describe_automation_storage(task_name, path=active_path)
    st.success(t("automation_config.saved", language))

automation_prompt = build_daily_automation_prompt(preview_automation_payload)
automation_quality = resolve_quality_profile(preview_automation_payload.get("quality_profile"), task_type="automation")
storage = describe_automation_storage(preview_automation_payload["task_name"], path=active_path if submitted else None)

col1, col2 = st.columns(2)
with col1:
    st.subheader(t("automation_config.summary_heading", language))
    st.markdown(
        "\n".join(
            [
                f"- {t('automation_config.task_name', language)}: `{preview_automation_payload['task_name']}`",
                f"- {t('common.field', language)}: `{preview_automation_payload['field']}`",
                f"- {t('common.time_range', language)}: `{time_range_label(preview_automation_payload['time_range'], language)}`",
                f"- {t('common.sources', language)}: `{', '.join(preview_automation_payload['sources'])}`",
                f"- {t('common.ranking_profile', language)}: `{preview_automation_payload['ranking_profile']}`",
                f"- {t('common.language_display', language)}: `{language_option_label(preview_automation_payload.get('language', language), language)}`",
                f"- {t('common.quality_profile', language)}: `{preview_automation_payload['quality_profile']}`",
                f"- {t('common.recommended_model', language)}: `{automation_quality['model']}`",
                f"- {t('common.recommended_reasoning', language)}: `{automation_quality['reasoning_effort']}`",
                f"- {t('automation_config.run_time', language)}: `{preview_automation_payload['schedule']['time_of_day']}`",
                f"- {t('automation_config.auto_download_interesting', language)}: `{preview_automation_payload['auto_download_interesting']}`",
            ]
        )
    )
    render_path_expander(
        expander_title("paths_and_storage", language),
        {
            "daily profile": DAILY_PROFILE_PATH,
            "automation config": storage["path"],
            "filename": storage["filename"],
            "directory": storage["directory"],
        },
        expanded=False,
    )
with col2:
    st.subheader(t("automation_config.quality_heading", language))
    if language == "en-US":
        recommendations = [
            "- Daily Top 10: start with balanced, and drop to economy for lighter scans.",
            "- Paper Reader: balanced is enough for most reads; use high-accuracy only for important papers.",
            "- Deep Reports: topic maps and feasibility analysis should move up only when balanced is not enough.",
            "- Automation: avoid using max-analysis as the default for recurring runs.",
            f"- {t('automation_config.important_note', language)}",
        ]
    else:
        recommendations = [
            "- `daily_top10`: 建议优先 balanced；若只做轻量巡检可改 economy。",
            "- `paper_reader`: 常规精读建议 balanced；重要论文深读再切到 high-accuracy。",
            "- 深度分析: 方向地图、可行性分析只有在 balanced 不够时再提高档位。",
            "- 自动化: 每日自动化默认不要用 max-analysis，避免持续高成本运行。",
            f"- {t('automation_config.important_note', language)}",
        ]
    st.markdown("\n".join(recommendations))

with st.expander(t("automation_config.automation_prompt", language), expanded=False):
    st.code(automation_prompt, language="markdown")

with st.expander(expander_title("config_preview", language), expanded=False):
    preview_left, preview_right = st.columns(2)
    with preview_left:
        st.markdown(f"**{t('automation_config.daily_profile_preview', language)}**")
        st.code(yaml.safe_dump(daily_payload, allow_unicode=True, sort_keys=False), language="yaml")
    with preview_right:
        st.markdown(f"**`{Path(storage['path']).relative_to(ROOT)}`**")
        st.code(yaml.safe_dump(preview_automation_payload, allow_unicode=True, sort_keys=False), language="yaml")
