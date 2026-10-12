"""Interfaces the share use cases depend on."""

from __future__ import annotations

from typing import Protocol

from .models import ShareRecord


class ShareRepository(Protocol):
    def get(self, token: str) -> ShareRecord | None: ...
    def save(self, record: ShareRecord) -> None: ...
    def delete(self, token: str) -> None: ...
    def list_for_file(self, owner_id: str, file_id: str) -> list[ShareRecord]: ...
