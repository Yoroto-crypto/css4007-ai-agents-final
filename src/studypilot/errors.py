"""Exception hierarchy for LLM calls.

The agent never has to know SDK-specific exception types: every failure of the
model layer is converted into one of these, so recovery logic stays simple:

    LLMTransientError   -> worth retrying (rate limit, 5xx, timeout, network)
    LLMPermanentError   -> retrying cannot help (bad key, unknown model, bad request)
    LLMRetriesExhausted -> transient errors kept happening until the retry limit
    LLMInvalidResponse  -> the call worked but the answer is empty/blocked/malformed
"""

from __future__ import annotations


class ConfigError(RuntimeError):
    """Missing or invalid configuration (API key, model name, SDK not installed)."""


class LLMError(Exception):
    """Base class for all model-layer failures."""


class LLMTransientError(LLMError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class LLMPermanentError(LLMError):
    def __init__(self, message: str, status: int | None = None):
        super().__init__(message)
        self.status = status


class LLMRetriesExhausted(LLMError):
    def __init__(self, attempts: int, last_error: LLMTransientError):
        super().__init__(f"Gave up after {attempts} attempts: {last_error}")
        self.attempts = attempts
        self.last_error = last_error


class LLMInvalidResponse(LLMError):
    """The model answered, but the answer cannot be used."""
