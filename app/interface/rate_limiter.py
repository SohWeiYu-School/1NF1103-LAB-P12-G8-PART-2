"""RateLimiter: one assessment per user per cooldown window."""

import time


class RateLimiter:
    """Stops one user starting assessments faster than the policy allows, because every
    assessment costs AI calls. It remembers when each user last started one.

    policy is the policy's "assessment_rate_limit" block: {"enabled", "cooldown_seconds"}.
    """

    DEFAULT_COOLDOWN_SECONDS: int = 60

    def __init__(self, policy: dict | None = None) -> None:
        settings = policy or {}
        self.__enabled: bool = bool(settings.get("enabled", True))
        self.__cooldown_seconds: int = int(settings.get("cooldown_seconds", RateLimiter.DEFAULT_COOLDOWN_SECONDS))
        self.__last_started: dict[str, float] = {}     # user key -> when their last assessment started

    def check(self, user_key: str) -> tuple[bool, int]:
        """(True, 0) if this user may start an assessment now, otherwise (False, seconds left to wait)."""
        if not self.__enabled:
            return True, 0
        last = self.__last_started.get(user_key)
        if last is None:
            return True, 0
        elapsed = time.time() - last
        if elapsed >= self.__cooldown_seconds:
            return True, 0
        return False, int(self.__cooldown_seconds - elapsed) + 1

    def record(self, user_key: str) -> None:
        """Note that this user has just started an assessment. The cooldown starts now."""
        self.__last_started[user_key] = time.time()

    def reset(self) -> None:
        """Forget every user (used when the settings change and in tests)."""
        self.__last_started.clear()
