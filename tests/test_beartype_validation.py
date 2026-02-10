"""Tests for beartype runtime type validation."""

from pathlib import Path

import pytest
from beartype.roar import (
    BeartypeCallHintParamViolation,
)

from linkedscout.models.job import JobPosting
from linkedscout.models.search import SavedAlert, SearchCriteria, TimeFilter
from linkedscout.scraper.parser import HTMLParser
from linkedscout.storage.json_store import JsonStore
from linkedscout.storage.sqlite_store import SqliteStore
from linkedscout.utils.rate_limiter import RateLimiter


def test_job_posting_to_dict_invalid_type() -> None:
    """Test that JobPosting.to_dict validates return type."""
    job = JobPosting(
        id="123",
        title="Software Engineer",
        company="Test Corp",
        location="Remote",
        url="https://linkedin.com/jobs/view/123",
    )
    # This should work fine
    result = job.to_dict()
    assert isinstance(result, dict)


def test_job_posting_from_dict_invalid_input() -> None:
    """Test that JobPosting.from_dict validates input types."""
    # Note: @beartype was removed from this method because it uses Self type hint
    # which beartype doesn't support on individual methods.
    # The method still fails with AttributeError when invalid types are passed.
    with pytest.raises(AttributeError):
        # Passing a list instead of dict should fail
        JobPosting.from_dict([])  # type: ignore[arg-type]


def test_search_criteria_to_params_return_type() -> None:
    """Test that SearchCriteria.to_params returns correct type."""
    criteria = SearchCriteria(keywords="Python", location="Remote")
    params = criteria.to_params()
    assert isinstance(params, dict)
    assert all(isinstance(k, str) and isinstance(v, str) for k, v in params.items())


def test_html_parser_parse_jobs_invalid_input() -> None:
    """Test that HTMLParser.parse_jobs validates input type."""
    parser = HTMLParser()

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing int instead of str should fail
        parser.parse_jobs(123)  # type: ignore[arg-type]


def test_html_parser_parse_jobs_return_type() -> None:
    """Test that HTMLParser.parse_jobs returns correct type."""
    parser = HTMLParser()
    html = "<html><body></body></html>"
    result = parser.parse_jobs(html)
    assert isinstance(result, list)


def test_json_store_save_invalid_jobs_type() -> None:
    """Test that JsonStore.save validates jobs parameter."""
    store = JsonStore()

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing dict instead of list should fail
        store.save({}, "test")  # type: ignore[arg-type]


def test_json_store_save_invalid_filename_type() -> None:
    """Test that JsonStore.save validates filename parameter."""
    store = JsonStore()
    job = JobPosting(
        id="123",
        title="Test",
        company="Test",
        location="Test",
        url="https://test.com",
    )

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing int instead of str should fail
        store.save([job], 123)  # type: ignore[arg-type]


def test_json_store_load_invalid_filename_type() -> None:
    """Test that JsonStore.load validates filename parameter."""
    store = JsonStore()

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing int instead of str should fail
        store.load(123)  # type: ignore[arg-type]


def test_sqlite_store_get_jobs_invalid_limit_type() -> None:
    """Test that SqliteStore.get_jobs validates limit parameter."""
    store = SqliteStore(db_path=Path(":memory:"))

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing str instead of int should fail
        store.get_jobs(limit="10")  # type: ignore[arg-type]


def test_sqlite_store_save_invalid_jobs_type() -> None:
    """Test that SqliteStore.save validates jobs parameter."""
    store = SqliteStore(db_path=Path(":memory:"))

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing dict instead of list should fail
        store.save({})  # type: ignore[arg-type]


def test_rate_limiter_init_invalid_types() -> None:
    """Test that RateLimiter.__init__ validates parameter types."""
    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing str instead of float for min_delay
        RateLimiter(min_delay="1.5")  # type: ignore[arg-type]

    with pytest.raises(BeartypeCallHintParamViolation):
        # Passing str instead of int for reset_after
        RateLimiter(reset_after="5")  # type: ignore[arg-type]


def test_saved_alert_to_yaml_return_type() -> None:
    """Test that SavedAlert.to_yaml returns string."""
    criteria = SearchCriteria(keywords="Python", location="Remote")
    alert = SavedAlert(name="test-alert", criteria=criteria)
    result = alert.to_yaml()
    assert isinstance(result, str)


def test_saved_alert_from_yaml_invalid_input() -> None:
    """Test that SavedAlert.from_yaml validates input type."""
    # Note: @beartype was removed from this method because it uses Self type hint
    # which beartype doesn't support on individual methods.
    # The method still fails with AttributeError when invalid types are passed.
    with pytest.raises(AttributeError):
        # Passing int instead of str should fail
        SavedAlert.from_yaml(123)  # type: ignore[arg-type]


def test_time_filter_enum_validation() -> None:
    """Test that enum parameters are validated correctly."""
    # Valid enum value should work
    criteria = SearchCriteria(
        keywords="Python",
        time_filter=TimeFilter.PAST_WEEK,
    )
    assert criteria.time_filter == TimeFilter.PAST_WEEK

    # Invalid enum value should fail at Pydantic level, not beartype
    with pytest.raises((ValueError, TypeError)):
        SearchCriteria(
            keywords="Python",
            time_filter="invalid",  # type: ignore[arg-type]
        )


def test_multiple_parameter_validation() -> None:
    """Test that functions with multiple parameters validate all of them."""
    parser = HTMLParser()

    # Both parameters valid - should work
    result = parser._check_remote(None, "Remote location")
    assert isinstance(result, bool)

    # Second parameter invalid - should fail
    with pytest.raises(BeartypeCallHintParamViolation):
        parser._check_remote(None, 123)  # type: ignore[arg-type]
