"""RateLimiter: one assessment per user per cooldown window."""

from app.interface import rate_limiter
from app.interface.rate_limiter import RateLimiter


def test_a_first_assessment_is_always_allowed():
    assert RateLimiter({"cooldown_seconds": 60}).check("officer-1") == (True, 0)


def test_a_second_assessment_inside_the_cooldown_is_refused_with_the_wait():
    limiter = RateLimiter({"cooldown_seconds": 60})
    limiter.record("officer-1")
    allowed, wait = limiter.check("officer-1")
    assert allowed is False
    assert 59 <= wait <= 61


def test_each_user_has_their_own_cooldown():
    limiter = RateLimiter({"cooldown_seconds": 60})
    limiter.record("officer-1")
    assert limiter.check("officer-2") == (True, 0)


def test_after_the_cooldown_the_user_may_start_again(monkeypatch):
    limiter = RateLimiter({"cooldown_seconds": 60})
    limiter.record("officer-1")
    later = rate_limiter.time.time() + 61
    monkeypatch.setattr(rate_limiter.time, "time", lambda: later)
    assert limiter.check("officer-1") == (True, 0)


def test_a_limiter_that_is_switched_off_allows_everything():
    limiter = RateLimiter({"enabled": False, "cooldown_seconds": 60})
    limiter.record("officer-1")
    assert limiter.check("officer-1") == (True, 0)


def test_with_no_settings_the_cooldown_is_one_minute():
    limiter = RateLimiter()
    limiter.record("officer-1")
    assert limiter.check("officer-1")[0] is False


def test_reset_forgets_every_user():
    limiter = RateLimiter({"cooldown_seconds": 60})
    limiter.record("officer-1")
    limiter.reset()
    assert limiter.check("officer-1") == (True, 0)
