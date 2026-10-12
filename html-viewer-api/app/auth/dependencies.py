"""FastAPI dependencies for the signed-in user."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request

from .models import User
from .principal import require_user


def current_user(request: Request) -> User:
    return require_user(request.headers)


CurrentUser = Annotated[User, Depends(current_user)]
