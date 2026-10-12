"""Use cases for uploading, listing, viewing and deleting HTML files."""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import replace
from datetime import timedelta
from typing import Any

from ..auth.models import User
from ..core.clock import Clock, utcnow
from ..core.config import Settings
from ..core.errors import BadRequest, Conflict, NotFound, PayloadTooLarge
from ..core.slug import is_slug, slugify
from ..labels.ports import LabelRepository
from ..shares.ports import ShareRepository
from ..users.service import HandleService
from .models import FileRecord, FileStatus, UploadTicket, ViewLink, Visibility
from .ports import BlobStore, FileRepository, SlugIndex

log = logging.getLogger(__name__)

ALLOWED_EXTENSIONS = (".html", ".htm")
MAX_NAME_LENGTH = 200
MAX_TITLE_LENGTH = 200
FALLBACK_SLUG = "archivo"
LABEL_ID_RE = re.compile(r"^[0-9a-f]{32}$")
_MAX_SLUG_ATTEMPTS = 1000
# Times a change is retried when someone else wrote the same file in between.
_MAX_WRITE_ATTEMPTS = 5

# Tells "not sent" apart from an explicit null (which clears the label).
UNSET: Any = object()

def clean_file_name(raw: object) -> str:
    if not isinstance(raw, str):
        raise BadRequest("fileName is required.")
    name = raw.replace("\\", "/").rsplit("/", 1)[-1]
    name = "".join(ch for ch in name if ch.isprintable()).strip()
    if not name:
        raise BadRequest("fileName is required.")
    if not name.lower().endswith(ALLOWED_EXTENSIONS):
        raise BadRequest("Only .html and .htm files are allowed.", code="unsupported_type")
    if len(name) > MAX_NAME_LENGTH:
        stem, ext = name.rsplit(".", 1)
        name = f"{stem[: MAX_NAME_LENGTH - len(ext) - 1]}.{ext}"
    return name


def clean_title(raw: object, fallback: str) -> str:
    if raw is None:
        return fallback
    if not isinstance(raw, str):
        raise BadRequest("title must be a string.")
    title = " ".join(raw.split())
    return title[:MAX_TITLE_LENGTH] or fallback


def _visibility(raw: object) -> Visibility:
    try:
        return Visibility(raw)
    except ValueError:
        raise BadRequest("visibility must be 'private' or 'org'.") from None


def _requested_slug(raw: object) -> str:
    slug = slugify(raw) if isinstance(raw, str) else ""
    if not slug:
        raise BadRequest("slug must contain letters or numbers.", code="invalid_slug")
    return slug


def _changed_meanwhile() -> Conflict:
    return Conflict("The file was changed at the same time. Try again.", code="conflict")


def _default_title(file_name: str) -> str:
    return file_name.rsplit(".", 1)[0] or file_name


