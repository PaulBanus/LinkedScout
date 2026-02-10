"""LinkedIn HTTP client for fetching job listings."""

import logging
from typing import TYPE_CHECKING

import httpx
from beartype import beartype

from linkedscout.config import Settings, get_settings
from linkedscout.scraper.parser import HTMLParser
from linkedscout.utils.rate_limiter import RateLimiter

if TYPE_CHECKING:
    from linkedscout.models.job import JobPosting
    from linkedscout.models.search import SearchCriteria

logger = logging.getLogger(__name__)


class LinkedInClient:
    """Async HTTP client for LinkedIn job search API."""

    BASE_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"
    PAGE_SIZE = 25

    @beartype
    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize LinkedIn client.

        Args:
            settings: Application settings. Uses defaults if not provided.
        """
        self._settings = settings or get_settings()
        self._parser = HTMLParser()
        self._rate_limiter = RateLimiter(
            min_delay=self._settings.request_delay,
            backoff_multiplier=self._settings.backoff_multiplier,
            max_delay=self._settings.max_backoff_delay,
            reset_after=self._settings.backoff_reset_after,
        )
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "LinkedInClient":
        """Async context manager entry."""
        self._client = httpx.AsyncClient(
            timeout=self._settings.timeout,
            headers={
                "User-Agent": self._settings.user_agent,
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
                "Accept-Encoding": "gzip, deflate, br",
                "Connection": "keep-alive",
            },
            follow_redirects=True,
        )
        return self

    @beartype
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        """Async context manager exit."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def search(self, criteria: "SearchCriteria") -> list["JobPosting"]:
        """Search for jobs matching the given criteria.

        Args:
            criteria: Search criteria to use.

        Returns:
            List of job postings sorted by date (most recent first).
        """
        if not self._client:
            raise RuntimeError("Client not initialized. Use async context manager.")

        all_jobs: list[JobPosting] = []
        start = 0

        while len(all_jobs) < criteria.max_results:
            async with self._rate_limiter:
                jobs = await self._fetch_page(criteria, start)

            if not jobs:
                # No more results
                break

            all_jobs.extend(jobs)
            start += self.PAGE_SIZE

            # LinkedIn has a hard limit of 1000 results
            if start >= 1000:
                break

        # Sort by posted_at (most recent first)
        all_jobs.sort(
            key=lambda j: (
                (j.posted_at or j.scraped_at).timestamp()
                if (j.posted_at or j.scraped_at)
                else 0.0
            ),
            reverse=True,
        )

        return all_jobs[: criteria.max_results]

    async def _fetch_page(
        self, criteria: "SearchCriteria", start: int
    ) -> list["JobPosting"]:
        """Fetch a single page of job results.

        Args:
            criteria: Search criteria.
            start: Pagination offset.

        Returns:
            List of jobs from this page.
        """
        if not self._client:
            raise RuntimeError("Client not initialized.")

        params = criteria.to_params()
        params["start"] = str(start)

        last_exc: httpx.HTTPStatusError | httpx.RequestError | None = None

        for attempt in range(self._settings.max_retries):
            try:
                response = await self._client.get(self.BASE_URL, params=params)
                response.raise_for_status()
                jobs = self._parser.parse_jobs(response.text, criteria)
                self._rate_limiter.record_success()
                return jobs
            except httpx.HTTPStatusError as e:
                last_exc = e
                if e.response.status_code == 429:
                    self._rate_limiter.increase_backoff()
                    logger.info(
                        "Rate limited (429), backing off (current delay: %.2fs)...",
                        self._rate_limiter._current_delay,
                    )
                    await self._rate_limiter.acquire()
                    continue
                logger.warning(
                    "HTTP error %d on attempt %d/%d, retrying...",
                    e.response.status_code,
                    attempt + 1,
                    self._settings.max_retries,
                )
            except httpx.RequestError as e:
                last_exc = e
                logger.warning(
                    "Network error on attempt %d/%d: %s, retrying...",
                    attempt + 1,
                    self._settings.max_retries,
                    str(e),
                )

        raise RuntimeError(
            f"Failed to fetch page after {self._settings.max_retries} retries"
        ) from last_exc
