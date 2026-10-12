"""Each user sees and changes only what is theirs.

Everything goes through HTTP, as a browser would. ALICE owns the data; BOB and
CAROL are other signed-in users of the same organization; an anonymous client
has no session at all.
"""

from __future__ import annotations

import base64
import json

import pytest
from fastapi.testclient import TestClient

from app.auth.principal import PRINCIPAL_HEADER, encode_principal
from app.main import app

from .conftest import ALICE, BOB, CAROL, upload
from .test_http import as_user


@pytest.fixture
def alice(world) -> TestClient:
    return TestClient(app, headers=as_user(ALICE), raise_server_exceptions=False)


@pytest.fixture
def bob(world) -> TestClient:
    return TestClient(app, headers=as_user(BOB), raise_server_exceptions=False)


@pytest.fixture
def carol(world) -> TestClient:
    return TestClient(app, headers=as_user(CAROL), raise_server_exceptions=False)


@pytest.fixture
def anonymous(world) -> TestClient:
    return TestClient(app, raise_server_exceptions=False)


@pytest.fixture
def scene(world, alice):
    """ALICE has a private file inside a label, with a public link."""
    record = upload(world, ALICE, "secreto.html")
    label = alice.post("/api/labels", json={"name": "Proyecto Alfa"}).json()
    alice.patch(f"/api/files/{record.file_id}", json={"labelId": label["id"]})
    token = alice.post(f"/api/files/{record.file_id}/shares", json={"expiresInDays": 2}).json()["token"]
    return {"file_id": record.file_id, "label_id": label["id"], "token": token}


def snapshot(alice: TestClient) -> tuple:
    return (alice.get("/api/files").json(), alice.get("/api/labels").json())


class TestListsAreSeparate:
    def test_each_user_lists_only_their_files(self, world, alice, bob, carol):
        mine = upload(world, ALICE, "a.html")
        theirs = upload(world, BOB, "b.html")
        assert [f["id"] for f in alice.get("/api/files").json()["items"]] == [mine.file_id]
        assert [f["id"] for f in bob.get("/api/files").json()["items"]] == [theirs.file_id]
        assert carol.get("/api/files").json() == {"items": []}

    def test_org_visibility_does_not_put_files_in_other_lists(self, world, alice, bob):
        record = upload(world, ALICE, "a.html")
        alice.patch(f"/api/files/{record.file_id}", json={"visibility": "org"})
        assert bob.get("/api/files").json() == {"items": []}

    def test_each_user_lists_only_their_labels(self, alice, bob, carol):
        alice.post("/api/labels", json={"name": "De Alice"})
        bob.post("/api/labels", json={"name": "De Bob"})
        assert [x["name"] for x in alice.get("/api/labels").json()["items"]] == ["De Alice"]
        assert [x["name"] for x in bob.get("/api/labels").json()["items"]] == ["De Bob"]
        assert carol.get("/api/labels").json() == {"items": []}

    def test_pending_uploads_of_others_are_invisible(self, world, alice, bob):
        ticket = world.files.start_upload(ALICE, file_name="draft.html", size_bytes=10)
        assert bob.get("/api/files").json() == {"items": []}
        assert bob.post(f"/api/files/{ticket.file.file_id}/complete").status_code == 404


