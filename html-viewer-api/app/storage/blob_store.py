"""Blob Storage adapter for the HTML files."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import quote

from azure.core.exceptions import ResourceNotFoundError
from azure.storage.blob import BlobSasPermissions, ContainerClient, ContentSettings

from .sas import SasSigner

HTML_CONTENT_TYPE = "text/html; charset=utf-8"


def _disposition(kind: str, file_name: str | None) -> str:
    if not file_name:
        return kind
    ascii_name = file_name.encode("ascii", "replace").decode().replace('"', "")
    return f"{kind}; filename=\"{ascii_name}\"; filename*=UTF-8''{quote(file_name)}"


class AzureBlobStore:
    def __init__(self, container: ContainerClient, signer: SasSigner, *, public_base_url: str | None = None) -> None:
        self._container = container
        self._signer = signer
        # Base URL for links handed to browsers: the container URL, or a custom
        # content domain in front of it.
        self._base_url = (
            f"{public_base_url}/{container.container_name}" if public_base_url else container.url.rstrip("/")
        )

    def _url(self, blob_name: str, sas: str) -> str:
        return f"{self._base_url}/{quote(blob_name)}?{sas}"

    def upload_url(self, blob_name: str, expires_at: datetime) -> str:
        sas = self._signer.sign(
            self._container.container_name,
            blob_name,
            BlobSasPermissions(create=True, write=True),
            expires_at,
        )
        return self._url(blob_name, sas)

    def read_url(self, blob_name: str, expires_at: datetime, *, download_name: str | None = None) -> str:
        # Response headers are pinned in the SAS, so the browser always renders
        # (or downloads) the blob as HTML regardless of what was uploaded.
        sas = self._signer.sign(
            self._container.container_name,
            blob_name,
            BlobSasPermissions(read=True),
            expires_at,
            content_type=HTML_CONTENT_TYPE,
            content_disposition=_disposition("attachment", download_name) if download_name else "inline",
        )
        return self._url(blob_name, sas)

    def get_size(self, blob_name: str) -> int | None:
        try:
            return self._container.get_blob_client(blob_name).get_blob_properties().size
        except ResourceNotFoundError:
            return None

    def finalize(self, blob_name: str) -> None:
        self._container.get_blob_client(blob_name).set_http_headers(
            ContentSettings(
                content_type=HTML_CONTENT_TYPE,
                content_disposition="inline",
                cache_control="private, max-age=300",
            )
        )

    def delete(self, blob_name: str) -> None:
        try:
            self._container.get_blob_client(blob_name).delete_blob(delete_snapshots="include")
        except ResourceNotFoundError:
            pass
