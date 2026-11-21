"""Schema validation for tool arguments and generated output.

A small, dependency-free validator for the subset of JSON Schema we use:
type, required, properties, enum, pattern, minLength/maxLength, minimum/maximum,
minItems/maxItems, items, and format "date" (strict YYYY-MM-DD).

Objects are strict: properties that are not declared in the schema are rejected,
so an LLM cannot smuggle extra parameters into a tool call.
All problems are collected, not only the first one.
"""

from __future__ import annotations

import math
import re
from typing import Any

from .dates import is_iso_date
from .errors import ValidationError
from .tools import TOOLS, ToolSpec


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    raise ValueError(f"unsupported schema type: {expected!r}")


def _describe(value: Any) -> str:
    if isinstance(value, float) and not math.isfinite(value):
        return "non-finite number"
    return type(value).__name__


def validate_against_schema(value: Any, schema: dict, path: str = "$") -> list[str]:
    """Return a list of human-readable problems (empty list means valid)."""
    expected = schema.get("type")
    if expected and not _type_ok(value, expected):
        return [f"{path}: expected {expected}, got {_describe(value)}"]

    problems: list[str] = []
    if "enum" in schema and value not in schema["enum"]:
        problems.append(f"{path}: must be one of {schema['enum']}")

    if expected == "string":
        if "minLength" in schema and len(value) < schema["minLength"]:
            problems.append(f"{path}: must be at least {schema['minLength']} characters")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            problems.append(f"{path}: must be at most {schema['maxLength']} characters")
        if "pattern" in schema and not re.search(schema["pattern"], value):
            problems.append(f"{path}: does not match the required format {schema['pattern']}")
        if schema.get("format") == "date" and not is_iso_date(value):
            problems.append(f"{path}: must be a valid date written as YYYY-MM-DD")

    elif expected in ("integer", "number"):
        if "minimum" in schema and value < schema["minimum"]:
            problems.append(f"{path}: must be >= {schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            problems.append(f"{path}: must be <= {schema['maximum']}")

    elif expected == "array":
        if "minItems" in schema and len(value) < schema["minItems"]:
            problems.append(f"{path}: must contain at least {schema['minItems']} item(s)")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            problems.append(f"{path}: must contain at most {schema['maxItems']} item(s)")
        if "items" in schema:
            for index, item in enumerate(value):
                problems += validate_against_schema(item, schema["items"], f"{path}[{index}]")

    elif expected == "object":
        properties = schema.get("properties")
        for name in schema.get("required", []):
            if name not in value:
                problems.append(f"{path}.{name}: required property is missing")
        if properties is not None:
            for name, item in value.items():
                if name not in properties:
                    problems.append(f"{path}: unexpected property {name!r}")
                else:
                    problems += validate_against_schema(item, properties[name], f"{path}.{name}")
    return problems


def validate_tool_args(
    tool_name: Any, args: Any, registry: dict[str, ToolSpec] | None = None
) -> dict:
    """Validate arguments proposed for a tool. Returns a copy or raises ValidationError.

    This runs BEFORE the tool is executed; a rejected call never reaches the tool.
    """
    registry = TOOLS if registry is None else registry
    if not isinstance(tool_name, str) or tool_name not in registry:
        raise ValidationError([f"unknown tool: {tool_name!r}"])
    problems = validate_against_schema(args, registry[tool_name].parameters, "args")
    if problems:
        raise ValidationError(problems)
    return dict(args)
