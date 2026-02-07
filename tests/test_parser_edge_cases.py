"""Tests for parser edge cases."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import ClassVar

import pytest

from linkedscout.models.search import SearchCriteria, WorkModel
from linkedscout.scraper.parser import HTMLParser


class TestRelativeTimeParsing:
    """Tests for relative time parsing."""

    @pytest.fixture
    def parser(self) -> HTMLParser:
        """Create a parser instance."""
        return HTMLParser()

    @pytest.mark.parametrize(
        "text,expected_delta",
        [
            ("5 minutes ago", timedelta(minutes=5)),
            ("1 minute ago", timedelta(minutes=1)),
            ("30 minutes ago", timedelta(minutes=30)),
            ("2 hours ago", timedelta(hours=2)),
            ("1 hour ago", timedelta(hours=1)),
            ("24 hours ago", timedelta(hours=24)),
            ("3 days ago", timedelta(days=3)),
            ("1 day ago", timedelta(days=1)),
            ("1 week ago", timedelta(weeks=1)),
            ("2 weeks ago", timedelta(weeks=2)),
            ("1 month ago", timedelta(days=30)),
            ("2 months ago", timedelta(days=60)),
        ],
    )
    def test_parse_relative_time_various_formats(
        self, parser: HTMLParser, text: str, expected_delta: timedelta
    ):
        """Test parsing various relative time formats."""
        result = parser._parse_relative_time(text)

        assert result is not None
        # Allow 2 seconds tolerance for test execution time
        expected = datetime.now() - expected_delta
        assert abs((result - expected).total_seconds()) < 2

    @pytest.mark.parametrize(
        "text",
        [
            "just now",
            "moments ago",
            "Just Now",
            "JUST NOW",
        ],
    )
    def test_parse_relative_time_just_now(self, parser: HTMLParser, text: str):
        """Test parsing 'just now' and similar phrases."""
        result = parser._parse_relative_time(text)

        assert result is not None
        # Should be very close to now
        assert abs((result - datetime.now()).total_seconds()) < 2

    @pytest.mark.parametrize(
        "text",
        [
            "invalid time",
            "yesterday",
            "last year",
            "",
            "posted recently",
        ],
    )
    def test_parse_relative_time_invalid(self, parser: HTMLParser, text: str):
        """Test invalid time strings return None."""
        result = parser._parse_relative_time(text)

        assert result is None

    def test_parse_relative_time_case_insensitive(self, parser: HTMLParser):
        """Test that parsing is case insensitive."""
        result_lower = parser._parse_relative_time("2 days ago")
        result_upper = parser._parse_relative_time("2 DAYS AGO")
        result_mixed = parser._parse_relative_time("2 Days Ago")

        assert result_lower is not None
        assert result_upper is not None
        assert result_mixed is not None

        # All should be approximately equal
        assert abs((result_lower - result_upper).total_seconds()) < 2
        assert abs((result_lower - result_mixed).total_seconds()) < 2

    def test_parse_relative_time_with_whitespace(self, parser: HTMLParser):
        """Test parsing with extra whitespace."""
        result = parser._parse_relative_time("  5 minutes ago  ")

        assert result is not None


class TestDateTimeParsing:
    """Tests for datetime string parsing."""

    @pytest.fixture
    def parser(self) -> HTMLParser:
        """Create a parser instance."""
        return HTMLParser()

    def test_parse_iso_datetime(self, parser: HTMLParser):
        """Test parsing ISO datetime string."""
        result = parser._parse_datetime("2024-01-15T10:30:00")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30

    def test_parse_iso_datetime_with_z(self, parser: HTMLParser):
        """Test parsing ISO datetime with Z suffix."""
        result = parser._parse_datetime("2024-01-15T10:30:00Z")

        assert result is not None
        assert result.year == 2024

    def test_parse_iso_date_only(self, parser: HTMLParser):
        """Test parsing ISO date only."""
        result = parser._parse_datetime("2024-01-15")

        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 15

    def test_parse_invalid_datetime(self, parser: HTMLParser):
        """Test parsing invalid datetime returns None."""
        result = parser._parse_datetime("not-a-date")

        assert result is None

    def test_parse_empty_datetime(self, parser: HTMLParser):
        """Test parsing empty string returns None."""
        result = parser._parse_datetime("")

        assert result is None


class TestRemoteDetection:
    """Tests for remote job detection."""

    @pytest.fixture
    def parser(self) -> HTMLParser:
        """Create a parser instance."""
        return HTMLParser()

    @pytest.mark.parametrize(
        "location",
        [
            "Remote",
            "REMOTE",
            "remote",
            "Remote, USA",
            "Paris (Remote)",
            "Fully Remote",
            "100% Remote",
        ],
    )
    def test_check_remote_from_location(self, parser: HTMLParser, location: str):
        """Test remote detection from location string."""
        # Create a mock card with no remote badge
        class MockCard:
            def css_first(self, _selector: str) -> None:
                return None

        result = parser._check_remote(MockCard(), location)

        assert result is True

    @pytest.mark.parametrize(
        "location",
        [
            "Paris, France",
            "New York, NY",
            "On-site",
            "Hybrid - London",
        ],
    )
    def test_check_remote_non_remote_location(self, parser: HTMLParser, location: str):
        """Test non-remote locations without badge."""
        class MockCard:
            def css_first(self, _selector: str) -> None:
                return None

        result = parser._check_remote(MockCard(), location)

        assert result is False

    def test_check_remote_with_badge(self, parser: HTMLParser):
        """Test remote detection with remote badge element."""
        class MockBadge:
            pass

        class MockCard:
            def css_first(self, selector: str) -> MockBadge | None:
                if "remote" in selector.lower():
                    return MockBadge()
                return None

        result = parser._check_remote(MockCard(), "Paris, France")

        assert result is True

    def test_check_remote_from_search_criteria(self, parser: HTMLParser):
        """Test remote detection when search criteria specifies remote-only."""
        class MockCard:
            def css_first(self, _selector: str) -> None:
                return None

        # Create criteria with only remote work model
        criteria = SearchCriteria(
            keywords="Python",
            location="France",
            work_models=[WorkModel.REMOTE],
        )

        # Even though location doesn't contain "remote" and no badge exists,
        # it should return True because search criteria was remote-only
        result = parser._check_remote(MockCard(), "France", criteria)

        assert result is True

    def test_check_remote_multiple_work_models(self, parser: HTMLParser):
        """Test that with multiple work models, HTML parsing is used."""
        class MockCard:
            def css_first(self, _selector: str) -> None:
                return None

        # Create criteria with multiple work models
        criteria = SearchCriteria(
            keywords="Python",
            location="France",
            work_models=[WorkModel.REMOTE, WorkModel.HYBRID],
        )

        # With multiple work models, should fall back to HTML parsing
        # Since location doesn't contain "remote" and no badge, should be False
        result = parser._check_remote(MockCard(), "France", criteria)

        assert result is False


class TestJobIdExtraction:
    """Tests for job ID extraction."""

    @pytest.fixture
    def parser(self) -> HTMLParser:
        """Create a parser instance."""
        return HTMLParser()

    def test_extract_job_id_from_urn(self, parser: HTMLParser):
        """Test extracting job ID from data-entity-urn attribute."""
        class MockCard:
            attributes: ClassVar[dict[str, str]] = {
                "data-entity-urn": "urn:li:jobPosting:123456789"
            }

            def css_first(self, _selector: str) -> None:
                return None

        result = parser._extract_job_id(MockCard())

        assert result == "123456789"

    def test_extract_job_id_from_link(self, parser: HTMLParser):
        """Test extracting job ID from link href."""
        class MockLink:
            attributes: ClassVar[dict[str, str]] = {
                "href": "https://www.linkedin.com/jobs/view/987654321"
            }

        class MockCard:
            attributes: ClassVar[dict[str, str]] = {}

            def css_first(self, selector: str) -> MockLink | None:
                if "jobs/view" in selector:
                    return MockLink()
                return None

        result = parser._extract_job_id(MockCard())

        assert result == "987654321"

    def test_extract_job_id_no_id_found(self, parser: HTMLParser):
        """Test extraction when no ID is found."""
        class MockCard:
            attributes: ClassVar[dict[str, str]] = {}

            def css_first(self, _selector: str) -> None:
                return None

        result = parser._extract_job_id(MockCard())

        assert result is None


class TestParseJobs:
    """Tests for the main parse_jobs method."""

    @pytest.fixture
    def parser(self) -> HTMLParser:
        """Create a parser instance."""
        return HTMLParser()

    def test_parse_empty_html(self, parser: HTMLParser):
        """Test parsing empty HTML returns empty list."""
        result = parser.parse_jobs("<html><body></body></html>")

        assert result == []

    def test_parse_jobs_with_remote_criteria_sets_is_remote(self, parser: HTMLParser):
        """Test that jobs from remote-only search have is_remote=True.

        This test demonstrates the bug fix: when searching with remote-only criteria,
        jobs should have is_remote=True even if the location field doesn't contain
        "remote" and no remote badge is present in the HTML.

        Before the fix: This test would FAIL because is_remote would be False.
        After the fix: This test PASSES because we trust the search criteria.
        """
        # HTML with jobs that don't have "remote" in location or badges
        # This simulates real LinkedIn responses where remote jobs from
        # France/Europe don't have "remote" in the location field
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:111">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/111">
                        <span class="sr-only">SRE</span>
                    </a>
                    <h3 class="base-search-card__title">SRE</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Tech Company</a>
                    </h4>
                    <span class="job-search-card__location">France</span>
                </div>
            </li>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:222">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/222">
                        <span class="sr-only">DevOps Engineer</span>
                    </a>
                    <h3 class="base-search-card__title">DevOps Engineer</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Another Company</a>
                    </h4>
                    <span class="job-search-card__location">Europe</span>
                </div>
            </li>
        </body>
        </html>
        """

        # Create remote-only search criteria
        criteria = SearchCriteria(
            keywords="DevOps",
            location="France",
            work_models=[WorkModel.REMOTE],
        )

        # Parse with criteria
        jobs = parser.parse_jobs(html, criteria)

        # All jobs should have is_remote=True because they came from a remote-only search
        assert len(jobs) == 2
        assert jobs[0].is_remote is True, (
            f"Job '{jobs[0].title}' at '{jobs[0].location}' should be remote "
            f"because search criteria specified remote-only work model"
        )
        assert jobs[1].is_remote is True, (
            f"Job '{jobs[1].title}' at '{jobs[1].location}' should be remote "
            f"because search criteria specified remote-only work model"
        )

    def test_parse_jobs_without_criteria_uses_html_parsing(self, parser: HTMLParser):
        """Test that without criteria, parser falls back to HTML-based detection."""
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:333">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/333">
                        <span class="sr-only">Developer</span>
                    </a>
                    <h3 class="base-search-card__title">Developer</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Company</a>
                    </h4>
                    <span class="job-search-card__location">France</span>
                </div>
            </li>
        </body>
        </html>
        """

        # Parse without criteria - should use HTML parsing
        jobs = parser.parse_jobs(html, criteria=None)

        # Without criteria and no "remote" in location/badge, should be False
        assert len(jobs) == 1
        assert jobs[0].is_remote is False

    def test_parse_html_with_no_job_cards(self, parser: HTMLParser):
        """Test parsing HTML without job cards."""
        html = """
        <html>
        <body>
            <div class="other-content">No jobs here</div>
        </body>
        </html>
        """
        result = parser.parse_jobs(html)

        assert result == []

    def test_parse_deduplicates_jobs(self, parser: HTMLParser):
        """Test that duplicate job IDs are deduplicated."""
        # HTML with the same job ID appearing twice
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:123">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123">
                        <span class="sr-only">Job Title</span>
                    </a>
                    <h3 class="base-search-card__title">Job Title</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Company</a>
                    </h4>
                    <span class="job-search-card__location">Paris</span>
                </div>
            </li>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:123">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123">
                        <span class="sr-only">Job Title</span>
                    </a>
                    <h3 class="base-search-card__title">Job Title</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Company</a>
                    </h4>
                    <span class="job-search-card__location">Paris</span>
                </div>
            </li>
        </body>
        </html>
        """
        result = parser.parse_jobs(html)

        assert len(result) == 1
        assert result[0].id == "123"

    def test_parse_extracts_salary(self, parser: HTMLParser):
        """Test that salary information is extracted."""
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:123">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123">
                        <span class="sr-only">Developer</span>
                    </a>
                    <h3 class="base-search-card__title">Developer</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Company</a>
                    </h4>
                    <span class="job-search-card__location">Paris</span>
                    <span class="job-search-card__salary-info">50k-70k EUR</span>
                </div>
            </li>
        </body>
        </html>
        """
        result = parser.parse_jobs(html)

        assert len(result) == 1
        assert result[0].salary == "50k-70k EUR"

    def test_parse_extracts_description_snippet(self, parser: HTMLParser):
        """Test that description snippet is extracted."""
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:123">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123">
                        <span class="sr-only">Developer</span>
                    </a>
                    <h3 class="base-search-card__title">Developer</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Company</a>
                    </h4>
                    <span class="job-search-card__location">Paris</span>
                    <p class="job-search-card__snippet">Looking for a Python developer...</p>
                </div>
            </li>
        </body>
        </html>
        """
        result = parser.parse_jobs(html)

        assert len(result) == 1
        assert result[0].description_snippet == "Looking for a Python developer..."
