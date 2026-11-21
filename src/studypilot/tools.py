"""Tools backed by local mock data (no real student records).

Week 10 contains the three read-only tools. `save_study_plan` (a consequential
write that needs human approval) is added in weeks 13-15.

Tool results are returned as plain dicts/lists. Errors are returned as
{"error": "..."} so the agent can observe them instead of crashing.
IMPORTANT: tool output is untrusted data; it must never be treated as instructions.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .dates import is_iso_date

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

STUDENT_ID_RE = re.compile(r"^S\d{3}$")
COURSE_ID_RE = re.compile(r"^[A-Z]{2,3}\d{3}$")


def _load(name: str) -> Any:
    with open(DATA_DIR / name, encoding="utf-8") as f:
        return json.load(f)


def get_student_courses(student_id: str) -> list[str] | dict:
    """Return the course IDs a student is enrolled in."""
    if not isinstance(student_id, str) or not STUDENT_ID_RE.match(student_id):
        return {"error": "Invalid student_id format (expected e.g. S001)"}
    students = _load("students.json")
    if student_id not in students:
        return {"error": f"Student not found: {student_id}"}
    return list(students[student_id])


def get_course_info(course_id: str) -> dict:
    """Return title, credits, exam date, weekly workload, and description."""
    if not isinstance(course_id, str) or not COURSE_ID_RE.match(course_id):
        return {"error": "Invalid course_id format (expected e.g. AI101)"}
    courses = _load("courses.json")
    return dict(courses.get(course_id, {"error": "Course not found"}))


def get_course_deadlines(course_id: str, on_or_after: str | None = None) -> list[dict] | dict:
    """Return deadlines [{date, title, weight}] for a course.

    If `on_or_after` (YYYY-MM-DD) is given, earlier deadlines are left out.
    """
    if not isinstance(course_id, str) or not COURSE_ID_RE.match(course_id):
        return {"error": "Invalid course_id format (expected e.g. AI101)"}
    if on_or_after is not None and not is_iso_date(on_or_after):
        return {"error": "Invalid on_or_after (expected a valid date as YYYY-MM-DD)"}
    deadlines = _load("deadlines.json")
    if course_id not in deadlines:
        return {"error": "Course not found"}
    items = list(deadlines[course_id])
    if on_or_after is not None:
        items = [d for d in items if d["date"] >= on_or_after]
    return items


@dataclass(frozen=True)
class ToolSpec:
    name: str
    func: Callable[..., Any]
    description: str
    parameters: dict  # JSON-schema style, used for LLM function declarations
    read_only: bool = True


def _params(properties: dict, required: list[str]) -> dict:
    return {"type": "object", "properties": properties, "required": required}


_STUDENT_ID = {
    "type": "string",
    "pattern": r"^S\d{3}$",
    "description": "Student identifier, e.g. S001",
}
_COURSE_ID = {
    "type": "string",
    "pattern": r"^[A-Z]{2,3}\d{3}$",
    "description": "Course identifier, e.g. AI101",
}
_ON_OR_AFTER = {
    "type": "string",
    "format": "date",
    "description": "Optional. Only return deadlines on or after this date (YYYY-MM-DD).",
}

TOOLS: dict[str, ToolSpec] = {
    "get_student_courses": ToolSpec(
        name="get_student_courses",
        func=get_student_courses,
        description="List the course IDs a student is enrolled in.",
        parameters=_params({"student_id": _STUDENT_ID}, ["student_id"]),
    ),
    "get_course_info": ToolSpec(
        name="get_course_info",
        func=get_course_info,
        description="Get title, credits, exam date and weekly workload of a course.",
        parameters=_params({"course_id": _COURSE_ID}, ["course_id"]),
    ),
    "get_course_deadlines": ToolSpec(
        name="get_course_deadlines",
        func=get_course_deadlines,
        description="Get the list of deadlines (date, title, weight) of a course.",
        parameters=_params(
            {"course_id": _COURSE_ID, "on_or_after": _ON_OR_AFTER}, ["course_id"]
        ),
    ),
}


def declarations() -> list[dict]:
    """Tool declarations ({name, description, parameters}) to register with the LLM."""
    return [
        {"name": t.name, "description": t.description, "parameters": t.parameters}
        for t in TOOLS.values()
    ]
