"""
Rate limiter for X scraping. Conservative defaults to avoid detection.
"""

import asyncio
import random
import time


class RateLimiter:
    """
    Min delay between page loads, max per 15min and per day, with jitter.
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_per_15min: int = 30,
        max_per_day: int = 500,
    ):
        self.min_delay = min_delay
        self.max_per_15min = max_per_15min
        self.max_per_day = max_per_day
        self._timestamps: list[float] = []
        self._last_request: float = 0.0

    async def wait(self) -> None:
        """Wait until it's safe to make another request."""
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 86400]
        if len(self._timestamps) >= self.max_per_day:
            raise RuntimeError("Daily scraping limit reached. Try again tomorrow.")
        recent = [t for t in self._timestamps if now - t < 900]
        if len(recent) >= self.max_per_15min:
            wait_time = 900 - (now - recent[0]) + random.uniform(5, 15)
            await asyncio.sleep(wait_time)
        elapsed = now - self._last_request
        if elapsed < self.min_delay:
            jitter = random.uniform(0.5, 1.5)
            wait_time = (self.min_delay - elapsed) * jitter
            await asyncio.sleep(max(0, wait_time))
        self._last_request = time.time()
        self._timestamps.append(self._last_request)
