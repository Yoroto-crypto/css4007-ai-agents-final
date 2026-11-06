"""Execution trace (JSON Lines) with secret redaction.

We log observable actions and concise summaries only: never API keys and never
raw private reasoning.
"""

from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any

# Google API keys look like "AIza" followed by 35 URL-safe characters.
_GOOGLE_KEY_RE = re.compile(r"AIza[0-9A-Za-z_\-]{35}")
REDACTED = "[REDACTED]"


def redact(value: Any) -> Any:
    """Recursively remove API keys from any JSON-like value."""
    if isinstance(value, str):
        text = _GOOGLE_KEY_RE.sub(REDACTED, value)
        secret = os.environ.get("GEMINI_API_KEY", "")
        if secret:
            text = text.replace(secret, REDACTED)
        return text
    if isinstance(value, dict):
        return {k: redact(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(v) for v in value]
    return value


class Trace:
    """Append-only trace. Keeps events in memory and optionally writes to a file."""

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None
        self.events: list[dict] = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    def log(self, event: str, **data: Any) -> dict:
        record = redact({"ts": time.time(), "event": event, **data})
        self.events.append(record)
        if self.path:
            with open(self.path, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return record
