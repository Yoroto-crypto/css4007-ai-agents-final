"""Validated tool execution.

    proposed call -> validate arguments -> (rejected | execute) -> ToolResult -> trace

The model only *proposes* a call. Nothing reaches a tool unless its arguments pass
validation. Permission checks, the approval gate, and execution limits are added
around this function in weeks 13-15.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from .errors import ValidationError
from .tools import TOOLS, ToolSpec
from .trace import Trace, redact
from .validation import validate_tool_args


@dataclass
class ToolResult:
    ok: bool
    tool: str
    args: dict
    data: Any = None
    error: str | None = None
    rejected: bool = False  # True when validation stopped the call before execution


def _preview(value: Any, limit: int = 300) -> str:
    try:
        text = json.dumps(value, ensure_ascii=False, default=str)
    except (TypeError, ValueError):
        text = repr(value)
    return redact(text[:limit])


def execute_tool(
    name: Any,
    args: Any,
    *,
    trace: Trace | None = None,
    registry: dict[str, ToolSpec] | None = None,
) -> ToolResult:
    registry = TOOLS if registry is None else registry

    def log(event: str, **data: Any) -> None:
        if trace:
            trace.log(event, **data)

    tool_name = name if isinstance(name, str) else repr(name)

    try:
        clean_args = validate_tool_args(name, args, registry)
    except ValidationError as exc:
        log("tool_rejected", tool=tool_name, args=_preview(args), problems=exc.problems)
        return ToolResult(
            ok=False,
            tool=tool_name,
            args=args if isinstance(args, dict) else {},
            error="Invalid tool call: " + "; ".join(exc.problems),
            rejected=True,
        )

    log("tool_call", tool=tool_name, args=clean_args)
    try:
        data = registry[tool_name].func(**clean_args)
    except Exception as exc:  # a failing tool must not crash the agent
        message = redact(f"tool raised {type(exc).__name__}: {exc}")
        log("tool_error", tool=tool_name, error=message)
        return ToolResult(ok=False, tool=tool_name, args=clean_args, error=message)

    if isinstance(data, dict) and "error" in data:
        log("tool_result", tool=tool_name, ok=False, error=str(data["error"]))
        return ToolResult(ok=False, tool=tool_name, args=clean_args, error=str(data["error"]))

    size = len(data) if hasattr(data, "__len__") else None
    log("tool_result", tool=tool_name, ok=True, items=size)
    return ToolResult(ok=True, tool=tool_name, args=clean_args, data=data)
