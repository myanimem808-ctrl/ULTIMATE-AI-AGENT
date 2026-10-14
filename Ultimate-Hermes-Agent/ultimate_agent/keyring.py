from __future__ import annotations

import re
import threading
from typing import Any, Callable

from .config import get_gemini_keys


class NoGeminiKeys(RuntimeError):
    pass


class AllGeminiKeysFailed(RuntimeError):
    pass


class GeminiKeyPool:
    """Round-robin key selection with request-level failover.

    A key is tried at most once per generation attempt. This is failover, not a
    way to bypass quota: keys on the same project can share quota limits.
    """
    def __init__(self) -> None:
        self._cursor = 0
        self._lock = threading.Lock()
        self._last_success: int | None = None

    def ordered_keys(self) -> list[str]:
        keys = get_gemini_keys()
        if not keys:
            raise NoGeminiKeys(
                "No Gemini API key is configured. Add one or more keys in Settings, "
                "or set GEMINI_API_KEYS in the environment."
            )
        with self._lock:
            start = self._cursor % len(keys)
            return keys[start:] + keys[:start]

    def mark_success(self, key: str) -> None:
        keys = get_gemini_keys()
        with self._lock:
            try:
                index = keys.index(key)
            except ValueError:
                return
            self._last_success = index
            self._cursor = (index + 1) % max(1, len(keys))

    @staticmethod
    def _status_code(exc: BaseException) -> int | None:
        for attr in ("status_code", "code", "http_status"):
            value = getattr(exc, attr, None)
            try:
                if value is not None:
                    return int(value)
            except (TypeError, ValueError):
                pass
        response = getattr(exc, "response", None)
        value = getattr(response, "status_code", None)
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @classmethod
    def _should_failover(cls, exc: BaseException) -> bool:
        code = cls._status_code(exc)
        if code in {401, 403, 408, 409, 425, 429, 500, 502, 503, 504}:
            return True
        message = str(exc).lower()
        tokens = (
            "api key not valid", "invalid api key", "permission denied", "unauthorized",
            "resource_exhausted", "quota", "rate limit", "too many requests", "timed out",
            "timeout", "connection reset", "temporarily unavailable", "service unavailable",
        )
        return any(token in message for token in tokens)

    def call(self, operation: Callable[[str], Any]) -> Any:
        keys = self.ordered_keys()
        failures: list[str] = []
        last_exc: BaseException | None = None
        for key in keys:
            try:
                result = operation(key)
                self.mark_success(key)
                return result
            except Exception as exc:  # provider exceptions vary by SDK release
                last_exc = exc
                code = self._status_code(exc)
                failures.append(f"HTTP {code}" if code else type(exc).__name__)
                if not self._should_failover(exc):
                    raise RuntimeError(
                        f"Gemini request failed ({type(exc).__name__}). Check the model name and request settings."
                    ) from exc
        summary = ", ".join(failures) if failures else "no attempts completed"
        raise AllGeminiKeysFailed(
            f"Every configured Gemini key failed ({summary}). Check key validity, API access, quota, and model availability."
        ) from last_exc


key_pool = GeminiKeyPool()
