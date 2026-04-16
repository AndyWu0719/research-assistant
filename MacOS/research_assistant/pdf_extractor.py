from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from pypdf import PdfReader

from research_assistant.config_store import now_iso
from research_assistant.file_naming import pdf_text_output_path, sidecar_json_path
from research_assistant.language import normalize_language


WHITESPACE_RE = re.compile(r"[ \t]+")
MULTI_BLANK_RE = re.compile(r"\n{3,}")


@dataclass(slots=True)
class PDFExtractionResult:
    source_pdf: Path
    text_path: Path
    sidecar_path: Path
    status: str
    quality: str
    total_pages: int
    pages_with_text: int
    total_characters: int
    average_characters_per_page: float
    empty_pages: list[int]
    warnings: list[str]
    extracted_at: str
    language: str

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["source_pdf"] = str(self.source_pdf)
        payload["text_path"] = str(self.text_path)
        payload["sidecar_path"] = str(self.sidecar_path)
        return payload


def clean_page_text(text: str) -> str:
    value = (text or "").replace("\r", "\n")
    value = re.sub(r"(\w)-\n(\w)", r"\1\2", value)
    value = WHITESPACE_RE.sub(" ", value)
    value = re.sub(r"\n +", "\n", value)
    value = MULTI_BLANK_RE.sub("\n\n", value)
    return value.strip()


def _quality_grade(total_pages: int, pages_with_text: int, total_characters: int, language: str) -> tuple[str, list[str]]:
    warnings: list[str] = []
    coverage = (pages_with_text / total_pages) if total_pages else 0.0
    average_chars = (total_characters / total_pages) if total_pages else 0.0

    if total_pages == 0 or total_characters < 1200:
        warnings.append(
            "The extracted body text is very limited. The result may cover only the title, abstract, or scattered fragments."
            if language == "en-US"
            else "抽取到的正文过少，结果可能只覆盖标题、摘要或零散段落。"
        )
    if coverage < 0.6:
        warnings.append(
            "Many pages did not yield extractable text. The PDF may be scanned, image-based, or poorly compatible with text extraction."
            if language == "en-US"
            else "较多页面未抽取到文本，可能是扫描版 PDF、图片页或版式兼容问题。"
        )
    if average_chars < 350:
        warnings.append(
            "Average text per page is low. Tables, formulas, and experimental details may be missing or heavily distorted."
            if language == "en-US"
            else "平均每页文本较少，表格、公式和实验细节可能缺失或严重变形。"
        )

    if total_pages == 0 or total_characters < 1200 or coverage < 0.45:
        return "poor", warnings
    if coverage < 0.85 or average_chars < 600:
        return "mixed", warnings
    return "good", warnings


def extract_pdf_text(pdf_path: str | Path, force: bool = False, language: str | None = None) -> PDFExtractionResult:
    normalized_language = normalize_language(language)
    source_pdf = Path(pdf_path).expanduser().resolve()
    text_path = pdf_text_output_path(source_pdf.stem)
    sidecar_path = sidecar_json_path(text_path)

    if source_pdf.exists() and text_path.exists() and sidecar_path.exists() and not force:
        try:
            payload = json.loads(sidecar_path.read_text(encoding="utf-8"))
            if payload.get("language") == normalized_language:
                return PDFExtractionResult(
                    source_pdf=source_pdf,
                    text_path=text_path,
                    sidecar_path=sidecar_path,
                    status=str(payload.get("status", "success")),
                    quality=str(payload.get("quality", "mixed")),
                    total_pages=int(payload.get("total_pages", 0)),
                    pages_with_text=int(payload.get("pages_with_text", 0)),
                    total_characters=int(payload.get("total_characters", 0)),
                    average_characters_per_page=float(payload.get("average_characters_per_page", 0.0)),
                    empty_pages=list(payload.get("empty_pages", [])),
                    warnings=[str(item) for item in payload.get("warnings", [])],
                    extracted_at=str(payload.get("extracted_at", now_iso())),
                    language=str(payload.get("language", normalized_language)),
                )
        except Exception:
            pass

    text_path.parent.mkdir(parents=True, exist_ok=True)
    sidecar_path.parent.mkdir(parents=True, exist_ok=True)

    extracted_at = now_iso()
    if not source_pdf.exists():
        result = PDFExtractionResult(
            source_pdf=source_pdf,
            text_path=text_path,
            sidecar_path=sidecar_path,
            status="error",
            quality="poor",
            total_pages=0,
            pages_with_text=0,
            total_characters=0,
            average_characters_per_page=0.0,
            empty_pages=[],
            warnings=[
                "The local PDF file does not exist, so text extraction could not run."
                if normalized_language == "en-US"
                else "本地 PDF 文件不存在，无法执行文本抽取。"
            ],
            extracted_at=extracted_at,
            language=normalized_language,
        )
        sidecar_path.write_text(
            json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return result

    try:
        reader = PdfReader(str(source_pdf))
        page_texts: list[str] = []
        empty_pages: list[int] = []
        total_characters = 0
        for index, page in enumerate(reader.pages, start=1):
            cleaned = clean_page_text(page.extract_text() or "")
            if not cleaned:
                empty_pages.append(index)
            else:
                total_characters += len(cleaned)
            page_texts.append(cleaned)

        total_pages = len(reader.pages)
        pages_with_text = total_pages - len(empty_pages)
        quality, warnings = _quality_grade(total_pages, pages_with_text, total_characters, normalized_language)

        rendered_pages = []
        for index, body in enumerate(page_texts, start=1):
            if not body:
                continue
            rendered_pages.append(f"## Page {index}\n\n{body}")
        cleaned_text = "\n\n".join(rendered_pages).strip()
        if cleaned_text:
            text_path.write_text(cleaned_text + "\n", encoding="utf-8")

        result = PDFExtractionResult(
            source_pdf=source_pdf,
            text_path=text_path,
            sidecar_path=sidecar_path,
            status="success",
            quality=quality,
            total_pages=total_pages,
            pages_with_text=pages_with_text,
            total_characters=total_characters,
            average_characters_per_page=(total_characters / total_pages) if total_pages else 0.0,
            empty_pages=empty_pages,
            warnings=warnings,
            extracted_at=extracted_at,
            language=normalized_language,
        )
    except Exception as exc:
        result = PDFExtractionResult(
            source_pdf=source_pdf,
            text_path=text_path,
            sidecar_path=sidecar_path,
            status="error",
            quality="poor",
            total_pages=0,
            pages_with_text=0,
            total_characters=0,
            average_characters_per_page=0.0,
            empty_pages=[],
            warnings=[
                f"PDF text extraction failed: {exc}"
                if normalized_language == "en-US"
                else f"PDF 文本抽取失败：{exc}"
            ],
            extracted_at=extracted_at,
            language=normalized_language,
        )

    sidecar_path.write_text(
        json.dumps(result.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result
