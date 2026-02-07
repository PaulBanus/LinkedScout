"""Tests for CLI interface."""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

if TYPE_CHECKING:
    from pathlib import Path

import pytest
from typer.testing import CliRunner

from linkedscout.cli import app
from linkedscout.models.job import JobPosting
from linkedscout.models.search import SavedAlert, SearchCriteria

runner = CliRunner()


@pytest.fixture
def sample_jobs() -> list[JobPosting]:
    """Create sample job postings for testing."""
    return [
        JobPosting(
            id="123456789",
            title="Python Developer",
            company="Acme Corp",
            location="Paris, France",
            url="https://www.linkedin.com/jobs/view/123456789",
            is_remote=False,
        ),
        JobPosting(
            id="987654321",
            title="Senior Engineer",
            company="Tech Startup",
            location="Remote",
            url="https://www.linkedin.com/jobs/view/987654321",
            is_remote=True,
        ),
    ]


class TestSearchCommand:
    """Tests for the search command."""

    def test_search_requires_keywords(self):
        """Test that search command requires keywords."""
        result = runner.invoke(app, ["search"])

        assert result.exit_code != 0
        # Typer may write error to stdout or output, check both
        output = result.stdout + (result.output or "")
        assert "Missing option" in output or "keywords" in output.lower() or result.exit_code == 2

    def test_search_displays_results(self, sample_jobs: list[JobPosting]):
        """Test search command displays job results."""
        with patch(
            "linkedscout.cli.JobService"
        ) as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search = AsyncMock(return_value=sample_jobs)

            result = runner.invoke(
                app,
                [
                    "search",
                    "--keywords", "Python Developer",
                    "--location", "Paris",
                ],
            )

        assert result.exit_code == 0
        assert "Python Developer" in result.stdout
        assert "Acme Corp" in result.stdout
        assert "Found 2 jobs" in result.stdout

    def test_search_no_results(self):
        """Test search command with no results."""
        with patch("linkedscout.cli.JobService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search = AsyncMock(return_value=[])

            result = runner.invoke(
                app,
                [
                    "search",
                    "--keywords", "NonexistentJob12345",
                ],
            )

        assert result.exit_code == 0
        assert "No jobs found" in result.stdout

    def test_search_saves_to_json(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test search command saves results to JSON."""
        output_file = temp_dir / "output.json"

        with patch("linkedscout.cli.JobService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search = AsyncMock(return_value=sample_jobs)
            mock_service.save_to_json = lambda _jobs, output_path: output_path

            result = runner.invoke(
                app,
                [
                    "search",
                    "--keywords", "Python",
                    "--output", str(output_file),
                ],
            )

        assert result.exit_code == 0
        assert f"Saved 2 jobs to {output_file}" in result.stdout

    def test_search_with_filters(self, sample_jobs: list[JobPosting]):
        """Test search command with work model and job type filters."""
        with patch("linkedscout.cli.JobService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search = AsyncMock(return_value=sample_jobs)

            result = runner.invoke(
                app,
                [
                    "search",
                    "--keywords", "Python",
                    "--remote",
                    "--full-time",
                    "--time", "24h",
                    "--max", "50",
                ],
            )

        assert result.exit_code == 0
        # Verify the search was called
        mock_service.search.assert_called_once()


class TestAlertsListCommand:
    """Tests for alerts list command."""

    def test_list_alerts_empty(self, temp_dir: Path):
        """Test listing alerts when none exist."""
        result = runner.invoke(
            app,
            ["alerts", "list", "--file", str(temp_dir / "alerts.yaml")],
        )

        assert result.exit_code == 0
        assert "No alerts found" in result.stdout

    def test_list_alerts_shows_alerts(self, temp_dir: Path):
        """Test listing alerts displays them in a table."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.list_alerts.return_value = [
                SavedAlert(
                    name="python-jobs",
                    criteria=SearchCriteria(keywords="Python", location="Paris"),
                    enabled=True,
                ),
                SavedAlert(
                    name="java-jobs",
                    criteria=SearchCriteria(keywords="Java"),
                    enabled=False,
                ),
            ]

            result = runner.invoke(
                app,
                ["alerts", "list", "--file", str(temp_dir)],
            )

        assert result.exit_code == 0
        assert "python-jobs" in result.stdout
        assert "java-jobs" in result.stdout
        assert "Python" in result.stdout


class TestAlertsCreateCommand:
    """Tests for alerts create command."""

    def test_create_alert(self, temp_dir: Path):
        """Test creating an alert."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_alert.return_value = None
            mock_service.create_alert.return_value = SavedAlert(
                name="new-alert",
                criteria=SearchCriteria(keywords="Python"),
                enabled=True,
            )
            mock_service.get_alerts_file.return_value = temp_dir / "alerts.yaml"

            result = runner.invoke(
                app,
                [
                    "alerts", "create", "new-alert",
                    "--keywords", "Python Developer",
                    "--file", str(temp_dir / "alerts.yaml"),
                ],
            )

        assert result.exit_code == 0
        assert "Created alert" in result.stdout

    def test_create_duplicate_alert_fails(self, temp_dir: Path):
        """Test that creating a duplicate alert fails."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_alert.return_value = SavedAlert(
                name="existing-alert",
                criteria=SearchCriteria(keywords="Python"),
                enabled=True,
            )

            result = runner.invoke(
                app,
                [
                    "alerts", "create", "existing-alert",
                    "--keywords", "Java",
                    "--file", str(temp_dir),
                ],
            )

        assert result.exit_code == 1
        assert "already exists" in result.stdout


