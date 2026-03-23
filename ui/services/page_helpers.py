from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import streamlit as st
from streamlit.errors import StreamlitAPIException

from ui.services.codex_bridge import BridgeResponse, CodexCLIStatus
from ui.services.config_store import (
    USER_PREFERENCES_PATH,
    current_automation_config_path,
    load_user_preferences,
    resolve_quality_profile,
    update_user_preferences,
)
from ui.services.language import LANGUAGE_OPTIONS
from ui.services.result_loader import LoadedResult
from ui.services.ui_text import (
    NAV_ITEMS,
    bool_label,
    expander_title,
    language_option_label,
    page_copy,
    section_aliases,
    section_key_from_title,
    section_label,
    t,
)


def _current_language() -> str:
    return load_user_preferences()["language"]


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
    language = _current_language()
    if result.metadata:
        with st.expander(expander_title("metadata_sidecar", language), expanded=False):
            render_metadata(result.metadata)
    if not result.sections:
        st.markdown(result.content)
        return

    for title, body in result.sections:
        display_title = section_label("overview", language) if title == "__overview__" else title
        section_key = section_key_from_title(title)
        should_expand = section_key in {"overview", "one_sentence", "task_definition"}
        if expand_sections:
            with st.expander(display_title, expanded=should_expand):
                st.markdown(body)
        else:
            st.markdown(f"### {display_title}")
            st.markdown(body)


def remember_prompt(state_key: str, payload: dict[str, Any]) -> None:
    st.session_state[state_key] = payload


def recall_prompt(state_key: str) -> dict[str, Any] | None:
    payload = st.session_state.get(state_key)
    return payload if isinstance(payload, dict) else None


def render_codex_status(status: CodexCLIStatus) -> None:
    language = _current_language()
    if status.can_execute:
        st.success(status.message)
    else:
        st.warning(status.message)
    if status.version:
        st.markdown(f"- {t('common.version', language)}: `{status.version}`")
    if status.executable:
        st.markdown(f"- {t('common.executable_path', language)}: `{status.executable}`")
    if status.login_mode:
        st.markdown(f"- {t('common.login_mode', language)}: `{status.login_mode}`")
    if status.issues:
        st.markdown("\n".join(f"- {t('common.issue', language)}: {item}" for item in status.issues))
    if status.notes:
        st.markdown("\n".join(f"- {t('common.note', language)}: {item}" for item in status.notes))


def render_codex_status_panel(status: CodexCLIStatus, expanded: bool = False) -> None:
    with st.expander(expander_title("local_environment", _current_language()), expanded=expanded):
        render_codex_status(status)


def render_quality_mapping(
    quality_profile: str | None,
    model: str | None,
    reasoning_effort: str | None,
    control_level: str | None = None,
) -> None:
    language = _current_language()
    lines = []
    if quality_profile:
        lines.append(f"- {t('common.quality_profile_line', language)}: `{quality_profile}`")
    if model:
        lines.append(f"- {t('common.model', language)}: `{model}`")
    if reasoning_effort:
        lines.append(f"- {t('common.reasoning_effort', language)}: `{reasoning_effort}`")
    if control_level:
        lines.append(f"- {t('common.control_level', language)}: `{control_level}`")
    if lines:
        st.markdown("\n".join(lines))


def format_quality_option(name: str, task_type: str | None = None) -> str:
    profile = resolve_quality_profile(name, task_type=task_type)
    return f"{profile['label']} | {profile['model']} | {profile['reasoning_effort']}"


def render_bridge_response(response: BridgeResponse | dict[str, Any]) -> None:
    language = _current_language()
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
        st.error(message or ("Execution failed." if language == "en-US" else "执行失败。"))

    render_quality_mapping(
        payload.get("quality_profile"),
        payload.get("model"),
        payload.get("reasoning_effort"),
        payload.get("control_level") or payload.get("execution_mode"),
    )
    mode = payload.get("mode") or payload.get("execution_mode")
    if mode:
        st.markdown(f"- {t('common.execution_mode', language)}: `{mode}`")
    if payload.get("error"):
        st.markdown(f"- {t('common.failure_reason', language)}: {payload['error']}")

    output_paths = payload.get("output_paths") or {}
    if output_paths:
        render_path_expander(expander_title("output_paths", language), output_paths)

    debug_payload = payload.get("payload") or {}
    if debug_payload:
        render_debug_expander(debug_payload)


