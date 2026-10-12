"""End-to-end against Azurite: real Table Storage, real Blob Storage, real SAS.

Run with Azurite listening locally:  RUN_AZURITE_TESTS=1 pytest -k azurite
"""

from __future__ import annotations

import os
import uuid

import pytest
import requests
from azure.data.tables import TableServiceClient
from azure.storage.blob import BlobServiceClient
from fastapi.testclient import TestClient

from app.auth.models import User
from app.core.container import build_services
from app.core.errors import BadRequest, NotFound

from app.auth.principal import PRINCIPAL_HEADER, encode_principal
from app.core import container
from app.main import app

from .fakes import make_settings

pytestmark = pytest.mark.skipif(not os.getenv("RUN_AZURITE_TESTS"), reason="needs Azurite (RUN_AZURITE_TESTS=1)")

HTML = "<!doctype html><title>Reporte</title><h1>Ventas Q3 – ñandú</h1><script>document.title='ok'</script>"


@pytest.fixture
def services():
    """Its own container and tables, removed afterwards so runs leave nothing behind."""
    suffix = uuid.uuid4().hex[:8]
    settings = make_settings(
        connection_string=os.getenv("STORAGE_CONNECTION_STRING", "UseDevelopmentStorage=true"),
        container_name=f"html{suffix}",
        files_table=f"files{suffix}",
        shares_table=f"shares{suffix}",
        users_table=f"users{suffix}",
        slugs_table=f"slugs{suffix}",
        labels_table=f"labels{suffix}",
        max_upload_bytes=1024 * 1024,
        auto_create_resources=True,
    )
    yield build_services(settings)

    BlobServiceClient.from_connection_string(settings.connection_string).delete_container(settings.container_name)
    tables = TableServiceClient.from_connection_string(settings.connection_string)
    for name in settings.table_names:
        tables.delete_table(name)


def test_full_flow(services):
    user = User(id=uuid.uuid4().hex, name="emma@contoso.com")
    body = HTML.encode()

    ticket = services.files.start_upload(user, file_name="Reporte Q3.html", size_bytes=len(body))

    # Browser-side upload straight to Blob Storage with the SAS.
    put = requests.put(
        ticket.upload_url,
        data=body,
        headers={**ticket.required_headers, "Content-Type": "application/octet-stream"},
        timeout=10,
    )
    assert put.status_code == 201, put.text

    ready = services.files.complete_upload(user, ticket.file.file_id)
    assert ready.size_bytes == len(body)
    assert [f.file_id for f in services.files.list_files(user)] == [ready.file_id]

    link = services.files.view(user, user.id, ready.file_id)
    got = requests.get(link.view_url, timeout=10)
    assert got.status_code == 200
    assert got.headers["Content-Type"].startswith("text/html")
    assert got.headers.get("Content-Disposition") == "inline"
    assert got.content == body

    dl = requests.get(link.download_url, timeout=10)
    assert dl.headers["Content-Disposition"].startswith("attachment")

    # The upload SAS cannot be used to read, and the read SAS cannot write.
    assert requests.get(ticket.upload_url, timeout=10).status_code == 403
    assert requests.put(link.view_url, data=b"x", headers={"x-ms-blob-type": "BlockBlob"}, timeout=10).status_code == 403

    share = services.shares.create(user, ready.file_id, expires_in_days=2)
    assert services.shares.list_for_file(user, ready.file_id)[0].token == share.token
    public = services.shares.resolve(share.token)
    assert requests.get(public.view_url, timeout=10).content == body

    services.files.delete(user, ready.file_id)
    assert services.files.list_files(user) == []
    assert requests.get(link.view_url, timeout=10).status_code == 404
    with pytest.raises(Exception):
        services.shares.resolve(share.token)


def test_purge_pending(services):
    user = User(id=uuid.uuid4().hex, name="x")
    services.files.start_upload(user, file_name="a.html", size_bytes=10)
    # Nothing is stale yet.
    assert services.files.purge_stale_pending() == 0


