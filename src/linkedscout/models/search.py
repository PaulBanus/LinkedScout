"""Search criteria and alert models."""

from enum import Enum
from typing import TYPE_CHECKING, Self

import yaml
from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field

if TYPE_CHECKING:
    from pathlib import Path


class TimeFilter(str, Enum):
    """Time filter for job search."""

    PAST_24H = "r86400"
    PAST_WEEK = "r604800"
    PAST_MONTH = "r2592000"
    ANY_TIME = ""


class WorkModel(str, Enum):
    """Work model/location type."""

    ON_SITE = "1"
    REMOTE = "2"
    HYBRID = "3"


class JobType(str, Enum):
    """Job/contract type."""

    FULL_TIME = "F"
    PART_TIME = "P"
    CONTRACT = "C"
    INTERNSHIP = "I"
    TEMPORARY = "T"
    VOLUNTEER = "V"


@beartype
def _serialize_enum(enum_value: Enum) -> str:
    """Serialize enum to human-readable string (lowercase name)."""
    return enum_value.name.lower()


@beartype
def _deserialize_time_filter(value: str) -> TimeFilter:
    """Deserialize time filter (supports both old and new formats)."""
    try:
        return TimeFilter[value.upper()]
    except KeyError:
        return TimeFilter(value)  # Fall back to raw value


@beartype
def _deserialize_work_model(value: str) -> WorkModel:
    """Deserialize work model (supports both old and new formats)."""
    try:
        return WorkModel[value.upper()]
    except KeyError:
        return WorkModel(value)


@beartype
def _deserialize_job_type(value: str) -> JobType:
    """Deserialize job type (supports both old and new formats)."""
    try:
        return JobType[value.upper()]
    except KeyError:
        return JobType(value)


class SearchCriteria(BaseModel):
    """Search criteria for LinkedIn jobs."""

    model_config = ConfigDict(frozen=True)

    keywords: str = Field(description="Search keywords")
    location: str = Field(default="", description="Location to search in")
    time_filter: TimeFilter = Field(
        default=TimeFilter.PAST_WEEK, description="Time filter for results"
    )
    work_models: list[WorkModel] = Field(
        default_factory=list, description="Work models to filter by"
    )
    job_types: list[JobType] = Field(
        default_factory=list, description="Job types to filter by"
    )
    max_results: int = Field(
        default=100, ge=1, le=1000, description="Maximum results to fetch"
    )

    @beartype
    def to_params(self) -> dict[str, str]:
        """Convert criteria to LinkedIn API query parameters."""
        params: dict[str, str] = {"keywords": self.keywords}

        if self.location:
            params["location"] = self.location

        if self.time_filter != TimeFilter.ANY_TIME:
            params["f_TPR"] = self.time_filter.value

        if self.work_models:
            params["f_WT"] = ",".join(wm.value for wm in self.work_models)

        if self.job_types:
            params["f_JT"] = ",".join(jt.value for jt in self.job_types)

        return params


class SavedAlert(BaseModel):
    """A saved job search alert."""

    model_config = ConfigDict(frozen=True)

    name: str = Field(description="Alert name (used as filename)")
    criteria: SearchCriteria = Field(description="Search criteria for this alert")
    enabled: bool = Field(default=True, description="Whether the alert is active")

    @beartype
    def to_yaml(self) -> str:
        """Serialize alert to YAML string."""
        data = {
            "name": self.name,
            "criteria": {
                "keywords": self.criteria.keywords,
                "location": self.criteria.location,
                "time_filter": _serialize_enum(self.criteria.time_filter),
                "work_models": [
                    _serialize_enum(wm) for wm in self.criteria.work_models
                ],
                "job_types": [_serialize_enum(jt) for jt in self.criteria.job_types],
                "max_results": self.criteria.max_results,
            },
            "enabled": self.enabled,
        }
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> Self:
        """Load alert from YAML string."""
        data = yaml.safe_load(yaml_content)
        if not isinstance(data, dict):
            msg = "Invalid YAML: expected a mapping"
            raise ValueError(msg)
        if "name" not in data or not isinstance(data["name"], str):
            msg = "Invalid YAML: 'name' must be a string"
            raise ValueError(msg)
        if "criteria" not in data or not isinstance(data["criteria"], dict):
            msg = "Invalid YAML: 'criteria' must be a mapping"
            raise ValueError(msg)
        criteria_data = data["criteria"]

        criteria = SearchCriteria(
            keywords=criteria_data["keywords"],
            location=criteria_data.get("location", ""),
            time_filter=_deserialize_time_filter(criteria_data.get("time_filter", "")),
            work_models=[
                _deserialize_work_model(wm)
                for wm in criteria_data.get("work_models", [])
            ],
            job_types=[
                _deserialize_job_type(jt) for jt in criteria_data.get("job_types", [])
            ],
            max_results=criteria_data.get("max_results", 100),
        )

        return cls(
            name=data["name"],
            criteria=criteria,
            enabled=data.get("enabled", True),
        )

    @classmethod
    def from_file(cls, path: "Path") -> Self:
        """Load alert from YAML file."""
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    def save(self, alerts_dir: "Path") -> "Path":
        """Save alert to YAML file."""
        from pathlib import Path as _Path

        safe_name = _Path(self.name).name
        if safe_name != self.name or not self.name or self.name in (".", ".."):
            msg = f"Invalid alert name: '{self.name}' contains path separators"
            raise ValueError(msg)
        file_path = alerts_dir / f"{self.name}.yaml"
        file_path.write_text(self.to_yaml(), encoding="utf-8")
        return file_path


