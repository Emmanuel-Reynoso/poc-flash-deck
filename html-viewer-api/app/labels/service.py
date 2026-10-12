"""Use cases for labels. Every operation is scoped to the signed-in user."""

from __future__ import annotations

import re
import uuid
from dataclasses import replace

from ..auth.models import User
from ..core.clock import Clock, utcnow
from ..core.errors import BadRequest, Conflict, NotFound
from ..files.ports import FileRepository
from .models import Label
from .ports import LabelRepository

MAX_NAME_LENGTH = 50
MAX_LABELS = 100
LABEL_ID_RE = re.compile(r"^[0-9a-f]{32}$")


def clean_label_name(raw: object) -> str:
    if not isinstance(raw, str):
        raise BadRequest("name is required.")
    name = " ".join("".join(ch for ch in raw if ch.isprintable()).split())
    if not name:
        raise BadRequest("name is required.")
    if len(name) > MAX_NAME_LENGTH:
        raise BadRequest(f"name must be at most {MAX_NAME_LENGTH} characters.")
    return name


class LabelService:
    def __init__(self, labels: LabelRepository, files: FileRepository, clock: Clock = utcnow) -> None:
        self._labels = labels
        self._files = files
        self._now = clock

    def list(self, user: User) -> list[Label]:
        return sorted(self._labels.list(user.id), key=lambda label: label.created_at)

    def create(self, user: User, *, name: object) -> Label:
        clean = clean_label_name(name)
        existing = self._labels.list(user.id)
        if len(existing) >= MAX_LABELS:
            raise Conflict(f"You can have up to {MAX_LABELS} labels.", code="label_limit")
        self._ensure_unique(existing, clean)
        label = Label(owner_id=user.id, label_id=uuid.uuid4().hex, name=clean, created_at=self._now())
        self._labels.save(label)
        return label

    def rename(self, user: User, label_id: str, *, name: object) -> Label:
        label = self._get_owned(user, label_id)
        clean = clean_label_name(name)
        self._ensure_unique([other for other in self._labels.list(user.id) if other.label_id != label_id], clean)
        renamed = replace(label, name=clean)
        self._labels.save(renamed)
        return renamed

    def delete(self, user: User, label_id: str) -> None:
        """Removes the label. Its files are kept and become unlabeled."""
        label = self._get_owned(user, label_id)
        for record in self._files.list_ready(user.id):
            # Retried if the file changes meanwhile, so that change is not overwritten.
            while record is not None and record.label_id == label.label_id:
                if self._files.update(replace(record, label_id=None)):
                    break
                record = self._files.get(user.id, record.file_id)
        self._labels.delete(user.id, label.label_id)

    def _get_owned(self, user: User, label_id: str) -> Label:
        label = self._labels.get(user.id, label_id) if LABEL_ID_RE.match(label_id) else None
        if label is None:
            raise NotFound("Label not found.")
        return label

    @staticmethod
    def _ensure_unique(others: list[Label], name: str) -> None:
        if any(other.name.casefold() == name.casefold() for other in others):
            raise Conflict("You already have a label with that name.", code="label_exists")
