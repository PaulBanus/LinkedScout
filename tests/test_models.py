"""Tests for data models."""

from datetime import datetime
from enum import Enum
from pathlib import Path

import pytest

from linkedscout.models.job import JobPosting, _parse_bool
from linkedscout.models.search import (
    AlertsConfig,
    JobType,
    SavedAlert,
    SearchCriteria,
    TimeFilter,
    WorkModel,
)


class TestJobPosting:
    """Tests for JobPosting model."""

    def test_create_job_posting(self) -> None:
        """Test creating a job posting."""
        job = JobPosting(
            id="12345",
            title="Python Developer",
            company="Acme Corp",
            location="Paris, France",
            url="https://www.linkedin.com/jobs/view/12345",
        )

        assert job.id == "12345"
        assert job.title == "Python Developer"
        assert job.company == "Acme Corp"
        assert job.location == "Paris, France"
        assert str(job.url) == "https://www.linkedin.com/jobs/view/12345"
        assert job.is_remote is False

    def test_job_posting_with_optional_fields(self) -> None:
        """Test job posting with all optional fields."""
        posted = datetime(2024, 1, 15, 10, 0, 0)
        job = JobPosting(
            id="12345",
            title="Python Developer",
            company="Acme Corp",
            location="Remote",
            url="https://www.linkedin.com/jobs/view/12345",
            posted_at=posted,
            description_snippet="Looking for a Python developer...",
            salary="50k-70k EUR",
            is_remote=True,
            applicants_count="25 applicants",
        )

        assert job.posted_at == posted
        assert job.description_snippet == "Looking for a Python developer..."
        assert job.salary == "50k-70k EUR"
        assert job.is_remote is True
        assert job.applicants_count == "25 applicants"

    def test_job_posting_to_dict(self) -> None:
        """Test converting job posting to dictionary."""
        job = JobPosting(
            id="12345",
            title="Python Developer",
            company="Acme Corp",
            location="Paris",
            url="https://www.linkedin.com/jobs/view/12345",
            is_remote=False,
        )

        data = job.to_dict()

        assert data["id"] == "12345"
        assert data["title"] == "Python Developer"
        assert data["url"] == "https://www.linkedin.com/jobs/view/12345"
        assert "scraped_at" in data

    def test_job_posting_from_dict(self) -> None:
        """Test creating job posting from dictionary."""
        data: dict[str, str | bool | None] = {
            "id": "12345",
            "title": "Python Developer",
            "company": "Acme Corp",
            "location": "Paris",
            "url": "https://www.linkedin.com/jobs/view/12345",
            "posted_at": "2024-01-15T10:00:00",
            "is_remote": True,
        }

        job = JobPosting.from_dict(data)

        assert job.id == "12345"
        assert job.title == "Python Developer"
        assert job.is_remote is True
        assert job.posted_at == datetime(2024, 1, 15, 10, 0, 0)

    def test_job_posting_frozen(self) -> None:
        """Test that job posting is immutable."""
        from pydantic import ValidationError

        job = JobPosting(
            id="12345",
            title="Python Developer",
            company="Acme Corp",
            location="Paris",
            url="https://www.linkedin.com/jobs/view/12345",
        )

        with pytest.raises(ValidationError):
            job.title = "New Title"  # type: ignore[misc]


class TestSearchCriteria:
    """Tests for SearchCriteria model."""

    def test_create_search_criteria(self) -> None:
        """Test creating search criteria."""
        criteria = SearchCriteria(
            keywords="Python Developer",
            location="Paris",
        )

        assert criteria.keywords == "Python Developer"
        assert criteria.location == "Paris"
        assert criteria.time_filter == TimeFilter.PAST_WEEK
        assert criteria.max_results == 100

    def test_search_criteria_with_filters(self) -> None:
        """Test search criteria with work model and job type filters."""
        criteria = SearchCriteria(
            keywords="Python",
            location="France",
            time_filter=TimeFilter.PAST_24H,
            work_models=[WorkModel.REMOTE, WorkModel.HYBRID],
            job_types=[JobType.FULL_TIME],
            max_results=50,
        )

        assert criteria.time_filter == TimeFilter.PAST_24H
        assert WorkModel.REMOTE in criteria.work_models
        assert WorkModel.HYBRID in criteria.work_models
        assert JobType.FULL_TIME in criteria.job_types
        assert criteria.max_results == 50

    def test_search_criteria_to_params(self) -> None:
        """Test converting criteria to API parameters."""
        criteria = SearchCriteria(
            keywords="Python Developer",
            location="Paris",
            time_filter=TimeFilter.PAST_24H,
            work_models=[WorkModel.REMOTE],
            job_types=[JobType.FULL_TIME, JobType.CONTRACT],
        )

        params = criteria.to_params()

        assert params["keywords"] == "Python Developer"
        assert params["location"] == "Paris"
        assert params["f_TPR"] == "r86400"
        assert params["f_WT"] == "2"
        assert params["f_JT"] == "F,C"

    def test_search_criteria_to_params_minimal(self) -> None:
        """Test params with only keywords."""
        criteria = SearchCriteria(keywords="Python")

        params = criteria.to_params()

        assert params["keywords"] == "Python"
        assert "location" not in params
        assert params["f_TPR"] == "r604800"  # Default is past week


