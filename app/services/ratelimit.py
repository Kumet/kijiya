import asyncio
import time

from app.config import settings
from app.errors import RateLimitError

WINDOW_SECONDS = 3600


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, list[float]] = {}
        self._lock = asyncio.Lock()

    async def check(self, key: str) -> None:
        now = time.time()
        window_start = now - WINDOW_SECONDS

        async with self._lock:
            hits = [t for t in self._hits.get(key, []) if t > window_start]

            if len(hits) >= settings.rate_limit_per_hour:
                self._hits[key] = hits
                raise RateLimitError("生成回数の上限に達しました。1時間後に再度お試しください。")

            hits.append(now)
            self._hits[key] = hits


rate_limiter = RateLimiter()
