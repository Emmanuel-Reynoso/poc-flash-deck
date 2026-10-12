"""Reads the identity that Azure Static Web Apps forwards to the linked backend.

SWA authenticates the user (Entra ID) and adds the `x-ms-client-principal`
header. Linking the Function App to SWA restricts the Function App so that
only SWA can call it, which is what makes trusting this header safe.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Mapping

from ..core.errors import Unauthorized
from .models import User

PRINCIPAL_HEADER = "x-ms-client-principal"
_USER_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,128}$")


def parse_principal(headers: Mapping[str, str]) -> User | None:
    raw = headers.get(PRINCIPAL_HEADER)
    if not raw:
        return None
    try:
        data = json.loads(base64.b64decode(raw))
    except (ValueError, binascii.Error):
        return None
    if not isinstance(data, dict):
        return None

    user_id = str(data.get("userId") or "")
    roles = data.get("userRoles") or []
    if not _USER_ID_RE.match(user_id) or "authenticated" not in roles:
        return None

    name = str(data.get("userDetails") or user_id)[:256]
    return User(id=user_id, name=name)


def require_user(headers: Mapping[str, str]) -> User:
    user = parse_principal(headers)
    if user is None:
        raise Unauthorized("Authentication required.")
    return user


def encode_principal(user_id: str, name: str, roles: list[str] | None = None) -> str:
    """Builds a header value. Used by tests and local tooling."""
    payload = {
        "identityProvider": "aad",
        "userId": user_id,
        "userDetails": name,
        "userRoles": roles if roles is not None else ["anonymous", "authenticated"],
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()
