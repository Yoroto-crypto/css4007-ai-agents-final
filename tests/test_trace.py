import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from studypilot.trace import REDACTED, Trace, redact

FAKE_KEY = "AIza" + "A" * 35  # fake key shaped like a Google API key


class TestTrace(unittest.TestCase):
    def test_redacts_google_style_key_in_nested_data(self):
        out = redact({"a": ["see " + FAKE_KEY], "b": {"c": FAKE_KEY}})
        self.assertNotIn(FAKE_KEY, json.dumps(out))
        self.assertIn(REDACTED, json.dumps(out))

    def test_redacts_configured_secret(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "my-secret-value"}):
            self.assertEqual(redact("token=my-secret-value"), f"token={REDACTED}")

    def test_trace_writes_jsonl_without_secrets(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sub" / "trace.jsonl"
            trace = Trace(path)
            trace.log("tool_call", tool="get_course_info", args={"course_id": "AI101"})
            trace.log("error", message="failed with " + FAKE_KEY)
            lines = path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual(json.loads(lines[0])["event"], "tool_call")
        self.assertNotIn(FAKE_KEY, lines[1])
        self.assertEqual(len(trace.events), 2)


if __name__ == "__main__":
    unittest.main()
