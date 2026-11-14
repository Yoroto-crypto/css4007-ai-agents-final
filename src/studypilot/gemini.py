"""Gemini client built on the official `google-genai` SDK.

Design notes
- The SDK client is created lazily and can be injected, so unit tests run with a
  fake client and never need a network connection or an API key.
- Requests use plain dicts (the SDK accepts dicts everywhere), so this module does
  not depend on SDK types and stays easy to test.
- Every SDK exception is converted into our own hierarchy (see errors.py) and the
  retry policy is applied here, in one place.
- Tool results and the multi-turn tool loop are added in week 13.
"""

from __future__ import annotations

import time
from typing import Any, Callable

from .config import AgentConfig, get_api_key
from .errors import (
    ConfigError,
    LLMError,
    LLMInvalidResponse,
    LLMPermanentError,
    LLMTransientError,
)
from .llm import LLMResponse, ToolCall
from .retry import call_with_retries
from .trace import Trace, redact

# HTTP status codes worth retrying: request timeout, rate limit, server errors.
_TRANSIENT_STATUS = {408, 429}

_PERMANENT_HINTS = {
    400: "bad request: check the model name, parameters, and tool declarations",
    401: "the API key was rejected: check GEMINI_API_KEY",
    403: "access denied: the key is not allowed to use this model or API",
    404: "model not found: check GEMINI_MODEL_FAST / GEMINI_MODEL_PLANNER",
}

# JSON-schema keys that we keep for our own validation but do not send to Gemini.
_UNSENT_SCHEMA_KEYS = {"pattern"}


def _network_error_types() -> tuple[type[BaseException], ...]:
    types: tuple[type[BaseException], ...] = (TimeoutError, ConnectionError)
    try:  # httpx is a dependency of google-genai
        import httpx

        types += (httpx.TransportError,)
    except ImportError:  # pragma: no cover
        pass
    return types


def classify_error(exc: BaseException) -> LLMError:
    """Convert any exception raised by the SDK into one of our LLMError types."""
    if isinstance(exc, LLMError):
        return exc
    status = getattr(exc, "code", None)
    detail = redact(f"{type(exc).__name__}: {exc}")
    if isinstance(status, int):
        if status in _TRANSIENT_STATUS or 500 <= status < 600:
            return LLMTransientError(f"HTTP {status}: {detail}", status=status)
        hint = _PERMANENT_HINTS.get(status, "request rejected")
        return LLMPermanentError(f"HTTP {status} ({hint}): {detail}", status=status)
    if isinstance(exc, _network_error_types()):
        return LLMTransientError(f"network error: {detail}")
    return LLMPermanentError(f"unexpected error: {detail}")


def to_contents(messages: list[dict]) -> tuple[str | None, list[dict]]:
    """Split our messages into (system_instruction, Gemini `contents`).

    Accepts roles: system, user, assistant (or model). Text only for now.
    """
    system_parts: list[str] = []
    contents: list[dict] = []
    for msg in messages:
        role, text = msg.get("role"), msg.get("content")
        if not isinstance(text, str):
            raise ValueError("message content must be a string")
        if role == "system":
            system_parts.append(text)
        elif role == "user":
            contents.append({"role": "user", "parts": [{"text": text}]})
        elif role in ("assistant", "model"):
            contents.append({"role": "model", "parts": [{"text": text}]})
        else:
            raise ValueError(f"unsupported message role: {role!r}")
    if not contents:
        raise ValueError("at least one user message is required")
    return ("\n\n".join(system_parts) or None), contents


def _strip_schema(schema: Any) -> Any:
    if isinstance(schema, dict):
        return {k: _strip_schema(v) for k, v in schema.items() if k not in _UNSENT_SCHEMA_KEYS}
    if isinstance(schema, list):
        return [_strip_schema(v) for v in schema]
    return schema


def to_function_declarations(tools: list[dict]) -> list[dict]:
    """Prepare tool declarations ({name, description, parameters}) for Gemini."""
    return [
        {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": _strip_schema(tool["parameters"]),
        }
        for tool in tools
    ]


