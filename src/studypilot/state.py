"""Explicit agent state (A-level requirement).

The state is plain data so it can be inspected, logged, and tested. The agent
loop (weeks 13-14) reads and updates it after every observation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Status(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"  # goal achieved and verified
    PARTIAL = "partial"  # some subtasks done, some failed or missing
    FAILED = "failed"  # goal could not be achieved
    UNVERIFIED = "unverified"  # result produced but not verified


class StopReason(str, Enum):
    GOAL_COMPLETED = "goal_completed"
    NEEDS_INFO = "needs_info"
    TOOL_FAILURE = "tool_failure"
    MAX_STEPS = "max_steps"
    MAX_TOOL_CALLS = "max_tool_calls"
    MAX_RETRIES = "max_retries"
    TOKEN_LIMIT = "token_limit"
    USER_REJECTED = "user_rejected"


@dataclass
class PlanStep:
    description: str
    status: str = "pending"  # pending | done | failed | skipped


@dataclass
class AgentState:
    goal: str
    plan: list[PlanStep] = field(default_factory=list)
    student_id: str | None = None
    courses: list[str] = field(default_factory=list)
    course_info: dict[str, dict] = field(default_factory=dict)
    deadlines: dict[str, list[dict]] = field(default_factory=dict)
    errors: list[str] = field(default_factory=list)
    steps: int = 0
    tool_calls: int = 0
    retries: int = 0
    tokens_used: int = 0
    approved_by_user: bool = False
    status: Status = Status.RUNNING
    stop_reason: StopReason | None = None

    def record_error(self, message: str) -> None:
        self.errors.append(message)

    def finish(self, status: Status, reason: StopReason) -> None:
        self.status = status
        self.stop_reason = reason
