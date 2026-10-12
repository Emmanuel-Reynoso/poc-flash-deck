"""Handles in Azure Table Storage.

Two rows per user, both point reads:
  ("handle", {handle}) -> ownerId   resolves a link; its creation is the uniqueness check
  ("owner", {ownerId}) -> handle    the handle of a signed-in user
"""

from __future__ import annotations

from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

_BY_HANDLE = "handle"
_BY_OWNER = "owner"


class TableHandleRepository:
    def __init__(self, table: TableClient) -> None:
        self._table = table

    def handle_of(self, owner_id: str) -> str | None:
        try:
            return self._table.get_entity(_BY_OWNER, owner_id)["handle"]
        except ResourceNotFoundError:
            return None

    def owner_of(self, handle: str) -> str | None:
        try:
            return self._table.get_entity(_BY_HANDLE, handle)["ownerId"]
        except ResourceNotFoundError:
            return None

    def claim(self, handle: str, owner_id: str) -> bool:
        try:
            self._table.create_entity({"PartitionKey": _BY_HANDLE, "RowKey": handle, "ownerId": owner_id})
            return True
        except ResourceExistsError:
            # Ours already if a previous attempt stopped half way.
            return self.owner_of(handle) == owner_id

    def set_handle(self, owner_id: str, handle: str) -> None:
        self._table.upsert_entity(
            {"PartitionKey": _BY_OWNER, "RowKey": owner_id, "handle": handle}, mode=UpdateMode.REPLACE
        )
