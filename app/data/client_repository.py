"""ClientRepository: the client records, one per client."""

import logging
import os

from app.data.json_repository import JsonRepository

logger = logging.getLogger(__name__)


class ClientRepository(JsonRepository):
    """Client records in sow_cases.json. Saving a client replaces the record with the same reference."""

    # Older command-line records used other names for these asset values (new name: old name).
    OLD_ASSET_KEYS: dict = {"current_declared_value": "current_value", "income_produced": "yearly_income"}

    def __init__(self, path: str = os.path.join(JsonRepository.DATA_DIR, "sow_cases.json"),
                 key_field: str = "client_ref") -> None:
        super().__init__(path, key_field)

    def save(self, record: dict) -> bool:
        """Add the client, or replace the saved record with the same reference. Returns False
        (and leaves the file untouched) if the saved clients cannot be read, so records that
        could not be read are never overwritten."""
        if not isinstance(record, dict) or self._key_field not in record:
            return False
        record = self.__standardise(record)
        try:
            records = super().load()
        except (OSError, ValueError) as error:
            logger.error("ClientRepository.save: not saved, the existing records cannot be read: %r", error)
            return False
        for position, existing in enumerate(records):
            if existing.get(self._key_field) == record[self._key_field]:
                records[position] = record
                break
        else:
            records.append(record)
        return self._write_all(records)

    def load(self) -> list[dict]:
        """Every client, in the current layout. Raises OSError or ValueError if the file cannot be read."""
        return [self.__standardise(record) for record in super().load()]

    def __standardise(self, record: dict) -> dict:
        """Bring a record saved in an older layout up to the one layout every screen uses:
        asset values as current_declared_value / income_produced, and the asset's description
        folded into asset_type ("Property - Condo"). Records already in that layout are unchanged."""
        if not isinstance(record, dict):
            return record
        for asset in record.get("investments") or []:
            if not isinstance(asset, dict):
                continue
            for new, old in ClientRepository.OLD_ASSET_KEYS.items():
                if asset.get(new) is None and old in asset:
                    asset[new] = asset[old]
                asset.pop(old, None)
            description = str(asset.pop("asset_description", None) or asset.pop("description", None) or "").strip()
            kind = str(asset.get("asset_type") or "").strip()
            if description and description.lower() not in kind.lower():
                asset["asset_type"] = f"{kind} - {description}" if kind else description
        return record
