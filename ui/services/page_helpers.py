from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from ui.services.codex_bridge import BridgeResponse, CodexCLIStatus
from ui.services.config_store import resolve_quality_profile
from ui.services.result_loader import LoadedResult


def show_path(label: str, path: str | Path | None) -> None:
    if not path:
        return
    st.markdown(f"**{label}**")
    st.code(str(path), language="text")


def render_metadata(metadata: dict[str, Any]) -> None:
    if not metadata:
        return
    lines = []
    for key, value in metadata.items():
        if value in ("", None, [], {}):
            continue
        lines.append(f"- `{key}`: {value}")
    if lines:
        st.markdown("\n".join(lines))


def render_loaded_result(result: LoadedResult, expand_sections: bool = True) -> None:
    if result.metadata:
        st.markdown("**参数摘要 / Sidecar**")
        render_metadata(result.metadata)
    if result.sections:
        for title, body in result.sections:
            if expand_sections:
                with st.expander(title, expanded=title in {"一句话总结", "任务定义", "概览"}):
                    st.markdown(body)
            else:
                st.markdown(f"### {title}")
                st.markdown(body)
    else:
        st.markdown(result.content)


def remember_prompt(state_key: str, payload: dict[str, Any]) -> None:
    st.session_state[state_key] = payload


def recall_prompt(state_key: str) -> dict[str, Any] | None:
    payload = st.session_state.get(state_key)
    return payload if isinstance(payload, dict) else None


def render_codex_status(status: CodexCLIStatus) -> None:
    if status.can_execute:
        st.success(status.message)
    else:
        st.warning(status.message)
    if status.version:
        st.markdown(f"- 版本: `{status.version}`")
    if status.executable:
        st.markdown(f"- 可执行路径: `{status.executable}`")
    if status.login_mode:
        st.markdown(f"- 登录方式: `{status.login_mode}`")
    if status.issues:
        st.markdown("\n".join(f"- 问题: {item}" for item in status.issues))
    if status.notes:
        st.markdown("\n".join(f"- 说明: {item}" for item in status.notes))


def render_quality_mapping(
    quality_profile: str | None,
    model: str | None,
    reasoning_effort: str | None,
    control_level: str | None = None,
) -> None:
    lines = []
    if quality_profile:
        lines.append(f"- 质量档位: `{quality_profile}`")
    if model:
        lines.append(f"- 模型: `{model}`")
    if reasoning_effort:
        lines.append(f"- reasoning effort: `{reasoning_effort}`")
    if control_level:
        lines.append(f"- 控制状态: `{control_level}`")
    if lines:
        st.markdown("\n".join(lines))


def format_quality_option(name: str, task_type: str | None = None) -> str:
    profile = resolve_quality_profile(name, task_type=task_type)
    return f"{profile['label']} | {profile['model']} | {profile['reasoning_effort']}"


def render_bridge_response(response: BridgeResponse | dict[str, Any]) -> None:
    payload = response.to_dict() if isinstance(response, BridgeResponse) else response
    status = payload.get("status")
    message = payload.get("message") or ""
    if status in {"success", "ok"}:
        st.success(message)
    elif status in {"partial", "saved"}:
        st.info(message)
    elif status == "unavailable":
        st.warning(message)
    else:
        st.error(message or "执行失败。")

    render_quality_mapping(
        payload.get("quality_profile"),
        payload.get("model"),
        payload.get("reasoning_effort"),
        payload.get("control_level") or payload.get("execution_mode"),
    )
    mode = payload.get("mode") or payload.get("execution_mode")
    if mode:
        st.markdown(f"- 执行模式: `{mode}`")
    if payload.get("error"):
        st.markdown(f"- 失败原因: {payload['error']}")

    output_paths = payload.get("output_paths") or {}
    for key, value in output_paths.items():
        if value:
            show_path(key, value)


def render_named_sections(result: LoadedResult, section_titles: list[str]) -> None:
    indexed = {title.strip(): body for title, body in result.sections}
    rendered = False
    for section_title in section_titles:
        body = indexed.get(section_title)
        if body:
            rendered = True
            with st.expander(section_title, expanded=section_title in {"一句话总结", "论文速览", "任务定义"}):
                st.markdown(body)
    if not rendered:
        render_loaded_result(result)
