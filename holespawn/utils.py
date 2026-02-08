"""
Retry with backoff and rate limiting for API calls.
"""

import time
from collections.abc import Callable
from functools import wraps
from typing import TypeVar

F = TypeVar("F", bound=Callable)


def retry_with_backoff(max_retries: int = 3, base_delay: float = 1.0):
    """Decorator: exponential backoff retry on exception."""

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exc = None
            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exc = e
                    if attempt == max_retries - 1:
                        raise
                    delay = base_delay * (2**attempt)
                    try:
                        from loguru import logger

                        logger.warning(
                            "Attempt {}/{} failed, retrying in {:.1f}s: {}",
                            attempt + 1,
                            max_retries,
                            delay,
                            e,
                        )
                    except ImportError:
                        pass
                    time.sleep(delay)
            raise last_exc  # type: ignore

        return wrapper  # type: ignore

    return decorator


def rate_limit(calls_per_minute: float = 20):
    """Decorator: throttle calls to respect rate limit."""
    min_interval = 60.0 / calls_per_minute
    last_called = [0.0]

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args, **kwargs):
            elapsed = time.time() - last_called[0]
            wait = min_interval - elapsed
            if wait > 0:
                time.sleep(wait)
            result = func(*args, **kwargs)
            last_called[0] = time.time()
            return result

        return wrapper  # type: ignore

    return decorator
