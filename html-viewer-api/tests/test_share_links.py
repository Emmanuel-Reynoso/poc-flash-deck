"""Readable public links: /s/{handle}/{slug}-{token}."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.errors import NotFound
from app.main import app
from app.shares.service import TOKEN_ALPHABET, TOKEN_LENGTH, new_token

from .conftest import ALICE, BOB, upload
from .test_http import as_user


def shared(world, user=ALICE, name="report.html"):
    record = upload(world, user, name)
    return record, world.shares.create(user, record.file_id, expires_in_days=2)


class TestToken:
    def test_shape(self):
        tokens = {new_token() for _ in range(200)}
        assert len(tokens) == 200
        assert all(len(t) == TOKEN_LENGTH and set(t) <= set(TOKEN_ALPHABET) for t in tokens)
        assert "-" not in TOKEN_ALPHABET  # the token is split off the link at the last dash


class TestResolveReadable:
    def test_resolves(self, world):
        record, share = shared(world)
        link = world.shares.resolve_readable("alice", f"report-{share.token}")
        assert link.file.file_id == record.file_id

    def test_slug_with_dashes(self, world):
        record, share = shared(world, name="ventas q3 final.html")
        assert world.shares.resolve_readable("alice", f"ventas-q3-final-{share.token}").file.file_id == record.file_id

    def test_old_style_link_still_works(self, world):
        record, share = shared(world)
        assert world.shares.resolve(share.token).file.file_id == record.file_id

    @pytest.mark.parametrize(
        "path",
        [
            ("alice", "report-AAAAAAAAAAAA"),  # guessed suffix
            ("alice", "report"),  # no suffix at all
            ("alice", "report-"),
            ("alice", "{token}"),  # token without the readable part
            ("alice", "other-{token}"),  # right token, wrong name
            ("bob", "report-{token}"),  # right token, wrong user
            ("nadie", "report-{token}"),
            ("", ""),
        ],
    )
    def test_rejects(self, world, path):
        _, share = shared(world)
        upload(world, BOB, "report.html")
        handle, rest = path
        with pytest.raises(NotFound):
            world.shares.resolve_readable(handle, rest.format(token=share.token))

    def test_knowing_user_and_name_is_not_enough(self, world):
        """The readable part is public knowledge; only the random suffix opens the file."""
        shared(world)
        for guess in ("report-1", "report-2", "report-000000000000", "report-report"):
            with pytest.raises(NotFound):
                world.shares.resolve_readable("alice", guess)

    def test_stops_working_when_the_link_name_changes(self, world):
        record, share = shared(world)
        world.files.update(ALICE, record.file_id, slug="nuevo")
        with pytest.raises(NotFound):
            world.shares.resolve_readable("alice", f"report-{share.token}")
        assert world.shares.resolve_readable("alice", f"nuevo-{share.token}").file.file_id == record.file_id

    def test_expired(self, world):
        _, share = shared(world)
        world.clock.advance(days=3)
        with pytest.raises(NotFound):
            world.shares.resolve_readable("alice", f"report-{share.token}")

    def test_revoked_and_deleted(self, world):
        record, share = shared(world)
        world.shares.revoke(ALICE, share.token)
        with pytest.raises(NotFound):
            world.shares.resolve_readable("alice", f"report-{share.token}")

        record, share = shared(world, name="otro.html")
        world.files.delete(ALICE, record.file_id)
        with pytest.raises(NotFound):
            world.shares.resolve_readable("alice", f"otro-{share.token}")


class TestHttp:
    def test_anonymous_can_open_it_and_sees_no_ids(self, world):
        _, share = shared(world)
        resp = TestClient(app).get(f"/api/public/s/alice/report-{share.token}")
        assert resp.status_code == 200
        assert set(resp.json()["file"]) == {"title", "fileName", "ownerName", "sizeBytes", "updatedAt"}

    def test_wrong_suffix_is_404(self, world):
        shared(world)
        resp = TestClient(app).get("/api/public/s/alice/report-AAAAAAAAAAAA")
        assert (resp.status_code, resp.json()["error"]["code"]) == (404, "not_found")

    def test_created_token_is_short_and_alphanumeric(self, world):
        record = upload(world)
        client = TestClient(app, headers=as_user(ALICE))
        token = client.post(f"/api/files/{record.file_id}/shares", json={"expiresInDays": 1}).json()["token"]
        assert len(token) == TOKEN_LENGTH and token.isalnum()
