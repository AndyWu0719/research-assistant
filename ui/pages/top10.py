from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import (
    LiteratureScoutInput,
    PaperFetcherInput,
    detect_codex_cli,
    download_and_run_reader,
    run_literature_scout,
    run_paper_fetch,
)
from ui.services.config_store import (
    OUTPUTS_DIR,
    QUALITY_PROFILE_OPTIONS,
    RANKING_PROFILES,
    SOURCE_OPTIONS,
    TIME_RANGE_OPTIONS,
    add_interesting_paper,
    default_quality_for_task,
    ensure_project_layout,
    load_daily_profile,
    load_interesting_papers,
    save_daily_profile,
    time_range_key,
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


STATE_KEY = "top10_last_execution"

ensure_project_layout()
daily_profile = load_daily_profile()
interesting_payload = load_interesting_papers()
interesting_keys = {
    f"{(item.get('paper_url') or '').strip().lower()}||{(item.get('title') or '').strip().lower()}"
    for item in interesting_payload["items"]
}
codex_status = detect_codex_cli()


def is_interesting(title: str, paper_url: str) -> bool:
    key = f"{paper_url.strip().lower()}||{title.strip().lower()}"
    return key in interesting_keys


st.title("Top 10 文献巡检")
st.caption("当前页面默认走 `网页 -> 本地 Codex CLI -> outputs/daily_top10/`。如果本地 CLI 不可用，会明确显示真实状态并保留 prompt 回放文件。")
render_codex_status(codex_status)

time_key = time_range_key(daily_profile["time_range"])
time_options = list(TIME_RANGE_OPTIONS.keys())
quality_options = list(QUALITY_PROFILE_OPTIONS)
default_quality = daily_profile.get("quality_profile") or default_quality_for_task("literature_scout")

with st.form("top10_form"):
    field = st.text_input("研究领域", value=daily_profile["field"])
    selected_time = st.selectbox(
        "时间范围",
        options=time_options,
        index=time_options.index(time_key),
        format_func=lambda item: TIME_RANGE_OPTIONS[item]["label"],
    )
    sources = st.multiselect("来源范围", options=SOURCE_OPTIONS, default=daily_profile["sources"])
    ranking_profile = st.selectbox(
        "排序 profile",
        options=RANKING_PROFILES,
        index=RANKING_PROFILES.index(daily_profile["ranking_profile"]),
    )
    quality_profile = st.selectbox(
        "执行质量档位",
        options=quality_options,
        index=quality_options.index(default_quality),
        format_func=lambda item: format_quality_option(item, task_type="literature_scout"),
        help="常规 Top10 巡检默认使用 balanced；只有明确需要更深分析时再切高档位。",
    )
    constraints = st.text_area(
        "自定义约束",
        value=daily_profile.get("constraints", {}).get("notes", ""),
        height=100,
        placeholder="例如：单卡 24G、优先公开代码、两周内能启动。",
    )
    top_k = st.number_input("Top K", min_value=1, max_value=50, value=int(daily_profile["top_k"]))
    save_as_daily = st.checkbox("同步保存为 daily profile", value=False)
    show_prompt = st.checkbox("展示本次执行 prompt", value=False)
    submitted = st.form_submit_button("执行巡检", use_container_width=True)

if submitted:
    params = {
        "field": field,
        "time_range": TIME_RANGE_OPTIONS[selected_time],
        "sources": sources or daily_profile["sources"],
        "ranking_profile": ranking_profile,
        "constraints": constraints,
        "top_k": int(top_k),
        "quality_profile": quality_profile,
    }
    if save_as_daily:
        save_daily_profile(
            {
                "field": field,
                "time_range": TIME_RANGE_OPTIONS[selected_time],
                "sources": params["sources"],
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
        )
        st.success("已更新 `configs/daily_profile.yaml`。")

    response = run_literature_scout(
        LiteratureScoutInput(
            field=field,
            time_range=TIME_RANGE_OPTIONS[selected_time],
            sources=params["sources"],
            ranking_profile=ranking_profile,
            constraints=constraints,
            top_k=int(top_k),
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
        st.markdown("**本次执行 Prompt**")
        st.code(stored["prompt"], language="markdown")
    output_path = stored["response"].get("expected_output_path")
    if output_path and Path(output_path).exists():
        st.markdown("**本次结果回读**")
        render_loaded_result(load_result(Path(output_path)))

st.divider()
st.subheader("最近结果")
recent_results = list_recent_markdown(OUTPUTS_DIR / "daily_top10", limit=20)
if not recent_results:
    st.info("还没有 `outputs/daily_top10/` 结果文件。")
else:
    selected_result = st.selectbox(
        "选择结果文件",
        options=recent_results,
        format_func=lambda path: path.name,
    )
    loaded = load_result(selected_result)
    show_path("结果文件路径", selected_result)
    if loaded.metadata:
        st.markdown("**本次参数与执行信息**")
        render_bridge_response(
            {
                "status": loaded.metadata.get("status", "success"),
                "message": "已回读历史结果。",
                "quality_profile": loaded.metadata.get("quality_profile"),
                "model": loaded.metadata.get("model"),
                "reasoning_effort": loaded.metadata.get("reasoning_effort"),
                "control_level": loaded.metadata.get("execution_mode"),
                "output_paths": loaded.metadata.get("output_paths") or {},
                "error": loaded.metadata.get("error"),
                "mode": loaded.metadata.get("execution_mode"),
            }
        )

    if loaded.table_rows:
        st.markdown("**Top K 列表**")
        for index, row in enumerate(loaded.table_rows, start=1):
            rank = row.get("rank") or row.get("排名") or str(index)
            title = row.get("title") or row.get("论文") or f"Paper {index}"
            paper_url = row.get("paper_url", "")
            code_url = row.get("code_url", "")
            flagged = is_interesting(title, paper_url)
            expander_title = f"#{rank} {title}"
            if flagged:
                expander_title = f"{expander_title} | 已标记感兴趣"
            with st.expander(expander_title, expanded=index <= 3):
                st.markdown(
                    "\n".join(
                        [
                            f"- 感兴趣状态: {'已标记' if flagged else '未标记'}",
                            f"- 论文链接: {paper_url or '未解析到'}",
                            f"- 代码链接: {code_url or '未解析到'}",
                            f"- 相关性原因: {row.get('why_relevant') or row.get('相关性原因') or '未提供'}",
                            f"- 排名原因: {row.get('why_priority') or row.get('排名原因') or '未提供'}",
                            f"- 推荐优先级: {row.get('priority') or row.get('推荐优先级') or '未提供'}",
                        ]
                    )
                )
                interest_item = {
                    "title": title,
                    "paper_url": paper_url,
                    "code_url": code_url,
                    "source_result": str(selected_result),
                    "rank": rank,
                }
                col1, col2, col3 = st.columns(3)
                if col1.button("标记感兴趣", key=f"interest-{selected_result.name}-{index}", disabled=flagged):
                    added = add_interesting_paper(interest_item)
                    if added:
                        st.success("已写入 `configs/interesting_papers.json`。")
                    else:
                        st.info("该论文已经在感兴趣列表中。")
                if col2.button("下载 PDF", key=f"download-{selected_result.name}-{index}", disabled=not bool(paper_url)):
                    fetch_response = run_paper_fetch(
                        PaperFetcherInput(
                            reference=paper_url,
                            output_dir=OUTPUTS_DIR / "pdfs",
                            quality_profile="economy",
                        )
                    )
                    render_bridge_response(fetch_response)
                    candidates = (fetch_response.payload or {}).get("candidates") or []
                    if fetch_response.status != "success" and candidates:
                        st.markdown("候选链接：")
                        st.markdown("\n".join(f"- {item}" for item in candidates))
                if col3.button("下载并精读", key=f"download-read-{selected_result.name}-{index}", disabled=not bool(paper_url)):
                    pipeline = download_and_run_reader(
                        reference=paper_url,
                        quality_profile="economy",
                        reader_quality_profile="balanced",
                        output_dir=OUTPUTS_DIR / "pdfs",
                    )
                    download_response = pipeline["download"]
                    reader_response = pipeline["reader"]
                    if download_response:
                        st.markdown("**下载状态**")
                        render_bridge_response(download_response)
                        candidates = (download_response.payload or {}).get("candidates") or []
                        if download_response.status != "success" and candidates:
                            st.markdown("候选链接：")
                            st.markdown("\n".join(f"- {item}" for item in candidates))
                    if reader_response:
                        st.markdown("**精读状态**")
                        render_bridge_response(reader_response)
                        output_path = reader_response.expected_output_path
                        if output_path and output_path.exists():
                            st.markdown("**精读结果预览**")
                            render_loaded_result(load_result(output_path))
    render_loaded_result(loaded)
