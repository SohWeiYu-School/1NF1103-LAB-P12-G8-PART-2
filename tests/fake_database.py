"""A DatabaseRepository that keeps its records in memory, for tests. No network."""

from app.data.database_repository import DatabaseRepository


class FakeDatabase(DatabaseRepository):

    def __init__(self, collection_name: str = "client_cases", key_field: str = "client_ref",
                 online: bool = True) -> None:
        super().__init__(collection_name, key_field, "fake://database")
        self.online = online
        self.records: dict[str, dict] = {}
        self.files: list[str] = []
        self.fail_on: set[str] = set()

    def _connect(self) -> bool:
        return self.online

    def _upsert(self, key: str, record: dict) -> bool:
        if key in self.fail_on:
            return False
        self.records[key] = dict(record)
        return True

    def _fetch(self, query: dict) -> list[dict]:
        return [record for record in self.records.values()
                if all(record.get(field) == value for field, value in query.items())]

    def _store_file(self, path: str, name: str) -> str:
        self.files.append(name)
        return f"file-{len(self.files)}"
