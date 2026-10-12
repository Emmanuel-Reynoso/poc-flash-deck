from __future__ import annotations

import pytest

from app.core.errors import BadRequest, Conflict, NotFound, PayloadTooLarge
from app.files.models import FileStatus, Visibility
from app.files.service import clean_file_name

from .conftest import ALICE, BOB, upload


class TestFileNames:
    def test_strips_paths(self):
        assert clean_file_name("C:\\users\\x\\Reporte final.HTML") == "Reporte final.HTML"

    @pytest.mark.parametrize("bad", ["", "   ", "notes.txt", "x.html.exe", None, 42])
    def test_rejects_invalid(self, bad):
        with pytest.raises(BadRequest):
            clean_file_name(bad)

    def test_truncates_long_names_keeping_extension(self):
        name = clean_file_name("a" * 500 + ".html")
        assert len(name) == 200 and name.endswith(".html")


class TestUpload:
    def test_happy_path(self, world):
        ticket = world.files.start_upload(ALICE, file_name="ventas.html", size_bytes=100)
        assert ticket.file.status is FileStatus.PENDING
        assert ticket.file.title == "ventas"
        assert ticket.file.blob_name.startswith(f"{ALICE.id}/")
        assert ticket.required_headers["x-ms-blob-type"] == "BlockBlob"
        assert world.files.list_files(ALICE) == []  # pending files are hidden

        world.blobs.blobs[ticket.file.blob_name] = 90
        ready = world.files.complete_upload(ALICE, ticket.file.file_id)
        assert ready.status is FileStatus.READY
        assert ready.size_bytes == 90  # real size wins over the declared one
        assert ticket.file.blob_name in world.blobs.finalized
        assert world.files.list_files(ALICE) == [ready]

    def test_rejects_declared_size_over_limit(self, world):
        with pytest.raises(PayloadTooLarge):
            world.files.start_upload(ALICE, file_name="big.html", size_bytes=10_000)

    @pytest.mark.parametrize("size", [0, -1, "100", True, None])
    def test_rejects_bad_size(self, world, size):
        with pytest.raises(BadRequest):
            world.files.start_upload(ALICE, file_name="a.html", size_bytes=size)

    def test_complete_without_blob_is_conflict(self, world):
        ticket = world.files.start_upload(ALICE, file_name="a.html", size_bytes=10)
        with pytest.raises(Conflict):
            world.files.complete_upload(ALICE, ticket.file.file_id)

    def test_actual_blob_over_limit_is_deleted(self, world):
        ticket = world.files.start_upload(ALICE, file_name="a.html", size_bytes=10)
        world.blobs.blobs[ticket.file.blob_name] = 5_000  # lied about the size
        with pytest.raises(PayloadTooLarge):
            world.files.complete_upload(ALICE, ticket.file.file_id)
        assert ticket.file.blob_name not in world.blobs.blobs
        assert world.files_repo.get(ALICE.id, ticket.file.file_id) is None

    def test_complete_is_idempotent(self, world):
        record = upload(world)
        assert world.files.complete_upload(ALICE, record.file_id) == record

    def test_cannot_complete_someone_elses_upload(self, world):
        ticket = world.files.start_upload(ALICE, file_name="a.html", size_bytes=10)
        with pytest.raises(NotFound):
            world.files.complete_upload(BOB, ticket.file.file_id)


class TestListing:
    def test_newest_first_and_only_mine(self, world):
        first = upload(world, name="one.html")
        world.clock.advance(minutes=1)
        second = upload(world, name="two.html")
        upload(world, user=BOB, name="bob.html")
        assert [f.file_id for f in world.files.list_files(ALICE)] == [second.file_id, first.file_id]


