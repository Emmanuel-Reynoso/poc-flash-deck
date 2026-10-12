"""Two changes to the same file at the same time: neither may be lost.

Happens with two quick actions in a row (drag to a label, then somewhere else),
two tabs, or the page asking twice.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import Conflict, NotFound
from app.files.models import FileStatus, Visibility
from app.main import app

from .conftest import ALICE, upload
from .test_http import as_user


def someone_else_writes_first(world, change, *, times=1):
    """Before our write lands, another request changes the stored file `times` times."""
    real_update = world.files_repo.update
    remaining = [times]

    def update(record):
        if remaining[0] > 0:
            remaining[0] -= 1
            change(world.files_repo.get(record.owner_id, record.file_id))
        return real_update(record)

    world.files_repo.update = update


class TestRepositoryContract:
    def test_update_needs_the_version_that_was_read(self, world):
        record = upload(world)
        fresh = world.files_repo.get(ALICE.id, record.file_id)
        assert world.files_repo.update(replace(fresh, title="A")) is True
        assert world.files_repo.update(replace(fresh, title="B")) is False  # read before the previous write
        assert world.files_repo.get(ALICE.id, record.file_id).title == "A"

    def test_update_does_not_bring_back_a_deleted_file(self, world):
        record = upload(world)
        fresh = world.files_repo.get(ALICE.id, record.file_id)
        world.files_repo.delete(ALICE.id, record.file_id)
        assert world.files_repo.update(replace(fresh, title="A")) is False
        assert world.files_repo.get(ALICE.id, record.file_id) is None


class TestUpdate:
    def test_changes_to_different_fields_are_both_kept(self, world):
        record = upload(world)
        someone_else_writes_first(world, lambda r: world.files_repo.save(replace(r, title="Desde otra pestaña")))

        updated = world.files.update(ALICE, record.file_id, visibility="org")

        assert (updated.title, updated.visibility) == ("Desde otra pestaña", Visibility.ORG)
        assert world.files_repo.get(ALICE.id, record.file_id) == updated

    def test_label_move_survives_a_simultaneous_rename(self, world):
        label = world.labels.create(ALICE, name="Alfa")
        record = upload(world)
        someone_else_writes_first(world, lambda r: world.files_repo.save(replace(r, title="Renombrado")))

        updated = world.files.update(ALICE, record.file_id, label_id=label.label_id)

        assert (updated.title, updated.label_id) == ("Renombrado", label.label_id)

    def test_two_link_names_at_once_leave_only_one_reserved(self, world):
        record = upload(world, name="report.html")

        def other_request(r):
            world.slugs.reserve(ALICE.id, "desde-otra", r.file_id)
            world.files_repo.save(replace(r, slug="desde-otra"))
            world.slugs.release(ALICE.id, "report")

        someone_else_writes_first(world, other_request)
        updated = world.files.update(ALICE, record.file_id, slug="la-mia")

        assert updated.slug == "la-mia"
        assert world.slugs.items == {(ALICE.id, "la-mia"): record.file_id}

    def test_file_deleted_meanwhile_is_not_found_and_reserves_nothing(self, world):
        record = upload(world, name="report.html")
        someone_else_writes_first(world, lambda r: world.files.delete(ALICE, r.file_id))

        with pytest.raises(NotFound):
            world.files.update(ALICE, record.file_id, slug="nuevo")

        assert world.files_repo.get(ALICE.id, record.file_id) is None  # not resurrected
        assert world.slugs.items == {}

    def test_gives_up_cleanly_if_it_never_gets_through(self, world):
        record = upload(world, name="report.html")
        counter = iter(range(1000))
        someone_else_writes_first(
            world, lambda r: world.files_repo.save(replace(r, title=f"t{next(counter)}")), times=1000
        )

        with pytest.raises(Conflict) as err:
            world.files.update(ALICE, record.file_id, slug="nuevo")

        assert err.value.code == "conflict"
        assert world.slugs.items == {(ALICE.id, "report"): record.file_id}  # the new name was given back

    def test_http_answers_409(self, world):
        record = upload(world)
        someone_else_writes_first(world, lambda r: world.files_repo.save(replace(r, title="x")), times=1000)
        client = TestClient(app, headers=as_user(ALICE))
        resp = client.patch(f"/api/files/{record.file_id}", json={"visibility": "org"})
        assert (resp.status_code, resp.json()["error"]["code"]) == (409, "conflict")


class TestOtherWriters:
    def test_complete_upload_twice_at_once(self, world):
        ticket = world.files.start_upload(ALICE, file_name="a.html", size_bytes=10)
        world.blobs.blobs[ticket.file.blob_name] = 10
        someone_else_writes_first(world, lambda r: world.files_repo.save(replace(r, status=FileStatus.READY)))

        ready = world.files.complete_upload(ALICE, ticket.file.file_id)

        assert ready.status is FileStatus.READY

    def test_complete_upload_of_a_file_deleted_meanwhile(self, world):
        ticket = world.files.start_upload(ALICE, file_name="a.html", size_bytes=10)
        world.blobs.blobs[ticket.file.blob_name] = 10
        someone_else_writes_first(world, lambda r: world.files_repo.delete(r.owner_id, r.file_id))

        with pytest.raises(NotFound):
            world.files.complete_upload(ALICE, ticket.file.file_id)
        assert world.files_repo.get(ALICE.id, ticket.file.file_id) is None

    def test_deleting_a_label_while_a_file_is_renamed(self, world):
        label = world.labels.create(ALICE, name="Alfa")
        record = world.files.update(ALICE, upload(world).file_id, label_id=label.label_id)
        someone_else_writes_first(world, lambda r: world.files_repo.save(replace(r, title="Renombrado")))

        world.labels.delete(ALICE, label.label_id)

        stored = world.files_repo.get(ALICE.id, record.file_id)
        assert (stored.title, stored.label_id) == ("Renombrado", None)

    def test_deleting_a_label_while_its_file_moves_elsewhere(self, world):
        label = world.labels.create(ALICE, name="Alfa")
        other = world.labels.create(ALICE, name="Beta")
        record = world.files.update(ALICE, upload(world).file_id, label_id=label.label_id)
        someone_else_writes_first(world, lambda r: world.files_repo.save(replace(r, label_id=other.label_id)))

        world.labels.delete(ALICE, label.label_id)

        assert world.files_repo.get(ALICE.id, record.file_id).label_id == other.label_id  # the move wins
