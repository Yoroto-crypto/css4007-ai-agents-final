import os
import unittest
from unittest import mock

from studypilot.config import AgentConfig, get_api_key
from studypilot.state import AgentState, Status, StopReason


class TestState(unittest.TestCase):
    def test_initial_state(self):
        state = AgentState(goal="plan for S001")
        self.assertEqual(state.status, Status.RUNNING)
        self.assertIsNone(state.stop_reason)
        self.assertFalse(state.approved_by_user)
        self.assertEqual((state.steps, state.tool_calls, state.retries), (0, 0, 0))

    def test_finish_sets_status_and_reason(self):
        state = AgentState(goal="x")
        state.finish(Status.PARTIAL, StopReason.MAX_STEPS)
        self.assertEqual(state.status, Status.PARTIAL)
        self.assertEqual(state.stop_reason, StopReason.MAX_STEPS)

    def test_record_error(self):
        state = AgentState(goal="x")
        state.record_error("tool failed")
        self.assertEqual(state.errors, ["tool failed"])


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            cfg = AgentConfig.from_env()
        self.assertEqual((cfg.max_steps, cfg.max_tool_calls, cfg.max_retries), (10, 20, 2))

    def test_env_override(self):
        with mock.patch.dict(os.environ, {"MAX_STEPS": "3", "GEMINI_MODEL_FAST": "m-fast"}, clear=True):
            cfg = AgentConfig.from_env()
        self.assertEqual(cfg.max_steps, 3)
        self.assertEqual(cfg.model_fast, "m-fast")

    def test_invalid_limit_rejected(self):
        for bad in ["abc", "0", "-1"]:
            with mock.patch.dict(os.environ, {"MAX_STEPS": bad}, clear=True):
                with self.assertRaises(ValueError):
                    AgentConfig.from_env()

    def test_missing_api_key_raises_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError):
                get_api_key()


if __name__ == "__main__":
    unittest.main()
