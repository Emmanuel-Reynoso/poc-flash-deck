"""Interface the label use cases depend on."""

from __future__ import annotations

from typing import Protocol

from .models import Label


class LabelRepository(Protocol):
    def get(self, owner_id: str, label_id: str) -> Label | None: ...
    def save(self, label: Label) -> None: ...
    def delete(self, owner_id: str, label_id: str) -> None: ...
    def list(self, owner_id: str) -> list[Label]: ...
