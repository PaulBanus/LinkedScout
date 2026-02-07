"""JSON storage for job data."""

import json
from pathlib import Path

from beartype import beartype

from linkedscout.models.job import JobPosting


class JsonStore:
    """Store job postings as JSON files."""

    @beartype
    def __init__(self, output_dir: Path | None = None) -> None:
        """Initialize JSON store.

        Args:
            output_dir: Directory for output files. Defaults to current directory.
        """
        self._output_dir = output_dir or Path()

    @beartype
    def save(self, jobs: list[JobPosting], filename: str) -> Path:
        """Save jobs to a JSON file.

        Args:
            jobs: List of job postings to save.
            filename: Output filename (without extension).

        Returns:
            Path to the saved file.
        """
        self._output_dir.mkdir(parents=True, exist_ok=True)

        file_path = self._output_dir / f"{filename}.json"
        data = {
            "count": len(jobs),
            "jobs": [job.to_dict() for job in jobs],
        }

        file_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        return file_path

    @beartype
    def load(self, filename: str) -> list[JobPosting]:
        """Load jobs from a JSON file.

        Args:
            filename: Filename to load (with or without extension).

        Returns:
            List of job postings.
        """
        if not filename.endswith(".json"):
            filename = f"{filename}.json"

        file_path = self._output_dir / filename
        if not file_path.exists():
            return []

        data = json.loads(file_path.read_text(encoding="utf-8"))
        return [JobPosting.from_dict(job) for job in data.get("jobs", [])]

    @beartype
    def save_to_path(self, jobs: list[JobPosting], path: Path) -> None:
        """Save jobs directly to a specific path.

        Args:
            jobs: List of job postings to save.
            path: Full path to the output file.
        """
        path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "count": len(jobs),
            "jobs": [job.to_dict() for job in jobs],
        }

        path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
