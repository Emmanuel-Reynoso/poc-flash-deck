"""Public share links in Azure Table Storage.

PartitionKey = token, so resolving a public link (the anonymous hot path) is a
point read. Listing the shares of one file filters by ownerId/fileId; that is a
table scan, acceptable because it only runs when an owner opens the share dialog.
"""

from __future__ import annotations

from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from ..storage.table import as_utc
from .models import ShareRecord

_ROW = "share"


def _to_entity(r: ShareRecord) -> dict[str, Any]:
    return {
        "PartitionKey": r.token,
        "RowKey": _ROW,
        "ownerId": r.owner_id,
        "fileId": r.file_id,
        "createdAt": r.created_at,
        "expiresAt": r.expires_at,
    }


def _from_entity(e: dict[str, Any]) -> ShareRecord:
    return ShareRecord(
        token=e["PartitionKey"],
        owner_id=e["ownerId"],
        file_id=e["fileId"],
        created_at=as_utc(e["createdAt"]),
        expires_at=as_utc(e["expiresAt"]),
    )


class TableShareRepository:
    def __init__(self, table: TableClient) -> None:
        self._table = table

    def get(self, token: str) -> ShareRecord | None:
        try:
            return _from_entity(self._table.get_entity(token, _ROW))
        except ResourceNotFoundError:
            return None

    def save(self, record: ShareRecord) -> None:
        self._table.upsert_entity(_to_entity(record), mode=UpdateMode.REPLACE)

    def delete(self, token: str) -> None:
        try:
            self._table.delete_entity(partition_key=token, row_key=_ROW)
        except ResourceNotFoundError:
            pass

    def list_for_file(self, owner_id: str, file_id: str) -> list[ShareRecord]:
        entities = self._table.query_entities(
            "ownerId eq @owner and fileId eq @file",
            parameters={"owner": owner_id, "file": file_id},
        )
        return [_from_entity(e) for e in entities]
