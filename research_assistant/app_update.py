from __future__ import annotations

import fnmatch
import json
import os
import plistlib
import re
import shutil
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlparse
from urllib.request import Request, urlopen

import yaml

from research_assistant.config_store import APP_UPDATE_CONFIG_PATH, ROOT, load_app_update_config


APP_NAME = "Research Assistant"
BUILD_METADATA_NAME = ".app-build.json"
GITHUB_API_VERSION = "2022-11-28"
UPDATE_STATE_PATH = ROOT / "configs" / "update_state.json"
UPDATE_DOWNLOAD_DIR = ROOT / "downloads"
DEFAULT_UPDATE_STATE: dict[str, Any] = {
    "last_checked_at": None,
    "last_prompted_version": "",
    "last_downloaded_version": "",
    "last_downloaded_path": "",
}


def _bundle_info_plist_path() -> Path | None:
    executable = Path(sys.executable).resolve()
    if executable.name != APP_NAME:
        return None
    contents_dir = executable.parents[1]
    info_plist = contents_dir / "Info.plist"
    return info_plist if info_plist.exists() else None


def current_build_info() -> dict[str, Any]:
    payload: dict[str, Any] = {
        "app_name": APP_NAME,
        "version": "1.0.0",
        "platform": sys.platform,
        "built_from": str(ROOT),
    }

    metadata_path = ROOT / BUILD_METADATA_NAME
    if metadata_path.exists():
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
            if isinstance(metadata, dict):
                payload.update({key: value for key, value in metadata.items() if value is not None})
        except json.JSONDecodeError:
            pass

    bundle_info_path = _bundle_info_plist_path()
    if bundle_info_path:
        try:
            with bundle_info_path.open("rb") as handle:
                bundle_info = plistlib.load(handle)
            payload["bundle_identifier"] = bundle_info.get("CFBundleIdentifier")
            payload["bundle_version"] = bundle_info.get("CFBundleVersion")
            payload["bundle_short_version"] = bundle_info.get("CFBundleShortVersionString")
            if payload.get("version") in {"", None, "1.0.0"}:
                payload["version"] = bundle_info.get("CFBundleShortVersionString") or bundle_info.get("CFBundleVersion") or "1.0.0"
        except (OSError, plistlib.InvalidFileException):
            pass

    payload["version"] = str(payload.get("version") or "1.0.0").strip() or "1.0.0"
    return payload


def current_version() -> str:
    return str(current_build_info().get("version") or "1.0.0")


def _version_key(value: str) -> tuple[int, ...]:
    numbers = [int(item) for item in re.findall(r"\d+", value or "")]
    return tuple(numbers) if numbers else (0,)


def compare_versions(left: str, right: str) -> int:
    left_key = _version_key(left)
    right_key = _version_key(right)
    width = max(len(left_key), len(right_key))
    padded_left = left_key + (0,) * (width - len(left_key))
    padded_right = right_key + (0,) * (width - len(right_key))
    if padded_left < padded_right:
        return -1
    if padded_left > padded_right:
        return 1
    return 0


