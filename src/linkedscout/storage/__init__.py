"""Storage backends for job data."""

from linkedscout.storage.json_store import JsonStore
from linkedscout.storage.sqlite_store import SqliteStore

__all__ = ["JsonStore", "SqliteStore"]
