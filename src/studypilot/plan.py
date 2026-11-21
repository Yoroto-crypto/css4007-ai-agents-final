"""Structured study plan: schema, parsing, and validation of generated output.

The planner model is asked for JSON that matches PLAN_SCHEMA. Model output is never
trusted: `parse_plan` checks the structure and the constraints below and raises
ValidationError listing every problem, so the agent can ask the model to fix it.

  - well-formed JSON (a Markdown code fence around it is tolerated)
  - required fields, types, allowed `kind` values, ID formats, real YYYY-MM-DD dates
  - hours per task in a sensible range, and at most MAX_HOURS_PER_DAY per day
  - tasks in chronological order
Checking the plan against the data the agent actually retrieved (coverage of all
deadlines) belongs to output verification, added in weeks 15-16.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from .dates import is_iso_date
from .errors import ValidationError
from .validation import validate_against_schema

MAX_HOURS_PER_DAY = 12.0
TASK_KINDS = ["study", "assignment", "exam_prep", "exam"]

PLAN_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "student_id": {"type": "string", "pattern": r"^S\d{3}$"},
        "tasks": {
            "type": "array",
            "minItems": 1,
            "maxItems": 60,
            "items": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "format": "date"},
                    "course_id": {"type": "string", "pattern": r"^[A-Z]{2,3}\d{3}$"},
                    "task": {"type": "string", "minLength": 3, "maxLength": 200},
                    "hours": {"type": "number", "minimum": 0.5, "maximum": MAX_HOURS_PER_DAY},
                    "kind": {"type": "string", "enum": TASK_KINDS},
                },
                "required": ["date", "course_id", "task", "hours", "kind"],
            },
        },
        "notes": {"type": "string", "maxLength": 500},
    },
    "required": ["student_id", "tasks"],
}


@dataclass(frozen=True)
class StudyTask:
    date: str
    course_id: str
    task: str
    hours: float
    kind: str


@dataclass(frozen=True)
class StudyPlan:
    student_id: str
    tasks: tuple[StudyTask, ...]
    notes: str = ""

    def total_hours(self) -> float:
        return sum(t.hours for t in self.tasks)

    def to_dict(self) -> dict:
        return {
            "student_id": self.student_id,
            "tasks": [vars(t).copy() for t in self.tasks],
            "notes": self.notes,
        }


_FENCE_RE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL | re.IGNORECASE)


def parse_plan(output: str | dict) -> StudyPlan:
    """Parse and validate model output. Raises ValidationError with all problems."""
    if isinstance(output, str):
        text = output.strip()
        match = _FENCE_RE.match(text)
        if match:
            text = match.group(1)
        try:
            data: Any = json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValidationError([f"output is not valid JSON: {exc.msg} (line {exc.lineno})"]) from exc
    else:
        data = output

    problems = validate_against_schema(data, PLAN_SCHEMA, "plan")
    if problems:
        raise ValidationError(problems)

    tasks = data["tasks"]
    for index in range(1, len(tasks)):
        if tasks[index]["date"] < tasks[index - 1]["date"]:
            problems.append(
                f"plan.tasks[{index}]: tasks must be in chronological order "
                f"({tasks[index]['date']} comes after {tasks[index - 1]['date']})"
            )
    per_day: dict[str, float] = defaultdict(float)
    for task in tasks:
        per_day[task["date"]] += task["hours"]
    for day, hours in sorted(per_day.items()):
        if hours > MAX_HOURS_PER_DAY:
            problems.append(f"plan: {day} has {hours:g} hours, the daily limit is {MAX_HOURS_PER_DAY:g}")
    if problems:
        raise ValidationError(problems)

    return StudyPlan(
        student_id=data["student_id"],
        tasks=tuple(
            StudyTask(t["date"], t["course_id"], t["task"], float(t["hours"]), t["kind"]) for t in tasks
        ),
        notes=data.get("notes", ""),
    )


def collect_deadlines(deadlines_by_course: dict[str, list[dict]]) -> list[dict]:
    """Merge per-course deadlines into one chronologically sorted list.

    Entries without a valid YYYY-MM-DD date are skipped. Used later to verify that a
    generated plan covers every retrieved deadline.
    """
    merged: list[dict] = []
    for course_id, items in deadlines_by_course.items():
        for item in items or []:
            if isinstance(item, dict) and is_iso_date(item.get("date")):
                merged.append({"course_id": course_id, **item})
    return sorted(merged, key=lambda d: (d["date"], d["course_id"], str(d.get("title", ""))))
