from unittest.mock import patch

from app.services import chunking
from app.services.document_parsing import ExtractedSegment


class _WhitespaceEncoding:
    """Stand-in for tiktoken's real encoding: splits/joins on spaces. Avoids
    a real test dependency on tiktoken's network vocab download (see the
    lazy-load comment on chunking._encoding) while still exercising the
    actual windowing logic in chunk_segments.
    """

    def encode(self, text: str) -> list[str]:
        # Real tiktoken returns [] for "", unlike str.split(" ") which
        # returns [""] - match that so empty-segment handling is testable.
        return text.split(" ") if text else []

    def decode(self, tokens: list[str]) -> str:
        return " ".join(tokens)


def test_chunk_segments_splits_into_windows_of_token_size():
    segments = [ExtractedSegment(text="one two three four five six seven", source_location={"page": 1})]

    with patch.object(chunking, "_encoding", return_value=_WhitespaceEncoding()):
        chunks = chunking.chunk_segments(segments, token_size=3)

    assert [c.content for c in chunks] == ["one two three", "four five six", "seven"]
    assert [c.token_count for c in chunks] == [3, 3, 1]


def test_chunk_segments_preserves_source_location_and_adds_token_offset():
    segments = [ExtractedSegment(text="one two three four", source_location={"page": 2})]

    with patch.object(chunking, "_encoding", return_value=_WhitespaceEncoding()):
        chunks = chunking.chunk_segments(segments, token_size=2)

    assert chunks[0].source_location == {"page": 2}
    assert chunks[1].source_location == {"page": 2, "token_offset": 2}


def test_chunk_segments_skips_empty_segments():
    segments = [
        ExtractedSegment(text="", source_location={"page": 1}),
        ExtractedSegment(text="content", source_location={"page": 2}),
    ]

    with patch.object(chunking, "_encoding", return_value=_WhitespaceEncoding()):
        chunks = chunking.chunk_segments(segments, token_size=5)

    assert len(chunks) == 1
    assert chunks[0].source_location == {"page": 2}


def test_chunk_segments_handles_multiple_segments_independently():
    segments = [
        ExtractedSegment(text="a b c", source_location={"page": 1}),
        ExtractedSegment(text="d e f", source_location={"page": 2}),
    ]

    with patch.object(chunking, "_encoding", return_value=_WhitespaceEncoding()):
        chunks = chunking.chunk_segments(segments, token_size=10)

    assert [c.content for c in chunks] == ["a b c", "d e f"]
