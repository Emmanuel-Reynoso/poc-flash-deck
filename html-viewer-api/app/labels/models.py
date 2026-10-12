"""Domain model for labels: the headers a user groups their files under."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Label:
    owner_id: str
    label_id: str
    name: str
    created_at: datetime
