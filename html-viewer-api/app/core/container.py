"""Composition root: wires settings, Azure clients, repositories and services.

Built lazily once per process and injected into the routers as `ServicesDep`.
Tests swap it with `set_services`.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from typing import Annotated

from azure.core.exceptions import ResourceExistsError
from azure.data.tables import TableServiceClient
from azure.identity import DefaultAzureCredential
from azure.storage.blob import BlobServiceClient
from fastapi import Depends

from ..files.repository import TableFileRepository, TableSlugIndex
from ..files.service import FileService
from ..labels.repository import TableLabelRepository
from ..labels.service import LabelService
from ..shares.repository import TableShareRepository
from ..shares.service import ShareService
from ..users.repository import TableHandleRepository
from ..users.service import HandleService
from ..storage.blob_store import AzureBlobStore
from ..storage.sas import build_signer
from .config import Settings


@dataclass(frozen=True)
class Services:
    settings: Settings
    files: FileService
    shares: ShareService
    labels: LabelService


_services: Services | None = None
_lock = threading.Lock()


def _clients(settings: Settings) -> tuple[BlobServiceClient, TableServiceClient]:
    if settings.connection_string:
        return (
            BlobServiceClient.from_connection_string(settings.connection_string),
            TableServiceClient.from_connection_string(settings.connection_string),
        )
    credential = DefaultAzureCredential()
    return (
        BlobServiceClient(settings.blob_endpoint, credential=credential),
        TableServiceClient(settings.table_endpoint, credential=credential),
    )


def build_services(settings: Settings) -> Services:
    blob_service, table_service = _clients(settings)
    container = blob_service.get_container_client(settings.container_name)

    if settings.auto_create_resources:
        try:
            container.create_container()
        except ResourceExistsError:
            pass
        for name in settings.table_names:
            table_service.create_table_if_not_exists(name)

    files_repo = TableFileRepository(table_service.get_table_client(settings.files_table))
    shares_repo = TableShareRepository(table_service.get_table_client(settings.shares_table))
    blobs = AzureBlobStore(container, build_signer(blob_service), public_base_url=settings.public_blob_base_url)

    labels_repo = TableLabelRepository(table_service.get_table_client(settings.labels_table))
    slugs = TableSlugIndex(table_service.get_table_client(settings.slugs_table))
    handles = HandleService(TableHandleRepository(table_service.get_table_client(settings.users_table)))

    file_service = FileService(files_repo, shares_repo, blobs, slugs, handles, labels_repo, settings)
    share_service = ShareService(shares_repo, files_repo, file_service, settings)
    label_service = LabelService(labels_repo, files_repo)
    return Services(settings=settings, files=file_service, shares=share_service, labels=label_service)


def get_services() -> Services:
    global _services
    if _services is None:
        with _lock:
            if _services is None:
                _services = build_services(Settings.from_env())
    return _services


def set_services(services: Services | None) -> None:
    global _services
    _services = services


ServicesDep = Annotated[Services, Depends(get_services)]
