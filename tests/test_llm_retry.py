"""Transient-failure retries for the Anthropic client.

Anthropic reports overload mid-stream: the HTTP response is already 200 when an
SSE ``error`` event arrives, so the SDK's own retry logic never sees it. These
tests pin the application-level retry that covers that gap.
"""

from __future__ import annotations

from typing import Any

import anthropic
import httpx
import pytest

from pitchdeck_onepager.analysis import llm as llm_mod
from pitchdeck_onepager.analysis.llm import AnthropicClient
from pitchdeck_onepager.errors import LLMRequestError

SCHEMA: dict[str, Any] = {"type": "object", "properties": {"ok": {"type": "boolean"}}}


def _overloaded_error(status_code: int = 200) -> anthropic.APIStatusError:
    """The exception the SDK raises for a mid-stream ``overloaded_error`` event."""
    body = {
        "type": "error",
        "error": {"details": None, "type": "overloaded_error", "message": "Overloaded"},
    }
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(status_code, request=request)
    return anthropic.APIStatusError(f"{body}", response=response, body=body)


def _auth_error() -> anthropic.APIStatusError:
    body = {"type": "error", "error": {"type": "authentication_error", "message": "invalid x-api-key"}}
    request = httpx.Request("POST", "https://api.anthropic.com/v1/messages")
    response = httpx.Response(401, request=request)
    return anthropic.AuthenticationError(f"{body}", response=response, body=body)


class _FakeMessage:
    stop_reason = "end_turn"
    model = "claude-opus-5"
    usage = None

    def __init__(self, text: str) -> None:
        block = type("Block", (), {"type": "text", "text": text})()
        self.content = [block]


@pytest.fixture
def client(monkeypatch) -> AnthropicClient:
    monkeypatch.setattr(llm_mod.time, "sleep", lambda _seconds: None)
    return AnthropicClient(
        model="claude-opus-5",
        api_key="sk-ant-not-a-real-key",
        max_tokens=1024,
        effort="high",
        enable_fallback=False,
    )


def test_overloaded_inside_a_200_response_is_classified_transient(client) -> None:
    assert client._is_transient(_overloaded_error(status_code=200)) is True


def test_authentication_failure_is_not_transient(client) -> None:
    assert client._is_transient(_auth_error()) is False


def test_a_transient_overload_is_retried_and_then_succeeds(client, monkeypatch) -> None:
    attempts: list[int] = []

    def fake_stream(self, beta: bool, **kwargs: Any) -> _FakeMessage:
        attempts.append(1)
        if len(attempts) < 3:
            raise _overloaded_error()
        return _FakeMessage('{"ok": true}')

    monkeypatch.setattr(AnthropicClient, "_stream", fake_stream)

    result = client.generate_json("system", "user", SCHEMA)

    assert result.data == {"ok": True}
    assert len(attempts) == 3


def test_persistent_overload_raises_an_actionable_error(client, monkeypatch) -> None:
    def always_overloaded(self, beta: bool, **kwargs: Any) -> _FakeMessage:
        raise _overloaded_error()

    monkeypatch.setattr(AnthropicClient, "_stream", always_overloaded)

    with pytest.raises(LLMRequestError) as excinfo:
        client.generate_json("system", "user", SCHEMA)

    assert "Overloaded" in excinfo.value.message
    assert "temporarily unavailable" in excinfo.value.message
    # The raw error dict must not leak into the user-facing message.
    assert "'type': 'error'" not in excinfo.value.message


def test_non_transient_errors_are_not_retried(client, monkeypatch) -> None:
    attempts: list[int] = []

    def always_unauthorised(self, beta: bool, **kwargs: Any) -> _FakeMessage:
        attempts.append(1)
        raise _auth_error()

    monkeypatch.setattr(AnthropicClient, "_stream", always_unauthorised)

    with pytest.raises(LLMRequestError) as excinfo:
        client.generate_json("system", "user", SCHEMA)

    assert attempts == [1]
    assert "invalid x-api-key" in excinfo.value.message


def test_retry_delay_honours_retry_after(client) -> None:
    exc = _overloaded_error(status_code=429)
    exc.response.headers["retry-after"] = "7"
    assert client._retry_delay(exc, attempt=1) == 7.0


def test_retry_delay_backs_off_within_bounds(client) -> None:
    exc = _overloaded_error()
    first = client._retry_delay(exc, attempt=1)
    fourth = client._retry_delay(exc, attempt=4)
    assert 0 < first <= llm_mod._BACKOFF_BASE_SECONDS
    assert fourth <= llm_mod._BACKOFF_MAX_SECONDS