class TestSavedAlert:
    """Tests for SavedAlert model."""

    def test_create_saved_alert(self) -> None:
        """Test creating a saved alert."""
        criteria = SearchCriteria(keywords="Python", location="Paris")
        alert = SavedAlert(name="python-paris", criteria=criteria)

        assert alert.name == "python-paris"
        assert alert.criteria.keywords == "Python"
        assert alert.enabled is True

    def test_alert_to_yaml(self) -> None:
        """Test serializing alert to YAML."""
        criteria = SearchCriteria(
            keywords="Python Developer",
            location="France",
            time_filter=TimeFilter.PAST_24H,
            work_models=[WorkModel.REMOTE],
        )
        alert = SavedAlert(name="test-alert", criteria=criteria, enabled=True)

        yaml_str = alert.to_yaml()

        assert "name: test-alert" in yaml_str
        assert "keywords: Python Developer" in yaml_str
        assert "location: France" in yaml_str
        assert "time_filter: past_24h" in yaml_str
        assert "enabled: true" in yaml_str

    def test_alert_from_yaml(self) -> None:
        """Test loading alert from YAML (new format)."""
        yaml_content = """
name: test-alert
criteria:
  keywords: Python Developer
  location: France
  time_filter: past_24h
  work_models: ['remote']
  job_types: ['full_time']
  max_results: 50
enabled: true
"""
        alert = SavedAlert.from_yaml(yaml_content)

        assert alert.name == "test-alert"
        assert alert.criteria.keywords == "Python Developer"
        assert alert.criteria.location == "France"
        assert alert.criteria.time_filter == TimeFilter.PAST_24H
        assert WorkModel.REMOTE in alert.criteria.work_models
        assert JobType.FULL_TIME in alert.criteria.job_types
        assert alert.criteria.max_results == 50
        assert alert.enabled is True

    def test_alert_from_yaml_backwards_compatible(self) -> None:
        """Test loading alert from YAML (old format for backwards compatibility)."""
        yaml_content = """
name: test-alert
criteria:
  keywords: Python Developer
  location: France
  time_filter: r86400
  work_models: ['2']
  job_types: ['F']
  max_results: 50
enabled: true
"""
        alert = SavedAlert.from_yaml(yaml_content)

        assert alert.name == "test-alert"
        assert alert.criteria.keywords == "Python Developer"
        assert alert.criteria.location == "France"
        assert alert.criteria.time_filter == TimeFilter.PAST_24H
        assert WorkModel.REMOTE in alert.criteria.work_models
        assert JobType.FULL_TIME in alert.criteria.job_types
        assert alert.criteria.max_results == 50
        assert alert.enabled is True

    def test_alert_save_and_load(self, temp_dir: Path) -> None:
        """Test saving and loading alert from file."""
        criteria = SearchCriteria(keywords="Test", location="Paris")
        alert = SavedAlert(name="test-save", criteria=criteria)

        # Save
        path = alert.save(temp_dir)
        assert path.exists()
        assert path.name == "test-save.yaml"

        # Load
        loaded = SavedAlert.from_file(path)
        assert loaded.name == alert.name
        assert loaded.criteria.keywords == alert.criteria.keywords


