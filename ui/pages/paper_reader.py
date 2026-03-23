from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import PaperReaderInput, detect_codex_cli, run_paper_reader
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
    render_named_sections,
    show_path,
)
from ui.services.result_loader import list_recent_markdown, load_result


STATE_KEY = "paper_reader_last_execution"

ensure_project_layout()
codex_status = detect_codex_cli()
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = default_quality_for_task("paper_reader")

st.title("单篇论文精读")
st.caption("支持链接 / arXiv ID / DOI / 本地 PDF。若需要先抓 PDF，会先走 `paper-fetcher`，再把本地 PDF 串给 `paper-reader`。")
render_codex_status(codex_status)

with st.form("paper_reader_form"):
    paper_reference = st.text_input(
        "论文链接 / arXiv ID / DOI / 本地 PDF 路径",
        placeholder="例如：2603.19765 或 /absolute/path/to/paper.pdf",
    )
    summary_depth = st.selectbox("摘要深度", options=["标准", "深入", "超详细"], index=0)
    quality_profile = st.selectbox(
        "执行质量档位",
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="paper_reader"),
        help="常规总结建议 balanced；重要论文深读再切到 high-accuracy。",
    )
    diagram_summary = st.checkbox("需要图示化解释", value=True)
    focus_experiments = st.checkbox("优先解释实验细节", value=True)
    auto_fetch_pdf = st.checkbox("若输入不是本地 PDF，则先自动抓 PDF", value=True)
    show_prompt = st.checkbox("展示本次执行 prompt", value=False)
    submitted = st.form_submit_button("执行精读", use_container_width=True)

if submitted:
    response = run_paper_reader(
        PaperReaderInput(
            paper_reference=paper_reference,
            summary_depth=summary_depth,
            diagram_summary=diagram_summary,
            focus_experiments=focus_experiments,
            auto_fetch_pdf=auto_fetch_pdf,
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
    fetch_payload = (stored["response"].get("payload") or {}).get("fetch")
    if fetch_payload:
        st.markdown("**PDF 获取链路**")
        render_bridge_response(fetch_payload)
    if stored.get("show_prompt") and stored.get("prompt"):
        st.markdown("**本次执行 Prompt**")
        st.code(stored["prompt"], language="markdown")
    output_path = stored["response"].get("expected_output_path")
    if output_path and Path(output_path).exists():
        st.markdown("**本次精读结果**")
        render_named_sections(
            load_result(Path(output_path)),
            [
                "一句话总结",
                "论文速览",
                "研究背景",
                "目标",
                "核心问题与方法",
                "核心方法",
                "关键实验与结论",
                "实验细节",
                "结果",
                "局限性",
                "开源资源",
                "通俗图示",
                "图示化解释",
            ],
        )

st.divider()
st.subheader("最近精读结果")
recent_results = list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=20)
if not recent_results:
    st.info("还没有 `outputs/paper_summaries/` 结果。")
else:
    selected_result = st.selectbox(
        "选择精读结果文件",
        options=recent_results,
        format_func=lambda path: path.name,
    )
    loaded = load_result(selected_result)
    show_path("结果文件路径", selected_result)
    render_named_sections(
        loaded,
        [
            "一句话总结",
            "论文速览",
            "研究背景",
            "目标",
            "核心问题与方法",
            "核心方法",
            "关键实验与结论",
            "实验细节",
            "结果",
            "局限性",
            "开源资源",
            "通俗图示",
            "图示化解释",
        ],
    )
