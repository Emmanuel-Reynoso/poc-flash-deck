"""Labels: the headers a user groups their files under."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import BadRequest, Conflict, NotFound
from app.main import app

from .conftest import ALICE, BOB, upload
from .test_http import as_user


class TestLabelService:
    def test_create_and_list_in_creation_order(self, world):
        first = world.labels.create(ALICE, name="  Proyecto   Alfa ")
        world.clock.advance(minutes=1)
        second = world.labels.create(ALICE, name="Beta")
        assert first.name == "Proyecto Alfa"
        assert world.labels.list(ALICE) == [first, second]

    @pytest.mark.parametrize("bad", ["", "   ", None, 5, "x" * 51])
    def test_invalid_name(self, world, bad):
        with pytest.raises(BadRequest):
            world.labels.create(ALICE, name=bad)

    def test_name_is_unique_per_user_ignoring_case(self, world):
        world.labels.create(ALICE, name="Ventas")
        with pytest.raises(Conflict) as err:
            world.labels.create(ALICE, name="VENTAS")
        assert err.value.code == "label_exists"
        assert world.labels.create(BOB, name="Ventas").name == "Ventas"  # other users are unaffected

    def test_limit(self, world):
        for n in range(100):
            world.labels.create(ALICE, name=f"L{n}")
        with pytest.raises(Conflict) as err:
            world.labels.create(ALICE, name="one too many")
        assert err.value.code == "label_limit"

    def test_rename(self, world):
        label = world.labels.create(ALICE, name="Alfa")
        world.labels.create(ALICE, name="Beta")
        assert world.labels.rename(ALICE, label.label_id, name="Gamma").name == "Gamma"
        assert world.labels.rename(ALICE, label.label_id, name="gamma").name == "gamma"  # own name, new case
        with pytest.raises(Conflict):
            world.labels.rename(ALICE, label.label_id, name="beta")

    def test_delete_keeps_the_files_unlabeled(self, world):
        label = world.labels.create(ALICE, name="Alfa")
        other = world.labels.create(ALICE, name="Beta")
        in_label = world.files.update(ALICE, upload(world, name="a.html").file_id, label_id=label.label_id)
        in_other = world.files.update(ALICE, upload(world, name="b.html").file_id, label_id=other.label_id)

        world.labels.delete(ALICE, label.label_id)

        by_id = {f.file_id: f for f in world.files.list_files(ALICE)}
        assert by_id[in_label.file_id].label_id is None
        assert by_id[in_other.file_id].label_id == other.label_id
        assert world.labels.list(ALICE) == [other]

    @pytest.mark.parametrize("label_id", ["nope", "0" * 32, "../x", ""])
    def test_unknown_label(self, world, label_id):
        with pytest.raises(NotFound):
            world.labels.rename(ALICE, label_id, name="x")
        with pytest.raises(NotFound):
            world.labels.delete(ALICE, label_id)


class TestAssignLabel:
    def test_move_between_labels_and_out(self, world):
        alfa = world.labels.create(ALICE, name="Alfa")
        beta = world.labels.create(ALICE, name="Beta")
        record = upload(world)
        assert record.label_id is None

        assert world.files.update(ALICE, record.file_id, label_id=alfa.label_id).label_id == alfa.label_id
        assert world.files.update(ALICE, record.file_id, label_id=beta.label_id).label_id == beta.label_id
        assert world.files.update(ALICE, record.file_id, title="New").label_id == beta.label_id  # untouched
        assert world.files.update(ALICE, record.file_id, label_id=None).label_id is None

    @pytest.mark.parametrize("label_id", ["nope", "0" * 32, 5, ""])
    def test_unknown_label_is_rejected(self, world, label_id):
        record = upload(world)
        with pytest.raises(BadRequest) as err:
            world.files.update(ALICE, record.file_id, label_id=label_id)
        assert err.value.code == "label_not_found"


class TestHttp:
    @pytest.fixture
    def client(self, world) -> TestClient:
        return TestClient(app, headers=as_user(ALICE), raise_server_exceptions=False)

    def test_crud(self, client):
        resp = client.post("/api/labels", json={"name": "Proyecto Alfa"})
        assert resp.status_code == 201
        label = resp.json()
        assert set(label) == {"id", "name", "createdAt"}

        assert client.get("/api/labels").json() == {"items": [label]}
        assert client.patch(f"/api/labels/{label['id']}", json={"name": "Beta"}).json()["name"] == "Beta"
        resp = client.post("/api/labels", json={"name": "beta"})
        assert (resp.status_code, resp.json()["error"]["code"]) == (409, "label_exists")
        assert client.delete(f"/api/labels/{label['id']}").status_code == 204
        assert client.delete(f"/api/labels/{label['id']}").status_code == 404
        assert client.get("/api/labels").json() == {"items": []}

    @pytest.mark.parametrize("body", [{}, {"name": ""}, {"name": 5}, {"name": "x" * 51}])
    def test_invalid_body(self, client, body):
        assert client.post("/api/labels", json=body).status_code == 400

    def test_requires_login(self, world):
        anonymous = TestClient(app)
        assert anonymous.get("/api/labels").status_code == 401
        assert anonymous.post("/api/labels", json={"name": "x"}).status_code == 401
        assert anonymous.patch("/api/labels/x", json={"name": "x"}).status_code == 401
        assert anonymous.delete("/api/labels/x").status_code == 401

    def test_assign_and_clear_through_the_api(self, world, client):
        label = client.post("/api/labels", json={"name": "Alfa"}).json()
        record = upload(world)
        path = f"/api/files/{record.file_id}"

        assert client.patch(path, json={"labelId": label["id"]}).json()["labelId"] == label["id"]
        assert client.patch(path, json={"title": "Otro"}).json()["labelId"] == label["id"]  # not sent: kept
        assert client.patch(path, json={"labelId": None}).json()["labelId"] is None  # null: cleared

        resp = client.patch(path, json={"labelId": "0" * 32})
        assert (resp.status_code, resp.json()["error"]["code"]) == (400, "label_not_found")