class TestAlertsDeleteCommand:
    """Tests for alerts delete command."""

    def test_delete_alert_with_force(self, temp_dir: Path):
        """Test deleting an alert with force flag."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_alert.return_value = SavedAlert(
                name="delete-me",
                criteria=SearchCriteria(keywords="Python"),
                enabled=True,
            )
            mock_service.delete_alert.return_value = True

            result = runner.invoke(
                app,
                [
                    "alerts", "delete", "delete-me",
                    "--force",
                    "--file", str(temp_dir),
                ],
            )

        assert result.exit_code == 0
        assert "Deleted alert" in result.stdout

    def test_delete_nonexistent_alert(self, temp_dir: Path):
        """Test deleting a nonexistent alert fails."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.get_alert.return_value = None

            result = runner.invoke(
                app,
                [
                    "alerts", "delete", "nonexistent",
                    "--force",
                    "--file", str(temp_dir),
                ],
            )

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestAlertsRunCommand:
    """Tests for alerts run command."""

    def test_run_requires_name_or_all(self, temp_dir: Path):
        """Test that run command requires --name or --all."""
        result = runner.invoke(
            app,
            ["alerts", "run", "--file", str(temp_dir)],
        )

        assert result.exit_code == 1
        assert "--name or --all" in result.stdout

    def test_run_specific_alert(
        self, temp_dir: Path, sample_jobs: list[JobPosting]
    ):
        """Test running a specific alert by name."""
        alert = SavedAlert(
            name="test-alert",
            criteria=SearchCriteria(keywords="Python"),
            enabled=True,
        )

        with patch("linkedscout.cli.AlertService") as mock_alert_class, patch(
            "linkedscout.cli.JobService"
        ) as mock_job_class:
            mock_alert = mock_alert_class.return_value
            mock_alert.get_alert.return_value = alert

            mock_job = mock_job_class.return_value
            mock_job.run_alert = AsyncMock(return_value=sample_jobs)

            result = runner.invoke(
                app,
                [
                    "alerts", "run",
                    "--name", "test-alert",
                    "--file", str(temp_dir),
                ],
            )

        assert result.exit_code == 0
        assert "Found 2 unique jobs" in result.stdout

    def test_run_all_alerts(self, temp_dir: Path, sample_jobs: list[JobPosting]):
        """Test running all enabled alerts."""
        alerts = [
            SavedAlert(
                name="alert-1",
                criteria=SearchCriteria(keywords="Python"),
                enabled=True,
            ),
            SavedAlert(
                name="alert-2",
                criteria=SearchCriteria(keywords="Java"),
                enabled=True,
            ),
        ]

        with patch("linkedscout.cli.AlertService") as mock_alert_class, patch(
            "linkedscout.cli.JobService"
        ) as mock_job_class:
            mock_alert = mock_alert_class.return_value
            mock_alert.get_enabled_alerts.return_value = alerts

            mock_job = mock_job_class.return_value
            mock_job.run_alert = AsyncMock(return_value=sample_jobs)

            result = runner.invoke(
                app,
                ["alerts", "run", "--all", "--file", str(temp_dir)],
            )

        assert result.exit_code == 0
        # Jobs are deduplicated, so we should see 2 unique jobs
        assert "unique jobs" in result.stdout

    def test_run_alert_not_found(self, temp_dir: Path):
        """Test running a nonexistent alert fails."""
        with patch("linkedscout.cli.AlertService") as mock_alert_class:
            mock_alert = mock_alert_class.return_value
            mock_alert.get_alert.return_value = None

            result = runner.invoke(
                app,
                [
                    "alerts", "run",
                    "--name", "nonexistent",
                    "--file", str(temp_dir),
                ],
            )

        assert result.exit_code == 1
        assert "not found" in result.stdout


