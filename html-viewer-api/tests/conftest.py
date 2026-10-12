from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.auth.models import User  # noqa: E402
from app.core import container  # noqa: E402
from app.files.service import FileService  # noqa: E402
from app.labels.service import LabelService  # noqa: E402
from app.shares.service import ShareService  # noqa: E402
from app.users.service import HandleService  # noqa: E402

from .fakes import (  # noqa: E402
    FakeBlobStore,
    FakeClock,
    FakeFileRepository,
    FakeHandleRepository,
    FakeLabelRepository,
    FakeShareRepository,
    FakeSlugIndex,
    make_settings,
)


@dataclass
class World:
    clock: FakeClock
    files_repo: FakeFileRepository
    shares_repo: FakeShareRepository
    blobs: FakeBlobStore
    slugs: FakeSlugIndex
    handles_repo: FakeHandleRepository
    labels_repo: FakeLabelRepository
    files: FileService
    shares: ShareService
    labels: LabelService
    handles: HandleService


ALICE = User(id="alice01", name="alice@contoso.com")
BOB = User(id="bob02", name="bob@contoso.com")
CAROL = User(id="carol03", name="carol@contoso.com")


@pytest.fixture
def world() -> World:
    settings = make_settings()
    clock = FakeClock()
    files_repo, shares_repo, blobs = FakeFileRepository(), FakeShareRepository(), FakeBlobStore()
    slugs, handles_repo, labels_repo = FakeSlugIndex(), FakeHandleRepository(), FakeLabelRepository()
    handles = HandleService(handles_repo)
    files = FileService(files_repo, shares_repo, blobs, slugs, handles, labels_repo, settings, clock)
    shares = ShareService(shares_repo, files_repo, files, settings, clock)
    labels = LabelService(labels_repo, files_repo, clock)
    w = World(clock, files_repo, shares_repo, blobs, slugs, handles_repo, labels_repo, files, shares, labels, handles)
    container.set_services(container.Services(settings=settings, files=files, shares=shares, labels=labels))
    yield w
    container.set_services(None)


def upload(world: World, user: User = ALICE, name: str = "report.html", size: int = 100):
    ticket = world.files.start_upload(user, file_name=name, size_bytes=size)
    world.blobs.blobs[ticket.file.blob_name] = size
    return world.files.complete_upload(user, ticket.file.file_id)
