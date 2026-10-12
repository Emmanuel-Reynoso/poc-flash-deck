"""SAS token signing.

Production uses a *user delegation* SAS: it is signed with a key obtained via
Entra ID (Managed Identity), so the storage account can keep shared-key access
disabled. Local development against Azurite signs with the account key.
"""

from __future__ import annotations

import threading
from datetime import datetime, timedelta, timezone
from typing import Protocol

from azure.storage.blob import (
    BlobSasPermissions,
    BlobServiceClient,
    UserDelegationKey,
    generate_blob_sas,
)

_CLOCK_SKEW = timedelta(minutes=5)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class SasSigner(Protocol):
    def sign(
        self,
        container: str,
        blob_name: str,
        permission: BlobSasPermissions,
        expires_at: datetime,
        *,
        content_type: str | None = None,
        content_disposition: str | None = None,
    ) -> str: ...


class AccountKeySasSigner:
    """Signs with the account key. Local development only."""

    def __init__(self, account_name: str, account_key: str) -> None:
        self._account_name = account_name
        self._account_key = account_key

    def sign(self, container, blob_name, permission, expires_at, *, content_type=None, content_disposition=None) -> str:
        return generate_blob_sas(
            account_name=self._account_name,
            container_name=container,
            blob_name=blob_name,
            account_key=self._account_key,
            permission=permission,
            start=_now() - _CLOCK_SKEW,
            expiry=expires_at,
            content_type=content_type,
            content_disposition=content_disposition,
        )


class UserDelegationSasSigner:
    """Signs with a cached user delegation key, refreshed before it expires."""

    def __init__(
        self,
        service: BlobServiceClient,
        *,
        key_lifetime: timedelta = timedelta(hours=6),
        refresh_margin: timedelta = timedelta(hours=1),
    ) -> None:
        self._service = service
        self._key_lifetime = key_lifetime
        self._refresh_margin = refresh_margin
        self._key: UserDelegationKey | None = None
        self._key_expires_at: datetime | None = None
        self._lock = threading.Lock()

    def _delegation_key(self, needed_until: datetime) -> UserDelegationKey:
        with self._lock:
            if (
                self._key is None
                or self._key_expires_at is None
                or self._key_expires_at - self._refresh_margin <= max(_now(), needed_until)
            ):
                start = _now() - _CLOCK_SKEW
                expiry = max(_now() + self._key_lifetime, needed_until + self._refresh_margin)
                self._key = self._service.get_user_delegation_key(start, expiry)
                self._key_expires_at = expiry
            return self._key

    def sign(self, container, blob_name, permission, expires_at, *, content_type=None, content_disposition=None) -> str:
        return generate_blob_sas(
            account_name=self._service.account_name,
            container_name=container,
            blob_name=blob_name,
            user_delegation_key=self._delegation_key(expires_at),
            permission=permission,
            start=_now() - _CLOCK_SKEW,
            expiry=expires_at,
            protocol="https",
            content_type=content_type,
            content_disposition=content_disposition,
        )


def build_signer(service: BlobServiceClient) -> SasSigner:
    account_key = getattr(service.credential, "account_key", None)
    if account_key:
        return AccountKeySasSigner(service.account_name, account_key)
    return UserDelegationSasSigner(service)
