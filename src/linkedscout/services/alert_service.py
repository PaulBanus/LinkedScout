"""Service for managing job alerts."""

import logging
from pathlib import Path

from beartype import beartype

from linkedscout.config import Settings, get_settings
from linkedscout.models.search import (
    AlertsConfig,
    JobType,
    SavedAlert,
    SearchCriteria,
    TimeFilter,
    WorkModel,
)

logger = logging.getLogger(__name__)


class AlertService:
    """Service for managing saved job alerts."""

    @beartype
    def __init__(self, settings: Settings | None = None) -> None:
        """Initialize alert service.

        Args:
            settings: Application settings. Uses defaults if not provided.
        """
        self._settings = settings or get_settings()
        self._alerts_file = self._settings.alerts_file

    @beartype
    def _load_config(self) -> AlertsConfig:
        """Load alerts configuration from file.

        Returns:
            AlertsConfig instance (empty if file doesn't exist).
        """
        return AlertsConfig.from_file(self._alerts_file)

    @beartype
    def _save_config(self, config: AlertsConfig) -> None:
        """Save alerts configuration to file.

        Args:
            config: AlertsConfig to save.
        """
        # Ensure parent directory exists
        self._alerts_file.parent.mkdir(parents=True, exist_ok=True)
        config.save(self._alerts_file)

    @beartype
    def list_alerts(self) -> list[SavedAlert]:
        """List all saved alerts.

        Returns:
            List of saved alerts sorted by name.
        """
        config = self._load_config()
        return sorted(config.alerts, key=lambda a: a.name)

    @beartype
    def get_alert(self, name: str) -> SavedAlert | None:
        """Get a specific alert by name.

        Args:
            name: Alert name.

        Returns:
            The alert if found, None otherwise.
        """
        config = self._load_config()
        return config.get_alert(name)

    @beartype
    def create_alert(
        self,
        name: str,
        keywords: str,
        location: str = "",
        time_filter: TimeFilter = TimeFilter.PAST_WEEK,
        work_models: list[WorkModel] | None = None,
        job_types: list[JobType] | None = None,
        max_results: int = 100,
        enabled: bool = True,
    ) -> SavedAlert:
        """Create and save a new alert.

        Args:
            name: Unique name for the alert.
            keywords: Search keywords.
            location: Location to search in.
            time_filter: Time filter for results.
            work_models: Work models to filter by.
            job_types: Job types to filter by.
            max_results: Maximum results per search.
            enabled: Whether the alert is active.

        Returns:
            The created alert.

        Raises:
            ValueError: If alert with same name already exists.
        """
        criteria = SearchCriteria(
            keywords=keywords,
            location=location,
            time_filter=time_filter,
            work_models=work_models or [],
            job_types=job_types or [],
            max_results=max_results,
        )

        alert = SavedAlert(name=name, criteria=criteria, enabled=enabled)

        config = self._load_config()
        new_config = config.add_alert(alert)
        self._save_config(new_config)

        return alert

    @beartype
    def update_alert(
        self,
        name: str,
        enabled: bool | None = None,
        keywords: str | None = None,
        location: str | None = None,
    ) -> SavedAlert | None:
        """Update an existing alert.

        Args:
            name: Name of the alert to update.
            enabled: New enabled state (optional).
            keywords: New keywords (optional).
            location: New location (optional).

        Returns:
            Updated alert or None if not found.
        """
        config = self._load_config()
        existing = config.get_alert(name)
        if existing is None:
            return None

        # Build update dict for only changed fields
        updates: dict[str, object] = {}

        if enabled is not None:
            updates["enabled"] = enabled

        if keywords is not None or location is not None:
            # Need to update criteria
            new_keywords = keywords if keywords is not None else existing.criteria.keywords
            new_location = location if location is not None else existing.criteria.location

            new_criteria = SearchCriteria(
                keywords=new_keywords,
                location=new_location,
                time_filter=existing.criteria.time_filter,
                work_models=list(existing.criteria.work_models),
                job_types=list(existing.criteria.job_types),
                max_results=existing.criteria.max_results,
            )
            updates["criteria"] = new_criteria

        try:
            new_config = config.update_alert(name, **updates)
            self._save_config(new_config)
            return new_config.get_alert(name)
        except ValueError:
            return None

    @beartype
    def delete_alert(self, name: str) -> bool:
        """Delete an alert.

        Args:
            name: Name of the alert to delete.

        Returns:
            True if deleted, False if not found.
        """
        config = self._load_config()
        if config.get_alert(name) is None:
            return False

        try:
            new_config = config.remove_alert(name)
            self._save_config(new_config)
            return True
        except ValueError:
            return False

    @beartype
    def get_enabled_alerts(self) -> list[SavedAlert]:
        """Get all enabled alerts.

        Returns:
            List of enabled alerts.
        """
        return [alert for alert in self.list_alerts() if alert.enabled]

    @beartype
    def get_alerts_file(self) -> Path:
        """Get the alerts file path.

        Returns:
            Path to the alerts.yaml file.
        """
        return self._alerts_file

    @staticmethod
    @beartype
    def migrate_from_directory(alerts_dir: Path, alerts_file: Path) -> int:
        """Migrate alerts from directory-based storage to single file.

        Args:
            alerts_dir: Directory containing individual alert YAML files.
            alerts_file: Target alerts.yaml file path.

        Returns:
            Number of alerts migrated.

        Raises:
            FileNotFoundError: If alerts_dir doesn't exist.
            ValueError: If alerts_file already exists.
        """
        if not alerts_dir.exists():
            msg = f"Alerts directory not found: {alerts_dir}"
            raise FileNotFoundError(msg)

        if alerts_file.exists():
            msg = f"Target file already exists: {alerts_file}"
            raise ValueError(msg)

        # Load all alerts from directory
        alerts: list[SavedAlert] = []
        for path in alerts_dir.glob("*.yaml"):
            try:
                alert = SavedAlert.from_file(path)
                alerts.append(alert)
                logger.info("Loaded alert: %s", alert.name)
            except Exception:
                logger.warning("Failed to load alert file: %s", path, exc_info=True)
                continue

        # Create config and save
        config = AlertsConfig(alerts=alerts)
        alerts_file.parent.mkdir(parents=True, exist_ok=True)
        config.save(alerts_file)

        logger.info("Migrated %d alerts to %s", len(alerts), alerts_file)
        return len(alerts)
