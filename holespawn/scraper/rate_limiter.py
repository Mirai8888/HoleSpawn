"""
Rate limiter for X scraping. Conservative defaults to avoid detection.
Includes exponential backoff with jitter for 429/5xx responses.
"""

import asyncio
import logging
import random
import time

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Min delay between page loads, max per 15min and per day, with jitter.
    Includes exponential backoff for rate-limited responses.
    """

    def __init__(
        self,
        min_delay: float = 2.0,
        max_per_15min: int = 30,
        max_per_day: int = 500,
        base_backoff: float = 5.0,
        max_backoff: float = 300.0,
    ):
        self.min_delay = min_delay
        self.max_per_15min = max_per_15min
        self.max_per_day = max_per_day
        self.base_backoff = base_backoff
        self.max_backoff = max_backoff
        self._timestamps: list[float] = []
        self._last_request: float = 0.0
        self._consecutive_429s: int = 0

    async def wait(self) -> None:
        """Wait until it's safe to make another request."""
        now = time.time()
        self._timestamps = [t for t in self._timestamps if now - t < 86400]
        if len(self._timestamps) >= self.max_per_day:
            raise RuntimeError("Daily scraping limit reached. Try again tomorrow.")
        recent = [t for t in self._timestamps if now - t < 900]
        if len(recent) >= self.max_per_15min:
            wait_time = 900 - (now - recent[0]) + random.uniform(5, 15)
            logger.info("15-min rate limit reached, waiting %.1fs", wait_time)
            await asyncio.sleep(wait_time)
        elapsed = now - self._last_request
        if elapsed < self.min_delay:
            jitter = random.uniform(0.5, 1.5)
            wait_time = (self.min_delay - elapsed) * jitter
            await asyncio.sleep(max(0, wait_time))
        self._last_request = time.time()
        self._timestamps.append(self._last_request)

    async def backoff_on_rate_limit(self) -> float:
        """
        Exponential backoff with jitter for 429 responses.
        Returns the time waited.
        """
        self._consecutive_429s += 1
        delay = min(
            self.base_backoff * (2 ** (self._consecutive_429s - 1)),
            self.max_backoff,
        )
        # Add jitter: ±25%
        jitter = delay * random.uniform(-0.25, 0.25)
        actual_delay = max(1.0, delay + jitter)
        logger.warning(
            "Rate limited (429). Backoff attempt %d: waiting %.1fs",
            self._consecutive_429s,
            actual_delay,
        )
        await asyncio.sleep(actual_delay)
        return actual_delay

    async def backoff_on_error(self, attempt: int) -> float:
        """
        Backoff for transient errors (5xx, network). Uses attempt number.
        Returns the time waited.
        """
        delay = min(
            self.base_backoff * (2 ** (attempt - 1)),
            self.max_backoff,
        )
        jitter = delay * random.uniform(-0.25, 0.25)
        actual_delay = max(1.0, delay + jitter)
        logger.warning(
            "Transient error. Backoff attempt %d: waiting %.1fs",
            attempt,
            actual_delay,
        )
        await asyncio.sleep(actual_delay)
        return actual_delay

    def reset_backoff(self) -> None:
        """Reset consecutive 429 counter on successful request."""
        self._consecutive_429s = 0
