from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import TopicMapperInput, detect_codex_cli, run_topic_mapper
from ui.services.config_store import (
    OUTPUTS_DIR,
    QUALITY_PROFILE_OPTIONS,
    RANKING_PROFILES,
    TIME_RANGE_OPTIONS,
    default_quality_for_task,
    ensure_project_layout,
)
from ui.services.page_helpers import (
    format_quality_option,
    recall_prompt,
    remember_prompt,
    render_bridge_response,
    render_codex_status,
    render_loaded_result,
    show_path,
)
from ui.services.result_loader import list_recent_markdown, load_result


STATE_KEY = "topic_mapper_last_execution"

ensure_project_layout()
codex_status = detect_codex_cli()
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = default_quality_for_task("topic_mapper")

st.title("方向论文地图")
st.caption("当前页面会真实触发本地 Codex CLI 执行，并将结果写入 `outputs/topic_maps/`。")
render_codex_status(codex_status)

with st.form("topic_mapper_form"):
    topic = st.text_area("方向描述", height=120, placeholder="例如：长视频叙事推理中的 evidence retrieval")
    time_range_key = st.selectbox(
        "时间窗口",
        options=list(TIME_RANGE_OPTIONS.keys()),
        index=2,
        format_func=lambda item: TIME_RANGE_OPTIONS[item]["label"],
    )
    cross_domain = st.checkbox("跨领域扩展", value=False)
    return_count = st.number_input("返回数量", min_value=5, max_value=60, value=15)
    ranking_mode = st.selectbox("排序方式", options=RANKING_PROFILES, index=0)
    quality_profile = st.selectbox(
        "执行质量档位",
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="topic_mapper"),
    )
    show_prompt = st.checkbox("展示本次执行 prompt", value=False)
    submitted = st.form_submit_button("执行论文地图", use_container_width=True)

if submitted:
    response = run_topic_mapper(
        TopicMapperInput(
            topic=topic,
            time_range=TIME_RANGE_OPTIONS[time_range_key],
            cross_domain=cross_domain,
            return_count=int(return_count),
            ranking_mode=ranking_mode,
            quality_profile=quality_profile,
        )
    )
    remember_prompt(
        STATE_KEY,
        {
            "response": response.to_dict(),
            "show_prompt": show_prompt,
            "prompt": response.prompt_text,
        },
    )

stored = recall_prompt(STATE_KEY)
if stored:
    st.subheader("本次执行状态")
    render_bridge_response(stored["response"])
    if stored.get("show_prompt") and stored.get("prompt"):
        st.code(stored["prompt"], language="markdown")
    output_path = stored["response"].get("expected_output_path")
    if output_path and Path(output_path).exists():
        render_loaded_result(load_result(Path(output_path)))

st.divider()
st.subheader("最近方向地图")
recent_results = list_recent_markdown(OUTPUTS_DIR / "topic_maps", limit=20)
if not recent_results:
    st.info("还没有 `outputs/topic_maps/` 结果。")
else:
    selected_result = st.selectbox("选择结果文件", options=recent_results, format_func=lambda path: path.name)
    loaded = load_result(selected_result)
    show_path("结果文件路径", selected_result)
    render_loaded_result(loaded)