class TestAlertsEnableDisableCommands:
    """Tests for alerts enable/disable commands."""

    def test_enable_alert(self, temp_dir: Path):
        """Test enabling an alert."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.update_alert.return_value = SavedAlert(
                name="my-alert",
                criteria=SearchCriteria(keywords="Python"),
                enabled=True,
            )

            result = runner.invoke(
                app,
                ["alerts", "enable", "my-alert", "--file", str(temp_dir)],
            )

        assert result.exit_code == 0
        assert "Enabled alert" in result.stdout

    def test_enable_nonexistent_alert(self, temp_dir: Path):
        """Test enabling a nonexistent alert fails."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.update_alert.return_value = None

            result = runner.invoke(
                app,
                ["alerts", "enable", "nonexistent", "--file", str(temp_dir)],
            )

        assert result.exit_code == 1
        assert "not found" in result.stdout

    def test_disable_alert(self, temp_dir: Path):
        """Test disabling an alert."""
        with patch("linkedscout.cli.AlertService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.update_alert.return_value = SavedAlert(
                name="my-alert",
                criteria=SearchCriteria(keywords="Python"),
                enabled=False,
            )

            result = runner.invoke(
                app,
                ["alerts", "disable", "my-alert", "--file", str(temp_dir)],
            )

        assert result.exit_code == 0
        assert "Disabled alert" in result.stdout


class TestTimeFilterParsing:
    """Tests for time filter parsing."""

    @pytest.mark.parametrize(
        "time_arg,expected_display",
        [
            ("24h", "Found"),
            ("1d", "Found"),
            ("7d", "Found"),
            ("1w", "Found"),
            ("30d", "Found"),
            ("1m", "Found"),
            ("any", "Found"),
        ],
    )
    def test_time_filter_parsing(
        self,
        sample_jobs: list[JobPosting],
        time_arg: str,
        expected_display: str,
    ):
        """Test various time filter formats are accepted."""
        with patch("linkedscout.cli.JobService") as mock_service_class:
            mock_service = mock_service_class.return_value
            mock_service.search = AsyncMock(return_value=sample_jobs)

            result = runner.invoke(
                app,
                [
                    "search",
                    "--keywords", "Python",
                    "--time", time_arg,
                ],
            )

        assert result.exit_code == 0
        assert expected_display in result.stdout
