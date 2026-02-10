"""Tests for rate limiter."""

import asyncio
import time

import pytest

from linkedscout.utils.rate_limiter import RateLimiter


class TestRateLimiter:
    """Tests for RateLimiter."""

    @pytest.mark.asyncio
    async def test_first_acquire_immediate(self) -> None:
        """Test that first acquire is immediate."""
        limiter = RateLimiter(min_delay=0.1)

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # First acquire should be nearly instant
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_enforces_minimum_delay(self) -> None:
        """Test that rate limiter enforces minimum delay."""
        limiter = RateLimiter(min_delay=0.1)

        await limiter.acquire()

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Second acquire should wait at least min_delay
        assert elapsed >= 0.09  # Small tolerance

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """Test using rate limiter as context manager."""
        limiter = RateLimiter(min_delay=0.05)

        async with limiter:
            pass

        start = time.monotonic()
        async with limiter:
            pass
        elapsed = time.monotonic() - start

        assert elapsed >= 0.04  # Small tolerance

    @pytest.mark.asyncio
    async def test_concurrent_access_serializes(self) -> None:
        """Test rate limiter serializes concurrent access."""
        limiter = RateLimiter(min_delay=0.05)
        results: list[float] = []

        async def acquire_and_record() -> None:
            await limiter.acquire()
            results.append(time.monotonic())

        # Run 3 concurrent acquires
        await asyncio.gather(
            acquire_and_record(),
            acquire_and_record(),
            acquire_and_record(),
        )

        # All should complete
        assert len(results) == 3

        # Verify they're spaced at least min_delay apart
        results.sort()
        for i in range(1, len(results)):
            diff = results[i] - results[i - 1]
            assert diff >= 0.04  # Small tolerance

    @pytest.mark.asyncio
    async def test_zero_delay(self) -> None:
        """Test rate limiter with zero delay."""
        limiter = RateLimiter(min_delay=0.0)

        start = time.monotonic()
        await limiter.acquire()
        await limiter.acquire()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should complete very quickly with no delay
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_delay_after_waiting(self) -> None:
        """Test that delay resets after waiting longer than min_delay."""
        limiter = RateLimiter(min_delay=0.05)

        await limiter.acquire()
        await asyncio.sleep(0.1)  # Wait longer than min_delay

        start = time.monotonic()
        await limiter.acquire()
        elapsed = time.monotonic() - start

        # Should be immediate since we already waited
        assert elapsed < 0.02

    @pytest.mark.asyncio
    async def test_context_manager_exception_handling(self) -> None:
        """Test that context manager works with exceptions."""
        limiter = RateLimiter(min_delay=0.05)

        with pytest.raises(ValueError):
            async with limiter:
                raise ValueError("test error")

        # Should still be able to acquire after exception
        await limiter.acquire()

    @pytest.mark.asyncio
    async def test_multiple_rate_limiters_independent(self) -> None:
        """Test that multiple rate limiters are independent."""
        limiter1 = RateLimiter(min_delay=0.1)
        limiter2 = RateLimiter(min_delay=0.1)

        await limiter1.acquire()

        start = time.monotonic()
        await limiter2.acquire()
        elapsed = time.monotonic() - start

        # limiter2 should be immediate since it's independent
        assert elapsed < 0.02

    @pytest.mark.asyncio
    async def test_default_min_delay(self) -> None:
        """Test default min_delay value."""
        limiter = RateLimiter()

        # Default should be 1.5 seconds
        assert limiter._min_delay == 1.5

    @pytest.mark.asyncio
    async def test_increase_backoff_doubles_delay(self) -> None:
        """Test that increase_backoff doubles the delay."""
        limiter = RateLimiter(min_delay=0.1, backoff_multiplier=2.0)

        assert limiter._current_delay == 0.1

        limiter.increase_backoff()
        assert limiter._current_delay == 0.2

        limiter.increase_backoff()
        assert limiter._current_delay == 0.4

    @pytest.mark.asyncio
    async def test_backoff_respects_max_delay(self) -> None:
        """Test that backoff doesn't exceed max_delay."""
        limiter = RateLimiter(min_delay=0.1, backoff_multiplier=2.0, max_delay=0.3)

        limiter.increase_backoff()  # 0.2
        limiter.increase_backoff()  # Should cap at 0.3, not 0.4

        assert limiter._current_delay == 0.3

        limiter.increase_backoff()  # Should stay at 0.3
        assert limiter._current_delay == 0.3

    @pytest.mark.asyncio
    async def test_record_success_resets_after_threshold(self) -> None:
        """Test that backoff resets after enough successful requests."""
        limiter = RateLimiter(min_delay=0.1, backoff_multiplier=2.0, reset_after=3)

        # Increase backoff first
        limiter.increase_backoff()
        limiter.increase_backoff()
        assert limiter._current_delay == 0.4

        # Record successes
        limiter.record_success()
        assert limiter._current_delay == 0.4  # Not reset yet

        limiter.record_success()
        assert limiter._current_delay == 0.4  # Not reset yet

        limiter.record_success()
        assert limiter._current_delay == 0.1  # Reset to min_delay

    @pytest.mark.asyncio
    async def test_record_success_does_not_reset_before_threshold(self) -> None:
        """Test that partial successes don't reset backoff."""
        limiter = RateLimiter(min_delay=0.1, backoff_multiplier=2.0, reset_after=5)

        limiter.increase_backoff()
        assert limiter._current_delay == 0.2

        # Record a few successes (less than threshold)
        limiter.record_success()
        limiter.record_success()
        assert limiter._current_delay == 0.2  # Should not reset yet

    @pytest.mark.asyncio
    async def test_reset_backoff_returns_to_minimum(self) -> None:
        """Test that reset_backoff returns delay to minimum."""
        limiter = RateLimiter(min_delay=0.1, backoff_multiplier=2.0)

        limiter.increase_backoff()
        limiter.increase_backoff()
        assert limiter._current_delay == 0.4

        limiter.reset_backoff()
        assert limiter._current_delay == 0.1
        assert limiter._consecutive_successes == 0

    @pytest.mark.asyncio
    async def test_adaptive_parameters_configurable(self) -> None:
        """Test that adaptive parameters are configurable."""
        limiter = RateLimiter(
            min_delay=0.5,
            backoff_multiplier=3.0,
            max_delay=10.0,
            reset_after=10,
        )

        assert limiter._min_delay == 0.5
        assert limiter._backoff_multiplier == 3.0
        assert limiter._max_delay == 10.0
        assert limiter._reset_after == 10
        assert limiter._current_delay == 0.5

        limiter.increase_backoff()
        assert limiter._current_delay == 1.5  # 0.5 * 3.0

    def test_rate_limiter_negative_min_delay(self) -> None:
        """Test that negative min_delay is rejected."""
        with pytest.raises(ValueError, match="min_delay must be >= 0"):
            RateLimiter(min_delay=-1.0)

    def test_rate_limiter_backoff_multiplier_too_small(self) -> None:
        """Test that backoff_multiplier < 1.0 is rejected."""
        with pytest.raises(ValueError, match="backoff_multiplier must be >= 1.0"):
            RateLimiter(backoff_multiplier=0.5)

    def test_rate_limiter_max_delay_less_than_min(self) -> None:
        """Test that max_delay < min_delay is rejected."""
        with pytest.raises(ValueError, match="max_delay must be >= min_delay"):
            RateLimiter(min_delay=5.0, max_delay=1.0)

    def test_rate_limiter_negative_reset_after(self) -> None:
        """Test that negative reset_after is rejected."""
        with pytest.raises(ValueError, match="reset_after must be >= 0"):
            RateLimiter(reset_after=-1)

    def test_rate_limiter_valid_boundary_values(self) -> None:
        """Test that boundary values (zeros) are accepted."""
        limiter = RateLimiter(min_delay=0.0, max_delay=0.0, reset_after=0)
        assert limiter._min_delay == 0.0
        assert limiter._max_delay == 0.0
        assert limiter._reset_after == 0
