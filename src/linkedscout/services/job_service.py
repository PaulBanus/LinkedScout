"""Service for searching and managing jobs."""


from typing import TYPE_CHECKING

from beartype import beartype

from linkedscout.config import Settings, get_settings
from linkedscout.scraper.client import LinkedInClient
from linkedscout.storage.json_store import JsonStore
from linkedscout.storage.sqlite_store import SqliteStore

if TYPE_CHECKING:
    from pathlib import Path

    from linkedscout.models.job import JobPosting
    from linkedscout.models.search import SavedAlert, SearchCriteria


class JobService:
    """Service for searching jobs and managing results."""

    @beartype
    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize job service.

        Args:
            settings: Application settings. Uses defaults if not provided.
        """
        self._settings = settings or get_settings()
        self._json_store = JsonStore(self._settings.output_dir)
        self._sqlite_store = SqliteStore(self._settings.db_path)

    async def search(
        self,
        criteria: "SearchCriteria",
        save_to_db: bool = True,
    ) -> list["JobPosting"]:
        """Search for jobs matching criteria.

        Args:
            criteria: Search criteria.
            save_to_db: Whether to save results to SQLite database.

        Returns:
            List of job postings sorted by date (most recent first).
        """
        async with LinkedInClient(self._settings) as client:
            jobs = await client.search(criteria)

        if save_to_db and jobs:
            self._sqlite_store.save(jobs)

        return jobs

    async def run_alert(
        self,
        alert: "SavedAlert",
        only_new: bool = False,
        save_to_db: bool = True,
    ) -> list["JobPosting"]:
        """Run a saved alert and return matching jobs.

        Args:
            alert: The alert to run.
            only_new: If True, only return jobs not yet in database.
            save_to_db: Whether to save results to SQLite database.

        Returns:
            List of job postings.
        """
        if not alert.enabled:
            return []

        jobs = await self.search(alert.criteria, save_to_db=save_to_db)

        if only_new:
            jobs = self._sqlite_store.get_new_jobs(jobs)

        return jobs

    def save_to_json(
        self,
        jobs: list["JobPosting"],
        output_path: "Path | None" = None,
        filename: str | None = None,
    ) -> "Path":
        """Save jobs to JSON file.

        Args:
            jobs: List of jobs to save.
            output_path: Full path to output file (takes precedence).
            filename: Filename without extension (uses output_dir).

        Returns:
            Path to saved file.
        """
        if output_path:
            self._json_store.save_to_path(jobs, output_path)
            return output_path

        return self._json_store.save(jobs, filename or "jobs")

    def get_stored_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        company: str | None = None,
    ) -> list["JobPosting"]:
        """Get jobs from SQLite storage.

        Args:
            limit: Maximum number of jobs.
            offset: Pagination offset.
            company: Filter by company name.

        Returns:
            List of job postings.
        """
        return self._sqlite_store.get_jobs(limit, offset, company)

    @beartype
    def get_job_count(self) -> int:
        """Get total number of jobs in database."""
        return self._sqlite_store.count()

    def get_new_job_count(self, jobs: list["JobPosting"]) -> int:
        """Count how many jobs are not yet in database.

        Args:
            jobs: List of jobs to check.

        Returns:
            Number of new jobs.
        """
        new_jobs = self._sqlite_store.get_new_jobs(jobs)
        return len(new_jobs)
