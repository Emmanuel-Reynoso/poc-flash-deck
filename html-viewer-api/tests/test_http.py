from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.auth.principal import PRINCIPAL_HEADER, encode_principal, parse_principal
from app.main import app

from .conftest import ALICE, BOB, upload


def as_user(user) -> dict[str, str]:
    return {PRINCIPAL_HEADER: encode_principal(user.id, user.name)} if user else {}


@pytest.fixture
def client(world) -> TestClient:
    return TestClient(app, headers=as_user(ALICE), raise_server_exceptions=False)


class TestPrincipal:
    def test_rejects_garbage_and_anonymous(self):
        assert parse_principal({PRINCIPAL_HEADER: "%%%"}) is None
        assert parse_principal({PRINCIPAL_HEADER: encode_principal("u1", "x", roles=["anonymous"])}) is None
        assert parse_principal({PRINCIPAL_HEADER: encode_principal("../etc", "x")}) is None

    def test_accepts_authenticated(self):
        user = parse_principal({PRINCIPAL_HEADER: encode_principal("abc123", "a@b.com")})
        assert user is not None and user.id == "abc123"


class TestEndpoints:
    def test_requires_login(self, world):
        anonymous = TestClient(app)
        for method, path in [
            ("GET", "/api/files"),
            ("POST", "/api/files"),
            ("POST", "/api/files/x/complete"),
            ("PATCH", "/api/files/x"),
            ("DELETE", "/api/files/x"),
            ("GET", "/api/view/o/x"),
            ("GET", "/api/files/x/shares"),
            ("POST", "/api/files/x/shares"),
            ("DELETE", "/api/shares/t"),
        ]:
            resp = anonymous.request(method, path, json={} if method in ("POST", "PATCH") else None)
            assert resp.status_code == 401, (method, path)
            assert resp.json()["error"]["code"] == "unauthorized"

    def test_upload_flow(self, world, client):
        resp = client.post("/api/files", json={"fileName": "kpi.html", "sizeBytes": 50})
        assert resp.status_code == 201
        ticket = resp.json()
        file_id = ticket["file"]["id"]
        assert ticket["uploadUrl"].startswith("https://")
        assert ticket["requiredHeaders"]["x-ms-blob-type"] == "BlockBlob"
        assert ticket["file"]["createdAt"].endswith("Z")

        assert client.post(f"/api/files/{file_id}/complete").status_code == 409  # blob not uploaded yet

        world.blobs.blobs[f"{ALICE.id}/{file_id}.html"] = 50
        resp = client.post(f"/api/files/{file_id}/complete")
        assert resp.json()["status"] == "ready"
        assert resp.headers["Cache-Control"] == "no-store"

        items = client.get("/api/files").json()["items"]
        assert [i["id"] for i in items] == [file_id]
        assert set(items[0]) == {
            "id", "ownerId", "ownerName", "fileName", "title", "sizeBytes",
            "visibility", "status", "createdAt", "updatedAt", "slug", "ownerHandle", "labelId",
        }  # fmt: skip

    def test_bad_json(self, client):
        resp = client.post("/api/files", content=b"{not json", headers={"Content-Type": "application/json"})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    @pytest.mark.parametrize(
        "body",
        [{}, {"fileName": "a.html"}, {"fileName": "a.html", "sizeBytes": "5"}, {"fileName": 7, "sizeBytes": 5}, []],
    )
    def test_invalid_body_is_400(self, client, body):
        resp = client.post("/api/files", json=body)
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "bad_request"

    def test_wrong_type_is_400(self, client):
        resp = client.post("/api/files", json={"fileName": "x.pdf", "sizeBytes": 5})
        assert resp.status_code == 400
        assert resp.json()["error"]["code"] == "unsupported_type"

    def test_view_and_visibility(self, world, client):
        record = upload(world)
        path = f"/api/view/{ALICE.id}/{record.file_id}"
        assert client.get(path, headers=as_user(BOB)).status_code == 404

        assert client.patch(f"/api/files/{record.file_id}", json={"visibility": "nope"}).status_code == 400
        assert client.patch(f"/api/files/{record.file_id}", json={"visibility": "org"}).json()["visibility"] == "org"
        resp = client.get(path, headers=as_user(BOB))
        assert resp.status_code == 200
        assert resp.json()["viewUrl"]

    def test_cannot_touch_other_users_files(self, world, client):
        record = upload(world)
        bob = as_user(BOB)
        assert client.patch(f"/api/files/{record.file_id}", json={"title": "x"}, headers=bob).status_code == 404
        assert client.delete(f"/api/files/{record.file_id}", headers=bob).status_code == 404
        assert client.post(f"/api/files/{record.file_id}/shares", json={}, headers=bob).status_code == 404

    def test_public_share_hides_owner_id(self, world, client):
        record = upload(world)
        resp = client.post(f"/api/files/{record.file_id}/shares", json={"expiresInDays": 2})
        assert resp.status_code == 201
        token = resp.json()["token"]
        assert [s["token"] for s in client.get(f"/api/files/{record.file_id}/shares").json()["items"]] == [token]

        anonymous = TestClient(app)
        resp = anonymous.get(f"/api/public/shares/{token}")
        body = resp.json()
        assert resp.status_code == 200
        assert "ownerId" not in body["file"] and "id" not in body["file"]

        assert client.delete(f"/api/shares/{token}", headers=as_user(BOB)).status_code == 404
        assert client.delete(f"/api/shares/{token}").status_code == 204
        assert anonymous.get(f"/api/public/shares/{token}").status_code == 404

    def test_share_defaults_and_limits(self, world, client):
        record = upload(world)
        assert client.post(f"/api/files/{record.file_id}/shares").status_code == 201  # no body: 7 days
        assert client.post(f"/api/files/{record.file_id}/shares", json={"expiresInDays": 999}).status_code == 400

    def test_delete(self, world, client):
        record = upload(world)
        assert client.delete(f"/api/files/{record.file_id}").status_code == 204
        assert client.delete(f"/api/files/{record.file_id}").status_code == 404

    def test_unexpected_errors_do_not_leak(self, world, client, monkeypatch):
        def boom(*_a, **_k):
            raise RuntimeError("secret connection string")

        monkeypatch.setattr(world.files, "list_files", boom)
        resp = client.get("/api/files")
        assert resp.status_code == 500
        assert resp.json()["error"]["code"] == "internal_error"
        assert "secret" not in resp.text

    def test_unknown_route_uses_error_shape(self, client):
        resp = client.get("/api/nope")
        assert resp.status_code == 404
        assert resp.json()["error"]["code"] == "not_found"

    def test_health_is_public(self):
        assert TestClient(app).get("/api/public/health").json() == {"status": "ok"}


def test_function_app_hosts_fastapi_and_jobs():
    import function_app

    names = {f.get_function_name() for f in function_app.app.get_functions()}
    assert "purge_stale_uploads" in names
    assert len(names) == 2  # ASGI catch-all + timer