class TestPrivateFileOfSomeoneElse:
    """BOB knows every id of ALICE's file and still gets nothing."""

    def test_cannot_view_it(self, scene, bob):
        assert bob.get(f"/api/view/{ALICE.id}/{scene['file_id']}").status_code == 404
        assert bob.get("/api/u/alice/secreto").status_code == 404

    def test_cannot_view_it_claiming_to_be_the_owner_in_the_url(self, scene, bob):
        # The owner id in the URL is only a lookup key; the session decides access.
        assert bob.get(f"/api/view/{BOB.id}/{scene['file_id']}").status_code == 404
        assert bob.get("/api/u/bob/secreto").status_code == 404

    def test_answers_exactly_like_a_file_that_does_not_exist(self, scene, bob):
        real = bob.get(f"/api/view/{ALICE.id}/{scene['file_id']}")
        fake = bob.get(f"/api/view/{ALICE.id}/{'0' * 32}")
        assert (real.status_code, real.json()) == (fake.status_code, fake.json())
        real = bob.get("/api/u/alice/secreto")
        fake = bob.get("/api/u/alice/no-existe")
        assert (real.status_code, real.json()) == (fake.status_code, fake.json())

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("PATCH", "/api/files/{file_id}", {"title": "hackeado"}),
            ("PATCH", "/api/files/{file_id}", {"visibility": "org"}),
            ("PATCH", "/api/files/{file_id}", {"slug": "mio"}),
            ("PATCH", "/api/files/{file_id}", {"labelId": None}),
            ("DELETE", "/api/files/{file_id}", None),
            ("POST", "/api/files/{file_id}/complete", None),
            ("GET", "/api/files/{file_id}/shares", None),
            ("POST", "/api/files/{file_id}/shares", {"expiresInDays": 1}),
            ("DELETE", "/api/shares/{token}", None),
            ("PATCH", "/api/labels/{label_id}", {"name": "hackeada"}),
            ("DELETE", "/api/labels/{label_id}", None),
        ],
    )
    def test_cannot_change_anything(self, scene, alice, bob, method, path, body):
        before = snapshot(alice)
        resp = bob.request(method, path.format(**scene), json=body)
        assert resp.status_code == 404, resp.text
        assert snapshot(alice) == before
        assert alice.get(f"/api/public/shares/{scene['token']}").status_code == 200  # link untouched

    def test_cannot_use_someone_elses_label(self, scene, world, bob):
        mine = upload(world, BOB, "mio.html")
        resp = bob.patch(f"/api/files/{mine.file_id}", json={"labelId": scene["label_id"]})
        assert (resp.status_code, resp.json()["error"]["code"]) == (400, "label_not_found")
        assert bob.get("/api/files").json()["items"][0]["labelId"] is None


class TestOrgFile:
    """Shared with the organization: others may look, never touch."""

    @pytest.fixture
    def org(self, scene, alice):
        alice.patch(f"/api/files/{scene['file_id']}", json={"visibility": "org"})
        return scene

    def test_others_can_view_it(self, org, bob):
        assert bob.get(f"/api/view/{ALICE.id}/{org['file_id']}").status_code == 200
        assert bob.get("/api/u/alice/secreto").status_code == 200

    def test_viewer_does_not_see_how_the_owner_organizes_it(self, org, alice, bob):
        assert alice.get("/api/u/alice/secreto").json()["file"]["labelId"] == org["label_id"]
        assert bob.get("/api/u/alice/secreto").json()["file"]["labelId"] is None

    @pytest.mark.parametrize(
        ("method", "path", "body"),
        [
            ("PATCH", "/api/files/{file_id}", {"title": "hackeado"}),
            ("PATCH", "/api/files/{file_id}", {"visibility": "private"}),
            ("DELETE", "/api/files/{file_id}", None),
            ("GET", "/api/files/{file_id}/shares", None),
            ("POST", "/api/files/{file_id}/shares", {"expiresInDays": 1}),
            ("DELETE", "/api/shares/{token}", None),
        ],
    )
    def test_others_still_cannot_change_it(self, org, alice, bob, method, path, body):
        before = snapshot(alice)
        assert bob.request(method, path.format(**org), json=body).status_code == 404
        assert snapshot(alice) == before

    def test_back_to_private_closes_it_again(self, org, alice, bob):
        alice.patch(f"/api/files/{org['file_id']}", json={"visibility": "private"})
        assert bob.get("/api/u/alice/secreto").status_code == 404


