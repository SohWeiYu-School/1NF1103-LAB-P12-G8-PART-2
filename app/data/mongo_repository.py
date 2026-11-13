"""MongoRepository: the DatabaseRepository for MongoDB Atlas."""

import logging

import certifi
from gridfs import GridFS
from pymongo import MongoClient
from pymongo.errors import PyMongoError

from app.data.database_repository import DatabaseRepository

logger = logging.getLogger(__name__)


class MongoRepository(DatabaseRepository):
    """One MongoDB collection. Files go to GridFS in the same database."""

    DB_NAME: str = "sow_risk_db"
    TIMEOUT_MS: int = 2000

    def __init__(self, collection_name: str, key_field: str, uri: str) -> None:
        super().__init__(collection_name, key_field, uri)
        self.__client: MongoClient | None = None

    def _connect(self) -> bool:
        if self.__client is not None:
            return True
        if not self._uri:
            logger.warning("MongoRepository: no database address is set (MONGODB_URI)")
            return False
        try:
            client = MongoClient(self._uri, serverSelectionTimeoutMS=MongoRepository.TIMEOUT_MS,
                                 tlsCAFile=certifi.where())
            client.admin.command("ping")
        except Exception as error:   # a wrong address raises other errors than PyMongoError
            logger.warning("MongoRepository: MongoDB is not reachable: %s", repr(error))
            return False
        self.__client = client
        return True

    def _upsert(self, key: str, record: dict) -> bool:
        # An older assessment has no id: match it on the client and the time it was run.
        query = ({self._key_field: key} if key
                 else {"client_ref": record.get("client_ref"), "assessed_at": record.get("assessed_at")})
        try:
            self.__collection().update_one(query, {"$set": record}, upsert=True)
            return True
        except PyMongoError as error:
            logger.error("MongoRepository: could not write %s to %s: %s", key, self._collection_name, repr(error))
            return False

    def _fetch(self, query: dict) -> list[dict]:
        try:
            return list(self.__collection().find(query, {"_id": 0}))
        except PyMongoError as error:
            logger.error("MongoRepository: could not read %s: %s", self._collection_name, repr(error))
            return []

    def _store_file(self, path: str, name: str) -> str:
        try:
            with open(path, "rb") as handle:
                return str(GridFS(self.__client[MongoRepository.DB_NAME]).put(handle, filename=name))
        except (PyMongoError, OSError) as error:
            logger.error("MongoRepository: could not store file %s: %s", name, repr(error))
            return ""

    def __collection(self):
        return self.__client[MongoRepository.DB_NAME][self._collection_name]
