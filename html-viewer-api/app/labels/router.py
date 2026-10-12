"""HTTP endpoints for labels."""

from __future__ import annotations

from fastapi import APIRouter, Response, status

from ..auth.dependencies import CurrentUser
from ..core.container import ServicesDep
from .schemas import LabelListResponse, LabelNameRequest, LabelResponse

router = APIRouter(tags=["labels"])


@router.get("/labels", response_model=LabelListResponse, summary="List my labels")
def list_labels(user: CurrentUser, services: ServicesDep) -> LabelListResponse:
    return LabelListResponse(items=[LabelResponse.of(label) for label in services.labels.list(user)])


@router.post("/labels", response_model=LabelResponse, status_code=status.HTTP_201_CREATED, summary="Create a label")
def create_label(body: LabelNameRequest, user: CurrentUser, services: ServicesDep) -> LabelResponse:
    return LabelResponse.of(services.labels.create(user, name=body.name))


@router.patch("/labels/{label_id}", response_model=LabelResponse, summary="Rename a label")
def rename_label(label_id: str, body: LabelNameRequest, user: CurrentUser, services: ServicesDep) -> LabelResponse:
    return LabelResponse.of(services.labels.rename(user, label_id, name=body.name))


@router.delete(
    "/labels/{label_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a label (its files are kept, unlabeled)",
)
def delete_label(label_id: str, user: CurrentUser, services: ServicesDep) -> Response:
    services.labels.delete(user, label_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
