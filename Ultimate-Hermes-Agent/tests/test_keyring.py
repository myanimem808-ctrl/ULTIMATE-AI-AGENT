import unittest
from unittest.mock import patch

from ultimate_agent.keyring import AllGeminiKeysFailed, GeminiKeyPool, NoGeminiKeys


class FakeAPIError(Exception):
    def __init__(self, message: str, status_code: int):
        super().__init__(message)
        self.status_code = status_code


class GeminiKeyPoolTests(unittest.TestCase):
    def test_no_keys_has_actionable_error(self):
        pool = GeminiKeyPool()
        with patch("ultimate_agent.keyring.get_gemini_keys", return_value=[]):
            with self.assertRaises(NoGeminiKeys):
                pool.call(lambda key: "should not execute")

    def test_429_falls_back_to_next_key(self):
        pool = GeminiKeyPool()
        with patch("ultimate_agent.keyring.get_gemini_keys", return_value=["key-a", "key-b"]):
            attempted = []

            def operation(key: str) -> str:
                attempted.append(key)
                if key == "key-a":
                    raise FakeAPIError("resource exhausted", 429)
                return "success"

            self.assertEqual(pool.call(operation), "success")
            self.assertEqual(attempted, ["key-a", "key-b"])

    def test_non_retriable_error_does_not_echo_secret(self):
        pool = GeminiKeyPool()
        secret = "my-secret-api-key"
        with patch("ultimate_agent.keyring.get_gemini_keys", return_value=[secret, "second"]):
            with self.assertRaises(RuntimeError) as caught:
                pool.call(lambda key: (_ for _ in ()).throw(FakeAPIError(f"bad request with {secret}", 400)))
            self.assertNotIn(secret, str(caught.exception))

    def test_all_quota_errors_are_reported_without_keys(self):
        pool = GeminiKeyPool()
        secret_keys = ["secret-one", "secret-two"]
        with patch("ultimate_agent.keyring.get_gemini_keys", return_value=secret_keys):
            with self.assertRaises(AllGeminiKeysFailed) as caught:
                pool.call(lambda key: (_ for _ in ()).throw(FakeAPIError("rate limited", 429)))
            self.assertNotIn("secret-one", str(caught.exception))
            self.assertNotIn("secret-two", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
