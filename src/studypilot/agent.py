"""Agent loop (skeleton).

Target architecture (see reports/proposal.md):

    goal -> plan -> select action -> guardrails -> tool -> observe
         -> update state -> continue / replan / stop

Week 10 only defines the public interface and the result type. The loop is built
in weeks 13-14 and the guardrail layer in week 15.
"""

from __future__ import annotations

from dataclasses import dataclass

from .config import AgentConfig
from .llm import LLMClient
from .state import AgentState, Status, StopReason
from .trace import Trace


@dataclass
class AgentResult:
    status: Status
    stop_reason: StopReason | None
    answer: str
    state: AgentState


def run_agent(
    goal: str,
    config: AgentConfig,
    llm: LLMClient,
    trace: Trace | None = None,
) -> AgentResult:
    """Run the agent on a user goal. Not implemented yet (weeks 13-14)."""
    raise NotImplementedError("The agent loop is implemented in weeks 13-14")