def test_links_labels_and_isolation(services):
    """The same rules as the unit tests, against real tables."""
    suffix = uuid.uuid4().hex[:6]
    ana = User(id=uuid.uuid4().hex, name=f"ana{suffix}@contoso.com")
    twin = User(id=uuid.uuid4().hex, name=f"ana{suffix}@fabrikam.com")
    body = HTML.encode()

    def put(user, name):
        ticket = services.files.start_upload(user, file_name=name, size_bytes=len(body))
        requests.put(ticket.upload_url, data=body, headers=ticket.required_headers, timeout=10).raise_for_status()
        return services.files.complete_upload(user, ticket.file.file_id)

    first, second, other = put(ana, "Ventas Q3.html"), put(ana, "Ventas Q3.html"), put(twin, "Ventas Q3.html")
    assert (first.owner_handle, first.slug, second.slug) == (f"ana{suffix}", "ventas-q3", "ventas-q3-2")
    assert (other.owner_handle, other.slug) == (f"ana{suffix}-2", "ventas-q3")

    assert services.files.view_by_slug(ana, first.owner_handle, "ventas-q3").file.file_id == first.file_id
    with pytest.raises(NotFound):
        services.files.view_by_slug(twin, first.owner_handle, "ventas-q3")  # private, other user

    label = services.labels.create(ana, name="Proyecto")
    assert services.files.update(ana, first.file_id, label_id=label.label_id).label_id == label.label_id
    assert services.labels.list(twin) == []
    with pytest.raises(BadRequest):
        services.files.update(twin, other.file_id, label_id=label.label_id)  # not their label
    with pytest.raises(NotFound):
        services.labels.delete(twin, label.label_id)

    share = services.shares.create(ana, first.file_id, expires_in_days=1)
    public = services.shares.resolve_readable(first.owner_handle, f"ventas-q3-{share.token}")
    assert requests.get(public.view_url, timeout=10).content == body
    with pytest.raises(NotFound):
        services.shares.resolve_readable(other.owner_handle, f"ventas-q3-{share.token}")

    services.labels.delete(ana, label.label_id)
    assert [f.label_id for f in services.files.list_files(ana)] == [None, None]
    assert [f.file_id for f in services.files.list_files(twin)] == [other.file_id]


# --- over HTTP, with real storage behind -----------------------------------


def client_for(user: User | None) -> TestClient:
    headers = {PRINCIPAL_HEADER: encode_principal(user.id, user.name)} if user else {}
    return TestClient(app, headers=headers, raise_server_exceptions=False)


@pytest.fixture
def api(services):
    container.set_services(services)
    yield services
    container.set_services(None)