class FileService:
    def __init__(
        self,
        files: FileRepository,
        shares: ShareRepository,
        blobs: BlobStore,
        slugs: SlugIndex,
        handles: HandleService,
        labels: LabelRepository,
        settings: Settings,
        clock: Clock = utcnow,
    ) -> None:
        self._files = files
        self._shares = shares
        self._blobs = blobs
        self._slugs = slugs
        self._handles = handles
        self._labels = labels
        self._settings = settings
        self._now = clock

    # --- upload -----------------------------------------------------------

    def start_upload(self, user: User, *, file_name: object, size_bytes: object, title: object = None) -> UploadTicket:
        name = clean_file_name(file_name)
        if not isinstance(size_bytes, int) or isinstance(size_bytes, bool) or size_bytes <= 0:
            raise BadRequest("sizeBytes must be a positive integer.")
        self._ensure_size(size_bytes)

        now = self._now()
        file_id = uuid.uuid4().hex
        clean = clean_title(title, _default_title(name))
        record = FileRecord(
            owner_id=user.id,
            file_id=file_id,
            file_name=name,
            title=clean,
            owner_name=user.name,
            status=FileStatus.PENDING,
            visibility=Visibility.PRIVATE,
            size_bytes=size_bytes,
            created_at=now,
            updated_at=now,
            slug=self._reserve_free_slug(user.id, slugify(clean) or FALLBACK_SLUG, file_id),
            owner_handle=self._handles.ensure(user),
        )
        self._files.save(record)

        expires_at = now + timedelta(minutes=self._settings.upload_sas_minutes)
        return UploadTicket(
            file=record,
            upload_url=self._blobs.upload_url(record.blob_name, expires_at),
            expires_at=expires_at,
            required_headers={
                "x-ms-blob-type": "BlockBlob",
                "x-ms-blob-content-type": "text/html; charset=utf-8",
            },
        )

    def complete_upload(self, user: User, file_id: str) -> FileRecord:
        for _ in range(_MAX_WRITE_ATTEMPTS):
            done = self._try_complete_upload(user, file_id)
            if done is not None:
                return done
        raise _changed_meanwhile()

    def _try_complete_upload(self, user: User, file_id: str) -> FileRecord | None:
        record = self._get_owned(user, file_id)
        if record.status is FileStatus.READY:
            return record

        size = self._blobs.get_size(record.blob_name)
        if size is None:
            raise Conflict("The file has not been uploaded yet.", code="upload_missing")
        if size > self._settings.max_upload_bytes:
            # A SAS cannot cap the upload size, so it is enforced here.
            self._discard(record)
            self._ensure_size(size)

        self._blobs.finalize(record.blob_name)
        ready = replace(record, status=FileStatus.READY, size_bytes=size, updated_at=self._now())
        return ready if self._files.update(ready) else None

    # --- queries ----------------------------------------------------------

    def list_files(self, user: User) -> list[FileRecord]:
        records = [self._with_readable_link(user, r) for r in self._files.list_ready(user.id)]
        return sorted(records, key=lambda r: r.created_at, reverse=True)

    def view(self, user: User, owner_id: str, file_id: str) -> ViewLink:
        record = self._files.get(owner_id, file_id)
        can_see = record is not None and record.status is FileStatus.READY and (
            record.owner_id == user.id or record.visibility is Visibility.ORG
        )
        if not can_see:
            # Same answer for "missing" and "not yours", so ids can't be probed.
            raise NotFound("File not found.")
        return self.view_link(record)

    def view_by_slug(self, user: User, handle: str, slug: str) -> ViewLink:
        """Readable link: /u/{handle}/{slug}. Same access rules as `view`."""
        owner_id = self._handles.owner_of(handle)
        file_id = self._slugs.lookup(owner_id, slug) if owner_id and is_slug(slug) else None
        if file_id is None:
            raise NotFound("File not found.")
        link = self.view(user, owner_id, file_id)
        if link.file.slug != slug:  # stale index entry
            raise NotFound("File not found.")
        return link

    def view_link(self, record: FileRecord) -> ViewLink:
        expires_at = self._now() + timedelta(minutes=self._settings.view_sas_minutes)
        return ViewLink(
            file=record,
            view_url=self._blobs.read_url(record.blob_name, expires_at),
            download_url=self._blobs.read_url(record.blob_name, expires_at, download_name=record.file_name),
            expires_at=expires_at,
        )

    # --- changes ----------------------------------------------------------

    def update(
        self,
        user: User,
        file_id: str,
        *,
        title: object = None,
        visibility: object = None,
        slug: object = None,
        label_id: object = UNSET,
    ) -> FileRecord:
        new_label = self._owned_label_id(user, label_id) if label_id is not UNSET else None
        new_visibility = _visibility(visibility) if visibility is not None else None
        new_slug = _requested_slug(slug) if slug is not None else None

        claimed: str | None = None  # link name reserved here and not yet stored in the file
        try:
            for _ in range(_MAX_WRITE_ATTEMPTS):
                record = self._get_ready(user, file_id)
                changes: dict[str, object] = {}
                if label_id is not UNSET:
                    changes["label_id"] = new_label
                if title is not None:
                    changes["title"] = clean_title(title, record.title)
                if new_visibility is not None:
                    changes["visibility"] = new_visibility
                if new_slug is not None and new_slug != record.slug:
                    if not self._claim_slug(record.owner_id, new_slug, record.file_id):
                        raise Conflict("You already have a file with that link name.", code="slug_taken")
                    claimed = new_slug
                    changes["slug"] = new_slug
                if not changes:
                    return record

                updated = replace(record, **changes, updated_at=self._now())
                if not self._files.update(updated):
                    continue  # someone else wrote first: read again and reapply
                if "slug" in changes:
                    claimed = None
                    if record.slug:
                        # The old link stops working; the name becomes free again.
                        self._slugs.release(record.owner_id, record.slug)
                return updated
            raise _changed_meanwhile()
        finally:
            if claimed is not None:
                self._release_unless_stored(user.id, file_id, claimed)

    def delete(self, user: User, file_id: str) -> None:
        record = self._get_owned(user, file_id)
        for share in self._shares.list_for_file(record.owner_id, record.file_id):
            self._shares.delete(share.token)
        self._discard(record)

    def purge_stale_pending(self) -> int:
        cutoff = self._now() - timedelta(hours=self._settings.pending_ttl_hours)
        purged = 0
        for record in self._files.list_pending_before(cutoff):
            self._discard(record)
            purged += 1
        log.info("Purged %d stale pending uploads", purged)
        return purged

    # --- helpers ----------------------------------------------------------

    def get_ready_owned(self, user: User, file_id: str) -> FileRecord:
        return self._get_ready(user, file_id)

    def _get_owned(self, user: User, file_id: str) -> FileRecord:
        record = self._files.get(user.id, file_id)
        if record is None:
            raise NotFound("File not found.")
        return record

    def _get_ready(self, user: User, file_id: str) -> FileRecord:
        record = self._get_owned(user, file_id)
        if record.status is not FileStatus.READY:
            raise NotFound("File not found.")
        return self._with_readable_link(user, record)

    def _with_readable_link(self, owner: User, record: FileRecord) -> FileRecord:
        """Files stored before readable links existed get theirs the first time their owner touches them."""
        if record.slug and record.owner_handle:
            return record
        base = slugify(record.title) or FALLBACK_SLUG
        for _ in range(_MAX_WRITE_ATTEMPTS):
            linked = replace(
                record,
                slug=record.slug or self._reserve_free_slug(record.owner_id, base, record.file_id),
                owner_handle=record.owner_handle or self._handles.ensure(owner),
            )
            if self._files.update(linked):
                return linked
            # Someone else wrote first, most likely the same fix from another request.
            record = self._files.get(record.owner_id, record.file_id)
            if record is None:
                raise NotFound("File not found.")
            if record.slug and record.owner_handle:
                return record
        raise _changed_meanwhile()

    def _discard(self, record: FileRecord) -> None:
        self._blobs.delete(record.blob_name)
        self._files.delete(record.owner_id, record.file_id)
        if record.slug:
            self._slugs.release(record.owner_id, record.slug)

    def _claim_slug(self, owner_id: str, slug: str, file_id: str) -> bool:
        """Reserves the name for the file. Also true if this same file already holds it."""
        return self._slugs.reserve(owner_id, slug, file_id) or self._slugs.lookup(owner_id, slug) == file_id

    def _release_unless_stored(self, owner_id: str, file_id: str, slug: str) -> None:
        """Gives back a name that was reserved for a change that did not happen."""
        current = self._files.get(owner_id, file_id)
        if current is None or current.slug != slug:
            self._slugs.release(owner_id, slug)

    def _reserve_free_slug(self, owner_id: str, base: str, file_id: str) -> str:
        for n in range(1, _MAX_SLUG_ATTEMPTS):
            candidate = base if n == 1 else f"{base}-{n}"
            if self._claim_slug(owner_id, candidate, file_id):
                return candidate
        raise Conflict("Could not find a free link name.", code="slug_taken")

    def _owned_label_id(self, user: User, label_id: object) -> str | None:
        if label_id is None:
            return None
        known = isinstance(label_id, str) and LABEL_ID_RE.match(label_id) and self._labels.get(user.id, label_id)
        if not known:
            # Labels of other users look exactly like labels that do not exist.
            raise BadRequest("That label does not exist.", code="label_not_found")
        return label_id

    def _ensure_size(self, size: int) -> None:
        if size > self._settings.max_upload_bytes:
            limit_mb = self._settings.max_upload_bytes // (1024 * 1024)
            raise PayloadTooLarge(f"The file exceeds the {limit_mb} MB limit.")
