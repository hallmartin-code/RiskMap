"""Provider-agnostic structured-output LLM client.

The application never asks a model for prose it will render directly - it asks
for JSON conforming to a schema. Each provider enforces that differently, so
:meth:`LLMClient.generate_json` is the only surface the rest of the app uses.

Credentials come from environment variables and are never logged.
"""

from __future__ import annotations

import json
import random
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

from ..config import AppConfig
from ..errors import LLMConfigurationError, LLMRequestError, LLMResponseError
from ..logging_setup import get_logger

log = get_logger("analysis.llm")

#: Beta flag for Anthropic server-side refusal fallbacks.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"

#: Transient failures worth retrying. Anthropic reports mid-stream failures
#: (notably ``overloaded_error``) as an SSE ``error`` event inside a response
#: that already returned HTTP 200, so neither the status code nor the SDK's own
#: HTTP-level retries identify them - classify on the error payload too.
_TRANSIENT_ERROR_TYPES = frozenset(
    {"overloaded_error", "rate_limit_error", "api_error", "timeout_error"}
)
_TRANSIENT_STATUS_CODES = frozenset({408, 409, 429, 500, 502, 503, 504, 529})

#: Retry schedule for transient failures: ~1s, 2s, 4s, 8s between attempts.
_MAX_ATTEMPTS = 5
_BACKOFF_BASE_SECONDS = 1.0
_BACKOFF_MAX_SECONDS = 30.0


def _error_payload(exc: Exception) -> dict[str, Any]:
    """The ``error`` object Anthropic returned, or an empty dict."""
    body = getattr(exc, "body", None)
    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            return error
    return {}


def _error_type(exc: Exception) -> str | None:
    """Anthropic's machine-readable ``error.type``, if the exception carries one."""
    kind = _error_payload(exc).get("type")
    return kind if isinstance(kind, str) else None


def _error_message(exc: Exception) -> str:
    """Readable reason, preferring the API's own message over the raw body dump."""
    message = _error_payload(exc).get("message")
    if isinstance(message, str) and message:
        return message
    return getattr(exc, "message", None) or str(exc)


@dataclass
class LLMResult:
    """One structured response plus usage metadata."""

    data: dict[str, Any]
    model: str
    input_tokens: int | None = None
    output_tokens: int | None = None

    def usage_summary(self) -> str:
        if self.input_tokens is None and self.output_tokens is None:
            return "usage not reported"
        return f"in={self.input_tokens} out={self.output_tokens}"


