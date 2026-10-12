"""Files uploaded before readable links existed: no slug, no owner handle.

They must end up exactly like new files, without anyone having to do anything.
"""

from __future__ import annotations

from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NotFound
from app.files.models import Visibility
from app.main import app

from .conftest import ALICE, BOB, upload
from .test_http import as_user


def legacy(world, user=ALICE, name="JEV en acción.html", **changes):
    """A stored file as it looked before readable links: no slug, no handle, nothing reserved."""
    record = upload(world, user, name)
    world.slugs.release(user.id, record.slug)
    old = replace(record, slug="", owner_handle="", **changes)
    world.files_repo.save(old)
    world.handles_repo.by_owner.pop(user.id, None)
    world.handles_repo.by_handle.pop(record.owner_handle, None)
    return old


class TestBackfill:
    def test_listing_gives_old_files_their_link(self, world):
        old = legacy(world)
        (listed,) = world.files.list_files(ALICE)
        assert (listed.file_id, listed.owner_handle, listed.slug) == (old.file_id, "alice", "jev-en-accion")
        assert world.files_repo.get(ALICE.id, old.file_id) == listed  # stored, not just shown
        assert world.files.view_by_slug(ALICE, "alice", "jev-en-accion").file.file_id == old.file_id

    def test_nothing_else_about_the_file_changes(self, world):
        old = legacy(world, visibility=Visibility.ORG, label_id="a" * 32)
        (listed,) = world.files.list_files(ALICE)
        assert replace(listed, slug="", owner_handle="") == old

    def test_listing_twice_is_stable(self, world):
        legacy(world)
        first = world.files.list_files(ALICE)
        assert world.files.list_files(ALICE) == first
        assert list(world.slugs.items) == [(ALICE.id, "jev-en-accion")]

    def test_two_requests_at_once_do_not_leave_a_second_name_reserved(self, world):
        """The page asks for the list twice in a row; both may see the file without a link."""
        old = legacy(world)
        stale_read = [old]
        world.files.list_files(ALICE)
        world.files_repo.list_ready = lambda owner_id: stale_read  # second request still sees the old row
        (again,) = world.files.list_files(ALICE)
        assert again.slug == "jev-en-accion"
        assert list(world.slugs.items) == [(ALICE.id, "jev-en-accion")]

    def test_old_file_does_not_take_the_name_of_a_newer_one(self, world):
        old = legacy(world, name="report.html")
        newer = upload(world, ALICE, "report.html")
        by_id = {f.file_id: f.slug for f in world.files.list_files(ALICE)}
        assert by_id == {newer.file_id: "report", old.file_id: "report-2"}

    def test_several_old_files_with_the_same_name(self, world):
        ids = [legacy(world, name="report.html").file_id for _ in range(3)]
        slugs = sorted(f.slug for f in world.files.list_files(ALICE))
        assert slugs == ["report", "report-2", "report-3"]
        assert len(ids) == 3

    def test_only_the_owners_listing_touches_it(self, world):
        old = legacy(world)
        assert world.files.list_files(BOB) == []
        assert world.files_repo.get(ALICE.id, old.file_id).slug == ""

    def test_half_migrated_file_keeps_its_slug(self, world):
        record = upload(world, ALICE, "report.html")
        world.files_repo.save(replace(record, owner_handle=""))
        (listed,) = world.files.list_files(ALICE)
        assert (listed.owner_handle, listed.slug) == ("alice", "report")


class TestActionsOnAnOldFileBeforeItIsListed:
    """Every way of touching the file fixes it too, not only the list."""

    def test_edit_link(self, world):
        old = legacy(world)
        updated = world.files.update(ALICE, old.file_id, slug="Inducción a JEV")
        assert (updated.owner_handle, updated.slug) == ("alice", "induccion-a-jev")
        assert world.files.view_by_slug(ALICE, "alice", "induccion-a-jev").file.file_id == old.file_id
        with pytest.raises(NotFound):
            world.files.view_by_slug(ALICE, "alice", "jev-en-accion")  # the automatic name was released

    def test_rename_or_change_visibility(self, world):
        old = legacy(world)
        updated = world.files.update(ALICE, old.file_id, title="Otro")
        assert (updated.owner_handle, updated.slug) == ("alice", "jev-en-accion")

    def test_share(self, world):
        old = legacy(world)
        share = world.shares.create(ALICE, old.file_id, expires_in_days=1)
        assert world.shares.resolve_readable("alice", f"jev-en-accion-{share.token}").file.file_id == old.file_id

    def test_share_created_before_still_opens_both_ways(self, world):
        old = legacy(world)
        share = world.shares.create(ALICE, old.file_id, expires_in_days=1)
        assert world.shares.resolve(share.token).file.file_id == old.file_id
        assert world.shares.resolve_readable("alice", f"jev-en-accion-{share.token}").file.file_id == old.file_id

    def test_delete_leaves_nothing_reserved(self, world):
        old = legacy(world)
        world.files.list_files(ALICE)
        world.files.delete(ALICE, old.file_id)
        assert world.slugs.items == {}

    def test_old_link_by_ids_keeps_working(self, world):
        old = legacy(world)
        assert world.files.view(ALICE, ALICE.id, old.file_id).file.file_id == old.file_id
        world.files.list_files(ALICE)
        assert world.files.view(ALICE, ALICE.id, old.file_id).file.file_id == old.file_id


class TestHttp:
    @pytest.fixture
    def client(self, world) -> TestClient:
        return TestClient(app, headers=as_user(ALICE), raise_server_exceptions=False)

    def test_list_never_returns_a_file_without_its_link(self, world, client):
        legacy(world)
        item = client.get("/api/files").json()["items"][0]
        assert (item["ownerHandle"], item["slug"]) == ("alice", "jev-en-accion")
        assert client.get("/api/u/alice/jev-en-accion").status_code == 200

    def test_edit_link_answers_with_a_usable_link(self, world, client):
        old = legacy(world)
        body = client.patch(f"/api/files/{old.file_id}", json={"slug": "induccion a jev"}).json()
        assert (body["ownerHandle"], body["slug"]) == ("alice", "induccion-a-jev")
        assert client.get("/api/u/alice/induccion-a-jev").status_code == 200

    def test_other_users_gain_nothing_from_the_migration(self, world, client):
        legacy(world)
        client.get("/api/files")
        bob = TestClient(app, headers=as_user(BOB))
        assert bob.get("/api/u/alice/jev-en-accion").status_code == 404
        assert bob.get("/api/files").json() == {"items": []}
