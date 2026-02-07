"""Tests for scraper module."""

import httpx
import pytest
import respx

from linkedscout.models.search import SearchCriteria, TimeFilter, WorkModel
from linkedscout.scraper.client import LinkedInClient
from linkedscout.scraper.parser import HTMLParser


class TestHTMLParser:
    """Tests for HTML parser."""

    def test_parse_jobs(self, sample_html: str):
        """Test parsing job listings from HTML."""
        parser = HTMLParser()
        jobs = parser.parse_jobs(sample_html)

        assert len(jobs) == 2

        # First job
        assert jobs[0].id == "123456789"
        assert jobs[0].title == "Python Developer"
        assert jobs[0].company == "Acme Corp"
        assert jobs[0].location == "Paris, France"
        assert jobs[0].salary == "50k-70k EUR"
        assert jobs[0].is_remote is False

        # Second job (remote)
        assert jobs[1].id == "987654321"
        assert jobs[1].title == "Senior Python Engineer"
        assert jobs[1].company == "Tech Startup"
        assert jobs[1].location == "Remote"
        assert jobs[1].is_remote is True

    def test_parse_empty_html(self):
        """Test parsing empty HTML returns empty list."""
        parser = HTMLParser()
        jobs = parser.parse_jobs("<html><body></body></html>")

        assert jobs == []

    def test_parse_malformed_card(self):
        """Test that malformed cards are skipped."""
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card">
                    <!-- Missing required elements -->
                </div>
            </li>
        </body>
        </html>
        """
        parser = HTMLParser()
        jobs = parser.parse_jobs(html)

        assert jobs == []


class TestLinkedInClient:
    """Tests for LinkedIn client."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_jobs(self, test_settings, sample_html: str):
        """Test searching for jobs."""
        # Mock the API response - first returns jobs, second is empty
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=sample_html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        criteria = SearchCriteria(
            keywords="Python",
            location="Paris",
            max_results=10,
        )

        async with LinkedInClient(test_settings) as client:
            jobs = await client.search(criteria)

        assert len(jobs) == 2
        assert jobs[0].title == "Python Developer"

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_empty_results(self, test_settings):
        """Test search with no results."""
        respx.get(LinkedInClient.BASE_URL).mock(
            return_value=httpx.Response(200, text="<html><body></body></html>")
        )

        criteria = SearchCriteria(keywords="nonexistent")

        async with LinkedInClient(test_settings) as client:
            jobs = await client.search(criteria)

        assert jobs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_pagination(self, test_settings, sample_html: str):
        """Test that pagination works correctly."""
        # First page returns jobs, second page is empty
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=sample_html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        criteria = SearchCriteria(keywords="Python", max_results=50)

        async with LinkedInClient(test_settings) as client:
            jobs = await client.search(criteria)

        # 2 unique jobs from sample_html
        assert len(jobs) == 2
        # Should have made 2 requests (first with results, second empty)
        assert route.call_count == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_respects_max_results(self, test_settings, sample_html: str):
        """Test that max_results is respected."""
        respx.get(LinkedInClient.BASE_URL).mock(
            return_value=httpx.Response(200, text=sample_html)
        )

        criteria = SearchCriteria(keywords="Python", max_results=1)

        async with LinkedInClient(test_settings) as client:
            jobs = await client.search(criteria)

        assert len(jobs) == 1

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_with_filters(self, test_settings, sample_html: str):
        """Test search includes filter parameters."""
        route = respx.get(LinkedInClient.BASE_URL).mock(
            return_value=httpx.Response(200, text=sample_html)
        )

        criteria = SearchCriteria(
            keywords="Python",
            location="France",
            time_filter=TimeFilter.PAST_24H,
        )

        async with LinkedInClient(test_settings) as client:
            await client.search(criteria)

        # Check that parameters were passed correctly
        request = route.calls[0].request
        assert "keywords=Python" in str(request.url)
        assert "location=France" in str(request.url)
        assert "f_TPR=r86400" in str(request.url)

    @pytest.mark.asyncio
    async def test_client_not_initialized_error(self, test_settings):
        """Test error when client used without context manager."""
        client = LinkedInClient(test_settings)
        criteria = SearchCriteria(keywords="Python")

        with pytest.raises(RuntimeError, match="not initialized"):
            await client.search(criteria)

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_remote_only_sets_is_remote(self, test_settings):
        """Test that remote-only search criteria sets is_remote=True on all jobs."""
        # HTML with job that doesn't have "remote" in location or badge
        html = """
        <html>
        <body>
            <li class="jobs-search__result-card">
                <div class="base-card" data-entity-urn="urn:li:jobPosting:123456789">
                    <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/123456789">
                        <span class="sr-only">Python Developer</span>
                    </a>
                    <h3 class="base-search-card__title">Python Developer</h3>
                    <h4 class="base-search-card__subtitle">
                        <a class="hidden-nested-link">Acme Corp</a>
                    </h4>
                    <span class="job-search-card__location">France</span>
                    <time datetime="2024-01-15T10:00:00Z">2 days ago</time>
                </div>
            </li>
        </body>
        </html>
        """
        # Mock returns jobs first, then empty to stop pagination
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        # Search with remote-only criteria
        criteria = SearchCriteria(
            keywords="Python",
            location="France",
            work_models=[WorkModel.REMOTE],
            max_results=10,
        )

        async with LinkedInClient(test_settings) as client:
            jobs = await client.search(criteria)

        assert len(jobs) == 1
        # Even though location is "France" without "remote" keyword,
        # is_remote should be True because search criteria was remote-only
        assert jobs[0].is_remote is True
        assert jobs[0].location == "France"