class LLMClient(ABC):
    """Minimal interface: system + user + schema -> validated JSON object."""

    def __init__(self, model: str) -> None:
        self.model = model

    @abstractmethod
    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str = "response",
    ) -> LLMResult: ...

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        text = (text or "").strip()
        if not text:
            raise LLMResponseError("The model returned an empty response.")
        # Tolerate a fenced block even though structured outputs should not emit one.
        if text.startswith("```"):
            text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            raise LLMResponseError(f"The model returned invalid JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise LLMResponseError("The model returned JSON that was not an object.")
        return parsed


class AnthropicClient(LLMClient):
    """Claude via the Anthropic Messages API with structured outputs."""

    def __init__(self, model: str, api_key: str, max_tokens: int, effort: str, enable_fallback: bool) -> None:
        super().__init__(model)
        try:
            import anthropic
        except ImportError as exc:
            raise LLMConfigurationError(
                "The 'anthropic' package is not installed.", hint="pip install anthropic"
            ) from exc
        self._anthropic = anthropic
        self._client = anthropic.Anthropic(api_key=api_key)
        self._max_tokens = max_tokens
        self._effort = effort
        self._enable_fallback = enable_fallback

    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str = "response",
    ) -> LLMResult:
        kwargs: dict[str, Any] = {
            "model": self.model,
            "max_tokens": self._max_tokens,
            # A stable, cacheable system prefix: the prompt never varies per deck.
            "system": [{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": user}],
            "output_config": {
                "effort": self._effort,
                "format": {"type": "json_schema", "schema": schema},
            },
        }

        message = None
        if self._enable_fallback:
            try:
                message = self._request(beta=True, **kwargs)
            except LLMRequestError:
                # Already retried to exhaustion: the API is down, not the feature.
                # Keep the fallback enabled so the next deck can use it.
                raise
            except Exception as exc:  # noqa: BLE001 - feature probe, see below
                # Server-side fallbacks are a beta feature; older SDKs/accounts
                # reject the parameter. Degrade to the standard endpoint.
                log.debug("Refusal fallback unavailable (%s); using standard endpoint.", exc)
                self._enable_fallback = False

        if message is None:
            try:
                message = self._request(beta=False, **kwargs)
            except self._anthropic.APIStatusError as exc:
                raise LLMRequestError(
                    f"Anthropic API error ({exc.status_code}): {_error_message(exc)}"
                ) from exc
            except self._anthropic.APIConnectionError as exc:
                raise LLMRequestError(f"Could not reach the Anthropic API: {exc}") from exc

        if getattr(message, "stop_reason", None) == "refusal":
            details = getattr(message, "stop_details", None)
            category = getattr(details, "category", None) or "unspecified"
            raise LLMRequestError(
                f"The model declined this request (category: {category}).",
                hint="Try a different provider or model with --provider/--model.",
            )
        if getattr(message, "stop_reason", None) == "max_tokens":
            raise LLMResponseError(
                "The response hit the output token limit before completing.",
                hint="Increase LLM_MAX_TOKENS and retry.",
            )

        text = "".join(block.text for block in message.content if getattr(block, "type", "") == "text")
        usage = getattr(message, "usage", None)
        return LLMResult(
            data=self._parse_json(text),
            model=getattr(message, "model", self.model),
            input_tokens=getattr(usage, "input_tokens", None),
            output_tokens=getattr(usage, "output_tokens", None),
        )

    def _is_transient(self, exc: Exception) -> bool:
        """True when retrying the identical request could plausibly succeed."""
        if isinstance(exc, self._anthropic.APIConnectionError):  # includes timeouts
            return True
        if isinstance(exc, self._anthropic.APIStatusError):
            if _error_type(exc) in _TRANSIENT_ERROR_TYPES:
                return True
            return exc.status_code in _TRANSIENT_STATUS_CODES
        return False

    def _retry_delay(self, exc: Exception, attempt: int) -> float:
        """Server-advised delay when offered, else exponential backoff with jitter."""
        headers = getattr(getattr(exc, "response", None), "headers", None)
        if headers is not None:
            try:
                retry_after = headers.get("retry-after")
                if retry_after is not None:
                    return min(max(float(retry_after), 0.0), _BACKOFF_MAX_SECONDS)
            except (AttributeError, TypeError, ValueError):
                pass  # Malformed header - fall through to backoff.
        backoff = min(_BACKOFF_BASE_SECONDS * 2 ** (attempt - 1), _BACKOFF_MAX_SECONDS)
        # Jitter keeps concurrent retries from re-colliding on the same second.
        return backoff * random.uniform(0.5, 1.0)

    def _request(self, beta: bool, **kwargs: Any):
        """Stream one request, retrying transient API failures with backoff."""
        last: Exception | None = None
        for attempt in range(1, _MAX_ATTEMPTS + 1):
            try:
                return self._stream(beta=beta, **kwargs)
            except Exception as exc:  # noqa: BLE001 - re-raised unless transient
                if not self._is_transient(exc):
                    raise
                last = exc
                if attempt == _MAX_ATTEMPTS:
                    break
                delay = self._retry_delay(exc, attempt)
                log.warning(
                    "Anthropic API transient failure (%s); retrying in %.1fs "
                    "(attempt %d/%d).",
                    _error_type(last) or "connection error",
                    delay,
                    attempt,
                    _MAX_ATTEMPTS,
                )
                time.sleep(delay)

        raise LLMRequestError(
            f"The Anthropic API is temporarily unavailable: {_error_message(last)} "
            f"(gave up after {_MAX_ATTEMPTS} attempts).",
            hint=(
                "Anthropic is overloaded or rate-limiting this key. Wait a minute "
                "and retry, or switch provider with --provider openai."
            ),
        ) from last

    def _stream(self, beta: bool, **kwargs: Any):
        """Stream the request and return the accumulated message.

        Streaming avoids HTTP timeouts on large ``max_tokens`` values.
        """
        if beta:
            with self._client.beta.messages.stream(
                betas=[_FALLBACK_BETA], fallbacks="default", **kwargs
            ) as stream:
                return stream.get_final_message()
        with self._client.messages.stream(**kwargs) as stream:
            return stream.get_final_message()


class OpenAICompatibleClient(LLMClient):
    """OpenAI or any OpenAI-compatible endpoint, via strict JSON schema."""

    def __init__(self, model: str, api_key: str, base_url: str | None, max_tokens: int) -> None:
        super().__init__(model)
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise LLMConfigurationError(
                "The 'openai' package is not installed.", hint="pip install openai"
            ) from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url) if base_url else OpenAI(api_key=api_key)
        self._max_tokens = max_tokens

    def generate_json(
        self,
        system: str,
        user: str,
        schema: dict[str, Any],
        schema_name: str = "response",
    ) -> LLMResult:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                max_completion_tokens=self._max_tokens,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": schema_name, "schema": schema, "strict": True},
                },
            )
        except Exception as exc:  # noqa: BLE001 - provider exception classes vary
            raise LLMRequestError(f"LLM request failed: {exc}") from exc

        choice = response.choices[0]
        if getattr(choice.message, "refusal", None):
            raise LLMRequestError(f"The model declined this request: {choice.message.refusal}")
        if choice.finish_reason == "length":
            raise LLMResponseError(
                "The response hit the output token limit before completing.",
                hint="Increase LLM_MAX_TOKENS and retry.",
            )

        usage = getattr(response, "usage", None)
        return LLMResult(
            data=self._parse_json(choice.message.content or ""),
            model=getattr(response, "model", self.model),
            input_tokens=getattr(usage, "prompt_tokens", None),
            output_tokens=getattr(usage, "completion_tokens", None),
        )


