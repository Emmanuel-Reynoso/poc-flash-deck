"""Use cases for public, expiring share links."""

from __future__ import annotations

import secrets
import string
from datetime import timedelta

from ..auth.models import User
from ..core.clock import Clock, utcnow
from ..core.config import Settings
from ..core.errors import BadRequest, NotFound
from ..files.models import FileStatus, ViewLink
from ..files.ports import FileRepository
from ..files.service import FileService
from .models import ShareRecord
from .ports import ShareRepository

# Letters and digits only, so the token can be split off the end of a readable
# link (/s/{handle}/{slug}-{token}). 12 characters is about 71 bits of entropy.
TOKEN_ALPHABET = string.ascii_letters + string.digits
TOKEN_LENGTH = 12


def new_token() -> str:
    return "".join(secrets.choice(TOKEN_ALPHABET) for _ in range(TOKEN_LENGTH))


class ShareService:
    def __init__(
        self,
        shares: ShareRepository,
        files: FileRepository,
        file_service: FileService,
        settings: Settings,
        clock: Clock = utcnow,
    ) -> None:
        self._shares = shares
        self._files = files
        self._file_service = file_service
        self._settings = settings
        self._now = clock

    def create(self, user: User, file_id: str, *, expires_in_days: object) -> ShareRecord:
        record = self._file_service.get_ready_owned(user, file_id)
        max_days = self._settings.share_max_days
        if (
            not isinstance(expires_in_days, int)
            or isinstance(expires_in_days, bool)
            or not 1 <= expires_in_days <= max_days
        ):
            raise BadRequest(f"expiresInDays must be between 1 and {max_days}.")

        now = self._now()
        share = ShareRecord(
            token=new_token(),
            owner_id=record.owner_id,
            file_id=record.file_id,
            created_at=now,
            expires_at=now + timedelta(days=expires_in_days),
        )
        self._shares.save(share)
        return share

    def list_for_file(self, user: User, file_id: str) -> list[ShareRecord]:
        record = self._file_service.get_ready_owned(user, file_id)
        now = self._now()
        active = [s for s in self._shares.list_for_file(record.owner_id, record.file_id) if not s.is_expired(now)]
        return sorted(active, key=lambda s: s.created_at, reverse=True)

    def revoke(self, user: User, token: str) -> None:
        share = self._shares.get(token)
        if share is None or share.owner_id != user.id:
            raise NotFound("Share link not found.")
        self._shares.delete(token)

    def resolve(self, token: str) -> ViewLink:
        """Anonymous access through a share link."""
        share = self._shares.get(token) if token else None
        if share is None or share.is_expired(self._now()):
            raise NotFound("This link does not exist or has expired.")
        record = self._files.get(share.owner_id, share.file_id)
        if record is None or record.status is not FileStatus.READY:
            raise NotFound("This link does not exist or has expired.")
        return self._file_service.view_link(record)

    def resolve_readable(self, handle: str, slug_and_token: str) -> ViewLink:
        """Anonymous access through /s/{handle}/{slug}-{token}.

        The token is the credential. The readable part must match the file too,
        so a link stops working when its file gets another link name.
        """
        slug, _, token = slug_and_token.rpartition("-")
        link = self.resolve(token)
        if not slug or link.file.slug != slug or link.file.owner_handle != handle:
            raise NotFound("This link does not exist or has expired.")
        return link
