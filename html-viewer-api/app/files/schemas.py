"""Request and response shapes for files."""

from __future__ import annotations

from datetime import datetime

from pydantic import StrictInt, StrictStr

from ..core.schemas import ApiModel
from .models import FileRecord, FileStatus, UploadTicket, ViewLink, Visibility


class CreateUploadRequest(ApiModel):
    file_name: StrictStr
    size_bytes: StrictInt
    title: StrictStr | None = None


class UpdateFileRequest(ApiModel):
    title: StrictStr | None = None
    visibility: Visibility | None = None
    slug: StrictStr | None = None
    # null moves the file out of any label; leaving it out keeps the current one.
    label_id: StrictStr | None = None


class FileResponse(ApiModel):
    id: str
    owner_id: str
    owner_name: str
    file_name: str
    title: str
    size_bytes: int
    visibility: Visibility
    status: FileStatus
    created_at: datetime
    updated_at: datetime
    slug: str
    owner_handle: str
    label_id: str | None

    @classmethod
    def of(cls, r: FileRecord, *, for_owner: bool = True) -> "FileResponse":
        return cls(
            id=r.file_id,
            owner_id=r.owner_id,
            owner_name=r.owner_name,
            slug=r.slug,
            owner_handle=r.owner_handle,
            # How the owner organizes their files is not shown to other viewers.
            label_id=r.label_id if for_owner else None,
            file_name=r.file_name,
            title=r.title,
            size_bytes=r.size_bytes,
            visibility=r.visibility,
            status=r.status,
            created_at=r.created_at,
            updated_at=r.updated_at,
        )


class PublicFileResponse(ApiModel):
    """What anonymous viewers of a share link may see. No owner id."""

    title: str
    file_name: str
    owner_name: str
    size_bytes: int
    updated_at: datetime

    @classmethod
    def of(cls, r: FileRecord) -> "PublicFileResponse":
        return cls(
            title=r.title,
            file_name=r.file_name,
            owner_name=r.owner_name,
            size_bytes=r.size_bytes,
            updated_at=r.updated_at,
        )


class FileListResponse(ApiModel):
    items: list[FileResponse]


class UploadTicketResponse(ApiModel):
    file: FileResponse
    upload_url: str
    expires_at: datetime
    required_headers: dict[str, str]

    @classmethod
    def of(cls, t: UploadTicket) -> "UploadTicketResponse":
        return cls(
            file=FileResponse.of(t.file),
            upload_url=t.upload_url,
            expires_at=t.expires_at,
            required_headers=t.required_headers,
        )


class ViewResponse(ApiModel):
    file: FileResponse
    view_url: str
    download_url: str
    expires_at: datetime

    @classmethod
    def of(cls, v: ViewLink, *, viewer_id: str) -> "ViewResponse":
        return cls(
            file=FileResponse.of(v.file, for_owner=v.file.owner_id == viewer_id),
            view_url=v.view_url,
            download_url=v.download_url,
            expires_at=v.expires_at,
        )


class PublicViewResponse(ApiModel):
    file: PublicFileResponse
    view_url: str
    download_url: str
    expires_at: datetime

    @classmethod
    def of(cls, v: ViewLink) -> "PublicViewResponse":
        return cls(
            file=PublicFileResponse.of(v.file),
            view_url=v.view_url,
            download_url=v.download_url,
            expires_at=v.expires_at,
        )
