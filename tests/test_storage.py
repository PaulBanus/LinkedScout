"""Tests for storage modules."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

from linkedscout.models.job import JobPosting
from linkedscout.storage.json_store import JsonStore
from linkedscout.storage.sqlite_store import SqliteStore


@pytest.fixture
def sample_jobs() -> list[JobPosting]:
    """Create sample job postings for testing."""
    return [
        JobPosting(
            id="1",
            title="Python Developer",
            company="Acme Corp",
            location="Paris",
            url="https://linkedin.com/jobs/view/1",
            is_remote=False,
            salary="50k-70k EUR",
        ),
        JobPosting(
            id="2",
            title="Senior Engineer",
            company="Tech Co",
            location="Remote",
            url="https://linkedin.com/jobs/view/2",
            is_remote=True,
        ),
    ]


class TestJsonStore:
    """Tests for JsonStore."""

    def test_save_creates_directory(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test that save creates the output directory if it doesn't exist."""
        output_dir = temp_dir / "nested" / "output"
        store = JsonStore(output_dir)

        path = store.save(sample_jobs, "test-jobs")

        assert output_dir.exists()
        assert path.exists()

    def test_save_and_load(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test saving and loading jobs."""
        store = JsonStore(temp_dir)

        path = store.save(sample_jobs, "test-jobs")

        assert path.exists()
        assert path.name == "test-jobs.json"

        loaded = store.load("test-jobs")
        assert len(loaded) == 2
        assert loaded[0].id == "1"
        assert loaded[0].title == "Python Developer"
        assert loaded[1].id == "2"
        assert loaded[1].is_remote is True

    def test_load_with_extension(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test loading with .json extension included."""
        store = JsonStore(temp_dir)
        store.save(sample_jobs, "test-jobs")

        loaded = store.load("test-jobs.json")

        assert len(loaded) == 2

    def test_load_nonexistent_returns_empty(self, temp_dir: Path):
        """Test loading nonexistent file returns empty list."""
        store = JsonStore(temp_dir)

        loaded = store.load("does-not-exist")

        assert loaded == []

    def test_save_to_path(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test saving to specific path."""
        store = JsonStore(temp_dir)
        custom_path = temp_dir / "custom" / "jobs.json"

        store.save_to_path(sample_jobs, custom_path)

        assert custom_path.exists()
        data = json.loads(custom_path.read_text())
        assert data["count"] == 2
        assert len(data["jobs"]) == 2

    def test_save_preserves_all_fields(self, temp_dir: Path):
        """Test that save preserves all job fields."""
        job = JobPosting(
            id="test-id",
            title="Test Title",
            company="Test Company",
            location="Test Location",
            url="https://linkedin.com/jobs/view/test-id",
            salary="100k USD",
            description_snippet="Test description",
            is_remote=True,
            applicants_count="50 applicants",
        )
        store = JsonStore(temp_dir)

        store.save([job], "full-fields")
        loaded = store.load("full-fields")

        assert len(loaded) == 1
        assert loaded[0].id == "test-id"
        assert loaded[0].salary == "100k USD"
        assert loaded[0].description_snippet == "Test description"
        assert loaded[0].is_remote is True
        assert loaded[0].applicants_count == "50 applicants"

    def test_save_empty_list(self, temp_dir: Path):
        """Test saving an empty list."""
        store = JsonStore(temp_dir)

        path = store.save([], "empty")

        assert path.exists()
        loaded = store.load("empty")
        assert loaded == []


class TestSqliteStore:
    """Tests for SqliteStore."""

    def test_init_creates_database(self, temp_dir: Path):
        """Test that initializing creates the database file."""
        db_path = temp_dir / "test.db"

        SqliteStore(db_path)

        assert db_path.exists()

    def test_save_new_jobs(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test saving new jobs to database."""
        store = SqliteStore(temp_dir / "test.db")

        new, updated = store.save(sample_jobs)

        assert new == 2
        assert updated == 0
        assert store.count() == 2

    def test_save_duplicate_updates_last_seen(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test that duplicate jobs update last_seen_at."""
        store = SqliteStore(temp_dir / "test.db")

        store.save(sample_jobs)
        new, updated = store.save(sample_jobs)

        assert new == 0
        assert updated == 2
        assert store.count() == 2

    def test_save_mixed_new_and_existing(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test saving a mix of new and existing jobs."""
        store = SqliteStore(temp_dir / "test.db")
        store.save([sample_jobs[0]])  # Save first job

        new_job = JobPosting(
            id="3",
            title="New Job",
            company="New Company",
            location="New Location",
            url="https://linkedin.com/jobs/view/3",
        )

        new, updated = store.save([sample_jobs[0], new_job])

        assert new == 1
        assert updated == 1
        assert store.count() == 2

    def test_get_new_jobs_filters_existing(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test filtering to only new jobs."""
        store = SqliteStore(temp_dir / "test.db")
        store.save([sample_jobs[0]])  # Save first job

        new_jobs = store.get_new_jobs(sample_jobs)

        assert len(new_jobs) == 1
        assert new_jobs[0].id == "2"

    def test_get_new_jobs_empty_input(self, temp_dir: Path):
        """Test get_new_jobs with empty input returns empty list."""
        store = SqliteStore(temp_dir / "test.db")

        new_jobs = store.get_new_jobs([])

        assert new_jobs == []

    def test_get_new_jobs_all_existing(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test get_new_jobs when all jobs already exist."""
        store = SqliteStore(temp_dir / "test.db")
        store.save(sample_jobs)

        new_jobs = store.get_new_jobs(sample_jobs)

        assert new_jobs == []

    def test_get_new_jobs_all_new(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test get_new_jobs when all jobs are new."""
        store = SqliteStore(temp_dir / "test.db")

        new_jobs = store.get_new_jobs(sample_jobs)

        assert len(new_jobs) == 2

    def test_get_jobs_with_company_filter(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test filtering jobs by company."""
        store = SqliteStore(temp_dir / "test.db")
        store.save(sample_jobs)

        filtered = store.get_jobs(limit=10, company="Acme")

        assert len(filtered) == 1
        assert filtered[0].company == "Acme Corp"

    def test_get_jobs_company_filter_partial_match(self, temp_dir: Path):
        """Test company filter with partial match."""
        jobs = [
            JobPosting(
                id="1",
                title="Job 1",
                company="Acme Corporation",
                location="Paris",
                url="https://linkedin.com/jobs/view/1",
            ),
            JobPosting(
                id="2",
                title="Job 2",
                company="Acme Inc",
                location="Lyon",
                url="https://linkedin.com/jobs/view/2",
            ),
            JobPosting(
                id="3",
                title="Job 3",
                company="Other Corp",
                location="Marseille",
                url="https://linkedin.com/jobs/view/3",
            ),
        ]
        store = SqliteStore(temp_dir / "test.db")
        store.save(jobs)

        filtered = store.get_jobs(limit=10, company="Acme")

        assert len(filtered) == 2

    def test_get_jobs_pagination(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test pagination of job results."""
        store = SqliteStore(temp_dir / "test.db")
        store.save(sample_jobs)

        page1 = store.get_jobs(limit=1, offset=0)
        page2 = store.get_jobs(limit=1, offset=1)

        assert len(page1) == 1
        assert len(page2) == 1
        assert page1[0].id != page2[0].id

    def test_get_jobs_limit(self, temp_dir: Path):
        """Test that limit restricts results."""
        jobs = [
            JobPosting(
                id=str(i),
                title=f"Job {i}",
                company="Company",
                location="Location",
                url=f"https://linkedin.com/jobs/view/{i}",
            )
            for i in range(10)
        ]
        store = SqliteStore(temp_dir / "test.db")
        store.save(jobs)

        result = store.get_jobs(limit=5)

        assert len(result) == 5

    def test_count_empty_database(self, temp_dir: Path):
        """Test count on empty database."""
        store = SqliteStore(temp_dir / "test.db")

        assert store.count() == 0

    def test_save_preserves_all_fields(self, temp_dir: Path):
        """Test that save preserves all job fields in database."""
        from datetime import datetime

        posted = datetime(2024, 1, 15, 10, 0, 0)
        job = JobPosting(
            id="test-id",
            title="Test Title",
            company="Test Company",
            location="Test Location",
            url="https://linkedin.com/jobs/view/test-id",
            posted_at=posted,
            salary="100k USD",
            description_snippet="Test description",
            is_remote=True,
            applicants_count="50 applicants",
        )
        store = SqliteStore(temp_dir / "test.db")

        store.save([job])
        retrieved = store.get_jobs(limit=1)

        assert len(retrieved) == 1
        assert retrieved[0].id == "test-id"
        assert retrieved[0].title == "Test Title"
        assert retrieved[0].company == "Test Company"
        assert retrieved[0].posted_at == posted
        assert retrieved[0].salary == "100k USD"
        assert retrieved[0].description_snippet == "Test description"
        assert retrieved[0].is_remote is True
        assert retrieved[0].applicants_count == "50 applicants"

    def test_multiple_stores_same_database(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test that multiple store instances can access the same database."""
        db_path = temp_dir / "shared.db"

        store1 = SqliteStore(db_path)
        store1.save(sample_jobs)

        store2 = SqliteStore(db_path)

        assert store2.count() == 2

    def test_get_jobs_no_company_filter(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test getting jobs without company filter."""
        store = SqliteStore(temp_dir / "test.db")
        store.save(sample_jobs)

        jobs = store.get_jobs(limit=10)

        assert len(jobs) == 2