class TestViewing:
    def test_owner_can_view(self, world):
        record = upload(world)
        link = world.files.view(ALICE, ALICE.id, record.file_id)
        assert "inline" in link.view_url
        assert "attachment:report.html" in link.download_url

    def test_private_file_hidden_from_others(self, world):
        record = upload(world)
        with pytest.raises(NotFound):
            world.files.view(BOB, ALICE.id, record.file_id)

    def test_org_file_visible_to_colleagues(self, world):
        record = upload(world)
        world.files.update(ALICE, record.file_id, visibility="org")
        assert world.files.view(BOB, ALICE.id, record.file_id).file.visibility is Visibility.ORG

    def test_pending_file_not_viewable(self, world):
        ticket = world.files.start_upload(ALICE, file_name="a.html", size_bytes=10)
        with pytest.raises(NotFound):
            world.files.view(ALICE, ALICE.id, ticket.file.file_id)


class TestUpdateAndDelete:
    def test_rename_and_visibility(self, world):
        record = upload(world)
        updated = world.files.update(ALICE, record.file_id, title="  Ventas   Q3 ", visibility="org")
        assert updated.title == "Ventas Q3"
        assert updated.visibility is Visibility.ORG

    def test_bad_visibility(self, world):
        record = upload(world)
        with pytest.raises(BadRequest):
            world.files.update(ALICE, record.file_id, visibility="public")

    def test_others_cannot_update(self, world):
        record = upload(world)
        with pytest.raises(NotFound):
            world.files.update(BOB, record.file_id, title="hacked")

    def test_delete_removes_blob_record_and_shares(self, world):
        record = upload(world)
        share = world.shares.create(ALICE, record.file_id, expires_in_days=7)
        world.files.delete(ALICE, record.file_id)
        assert world.files_repo.items == {}
        assert world.blobs.blobs == {}
        assert world.shares_repo.get(share.token) is None


class TestPurge:
    def test_removes_only_stale_pending(self, world):
        stale = world.files.start_upload(ALICE, file_name="old.html", size_bytes=10)
        world.blobs.blobs[stale.file.blob_name] = 10
        ready = upload(world)
        world.clock.advance(hours=25)
        fresh = world.files.start_upload(ALICE, file_name="new.html", size_bytes=10)

        assert world.files.purge_stale_pending() == 1
        assert world.files_repo.get(ALICE.id, stale.file.file_id) is None
        assert stale.file.blob_name not in world.blobs.blobs
        assert world.files_repo.get(ALICE.id, ready.file_id) is not None
        assert world.files_repo.get(ALICE.id, fresh.file.file_id) is not None


class TestShares:
    def test_create_and_resolve(self, world):
        record = upload(world)
        share = world.shares.create(ALICE, record.file_id, expires_in_days=3)
        assert len(share.token) == 12 and share.token.isalnum()
        link = world.shares.resolve(share.token)
        assert link.file.file_id == record.file_id

    def test_expired_link(self, world):
        record = upload(world)
        share = world.shares.create(ALICE, record.file_id, expires_in_days=1)
        world.clock.advance(days=1)
        with pytest.raises(NotFound):
            world.shares.resolve(share.token)
        assert world.shares.list_for_file(ALICE, record.file_id) == []

    @pytest.mark.parametrize("days", [0, 31, "7", None, True])
    def test_invalid_duration(self, world, days):
        record = upload(world)
        with pytest.raises(BadRequest):
            world.shares.create(ALICE, record.file_id, expires_in_days=days)

    def test_only_owner_can_share_or_revoke(self, world):
        record = upload(world)
        with pytest.raises(NotFound):
            world.shares.create(BOB, record.file_id, expires_in_days=7)
        share = world.shares.create(ALICE, record.file_id, expires_in_days=7)
        with pytest.raises(NotFound):
            world.shares.revoke(BOB, share.token)
        world.shares.revoke(ALICE, share.token)
        with pytest.raises(NotFound):
            world.shares.resolve(share.token)

    def test_unknown_token(self, world):
        with pytest.raises(NotFound):
            world.shares.resolve("nope")
