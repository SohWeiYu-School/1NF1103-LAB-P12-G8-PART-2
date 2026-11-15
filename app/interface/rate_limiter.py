"""RateLimiter: one assessment per user per cooldown window."""

import time


class RateLimiter:
    """Stops one user starting assessments faster than the policy allows, because every
    assessment costs AI calls. It remembers when each user last started one.

    App hands in the policy's "assessment_rate_limit" settings: cooldown_seconds, and enabled
    (False lets every assessment start).
    """

    DEFAULT_COOLDOWN_SECONDS: int = 60

    def __init__(self, cooldown_seconds: int = DEFAULT_COOLDOWN_SECONDS, enabled: bool = True) -> None:
        if isinstance(cooldown_seconds, bool) or not isinstance(cooldown_seconds, int) or cooldown_seconds < 0:
            raise ValueError("the assessment cooldown must be a whole number of seconds, 0 or more "
                             f"(got {cooldown_seconds!r})")
        if not isinstance(enabled, bool):
            raise ValueError(f"the rate limit's enabled setting must be true or false (got {enabled!r})")
        self.__enabled: bool = enabled
        self.__cooldown_seconds: int = cooldown_seconds
        self.__last_run: dict[str, float] = {}     # user key -> when their last assessment started

    def check(self, user_key: str) -> tuple[bool, int]:
        """(True, 0) if this user may start an assessment now, otherwise (False, seconds left to wait)."""
        if not self.__enabled:
            return True, 0
        last = self.__last_run.get(user_key)
        if last is None:
            return True, 0
        elapsed = time.time() - last
        if elapsed >= self.__cooldown_seconds:
            return True, 0
        return False, int(self.__cooldown_seconds - elapsed) + 1

    def record(self, user_key: str) -> None:
        """Note that this user has just started an assessment. The cooldown starts now."""
        self.__last_run[user_key] = time.time()

    def reset(self) -> None:
        """Forget every user (used when the settings change and in tests)."""
        self.__last_run.clear()
