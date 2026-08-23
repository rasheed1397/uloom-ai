"""Text extraction for uploaded documents (FR-003/FR-004: PDF, DOCX,
Markdown, plain text). Each page/paragraph is kept as its own source-location
entry so Chunk.source_location can cite where an answer came from (FR-007).
"""
import io
from dataclasses import dataclass

import docx
from pypdf import PdfReader


class UnsupportedMimeTypeError(Exception): ...


@dataclass
class ExtractedSegment:
    text: str
    source_location: dict


def extract_text(mime_type: str, content: bytes) -> list[ExtractedSegment]:
    if mime_type == "application/pdf":
        return _extract_pdf(content)
    if mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        return _extract_docx(content)
    if mime_type in ("text/markdown", "text/plain"):
        return _extract_plain_text(content)
    raise UnsupportedMimeTypeError(mime_type)


def _extract_pdf(content: bytes) -> list[ExtractedSegment]:
    reader = PdfReader(io.BytesIO(content))
    segments = []
    for page_number, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if text.strip():
            segments.append(ExtractedSegment(text=text, source_location={"page": page_number}))
    return segments


def _extract_docx(content: bytes) -> list[ExtractedSegment]:
    document = docx.Document(io.BytesIO(content))
    segments = []
    for index, paragraph in enumerate(document.paragraphs):
        if paragraph.text.strip():
            segments.append(ExtractedSegment(text=paragraph.text, source_location={"paragraph": index}))
    return segments


def _extract_plain_text(content: bytes) -> list[ExtractedSegment]:
    text = content.decode("utf-8", errors="replace")
    return [ExtractedSegment(text=text, source_location={"offset": 0})] if text.strip() else []