def http_upload(client: TestClient, name: str, body: bytes) -> dict:
    ticket = client.post("/api/files", json={"fileName": name, "sizeBytes": len(body)}).json()
    requests.put(ticket["uploadUrl"], data=body, headers=ticket["requiredHeaders"], timeout=10).raise_for_status()
    resp = client.post(f"/api/files/{ticket['file']['id']}/complete")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_every_endpoint_end_to_end(api):
    suffix = uuid.uuid4().hex[:6]
    ana = User(id=uuid.uuid4().hex, name=f"ana{suffix}@contoso.com")
    beto = User(id=uuid.uuid4().hex, name=f"beto{suffix}@contoso.com")
    a, b, anonymous = client_for(ana), client_for(beto), client_for(None)
    body = HTML.encode()

    # upload, list, readable link
    file = http_upload(a, "Ventas Q3.html", body)
    assert (file["ownerHandle"], file["slug"], file["status"]) == (f"ana{suffix}", "ventas-q3", "ready")
    assert [f["id"] for f in a.get("/api/files").json()["items"]] == [file["id"]]
    link = f"/api/u/ana{suffix}/ventas-q3"
    view = a.get(link).json()
    assert requests.get(view["viewUrl"], timeout=10).content == body
    assert a.get(f"/api/view/{ana.id}/{file['id']}").json()["file"]["id"] == file["id"]

    # the other user and the anonymous one get nothing
    assert b.get("/api/files").json() == {"items": []}
    assert b.get(link).status_code == 404
    assert b.get(f"/api/view/{ana.id}/{file['id']}").status_code == 404
    assert b.patch(f"/api/files/{file['id']}", json={"title": "x"}).status_code == 404
    assert b.delete(f"/api/files/{file['id']}").status_code == 404
    assert anonymous.get(link).status_code == 401
    assert anonymous.get("/api/files").status_code == 401

    # rename, edit link, visibility
    assert a.patch(f"/api/files/{file['id']}", json={"title": "Ventas"}).json()["slug"] == "ventas-q3"
    assert a.patch(f"/api/files/{file['id']}", json={"slug": "Informe Final"}).json()["slug"] == "informe-final"
    assert a.get(link).status_code == 404
    link = f"/api/u/ana{suffix}/informe-final"
    assert a.get(link).status_code == 200
    second = http_upload(a, "otro.html", body)
    resp = a.patch(f"/api/files/{second['id']}", json={"slug": "informe-final"})
    assert (resp.status_code, resp.json()["error"]["code"]) == (409, "slug_taken")
    a.patch(f"/api/files/{file['id']}", json={"visibility": "org"})
    assert b.get(link).status_code == 200
    assert b.get("/api/files").json() == {"items": []}
    a.patch(f"/api/files/{file['id']}", json={"visibility": "private"})
    assert b.get(link).status_code == 404

    # labels
    label = a.post("/api/labels", json={"name": "Proyecto"}).json()
    assert a.post("/api/labels", json={"name": "proyecto"}).status_code == 409
    assert a.patch(f"/api/files/{file['id']}", json={"labelId": label["id"]}).json()["labelId"] == label["id"]
    assert b.get("/api/labels").json() == {"items": []}
    assert b.patch(f"/api/labels/{label['id']}", json={"name": "x"}).status_code == 404
    assert b.delete(f"/api/labels/{label['id']}").status_code == 404
    mine = http_upload(b, "mio.html", body)
    assert b.patch(f"/api/files/{mine['id']}", json={"labelId": label["id"]}).status_code == 400
    assert a.patch(f"/api/labels/{label['id']}", json={"name": "Cliente"}).json()["name"] == "Cliente"
    assert a.delete(f"/api/labels/{label['id']}").status_code == 204
    assert {f["labelId"] for f in a.get("/api/files").json()["items"]} == {None}

    # public links
    token = a.post(f"/api/files/{file['id']}/shares", json={"expiresInDays": 1}).json()["token"]
    assert [s["token"] for s in a.get(f"/api/files/{file['id']}/shares").json()["items"]] == [token]
    assert b.get(f"/api/files/{file['id']}/shares").status_code == 404
    public = anonymous.get(f"/api/public/s/ana{suffix}/informe-final-{token}")
    assert public.status_code == 200 and "ownerId" not in public.json()["file"]
    assert requests.get(public.json()["viewUrl"], timeout=10).content == body
    assert anonymous.get(f"/api/public/shares/{token}").status_code == 200
    assert anonymous.get(f"/api/public/s/ana{suffix}/informe-final-{'A' * 12}").status_code == 404
    assert anonymous.get(f"/api/public/s/beto{suffix}/informe-final-{token}").status_code == 404
    assert b.delete(f"/api/shares/{token}").status_code == 404
    assert a.delete(f"/api/shares/{token}").status_code == 204
    assert anonymous.get(f"/api/public/s/ana{suffix}/informe-final-{token}").status_code == 404

    # delete
    token = a.post(f"/api/files/{file['id']}/shares", json={"expiresInDays": 1}).json()["token"]
    assert a.delete(f"/api/files/{file['id']}").status_code == 204
    assert a.get(link).status_code == 404
    assert anonymous.get(f"/api/public/shares/{token}").status_code == 404
    assert requests.get(view["viewUrl"], timeout=10).status_code == 404
    assert [f["id"] for f in a.get("/api/files").json()["items"]] == [second["id"]]
    assert [f["id"] for f in b.get("/api/files").json()["items"]] == [mine["id"]]
    # the freed link name can be used again
    assert a.patch(f"/api/files/{second['id']}", json={"slug": "informe-final"}).json()["slug"] == "informe-final"


def test_three_uploads_at_once_with_the_same_name(api):
    """The web uploads up to three files in parallel: each must get its own link name."""
    from concurrent.futures import ThreadPoolExecutor

    user = User(id=uuid.uuid4().hex, name=f"par{uuid.uuid4().hex[:6]}@contoso.com")
    client = client_for(user)
    with ThreadPoolExecutor(max_workers=6) as pool:
        files = list(pool.map(lambda _: http_upload(client, "reporte.html", HTML.encode()), range(6)))
    assert sorted(f["slug"] for f in files) == ["reporte", "reporte-2", "reporte-3", "reporte-4", "reporte-5", "reporte-6"]
    assert len({f["ownerHandle"] for f in files}) == 1


