#!/usr/bin/env python3
"""Download a paper PDF from arXiv, OpenReview, DOI, or a landing page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, quote, urljoin, urlparse
from urllib.request import Request, urlopen


USER_AGENT = "research-assistant-paper-fetcher/2.0"
DEFAULT_TIMEOUT = 30
DEFAULT_OUTPUT_DIR = Path("outputs/pdfs")
ARXIV_ID_RE = re.compile(
    r"^(?:arxiv:)?(?P<id>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)$",
    re.IGNORECASE,
)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


@dataclass(slots=True)
class Resolution:
    input_value: str
    source_type: str
    source_id: str
    landing_url: str
    pdf_url: str
    candidates: list[str] = field(default_factory=list)
    title: str = ""
    authors: list[str] = field(default_factory=list)
    year: str = ""


class MetaCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, list[str]] = {}
        self.links: list[tuple[str, str]] = []
        self.title_parts: list[str] = []
        self._current_href: str | None = None
        self._current_text: list[str] = []
        self._inside_title = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {key.lower(): value for key, value in attrs if value}
        lowered = tag.lower()
        if lowered == "meta":
            name = (attrs_map.get("name") or attrs_map.get("property") or "").strip().lower()
            content = (attrs_map.get("content") or "").strip()
            if name and content:
                self.meta.setdefault(name, []).append(content)
            return
        if lowered == "title":
            self._inside_title = True
            return
        if lowered == "a":
            href = attrs_map.get("href")
            if href:
                self._current_href = href
                self._current_text = []

    def handle_data(self, data: str) -> None:
        if self._inside_title:
            self.title_parts.append(data)
        if self._current_href is not None:
            stripped = data.strip()
            if stripped:
                self._current_text.append(stripped)

    def handle_endtag(self, tag: str) -> None:
        lowered = tag.lower()
        if lowered == "title":
            self._inside_title = False
            return
        if lowered == "a" and self._current_href is not None:
            self.links.append((self._current_href, " ".join(self._current_text).strip()))
            self._current_href = None
            self._current_text = []


def slugify(value: str, max_length: int = 60) -> str:
    lowered = value.strip().lower()
    lowered = re.sub(r"\.pdf$", "", lowered)
    lowered = re.sub(r"[^a-z0-9._-]+", "-", lowered)
    lowered = re.sub(r"-{2,}", "-", lowered).strip("-._")
    lowered = lowered or "paper"
    return lowered[:max_length].rstrip("-._")


def ensure_pdf_suffix(filename: str) -> str:
    return filename if filename.lower().endswith(".pdf") else f"{filename}.pdf"


def make_request(url: str, accept: str) -> Request:
    return Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": accept,
            "Accept-Language": "en-US,en;q=0.8",
        },
    )


def read_url(url: str, accept: str) -> tuple[bytes, Any, str]:
    request = make_request(url, accept)
    with urlopen(request, timeout=DEFAULT_TIMEOUT) as response:
        return response.read(), response.info(), response.geturl()


def parse_arxiv_id(value: str) -> str | None:
    candidate = value.strip()
    match = ARXIV_ID_RE.match(candidate)
    if match:
        return match.group("id")

    parsed = urlparse(candidate)
    if "arxiv.org" not in parsed.netloc.lower():
        return None

    path = parsed.path.strip("/")
    if path.startswith("abs/"):
        return path.split("/", 1)[1]
    if path.startswith("pdf/"):
        return re.sub(r"\.pdf$", "", path.split("/", 1)[1])
    return None


def parse_openreview_id(value: str) -> str | None:
    parsed = urlparse(value.strip())
    if "openreview.net" not in parsed.netloc.lower():
        return None
    query = parse_qs(parsed.query)
    for key in ("id", "noteId"):
        if query.get(key):
            return query[key][0]
    return None


def parse_doi(value: str) -> str | None:
    candidate = value.strip()
    match = DOI_RE.search(candidate)
    if match:
        return match.group(0)
    parsed = urlparse(candidate)
    if "doi.org" in parsed.netloc.lower():
        return parsed.path.strip("/") or None
    return None


def direct_pdf_url(value: str) -> str | None:
    parsed = urlparse(value.strip())
    if parsed.scheme in {"http", "https"} and parsed.path.lower().endswith(".pdf"):
        return value.strip()
    return None


def extract_year(text: str) -> str:
    match = re.search(r"(19|20)\d{2}", text)
    return match.group(0) if match else ""


def author_token(name: str) -> str:
    parts = [part for part in re.split(r"[\s,]+", name.strip()) if part]
    if not parts:
        return "unknown"
    return slugify(parts[-1], max_length=24) or "unknown"


def choose_title(meta: dict[str, list[str]], collector: MetaCollector) -> str:
    keys = [
        "citation_title",
        "dc.title",
        "dc.title",
        "og:title",
        "twitter:title",
    ]
    for key in keys:
        values = meta.get(key)
        if values:
            return values[0].strip()
    title = "".join(collector.title_parts).strip()
    return re.sub(r"\s+", " ", title)


def choose_authors(meta: dict[str, list[str]]) -> list[str]:
    keys = ["citation_author", "dc.creator", "dc.contributor"]
    authors: list[str] = []
    for key in keys:
        authors.extend(value.strip() for value in meta.get(key, []) if value.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for author in authors:
        lowered = author.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(author)
    return deduped


def candidate_score(url: str, text: str) -> int:
    lowered = url.lower()
    lowered_text = text.lower()
    score = 0
    if lowered.endswith(".pdf"):
        score += 100
    if "citation_pdf_url" in lowered:
        score += 95
    if "arxiv.org/pdf/" in lowered:
        score += 95
    if "openreview.net/pdf" in lowered:
        score += 95
    if "pdf" in lowered:
        score += 60
    if lowered_text in {"pdf", "download pdf", "paper pdf"}:
        score += 45
    if "supp" in lowered or "supplement" in lowered:
        score -= 35
    if "supp" in lowered_text or "supplement" in lowered_text:
        score -= 35
    if "poster" in lowered or "poster" in lowered_text:
        score -= 20
    return score


def parse_html_page(page_url: str) -> tuple[bytes, Any, str, MetaCollector]:
    body, headers, final_url = read_url(page_url, "text/html,application/xhtml+xml,*/*;q=0.8")
    collector = MetaCollector()
    collector.feed(body.decode("utf-8", errors="ignore"))
    return body, headers, final_url, collector


def collect_candidates(page_url: str, collector: MetaCollector) -> list[str]:
    candidates: list[tuple[int, str]] = []
    meta_pdf = collector.meta.get("citation_pdf_url", []) + collector.meta.get("pdf_url", [])
    for value in meta_pdf:
        candidates.append((1000, urljoin(page_url, value)))
    for href, text in collector.links:
        resolved = urljoin(page_url, href)
        score = candidate_score(resolved, text)
        if score >= 40:
            candidates.append((score, resolved))
    deduped: list[str] = []
    seen: set[str] = set()
    for _, url in sorted(candidates, key=lambda item: item[0], reverse=True):
        if url in seen:
            continue
        seen.add(url)
        deduped.append(url)
    return deduped[:8]


def metadata_from_page(page_url: str, collector: MetaCollector) -> tuple[str, list[str], str, list[str]]:
    meta = collector.meta
    title = choose_title(meta, collector)
    authors = choose_authors(meta)
    year_candidates = []
    for key in ("citation_date", "citation_publication_date", "dc.date", "article:published_time"):
        year_candidates.extend(meta.get(key, []))
    year = ""
    for candidate in year_candidates:
        year = extract_year(candidate)
        if year:
            break
    candidates = collect_candidates(page_url, collector)
    return title, authors, year, candidates


def fallback_resolution(
    input_value: str,
    source_type: str,
    source_id: str,
    landing_url: str,
    pdf_url: str,
) -> Resolution:
    return Resolution(
        input_value=input_value,
        source_type=source_type,
        source_id=source_id,
        landing_url=landing_url,
        pdf_url=pdf_url,
        candidates=[pdf_url] if pdf_url else [landing_url],
    )


def resolve_from_page(input_value: str, page_url: str, source_type: str, source_id: str) -> Resolution:
    body, headers, final_url, collector = parse_html_page(page_url)
    content_type = getattr(headers, "get_content_type", lambda: "")()
    if body.startswith(b"%PDF") or content_type == "application/pdf":
        return fallback_resolution(
            input_value=input_value,
            source_type=source_type,
            source_id=source_id,
            landing_url=final_url,
            pdf_url=final_url,
        )

    title, authors, year, candidates = metadata_from_page(final_url, collector)
    pdf_url = candidates[0] if candidates else ""
    return Resolution(
        input_value=input_value,
        source_type=source_type,
        source_id=source_id,
        landing_url=final_url,
        pdf_url=pdf_url,
        candidates=[final_url, *candidates],
        title=title,
        authors=authors,
        year=year,
    )


def resolve_input(value: str) -> Resolution:
    arxiv_id = parse_arxiv_id(value)
    if arxiv_id:
        abs_url = f"https://arxiv.org/abs/{arxiv_id}"
        try:
            resolution = resolve_from_page(
                input_value=value,
                page_url=abs_url,
                source_type="arxiv",
                source_id=arxiv_id,
            )
        except (HTTPError, URLError):
            resolution = fallback_resolution(
                input_value=value,
                source_type="arxiv",
                source_id=arxiv_id,
                landing_url=abs_url,
                pdf_url=f"https://arxiv.org/pdf/{arxiv_id}.pdf",
            )
        if not resolution.pdf_url:
            resolution.pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
            resolution.candidates.append(resolution.pdf_url)
        return resolution

    openreview_id = parse_openreview_id(value)
    if openreview_id:
        forum_url = f"https://openreview.net/forum?id={openreview_id}"
        pdf_url = f"https://openreview.net/pdf?id={openreview_id}"
        try:
            resolution = resolve_from_page(
                input_value=value,
                page_url=forum_url,
                source_type="openreview",
                source_id=openreview_id,
            )
        except (HTTPError, URLError):
            resolution = fallback_resolution(
                input_value=value,
                source_type="openreview",
                source_id=openreview_id,
                landing_url=forum_url,
                pdf_url=pdf_url,
            )
        if not resolution.pdf_url:
            resolution.pdf_url = pdf_url
            resolution.candidates.append(resolution.pdf_url)
        return resolution

    doi = parse_doi(value)
    if doi:
        encoded = quote(doi, safe="/")
        doi_url = f"https://doi.org/{encoded}"
        try:
            return resolve_from_page(
                input_value=value,
                page_url=doi_url,
                source_type="doi",
                source_id=doi,
            )
        except (HTTPError, URLError):
            return fallback_resolution(
                input_value=value,
                source_type="doi",
                source_id=doi,
                landing_url=doi_url,
                pdf_url="",
            )

    pdf_url = direct_pdf_url(value)
    if pdf_url:
        parsed = urlparse(pdf_url)
        source_id = Path(parsed.path).stem or "paper"
        return fallback_resolution(
            input_value=value,
            source_type="direct_pdf",
            source_id=source_id,
            landing_url=pdf_url,
            pdf_url=pdf_url,
        )

    parsed = urlparse(value.strip())
    if parsed.scheme not in {"http", "https"}:
        raise ValueError("无法识别输入。请提供 arXiv ID、OpenReview 页面、DOI 或可访问的论文链接。")

    return resolve_from_page(
        input_value=value,
        page_url=value.strip(),
        source_type="url",
        source_id=value.strip(),
    )


def destination_path(output_dir: Path, filename: str) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / ensure_pdf_suffix(filename)


def choose_filename(explicit: str | None, resolution: Resolution) -> str:
    if explicit:
        return ensure_pdf_suffix(slugify(explicit, max_length=80))

    if resolution.title:
        prefix = []
        if resolution.year:
            prefix.append(resolution.year)
        if resolution.authors:
            prefix.append(author_token(resolution.authors[0]))
        prefix.append(slugify(resolution.title, max_length=56))
        candidate = "-".join(part for part in prefix if part)
        if candidate:
            return ensure_pdf_suffix(candidate)

    fallback = resolution.source_id or Path(urlparse(resolution.pdf_url).path).stem or "paper"
    return ensure_pdf_suffix(slugify(fallback, max_length=80))


def write_file(content: bytes, dest: Path) -> None:
    dest.write_bytes(content)


def validate_pdf(content: bytes, headers: Any, url: str) -> None:
    content_type = getattr(headers, "get_content_type", lambda: "")()
    if content.startswith(b"%PDF"):
        return
    if content_type == "application/pdf":
        return
    raise ValueError(f"下载结果不是有效 PDF：{url}")


def download_pdf(pdf_url: str) -> tuple[bytes, Any, str]:
    return read_url(pdf_url, "application/pdf,*/*;q=0.8")


def source_record_path(dest: Path) -> Path:
    return dest.with_suffix(".source.json")


def write_source_record(dest: Path, resolution: Resolution, existed: bool) -> Path:
    created_at = datetime.now().isoformat(timespec="seconds")
    record = {
        "task_type": "paper_fetcher",
        "created_at": created_at,
        "input_summary": {
            "reference": resolution.input_value,
            "source_type": resolution.source_type,
            "source_id": resolution.source_id,
        },
        "quality_profile": "economy",
        "model": None,
        "reasoning_effort": None,
        "execution_mode": "local-script",
        "status": "success",
        "output_paths": {
            "pdf": str(dest),
            "source_record": "",
        },
        "error": None,
        "saved_path": str(dest),
        "file_name": dest.name,
        "source_type": resolution.source_type,
        "source_id": resolution.source_id,
        "input_value": resolution.input_value,
        "landing_url": resolution.landing_url,
        "resolved_pdf_url": resolution.pdf_url,
        "candidates": resolution.candidates[:6],
        "title": resolution.title,
        "authors": resolution.authors,
        "year": resolution.year,
        "existed": existed,
        "updated_at": created_at,
    }
    record_path = source_record_path(dest)
    record["output_paths"]["source_record"] = str(record_path)
    record_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    return record_path


def parse_args(argv: Iterable[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="下载论文 PDF 到 outputs/pdfs/")
    parser.add_argument("input", help="论文链接、arXiv ID、OpenReview 页面、DOI 或直接 PDF 链接")
    parser.add_argument("--output-dir", default=str(DEFAULT_OUTPUT_DIR), help="输出目录，默认 outputs/pdfs/")
    parser.add_argument("--filename", help="可选文件名，不带或带 .pdf 均可")
    parser.add_argument("--force", action="store_true", help="如果文件已存在则覆盖")
    parser.add_argument("--resolve-only", action="store_true", help="只解析 PDF 链接与目标路径，不执行下载")
    parser.add_argument("--json", action="store_true", help="输出 JSON 结果，便于网页桥接")
    return parser.parse_args(list(argv))


def emit(payload: dict[str, Any], json_mode: bool) -> None:
    if json_mode:
        print(json.dumps(payload, ensure_ascii=False))
        return
    if payload["status"] == "ok":
        print(payload["message"])
        if payload.get("resolved_pdf_url"):
            print(f"解析到的 PDF 链接：{payload['resolved_pdf_url']}")
        if payload.get("saved_path"):
            print(f"本地保存路径：{payload['saved_path']}")
        if payload.get("source_record"):
            print(f"来源记录：{payload['source_record']}")
        return
    print(payload["error"], file=sys.stderr)
    for candidate in payload.get("candidates", []):
        print(candidate, file=sys.stderr)


def main(argv: Iterable[str]) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)

    try:
        resolution = resolve_input(args.input)
        if not resolution.pdf_url:
            raise ValueError("未解析到稳定的 PDF 链接。")
        filename = choose_filename(args.filename, resolution)
        dest = destination_path(output_dir, filename)
    except (ValueError, HTTPError, URLError) as exc:
        payload = {
            "status": "error",
            "error": f"解析失败：{exc}",
            "candidates": [],
        }
        emit(payload, args.json)
        return 1

    if args.resolve_only:
        payload = {
            "status": "ok",
            "message": "仅解析模式，未执行下载。",
            "saved_path": str(dest),
            "resolved_pdf_url": resolution.pdf_url,
            "landing_url": resolution.landing_url,
            "source_type": resolution.source_type,
            "source_id": resolution.source_id,
            "candidates": resolution.candidates[:6],
            "metadata": asdict(resolution),
        }
        emit(payload, args.json)
        return 0

    if dest.exists() and not args.force:
        record_path = write_source_record(dest, resolution, existed=True)
        payload = {
            "status": "ok",
            "message": "文件已存在，未重复下载。",
            "saved_path": str(dest),
            "resolved_pdf_url": resolution.pdf_url,
            "landing_url": resolution.landing_url,
            "source_type": resolution.source_type,
            "source_id": resolution.source_id,
            "candidates": resolution.candidates[:6],
            "source_record": str(record_path),
        }
        emit(payload, args.json)
        return 0

    try:
        content, headers, final_pdf_url = download_pdf(resolution.pdf_url)
        validate_pdf(content, headers, final_pdf_url)
        resolution.pdf_url = final_pdf_url
        write_file(content, dest)
        record_path = write_source_record(dest, resolution, existed=False)
    except (ValueError, HTTPError, URLError) as exc:
        payload = {
            "status": "error",
            "error": f"下载失败：{exc}",
            "landing_url": resolution.landing_url,
            "resolved_pdf_url": resolution.pdf_url,
            "candidates": resolution.candidates[:6],
        }
        emit(payload, args.json)
        return 1

    payload = {
        "status": "ok",
        "message": "下载成功。",
        "saved_path": str(dest),
        "resolved_pdf_url": resolution.pdf_url,
        "landing_url": resolution.landing_url,
        "source_type": resolution.source_type,
        "source_id": resolution.source_id,
        "title": resolution.title,
        "authors": resolution.authors,
        "year": resolution.year,
        "candidates": resolution.candidates[:6],
        "source_record": str(record_path),
    }
    emit(payload, args.json)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
