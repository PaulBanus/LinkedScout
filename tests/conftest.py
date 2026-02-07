"""Pytest configuration and shared fixtures."""

import tempfile
from pathlib import Path

import pytest

from linkedscout.config import Settings


@pytest.fixture
def temp_dir():
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def test_settings(temp_dir: Path) -> Settings:
    """Create test settings with temporary directories."""
    return Settings(
        alerts_file=temp_dir / "alerts.yaml",
        output_dir=temp_dir / "output",
        db_path=temp_dir / "test.db",
        request_delay=0.0,  # No delay in tests
    )


@pytest.fixture
def sample_html() -> str:
    """Sample LinkedIn job listing HTML."""
    return """
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
                <span class="job-search-card__location">Paris, France</span>
                <time datetime="2024-01-15T10:00:00">1 day ago</time>
                <span class="job-search-card__salary-info">50k-70k EUR</span>
            </div>
        </li>
        <li class="jobs-search__result-card">
            <div class="base-card" data-entity-urn="urn:li:jobPosting:987654321">
                <a class="base-card__full-link" href="https://www.linkedin.com/jobs/view/987654321">
                    <span class="sr-only">Senior Python Engineer</span>
                </a>
                <h3 class="base-search-card__title">Senior Python Engineer</h3>
                <h4 class="base-search-card__subtitle">
                    <a class="hidden-nested-link">Tech Startup</a>
                </h4>
                <span class="job-search-card__location">Remote</span>
                <time datetime="2024-01-14T09:00:00">2 days ago</time>
            </div>
        </li>
    </body>
    </html>
    """
