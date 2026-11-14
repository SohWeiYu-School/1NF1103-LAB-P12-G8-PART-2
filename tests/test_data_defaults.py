"""Data Manager classes can be made with their defaults, and Repository has an __init__."""

from app.data.cloud_sync import CloudSync
from app.data.database_repository import DatabaseRepository
from app.data.json_repository import JsonRepository
from app.data.repository import Repository


def test_repository_interface_defines_its_own_init():
    assert "__init__" in Repository.__dict__


def test_both_kinds_of_store_are_repositories():
    assert issubclass(JsonRepository, Repository) and issubclass(DatabaseRepository, Repository)


def test_cloud_sync_with_no_stores_is_offline_and_sync_does_nothing():
    sync = CloudSync()
    assert sync.is_online() is False
    stats = sync.sync()
    assert stats["synced"] == 0 and stats["errors"]
