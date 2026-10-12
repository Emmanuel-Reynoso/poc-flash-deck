"""Request and response shapes for labels."""

from __future__ import annotations

from datetime import datetime

from pydantic import StrictStr

from ..core.schemas import ApiModel
from .models import Label


class LabelNameRequest(ApiModel):
    name: StrictStr


class LabelResponse(ApiModel):
    id: str
    name: str
    created_at: datetime

    @classmethod
    def of(cls, label: Label) -> "LabelResponse":
        return cls(id=label.label_id, name=label.name, created_at=label.created_at)


class LabelListResponse(ApiModel):
    items: list[LabelResponse]
