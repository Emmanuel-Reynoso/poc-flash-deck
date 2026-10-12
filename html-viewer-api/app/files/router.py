"""HTTP endpoints for files. Thin: parse input, call the service, shape the output."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ..auth.dependencies import CurrentUser
from ..core.container import ServicesDep
from .service import UNSET
from .schemas import (
    CreateUploadRequest,
    FileListResponse,
    FileResponse,
    UpdateFileRequest,
    UploadTicketResponse,
    ViewResponse,
)

router = APIRouter(tags=["files"])


@router.get("/files", response_model=FileListResponse, summary="List my files")
def list_files(user: CurrentUser, services: ServicesDep) -> FileListResponse:
    return FileListResponse(items=[FileResponse.of(r) for r in services.files.list_files(user)])


@router.post(
    "/files",
    response_model=UploadTicketResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Request an upload ticket",
)
def create_upload(body: CreateUploadRequest, user: CurrentUser, services: ServicesDep) -> UploadTicketResponse:
    ticket = services.files.start_upload(user, file_name=body.file_name, size_bytes=body.size_bytes, title=body.title)
    return UploadTicketResponse.of(ticket)


@router.post("/files/{file_id}/complete", response_model=FileResponse, summary="Confirm an upload")
def complete_upload(file_id: str, user: CurrentUser, services: ServicesDep) -> FileResponse:
    return FileResponse.of(services.files.complete_upload(user, file_id))


@router.patch("/files/{file_id}", response_model=FileResponse, summary="Change title, visibility, link name or label")
def update_file(file_id: str, body: UpdateFileRequest, user: CurrentUser, services: ServicesDep) -> FileResponse:
    record = services.files.update(
        user,
        file_id,
        title=body.title,
        visibility=body.visibility,
        slug=body.slug,
        label_id=body.label_id if "label_id" in body.model_fields_set else UNSET,
    )
    return FileResponse.of(record)


@router.delete("/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT, summary="Delete a file and its links")
def delete_file(file_id: str, user: CurrentUser, services: ServicesDep) -> Response:
    services.files.delete(user, file_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/view/{owner_id}/{file_id}",
    response_model=ViewResponse,
    summary="Get short-lived links to view a file",
)
def view_file(owner_id: str, file_id: str, user: CurrentUser, services: ServicesDep) -> ViewResponse:
    return ViewResponse.of(services.files.view(user, owner_id, file_id), viewer_id=user.id)


@router.get("/u/{handle}/{slug}", response_model=ViewResponse, summary="Same as view, by readable link")
def view_file_by_slug(handle: str, slug: str, user: CurrentUser, services: ServicesDep) -> ViewResponse:
    return ViewResponse.of(services.files.view_by_slug(user, handle, slug), viewer_id=user.id)
