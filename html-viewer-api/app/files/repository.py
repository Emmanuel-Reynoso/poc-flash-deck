"""File metadata in Azure Table Storage.

PartitionKey = owner id, RowKey = file id. Listing a user's files is a single
partition query, and opening a file by (owner, file) is a point read.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

from azure.core import MatchConditions
from azure.core.exceptions import ResourceExistsError, ResourceModifiedError, ResourceNotFoundError
from azure.data.tables import TableClient, UpdateMode

from ..storage.table import as_utc
from .models import FileRecord, FileStatus, Visibility


def _to_entity(r: FileRecord) -> dict[str, Any]:
    return {
        "PartitionKey": r.owner_id,
        "RowKey": r.file_id,
        "fileName": r.file_name,
        "title": r.title,
        "ownerName": r.owner_name,
        "status": r.status.value,
        "visibility": r.visibility.value,
        "sizeBytes": r.size_bytes,
        "createdAt": r.created_at,
        "updatedAt": r.updated_at,
        "slug": r.slug,
        "ownerHandle": r.owner_handle,
        "labelId": r.label_id or "",
    }


def _from_entity(e: dict[str, Any]) -> FileRecord:
    return FileRecord(
        owner_id=e["PartitionKey"],
        file_id=e["RowKey"],
        file_name=e["fileName"],
        title=e["title"],
        owner_name=e.get("ownerName", ""),
        status=FileStatus(e["status"]),
        visibility=Visibility(e.get("visibility", Visibility.PRIVATE.value)),
        size_bytes=int(e.get("sizeBytes", 0)),
        created_at=as_utc(e["createdAt"]),
        updated_at=as_utc(e["updatedAt"]),
        slug=e.get("slug", ""),
        owner_handle=e.get("ownerHandle", ""),
        label_id=e.get("labelId") or None,
        version=getattr(e, "metadata", {}).get("etag"),
    )


class TableFileRepository:
    def __init__(self, table: TableClient) -> None:
        self._table = table

    def get(self, owner_id: str, file_id: str) -> FileRecord | None:
        try:
            return _from_entity(self._table.get_entity(owner_id, file_id))
        except ResourceNotFoundError:
            return None

    def save(self, record: FileRecord) -> None:
        self._table.upsert_entity(_to_entity(record), mode=UpdateMode.REPLACE)

    def update(self, record: FileRecord) -> bool:
        if record.version is None:
            raise ValueError("update() needs a record that was read from storage.")
        try:
            self._table.update_entity(
                _to_entity(record),
                mode=UpdateMode.REPLACE,
                etag=record.version,
                match_condition=MatchConditions.IfNotModified,
            )
            return True
        except (ResourceModifiedError, ResourceNotFoundError):
            return False

    def delete(self, owner_id: str, file_id: str) -> None:
        try:
            self._table.delete_entity(partition_key=owner_id, row_key=file_id)
        except ResourceNotFoundError:
            pass

    def list_ready(self, owner_id: str) -> list[FileRecord]:
        entities = self._table.query_entities(
            "PartitionKey eq @owner and status eq @status",
            parameters={"owner": owner_id, "status": FileStatus.READY.value},
        )
        return [_from_entity(e) for e in entities]

    def list_pending_before(self, cutoff: datetime) -> Iterable[FileRecord]:
        entities = self._table.query_entities(
            "status eq @status and createdAt lt @cutoff",
            parameters={"status": FileStatus.PENDING.value, "cutoff": cutoff},
        )
        return (_from_entity(e) for e in entities)


class TableSlugIndex:
    """PartitionKey = owner id, RowKey = slug. Creating the row is the uniqueness check."""

    def __init__(self, table: TableClient) -> None:
        self._table = table

    def reserve(self, owner_id: str, slug: str, file_id: str) -> bool:
        try:
            self._table.create_entity({"PartitionKey": owner_id, "RowKey": slug, "fileId": file_id})
            return True
        except ResourceExistsError:
            return False

    def release(self, owner_id: str, slug: str) -> None:
        try:
            self._table.delete_entity(partition_key=owner_id, row_key=slug)
        except ResourceNotFoundError:
            pass

    def lookup(self, owner_id: str, slug: str) -> str | None:
        try:
            return self._table.get_entity(owner_id, slug)["fileId"]
        except ResourceNotFoundError:
            return None
