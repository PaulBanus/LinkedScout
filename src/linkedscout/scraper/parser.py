"""HTML parser for LinkedIn job listings."""

import logging
import re
from datetime import datetime, timedelta
from typing import Any

from beartype import beartype
from selectolax.parser import HTMLParser as SelectolaxParser

from linkedscout.models.job import JobPosting
from linkedscout.models.search import SearchCriteria, WorkModel

logger = logging.getLogger(__name__)


class HTMLParser:
    """Parser for LinkedIn job listing HTML."""

    # Base URL for job postings
    JOB_BASE_URL = "https://www.linkedin.com/jobs/view/"

    @beartype
    def parse_jobs(
        self, html: str, criteria: SearchCriteria | None = None
    ) -> list[JobPosting]:
        """Parse job listings from HTML response.

        Args:
            html: Raw HTML from LinkedIn jobs API.
            criteria: Optional search criteria used to fetch these jobs.

        Returns:
            List of parsed job postings.
        """
        parser = SelectolaxParser(html)
        jobs: list[JobPosting] = []
        seen_ids: set[str] = set()

        # Each job card is in a <li> element or div with base-card class
        for card in parser.css("li.jobs-search__result-card, div.base-card"):
            job = self._parse_job_card(card, criteria)
            if job and job.id not in seen_ids:
                seen_ids.add(job.id)
                jobs.append(job)

        return jobs

    @beartype
    def _parse_job_card(
        self, card: Any, criteria: SearchCriteria | None = None
    ) -> JobPosting | None:
        """Parse a single job card element.

        Args:
            card: The HTML element for a job card.
            criteria: Optional search criteria used to fetch this job.

        Returns:
            JobPosting if parsing successful, None otherwise.
        """
        try:
            # Extract job ID from data attribute or link
            job_id = self._extract_job_id(card)
            if not job_id:
                return None

            # Title
            title_elem = card.css_first(
                "h3.base-search-card__title, h3.job-search-card__title, span.sr-only"
            )
            title = title_elem.text(strip=True) if title_elem else "Unknown"

            # Company
            company_elem = card.css_first(
                "h4.base-search-card__subtitle a, "
                "a.hidden-nested-link, "
                "h4.base-search-card__subtitle"
            )
            company = company_elem.text(strip=True) if company_elem else "Unknown"

            # Location
            location_elem = card.css_first(
                "span.job-search-card__location, span.base-search-card__metadata"
            )
            location = location_elem.text(strip=True) if location_elem else "Unknown"

            # Posted time
            time_elem = card.css_first("time")
            posted_at = None
            if time_elem:
                datetime_attr = time_elem.attributes.get("datetime")
                if datetime_attr:
                    posted_at = self._parse_datetime(datetime_attr)
                else:
                    posted_at = self._parse_relative_time(time_elem.text(strip=True))

            # URL
            url = f"{self.JOB_BASE_URL}{job_id}"

            # Description snippet (if available)
            desc_elem = card.css_first("p.job-search-card__snippet")
            description = desc_elem.text(strip=True) if desc_elem else None

            # Salary (if available)
            salary_elem = card.css_first(
                "span.job-search-card__salary-info, span.base-search-card__salary"
            )
            salary = salary_elem.text(strip=True) if salary_elem else None

            # Check if remote
            is_remote = self._check_remote(card, location, criteria)

            # Applicants count
            applicants_elem = card.css_first("span.job-search-card__applicant-count")
            applicants = applicants_elem.text(strip=True) if applicants_elem else None

            return JobPosting(
                id=job_id,
                title=title,
                company=company,
                location=location,
                url=url,
                posted_at=posted_at,
                description_snippet=description,
                salary=salary,
                is_remote=is_remote,
                applicants_count=applicants,
            )

        except (ValueError, AttributeError, TypeError, KeyError):
            logger.warning("Failed to parse job card", exc_info=True)
            return None

    @beartype
    def _extract_job_id(self, card: Any) -> str | None:
        """Extract job ID from card element."""
        # Try data-entity-urn attribute
        if hasattr(card, "attributes"):
            urn = card.attributes.get("data-entity-urn", "")
            if urn:
                match = re.search(r"(\d+)$", urn)
                if match:
                    return match.group(1)

        # Try extracting from link href
        if hasattr(card, "css_first"):
            link = card.css_first("a.base-card__full-link, a[href*='/jobs/view/']")
            if link:
                href = link.attributes.get("href", "")
                match = re.search(r"/jobs/view/(\d+)", href)
                if match:
                    return match.group(1)

        return None

    @beartype
    def _parse_datetime(self, datetime_str: str) -> datetime | None:
        """Parse ISO datetime string."""
        try:
            # Handle various datetime formats
            if "T" in datetime_str:
                return datetime.fromisoformat(datetime_str.replace("Z", "+00:00"))
            return datetime.fromisoformat(datetime_str)
        except ValueError:
            return None

    @beartype
    def _parse_relative_time(self, text: str) -> datetime | None:
        """Parse relative time text like '2 days ago'."""
        text = text.lower().strip()
        now = datetime.now()

        patterns: list[tuple[str, Any]] = [
            (r"(\d+)\s*minute", lambda m: now - timedelta(minutes=int(m.group(1)))),
            (r"(\d+)\s*hour", lambda m: now - timedelta(hours=int(m.group(1)))),
            (r"(\d+)\s*day", lambda m: now - timedelta(days=int(m.group(1)))),
            (r"(\d+)\s*week", lambda m: now - timedelta(weeks=int(m.group(1)))),
            (r"(\d+)\s*month", lambda m: now - timedelta(days=int(m.group(1)) * 30)),
            (r"just now|moments ago", lambda _: now),
        ]

        for pattern, converter in patterns:
            match = re.search(pattern, text)
            if match:
                result: datetime = converter(match)
                return result

        return None

    @beartype
    def _check_remote(
        self, card: Any, location: str, criteria: SearchCriteria | None = None
    ) -> bool:
        """Check if job is remote based on card content, location, and search criteria.

        Args:
            card: The HTML element for a job card.
            location: The job location string.
            criteria: Optional search criteria used to fetch this job.

        Returns:
            True if the job is remote, False otherwise.
        """
        # If search criteria specified ONLY remote work model, trust LinkedIn's filter
        if criteria and criteria.work_models == [WorkModel.REMOTE]:
            return True

        # Otherwise, try to infer from HTML content
        location_lower = location.lower()
        if "remote" in location_lower:
            return True

        # Check for remote badge with specific selectors
        # Avoid overly broad selectors like [class*='remote'] that could match unrelated classes
        if hasattr(card, "css_first"):
            remote_badge = card.css_first(
                "span.job-search-card__remote-label, "
                "span.remote-badge, "
                "div.job-remote-label, "
                "span[class='remote-label']"
            )
            if remote_badge:
                return True

        return False
