"""HTTP endpoints for public share links."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ..auth.dependencies import CurrentUser
from ..core.container import ServicesDep
from ..files.schemas import PublicViewResponse
from .schemas import CreateShareRequest, ShareListResponse, ShareResponse

router = APIRouter(tags=["shares"])


@router.get("/files/{file_id}/shares", response_model=ShareListResponse, summary="List active links of a file")
def list_shares(file_id: str, user: CurrentUser, services: ServicesDep) -> ShareListResponse:
    return ShareListResponse(items=[ShareResponse.of(s) for s in services.shares.list_for_file(user, file_id)])


@router.post(
    "/files/{file_id}/shares",
    response_model=ShareResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a public link",
)
def create_share(
    file_id: str,
    user: CurrentUser,
    services: ServicesDep,
    body: CreateShareRequest | None = None,
) -> ShareResponse:
    body = body or CreateShareRequest()
    return ShareResponse.of(services.shares.create(user, file_id, expires_in_days=body.expires_in_days))


@router.delete("/shares/{token}", status_code=status.HTTP_204_NO_CONTENT, summary="Revoke a public link")
def revoke_share(token: str, user: CurrentUser, services: ServicesDep) -> Response:
    services.shares.revoke(user, token)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/public/shares/{token}", response_model=PublicViewResponse, summary="Open a public link")
def resolve_public_share(token: str, services: ServicesDep) -> PublicViewResponse:
    # Anonymous by design: the unguessable token is the credential.
    return PublicViewResponse.of(services.shares.resolve(token))


@router.get(
    "/public/s/{handle}/{slug_and_token}",
    response_model=PublicViewResponse,
    summary="Open a public link by its readable form",
)
def resolve_readable_share(handle: str, slug_and_token: str, services: ServicesDep) -> PublicViewResponse:
    return PublicViewResponse.of(services.shares.resolve_readable(handle, slug_and_token))