class TestAlertsConfig:
    """Tests for AlertsConfig model."""

    def test_create_empty_config(self) -> None:
        """Test creating an empty config."""
        config = AlertsConfig()
        assert config.alerts == []

    def test_create_config_with_alerts(self) -> None:
        """Test creating config with alerts."""
        alert1 = SavedAlert(
            name="alert1",
            criteria=SearchCriteria(keywords="Python"),
        )
        alert2 = SavedAlert(
            name="alert2",
            criteria=SearchCriteria(keywords="Java"),
        )
        config = AlertsConfig(alerts=[alert1, alert2])

        assert len(config.alerts) == 2
        assert config.alerts[0].name == "alert1"
        assert config.alerts[1].name == "alert2"

    def test_config_to_yaml(self) -> None:
        """Test serializing config to YAML."""
        alert1 = SavedAlert(
            name="test-alert-1",
            criteria=SearchCriteria(keywords="Python", location="Paris"),
            enabled=True,
        )
        alert2 = SavedAlert(
            name="test-alert-2",
            criteria=SearchCriteria(keywords="Java", location="London"),
            enabled=False,
        )
        config = AlertsConfig(alerts=[alert1, alert2])

        yaml_str = config.to_yaml()

        assert "alerts:" in yaml_str
        assert "name: test-alert-1" in yaml_str
        assert "name: test-alert-2" in yaml_str
        assert "keywords: Python" in yaml_str
        assert "keywords: Java" in yaml_str

    def test_config_from_yaml(self) -> None:
        """Test loading config from YAML (new format)."""
        yaml_content = """
alerts:
  - name: alert1
    enabled: true
    criteria:
      keywords: Python
      location: Paris
      time_filter: past_24h
      work_models: ['remote']
      job_types: []
      max_results: 100
  - name: alert2
    enabled: false
    criteria:
      keywords: Java
      location: London
      time_filter: past_week
      work_models: []
      job_types: ['full_time']
      max_results: 50
"""
        config = AlertsConfig.from_yaml(yaml_content)

        assert len(config.alerts) == 2
        assert config.alerts[0].name == "alert1"
        assert config.alerts[0].enabled is True
        assert config.alerts[0].criteria.keywords == "Python"
        assert config.alerts[1].name == "alert2"
        assert config.alerts[1].enabled is False
        assert config.alerts[1].criteria.keywords == "Java"

    def test_config_from_empty_yaml(self) -> None:
        """Test loading config from empty YAML."""
        config = AlertsConfig.from_yaml("")
        assert config.alerts == []

    def test_config_save_and_load(self, temp_dir: Path) -> None:
        """Test saving and loading config from file."""
        alert1 = SavedAlert(
            name="test1",
            criteria=SearchCriteria(keywords="Python"),
        )
        alert2 = SavedAlert(
            name="test2",
            criteria=SearchCriteria(keywords="Java"),
        )
        config = AlertsConfig(alerts=[alert1, alert2])

        # Save
        file_path = temp_dir / "test_alerts.yaml"
        config.save(file_path)
        assert file_path.exists()

        # Load
        loaded = AlertsConfig.from_file(file_path)
        assert len(loaded.alerts) == 2
        assert loaded.alerts[0].name == "test1"
        assert loaded.alerts[1].name == "test2"

    def test_config_from_nonexistent_file(self, temp_dir: Path) -> None:
        """Test loading from nonexistent file returns empty config."""
        file_path = temp_dir / "nonexistent.yaml"
        config = AlertsConfig.from_file(file_path)
        assert config.alerts == []

    def test_get_alert(self) -> None:
        """Test getting alert by name."""
        alert1 = SavedAlert(name="alert1", criteria=SearchCriteria(keywords="Python"))
        alert2 = SavedAlert(name="alert2", criteria=SearchCriteria(keywords="Java"))
        config = AlertsConfig(alerts=[alert1, alert2])

        found = config.get_alert("alert1")
        assert found is not None
        assert found.name == "alert1"

        not_found = config.get_alert("nonexistent")
        assert not_found is None

    def test_add_alert(self) -> None:
        """Test adding alert to config."""
        alert1 = SavedAlert(name="alert1", criteria=SearchCriteria(keywords="Python"))
        config = AlertsConfig(alerts=[alert1])

        alert2 = SavedAlert(name="alert2", criteria=SearchCriteria(keywords="Java"))
        new_config = config.add_alert(alert2)

        # Original config unchanged (immutable)
        assert len(config.alerts) == 1

        # New config has both alerts
        assert len(new_config.alerts) == 2
        assert new_config.get_alert("alert2") is not None

    def test_add_duplicate_alert_raises_error(self) -> None:
        """Test adding alert with duplicate name raises error."""
        alert1 = SavedAlert(name="alert1", criteria=SearchCriteria(keywords="Python"))
        config = AlertsConfig(alerts=[alert1])

        duplicate = SavedAlert(name="alert1", criteria=SearchCriteria(keywords="Java"))

        with pytest.raises(ValueError, match="already exists"):
            config.add_alert(duplicate)

    def test_update_alert(self) -> None:
        """Test updating alert in config."""
        alert = SavedAlert(
            name="alert1",
            criteria=SearchCriteria(keywords="Python"),
            enabled=True,
        )
        config = AlertsConfig(alerts=[alert])

        new_config = config.update_alert("alert1", enabled=False)

        # Original config unchanged
        original = config.get_alert("alert1")
        assert original is not None
        assert original.enabled is True

        # New config has updated alert
        updated = new_config.get_alert("alert1")
        assert updated is not None
        assert updated.enabled is False

    def test_update_nonexistent_alert_raises_error(self) -> None:
        """Test updating nonexistent alert raises error."""
        config = AlertsConfig()

        with pytest.raises(ValueError, match="not found"):
            config.update_alert("nonexistent", enabled=False)

    def test_remove_alert(self) -> None:
        """Test removing alert from config."""
        alert1 = SavedAlert(name="alert1", criteria=SearchCriteria(keywords="Python"))
        alert2 = SavedAlert(name="alert2", criteria=SearchCriteria(keywords="Java"))
        config = AlertsConfig(alerts=[alert1, alert2])

        new_config = config.remove_alert("alert1")

        # Original config unchanged
        assert len(config.alerts) == 2

        # New config has only alert2
        assert len(new_config.alerts) == 1
        assert new_config.get_alert("alert1") is None
        assert new_config.get_alert("alert2") is not None

    def test_remove_nonexistent_alert_raises_error(self) -> None:
        """Test removing nonexistent alert raises error."""
        config = AlertsConfig()

        with pytest.raises(ValueError, match="not found"):
            config.remove_alert("nonexistent")