def render_named_sections(result: LoadedResult, section_keys: list[str]) -> None:
    language = _current_language()
    indexed = {title.strip().lower(): (title, body) for title, body in result.sections}
    rendered = False
    for section_key in section_keys:
        matched: tuple[str, str] | None = None
        for alias in section_aliases(section_key):
            if alias in indexed:
                matched = indexed[alias]
                break
        if not matched:
            continue
        rendered = True
        _, body = matched
        with st.expander(section_label(section_key, language), expanded=section_key in {"one_sentence", "paper_overview", "task_definition"}):
            st.markdown(body)
    if not rendered:
        render_loaded_result(result)


def render_path_expander(title: str, paths: dict[str, Any] | None, expanded: bool = False) -> None:
    valid = {
        str(key): str(value)
        for key, value in (paths or {}).items()
        if value not in ("", None, [], {})
    }
    if not valid:
        return
    with st.expander(title, expanded=expanded):
        for label, value in valid.items():
            show_path(label, value)


def render_prompt_expander(prompt: str | None) -> None:
    if not prompt:
        return
    with st.expander(expander_title("raw_prompt", _current_language()), expanded=False):
        st.code(prompt, language="markdown")


def render_debug_expander(payload: dict[str, Any]) -> None:
    if not payload:
        return
    with st.expander(expander_title("debug_details", _current_language()), expanded=False):
        st.code(json.dumps(payload, ensure_ascii=False, indent=2), language="json")


def render_pdf_extraction_status(metadata: dict[str, Any] | None) -> None:
    language = _current_language()
    extraction = (metadata or {}).get("pdf_extraction") if isinstance(metadata, dict) else None
    if not extraction:
        return
    quality = str(extraction.get("quality", "unknown"))
    warnings = [str(item) for item in extraction.get("warnings", [])]
    status = str(extraction.get("status", "unknown"))
    if status != "success":
        st.warning(
            "PDF text extraction did not succeed. Interpret the current deep-read result cautiously."
            if language == "en-US"
            else "PDF 文本抽取未成功，当前精读结果需要谨慎解读。"
        )
    elif quality in {"mixed", "poor"}:
        st.warning(
            "PDF text extraction quality is limited. Tables, formulas, and experimental details may be missing or distorted."
            if language == "en-US"
            else "PDF 文本抽取质量不足，表格、公式和实验细节可能缺失或失真。"
        )
    else:
        st.info(
            "PDF text extraction quality is usable. The deep read primarily relies on the cleaned local text."
            if language == "en-US"
            else "PDF 文本抽取质量可用，精读优先基于清洗后的本地文本。"
        )

    details = {
        "status": status,
        "quality": quality,
        "total_pages": extraction.get("total_pages"),
        "pages_with_text": extraction.get("pages_with_text"),
        "total_characters": extraction.get("total_characters"),
        "average_characters_per_page": extraction.get("average_characters_per_page"),
        "text_path": extraction.get("text_path"),
        "sidecar_path": extraction.get("sidecar_path"),
        "warnings": warnings,
    }
    with st.expander(expander_title("pdf_extraction", language), expanded=False):
        render_metadata(details)


def render_app_sidebar(current_page: str) -> None:
    preferences = load_user_preferences()
    language = preferences["language"]
    st.sidebar.title(t("sidebar.title", language))
    display_to_code = {language_option_label(code, language): code for code in LANGUAGE_OPTIONS.keys()}
    display_options = list(display_to_code.keys())
    current_display = language_option_label(language, language)
    selected_display = st.sidebar.selectbox(
        t("sidebar.language", language),
        options=display_options,
        index=display_options.index(current_display),
        key="app-language-selector",
    )
    selected_language = display_to_code[selected_display]
    if selected_language != language:
        update_user_preferences({"language": selected_language})
        st.rerun()

    st.sidebar.caption(t("sidebar.navigation", language))
    for page_key, target in NAV_ITEMS:
        label = page_copy(page_key, language)["nav_label"]
        try:
            st.sidebar.page_link(
                target,
                label=label,
                disabled=page_key == current_page,
            )
        except StreamlitAPIException:
            if page_key == current_page:
                st.sidebar.markdown(f"**{label}**")
            else:
                st.sidebar.markdown(f"- {label}")

    with st.sidebar.expander(expander_title("saved_preferences", language), expanded=False):
        st.markdown(f"- {t('sidebar.preference_language', language)}: `{language_option_label(preferences['language'], language)}`")
        st.markdown(f"- {t('sidebar.preference_path', language)}: `{USER_PREFERENCES_PATH}`")
        st.markdown(
            f"- {t('sidebar.current_automation_config', language)}: `{current_automation_config_path().name}`"
        )


def render_page_header(page_key: str) -> None:
    language = _current_language()
    copy = page_copy(page_key, language)
    st.title(copy["title"])
    st.caption(copy["caption"])
