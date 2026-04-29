from __future__ import annotations

import os
import sys
from typing import Any


def _is_windows(platform_override: str | None = None) -> bool:
    normalized = str(platform_override or "").strip().lower()
    if normalized:
        return normalized == "windows"
    return os.name == "nt"


def configure_utf8_stdio(platform_override: str | None = None) -> None:
    if not _is_windows(platform_override):
        return
    os.environ.setdefault("PYTHONUTF8", "1")
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream_name, errors in (("stdout", "backslashreplace"), ("stderr", "backslashreplace"), ("stdin", "replace")):
        stream = getattr(sys, stream_name, None)
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors=errors)
            except Exception:
                pass


def utf8_subprocess_text_kwargs(platform_override: str | None = None) -> dict[str, Any]:
    if _is_windows(platform_override):
        return {
            "text": True,
            "encoding": "utf-8",
            "errors": "replace",
        }
    return {"text": True}


def apply_utf8_child_env(env: dict[str, str] | None = None, platform_override: str | None = None) -> dict[str, str]:
    merged = dict(os.environ if env is None else env)
    if _is_windows(platform_override):
        merged.setdefault("PYTHONUTF8", "1")
        merged.setdefault("PYTHONIOENCODING", "utf-8")
    return merged
