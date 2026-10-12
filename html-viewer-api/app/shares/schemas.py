"""Request and response shapes for share links."""

from __future__ import annotations

from datetime import datetime

from pydantic import StrictInt

from ..core.schemas import ApiModel
from .models import ShareRecord


class CreateShareRequest(ApiModel):
    expires_in_days: StrictInt = 7


class ShareResponse(ApiModel):
    token: str
    file_id: str
    created_at: datetime
    expires_at: datetime

    @classmethod
    def of(cls, s: ShareRecord) -> "ShareResponse":
        return cls(token=s.token, file_id=s.file_id, created_at=s.created_at, expires_at=s.expires_at)


class ShareListResponse(ApiModel):
    items: list[ShareResponse]