class TestEnumSerialization:
    """Tests for enum serialization and deserialization."""

    @pytest.mark.parametrize(
        ("enum_value", "expected_string"),
        [
            (TimeFilter.PAST_24H, "past_24h"),
            (TimeFilter.PAST_WEEK, "past_week"),
            (TimeFilter.PAST_MONTH, "past_month"),
            (TimeFilter.ANY_TIME, "any_time"),
            (WorkModel.ON_SITE, "on_site"),
            (WorkModel.REMOTE, "remote"),
            (WorkModel.HYBRID, "hybrid"),
            (JobType.FULL_TIME, "full_time"),
            (JobType.PART_TIME, "part_time"),
            (JobType.CONTRACT, "contract"),
            (JobType.INTERNSHIP, "internship"),
            (JobType.TEMPORARY, "temporary"),
            (JobType.VOLUNTEER, "volunteer"),
        ],
    )
    def test_serialize_enum(self, enum_value: Enum, expected_string: str) -> None:
        """Test that enums serialize to lowercase names."""
        from linkedscout.models.search import _serialize_enum

        result = _serialize_enum(enum_value)
        assert result == expected_string

    @pytest.mark.parametrize(
        ("string_value", "expected_enum"),
        [
            ("past_24h", TimeFilter.PAST_24H),
            ("PAST_24H", TimeFilter.PAST_24H),
            ("Past_24H", TimeFilter.PAST_24H),
            ("r86400", TimeFilter.PAST_24H),  # Old format
            ("past_week", TimeFilter.PAST_WEEK),
            ("r604800", TimeFilter.PAST_WEEK),  # Old format
            ("past_month", TimeFilter.PAST_MONTH),
            ("r2592000", TimeFilter.PAST_MONTH),  # Old format
            ("any_time", TimeFilter.ANY_TIME),
            ("", TimeFilter.ANY_TIME),  # Old format
        ],
    )
    def test_deserialize_time_filter(
        self, string_value: str, expected_enum: TimeFilter
    ) -> None:
        """Test that time filters deserialize from both old and new formats."""
        from linkedscout.models.search import _deserialize_time_filter

        result = _deserialize_time_filter(string_value)
        assert result == expected_enum

    @pytest.mark.parametrize(
        ("string_value", "expected_enum"),
        [
            ("on_site", WorkModel.ON_SITE),
            ("ON_SITE", WorkModel.ON_SITE),
            ("1", WorkModel.ON_SITE),  # Old format
            ("remote", WorkModel.REMOTE),
            ("2", WorkModel.REMOTE),  # Old format
            ("hybrid", WorkModel.HYBRID),
            ("3", WorkModel.HYBRID),  # Old format
        ],
    )
    def test_deserialize_work_model(
        self, string_value: str, expected_enum: WorkModel
    ) -> None:
        """Test that work models deserialize from both old and new formats."""
        from linkedscout.models.search import _deserialize_work_model

        result = _deserialize_work_model(string_value)
        assert result == expected_enum

    @pytest.mark.parametrize(
        ("string_value", "expected_enum"),
        [
            ("full_time", JobType.FULL_TIME),
            ("FULL_TIME", JobType.FULL_TIME),
            ("F", JobType.FULL_TIME),  # Old format
            ("part_time", JobType.PART_TIME),
            ("P", JobType.PART_TIME),  # Old format
            ("contract", JobType.CONTRACT),
            ("C", JobType.CONTRACT),  # Old format
            ("internship", JobType.INTERNSHIP),
            ("I", JobType.INTERNSHIP),  # Old format
            ("temporary", JobType.TEMPORARY),
            ("T", JobType.TEMPORARY),  # Old format
            ("volunteer", JobType.VOLUNTEER),
            ("V", JobType.VOLUNTEER),  # Old format
        ],
    )
    def test_deserialize_job_type(
        self, string_value: str, expected_enum: JobType
    ) -> None:
        """Test that job types deserialize from both old and new formats."""
        from linkedscout.models.search import _deserialize_job_type

        result = _deserialize_job_type(string_value)
        assert result == expected_enum


