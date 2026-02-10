"""Tests for services."""

from pathlib import Path

import httpx
import pytest
import respx

from linkedscout.config import Settings
from linkedscout.models.job import JobPosting
from linkedscout.models.search import (
    SavedAlert,
    SearchCriteria,
    TimeFilter,
    WorkModel,
)
from linkedscout.scraper.client import LinkedInClient
from linkedscout.services.alert_service import AlertService
from linkedscout.services.job_service import JobService


class TestAlertService:
    """Tests for AlertService."""

    def test_create_alert(self, test_settings: Settings) -> None:
        """Test creating an alert."""
        service = AlertService(test_settings)

        alert = service.create_alert(
            name="test-alert",
            keywords="Python Developer",
            location="Paris",
            time_filter=TimeFilter.PAST_24H,
            work_models=[WorkModel.REMOTE],
        )

        assert alert.name == "test-alert"
        assert alert.criteria.keywords == "Python Developer"
        assert alert.enabled is True

        # Check file was created
        assert test_settings.alerts_file.exists()

    def test_list_alerts(self, test_settings: Settings) -> None:
        """Test listing alerts."""
        service = AlertService(test_settings)

        # Create some alerts
        service.create_alert(name="alert-a", keywords="Python")
        service.create_alert(name="alert-b", keywords="Java")
        service.create_alert(name="alert-c", keywords="Go", enabled=False)

        alerts = service.list_alerts()

        assert len(alerts) == 3
        # Should be sorted by name
        assert alerts[0].name == "alert-a"
        assert alerts[1].name == "alert-b"
        assert alerts[2].name == "alert-c"

    def test_get_alert(self, test_settings: Settings) -> None:
        """Test getting a specific alert."""
        service = AlertService(test_settings)
        service.create_alert(name="my-alert", keywords="Python")

        alert = service.get_alert("my-alert")

        assert alert is not None
        assert alert.name == "my-alert"

    def test_get_nonexistent_alert(self, test_settings: Settings) -> None:
        """Test getting a nonexistent alert returns None."""
        service = AlertService(test_settings)

        alert = service.get_alert("does-not-exist")

        assert alert is None

    def test_update_alert(self, test_settings: Settings) -> None:
        """Test updating an alert."""
        service = AlertService(test_settings)
        service.create_alert(name="update-test", keywords="Python")

        updated = service.update_alert("update-test", enabled=False)

        assert updated is not None
        assert updated.enabled is False

        # Verify persisted
        loaded = service.get_alert("update-test")
        assert loaded is not None
        assert loaded.enabled is False

    def test_delete_alert(self, test_settings: Settings) -> None:
        """Test deleting an alert."""
        service = AlertService(test_settings)
        service.create_alert(name="delete-me", keywords="Python")

        result = service.delete_alert("delete-me")

        assert result is True
        assert service.get_alert("delete-me") is None

    def test_delete_nonexistent_alert(self, test_settings: Settings) -> None:
        """Test deleting nonexistent alert returns False."""
        service = AlertService(test_settings)

        result = service.delete_alert("does-not-exist")

        assert result is False

    def test_get_enabled_alerts(self, test_settings: Settings) -> None:
        """Test getting only enabled alerts."""
        service = AlertService(test_settings)
        service.create_alert(name="enabled-1", keywords="Python", enabled=True)
        service.create_alert(name="disabled", keywords="Java", enabled=False)
        service.create_alert(name="enabled-2", keywords="Go", enabled=True)

        enabled = service.get_enabled_alerts()

        assert len(enabled) == 2
        names = [a.name for a in enabled]
        assert "enabled-1" in names
        assert "enabled-2" in names
        assert "disabled" not in names

    def test_migrate_from_directory(self, temp_dir: Path) -> None:
        """Test migrating alerts from directory to single file."""
        # Create old-style directory with YAML files
        alerts_dir = temp_dir / "alerts"
        alerts_dir.mkdir()

        alert1 = SavedAlert(
            name="alert1",
            criteria=SearchCriteria(keywords="Python"),
            enabled=True,
        )
        alert2 = SavedAlert(
            name="alert2",
            criteria=SearchCriteria(keywords="Java"),
            enabled=False,
        )

        alert1.save(alerts_dir)
        alert2.save(alerts_dir)

        # Migrate to new file
        alerts_file = temp_dir / "alerts.yaml"
        count = AlertService.migrate_from_directory(alerts_dir, alerts_file)

        assert count == 2
        assert alerts_file.exists()

        # Verify contents
        from linkedscout.models.search import AlertsConfig

        config = AlertsConfig.from_file(alerts_file)
        assert len(config.alerts) == 2
        assert config.get_alert("alert1") is not None
        assert config.get_alert("alert2") is not None

    def test_migrate_from_nonexistent_dir(self, temp_dir: Path) -> None:
        """Test migration fails if source directory doesn't exist."""
        alerts_dir = temp_dir / "nonexistent"
        alerts_file = temp_dir / "alerts.yaml"

        with pytest.raises(NotADirectoryError):
            AlertService.migrate_from_directory(alerts_dir, alerts_file)

    def test_migrate_rejects_file_path(self, temp_dir: Path) -> None:
        """Test migration fails if source is a file, not a directory."""
        file_path = temp_dir / "not_a_dir"
        file_path.write_text("I am a file")
        alerts_file = temp_dir / "alerts.yaml"

        with pytest.raises(NotADirectoryError, match="not a directory"):
            AlertService.migrate_from_directory(file_path, alerts_file)

    def test_migrate_to_existing_file(self, temp_dir: Path) -> None:
        """Test migration fails if target file already exists."""
        alerts_dir = temp_dir / "alerts"
        alerts_dir.mkdir()

        alerts_file = temp_dir / "alerts.yaml"
        alerts_file.write_text("existing content")

        with pytest.raises(ValueError, match="already exists"):
            AlertService.migrate_from_directory(alerts_dir, alerts_file)