def build_client(config: AppConfig) -> LLMClient:
    """Instantiate the client for the configured provider."""
    model = config.resolved_model
    api_key = config.api_key()

    if config.provider == "anthropic":
        if not api_key:
            raise LLMConfigurationError(
                "ANTHROPIC_API_KEY is not set.", hint="Set it in your environment or .env file."
            )
        return AnthropicClient(
            model=model,
            api_key=api_key,
            max_tokens=config.max_tokens,
            effort=config.effort,
            enable_fallback=config.enable_fallback,
        )

    if config.provider in {"openai", "openai_compatible"}:
        if not api_key:
            raise LLMConfigurationError(
                "OPENAI_API_KEY is not set.", hint="Set it in your environment or .env file."
            )
        if not model:
            raise LLMConfigurationError(
                f"No model configured for provider '{config.provider}'.",
                hint="Set LLM_MODEL or pass --model; the app does not guess model ids.",
            )
        if config.provider == "openai_compatible" and not config.base_url():
            raise LLMConfigurationError(
                "OPENAI_BASE_URL is required for provider 'openai_compatible'."
            )
        return OpenAICompatibleClient(
            model=model, api_key=api_key, base_url=config.base_url(), max_tokens=config.max_tokens
        )

    raise LLMConfigurationError(
        f"Unknown provider '{config.provider}'.",
        hint="Use anthropic, openai or openai_compatible.",
    )
