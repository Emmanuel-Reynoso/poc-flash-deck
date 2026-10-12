"""The signed-in user. Plain dataclass, no framework types."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class User:
    id: str
    name: str
