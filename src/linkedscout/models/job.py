"""Job posting data model."""

from datetime import datetime
from typing import Self

from beartype import beartype
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

_TRUTHY_STRINGS = frozenset({"true", "yes", "1"})
_FALSY_STRINGS = frozenset({"false", "no", "0", ""})


@beartype
def _parse_bool(value: str | bool | int | None) -> bool:
    """Parse a value to boolean, handling string representations correctly.

    Args:
        value: The value to parse.

    Returns:
        The boolean result.

    Raises:
        ValueError: If value is a string that cannot be interpreted as boolean.
    """
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return bool(value)
    lower = value.lower()
    if lower in _TRUTHY_STRINGS:
        return True
    if lower in _FALSY_STRINGS:
        return False
    msg = f"Cannot convert '{value}' to bool"
    raise ValueError(msg)


class JobPosting(BaseModel):
    """Represents a LinkedIn job posting."""

    model_config = ConfigDict(frozen=True)

    id: str = Field(description="LinkedIn job ID")
    title: str = Field(description="Job title")
    company: str = Field(description="Company name")
    location: str = Field(description="Job location")
    url: HttpUrl = Field(description="URL to the job posting")
    posted_at: datetime | None = Field(
        default=None, description="When the job was posted"
    )
    description_snippet: str | None = Field(
        default=None, description="Short description snippet"
    )
    salary: str | None = Field(default=None, description="Salary information if shown")
    is_remote: bool = Field(default=False, description="Whether the job is remote")
    applicants_count: str | None = Field(
        default=None, description="Number of applicants (e.g., '25 applicants')"
    )
    scraped_at: datetime = Field(
        default_factory=datetime.now, description="When this job was scraped"
    )

    @beartype
    def to_dict(self) -> dict[str, str | bool | None]:
        """Convert to dictionary with serialized datetime fields."""
        return {
            "id": self.id,
            "title": self.title,
            "company": self.company,
            "location": self.location,
            "url": str(self.url),
            "posted_at": self.posted_at.isoformat() if self.posted_at else None,
            "description_snippet": self.description_snippet,
            "salary": self.salary,
            "is_remote": self.is_remote,
            "applicants_count": self.applicants_count,
            "scraped_at": self.scraped_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, str | bool | None]) -> Self:
        """Create a JobPosting from a dictionary."""
        posted_at = None
        if data.get("posted_at"):
            posted_at = datetime.fromisoformat(str(data["posted_at"]))

        scraped_at = datetime.now()
        if data.get("scraped_at"):
            scraped_at = datetime.fromisoformat(str(data["scraped_at"]))

        return cls(
            id=str(data["id"]),
            title=str(data["title"]),
            company=str(data["company"]),
            location=str(data["location"]),
            url=str(data["url"]),
            posted_at=posted_at,
            description_snippet=str(data["description_snippet"])
            if data.get("description_snippet")
            else None,
            salary=str(data["salary"]) if data.get("salary") else None,
            is_remote=_parse_bool(data.get("is_remote", False)),
            applicants_count=str(data["applicants_count"])
            if data.get("applicants_count")
            else None,
            scraped_at=scraped_at,
        )
