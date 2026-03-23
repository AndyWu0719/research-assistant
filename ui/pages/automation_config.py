from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st
import yaml

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.config_store import (
    AUTOMATION_CONFIG_PATH,
    DAILY_PROFILE_PATH,
    QUALITY_PROFILE_OPTIONS,
    RANKING_PROFILES,
    SOURCE_OPTIONS,
    TIME_RANGE_OPTIONS,
    ensure_project_layout,
    load_automation_config,
    load_daily_profile,
    load_execution_profiles,
    resolve_quality_profile,
    save_automation_config,
    save_daily_profile,
    time_range_key,
)
from ui.services.page_helpers import format_quality_option, show_path
from ui.services.prompt_builder import build_daily_automation_prompt


ensure_project_layout()
daily_profile = load_daily_profile()
automation_config = load_automation_config()
execution_profiles = load_execution_profiles()

st.title("自动化配置")
st.caption("当前页面会真实写入配置文件，并保留 `读取 daily_profile.yaml 执行` 这条 automation 主逻辑。模型与 reasoning effort 仍需在 Codex app automation 界面按推荐手动选择。")

quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = automation_config.get("quality_profile", "balanced")

with st.form("automation_form"):
    task_name = st.text_input("任务名称", value=automation_config["task_name"])
    field = st.text_input("研究领域", value=automation_config["field"])
    time_key = st.selectbox(
        "时间范围",
        options=list(TIME_RANGE_OPTIONS.keys()),
        index=list(TIME_RANGE_OPTIONS.keys()).index(time_range_key(automation_config["time_range"])),
        format_func=lambda item: TIME_RANGE_OPTIONS[item]["label"],
    )
    sources = st.multiselect("来源范围", options=SOURCE_OPTIONS, default=automation_config["sources"])
    ranking_profile = st.selectbox(
        "排序 profile",
        options=RANKING_PROFILES,
        index=RANKING_PROFILES.index(automation_config["ranking_profile"]),
    )
    quality_profile = st.selectbox(
        "执行质量档位",
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="automation"),
        help="daily_top10 建议用 balanced；只做轻量巡检时可用 economy。不要默认用 max-analysis。",
    )
    constraints = st.text_area(
        "约束",
        value=automation_config.get("constraints", {}).get("notes", ""),
        height=100,
    )
    top_k = st.number_input("Top K", min_value=1, max_value=50, value=int(automation_config["top_k"]))
    run_time = st.text_input("每天运行时间", value=automation_config["schedule"]["time_of_day"])
    enabled = st.checkbox("是否启用", value=bool(automation_config["enabled"]))
    auto_download_interesting = st.checkbox(
        "是否自动下载“已标记感兴趣”的论文",
        value=bool(automation_config["auto_download_interesting"]),
    )
    submitted = st.form_submit_button("保存自动化配置", use_container_width=True)

if submitted:
    time_range = TIME_RANGE_OPTIONS[time_key]
    daily_payload = {
        "field": field,
        "time_range": time_range,
        "sources": sources or ["arXiv", "OpenReview"],
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
    }
    automation_payload = {
        "task_name": task_name,
        "field": field,
        "time_range": time_range,
        "sources": sources or ["arXiv", "OpenReview"],
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
    }
    save_daily_profile(daily_payload)
    save_automation_config(automation_payload)
    daily_profile = load_daily_profile()
    automation_config = load_automation_config()
    st.success("配置已写入。")

automation_prompt = build_daily_automation_prompt(automation_config)
automation_quality = resolve_quality_profile(automation_config.get("quality_profile"), task_type="automation")

col1, col2 = st.columns(2)
with col1:
    st.subheader("当前配置摘要")
    st.markdown(
        "\n".join(
            [
                f"- 任务名称: `{automation_config['task_name']}`",
                f"- 研究领域: `{automation_config['field']}`",
                f"- 时间范围: `{automation_config['time_range']['label']}`",
                f"- 来源范围: `{', '.join(automation_config['sources'])}`",
                f"- 排序 profile: `{automation_config['ranking_profile']}`",
                f"- 质量档位: `{automation_config['quality_profile']}`",
                f"- 推荐模型: `{automation_quality['model']}`",
                f"- 推荐 reasoning effort: `{automation_quality['reasoning_effort']}`",
                f"- 每天运行时间: `{automation_config['schedule']['time_of_day']}`",
                f"- 自动下载感兴趣论文: `{automation_config['auto_download_interesting']}`",
            ]
        )
    )
    show_path("daily profile", DAILY_PROFILE_PATH)
    show_path("automation config", AUTOMATION_CONFIG_PATH)
with col2:
    st.subheader("质量档位建议")
    st.markdown(
        "\n".join(
            [
                f"- `daily_top10`: {execution_profiles['recommendations']['daily_top10']}",
                f"- `paper_reader`: {execution_profiles['recommendations']['paper_reader']}",
                f"- 深度分析: {execution_profiles['recommendations']['deep_reports']}",
                f"- 自动化: {execution_profiles['recommendations']['automation']}",
                "- 重要说明: 这里的档位会写入配置并体现在 automation prompt 中，但 Codex app automation 的实际 model / reasoning 需要你在创建 automation 时手动设置。",
            ]
        )
    )

st.subheader("固定 Automation Prompt")
st.code(automation_prompt, language="markdown")

st.subheader("配置预览")
preview_left, preview_right = st.columns(2)
with preview_left:
    st.markdown("**`configs/daily_profile.yaml`**")
    st.code(yaml.safe_dump(daily_profile, allow_unicode=True, sort_keys=False), language="yaml")
with preview_right:
    st.markdown("**`configs/automations/daily_top10.yaml`**")
    st.code(yaml.safe_dump(automation_config, allow_unicode=True, sort_keys=False), language="yaml")
