"""SQLite storage for job history and deduplication."""

import sqlite3
from datetime import datetime
from pathlib import Path

from beartype import beartype

from linkedscout.models.job import JobPosting


class SqliteStore:
    """Store job postings in SQLite database for history and deduplication."""

    @beartype
    def __init__(self, db_path: Path | None = None) -> None:
        """Initialize SQLite store.

        Args:
            db_path: Path to SQLite database file. Defaults to linkedscout.db.
        """
        self._db_path = db_path or Path("linkedscout.db")
        self._init_db()

    @beartype
    def _init_db(self) -> None:
        """Initialize database schema."""
        with self._get_connection() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT NOT NULL,
                    url TEXT NOT NULL,
                    posted_at TEXT,
                    description_snippet TEXT,
                    salary TEXT,
                    is_remote INTEGER DEFAULT 0,
                    applicants_count TEXT,
                    scraped_at TEXT NOT NULL,
                    first_seen_at TEXT NOT NULL,
                    last_seen_at TEXT NOT NULL
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_posted_at
                ON jobs(posted_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_jobs_company
                ON jobs(company)
            """)

            conn.commit()

    @beartype
    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection."""
        return sqlite3.connect(self._db_path)

    @beartype
    def save(self, jobs: list[JobPosting]) -> tuple[int, int]:
        """Save jobs to database, handling duplicates.

        Args:
            jobs: List of job postings to save.

        Returns:
            Tuple of (new_count, updated_count).
        """
        new_count = 0
        updated_count = 0
        now = datetime.now().isoformat()

        with self._get_connection() as conn:
            for job in jobs:
                # Check if job exists
                cursor = conn.execute(
                    "SELECT id FROM jobs WHERE id = ?",
                    (job.id,),
                )
                existing = cursor.fetchone()

                if existing:
                    # Update last_seen_at
                    conn.execute(
                        "UPDATE jobs SET last_seen_at = ? WHERE id = ?",
                        (now, job.id),
                    )
                    updated_count += 1
                else:
                    # Insert new job
                    conn.execute(
                        """
                        INSERT INTO jobs (
                            id, title, company, location, url,
                            posted_at, description_snippet, salary,
                            is_remote, applicants_count, scraped_at,
                            first_seen_at, last_seen_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            job.id,
                            job.title,
                            job.company,
                            job.location,
                            str(job.url),
                            job.posted_at.isoformat() if job.posted_at else None,
                            job.description_snippet,
                            job.salary,
                            1 if job.is_remote else 0,
                            job.applicants_count,
                            job.scraped_at.isoformat(),
                            now,
                            now,
                        ),
                    )
                    new_count += 1

            conn.commit()

        return new_count, updated_count

    @beartype
    def get_new_jobs(
        self, jobs: list[JobPosting]
    ) -> list[JobPosting]:
        """Filter jobs to only return ones not yet in database.

        Args:
            jobs: List of job postings to check.

        Returns:
            List of jobs not in database.
        """
        if not jobs:
            return []

        job_ids = [job.id for job in jobs]
        placeholders = ",".join("?" * len(job_ids))

        with self._get_connection() as conn:
            cursor = conn.execute(
                f"SELECT id FROM jobs WHERE id IN ({placeholders})",
                job_ids,
            )
            existing_ids = {row[0] for row in cursor.fetchall()}

        return [job for job in jobs if job.id not in existing_ids]

    @beartype
    def get_jobs(
        self,
        limit: int = 100,
        offset: int = 0,
        company: str | None = None,
    ) -> list[JobPosting]:
        """Get jobs from database.

        Args:
            limit: Maximum number of jobs to return.
            offset: Offset for pagination.
            company: Filter by company name (optional).

        Returns:
            List of job postings.
        """
        with self._get_connection() as conn:
            if company:
                cursor = conn.execute(
                    """
                    SELECT id, title, company, location, url,
                           posted_at, description_snippet, salary,
                           is_remote, applicants_count, scraped_at
                    FROM jobs
                    WHERE company LIKE ?
                    ORDER BY posted_at DESC NULLS LAST
                    LIMIT ? OFFSET ?
                    """,
                    (f"%{company}%", limit, offset),
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT id, title, company, location, url,
                           posted_at, description_snippet, salary,
                           is_remote, applicants_count, scraped_at
                    FROM jobs
                    ORDER BY posted_at DESC NULLS LAST
                    LIMIT ? OFFSET ?
                    """,
                    (limit, offset),
                )

            return [self._row_to_job(row) for row in cursor.fetchall()]

    @beartype
    def _row_to_job(self, row: tuple[object, ...]) -> JobPosting:
        """Convert database row to JobPosting."""
        return JobPosting(
            id=str(row[0]),
            title=str(row[1]),
            company=str(row[2]),
            location=str(row[3]),
            url=str(row[4]),
            posted_at=datetime.fromisoformat(str(row[5])) if row[5] else None,
            description_snippet=str(row[6]) if row[6] else None,
            salary=str(row[7]) if row[7] else None,
            is_remote=bool(row[8]),
            applicants_count=str(row[9]) if row[9] else None,
            scraped_at=datetime.fromisoformat(str(row[10])),
        )

    @beartype
    def count(self) -> int:
        """Get total number of jobs in database."""
        with self._get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) FROM jobs")
            result = cursor.fetchone()
            return int(result[0]) if result else 0