def _parse_manifest_payload(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = yaml.safe_load(text)
    if not isinstance(payload, dict):
        raise ValueError("更新清单格式无效，顶层必须是对象。")
    return payload


def _load_json_url(url: str, *, headers: dict[str, str] | None = None) -> dict[str, Any]:
    request_headers = {"User-Agent": "Research-Assistant-Updater"}
    if headers:
        request_headers.update(headers)
    request = Request(url, headers=request_headers)
    with urlopen(request, timeout=15) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("远端返回的更新数据不是对象。")
    return payload


def _resolve_manifest_source(manifest_url: str) -> tuple[dict[str, Any], str, Path | None]:
    if manifest_url.startswith(("https://", "http://")):
        request = Request(manifest_url, headers={"User-Agent": "Research-Assistant-Updater"})
        with urlopen(request, timeout=10) as response:
            payload = _parse_manifest_payload(response.read().decode("utf-8"))
        return payload, manifest_url, None

    manifest_path = Path(manifest_url).expanduser()
    if not manifest_path.is_absolute():
        manifest_path = (ROOT / manifest_path).resolve()
    if not manifest_path.exists():
        raise FileNotFoundError(f"找不到更新清单：{manifest_path}")
    payload = _parse_manifest_payload(manifest_path.read_text(encoding="utf-8"))
    return payload, str(manifest_path), manifest_path


def _resolve_download_url(value: str, manifest_path: Path | None) -> str:
    target = (value or "").strip()
    if not target:
        return ""
    if target.startswith(("https://", "http://", "file://")):
        return target
    resolved = Path(target).expanduser()
    if not resolved.is_absolute() and manifest_path is not None:
        resolved = (manifest_path.parent / resolved).resolve()
    return str(resolved)


def _extract_semver(*candidates: str) -> str:
    for candidate in candidates:
        match = re.search(r"(\d+\.\d+\.\d+)", candidate or "")
        if match:
            return match.group(1)
    return ""


def _resolve_release_asset(release: dict[str, Any], pattern: str) -> tuple[dict[str, Any] | None, str]:
    assets = release.get("assets") or []
    if not isinstance(assets, list):
        return None, ""

    normalized_pattern = pattern.strip() or "ResearchAssistant-macos-*.pkg"
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        if fnmatch.fnmatch(name, normalized_pattern):
            return asset, name
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        name = str(asset.get("name") or "")
        if name.endswith(".pkg"):
            return asset, name
    return None, ""


def _manifest_from_github_release(config: dict[str, Any]) -> tuple[dict[str, Any], str]:
    repo = str(config.get("github_repo") or "").strip().strip("/")
    if not repo:
        raise ValueError("GitHub 更新源缺少 `github_repo` 配置。")

    token_env = str(config.get("github_token_env") or "").strip()
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": GITHUB_API_VERSION,
    }
    if token_env:
        token = str(os.environ.get(token_env) or "").strip()
        if token:
            headers["Authorization"] = f"Bearer {token}"

    release_url = f"https://api.github.com/repos/{repo}/releases/latest"
    try:
        release = _load_json_url(release_url, headers=headers)
    except HTTPError as exc:
        if exc.code == 404:
            raise ValueError("GitHub Releases 暂无已发布版本。") from exc
        raise
    asset, asset_name = _resolve_release_asset(release, str(config.get("github_asset_pattern") or ""))
    latest_version = _extract_semver(
        asset_name,
        str(release.get("name") or ""),
        str(release.get("tag_name") or ""),
    )
    if not latest_version:
        raise ValueError("无法从 GitHub Release 解析版本号，请确保 tag 或 pkg 文件名里包含 x.y.z。")

    download_url = str(asset.get("browser_download_url") or "").strip() if asset else ""
    notes = str(release.get("body") or "").strip()
    published_at = str(release.get("published_at") or release.get("created_at") or "").strip()
    html_url = str(release.get("html_url") or "").strip()
    payload = {
        "latest_version": latest_version,
        "download_url": download_url,
        "notes": notes,
        "published_at": published_at,
        "release_name": str(release.get("name") or "").strip(),
        "release_tag": str(release.get("tag_name") or "").strip(),
        "release_page_url": html_url,
        "asset_name": asset_name,
    }
    return payload, html_url or release_url