class TestJobService:
    """Tests for JobService."""

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_saves_to_db(
        self, test_settings: Settings, sample_html: str
    ) -> None:
        """Test that search results are saved to database."""
        # Return sample on first call, empty on second
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=sample_html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        service = JobService(test_settings)
        criteria = SearchCriteria(keywords="Python", max_results=10)

        jobs = await service.search(criteria)

        assert len(jobs) == 2
        # Verify saved to DB
        assert service.get_job_count() == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_search_skip_db(
        self, test_settings: Settings, sample_html: str
    ) -> None:
        """Test search without saving to database."""
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=sample_html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        service = JobService(test_settings)
        criteria = SearchCriteria(keywords="Python", max_results=10)

        jobs = await service.search(criteria, save_to_db=False)

        assert len(jobs) == 2
        assert service.get_job_count() == 0

    def test_save_to_json(self, test_settings: Settings) -> None:
        """Test saving jobs to JSON file."""
        service = JobService(test_settings)

        jobs = [
            JobPosting(
                id="123",
                title="Developer",
                company="Acme",
                location="Paris",
                url="https://linkedin.com/jobs/view/123",
            ),
        ]

        output_path = test_settings.output_dir / "test-output.json"
        result = service.save_to_json(jobs, output_path=output_path)

        assert result == output_path
        assert output_path.exists()

    @pytest.mark.asyncio
    @respx.mock
    async def test_run_alert(self, test_settings: Settings, sample_html: str) -> None:
        """Test running an alert."""
        # Mock returns sample_html on first call, empty on subsequent calls
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=sample_html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        service = JobService(test_settings)
        alert = SavedAlert(
            name="test",
            criteria=SearchCriteria(keywords="Python", max_results=10),
            enabled=True,
        )

        jobs = await service.run_alert(alert)

        assert len(jobs) == 2

    @pytest.mark.asyncio
    @respx.mock
    async def test_run_disabled_alert(self, test_settings: Settings) -> None:
        """Test that disabled alerts return empty list."""
        service = JobService(test_settings)
        alert = SavedAlert(
            name="disabled",
            criteria=SearchCriteria(keywords="Python"),
            enabled=False,
        )

        jobs = await service.run_alert(alert)

        assert jobs == []

    @pytest.mark.asyncio
    @respx.mock
    async def test_run_alert_only_new_returns_new_jobs(
        self, test_settings: Settings, sample_html: str
    ) -> None:
        """Test that run_alert with only_new=True returns only new jobs."""
        service = JobService(test_settings)

        # Pre-populate DB with one known job (id matches sample_html)
        known_job = JobPosting(
            id="123456789",
            title="Known Job",
            company="Known Corp",
            location="Paris",
            url="https://linkedin.com/jobs/view/123456789",
        )
        service._sqlite_store.save([known_job])
        assert service.get_job_count() == 1

        # Mock search returns both known (123456789) and new (987654321)
        route = respx.get(LinkedInClient.BASE_URL)
        route.side_effect = [
            httpx.Response(200, text=sample_html),
            httpx.Response(200, text="<html><body></body></html>"),
        ]

        alert = SavedAlert(
            name="test",
            criteria=SearchCriteria(keywords="Python", max_results=10),
            enabled=True,
        )

        jobs = await service.run_alert(alert, only_new=True, save_to_db=True)

        # Should only return the new job (987654321), not the known one
        assert len(jobs) == 1
        assert jobs[0].id == "987654321"

        # Both jobs should now be in DB (original + new)
        assert service.get_job_count() == 2

    def test_get_stored_jobs(self, test_settings: Settings) -> None:
        """Test retrieving stored jobs."""
        service = JobService(test_settings)

        # Manually add some jobs to DB
        jobs = [
            JobPosting(
                id="1",
                title="Job 1",
                company="Company A",
                location="Paris",
                url="https://linkedin.com/jobs/view/1",
            ),
            JobPosting(
                id="2",
                title="Job 2",
                company="Company B",
                location="Lyon",
                url="https://linkedin.com/jobs/view/2",
            ),
        ]

        # Use internal sqlite store to save
        service._sqlite_store.save(jobs)

        retrieved = service.get_stored_jobs(limit=10)

        assert len(retrieved) == 2
