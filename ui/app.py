from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import capability_matrix, detect_codex_cli
from ui.services.config_store import (
    AUTOMATION_CONFIG_PATH,
    DAILY_PROFILE_PATH,
    EXECUTION_PROFILES_PATH,
    INTERESTING_PAPERS_PATH,
    OUTPUTS_DIR,
    ensure_project_layout,
    load_automation_config,
    load_daily_profile,
    load_interesting_papers,
    resolve_quality_profile,
)
from ui.services.page_helpers import render_codex_status
from ui.services.result_loader import list_recent_markdown


st.set_page_config(
    page_title="本地网页版研究助手",
    layout="wide",
    initial_sidebar_state="expanded",
)

ensure_project_layout()

daily_profile = load_daily_profile()
automation_config = load_automation_config()
interesting_papers = load_interesting_papers()
codex_status = detect_codex_cli()
daily_quality = resolve_quality_profile(daily_profile.get("quality_profile"), task_type="literature_scout")

st.title("本地网页版研究助手")
st.caption("默认运行模式：网页负责表单与展示，本地 Codex CLI 负责实际执行，Codex app 继续负责 Automations。")

st.markdown(
    """
**当前阶段说明**

- Top10 文献巡检、单篇论文精读、方向论文地图、想法可行性分析、资源受限探索现在优先走 `网页 -> 本地 Codex CLI -> outputs 回写`。
- `paper-fetcher` 继续使用本地脚本真实下载 PDF；`下载并精读` 会在下载成功后串到 `paper-reader`。
- `Automations` 页面会保存质量档位推荐，但 Codex app automation 的实际 model / reasoning 仍需你在 App 里手动选择，或由本地默认配置决定。
"""
)

st.subheader("本地执行环境")
render_codex_status(codex_status)

left, right = st.columns([1.2, 1])
with left:
    st.subheader("快速入口")
    st.page_link("app.py", label="首页")
    st.page_link("pages/top10.py", label="Top 10 文献巡检")
    st.page_link("pages/paper_reader.py", label="单篇论文精读")
    st.page_link("pages/topic_mapper.py", label="方向论文地图")
    st.page_link("pages/idea_feasibility.py", label="想法可行性分析")
    st.page_link("pages/constraint_explorer.py", label="资源受限探索")
    st.page_link("pages/pdf_fetcher.py", label="PDF 下载")
    st.page_link("pages/automation_config.py", label="自动化配置")

with right:
    st.subheader("默认配置")
    st.markdown(
        "\n".join(
            [
                f"- 研究领域: `{daily_profile['field']}`",
                f"- 时间范围: `{daily_profile['time_range']['label']}`",
                f"- 来源范围: `{', '.join(daily_profile['sources'])}`",
                f"- 排序 profile: `{daily_profile['ranking_profile']}`",
                f"- 质量档位: `{daily_profile['quality_profile']}`",
                f"- 映射模型: `{daily_quality['model']}`",
                f"- 映射 reasoning effort: `{daily_quality['reasoning_effort']}`",
                f"- Top K: `{daily_profile['top_k']}`",
                f"- 自动化时间: `{automation_config['schedule']['time_of_day']}`",
                f"- 已标记感兴趣论文数: `{len(interesting_papers['items'])}`",
            ]
        )
    )

st.subheader("能力状态")
for item in capability_matrix():
    with st.expander(f"{item['能力']} | {item['状态']}", expanded=item["状态"] == "已打通"):
        st.write(item["说明"])

st.subheader("最近产物")
recent_top10 = list_recent_markdown(OUTPUTS_DIR / "daily_top10", limit=5)
recent_summaries = list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=5)
recent_maps = list_recent_markdown(OUTPUTS_DIR / "topic_maps", limit=5)
recent_feasibility = list_recent_markdown(OUTPUTS_DIR / "feasibility_reports", limit=5)

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.markdown("**Top10 榜单**")
    if recent_top10:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_top10))
    else:
        st.info("还没有 Top10 结果。")
with col2:
    st.markdown("**论文精读**")
    if recent_summaries:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_summaries))
    else:
        st.info("还没有精读结果。")
with col3:
    st.markdown("**方向地图**")
    if recent_maps:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_maps))
    else:
        st.info("还没有方向地图结果。")
with col4:
    st.markdown("**可行性报告**")
    if recent_feasibility:
        st.markdown("\n".join(f"- `{path.name}`" for path in recent_feasibility))
    else:
        st.info("还没有可行性报告。")

st.subheader("关键配置文件")
st.markdown(
    "\n".join(
        [
            f"- `daily profile`: `{DAILY_PROFILE_PATH}`",
            f"- `automation config`: `{AUTOMATION_CONFIG_PATH}`",
            f"- `execution profiles`: `{EXECUTION_PROFILES_PATH}`",
            f"- `interesting papers`: `{INTERESTING_PAPERS_PATH}`",
        ]
    )
)
