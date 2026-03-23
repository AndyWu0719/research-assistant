from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ui.services.paper_sources import choose_code_url, choose_paper_url


TABLE_SEPARATOR_RE = re.compile(r"^\|?(?:\s*:?-+:?\s*\|)+\s*$")


@dataclass(slots=True)
class LoadedResult:
    path: Path
    content: str
    metadata: dict[str, Any]
    sections: list[tuple[str, str]]
    table_rows: list[dict[str, str]]


def list_recent_markdown(directory: Path, limit: int = 10) -> list[Path]:
    if not directory.exists():
        return []
    files = [path for path in directory.glob("*.md") if path.is_file()]
    return sorted(files, key=lambda item: item.stat().st_mtime, reverse=True)[:limit]


def load_sidecar_json(result_path: Path) -> dict[str, Any]:
    sidecar = result_path.with_suffix(".json")
    if not sidecar.exists():
        return {}
    try:
        return json.loads(sidecar.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def split_markdown_sections(text: str) -> list[tuple[str, str]]:
    sections: list[tuple[str, str]] = []
    current_title = "__overview__"
    current_lines: list[str] = []
    for line in text.splitlines():
        if line.startswith("## "):
            if current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = line[3:].strip()
            current_lines = []
            continue
        current_lines.append(line)
    if current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return [(title, body) for title, body in sections if body]


def extract_table_blocks(text: str) -> list[list[str]]:
    blocks: list[list[str]] = []
    current: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            current.append(stripped)
            continue
        if len(current) >= 2:
            blocks.append(current)
        current = []
    if len(current) >= 2:
        blocks.append(current)
    return blocks


def parse_markdown_table(lines: list[str]) -> list[dict[str, str]]:
    if len(lines) < 2 or not TABLE_SEPARATOR_RE.match(lines[1]):
        return []
    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def parse_table_rows(text: str, metadata: dict[str, Any]) -> list[dict[str, str]]:
    if isinstance(metadata.get("papers"), list):
        papers = []
        for item in metadata["papers"]:
            row = {key: str(value) for key, value in item.items()}
            row.setdefault("paper_url", item.get("paper_url", ""))
            row.setdefault("code_url", item.get("code_url", ""))
            papers.append(row)
        return papers

    for block in extract_table_blocks(text):
        rows = parse_markdown_table(block)
        if rows:
            for row in rows:
                row.setdefault("paper_url", choose_paper_url(row))
                row.setdefault("code_url", choose_code_url(row))
            return rows
    return []


def load_result(result_path: Path) -> LoadedResult:
    content = result_path.read_text(encoding="utf-8")
    metadata = load_sidecar_json(result_path)
    sections = split_markdown_sections(content)
    table_rows = parse_table_rows(content, metadata)
    return LoadedResult(
        path=result_path,
        content=content,
        metadata=metadata,
        sections=sections,
        table_rows=table_rows,
    )


def summarize_metadata(result: LoadedResult) -> dict[str, Any]:
    metadata = dict(result.metadata)
    metadata.setdefault("path", str(result.path))
    metadata.setdefault("updated_at", result.path.stat().st_mtime)
    if result.table_rows and "count" not in metadata:
        metadata["count"] = len(result.table_rows)
    return metadata