class TestWithoutSession:
    @pytest.mark.parametrize(
        ("method", "path"),
        [
            ("GET", "/api/files"),
            ("POST", "/api/files"),
            ("POST", "/api/files/{file_id}/complete"),
            ("PATCH", "/api/files/{file_id}"),
            ("DELETE", "/api/files/{file_id}"),
            ("GET", "/api/view/alice01/{file_id}"),
            ("GET", "/api/u/alice/secreto"),
            ("GET", "/api/files/{file_id}/shares"),
            ("POST", "/api/files/{file_id}/shares"),
            ("DELETE", "/api/shares/{token}"),
            ("GET", "/api/labels"),
            ("POST", "/api/labels"),
            ("PATCH", "/api/labels/{label_id}"),
            ("DELETE", "/api/labels/{label_id}"),
        ],
    )
    def test_everything_private_requires_login(self, scene, alice, anonymous, method, path):
        before = snapshot(alice)
        resp = anonymous.request(method, path.format(**scene), json={} if method in ("POST", "PATCH") else None)
        assert resp.status_code == 401, (method, path)
        assert snapshot(alice) == before

    def test_only_the_public_link_opens_and_it_hides_identities(self, scene, anonymous):
        for path in (f"/api/public/shares/{scene['token']}", f"/api/public/s/alice/secreto-{scene['token']}"):
            body = anonymous.get(path).json()
            assert set(body["file"]) == {"title", "fileName", "ownerName", "sizeBytes", "updatedAt"}
            assert ALICE.id not in json.dumps(body["file"])

    @pytest.mark.parametrize(
        "principal",
        [
            {"userId": "alice01", "userDetails": "alice@contoso.com", "userRoles": ["anonymous"]},  # not signed in
            {"userId": "alice01", "userDetails": "alice@contoso.com", "userRoles": []},
            {"userId": "alice01", "userDetails": "alice@contoso.com"},
            {"userId": "", "userDetails": "x", "userRoles": ["authenticated"]},
            {"userId": "alice01/../bob02", "userDetails": "x", "userRoles": ["authenticated"]},
            {"userDetails": "alice@contoso.com", "userRoles": ["authenticated"]},
            ["alice01"],
            "alice01",
        ],
    )
    def test_malformed_identity_is_not_a_session(self, scene, anonymous, principal):
        header = base64.b64encode(json.dumps(principal).encode()).decode()
        assert anonymous.get("/api/files", headers={PRINCIPAL_HEADER: header}).status_code == 401

    def test_identity_is_never_taken_from_the_request_itself(self, scene, bob):
        # Only the principal header counts: ids in the body, query or other headers are ignored.
        resp = bob.get("/api/files", params={"ownerId": ALICE.id, "userId": ALICE.id}, headers={"x-user-id": ALICE.id})
        assert resp.json() == {"items": []}
        resp = bob.post("/api/files", json={"fileName": "x.html", "sizeBytes": 5, "ownerId": ALICE.id})
        assert resp.json()["file"]["ownerId"] == BOB.id


class TestNamesDoNotCollideAcrossUsers:
    def test_same_file_name_same_link_name_different_owners(self, world, alice, bob):
        a = upload(world, ALICE, "report.html")
        b = upload(world, BOB, "report.html")
        assert alice.get("/api/u/alice/report").json()["file"]["id"] == a.file_id
        assert bob.get("/api/u/bob/report").json()["file"]["id"] == b.file_id
        assert bob.get("/api/u/alice/report").status_code == 404

    def test_taking_a_link_name_does_not_block_other_users(self, world, alice, bob):
        upload(world, ALICE, "a.html")
        mine = upload(world, BOB, "b.html")
        assert bob.patch(f"/api/files/{mine.file_id}", json={"slug": "a"}).json()["slug"] == "a"

    def test_same_sign_in_name_in_two_domains_never_shares_a_handle(self, world):
        twin = TestClient(app, headers={PRINCIPAL_HEADER: encode_principal("twin99", "alice@fabrikam.com")})
        upload(world, ALICE, "report.html")
        ticket = twin.post("/api/files", json={"fileName": "report.html", "sizeBytes": 5}).json()
        assert ticket["file"]["ownerHandle"] == "alice-2"
        assert twin.get("/api/u/alice/report").status_code == 404  # ALICE's private file
        assert twin.get("/api/files").json() == {"items": []}  # own upload still pending


class TestDeletingMyThingsLeavesOthersAlone:
    def test_delete_file_and_label(self, world, alice, bob):
        mine = upload(world, ALICE, "a.html")
        label = alice.post("/api/labels", json={"name": "Compartido"}).json()
        theirs = upload(world, BOB, "a.html")
        their_label = bob.post("/api/labels", json={"name": "Compartido"}).json()
        bob.patch(f"/api/files/{theirs.file_id}", json={"labelId": their_label["id"]})

        alice.delete(f"/api/labels/{label['id']}")
        alice.delete(f"/api/files/{mine.file_id}")

        item = bob.get("/api/files").json()["items"][0]
        assert (item["id"], item["labelId"]) == (theirs.file_id, their_label["id"])
        assert bob.get("/api/u/bob/a").status_code == 200
