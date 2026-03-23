from __future__ import annotations

import socket
import subprocess
import sys
import time
import webbrowser
from pathlib import Path
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
APP_PATH = ROOT / "ui" / "app.py"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ui.services.codex_bridge import detect_codex_cli
from ui.services.config_store import ensure_project_layout, load_user_preferences
from ui.services.ui_text import is_english


def current_language() -> str:
    ensure_project_layout()
    return load_user_preferences()["language"]


def find_free_port(start: int = 8501, end: int = 8510) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) != 0:
                return port
    language = current_language()
    raise RuntimeError(
        "Ports 8501-8510 are all occupied, so Streamlit cannot start."
        if is_english(language)
        else "8501-8510 端口都被占用，无法启动 Streamlit。"
    )


def wait_for_server(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2):
                return True
        except Exception:
            time.sleep(0.5)
    return False


def print_codex_preflight() -> None:
    language = current_language()
    status = detect_codex_cli(refresh=True, language=language)
    print("[Codex CLI Preflight]" if is_english(language) else "[Codex CLI 预检查]")
    if status.version:
        print(f"- {'Version' if is_english(language) else '版本'}: {status.version}")
    if status.executable:
        print(f"- {'Path' if is_english(language) else '路径'}: {status.executable}")
    if status.can_execute:
        print(f"- {'Status' if is_english(language) else '状态'}: {status.message}")
        print(
            "- Codex CLI does not need to stay resident. The web app will invoke `codex exec` on demand."
            if is_english(language)
            else "- 说明: Codex CLI 无需常驻，网页会在执行任务时按需调用 `codex exec`。"
        )
        return
    print(f"- {'Status' if is_english(language) else '状态'}: {status.message}")
    for item in status.issues:
        print(f"- {'Issue' if is_english(language) else '问题'}: {item}")
    print(
        "- The web app can still start even when this is not ready. Research pages will show the unavailable state clearly and keep a manual bridge path."
        if is_english(language)
        else "- 提示: 即使当前未就绪，网页仍可启动；研究类页面会明确显示不可执行状态，并保留手动桥接路径。"
    )
    print(
        "- First-time setup: install Codex CLI, then run `codex login` to complete ChatGPT account login."
        if is_english(language)
        else "- 首次使用建议: 先安装 Codex CLI，然后执行 `codex login` 完成 ChatGPT 账号登录。"
    )


def main() -> int:
    language = current_language()
    try:
        import streamlit  # noqa: F401
    except ImportError:
        print(
            "Streamlit was not found. Run: python -m pip install -r requirements.txt"
            if is_english(language)
            else "未检测到 Streamlit。请先执行: python -m pip install -r requirements.txt"
        )
        return 1

    print_codex_preflight()

    port = find_free_port()
    url = f"http://127.0.0.1:{port}"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PATH),
        "--server.port",
        str(port),
        "--browser.gatherUsageStats",
        "false",
        "--server.headless",
        "true",
    ]
    process = subprocess.Popen(command, cwd=ROOT)
    try:
        if wait_for_server(url):
            webbrowser.open_new_tab(url)
            print(f"Research Assistant started: {url}" if is_english(language) else f"研究助手已启动: {url}")
        else:
            print(
                "Streamlit started, but the web URL was not ready within the expected time. You can open it manually later:"
                if is_english(language)
                else "Streamlit 已启动，但网页地址未在预期时间内就绪。你可以稍后手动打开:"
            )
            print(url)
        return process.wait()
    except KeyboardInterrupt:
        process.terminate()
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
