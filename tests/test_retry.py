import unittest

from studypilot.errors import LLMPermanentError, LLMRetriesExhausted, LLMTransientError
from studypilot.retry import backoff_delay, call_with_retries


class Flaky:
    """Callable that raises the scripted errors in order, then returns 'ok'."""

    def __init__(self, errors):
        self.errors = list(errors)
        self.calls = 0

    def __call__(self):
        self.calls += 1
        if self.errors:
            raise self.errors.pop(0)
        return "ok"


class TestRetry(unittest.TestCase):
    def run_retry(self, func, max_retries=2, **kw):
        sleeps = []
        result = call_with_retries(func, max_retries=max_retries, sleep=sleeps.append, jitter=lambda: 1.0, **kw)
        return result, sleeps

    def test_success_first_try_does_not_sleep(self):
        result, sleeps = self.run_retry(Flaky([]))
        self.assertEqual((result, sleeps), ("ok", []))

    def test_transient_error_then_success(self):
        func = Flaky([LLMTransientError("503")])
        result, sleeps = self.run_retry(func)
        self.assertEqual(result, "ok")
        self.assertEqual(func.calls, 2)
        self.assertEqual(len(sleeps), 1)

    def test_retries_exhausted_after_max_retries_plus_one_attempts(self):
        func = Flaky([LLMTransientError("x")] * 10)
        sleeps = []
        with self.assertRaises(LLMRetriesExhausted) as ctx:
            call_with_retries(func, max_retries=2, sleep=sleeps.append, jitter=lambda: 1.0)
        self.assertEqual(func.calls, 3)
        self.assertEqual(ctx.exception.attempts, 3)
        self.assertEqual(len(sleeps), 2)

    def test_permanent_error_is_not_retried(self):
        func = Flaky([LLMPermanentError("401")])
        with self.assertRaises(LLMPermanentError):
            self.run_retry(func)
        self.assertEqual(func.calls, 1)

    def test_zero_retries_means_one_attempt(self):
        func = Flaky([LLMTransientError("x")])
        with self.assertRaises(LLMRetriesExhausted):
            self.run_retry(func, max_retries=0)
        self.assertEqual(func.calls, 1)

    def test_backoff_grows_and_is_capped(self):
        delays = [backoff_delay(n, 1.0, 5.0, 1.0) for n in range(5)]
        self.assertEqual(delays, [1.0, 2.0, 4.0, 5.0, 5.0])

    def test_jitter_scales_delay_between_half_and_full(self):
        self.assertEqual(backoff_delay(0, 2.0, 30.0, 0.0), 1.0)
        self.assertEqual(backoff_delay(0, 2.0, 30.0, 1.0), 2.0)

    def test_on_retry_callback_receives_attempt_and_delay(self):
        seen = []
        func = Flaky([LLMTransientError("a"), LLMTransientError("b")])
        self.run_retry(func, on_retry=lambda n, d, e: seen.append((n, d)))
        self.assertEqual(seen, [(1, 1.0), (2, 2.0)])

    def test_negative_max_retries_rejected(self):
        with self.assertRaises(ValueError):
            call_with_retries(lambda: 1, max_retries=-1)


if __name__ == "__main__":
    unittest.main()
