"""Token-range chunking (FR-004). A pluggable strategy behind a plain
function per Detailed Design Sec.5.2 - swap the body (or add a new function
and select between them in DocumentService) if a different strategy is
needed later; nothing above this module depends on tiktoken directly.
"""
from dataclasses import dataclass
from functools import lru_cache

import tiktoken
from tiktoken import Encoding

from app.services.document_parsing import ExtractedSegment


@lru_cache
def _encoding() -> Encoding:
    # Loaded lazily (not at import time): fetching the BPE vocab file is a
    # network call on first use, and importing this module must not require
    # network access just to start the app.
    return tiktoken.get_encoding("cl100k_base")


@dataclass
class TextChunk:
    content: str
    token_count: int
    source_location: dict


def chunk_segments(segments: list[ExtractedSegment], token_size: int) -> list[TextChunk]:
    chunks: list[TextChunk] = []
    for segment in segments:
        tokens = _encoding().encode(segment.text)
        if not tokens:
            continue
        for start in range(0, len(tokens), token_size):
            window = tokens[start : start + token_size]
            location = dict(segment.source_location)
            if start > 0:
                location["token_offset"] = start
            chunks.append(
                TextChunk(
                    content=_encoding().decode(window),
                    token_count=len(window),
                    source_location=location,
                )
            )
    return chunks