@pytest.mark.parametrize("columns", [{}, {"slug": "", "ownerHandle": "", "labelId": ""}], ids=["absent", "empty"])
def test_row_stored_before_readable_links(api, columns):
    """A real row as the previous version wrote it, with or without the new columns."""
    settings = api.settings
    user = User(id=uuid.uuid4().hex, name=f"vieja{uuid.uuid4().hex[:6]}@contoso.com")
    handle = user.name.split("@")[0]
    client = client_for(user)
    body = HTML.encode()

    current = http_upload(client, "JEV en acción.html", body)
    tables = TableServiceClient.from_connection_string(settings.connection_string)
    files_table = tables.get_table_client(settings.files_table)
    row = dict(files_table.get_entity(user.id, current["id"]))
    for name in ("slug", "ownerHandle", "labelId"):
        row.pop(name)
    files_table.upsert_entity({**row, **columns}, mode="replace")
    tables.get_table_client(settings.slugs_table).delete_entity(user.id, "jev-en-accion")
    users_table = tables.get_table_client(settings.users_table)
    users_table.delete_entity("owner", user.id)
    users_table.delete_entity("handle", handle)

    # First thing the page does is list. The old file comes back with a working link.
    (item,) = client.get("/api/files").json()["items"]
    assert (item["id"], item["ownerHandle"], item["slug"]) == (current["id"], handle, "jev-en-accion")
    view = client.get(f"/api/u/{handle}/jev-en-accion")
    assert view.status_code == 200
    assert requests.get(view.json()["viewUrl"], timeout=10).content == body

    # Edit link, exactly what failed in the browser.
    edited = client.patch(f"/api/files/{current['id']}", json={"slug": "induccion a jev"}).json()
    assert (edited["ownerHandle"], edited["slug"]) == (handle, "induccion-a-jev")
    assert client.get(f"/api/u/{handle}/induccion-a-jev").status_code == 200
    assert client.get(f"/api/u/{handle}/jev-en-accion").status_code == 404

    # And it is private like any other file.
    other = client_for(User(id=uuid.uuid4().hex, name="otra@contoso.com"))
    assert other.get(f"/api/u/{handle}/induccion-a-jev").status_code == 404


def test_simultaneous_changes_to_one_file_are_all_kept(api):
    """Real table, real threads: rename, visibility and label at the same instant, many times over."""
    from concurrent.futures import ThreadPoolExecutor

    user = User(id=uuid.uuid4().hex, name=f"sim{uuid.uuid4().hex[:6]}@contoso.com")
    client = client_for(user)
    file = http_upload(client, "reporte.html", HTML.encode())
    label = client.post("/api/labels", json={"name": "Alfa"}).json()
    path = f"/api/files/{file['id']}"

    for round_number in range(8):
        title = f"Título {round_number}"
        visibility = "org" if round_number % 2 == 0 else "private"
        label_id = label["id"] if round_number % 2 == 0 else None
        bodies = [{"title": title}, {"visibility": visibility}, {"labelId": label_id}]
        with ThreadPoolExecutor(max_workers=3) as pool:
            statuses = [r.status_code for r in pool.map(lambda body: client.patch(path, json=body), bodies)]
        assert statuses == [200, 200, 200]

        (stored,) = client.get("/api/files").json()["items"]
        assert (stored["title"], stored["visibility"], stored["labelId"]) == (title, visibility, label_id)


def test_simultaneous_link_names_leave_one_reserved(api):
    from concurrent.futures import ThreadPoolExecutor

    user = User(id=uuid.uuid4().hex, name=f"lnk{uuid.uuid4().hex[:6]}@contoso.com")
    client = client_for(user)
    file = http_upload(client, "reporte.html", HTML.encode())
    names = [f"nombre-{n}" for n in range(5)]

    with ThreadPoolExecutor(max_workers=5) as pool:
        results = list(pool.map(lambda name: client.patch(f"/api/files/{file['id']}", json={"slug": name}), names))
    assert {r.status_code for r in results} <= {200, 409}
    assert any(r.status_code == 200 for r in results)

    (stored,) = client.get("/api/files").json()["items"]
    assert stored["slug"] in names
    tables = TableServiceClient.from_connection_string(api.settings.connection_string)
    reserved = [e["RowKey"] for e in tables.get_table_client(api.settings.slugs_table).query_entities(
        "PartitionKey eq @owner", parameters={"owner": user.id})]
    assert reserved == [stored["slug"]]  # no name left taken by a change that lost
    handle = user.name.split("@")[0]
    assert client.get(f"/api/u/{handle}/{stored['slug']}").status_code == 200


def test_update_after_delete_does_not_bring_the_file_back(api):
    user = User(id=uuid.uuid4().hex, name=f"del{uuid.uuid4().hex[:6]}@contoso.com")
    client = client_for(user)
    file = http_upload(client, "reporte.html", HTML.encode())
    stale = api.files.list_files(user)[0]

    assert client.delete(f"/api/files/{file['id']}").status_code == 204
    from dataclasses import replace as dc_replace

    tables = TableServiceClient.from_connection_string(api.settings.connection_string)
    from app.files.repository import TableFileRepository

    repo = TableFileRepository(tables.get_table_client(api.settings.files_table))
    assert repo.update(dc_replace(stale, title="zombi")) is False
    assert client.get("/api/files").json() == {"items": []}
