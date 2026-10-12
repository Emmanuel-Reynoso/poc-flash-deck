"""Labels in Azure Table Storage.

PartitionKey = owner id, RowKey = label id: a user can only ever read or write
inside their own partition.
"""

from __future__ import annotations

from typing import Any

from azure.core.exceptions import ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from ..storage.table import as_utc
from .models import Label


def _to_entity(label: Label) -> dict[str, Any]:
    return {
        "PartitionKey": label.owner_id,
        "RowKey": label.label_id,
        "name": label.name,
        "createdAt": label.created_at,
    }


def _from_entity(e: dict[str, Any]) -> Label:
    return Label(owner_id=e["PartitionKey"], label_id=e["RowKey"], name=e["name"], created_at=as_utc(e["createdAt"]))


class TableLabelRepository:
    def __init__(self, table: TableClient) -> None:
        self._table = table

    def get(self, owner_id: str, label_id: str) -> Label | None:
        try:
            return _from_entity(self._table.get_entity(owner_id, label_id))
        except ResourceNotFoundError:
            return None

    def save(self, label: Label) -> None:
        self._table.upsert_entity(_to_entity(label), mode=UpdateMode.REPLACE)

    def delete(self, owner_id: str, label_id: str) -> None:
        try:
            self._table.delete_entity(partition_key=owner_id, row_key=label_id)
        except ResourceNotFoundError:
            pass

    def list(self, owner_id: str) -> list[Label]:
        entities = self._table.query_entities("PartitionKey eq @owner", parameters={"owner": owner_id})
        return [_from_entity(e) for e in entities]
