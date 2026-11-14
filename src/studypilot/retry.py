"""Retry with exponential backoff and jitter.

Only transient errors are retried. Permanent errors propagate immediately, so a
wrong API key or model name never burns the retry budget. The number of retries
comes from MAX_RETRIES (AgentConfig.max_retries): total attempts = 1 + max_retries.
`sleep` and `jitter` are injectable so tests run instantly and deterministically.
"""

from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from .errors import LLMRetriesExhausted, LLMTransientError

T = TypeVar("T")


def backoff_delay(attempt: int, base_delay: float, max_delay: float, jitter: float) -> float:
    """Delay before retry number `attempt+1`: base * 2**attempt, capped, with jitter.

    `jitter` is a number in [0, 1]; the delay is scaled to between 50% and 100%
    so that many clients do not retry at exactly the same moment.
    """
    raw = min(max_delay, base_delay * (2**attempt))
    return raw * (0.5 + 0.5 * jitter)


def call_with_retries(
    func: Callable[[], T],
    *,
    max_retries: int,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
    on_retry: Callable[[int, float, LLMTransientError], None] | None = None,
) -> T:
    """Call `func`, retrying on LLMTransientError up to `max_retries` times."""
    if max_retries < 0:
        raise ValueError("max_retries must be >= 0")
    for attempt in range(max_retries + 1):
        try:
            return func()
        except LLMTransientError as exc:
            if attempt == max_retries:
                raise LLMRetriesExhausted(attempt + 1, exc) from exc
            delay = backoff_delay(attempt, base_delay, max_delay, jitter())
            if on_retry:
                on_retry(attempt + 1, delay, exc)
            sleep(delay)
    raise AssertionError("unreachable")  # pragma: no cover