def _load_update_state() -> dict[str, Any]:
    if not UPDATE_STATE_PATH.exists():
        return dict(DEFAULT_UPDATE_STATE)
    try:
        payload = json.loads(UPDATE_STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return dict(DEFAULT_UPDATE_STATE)
    if not isinstance(payload, dict):
        return dict(DEFAULT_UPDATE_STATE)
    merged = dict(DEFAULT_UPDATE_STATE)
    merged.update(payload)
    return merged


def _save_update_state(payload: dict[str, Any]) -> None:
    UPDATE_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    UPDATE_STATE_PATH.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def should_auto_check_updates() -> bool:
    config = load_app_update_config()
    if not bool(config.get("check_on_launch", True)):
        return False
    interval_hours = int(config.get("check_interval_hours") or 24)
    state = _load_update_state()
    last_checked = _parse_iso(state.get("last_checked_at"))
    if last_checked is None:
        return True
    return datetime.now() - last_checked >= timedelta(hours=max(1, interval_hours))


def _record_update_check() -> None:
    state = _load_update_state()
    state["last_checked_at"] = _now_iso()
    _save_update_state(state)


def mark_update_prompted(version: str) -> None:
    state = _load_update_state()
    state["last_prompted_version"] = str(version or "").strip()
    state["last_checked_at"] = _now_iso()
    _save_update_state(state)


def _download_filename_from_url(download_url: str, version: str, fallback_name: str | None = None) -> str:
    if fallback_name:
        return fallback_name
    parsed = urlparse(download_url)
    name = unquote(Path(parsed.path).name)
    if name:
        return name
    return f"ResearchAssistant-macos-{version}.pkg"


def download_update_package(download_url: str, version: str, fallback_name: str | None = None) -> dict[str, Any]:
    target = str(download_url or "").strip()
    if not target:
        raise ValueError("缺少可下载的更新包地址。")

    if target.startswith("file://"):
        local_path = Path(urlparse(target).path).expanduser().resolve()
        return {"download_path": str(local_path), "filename": local_path.name, "downloaded": False}

    if not target.startswith(("https://", "http://")):
        local_path = Path(target).expanduser().resolve()
        return {"download_path": str(local_path), "filename": local_path.name, "downloaded": False}

    UPDATE_DOWNLOAD_DIR.mkdir(parents=True, exist_ok=True)
    filename = _download_filename_from_url(target, version, fallback_name)
    destination = UPDATE_DOWNLOAD_DIR / filename

    request = Request(target, headers={"User-Agent": "Research-Assistant-Updater"})
    with urlopen(request, timeout=60) as response, destination.open("wb") as handle:
        shutil.copyfileobj(response, handle)

    state = _load_update_state()
    state["last_downloaded_version"] = str(version or "").strip()
    state["last_downloaded_path"] = str(destination)
    state["last_checked_at"] = _now_iso()
    _save_update_state(state)
    return {"download_path": str(destination), "filename": filename, "downloaded": True}


def check_for_updates() -> dict[str, Any]:
    build = current_build_info()
    config = load_app_update_config()
    provider = str(config.get("provider") or "manifest").strip() or "manifest"
    manifest_url = str(config.get("manifest_url") or "").strip()
    base_payload = {
        "current_version": build["version"],
        "config_path": str(APP_UPDATE_CONFIG_PATH),
        "provider": provider,
        "manifest_url": manifest_url,
        "github_repo": str(config.get("github_repo") or "").strip(),
        "channel": config.get("channel", "stable"),
        "download_in_app": bool(config.get("download_in_app", True)),
        "open_download_in_browser": bool(config.get("open_download_in_browser", False)),
    }

    try:
        if provider == "github_release":
            manifest, resolved_source = _manifest_from_github_release(config)
            manifest_path = None
        else:
            if not manifest_url:
                return {
                    **base_payload,
                    "status": "unconfigured",
                    "message": "尚未配置更新清单地址。",
                }
            manifest, resolved_source, manifest_path = _resolve_manifest_source(manifest_url)
            manifest["download_url"] = _resolve_download_url(str(manifest.get("download_url") or ""), manifest_path)
    except FileNotFoundError as exc:
        return {**base_payload, "status": "error", "message": str(exc)}
    except (ValueError, URLError, OSError) as exc:
        message = str(exc)
        if "GitHub Releases 暂无已发布版本" in message:
            return {**base_payload, "status": "no_release", "message": message}
        return {**base_payload, "status": "error", "message": f"读取更新信息失败：{exc}"}

    latest_version = str(manifest.get("latest_version") or manifest.get("version") or "").strip()
    if not latest_version:
        return {
            **base_payload,
            "status": "error",
            "message": "更新数据缺少 `latest_version` 字段。",
            "resolved_manifest_source": resolved_source,
        }

    state = _load_update_state()
    download_url = str(manifest.get("download_url") or "").strip()
    notes = str(manifest.get("notes") or "").strip()
    published_at = str(manifest.get("published_at") or "").strip()
    comparison = compare_versions(build["version"], latest_version)
    _record_update_check()

    if comparison < 0:
        return {
            **base_payload,
            "status": "update_available",
            "message": "发现可用新版本。",
            "latest_version": latest_version,
            "download_url": download_url,
            "notes": notes,
            "published_at": published_at,
            "resolved_manifest_source": resolved_source,
            "release_name": str(manifest.get("release_name") or "").strip(),
            "release_tag": str(manifest.get("release_tag") or "").strip(),
            "release_page_url": str(manifest.get("release_page_url") or "").strip(),
            "asset_name": str(manifest.get("asset_name") or "").strip(),
            "already_prompted": str(state.get("last_prompted_version") or "").strip() == latest_version,
        }
    return {
        **base_payload,
        "status": "up_to_date",
        "message": "当前已是最新版本。",
        "latest_version": latest_version,
        "download_url": download_url,
        "notes": notes,
        "published_at": published_at,
        "resolved_manifest_source": resolved_source,
        "already_prompted": False,
    }
