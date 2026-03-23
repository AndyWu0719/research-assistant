from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import PaperFetcherInput, detect_codex_cli, download_and_run_reader, run_paper_fetch
from ui.services.config_store import (
    OUTPUTS_DIR,
    QUALITY_PROFILE_OPTIONS,
    default_quality_for_task,
    ensure_project_layout,
    load_interesting_papers,
    remove_interesting_paper,
)
from ui.services.page_helpers import format_quality_option, render_bridge_response, render_codex_status, show_path
from ui.services.paper_sources import split_references
from ui.services.result_loader import list_recent_markdown


ensure_project_layout()
codex_status = detect_codex_cli()
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_reader_quality = default_quality_for_task("paper_reader")

st.title("PDF 下载")
st.caption("当前页面是真实本地链路：`paper-fetcher` 负责下载，`下载并精读` 会在下载成功后自动串到 `paper-reader`。")
render_codex_status(codex_status)

with st.form("pdf_fetch_form"):
    raw_references = st.text_area(
        "论文链接 / arXiv ID / DOI / OpenReview 链接",
        height=180,
        placeholder="每行一条，例如：\n2603.19765\nhttps://openreview.net/forum?id=YeagC09j2K",
    )
    save_dir = st.text_input("保存目录", value=str(OUTPUTS_DIR / "pdfs"))
    auto_read = st.checkbox("下载后自动精读", value=False)
    reader_quality_profile = st.selectbox(
        "自动精读质量档位",
        options=quality_options,
        index=quality_options.index(default_reader_quality),
        format_func=lambda item: format_quality_option(item, task_type="paper_reader"),
        disabled=not auto_read,
    )
    show_candidates = st.checkbox("下载失败时返回候选页面", value=True)
    submitted = st.form_submit_button("开始执行", use_container_width=True)

if submitted:
    references = split_references(raw_references)
    if not references:
        st.warning("请至少输入一条论文引用。")
    else:
        for index, reference in enumerate(references, start=1):
            st.markdown(f"### 任务 {index}")
            st.code(reference, language="text")
            if auto_read:
                results = download_and_run_reader(
                    reference=reference,
                    quality_profile="economy",
                    reader_quality_profile=reader_quality_profile,
                    output_dir=save_dir,
                )
                download = results["download"]
                reader = results["reader"]
                if download:
                    st.markdown("**下载状态**")
                    render_bridge_response(download)
                    candidates = (download.payload or {}).get("candidates") or []
                    if show_candidates and download.status != "success" and candidates:
                        st.markdown("\n".join(f"- {item}" for item in candidates))
                if reader:
                    st.markdown("**精读状态**")
                    render_bridge_response(reader)
            else:
                response = run_paper_fetch(
                    PaperFetcherInput(
                        reference=reference,
                        output_dir=save_dir,
                        quality_profile="economy",
                    )
                )
                render_bridge_response(response)
                candidates = (response.payload or {}).get("candidates") or []
                if show_candidates and response.status != "success" and candidates:
                    st.markdown("候选页面 / 候选链接：")
                    st.markdown("\n".join(f"- {item}" for item in candidates))

st.divider()
st.subheader("感兴趣论文列表")
interesting = load_interesting_papers()
if not interesting["items"]:
    st.info("`configs/interesting_papers.json` 里还没有已标记论文。")
else:
    for index, item in enumerate(interesting["items"], start=1):
        title = item.get("title") or f"Paper {index}"
        paper_url = item.get("paper_url", "")
        with st.expander(f"{index}. {title}", expanded=index <= 5):
            st.markdown(
                "\n".join(
                    [
                        f"- 论文链接: {paper_url or '未提供'}",
                        f"- 来源结果: {item.get('source_result', '未记录')}",
                        f"- 标记时间: {item.get('saved_at', '未记录')}",
                    ]
                )
            )
            col1, col2, col3 = st.columns(3)
            if col1.button("仅下载", key=f"fetch-interesting-{index}", disabled=not bool(paper_url)):
                response = run_paper_fetch(
                    PaperFetcherInput(
                        reference=paper_url,
                        output_dir=OUTPUTS_DIR / "pdfs",
                        quality_profile="economy",
                    )
                )
                render_bridge_response(response)
            if col2.button("下载并精读", key=f"fetch-read-interesting-{index}", disabled=not bool(paper_url)):
                results = download_and_run_reader(
                    reference=paper_url,
                    quality_profile="economy",
                    reader_quality_profile=default_reader_quality,
                    output_dir=OUTPUTS_DIR / "pdfs",
                )
                if results["download"]:
                    render_bridge_response(results["download"])
                if results["reader"]:
                    render_bridge_response(results["reader"])
            if col3.button("移除标记", key=f"remove-interesting-{index}"):
                removed = remove_interesting_paper(paper_url or title)
                if removed:
                    st.success("已从感兴趣列表移除。")
                else:
                    st.info("未找到对应记录。")

st.divider()
st.subheader("最近精读结果")
recent_summaries = list_recent_markdown(OUTPUTS_DIR / "paper_summaries", limit=10)
if recent_summaries:
    st.markdown("\n".join(f"- `{path.name}`" for path in recent_summaries))
else:
    st.info("还没有 `paper-reader` 结果。")