def _extract_text(response: Any) -> str:
    """Concatenate the visible text parts of the first candidate.

    Reading parts directly avoids the SDK warning that `response.text` prints when the
    answer also contains a function call, and skips "thought" parts of thinking models.
    Falls back to `response.text` for simple responses.
    """
    try:
        parts = response.candidates[0].content.parts
    except (AttributeError, IndexError, TypeError):
        parts = None
    if parts:
        return "".join(
            part.text
            for part in parts
            if isinstance(getattr(part, "text", None), str) and not getattr(part, "thought", False)
        )
    try:
        return response.text or ""
    except Exception:  # SDK raises/returns nothing when there is no text part
        return ""


def parse_response(response: Any) -> LLMResponse:
    """Turn an SDK response into LLMResponse, or raise LLMInvalidResponse."""
    calls = getattr(response, "function_calls", None) or []
    tool_calls: list[ToolCall] = []
    for call in calls:
        name = getattr(call, "name", None)
        if not isinstance(name, str) or not name:
            raise LLMInvalidResponse("function call without a valid name")
        tool_calls.append(ToolCall(name=name, args=dict(getattr(call, "args", None) or {})))

    text = _extract_text(response)

    if not text.strip() and not tool_calls:
        feedback = getattr(response, "prompt_feedback", None)
        reason = getattr(feedback, "block_reason", None)
        if reason:
            raise LLMInvalidResponse(f"prompt was blocked by the API: {reason}")
        raise LLMInvalidResponse("model returned an empty response")

    usage = getattr(response, "usage_metadata", None)
    tokens = getattr(usage, "total_token_count", 0)
    return LLMResponse(
        text=text,
        tool_calls=tool_calls,
        tokens_used=tokens if isinstance(tokens, int) else 0,
    )


class GeminiClient:
    """Implements the LLMClient protocol on top of the Gemini API."""

    def __init__(
        self,
        config: AgentConfig,
        model: str | None = None,
        *,
        client: Any = None,
        trace: Trace | None = None,
        sleep: Callable[[float], None] = time.sleep,
        temperature: float = 0.0,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
    ):
        self.config = config
        self.model = model or config.model_fast or config.model_planner
        if not self.model:
            raise ConfigError(
                "No model configured: set GEMINI_MODEL_FAST or GEMINI_MODEL_PLANNER in .env"
            )
        self.trace = trace
        self.temperature = temperature
        self._sleep = sleep
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._client = client if client is not None else self._create_sdk_client()

    @staticmethod
    def _create_sdk_client() -> Any:
        api_key = get_api_key()
        try:
            from google import genai
        except ImportError as exc:
            raise ConfigError("google-genai is not installed: run pip install -r requirements.txt") from exc
        return genai.Client(api_key=api_key)

    def _log(self, event: str, **data: Any) -> None:
        if self.trace:
            self.trace.log(event, **data)

    def generate(self, messages: list[dict], tools: list[dict]) -> LLMResponse:
        system, contents = to_contents(messages)
        config: dict[str, Any] = {"temperature": self.temperature}
        if system:
            config["system_instruction"] = system
        declarations = to_function_declarations(tools)
        if declarations:
            config["tools"] = [{"function_declarations": declarations}]

        def attempt() -> Any:
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=config
                )
            except Exception as exc:  # converted, never leaked
                raise classify_error(exc) from exc

        def on_retry(number: int, delay: float, error: LLMTransientError) -> None:
            self._log("llm_retry", model=self.model, retry=number, delay_s=round(delay, 2), error=str(error))

        self._log("llm_request", model=self.model, messages=len(contents), tools=len(declarations))
        started = time.monotonic()
        try:
            response = call_with_retries(
                attempt,
                max_retries=self.config.max_retries,
                base_delay=self._base_delay,
                max_delay=self._max_delay,
                sleep=self._sleep,
                on_retry=on_retry,
            )
            result = parse_response(response)
        except LLMError as exc:
            self._log("llm_error", model=self.model, error_type=type(exc).__name__, error=str(exc))
            raise
        self._log(
            "llm_response",
            model=self.model,
            seconds=round(time.monotonic() - started, 3),
            tokens=result.tokens_used,
            tool_calls=[c.name for c in result.tool_calls],
            text_chars=len(result.text),
        )
        return result