class AlertsConfig(BaseModel):
    """Configuration containing multiple saved alerts."""

    model_config = ConfigDict(frozen=True)

    alerts: list[SavedAlert] = Field(
        default_factory=list, description="List of saved alerts"
    )

    @beartype
    def to_yaml(self) -> str:
        """Serialize all alerts to YAML string."""
        alerts_data = []
        for alert in self.alerts:
            alert_dict = {
                "name": alert.name,
                "enabled": alert.enabled,
                "criteria": {
                    "keywords": alert.criteria.keywords,
                    "location": alert.criteria.location,
                    "time_filter": _serialize_enum(alert.criteria.time_filter),
                    "work_models": [
                        _serialize_enum(wm) for wm in alert.criteria.work_models
                    ],
                    "job_types": [
                        _serialize_enum(jt) for jt in alert.criteria.job_types
                    ],
                    "max_results": alert.criteria.max_results,
                },
            }
            alerts_data.append(alert_dict)

        data = {"alerts": alerts_data}
        return yaml.dump(data, default_flow_style=False, allow_unicode=True)

    @classmethod
    def from_yaml(cls, yaml_content: str) -> Self:
        """Parse multi-alert YAML content."""
        data = yaml.safe_load(yaml_content)
        if not data or "alerts" not in data:
            return cls(alerts=[])

        alerts = []
        for i, alert_data in enumerate(data["alerts"]):
            if not isinstance(alert_data, dict):
                msg = f"Invalid alert at index {i}: expected a mapping, got {type(alert_data).__name__}"
                raise ValueError(msg)
            if "name" not in alert_data:
                msg = f"Invalid alert at index {i}: missing required key 'name'"
                raise ValueError(msg)
            if "criteria" not in alert_data:
                msg = f"Invalid alert at index {i} ('{alert_data['name']}'): missing required key 'criteria'"
                raise ValueError(msg)
            criteria_data = alert_data["criteria"]
            if not isinstance(criteria_data, dict):
                msg = f"Invalid alert at index {i} ('{alert_data['name']}'): 'criteria' must be a mapping, got {type(criteria_data).__name__}"
                raise ValueError(msg)

            criteria = SearchCriteria(
                keywords=criteria_data["keywords"],
                location=criteria_data.get("location", ""),
                time_filter=_deserialize_time_filter(
                    criteria_data.get("time_filter", "")
                ),
                work_models=[
                    _deserialize_work_model(wm)
                    for wm in criteria_data.get("work_models", [])
                ],
                job_types=[
                    _deserialize_job_type(jt)
                    for jt in criteria_data.get("job_types", [])
                ],
                max_results=criteria_data.get("max_results", 100),
            )

            alert = SavedAlert(
                name=alert_data["name"],
                criteria=criteria,
                enabled=alert_data.get("enabled", True),
            )
            alerts.append(alert)

        return cls(alerts=alerts)

    @classmethod
    def from_file(cls, path: "Path") -> Self:
        """Load alerts from YAML file."""
        if not path.exists():
            return cls(alerts=[])
        return cls.from_yaml(path.read_text(encoding="utf-8"))

    def save(self, path: "Path") -> None:
        """Write alerts to YAML file."""
        path.write_text(self.to_yaml(), encoding="utf-8")

    @beartype
    def get_alert(self, name: str) -> SavedAlert | None:
        """Find alert by name."""
        for alert in self.alerts:
            if alert.name == name:
                return alert
        return None

    def add_alert(self, alert: SavedAlert) -> Self:
        """Return new config with added alert."""
        # Check if alert with same name exists
        if any(a.name == alert.name for a in self.alerts):
            msg = f"Alert with name '{alert.name}' already exists"
            raise ValueError(msg)
        return self.model_copy(update={"alerts": [*self.alerts, alert]})

    def update_alert(self, name: str, **updates: object) -> Self:
        """Return new config with updated alert."""
        alert = self.get_alert(name)
        if alert is None:
            msg = f"Alert '{name}' not found"
            raise ValueError(msg)

        # Create updated alert
        updated_alert = alert.model_copy(update=updates)

        # Replace old alert with updated one
        new_alerts = [updated_alert if a.name == name else a for a in self.alerts]
        return self.model_copy(update={"alerts": new_alerts})

    def remove_alert(self, name: str) -> Self:
        """Return new config without specified alert."""
        if not any(a.name == name for a in self.alerts):
            msg = f"Alert '{name}' not found"
            raise ValueError(msg)

        new_alerts = [a for a in self.alerts if a.name != name]
        return self.model_copy(update={"alerts": new_alerts})
