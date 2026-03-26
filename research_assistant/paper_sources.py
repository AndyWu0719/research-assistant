from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


ARXIV_ID_RE = re.compile(
    r"^(?:arxiv:)?(?P<id>(?:\d{4}\.\d{4,5}|[a-z-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?)$",
    re.IGNORECASE,
)
DOI_RE = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)
URL_RE = re.compile(r"https?://[^\s)>\]]+")
MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)]+)\)")


@dataclass(slots=True)
class PaperReference:
    raw: str
    kind: str
    identifier: str
    normalized: str


def split_references(raw: str) -> list[str]:
    parts = []
    for line in raw.splitlines():
        candidate = line.strip()
        if not candidate:
            continue
        if candidate.startswith("- "):
            candidate = candidate[2:].strip()
        parts.append(candidate)
    return parts


def parse_reference(raw: str) -> PaperReference:
    candidate = raw.strip()
    if not candidate:
        return PaperReference(raw=raw, kind="empty", identifier="", normalized="")

    if Path(candidate).expanduser().exists():
        path = Path(candidate).expanduser().resolve()
        return PaperReference(raw=raw, kind="local_pdf", identifier=path.stem, normalized=str(path))

    arxiv_match = ARXIV_ID_RE.match(candidate)
    if arxiv_match:
        arxiv_id = arxiv_match.group("id")
        return PaperReference(
            raw=raw,
            kind="arxiv",
            identifier=arxiv_id,
            normalized=f"https://arxiv.org/abs/{arxiv_id}",
        )

    doi_match = DOI_RE.search(candidate)
    if doi_match:
        doi = doi_match.group(0)
        return PaperReference(
            raw=raw,
            kind="doi",
            identifier=doi,
            normalized=f"https://doi.org/{doi}",
        )

    if candidate.lower().startswith(("http://", "https://")):
        parsed = urlparse(candidate)
        host = parsed.netloc.lower()
        if "arxiv.org" in host:
            identifier = candidate.rstrip("/").split("/")[-1].replace(".pdf", "")
            return PaperReference(raw=raw, kind="arxiv", identifier=identifier, normalized=candidate)
        if "openreview.net" in host:
            return PaperReference(raw=raw, kind="openreview", identifier=candidate, normalized=candidate)
        if candidate.lower().endswith(".pdf"):
            identifier = Path(parsed.path).stem or "paper"
            return PaperReference(raw=raw, kind="direct_pdf", identifier=identifier, normalized=candidate)
        return PaperReference(raw=raw, kind="url", identifier=candidate, normalized=candidate)

    return PaperReference(raw=raw, kind="text", identifier=candidate, normalized=candidate)


def extract_urls(text: str) -> list[str]:
    urls: list[str] = []
    for _, url in MARKDOWN_LINK_RE.findall(text):
        urls.append(url)
    urls.extend(URL_RE.findall(text))
    deduped: list[str] = []
    seen: set[str] = set()
    for url in urls:
        cleaned = url.rstrip(".,)")
        if cleaned in seen:
            continue
        seen.add(cleaned)
        deduped.append(cleaned)
    return deduped


def choose_paper_url(row: dict[str, str]) -> str:
    candidates: list[str] = []
    for value in row.values():
        candidates.extend(extract_urls(value))
    priority = ["arxiv.org", "openreview.net", "doi.org", ".pdf"]
    for marker in priority:
        for url in candidates:
            lowered = url.lower()
            if marker in lowered:
                return url
    return candidates[0] if candidates else ""


def choose_code_url(row: dict[str, str]) -> str:
    for value in row.values():
        for url in extract_urls(value):
            lowered = url.lower()
            if "github.com" in lowered or "gitlab.com" in lowered or "huggingface.co" in lowered:
                return url
    return ""
