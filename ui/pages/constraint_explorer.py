from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import ConstraintExplorerInput, detect_codex_cli, run_constraint_explorer
from ui.services.config_store import (
    OUTPUTS_DIR,
    QUALITY_PROFILE_OPTIONS,
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


STATE_KEY = "constraint_explorer_last_execution"

ensure_project_layout()
codex_status = detect_codex_cli()
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = default_quality_for_task("constraint_explorer")

st.title("资源受限探索")
st.caption("当前页面会真实触发本地 Codex CLI 执行，并将结果写入 `outputs/constraint_reports/`。")
render_codex_status(codex_status)

with st.form("constraint_explorer_form"):
    field = st.text_input("研究领域", placeholder="例如：多模态长上下文、低资源语音建模")
    compute_limit = st.text_input("算力限制", value="单卡 24G")
    data_limit = st.text_input("数据限制", value="优先公开数据或可替代小规模数据")
    prefer_reproduction = st.checkbox("优先复现", value=True)
    prefer_open_source = st.checkbox("优先开源", value=True)
    quality_profile = st.selectbox(
        "执行质量档位",
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="constraint_explorer"),
    )
    show_prompt = st.checkbox("展示本次执行 prompt", value=False)
    submitted = st.form_submit_button("执行资源受限探索", use_container_width=True)

if submitted:
    response = run_constraint_explorer(
        ConstraintExplorerInput(
            field=field,
            compute_limit=compute_limit,
            data_limit=data_limit,
            prefer_reproduction=prefer_reproduction,
            prefer_open_source=prefer_open_source,
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
st.subheader("最近资源受限报告")
recent_results = list_recent_markdown(OUTPUTS_DIR / "constraint_reports", limit=20)
if not recent_results:
    st.info("还没有 `outputs/constraint_reports/` 结果。")
else:
    selected_result = st.selectbox("选择结果文件", options=recent_results, format_func=lambda path: path.name)
    loaded = load_result(selected_result)
    show_path("结果文件路径", selected_result)
    render_loaded_result(loaded)
