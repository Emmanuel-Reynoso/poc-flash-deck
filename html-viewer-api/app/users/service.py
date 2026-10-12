"""Handles: the readable user name that appears in links (/u/{handle}/...).

Derived once from the sign-in name (the part before the @) and then fixed, so
links never break. Two users that would get the same handle are told apart
with a numeric suffix.
"""

from __future__ import annotations

from ..auth.models import User
from ..core.slug import is_slug, slugify
from .ports import HandleRepository

FALLBACK = "usuario"
MAX_HANDLE_LENGTH = 40
_MAX_ATTEMPTS = 1000


def handle_base(user_name: str) -> str:
    return slugify(user_name.split("@", 1)[0], MAX_HANDLE_LENGTH) or FALLBACK


class HandleService:
    def __init__(self, handles: HandleRepository) -> None:
        self._handles = handles

    def ensure(self, user: User) -> str:
        """Returns the user's handle, assigning one on first use."""
        existing = self._handles.handle_of(user.id)
        if existing:
            return existing
        base = handle_base(user.name)
        for n in range(1, _MAX_ATTEMPTS):
            candidate = base if n == 1 else f"{base}-{n}"
            if self._handles.claim(candidate, user.id):
                self._handles.set_handle(user.id, candidate)
                return candidate
        raise RuntimeError("Could not assign a handle.")

    def owner_of(self, handle: str) -> str | None:
        return self._handles.owner_of(handle) if is_slug(handle) else None
