"""Interface for the handle <-> user id mapping."""

from __future__ import annotations

from typing import Protocol


class HandleRepository(Protocol):
    def handle_of(self, owner_id: str) -> str | None: ...
    def owner_of(self, handle: str) -> str | None: ...
    def claim(self, handle: str, owner_id: str) -> bool:
        """Atomically takes the handle. False if another user already has it."""
        ...

    def set_handle(self, owner_id: str, handle: str) -> None: ...
