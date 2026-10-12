"""Readable links: /u/{handle}/{slug}."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.models import User
from app.core.errors import BadRequest, Conflict, NotFound
from app.core.slug import is_slug, slugify
from app.files.models import Visibility
from app.main import app
from app.users.service import handle_base

from .conftest import ALICE, BOB, upload
from .test_http import as_user


class TestSlugify:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("Ventas Q3", "ventas-q3"),
            ("  Reporte__final (v2).html ", "reporte-final-v2-html"),
            ("Ñandú & Cía", "nandu-cia"),
            ("---", ""),
            ("日本語", ""),
            ("a" * 100, "a" * 60),
        ],
    )
    def test_slugify(self, raw, expected):
        assert slugify(raw) == expected

    def test_never_leaves_a_trailing_dash_when_truncating(self):
        assert slugify("a" * 59 + " b") == "a" * 59

    @pytest.mark.parametrize("bad", ["", "-a", "a-", "a--b", "A", "a b", "a/b", "../x", "a.b", "x" * 100])
    def test_is_slug_rejects(self, bad):
        assert not is_slug(bad)


class TestHandles:
    def test_comes_from_the_sign_in_name(self, world):
        assert world.handles.ensure(User("u1", "Emmanuel.Reynoso@contoso.com")) == "emmanuel-reynoso"

    def test_is_stable_even_if_the_name_changes(self, world):
        first = world.handles.ensure(User("u1", "ana@contoso.com"))
        assert world.handles.ensure(User("u1", "ana.maria@contoso.com")) == first == "ana"

    def test_same_name_in_two_domains_gets_distinct_handles(self, world):
        a = world.handles.ensure(User("u1", "ana@contoso.com"))
        b = world.handles.ensure(User("u2", "ana@fabrikam.com"))
        c = world.handles.ensure(User("u3", "ANA@other.com"))
        assert (a, b, c) == ("ana", "ana-2", "ana-3")
        assert world.handles.owner_of("ana") == "u1" and world.handles.owner_of("ana-2") == "u2"

    def test_fallback_for_names_without_letters(self, world):
        assert handle_base("@contoso.com") == "usuario"
        assert world.handles.ensure(User("u1", "日本")) == "usuario"

    def test_reuses_a_half_finished_claim(self, world):
        world.handles_repo.claim("ana", "u1")  # claimed, but never recorded for the owner
        assert world.handles.ensure(User("u1", "ana@contoso.com")) == "ana"

    def test_unknown_or_malformed_handle(self, world):
        assert world.handles.owner_of("nadie") is None
        assert world.handles.owner_of("../etc") is None


class TestFileSlugs:
    def test_upload_gets_slug_and_handle(self, world):
        record = upload(world, name="Ventas Q3.html")
        assert (record.owner_handle, record.slug) == ("alice", "ventas-q3")

    def test_same_name_twice_gets_a_suffix(self, world):
        slugs = [upload(world, name="report.html").slug for _ in range(3)]
        assert slugs == ["report", "report-2", "report-3"]

    def test_slugs_are_per_user(self, world):
        assert upload(world, ALICE, "report.html").slug == upload(world, BOB, "report.html").slug == "report"

    def test_name_without_letters_uses_fallback(self, world):
        assert upload(world, name="日本語.html").slug == "archivo"

    def test_renaming_the_title_keeps_the_link(self, world):
        record = upload(world, name="report.html")
        assert world.files.update(ALICE, record.file_id, title="Otro título").slug == "report"

    def test_change_slug_frees_the_old_one(self, world):
        record = upload(world, name="report.html")
        updated = world.files.update(ALICE, record.file_id, slug="Ventas 2026")
        assert updated.slug == "ventas-2026"
        assert world.files.view_by_slug(ALICE, "alice", "ventas-2026").file.file_id == record.file_id
        with pytest.raises(NotFound):
            world.files.view_by_slug(ALICE, "alice", "report")  # the old link stops working
        assert upload(world, name="report.html").slug == "report"  # and the name is free again

    def test_slug_must_be_unique_per_user(self, world):
        upload(world, name="a.html")
        other = upload(world, name="b.html")
        with pytest.raises(Conflict) as err:
            world.files.update(ALICE, other.file_id, slug="a")
        assert err.value.code == "slug_taken"
        assert world.files.view_by_slug(ALICE, "alice", "b").file.file_id == other.file_id  # unchanged

    def test_same_slug_is_a_no_op(self, world):
        record = upload(world, name="a.html")
        assert world.files.update(ALICE, record.file_id, slug="a") == record

    @pytest.mark.parametrize("bad", ["", "---", "日本", 5])
    def test_invalid_slug(self, world, bad):
        record = upload(world)
        with pytest.raises(BadRequest) as err:
            world.files.update(ALICE, record.file_id, slug=bad)
        assert err.value.code == "invalid_slug"

    def test_delete_frees_the_slug(self, world):
        record = upload(world, name="report.html")
        world.files.delete(ALICE, record.file_id)
        assert world.slugs.items == {}
        with pytest.raises(NotFound):
            world.files.view_by_slug(ALICE, "alice", "report")

    def test_purge_frees_the_slug(self, world):
        world.files.start_upload(ALICE, file_name="stale.html", size_bytes=10)
        world.clock.advance(hours=25)
        assert world.files.purge_stale_pending() == 1
        assert world.slugs.items == {}

    def test_oversized_upload_frees_the_slug(self, world):
        ticket = world.files.start_upload(ALICE, file_name="big.html", size_bytes=10)
        world.blobs.blobs[ticket.file.blob_name] = 10_000
        with pytest.raises(Exception):
            world.files.complete_upload(ALICE, ticket.file.file_id)
        assert world.slugs.items == {}

    def test_pending_file_is_not_viewable_by_slug(self, world):
        world.files.start_upload(ALICE, file_name="draft.html", size_bytes=10)
        with pytest.raises(NotFound):
            world.files.view_by_slug(ALICE, "alice", "draft")


class TestViewBySlugAccess:
    def test_private_file_is_hidden_from_others(self, world):
        upload(world, name="report.html")
        with pytest.raises(NotFound):
            world.files.view_by_slug(BOB, "alice", "report")

    def test_org_file_is_visible_to_others(self, world):
        record = upload(world, name="report.html")
        world.files.update(ALICE, record.file_id, visibility=Visibility.ORG)
        assert world.files.view_by_slug(BOB, "alice", "report").file.file_id == record.file_id

    def test_slug_is_looked_up_under_the_handle_in_the_url(self, world):
        upload(world, ALICE, "report.html")
        mine = upload(world, BOB, "report.html")
        assert world.files.view_by_slug(BOB, "bob", "report").file.file_id == mine.file_id

    @pytest.mark.parametrize(("handle", "slug"), [("nadie", "report"), ("alice", "nope"), ("alice", "../x"), ("", "")])
    def test_unknown(self, world, handle, slug):
        upload(world, name="report.html")
        with pytest.raises(NotFound):
            world.files.view_by_slug(ALICE, handle, slug)


class TestHttp:
    @pytest.fixture
    def client(self, world) -> TestClient:
        return TestClient(app, headers=as_user(ALICE), raise_server_exceptions=False)

    def test_file_exposes_what_the_link_needs(self, world, client):
        upload(world, name="Ventas Q3.html")
        item = client.get("/api/files").json()["items"][0]
        assert (item["ownerHandle"], item["slug"]) == ("alice", "ventas-q3")

    def test_view_by_readable_link(self, world, client):
        record = upload(world, name="report.html")
        resp = client.get("/api/u/alice/report")
        assert resp.status_code == 200
        assert resp.json()["file"]["id"] == record.file_id and resp.json()["viewUrl"]

    def test_requires_login(self, world):
        upload(world, name="report.html")
        assert TestClient(app).get("/api/u/alice/report").status_code == 401

    def test_change_slug(self, world, client):
        record = upload(world, name="report.html")
        upload(world, name="taken.html")
        assert client.patch(f"/api/files/{record.file_id}", json={"slug": "Mi Reporte"}).json()["slug"] == "mi-reporte"
        assert client.get("/api/u/alice/mi-reporte").status_code == 200
        assert client.get("/api/u/alice/report").status_code == 404

        resp = client.patch(f"/api/files/{record.file_id}", json={"slug": "taken"})
        assert (resp.status_code, resp.json()["error"]["code"]) == (409, "slug_taken")
        resp = client.patch(f"/api/files/{record.file_id}", json={"slug": "!!!"})
        assert (resp.status_code, resp.json()["error"]["code"]) == (400, "invalid_slug")
