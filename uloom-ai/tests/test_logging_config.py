import json
import logging

import pytest

from app.core.logging_config import _JsonFormatter, get_correlation_id


def _make_record(message: str = "hello") -> logging.LogRecord:
    return logging.LogRecord(
        name="app.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_json_formatter_emits_valid_json_with_expected_fields():
    formatter = _JsonFormatter()
    line = formatter.format(_make_record("hello world"))

    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "app.test"
    assert "timestamp" in payload


def test_json_formatter_defaults_correlation_id_to_placeholder_outside_a_request():
    formatter = _JsonFormatter()
    payload = json.loads(formatter.format(_make_record()))
    assert payload["correlation_id"] == "-"


def test_json_formatter_includes_exc_info_when_present():
    formatter = _JsonFormatter()
    try:
        raise ValueError("boom")
    except ValueError:
        record = logging.LogRecord(
            name="app.test",
            level=logging.ERROR,
            pathname=__file__,
            lineno=1,
            msg="failed",
            args=(),
            exc_info=__import__("sys").exc_info(),
        )
    payload = json.loads(formatter.format(record))
    assert "ValueError: boom" in payload["exc_info"]


@pytest.mark.asyncio
async def test_middleware_sets_response_header_and_reuses_inbound_request_id(client):
    response = await client.get("/health", headers={"X-Request-ID": "test-correlation-123"})
    assert response.headers["X-Request-ID"] == "test-correlation-123"


@pytest.mark.asyncio
async def test_middleware_generates_a_request_id_when_none_supplied(client):
    response = await client.get("/health")
    assert response.headers["X-Request-ID"]


def test_get_correlation_id_returns_none_outside_a_request():
    assert get_correlation_id() is None
