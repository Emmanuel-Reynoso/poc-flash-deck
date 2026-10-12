"""Domain models for HTML files. Plain dataclasses, no Azure SDK types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum


class FileStatus(StrEnum):
    PENDING = "pending"  # upload ticket issued, blob not confirmed yet
    READY = "ready"


class Visibility(StrEnum):
    PRIVATE = "private"  # only the owner
    ORG = "org"  # any signed-in user of the tenant with the link


@dataclass(frozen=True)
class FileRecord:
    owner_id: str
    file_id: str
    file_name: str
    title: str
    owner_name: str
    status: FileStatus
    visibility: Visibility
    size_bytes: int
    created_at: datetime
    updated_at: datetime
    slug: str = ""  # unique per owner; '' on files older than readable links
    owner_handle: str = ""
    label_id: str | None = None
    # Storage version this copy was read at; lets a write detect that someone else wrote first.
    version: str | None = field(default=None, compare=False)

    @property
    def blob_name(self) -> str:
        return f"{self.owner_id}/{self.file_id}.html"


@dataclass(frozen=True)
class UploadTicket:
    file: FileRecord
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]


@dataclass(frozen=True)
class ViewLink:
    file: FileRecord
    view_url: str
    download_url: str
    expires_at: datetime
