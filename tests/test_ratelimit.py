from unittest.mock import patch

import pytest

from app.config import settings
from app.errors import RateLimitError
from app.services.ratelimit import RateLimiter


async def test_allows_requests_under_the_limit(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_hour", 3)
    limiter = RateLimiter()

    for _ in range(3):
        await limiter.check("1.2.3.4")


async def test_raises_when_limit_exceeded(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_hour", 2)
    limiter = RateLimiter()

    await limiter.check("1.2.3.4")
    await limiter.check("1.2.3.4")

    with pytest.raises(RateLimitError):
        await limiter.check("1.2.3.4")


async def test_resets_after_window_expires(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_hour", 1)
    limiter = RateLimiter()
    clock = [1000.0]

    with patch("app.services.ratelimit.time.time", side_effect=lambda: clock[0]):
        await limiter.check("1.2.3.4")
        clock[0] += 3601
        await limiter.check("1.2.3.4")


async def test_limits_are_independent_per_key(monkeypatch):
    monkeypatch.setattr(settings, "rate_limit_per_hour", 1)
    limiter = RateLimiter()

    await limiter.check("1.2.3.4")
    await limiter.check("5.6.7.8")
