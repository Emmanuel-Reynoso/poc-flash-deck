"""Application settings, read once from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw not in (None, "") else default


def _bool(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # Storage access: a connection string (local dev / Azurite) OR an account name
    # used with Managed Identity (production). Endpoints can be overridden for
    # sovereign clouds or private endpoints.
    connection_string: str | None
    account_name: str | None
    blob_endpoint: str | None
    table_endpoint: str | None

    container_name: str
    files_table: str
    shares_table: str
    users_table: str
    slugs_table: str
    labels_table: str

    max_upload_bytes: int
    upload_sas_minutes: int
    view_sas_minutes: int
    share_max_days: int
    pending_ttl_hours: int

    # Optional custom domain that fronts the blob container (e.g. Front Door on
    # content.example.com). Must stay a different origin than the web app.
    public_blob_base_url: str | None

    # Create container/tables on first use. Only for local development; in
    # Azure they are provisioned by Bicep.
    auto_create_resources: bool

    @classmethod
    def from_env(cls) -> "Settings":
        account_name = os.getenv("STORAGE_ACCOUNT_NAME") or None
        connection_string = os.getenv("STORAGE_CONNECTION_STRING") or None
        if not connection_string and not account_name:
            raise RuntimeError("Set STORAGE_ACCOUNT_NAME (Azure) or STORAGE_CONNECTION_STRING (local).")

        return cls(
            connection_string=connection_string,
            account_name=account_name,
            blob_endpoint=os.getenv("STORAGE_BLOB_ENDPOINT")
            or (f"https://{account_name}.blob.core.windows.net" if account_name else None),
            table_endpoint=os.getenv("STORAGE_TABLE_ENDPOINT")
            or (f"https://{account_name}.table.core.windows.net" if account_name else None),
            container_name=os.getenv("HTML_CONTAINER", "html"),
            files_table=os.getenv("FILES_TABLE", "files"),
            shares_table=os.getenv("SHARES_TABLE", "shares"),
            users_table=os.getenv("USERS_TABLE", "users"),
            slugs_table=os.getenv("SLUGS_TABLE", "slugs"),
            labels_table=os.getenv("LABELS_TABLE", "labels"),
            max_upload_bytes=_int("MAX_UPLOAD_MB", 20) * 1024 * 1024,
            upload_sas_minutes=_int("UPLOAD_SAS_MINUTES", 10),
            view_sas_minutes=_int("VIEW_SAS_MINUTES", 10),
            share_max_days=_int("SHARE_MAX_DAYS", 30),
            pending_ttl_hours=_int("PENDING_TTL_HOURS", 24),
            public_blob_base_url=(os.getenv("PUBLIC_BLOB_BASE_URL") or "").rstrip("/") or None,
            auto_create_resources=_bool("AUTO_CREATE_RESOURCES"),
        )

    @property
    def table_names(self) -> tuple[str, ...]:
        return (self.files_table, self.shares_table, self.users_table, self.slugs_table, self.labels_table)