class TestParseBool:
    """Tests for _parse_bool helper."""

    @pytest.mark.parametrize(
        ("value", "expected"),
        [
            (True, True),
            (False, False),
            (1, True),
            (0, False),
            ("true", True),
            ("True", True),
            ("TRUE", True),
            ("false", False),
            ("False", False),
            ("FALSE", False),
            ("yes", True),
            ("Yes", True),
            ("no", False),
            ("No", False),
            ("1", True),
            ("0", False),
            (None, False),
            ("", False),
        ],
    )
    def test_parse_bool(self, value: str | bool | int | None, expected: bool) -> None:
        """Test _parse_bool with various inputs."""
        assert _parse_bool(value) is expected

    def test_parse_bool_unrecognized_string(self) -> None:
        """Test _parse_bool raises ValueError for unrecognized strings."""
        with pytest.raises(ValueError, match="Cannot convert"):
            _parse_bool("maybe")

    def test_job_posting_from_dict_with_string_false(self) -> None:
        """Test that JobPosting.from_dict handles string 'false' correctly."""
        data: dict[str, str | bool | None] = {
            "id": "12345",
            "title": "Python Developer",
            "company": "Acme Corp",
            "location": "Paris",
            "url": "https://www.linkedin.com/jobs/view/12345",
            "is_remote": "false",
        }

        job = JobPosting.from_dict(data)
        assert job.is_remote is False


class TestSavedAlertFromYamlValidation:
    """Tests for SavedAlert.from_yaml input validation."""

    @pytest.mark.parametrize(
        "yaml_content",
        [
            "",
            "null",
            "- item1\n- item2",
            "name: test\n",  # missing criteria
            "criteria:\n  keywords: Python\n",  # missing name
            "name: test\ncriteria: not-a-dict\n",  # criteria not a dict
            "name: 123\ncriteria:\n  keywords: Python\n",  # name not a string
        ],
        ids=[
            "empty",
            "null",
            "list",
            "missing_criteria",
            "missing_name",
            "criteria_not_dict",
            "name_not_string",
        ],
    )
    def test_saved_alert_from_yaml_invalid_structure(self, yaml_content: str) -> None:
        """Test that invalid YAML structures raise ValueError."""
        with pytest.raises(ValueError, match="Invalid YAML"):
            SavedAlert.from_yaml(yaml_content)


class TestSavedAlertSavePathTraversal:
    """Tests for SavedAlert.save() path traversal prevention."""

    @pytest.mark.parametrize(
        "name",
        [
            "../etc/passwd",
            "/absolute",
            "sub/dir",
            ".",
            "..",
        ],
    )
    def test_saved_alert_save_rejects_path_traversal(
        self, name: str, temp_dir: Path
    ) -> None:
        """Test that save() rejects names with path separators."""
        criteria = SearchCriteria(keywords="Python")
        alert = SavedAlert(name=name, criteria=criteria)

        with pytest.raises(ValueError, match="Invalid alert name"):
            alert.save(temp_dir)

    def test_saved_alert_save_accepts_valid_name(self, temp_dir: Path) -> None:
        """Test that save() works with valid names."""
        criteria = SearchCriteria(keywords="Python")
        alert = SavedAlert(name="valid-alert-name", criteria=criteria)

        path = alert.save(temp_dir)
        assert path.exists()
        assert path.name == "valid-alert-name.yaml"
