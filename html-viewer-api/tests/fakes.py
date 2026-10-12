"""In-memory implementations of the ports, for fast unit tests."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

from app.core.config import Settings
from app.files.models import FileRecord, FileStatus
from app.labels.models import Label
from app.shares.models import ShareRecord


def make_settings(**overrides) -> Settings:
    values = dict(
        connection_string="UseDevelopmentStorage=true",
        account_name=None,
        blob_endpoint=None,
        table_endpoint=None,
        container_name="html",
        files_table="files",
        shares_table="shares",
        users_table="users",
        slugs_table="slugs",
        labels_table="labels",
        max_upload_bytes=1024,
        upload_sas_minutes=10,
        view_sas_minutes=10,
        share_max_days=30,
        pending_ttl_hours=24,
        public_blob_base_url=None,
        auto_create_resources=False,
    )
    values.update(overrides)
    return Settings(**values)


class FakeClock:
    def __init__(self, start: datetime | None = None) -> None:
        self.now = start or datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)


class FakeFileRepository:
    """Keeps a version per file, like the ETag of the real table."""

    def __init__(self) -> None:
        self.items: dict[tuple[str, str], FileRecord] = {}
        self._writes = 0

    def get(self, owner_id, file_id):
        return self.items.get((owner_id, file_id))

    def save(self, record):
        self._writes += 1
        self.items[(record.owner_id, record.file_id)] = replace(record, version=f"v{self._writes}")

    def update(self, record):
        stored = self.items.get((record.owner_id, record.file_id))
        if stored is None or stored.version != record.version:
            return False
        self.save(record)
        return True

    def delete(self, owner_id, file_id):
        self.items.pop((owner_id, file_id), None)

    def list_ready(self, owner_id):
        return [r for r in self.items.values() if r.owner_id == owner_id and r.status is FileStatus.READY]

    def list_pending_before(self, cutoff):
        return [r for r in list(self.items.values()) if r.status is FileStatus.PENDING and r.created_at < cutoff]


class FakeShareRepository:
    def __init__(self) -> None:
        self.items: dict[str, ShareRecord] = {}

    def get(self, token):
        return self.items.get(token)

    def save(self, record):
        self.items[record.token] = record

    def delete(self, token):
        self.items.pop(token, None)

    def list_for_file(self, owner_id, file_id):
        return [s for s in self.items.values() if s.owner_id == owner_id and s.file_id == file_id]


class FakeSlugIndex:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], str] = {}

    def reserve(self, owner_id, slug, file_id):
        if (owner_id, slug) in self.items:
            return False
        self.items[(owner_id, slug)] = file_id
        return True

    def release(self, owner_id, slug):
        self.items.pop((owner_id, slug), None)

    def lookup(self, owner_id, slug):
        return self.items.get((owner_id, slug))


class FakeHandleRepository:
    def __init__(self) -> None:
        self.by_handle: dict[str, str] = {}
        self.by_owner: dict[str, str] = {}

    def handle_of(self, owner_id):
        return self.by_owner.get(owner_id)

    def owner_of(self, handle):
        return self.by_handle.get(handle)

    def claim(self, handle, owner_id):
        return self.by_handle.setdefault(handle, owner_id) == owner_id

    def set_handle(self, owner_id, handle):
        self.by_owner[owner_id] = handle


class FakeLabelRepository:
    def __init__(self) -> None:
        self.items: dict[tuple[str, str], Label] = {}

    def get(self, owner_id, label_id):
        return self.items.get((owner_id, label_id))

    def save(self, label):
        self.items[(label.owner_id, label.label_id)] = label

    def delete(self, owner_id, label_id):
        self.items.pop((owner_id, label_id), None)

    def list(self, owner_id):
        return [label for label in self.items.values() if label.owner_id == owner_id]


class FakeBlobStore:
    def __init__(self) -> None:
        self.blobs: dict[str, int] = {}
        self.finalized: set[str] = set()

    def upload_url(self, blob_name, expires_at):
        return f"https://blob.test/html/{blob_name}?sig=up&se={expires_at.isoformat()}"

    def read_url(self, blob_name, expires_at, *, download_name=None):
        kind = f"attachment:{download_name}" if download_name else "inline"
        return f"https://blob.test/html/{blob_name}?sig=read&rscd={kind}"

    def get_size(self, blob_name):
        return self.blobs.get(blob_name)

    def finalize(self, blob_name):
        self.finalized.add(blob_name)

    def delete(self, blob_name):
        self.blobs.pop(blob_name, None)
        self.finalized.discard(blob_name)
