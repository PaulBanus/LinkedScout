"""Rate limiter for HTTP requests."""

import asyncio
import time

from beartype import beartype


class RateLimiter:
    """Rate limiter with adaptive backoff for handling rate limits."""

    @beartype
    def __init__(
        self,
        min_delay: float = 1.5,
        backoff_multiplier: float = 2.0,
        max_delay: float = 30.0,
        reset_after: int = 5,
    ) -> None:
        """Initialize rate limiter.

        Args:
            min_delay: Minimum delay in seconds between requests.
            backoff_multiplier: Multiply delay by this value on rate limit hit.
            max_delay: Maximum delay cap in seconds.
            reset_after: Reset backoff after this many successful requests.
        """
        self._min_delay = min_delay
        self._backoff_multiplier = backoff_multiplier
        self._max_delay = max_delay
        self._reset_after = reset_after
        self._current_delay = min_delay
        self._consecutive_successes = 0
        self._last_request: float = 0.0
        self._lock = asyncio.Lock()

    @beartype
    async def acquire(self) -> None:
        """Wait until we can make another request."""
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last_request
            if elapsed < self._current_delay:
                await asyncio.sleep(self._current_delay - elapsed)
            self._last_request = time.monotonic()

    @beartype
    def increase_backoff(self) -> None:
        """Increase delay after rate limit hit (called on 429)."""
        self._current_delay = min(
            self._current_delay * self._backoff_multiplier,
            self._max_delay,
        )
        self._consecutive_successes = 0

    @beartype
    def record_success(self) -> None:
        """Record successful request, potentially reset backoff."""
        self._consecutive_successes += 1
        if self._consecutive_successes >= self._reset_after:
            self.reset_backoff()

    @beartype
    def reset_backoff(self) -> None:
        """Reset delay to minimum."""
        self._current_delay = self._min_delay
        self._consecutive_successes = 0

    async def __aenter__(self) -> "RateLimiter":
        """Context manager entry."""
        await self.acquire()
        return self

    @beartype
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Context manager exit."""
        pass
