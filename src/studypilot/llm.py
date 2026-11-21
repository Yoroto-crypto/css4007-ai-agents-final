"""LLM client interface.

`LLMClient` is the contract the agent depends on. `MockLLM` returns scripted
responses so tests are deterministic and need no API key. The real client is
`studypilot.gemini.GeminiClient`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class LLMResponse:
    text: str = ""
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens_used: int = 0


class LLMClient(Protocol):
    def generate(
        self, messages: list[dict], tools: list[dict], *, json_schema: dict | None = None
    ) -> LLMResponse:
        """Send messages. `json_schema` asks for a JSON answer (no tools in that call)."""
        ...


class MockLLM:
    """Returns pre-scripted responses in order; records every call it receives."""

    def __init__(self, responses: list[LLMResponse]):
        self._responses = list(responses)
        self.calls: list[dict] = []

    def generate(
        self, messages: list[dict], tools: list[dict], *, json_schema: dict | None = None
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "tools": tools, "json_schema": json_schema})
        if not self._responses:
            raise RuntimeError("MockLLM has no more scripted responses")
        return self._responses.pop(0)
